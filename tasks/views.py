from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.http import HttpResponseRedirect

from .models import Task, TimeLog, Comment
from projects.models import Project, Attachment
from accounts.models import CustomUser
from communications.models import Notification

@login_required
def task_list(request):
    """
    Tüm görevleri listeler.
    """
    # Filtreleme parametreleri
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    project_id = request.GET.get('project')
    assignee_id = request.GET.get('assignee')
    search = request.GET.get('search')
    
    # Temel sorgu
    tasks = Task.objects.all().select_related('project', 'assignee', 'parent_task')
    
    # Kullanıcı rolüne göre filtreleme
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        # Yönetici değilse, sadece atandığı veya projesi üzerinde çalıştığı görevleri görebilir
        tasks = tasks.filter(
            Q(assignee=request.user) | 
            Q(project__manager=request.user) |
            Q(project__team_members=request.user)
        ).distinct()
    
    # Diğer filtreleri uygulama
    if status:
        tasks = tasks.filter(status=status)
    
    if priority:
        tasks = tasks.filter(priority=priority)
    
    if project_id:
        tasks = tasks.filter(project_id=project_id)
    
    if assignee_id:
        tasks = tasks.filter(assignee_id=assignee_id)
    
    if search:
        tasks = tasks.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Görev istatistikleri
    total_tasks = tasks.count()
    todo_tasks = tasks.filter(status='todo').count()
    in_progress_tasks = tasks.filter(status='in_progress').count()
    review_tasks = tasks.filter(status='review').count()
    completed_tasks = tasks.filter(status='completed').count()
    overdue_tasks = tasks.filter(due_date__lt=timezone.now().date()).exclude(status='completed').count()
    
    # İlgili verileri getir
    projects = Project.objects.all()
    users = CustomUser.objects.all()
    
    context = {
        'tasks': tasks,
        'total_tasks': total_tasks,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'review_tasks': review_tasks,
        'completed_tasks': completed_tasks,
        'overdue_tasks': overdue_tasks,
        'status_filter': status,
        'priority_filter': priority,
        'project_filter': project_id,
        'assignee_filter': assignee_id,
        'search_query': search,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'projects': projects,
        'users': users,
        'title': 'Görevler',
    }
    
    return render(request, 'tasks/task_list.html', context)

