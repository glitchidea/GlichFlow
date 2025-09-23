from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.utils import timezone

from projects.models import Project
from tasks.models import Task
from teams.models import Team, TeamMember
from reports.models import Report
from communications.models import Notification

# Create your views here.

@login_required
def index(request):
    """
    Dashboard ana sayfası.
    """
    # Projeler istatistikleri
    projects = Project.objects.all()
    
    # Kullanıcı rolüne göre filtreleme
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        projects = projects.filter(
            Q(manager=request.user) | Q(team_members=request.user)
        ).distinct()
    
    total_projects = projects.count()
    active_projects = projects.filter(status='in_progress').count()
    completed_projects = projects.filter(status='completed').count()
    overdue_projects = projects.filter(end_date__lt=timezone.now().date()).exclude(status='completed').count()
    
    # Görevler istatistikleri
    tasks = Task.objects.filter(
        project__in=projects
    )
    
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    in_progress_tasks = tasks.filter(status='in_progress').count()
    todo_tasks = tasks.filter(status='todo').count()
    delayed_tasks = tasks.filter(due_date__lt=timezone.now().date()).exclude(status='completed').count()
    
    # Son görevler
    recent_tasks = tasks.order_by('-created_at')[:5]
    
    # Yaklaşan teslim tarihleri
    upcoming_tasks = tasks.filter(
        Q(status='todo') | Q(status='in_progress'),
        due_date__gte=timezone.now().date()
    ).order_by('due_date')[:5]
    
    # Aktif projeler
    active_project_list = projects.filter(status='in_progress').order_by('-updated_at')[:4]
    
    # Ekip bilgileri
    teams = Team.objects.all()
    team_count = teams.count()
    team_member_count = TeamMember.objects.count()
    
    context = {
        'title': 'Dashboard',
        # Proje istatistikleri
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'overdue_projects': overdue_projects,
        'active_project_list': active_project_list,
        
        # Görev istatistikleri
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'todo_tasks': todo_tasks,
        'delayed_tasks': delayed_tasks,
        'recent_tasks': recent_tasks,
        'upcoming_tasks': upcoming_tasks,
        
        # Ekip istatistikleri
        'team_count': team_count,
        'team_member_count': team_member_count,
        
        # Current date/time for template comparison
        'now': timezone.now(),
    }
    
    return render(request, 'dashboard/index.html', context)

@login_required
def personal_menu(request):
    """
    Kullanıcının kendisine atanan proje, görev, rapor ve bildirimlerini
    gösterir.
    """
    # Kullanıcının projeleri - tamamlanmış veya iptal edilmiş projeler hariç
    active_projects = Project.objects.filter(
        Q(manager=request.user) | Q(team_members=request.user),
        ~Q(status__in=['completed', 'cancelled'])  # Tamamlanmış veya iptal edilmiş projeleri hariç tut
    ).distinct().order_by('status', 'end_date')
    
    # Tamamlanmış projeler için ayrı bir sorgu
    completed_projects = Project.objects.filter(
        Q(manager=request.user) | Q(team_members=request.user),
        status='completed'  # Sadece tamamlanmış projeler
    ).distinct().order_by('-updated_at')
    
    # Kullanıcının görevleri - tamamlanmış veya iptal edilmiş projelerin görevleri hariç
    assigned_tasks = Task.objects.filter(
        Q(assignee=request.user),
        ~Q(project__status__in=['completed', 'cancelled'])  # Tamamlanmış veya iptal edilmiş projelerin görevlerini hariç tut
    ).order_by('status', 'due_date')

    # Kullanıcının proje veya görevleriyle ilgili raporlar
    # Önce kullanıcının projelerini ve görevlerini al
    user_projects = Project.objects.filter(
        Q(manager=request.user) | Q(team_members=request.user)
    ).values_list('id', flat=True)
    
    user_tasks = Task.objects.filter(
        assignee=request.user
    ).values_list('id', flat=True)
    
    # Kullanıcının projeleri veya görevleriyle ilgili raporları al
    related_reports = Report.objects.filter(
        Q(project__in=user_projects) |
        Q(created_by=request.user)
    ).distinct().order_by('-created_at')
    
    # Raporları tiplerine göre kategorize et
    report_categories = {}
    # Önce tüm rapor tiplerini tanımla ve kategorileri oluştur
    for report_type, report_type_display in Report.REPORT_TYPE_CHOICES:
        report_categories[report_type] = {
            'name': report_type_display,
            'reports': [],
            'icon': get_report_icon(report_type),
            'color': get_report_color(report_type)
        }
    
    # Raporları kategorilerine göre ekle
    for report in related_reports:
        if report.report_type in report_categories:
            # Her kategoride en fazla 5 rapor göster
            if len(report_categories[report.report_type]['reports']) < 5:
                report_categories[report.report_type]['reports'].append(report)
    
    # Boş kategorileri kaldır
    report_categories = {k: v for k, v in report_categories.items() if v['reports']}

    # Kullanıcının bildirimleri
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]  # Son 10 bildirim

    context = {
        'title': 'Kişisel Menü',
        'assigned_projects': active_projects,
        'completed_projects': completed_projects,
        'assigned_tasks': assigned_tasks,
        'related_reports': related_reports,
        'report_categories': report_categories,
        'notifications': notifications,
        'now': timezone.now(),
    }
    
    return render(request, 'dashboard/personal_menu.html', context)

def get_report_icon(report_type):
    """Rapor tipine göre ikon döndür"""
    icons = {
        'project_progress': 'chart-line',
        'time_usage': 'clock',
        'user_performance': 'user-check', 
        'workload': 'weight',
        'custom': 'file-alt'
    }
    return icons.get(report_type, 'file-alt')

def get_report_color(report_type):
    """Rapor tipine göre renk döndür"""
    colors = {
        'project_progress': 'info',
        'time_usage': 'primary',
        'user_performance': 'success',
        'workload': 'warning',
        'custom': 'secondary'
    }
    return colors.get(report_type, 'secondary')
