from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg, Max, Min, Q
from datetime import datetime, timedelta

from .models import Report, ReportSubscription
from projects.models import Project
from tasks.models import Task, TimeLog
from accounts.models import CustomUser

# Create your views here.

@login_required
def report_list(request):
    """
    Tüm raporları listeler.
    """
    reports = Report.objects.all().order_by('-created_at')
    
    # Filtreleme
    report_type = request.GET.get('type')
    current_report_type_display = None
    if report_type:
        reports = reports.filter(report_type=report_type)
        # Mevcut rapor tipinin görüntülenecek adını bul
        report_types_dict = dict(Report.REPORT_TYPE_CHOICES)
        if report_type in report_types_dict:
            current_report_type_display = report_types_dict[report_type]
    
    # Proje filtreleme
    project_id = request.GET.get('project')
    if project_id:
        reports = reports.filter(project_id=project_id)
    
    # Arama
    query = request.GET.get('q')
    if query:
        reports = reports.filter(Q(title__icontains=query) | Q(description__icontains=query))
    
    # Sayfalama
    paginator = Paginator(reports, 10)  # Her sayfada 10 rapor
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Projeler (filtreleme için)
    projects = Project.objects.all().order_by('name')
    
    context = {
        'title': 'Raporlar',
        'page_obj': page_obj,
        'report_types': dict(Report.REPORT_TYPE_CHOICES),
        'projects': projects,
        'current_filters': {
            'type': report_type,
            'project': project_id,
            'q': query
        },
        'current_report_type_display': current_report_type_display
    }
    
    return render(request, 'reports/report_list.html', context)

@login_required
def report_detail(request, report_id):
    """
    Rapor detaylarını gösterir.
    """
    report = get_object_or_404(Report, id=report_id)
    
    # Kullanıcının abonelik durumunu kontrol et
    is_subscribed = ReportSubscription.objects.filter(report=report, user=request.user).exists()
    
    # Rapora abone ol/abonelikten çık butonu için
    if request.method == 'POST' and 'toggle_subscription' in request.POST:
        if is_subscribed:
            ReportSubscription.objects.filter(report=report, user=request.user).delete()
            messages.success(request, 'Rapor aboneliğiniz iptal edildi.')
        else:
            ReportSubscription.objects.create(
                report=report,
                user=request.user,
                email_notification=True,
                system_notification=True
            )
            messages.success(request, 'Rapora başarıyla abone oldunuz.')
        return redirect('reports:report_detail', report_id=report.id)
    
    # Rapor verilerini hazırla
    context = {
        'title': report.title,
        'report': report,
        'is_subscribed': is_subscribed,
    }
    
    # Rapor tipine göre ek veri hazırla
    if report.report_type == 'project_progress':
        context.update(generate_project_progress_data(report))
    elif report.report_type == 'time_usage':
        context.update(generate_time_usage_data(report))
    elif report.report_type == 'user_performance':
        context.update(generate_user_performance_data(report))
    elif report.report_type == 'workload':
        context.update(generate_workload_data(report))
    
    return render(request, 'reports/report_detail.html', context)

@login_required
def report_create(request):
    """
    Yeni rapor oluşturma sayfası.
    """
    # Projeler
    projects = Project.objects.all().order_by('name')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        report_type = request.POST.get('report_type')
        project_id = request.POST.get('project')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        
        # Basit doğrulama
        if not title or not report_type:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
            return redirect('reports:report_create')
        
        # Proje kontrolü
        project = None
        if project_id:
            project = get_object_or_404(Project, id=project_id)
        
        # Tarih kontrolü
        try:
            if date_from:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            else:
                date_from = None
                
            if date_to:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            else:
                date_to = None
        except ValueError:
            messages.error(request, 'Geçersiz tarih formatı.')
            return redirect('reports:report_create')
        
        # Raporu oluştur
        report = Report.objects.create(
            title=title,
            description=description,
            report_type=report_type,
            project=project,
            date_from=date_from,
            date_to=date_to,
            created_by=request.user
        )
        
        # Raporu oluşturan kullanıcıyı otomatik olarak abone yap
        ReportSubscription.objects.create(
            report=report,
            user=request.user,
            email_notification=True,
            system_notification=True
        )
        
        messages.success(request, 'Rapor başarıyla oluşturuldu.')
        return redirect('reports:report_detail', report_id=report.id)
    
    context = {
        'title': 'Yeni Rapor Oluştur',
        'projects': projects,
        'report_types': Report.REPORT_TYPE_CHOICES
    }
    
    return render(request, 'reports/report_create.html', context)

