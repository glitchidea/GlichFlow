from celery import shared_task
from datetime import timedelta
from django.utils import timezone

@shared_task
def check_approaching_deadlines():
    """
    Yaklaşan proje ve görev teslim tarihlerini kontrol eder ve bildirim oluşturur.
    
    Bu fonksiyon, önümüzdeki 3 gün içinde bitecek projeler ve görevler için
    ilgili kullanıcılara bildirim gönderir.
    """
    from projects.models import Project
    from tasks.models import Task
    from communications.models import Notification
    
    # Bugün ve 3 gün sonrası
    today = timezone.now().date()
    upcoming_days = today + timedelta(days=3)
    
    notifications_created = 0
    
    # Projeler için kontrol
    approaching_projects = Project.objects.filter(
        end_date__range=[today, upcoming_days],
        status__in=['active', 'planning']  # Tamamlanmış projeler
    )
    
    for project in approaching_projects:
        # Proje yöneticisine bildirim
        manager = project.manager
        if manager:
            days_left = (project.end_date - today).days
            
            # Son gün, yarın veya birkaç gün kaldıysa farklı mesajlar
            if days_left == 0:
                message = f"Projenin teslim tarihi bugün: {project.name}"
            elif days_left == 1:
                message = f"Projenin teslim tarihi yarın: {project.name}"
            else:
                message = f"Projenin teslimine {days_left} gün kaldı: {project.name}"
                
            # Bugün bildirimi zaten gönderilmiş mi kontrol et
            if not Notification.objects.filter(
                recipient=manager,
                related_project=project,
                title="Yaklaşan Proje Teslim Tarihi",
                created_at__date=today
            ).exists():
                # Bildirim oluştur
                Notification.objects.create(
                    recipient=manager,
                    title="Yaklaşan Proje Teslim Tarihi",
                    content=message,
                    notification_type="warning",
                    related_project=project
                )
                notifications_created += 1
        
        # Proje ekibine bildirim
        team_members = project.team_members.all()
        for member in team_members:
            if member != manager:  # Yöneticiye tekrar bildirim gönderme
                days_left = (project.end_date - today).days
                
                if days_left == 0:
                    message = f"Projenin teslim tarihi bugün: {project.name}"
                elif days_left == 1:
                    message = f"Projenin teslim tarihi yarın: {project.name}"
                else:
                    message = f"Projenin teslimine {days_left} gün kaldı: {project.name}"
                
                # Bugün bildirimi zaten gönderilmiş mi kontrol et
                if not Notification.objects.filter(
                    recipient=member,
                    related_project=project,
                    title="Yaklaşan Proje Teslim Tarihi",
                    created_at__date=today
                ).exists():
                    Notification.objects.create(
                        recipient=member,
                        title="Yaklaşan Proje Teslim Tarihi",
                        content=message,
                        notification_type="warning",
                        related_project=project
                    )
                    notifications_created += 1
    
    # Görevler için kontrol
    approaching_tasks = Task.objects.filter(
        due_date__range=[today, upcoming_days],
        status__in=['todo', 'in_progress', 'review']  # Tamamlanmamış görevler
    )
    
    for task in approaching_tasks:
        # Görevin atandığı kişiye bildirim
        assignee = task.assignee
        if assignee:
            days_left = (task.due_date - today).days
            
            if days_left == 0:
                message = f"Görevin teslim tarihi bugün: {task.title}"
            elif days_left == 1:
                message = f"Görevin teslim tarihi yarın: {task.title}"
            else:
                message = f"Görevin teslimine {days_left} gün kaldı: {task.title}"
            
            # Bugün bildirimi zaten gönderilmiş mi kontrol et
            if not Notification.objects.filter(
                recipient=assignee,
                related_task=task,
                title="Yaklaşan Görev Teslim Tarihi",
                created_at__date=today
            ).exists():
                Notification.objects.create(
                    recipient=assignee,
                    title="Yaklaşan Görev Teslim Tarihi",
                    content=message,
                    notification_type="warning",
                    related_task=task,
                    related_project=task.project
                )
                notifications_created += 1
        
        # Görevin oluşturucusuna bildirim (eğer atanan kişiden farklıysa)
        creator = task.created_by
        if creator and creator != assignee:
            days_left = (task.due_date - today).days
            
            if days_left == 0:
                message = f"Oluşturduğunuz görevin teslim tarihi bugün: {task.title}"
            elif days_left == 1:
                message = f"Oluşturduğunuz görevin teslim tarihi yarın: {task.title}"
            else:
                message = f"Oluşturduğunuz görevin teslimine {days_left} gün kaldı: {task.title}"
            
            # Bugün bildirimi zaten gönderilmiş mi kontrol et
            if not Notification.objects.filter(
                recipient=creator,
                related_task=task,
                title="Yaklaşan Görev Teslim Tarihi",
                created_at__date=today
            ).exists():
                Notification.objects.create(
                    recipient=creator,
                    title="Yaklaşan Görev Teslim Tarihi",
                    content=message,
                    notification_type="warning",
                    related_task=task,
                    related_project=task.project
                )
                notifications_created += 1
        
        # Proje yöneticisine bildirim (eğer atanan kişi ve oluşturucudan farklıysa)
        if task.project and task.project.manager:
            project_manager = task.project.manager
            if project_manager != assignee and project_manager != creator:
                days_left = (task.due_date - today).days
                
                if days_left == 0:
                    message = f"Projenizin bir görevinin teslim tarihi bugün: {task.title}"
                elif days_left == 1:
                    message = f"Projenizin bir görevinin teslim tarihi yarın: {task.title}"
                else:
                    message = f"Projenizin bir görevinin teslimine {days_left} gün kaldı: {task.title}"
                
                # Bugün bildirimi zaten gönderilmiş mi kontrol et
                if not Notification.objects.filter(
                    recipient=project_manager,
                    related_task=task,
                    title="Yaklaşan Görev Teslim Tarihi",
                    created_at__date=today
                ).exists():
                    Notification.objects.create(
                        recipient=project_manager,
                        title="Yaklaşan Görev Teslim Tarihi",
                        content=message,
                        notification_type="warning",
                        related_task=task,
                        related_project=task.project
                    )
                    notifications_created += 1
    
    return f"{notifications_created} adet yaklaşan teslim tarihi bildirimi oluşturuldu." 