@login_required
def task_detail(request, task_id):
    """
    Görev detaylarını gösterir.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != task.assignee and request.user != task.project.manager and request.user not in task.project.team_members.all():
            messages.error(request, 'Bu görevi görüntüleme yetkiniz yok.')
            return redirect('tasks:task_list')
    
    # Alt görevleri getir
    subtasks = task.subtasks.all().select_related('assignee')
    
    # Zaman kayıtlarını getir
    time_logs = task.time_logs.all().select_related('user')
    
    # Yorumları getir
    comments = task.comments.all().select_related('author')
    
    # Dosya eklerini getir
    attachments = task.attachments.all().select_related('uploaded_by')
    
    # PRD'leri getir
    prds = task.prds.all().select_related('created_by', 'assigned_by')
    
    context = {
        'task': task,
        'subtasks': subtasks,
        'time_logs': time_logs,
        'comments': comments,
        'attachments': attachments,
        'prds': prds,
        'title': task.title,
    }
    
    return render(request, 'tasks/task_detail.html', context)

@login_required
def task_create(request, project_id=None):
    """
    Görev oluşturma formu ve işleme.
    """
    # Proje varsa kontrol et
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id)
        
        # Yetkilendirme kontrolü - Sadece admin ve proje yöneticisi görev oluşturabilir
        if not request.user.is_superuser and request.user.role != 'project_manager' and request.user != project.manager:
            messages.error(request, 'Bu projeye görev ekleme yetkiniz yok. Bu işlem yalnızca proje yöneticileri veya sistem yöneticileri tarafından yapılabilir.')
            return redirect('projects:project_detail', project_id=project.id)
    else:
        # Proje belirtilmemişse sadece admin ve proje yöneticileri görev oluşturabilir
        if not request.user.is_superuser and request.user.role != 'project_manager':
            messages.error(request, 'Görev oluşturma yetkiniz yok. Bu işlem yalnızca proje yöneticileri veya sistem yöneticileri tarafından yapılabilir.')
            return redirect('tasks:task_list')
    
    if request.method == 'POST':
        # Form verilerini işle
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        project_id = request.POST.get('project')
        assignee_id = request.POST.get('assignee') or None
        status = request.POST.get('status')
        priority = request.POST.get('priority')
        estimate_hours = request.POST.get('estimate_hours') or None
        start_date = request.POST.get('start_date') or None
        due_date = request.POST.get('due_date') or None
        parent_task_id = request.POST.get('parent_task') or None
        
        # PRD oluşturma seçeneği
        create_prd = request.POST.get('create_prd') == 'on'
        
        if not title or not project_id or not status or not priority:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            # Yeni görevi oluştur
            task = Task(
                title=title,
                description=description,
                project_id=project_id,
                creator=request.user,
                assignee_id=assignee_id,
                status=status,
                priority=priority,
                estimate_hours=estimate_hours,
                start_date=start_date,
                due_date=due_date,
                parent_task_id=parent_task_id,
                created_at=timezone.now()
            )
            task.save()
            
            # PRD oluşturma seçeneği işaretlenmişse PRD oluştur
            if create_prd:
                from projects.models import PRD
                
                prd_title = request.POST.get('prd_title', f'{title} - PRD')
                prd_product_summary = request.POST.get('prd_product_summary', '')
                prd_target_audience = request.POST.get('prd_target_audience', '')
                prd_functional_requirements = request.POST.get('prd_functional_requirements', '')
                prd_document = request.FILES.get('prd_document')
                
                prd = PRD.objects.create(
                    title=prd_title,
                    product_summary=prd_product_summary,
                    target_audience=prd_target_audience,
                    functional_requirements=prd_functional_requirements,
                    task=task,
                    created_by=request.user,
                    assigned_by=request.user,
                    document=prd_document,
                    assigned_at=timezone.now()
                )
            
            # Eğer bir kullanıcıya atanmışsa bildirim gönder
            if assignee_id:
                assignee = CustomUser.objects.get(id=assignee_id)
                
                # Atanana bildirim gönder (kendisine atamadıysa)
                if assignee != request.user:
                    Notification.objects.create(
                        recipient=assignee,
                        sender=request.user,
                        title=f"Yeni görev atandı: {title}",
                        content=f"{request.user.get_full_name() or request.user.username} size yeni bir görev atadı: {title}",
                        notification_type="info",
                        related_task=task,
                        related_project=task.project
                    )
                
                # Proje yöneticisine de bildirim gönder (kendisi değilse)
                if task.project.manager and task.project.manager != request.user and task.project.manager != assignee:
                    Notification.objects.create(
                        recipient=task.project.manager,
                        sender=request.user,
                        title=f"Görev atandı: {title}",
                        content=f"{request.user.get_full_name() or request.user.username}, {assignee.get_full_name() or assignee.username} kişisine görev atadı: {title}",
                        notification_type="info",
                        related_task=task,
                        related_project=task.project
                    )
            
            if create_prd:
                messages.success(request, f'"{title}" görevi ve PRD başarıyla oluşturuldu.')
            else:
                messages.success(request, f'"{title}" görevi başarıyla oluşturuldu.')
            
            # Yönlendirme
            if project:
                return redirect('projects:project_detail', project_id=project.id)
            else:
                return redirect('tasks:task_detail', task_id=task.id)
    
    # Formda kullanılacak verileri hazırla
    users = CustomUser.objects.all()
    projects = Project.objects.all()
    project_tasks = []
    
    # Kullanıcı rolüne göre erişilebilir projeleri filtrele
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        projects = projects.filter(
            Q(manager=request.user) | Q(team_members=request.user)
        ).distinct()
    
    # Eğer proje belirtilmişse, projenin görevlerini getir
    if project:
        project_tasks = project.tasks.all()
    
    context = {
        'users': users,
        'projects': projects,
        'project': project,
        'project_tasks': project_tasks,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'title': 'Yeni Görev',
    }
    
    return render(request, 'tasks/task_form.html', context)

@login_required
def task_update(request, task_id):
    """
    Görev düzenleme formu ve işleme.
    """
    task = get_object_or_404(Task, id=task_id)
    original_assignee_id = task.assignee_id  # Orijinal atananı kaydet
    original_status = task.status  # Orijinal durumu kaydet
    
    # Yetkilendirme kontrolü
    is_admin_or_manager = request.user.is_superuser or request.user.role == 'project_manager' or request.user == task.project.manager
    is_assignee = request.user == task.assignee
    is_creator = request.user == task.creator
    
    # Takım üyeleri sadece kendilerine atanmış görevlerin durumunu güncelleyebilir
    if not is_admin_or_manager:
        if not is_assignee and not is_creator:
            messages.error(request, 'Bu görevi düzenleme yetkiniz yok. Sadece göreve atanan kişi, görevi oluşturan kişi veya yöneticiler düzenleyebilir.')
            return redirect('tasks:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        # Form verilerini işle
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        assignee_id = request.POST.get('assignee') or None
        status = request.POST.get('status')
        priority = request.POST.get('priority')
        estimate_hours = request.POST.get('estimate_hours') or None
        actual_hours = request.POST.get('actual_hours') or None
        start_date = request.POST.get('start_date') or None
        due_date = request.POST.get('due_date') or None
        parent_task_id = request.POST.get('parent_task') or None
        create_prd = request.POST.get('create_prd') == 'on' # PRD oluşturma seçeneği
        
        if not title or not status or not priority:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            # Takım üyeleri sadece kendilerine atanmış görevin durumunu değiştirebilir
            # Diğer alanları değiştiremezler
            if not is_admin_or_manager and is_assignee:
                # Sadece durum güncellemesi yapılabilir
                if status != original_status:
                    task.status = status
                    
                    # Eğer tamamlandı olarak işaretlendiyse
                    if status == 'completed' and original_status != 'completed':
                        task.completed_date = timezone.now().date()
                    elif status != 'completed':
                        task.completed_date = None
                    
                    task.save()
                    
                    # Durum değişikliği bildirimi gönder
                    send_status_change_notification(task, request.user, status, original_status)
                    
                    messages.success(request, f'"{task.title}" görevinin durumu güncellendi.')
                else:
                    messages.info(request, 'Görev durumu değiştirilmedi. Takım üyeleri sadece görev durumunu güncelleyebilir.')
                
                return redirect('tasks:task_detail', task_id=task.id)
            
            # Yöneticiler ve proje yöneticileri için tam güncelleme
            # Görevi güncelle
            task.title = title
            task.description = description
            task.assignee_id = assignee_id
            task.status = status
            task.priority = priority
            task.estimate_hours = estimate_hours
            task.actual_hours = actual_hours
            task.start_date = start_date
            task.due_date = due_date
            
            # Alt görev ayarı - sadece admin ve proje yöneticileri alt görev atayabilir
            if is_admin_or_manager:
                task.parent_task_id = parent_task_id
            elif parent_task_id != task.parent_task_id:
                messages.warning(request, 'Alt görev atama yetkisi sadece yöneticilere aittir. Bu değişiklik uygulanmadı.')
            
            # Eğer tamamlandı olarak işaretlendiyse
            if status == 'completed' and original_status != 'completed':
                task.completed_date = timezone.now().date()
            elif status != 'completed':
                task.completed_date = None
            
            task.save()
            
            # PRD oluşturma seçeneği işaretlenmişse PRD oluştur
            if create_prd:
                from projects.models import PRD
                
                prd_title = request.POST.get('prd_title', f'{title} - PRD')
                prd_product_summary = request.POST.get('prd_product_summary', '')
                prd_target_audience = request.POST.get('prd_target_audience', '')
                prd_functional_requirements = request.POST.get('prd_functional_requirements', '')
                prd_document = request.FILES.get('prd_document')
                
                prd = PRD.objects.create(
                    title=prd_title,
                    product_summary=prd_product_summary,
                    target_audience=prd_target_audience,
                    functional_requirements=prd_functional_requirements,
                    task=task,
                    created_by=request.user,
                    assigned_by=request.user,
                    document=prd_document,
                    assigned_at=timezone.now()
                )
            
            # Görev ataması değiştiyse bildirim gönder
            if assignee_id != original_assignee_id and assignee_id:
                new_assignee = CustomUser.objects.get(id=assignee_id)
                
                # Yeni atanan kişiye bildirim gönder (kendisi değilse)
                if new_assignee != request.user:
                    Notification.objects.create(
                        recipient=new_assignee,
                        sender=request.user,
                        title=f"Görev atandı: {title}",
                        content=f"{request.user.get_full_name() or request.user.username} size görev atadı: {title}",
                        notification_type="info",
                        related_task=task,
                        related_project=task.project
                    )
                
                # Proje yöneticisine de bildirim gönder (kendisi değilse)
                if task.project.manager and task.project.manager != request.user and task.project.manager != new_assignee:
                    Notification.objects.create(
                        recipient=task.project.manager,
                        sender=request.user,
                        title=f"Görev atandı: {title}",
                        content=f"{request.user.get_full_name() or request.user.username}, {new_assignee.get_full_name() or new_assignee.username} kişisine görev atadı: {title}",
                        notification_type="info",
                        related_task=task,
                        related_project=task.project
                    )
            
            # Durum değişikliği bildirimi gönder
            if status != original_status:
                send_status_change_notification(task, request.user, status, original_status)
            
            if create_prd:
                messages.success(request, f'"{title}" görevi güncellendi ve PRD başarıyla oluşturuldu.')
            else:
                messages.success(request, f'"{title}" görevi başarıyla güncellendi.')
            
            return redirect('tasks:task_detail', task_id=task.id)
    
    # Formda kullanılacak verileri hazırla
    users = CustomUser.objects.all()
    projects = Project.objects.all()
    project_tasks = task.project.tasks.exclude(id=task.id)
    
    context = {
        'task': task,
        'users': users,
        'projects': projects,
        'project': task.project,
        'project_tasks': project_tasks,
        'status_choices': Task.STATUS_CHOICES,
        'priority_choices': Task.PRIORITY_CHOICES,
        'title': f'{task.title} - Düzenle',
        'is_admin_or_manager': is_admin_or_manager,
        'is_assignee': is_assignee,
    }
    
    return render(request, 'tasks/task_form.html', context)

# Yardımcı fonksiyon - durum değişikliği bildirimleri için
def send_status_change_notification(task, user, new_status, original_status):
    if new_status == original_status:
        return
        
    # Duruma göre bildirim tipi
    notification_type = "success" if new_status == "completed" else "info"
    
    # Durum mesajı
    status_display = dict(Task.STATUS_CHOICES).get(new_status, new_status)
    
    # Bildirim alıcılarını belirle (tekrarları önlemek için set kullan)
    recipients = set()
    
    # Proje yöneticisine bildirim
    if task.project.manager and task.project.manager != user:
        recipients.add(task.project.manager)
    
    # Görev oluşturucuya bildirim (kendisi değilse)
    if task.creator and task.creator != user and task.creator != task.project.manager:
        recipients.add(task.creator)
        
    # Göreve atanan kişi (kendisi değilse)
    if task.assignee and task.assignee != user:
        recipients.add(task.assignee)
    
    # Her alıcıya bildirim gönder
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=user,
            title=f"Görev durumu değişti: {task.title}",
            content=f"{user.get_full_name() or user.username} görevi '{status_display}' olarak işaretledi: {task.title}",
            notification_type=notification_type,
            related_task=task,
            related_project=task.project
        )

@login_required
def task_delete(request, task_id):
    """
    Görev silme işlemi.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user != task.project.manager:
        messages.error(request, 'Bu görevi silme yetkiniz yok.')
        return redirect('tasks:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        project_id = task.project.id
        title = task.title
        task.delete()
        messages.success(request, f'"{title}" görevi başarıyla silindi.')
        return redirect('projects:project_detail', project_id=project_id)
    
    context = {
        'task': task,
        'title': f'{task.title} - Sil',
    }
    
    return render(request, 'tasks/task_confirm_delete.html', context)

@login_required
def add_time_log(request, task_id):
    """
    Zaman kaydı ekleme.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != task.assignee and request.user not in task.project.team_members.all():
            messages.error(request, 'Bu göreve zaman kaydı ekleme yetkiniz yok.')
            return redirect('tasks:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        date = request.POST.get('date')
        hours = request.POST.get('hours')
        description = request.POST.get('description', '')
        
        if not date or not hours:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            # Yeni zaman kaydı oluştur
            time_log = TimeLog(
                task=task,
                user=request.user,
                date=date,
                hours=hours,
                description=description
            )
            time_log.save()
            
            # Güncel harcanan zamanı hesapla
            total_hours = task.time_logs.aggregate(total=Sum('hours'))['total'] or 0
            task.actual_hours = total_hours
            task.save()
            
            messages.success(request, 'Zaman kaydı başarıyla eklendi.')
        
        return redirect('tasks:task_detail', task_id=task.id)
    
    context = {
        'task': task,
        'title': 'Zaman Kaydı Ekle',
        'now': timezone.now(),
    }
    
    return render(request, 'tasks/time_log_form.html', context)

@login_required
def add_comment(request, task_id):
    """
    Yorum ekleme.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != task.assignee and request.user not in task.project.team_members.all():
            messages.error(request, 'Bu göreve yorum ekleme yetkiniz yok.')
            return redirect('tasks:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        content = request.POST.get('content')
        
        if not content:
            messages.error(request, 'Lütfen bir yorum yazın.')
        else:
            # Yeni yorum oluştur
            comment = Comment(
                task=task,
                author=request.user,
                content=content
            )
            comment.save()
            
            # Bildirim oluştur - göreve atanan kişiye, proje yöneticisine ve yorum yazarına (kendisi hariç)
            recipients = set()
            
            # Göreve atanan kişi varsa ve yorum yazan kişiden farklıysa ekle
            if task.assignee and task.assignee != request.user:
                recipients.add(task.assignee)
                
            # Proje yöneticisi
            if task.project.manager and task.project.manager != request.user:
                recipients.add(task.project.manager)
                
            # Projede çalışan herkes (yorum yazan kişi hariç)
            for member in task.project.team_members.all():
                if member != request.user:
                    recipients.add(member)
            
            # Her alıcı için bildirim oluştur
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    sender=request.user,
                    title=f"Yeni yorum: {task.title}",
                    content=f"{request.user.get_full_name() or request.user.username} görevinize yorum yaptı: {content[:100]}{'...' if len(content) > 100 else ''}",
                    notification_type="info",
                    related_task=task,
                    related_project=task.project
                )
            
            messages.success(request, 'Yorum başarıyla eklendi.')
        
        return redirect('tasks:task_detail', task_id=task.id)
    
    # Sadece POST istekleri destekleniyor
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
def update_status(request, task_id):
    """
    Görev durumunu hızlı bir şekilde günceller.
    """
    task = get_object_or_404(Task, id=task_id)
    original_status = task.status  # Orijinal durumu kaydet
    
    # Yetkilendirme kontrolü
    is_admin_or_manager = request.user.is_superuser or request.user.role == 'project_manager' or request.user == task.project.manager
    is_assignee = request.user == task.assignee
    
    # Takım üyeleri sadece kendilerine atanmış görevlerin durumunu değiştirebilir
    if not is_admin_or_manager and not is_assignee:
        messages.error(request, 'Görev durumunu değiştirme yetkiniz yok. Sadece göreve atanan kişi, proje yöneticisi veya sistem yöneticisi durum değişikliği yapabilir.')
        return redirect('tasks:task_detail', task_id=task.id)
    
    # Yeni durumu al
    new_status = request.GET.get('status')
    if new_status in dict(Task.STATUS_CHOICES).keys():
        # Eğer tamamlandı olarak işaretlendiyse
        if new_status == 'completed' and task.status != 'completed':
            task.completed_date = timezone.now().date()
        elif new_status != 'completed':
            task.completed_date = None
            
        # Durumu güncelle
        task.status = new_status
        task.save()
        
        # Durum değiştiyse bildirim gönder
        if new_status != original_status:
            # Bildirim alıcılarını belirle (tekrarları önlemek için set kullan)
            recipients = set()
            
            # Göreve atanan kişi (kendisi değilse)
            if task.assignee and task.assignee != request.user:
                recipients.add(task.assignee)
                
            # Görevi oluşturan kişi (kendisi değilse)
            if task.creator and task.creator != request.user:
                recipients.add(task.creator)
                
            # Proje yöneticisi (kendisi değilse)
            if task.project.manager and task.project.manager != request.user:
                recipients.add(task.project.manager)
                
            # Duruma göre bildirim tipi belirle
            notification_type = "success" if new_status == "completed" else "info"
            
            # Durum mesajı
            status_display = dict(Task.STATUS_CHOICES).get(new_status, new_status)
                
            # Her alıcıya bildirim gönder
            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    sender=request.user,
                    title=f"Görev durumu değişti: {task.title}",
                    content=f"{request.user.get_full_name() or request.user.username} görevi '{status_display}' olarak işaretledi: {task.title}",
                    notification_type=notification_type,
                    related_task=task,
                    related_project=task.project
                )
        
        messages.success(request, f'"{task.title}" görevinin durumu güncellendi.')
    
    # Geri yönlendirme
    next_url = request.GET.get('next')
    if next_url:
        return HttpResponseRedirect(next_url)
    else:
        return redirect('tasks:task_detail', task_id=task.id)

@login_required
def attachment_upload(request, task_id):
    """
    Görev için dosya ekleme.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager'] and request.user != task.assignee and request.user not in task.project.team_members.all():
        messages.error(request, 'Bu göreve dosya yükleme yetkiniz yok.')
        return redirect('tasks:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        file = request.FILES.get('file')
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        if not file or not name:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            attachment = Attachment(
                file=file,
                name=name,
                description=description,
                uploaded_by=request.user,
                task=task
            )
            attachment.save()
            
            messages.success(request, f'"{name}" dosyası başarıyla yüklendi.')
        
        return redirect('tasks:task_detail', task_id=task.id)
    
    context = {
        'task': task,
        'title': f'{task.title} - Dosya Ekle',
    }
    
    return render(request, 'tasks/attachment_form.html', context)