@login_required
def report_update(request, report_id):
    """
    Rapor güncelleme sayfası.
    """
    report = get_object_or_404(Report, id=report_id)
    projects = Project.objects.all().order_by('name')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        project_id = request.POST.get('project')
        date_from = request.POST.get('date_from')
        date_to = request.POST.get('date_to')
        
        # Basit doğrulama
        if not title:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
            return redirect('reports:report_update', report_id=report.id)
        
        # Proje kontrolü
        project = None
        if project_id:
            project = get_object_or_404(Project, id=project_id)
        
        # Tarih kontrolü
        try:
            if date_from:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            else:
                date_from = None
                
            if date_to:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            else:
                date_to = None
        except ValueError:
            messages.error(request, 'Geçersiz tarih formatı.')
            return redirect('reports:report_update', report_id=report.id)
        
        # Raporu güncelle
        report.title = title
        report.description = description
        report.project = project
        report.date_from = date_from
        report.date_to = date_to
        report.save()
        
        messages.success(request, 'Rapor başarıyla güncellendi.')
        return redirect('reports:report_detail', report_id=report.id)
    
    context = {
        'title': 'Raporu Düzenle',
        'report': report,
        'projects': projects,
        'report_types': Report.REPORT_TYPE_CHOICES
    }
    
    return render(request, 'reports/report_update.html', context)

@login_required
def report_delete(request, report_id):
    """
    Rapor silme sayfası.
    """
    report = get_object_or_404(Report, id=report_id)
    
    if request.method == 'POST':
        report.delete()
        messages.success(request, 'Rapor başarıyla silindi.')
        return redirect('reports:report_list')
    
    context = {
        'title': 'Raporu Sil',
        'report': report
    }
    
    return render(request, 'reports/report_delete.html', context)

@login_required
def report_run(request, report_id):
    """
    Raporu manuel olarak çalıştırır.
    """
    report = get_object_or_404(Report, id=report_id)
    
    # Raporu çalıştır
    report.last_run = timezone.now()
    report.save()
    
    # Burada rapor oluşturma mantığı çağrılabilir
    # report.generate()
    
    messages.success(request, 'Rapor başarıyla çalıştırıldı.')
    return redirect('reports:report_detail', report_id=report.id)

# Yardımcı fonksiyonlar
def generate_project_progress_data(report):
    """
    Proje ilerleme raporu için veri üretir.
    """
    data = {}
    
    # Tarih aralığını belirle
    date_from = report.date_from
    date_to = report.date_to or timezone.now().date()
    
    # Proje kontrolü
    if report.project:
        projects = [report.project]
    else:
        projects = Project.objects.all()
    
    # Proje verilerini topla
    project_data = []
    for project in projects:
        tasks = project.tasks.all()
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='completed').count()
        progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        project_data.append({
            'project': project,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'progress': round(progress, 1),
            'is_overdue': project.is_overdue
        })
    
    data['project_data'] = project_data
    return data

def generate_time_usage_data(report):
    """
    Zaman kullanım raporu için veri üretir.
    """
    data = {}
    
    # Tarih aralığını belirle
    date_from = report.date_from
    date_to = report.date_to or timezone.now().date()
    
    # Proje kontrolü
    if report.project:
        time_logs = TimeLog.objects.filter(task__project=report.project)
    else:
        time_logs = TimeLog.objects.all()
    
    # Tarih aralığına göre filtrele
    if date_from:
        time_logs = time_logs.filter(date__gte=date_from)
    if date_to:
        time_logs = time_logs.filter(date__lte=date_to)
    
    # Toplam saat
    total_hours = time_logs.aggregate(total=Sum('hours'))['total'] or 0
    
    # Kullanıcılara göre saatler
    user_hours = time_logs.values('user__username', 'user__first_name', 'user__last_name') \
                         .annotate(total_hours=Sum('hours')) \
                         .order_by('-total_hours')
    
    # Kullanıcı yüzdelerini hesapla
    if total_hours > 0:
        for item in user_hours:
            item['percentage'] = round((item['total_hours'] / total_hours) * 100, 1)
    else:
        for item in user_hours:
            item['percentage'] = 0
    
    # Projelere göre saatler
    project_hours = time_logs.values('task__project__name') \
                            .annotate(total_hours=Sum('hours')) \
                            .order_by('-total_hours')
    
    # Proje yüzdelerini hesapla
    if total_hours > 0:
        for item in project_hours:
            item['percentage'] = round((item['total_hours'] / total_hours) * 100, 1)
    else:
        for item in project_hours:
            item['percentage'] = 0
    
    # Günlere göre saatler
    date_hours = time_logs.values('date') \
                         .annotate(total_hours=Sum('hours')) \
                         .order_by('date')
    
    # Tarih yüzdelerini hesapla
    if total_hours > 0:
        for item in date_hours:
            item['percentage'] = round((item['total_hours'] / total_hours) * 100, 1)
    else:
        for item in date_hours:
            item['percentage'] = 0
    
    data.update({
        'total_hours': total_hours,
        'user_hours': user_hours,
        'project_hours': project_hours,
        'date_hours': date_hours
    })
    
    return data

