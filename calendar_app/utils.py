from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from datetime import datetime, timedelta

from .models import CalendarEvent, CalendarSettings

User = get_user_model()


def get_user_events(user, settings):
    """
    Kullanıcının yetkisine göre etkinlikleri döndürür.
    Sadece o kullanıcıya ait etkinlikleri gösterir.
    """
    # SADECE o kullanıcıya ait etkinlikleri getir
    events = CalendarEvent.objects.filter(user=user, is_visible=True)
    
    # Yetki bazlı filtreleme - kullanıcının yetkisi olmayan etkinlik türlerini filtrele
    if not has_permission_for_event_type(user, 'task'):
        events = events.exclude(event_type='task')
    if not has_permission_for_event_type(user, 'project'):
        events = events.exclude(event_type='project')
    if not has_permission_for_event_type(user, 'payment'):
        events = events.exclude(event_type='payment')
    if not has_permission_for_event_type(user, 'deadline'):
        events = events.exclude(event_type='deadline')
    if not has_permission_for_event_type(user, 'meeting'):
        events = events.exclude(event_type='meeting')
    
    return events


def has_permission_for_event_type(user, event_type):
    """
    Kullanıcının belirli bir etkinlik türü için yetkisi olup olmadığını kontrol eder.
    """
    if event_type == 'payment':
        # Ödeme etkinlikleri sadece muhasebeci ve muhasebeadmin etiketine sahip kullanıcılar görebilir
        return hasattr(user, 'has_tag') and (
            user.has_tag('muhasebeci') or 
            user.has_tag('muhasebeadmin')
        )
    elif event_type == 'project':
        # Proje etkinlikleri proje yöneticisi ve admin görebilir
        return user.role in ['admin', 'project_manager']
    elif event_type == 'task':
        # Görev etkinlikleri tüm kullanıcılar görebilir
        return True
    elif event_type == 'deadline':
        # Son tarih etkinlikleri tüm kullanıcılar görebilir
        return True
    elif event_type == 'meeting':
        # Toplantı etkinlikleri tüm kullanıcılar görebilir
        return True
    else:
        return True


