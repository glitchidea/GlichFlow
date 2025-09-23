from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta

from .models import CalendarEvent, CalendarSettings

User = get_user_model()


def get_user_events(user, settings):
    """
    Kullanıcının yetkisine göre etkinlikleri döndürür.
    """
    events = CalendarEvent.objects.filter(user=user, is_visible=True)
    
    # Ayar bazlı filtreleme
    if not settings.show_tasks:
        events = events.exclude(event_type='task')
    if not settings.show_projects:
        events = events.exclude(event_type='project')
    if not settings.show_payments:
        events = events.exclude(event_type='payment')
    if not settings.show_deadlines:
        events = events.exclude(event_type='deadline')
    if not settings.show_meetings:
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
    from sellers.models import PaymentReceipt
    
    # Görevlerden etkinlik oluştur
    if has_permission_for_event_type(user, 'task'):
        tasks = Task.objects.filter(
            Q(assignee=user) | Q(creator=user) | Q(project__team_members=user)
        ).distinct()
        
        for task in tasks:
            if task.due_date:
                CalendarEvent.objects.get_or_create(
                    user=user,
                    content_type__model='task',
                    object_id=task.id,
                    defaults={
                        'title': f"Görev: {task.title}",
                        'description': task.description,
                        'event_type': 'task',
                        'start_date': task.due_date,
                        'end_date': task.due_date,
                        'is_all_day': True,
                        'color': '#28a745' if task.status == 'completed' else '#dc3545' if task.is_overdue else '#007bff',
                        'icon': 'fas fa-tasks',
                        'priority': task.priority,
                        'is_completed': task.status == 'completed',
                        'content_type': task._meta.model,
                        'object_id': task.id,
                    }
                )
    
    # Projelerden etkinlik oluştur
    if has_permission_for_event_type(user, 'project'):
        projects = Project.objects.filter(
            Q(manager=user) | Q(team_members=user)
        ).distinct()
        
        for project in projects:
            if project.end_date:
                CalendarEvent.objects.get_or_create(
                    user=user,
                    content_type__model='project',
                    object_id=project.id,
                    defaults={
                        'title': f"Proje: {project.name}",
                        'description': project.description,
                        'event_type': 'project',
                        'start_date': project.end_date,
                        'end_date': project.end_date,
                        'is_all_day': True,
                        'color': '#007bff',
                        'icon': 'fas fa-project-diagram',
                        'priority': project.priority,
                        'is_completed': project.status == 'completed',
                        'content_type': project._meta.model,
                        'object_id': project.id,
                    }
                )
    
    # Ödemelerden etkinlik oluştur
    if has_permission_for_event_type(user, 'payment'):
        payments = PaymentReceipt.objects.filter(sale__created_by=user)
        
        for payment in payments:
            CalendarEvent.objects.get_or_create(
                user=user,
                content_type__model='paymentreceipt',
                object_id=payment.id,
                defaults={
                    'title': f"Ödeme: {payment.sale.project_name}",
                    'description': f"{payment.payment_type} - {payment.amount} ₺",
                    'event_type': 'payment',
                    'start_date': payment.payment_date,
                    'end_date': payment.payment_date,
                    'is_all_day': True,
                    'color': '#ffc107',
                    'icon': 'fas fa-money-bill-wave',
                    'priority': 'high' if payment.payment_type == 'final' else 'medium',
                    'is_completed': payment.status == 'completed',
                    'content_type': payment._meta.model,
                    'object_id': payment.id,
                }
            )


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