def generate_user_performance_data(report):
    """
    Kullanıcı performans raporu için veri üretir.
    """
    data = {}
    
    # Tarih aralığını belirle
    date_from = report.date_from
    date_to = report.date_to or timezone.now().date()
    
    # Tüm kullanıcıları al
    users = CustomUser.objects.all()
    
    # Genel istatistikler için değişkenler
    total_completed_tasks = 0
    total_completion_days = 0
    total_on_time_tasks = 0
    task_count_with_due_date = 0
    
    # Kullanıcı verilerini topla
    user_data = []
    user_performance = []  # Şablonda kullanılacak formatlanmış kullanıcı verileri
    
    for user in users:
        # Kullanıcıya atanan görevler
        tasks = Task.objects.filter(assignee=user)
        
        # Tamamlanan görevler
        completed_tasks = tasks.filter(status='completed')
        if date_from:
            completed_tasks = completed_tasks.filter(completed_date__gte=date_from)
        if date_to:
            completed_tasks = completed_tasks.filter(completed_date__lte=date_to)
        
        completed_count = completed_tasks.count()
        
        # Tamamlanan görevlerde kriterlere uygun olanları toplam sayılara ekle
        total_completed_tasks += completed_count
        
        # Toplam süre
        time_logs = TimeLog.objects.filter(user=user)
        if date_from:
            time_logs = time_logs.filter(date__gte=date_from)
        if date_to:
            time_logs = time_logs.filter(date__lte=date_to)
        
        total_hours = time_logs.aggregate(total=Sum('hours'))['total'] or 0
        
        # Tamamlama süresi hesaplama (gün olarak)
        avg_days = 0
        on_time_tasks = 0
        tasks_with_due_date = 0
        
        for task in completed_tasks:
            if task.completed_date and task.created_at:
                task_days = (task.completed_date - task.created_at.date()).days
                total_completion_days += task_days
                
            if task.due_date:
                tasks_with_due_date += 1
                task_count_with_due_date += 1
                
                if task.completed_date and task.completed_date <= task.due_date:
                    on_time_tasks += 1
                    total_on_time_tasks += 1
        
        # Kullanıcının ortalama tamamlama süresi
        if completed_count > 0:
            avg_days = total_completion_days / completed_count
        
        # Zamanında tamamlama yüzdesi
        on_time_percentage = 0
        if tasks_with_due_date > 0:
            on_time_percentage = (on_time_tasks / tasks_with_due_date) * 100
        
        # Performans puanı (5 üzerinden)
        # Basit bir hesaplama: %100 zamanında tamamlama = 5 yıldız
        rating = min(5, round(on_time_percentage / 20))
        rating_stars = rating  # Dolu yıldız sayısı
        empty_stars = 5 - rating  # Boş yıldız sayısı
        
        # Kullanıcı verilerini ekle
        user_data.append({
            'user': user,
            'total_tasks': tasks.count(),
            'completed_tasks': completed_count,
            'total_hours': total_hours,
            'avg_days': avg_days,
            'on_time_percentage': on_time_percentage,
            'rating': rating
        })
        
        # Şablon için formatlanmış kullanıcı verileri
        user_performance.append({
            'user__first_name': user.first_name,
            'user__last_name': user.last_name,
            'user__username': user.username,
            'completed_tasks': completed_count,
            'avg_days': avg_days,
            'on_time_percentage': on_time_percentage,
            'rating_stars': rating_stars,
            'empty_stars': empty_stars
        })
    
    # Genel istatistikleri hesapla
    avg_completion_days = 0
    if total_completed_tasks > 0:
        avg_completion_days = total_completion_days / total_completed_tasks
    
    on_time_percentage = 0
    if task_count_with_due_date > 0:
        on_time_percentage = (total_on_time_tasks / task_count_with_due_date) * 100
    
    # Verileri döndür
    data['user_data'] = sorted(user_data, key=lambda x: x['completed_tasks'], reverse=True)
    data['user_performance'] = sorted(user_performance, key=lambda x: x['completed_tasks'], reverse=True)
    data['total_completed_tasks'] = total_completed_tasks
    data['avg_completion_days'] = avg_completion_days
    data['on_time_percentage'] = on_time_percentage
    
    return data