def create_calendar_events_from_models(user):
    """
    Diğer modellerden takvim etkinlikleri oluşturur.
    """
    from tasks.models import Task
    from projects.models import Project
    from sellers.models import PaymentReceipt, ProjectSale
    
    # Görevlerden etkinlik oluştur
    if has_permission_for_event_type(user, 'task'):
        # Kullanıcının görevleri: atandığı, oluşturduğu, veya proje yöneticisi olduğu projelerdeki görevler
        tasks = Task.objects.filter(
            Q(assignee=user) |  # Kendisine atanan görevler
            Q(creator=user) |   # Kendisinin oluşturduğu görevler
            Q(project__team_members=user) |  # Üyesi olduğu projelerdeki görevler
            Q(project__manager=user)  # Yöneticisi olduğu projelerdeki görevler
        ).distinct()
        
        for task in tasks:
            if task.due_date:
                # Tarih alanlarını timezone-aware yap
                start_date = timezone.make_aware(datetime.combine(task.due_date, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(task.due_date, datetime.min.time()))
                
                CalendarEvent.objects.get_or_create(
                    user=user,
                    content_type=ContentType.objects.get_for_model(task),
                    object_id=task.id,
                    defaults={
                        'title': f"Görev: {task.title}",
                        'description': task.description,
                        'event_type': 'task',
                        'start_date': start_date,
                        'end_date': end_date,
                        'is_all_day': True,
                        'color': '#28a745' if task.status == 'completed' else '#dc3545' if task.is_overdue else '#007bff',
                        'icon': 'fas fa-tasks',
                        'priority': task.priority,
                        'is_completed': task.status == 'completed',
                    }
                )
    
    # Projelerden etkinlik oluştur
    if has_permission_for_event_type(user, 'project'):
        # Kullanıcının projeleri: yöneticisi olduğu veya üyesi olduğu projeler
        projects = Project.objects.filter(
            Q(manager=user) |      # Yöneticisi olduğu projeler
            Q(team_members=user)   # Üyesi olduğu projeler
        ).distinct()
        
        for project in projects:
            if project.end_date:
                # Tarih alanlarını timezone-aware yap
                start_date = timezone.make_aware(datetime.combine(project.end_date, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(project.end_date, datetime.min.time()))
                
                CalendarEvent.objects.get_or_create(
                    user=user,
                    content_type=ContentType.objects.get_for_model(project),
                    object_id=project.id,
                    defaults={
                        'title': f"Proje: {project.name}",
                        'description': project.description,
                        'event_type': 'project',
                        'start_date': start_date,
                        'end_date': end_date,
                        'is_all_day': True,
                        'color': '#007bff',
                        'icon': 'fas fa-project-diagram',
                        'priority': project.priority,
                        'is_completed': project.status == 'completed',
                    }
                )
    
    # Seller projelerinden etkinlik oluştur
    if has_permission_for_event_type(user, 'project'):
        try:
            # Kullanıcının seller projeleri: oluşturduğu projeler
            seller_projects = ProjectSale.objects.filter(seller=user)
            
            for project in seller_projects:
                # Teklif tarihi
                if project.quote_date:
                    start_date = timezone.make_aware(datetime.combine(project.quote_date, datetime.min.time()))
                    end_date = timezone.make_aware(datetime.combine(project.quote_date, datetime.min.time()))
                    
                    CalendarEvent.objects.get_or_create(
                        user=user,
                        content_type=ContentType.objects.get_for_model(project),
                        object_id=project.id,
                        defaults={
                            'title': f"Teklif: {project.project_name}",
                            'description': f"Müşteri: {project.customer.display_name} - {project.final_price} ₺",
                            'event_type': 'project',
                            'start_date': start_date,
                            'end_date': end_date,
                            'is_all_day': True,
                            'color': '#17a2b8',
                            'icon': 'fas fa-file-invoice',
                            'priority': 'medium',
                            'is_completed': project.status in ['completed', 'cancelled'],
                        }
                    )
                
                # Başlangıç tarihi
                if project.start_date:
                    start_date = timezone.make_aware(datetime.combine(project.start_date, datetime.min.time()))
                    end_date = timezone.make_aware(datetime.combine(project.start_date, datetime.min.time()))
                    
                    CalendarEvent.objects.get_or_create(
                        user=user,
                        content_type=ContentType.objects.get_for_model(project),
                        object_id=project.id,
                        defaults={
                            'title': f"Başlangıç: {project.project_name}",
                            'description': f"Müşteri: {project.customer.display_name} - Proje başladı",
                            'event_type': 'project',
                            'start_date': start_date,
                            'end_date': end_date,
                            'is_all_day': True,
                            'color': '#28a745',
                            'icon': 'fas fa-play-circle',
                            'priority': 'high',
                            'is_completed': project.status in ['completed', 'cancelled'],
                        }
                    )
                
                # Bitiş tarihi
                if project.end_date:
                    start_date = timezone.make_aware(datetime.combine(project.end_date, datetime.min.time()))
                    end_date = timezone.make_aware(datetime.combine(project.end_date, datetime.min.time()))
                    
                    CalendarEvent.objects.get_or_create(
                        user=user,
                        content_type=ContentType.objects.get_for_model(project),
                        object_id=project.id,
                        defaults={
                            'title': f"Bitiş: {project.project_name}",
                            'description': f"Müşteri: {project.customer.display_name} - Proje tamamlandı",
                            'event_type': 'project',
                            'start_date': start_date,
                            'end_date': end_date,
                            'is_all_day': True,
                            'color': '#dc3545',
                            'icon': 'fas fa-stop-circle',
                            'priority': 'high',
                            'is_completed': project.status in ['completed', 'cancelled'],
                        }
                    )
                
                # Teslim tarihi
                if project.delivery_date:
                    start_date = timezone.make_aware(datetime.combine(project.delivery_date, datetime.min.time()))
                    end_date = timezone.make_aware(datetime.combine(project.delivery_date, datetime.min.time()))
                    
                    CalendarEvent.objects.get_or_create(
                        user=user,
                        content_type=ContentType.objects.get_for_model(project),
                        object_id=project.id,
                        defaults={
                            'title': f"Teslim: {project.project_name}",
                            'description': f"Müşteri: {project.customer.display_name} - Proje teslim edildi",
                            'event_type': 'project',
                            'start_date': start_date,
                            'end_date': end_date,
                            'is_all_day': True,
                            'color': '#6f42c1',
                            'icon': 'fas fa-truck',
                            'priority': 'high',
                            'is_completed': project.status in ['completed', 'cancelled'],
                        }
                    )
        except Exception as e:
            # Kullanıcının seller projeleri yoksa veya başka bir hata varsa devam et
            pass
    
    # Ödemelerden etkinlik oluştur
    if has_permission_for_event_type(user, 'payment'):
        try:
            payments = PaymentReceipt.objects.filter(sale__seller=user)
            
            for payment in payments:
                # Tarih alanlarını timezone-aware yap
                start_date = timezone.make_aware(datetime.combine(payment.payment_date, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(payment.payment_date, datetime.min.time()))
                
                CalendarEvent.objects.get_or_create(
                    user=user,
                    content_type=ContentType.objects.get_for_model(payment),
                    object_id=payment.id,
                    defaults={
                        'title': f"Ödeme: {payment.sale.project_name}",
                        'description': f"{payment.payment_type} - {payment.amount} ₺",
                        'event_type': 'payment',
                        'start_date': start_date,
                        'end_date': end_date,
                        'is_all_day': True,
                        'color': '#ffc107',
                        'icon': 'fas fa-money-bill-wave',
                        'priority': 'high' if payment.payment_type == 'final' else 'medium',
                        'is_completed': payment.status == 'completed',
                    }
                )
        except Exception as e:
            # Kullanıcının ödeme kayıtları yoksa veya başka bir hata varsa devam et
            pass


def sync_calendar_events(user):
    """
    Kullanıcının takvim etkinliklerini diğer modellerle senkronize eder.
    """
    # Mevcut etkinlikleri temizle
    CalendarEvent.objects.filter(
        user=user,
        content_type__isnull=False
    ).delete()
    
    # Yeni etkinlikleri oluştur
    create_calendar_events_from_models(user)


def get_upcoming_events(user, days=7):
    """
    Kullanıcının yaklaşan etkinliklerini döndürür.
    """
    try:
        settings = CalendarSettings.objects.get(user=user)
    except CalendarSettings.DoesNotExist:
        settings = CalendarSettings.objects.create(user=user)
    
    end_date = timezone.now() + timedelta(days=days)
    
    events = get_user_events(user, settings).filter(
        start_date__gte=timezone.now(),
        start_date__lte=end_date,
        is_completed=False
    ).order_by('start_date')[:10]
    
    return events


def get_overdue_events(user):
    """
    Kullanıcının süresi geçmiş etkinliklerini döndürür.
    """
    try:
        settings = CalendarSettings.objects.get(user=user)
    except CalendarSettings.DoesNotExist:
        settings = CalendarSettings.objects.create(user=user)
    
    events = get_user_events(user, settings).filter(
        end_date__lt=timezone.now(),
        is_completed=False
    ).order_by('end_date')
    
    return events