def generate_workload_data(report):
    """
    İş yükü analizi raporu için veri üretir.
    """
    data = {}
    
    # Tarih aralığını belirle
    date_from = report.date_from
    date_to = report.date_to or timezone.now().date()
    today = timezone.now().date()
    
    # Tüm kullanıcıları al
    users = CustomUser.objects.all()
    
    # Kullanıcı verilerini topla
    user_workload = []
    for user in users:
        # Kullanıcıya atanan tüm görevler
        assigned_tasks = Task.objects.filter(assignee=user)
        
        # Kullanıcıya atanan açık/aktif görevler
        active_tasks = assigned_tasks.filter(
            status__in=['todo', 'in_progress', 'review']
        )
        
        # Geciken görevler
        overdue_tasks = active_tasks.filter(
            due_date__lt=today
        )
        
        # Tahmin edilen süreler
        estimated_hours = active_tasks.aggregate(total=Sum('estimate_hours'))['total'] or 0
        
        # Son 30 günde harcanan süre
        thirty_days_ago = today - timedelta(days=30)
        recent_hours = TimeLog.objects.filter(
            user=user,
            date__gte=thirty_days_ago
        ).aggregate(total=Sum('hours'))['total'] or 0
        
        # İş yükü yüzdesi hesaplama (yaklaşık bir metrik)
        # Burada tahmin edilen saat 0'dan büyükse, bir iş yükü hesaplanır
        # Değilse, aktif görev sayısına göre bir tahmin yapılır
        if estimated_hours > 0:
            # Tahmin edilen saatler üzerinden yüzde hesabı
            # Haftalık 40 saat normal iş yükü kabul edilirse
            workload_percentage = min(100, (estimated_hours / 40) * 100)
        else:
            # Görev sayısı ile basit bir hesaplama (5 görev = %50 iş yükü, 10 veya daha fazla = %100)
            workload_percentage = min(100, (active_tasks.count() / 10) * 100)
        
        user_workload.append({
            'user__first_name': user.first_name,
            'user__last_name': user.last_name,
            'user__username': user.username,
            'assigned_tasks': assigned_tasks.count(),
            'active_tasks': active_tasks.count(),
            'overdue_tasks': overdue_tasks.count(),
            'estimated_hours': estimated_hours,
            'recent_hours': recent_hours,
            'workload_percentage': workload_percentage
        })
    
    # Proje bazlı iş yükü verileri
    project_workload = []
    projects = Project.objects.all()
    
    for project in projects:
        # Projedeki tüm görevler
        project_tasks = Task.objects.filter(project=project)
        total_tasks = project_tasks.count()
        
        # Geciken görevler
        overdue_tasks = project_tasks.filter(
            status__in=['todo', 'in_progress', 'review'],
            due_date__lt=today
        ).count()
        
        # Projenin tamamlanma yüzdesi
        completed_tasks = project_tasks.filter(status='completed').count()
        completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Ters iş yükü yüzdesi (tamamlanma yüzdesinin tersi)
        workload_percentage = 100 - completion_percentage
        
        project_workload.append({
            'name': project.name,
            'total_tasks': total_tasks,
            'overdue_tasks': overdue_tasks,
            'workload_percentage': workload_percentage
        })
    
    # Risk altındaki görevler
    risky_tasks = []
    # Yaklaşan son tarihi olan aktif görevleri bul
    upcoming_deadline = today + timedelta(days=7)  # Önümüzdeki 7 gün
    
    tasks_at_risk = Task.objects.filter(
        status__in=['todo', 'in_progress', 'review'],
        due_date__gte=today,
        due_date__lte=upcoming_deadline
    ).select_related('project', 'assignee')
    
    for task in tasks_at_risk:
        # Görevin son tarihine kalan gün sayısı
        days_left = (task.due_date - today).days
        
        # Risk seviyesi belirleme
        if days_left <= 2:
            risk_level = 'yüksek'
        elif days_left <= 5:
            risk_level = 'orta'
        else:
            risk_level = 'düşük'
        
        risky_tasks.append({
            'name': task.title,
            'project__name': task.project.name if task.project else "Belirsiz",
            'assigned_to__first_name': task.assignee.first_name if task.assignee else "",
            'assigned_to__last_name': task.assignee.last_name if task.assignee else "",
            'due_date': task.due_date,
            'risk_level': risk_level
        })
    
    data.update({
        'user_workload': sorted(user_workload, key=lambda x: x['workload_percentage'], reverse=True),
        'project_workload': sorted(project_workload, key=lambda x: x['workload_percentage'], reverse=True),
        'risky_tasks': sorted(risky_tasks, key=lambda x: x['due_date'])
    })
    
    return data
