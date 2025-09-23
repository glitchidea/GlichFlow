import os
import mimetypes
import markdown
from django.http import HttpResponse, Http404
from django.conf import settings
from django.utils.safestring import mark_safe

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Project, Attachment, PRD
from tasks.models import Task

@login_required
def project_list(request):
    """
    Tüm projeleri listeler.
    """
    # Filtreleme parametreleri
    status = request.GET.get('status')
    priority = request.GET.get('priority')
    search = request.GET.get('search')
    
    # Temel sorgu
    projects = Project.objects.all().prefetch_related('team_members', 'tasks')
    
    # Kullanıcı rolüne göre filtreleme
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        # Yönetici değilse, sadece kendi projelerini görebilir
        projects = projects.filter(
            Q(manager=request.user) | Q(team_members=request.user)
        ).distinct()
    
    # Diğer filtreleri uygulama
    if status:
        projects = projects.filter(status=status)
    
    if priority:
        projects = projects.filter(priority=priority)
    
    if search:
        projects = projects.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # İstatistikleri hesapla
    total_projects = projects.count()
    active_projects = projects.filter(status='in_progress').count()
    completed_projects = projects.filter(status='completed').count()
    overdue_projects = projects.filter(end_date__lt=timezone.now().date()).exclude(status='completed').count()
    
    context = {
        'projects': projects,
        'total_projects': total_projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'overdue_projects': overdue_projects,
        'status_filter': status,
        'priority_filter': priority,
        'search_query': search,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
        'title': 'Projeler',
    }
    
    return render(request, 'projects/project_list.html', context)

@login_required
def project_detail(request, project_id):
    """
    Proje detaylarını gösterir.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != project.manager and request.user not in project.team_members.all():
            messages.error(request, 'Bu projeyi görüntüleme yetkiniz yok.')
            return redirect('projects:project_list')
    
    # Görevler ve metrikleri getir
    tasks = project.tasks.all().select_related('assignee')
    
    # Görev istatistikleri
    task_counts = {
        'total': tasks.count(),
        'todo': tasks.filter(status='todo').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'review': tasks.filter(status='review').count(),
        'completed': tasks.filter(status='completed').count(),
        'cancelled': tasks.filter(status='cancelled').count(),
    }
    
    # Dosya ekleri
    attachments = project.attachments.all().select_related('uploaded_by')
    
    context = {
        'project': project,
        'tasks': tasks,
        'task_counts': task_counts,
        'attachments': attachments,
        'title': project.name,
    }
    
    return render(request, 'projects/project_detail.html', context)

@login_required
def project_create(request):
    """
    Yeni proje oluşturma formu ve işleme.
    """
    # Yetkilendirme kontrolü - Sadece admin ve proje yöneticileri proje oluşturabilir
    if not request.user.is_superuser and request.user.role != 'project_manager':
        messages.error(request, 'Proje oluşturma yetkiniz yok. Bu işlem yalnızca proje yöneticileri veya sistem yöneticileri tarafından yapılabilir.')
        return redirect('projects:project_list')
    
    if request.method == 'POST':
        # Form verilerini işle
        name = request.POST.get('name')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        status = request.POST.get('status')
        priority = request.POST.get('priority')
        budget = request.POST.get('budget') or None
        manager_id = request.POST.get('manager')
        team_members = request.POST.getlist('team_members')
        
        if not name or not start_date or not status or not priority:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            # Yeni proje oluştur
            project = Project(
                name=name,
                description=description,
                start_date=start_date,
                end_date=end_date,
                status=status,
                priority=priority,
                budget=budget,
                manager_id=manager_id,
                created_at=timezone.now()
            )
            project.save()
            
            # Takım üyelerini ekle
            if team_members:
                project.team_members.set(team_members)
            
            messages.success(request, f'"{name}" projesi başarıyla oluşturuldu.')
            return redirect('projects:project_detail', project_id=project.id)
    
    # Proje yöneticisi olabilecek kullanıcıları getir
    from accounts.models import CustomUser
    managers = CustomUser.objects.filter(role__in=['admin', 'project_manager'])
    team_members = CustomUser.objects.filter(role__in=['team_member', 'project_manager'])
    
    context = {
        'managers': managers,
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
        'title': 'Yeni Proje',
    }
    
    return render(request, 'projects/project_form.html', context)

@login_required
def project_update(request, project_id):
    """
    Proje düzenleme formu ve işleme.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager'] and request.user != project.manager:
        messages.error(request, 'Bu projeyi düzenleme yetkiniz yok.')
        return redirect('projects:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        # Form verilerini işle
        name = request.POST.get('name')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        status = request.POST.get('status')
        priority = request.POST.get('priority')
        budget = request.POST.get('budget') or None
        cost = request.POST.get('cost') or None
        manager_id = request.POST.get('manager')
        team_members = request.POST.getlist('team_members')
        
        # PRD oluşturma seçeneği
        create_prd = request.POST.get('create_prd') == 'on'
        
        if not name or not start_date or not status or not priority:
            messages.error(request, 'Lütfen gerekli alanları doldurun.')
        else:
            # Projeyi güncelle
            project.name = name
            project.description = description
            project.start_date = start_date
            project.end_date = end_date
            project.status = status
            project.priority = priority
            project.budget = budget
            project.cost = cost
            project.manager_id = manager_id
            project.save()
            
            # Takım üyelerini güncelle
            project.team_members.set(team_members)
            
            # PRD oluşturma seçeneği işaretlenmişse PRD oluştur
            if create_prd:
                prd_title = request.POST.get('prd_title', f'{name} - PRD')
                prd_product_summary = request.POST.get('prd_product_summary', '')
                prd_target_audience = request.POST.get('prd_target_audience', '')
                prd_functional_requirements = request.POST.get('prd_functional_requirements', '')
                prd_document = request.FILES.get('prd_document')
                
                prd = PRD.objects.create(
                    title=prd_title,
                    product_summary=prd_product_summary,
                    target_audience=prd_target_audience,
                    functional_requirements=prd_functional_requirements,
                    project=project,
                    created_by=request.user,
                    assigned_by=request.user,
                    document=prd_document,
                    assigned_at=timezone.now()
                )
                
                messages.success(request, f'"{name}" projesi güncellendi ve PRD başarıyla oluşturuldu.')
            else:
                messages.success(request, f'"{name}" projesi başarıyla güncellendi.')
            
            return redirect('projects:project_detail', project_id=project.id)
    
    # Proje yöneticisi olabilecek kullanıcıları getir
    from accounts.models import CustomUser
    managers = CustomUser.objects.filter(role__in=['admin', 'project_manager'])
    team_members = CustomUser.objects.all()
    
    context = {
        'project': project,
        'managers': managers,
        'team_members': team_members,
        'status_choices': Project.STATUS_CHOICES,
        'priority_choices': Project.PRIORITY_CHOICES,
        'title': f'{project.name} - Düzenle',
    }
    
    return render(request, 'projects/project_form.html', context)

@login_required
def project_delete(request, project_id):
    """
    Proje silme işlemi.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user != project.manager:
        messages.error(request, 'Bu projeyi silme yetkiniz yok.')
        return redirect('projects:project_detail', project_id=project.id)
    
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'"{name}" projesi başarıyla silindi.')
        return redirect('projects:project_list')
    
    context = {
        'project': project,
        'title': f'{project.name} - Sil',
    }
    
    return render(request, 'projects/project_confirm_delete.html', context)

@login_required
def attachment_upload(request, project_id):
    """
    Proje için dosya ekleme.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager'] and request.user != project.manager and request.user not in project.team_members.all():
        messages.error(request, 'Bu projeye dosya yükleme yetkiniz yok.')
        return redirect('projects:project_detail', project_id=project.id)
    
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
                project=project
            )
            attachment.save()
            
            messages.success(request, f'"{name}" dosyası başarıyla yüklendi.')
        
        return redirect('projects:project_detail', project_id=project.id)
    
    context = {
        'project': project,
        'title': f'{project.name} - Dosya Ekle',
    }
    
    return render(request, 'projects/attachment_form.html', context)

@login_required
def attachment_delete(request, attachment_id):
    """
    Dosya ekini silme işlemi. Sadece dosyayı yükleyen kullanıcı veya admin/proje yöneticisi silebilir.
    """
    attachment = get_object_or_404(Attachment, id=attachment_id)
    
    # Yetkilendirme kontrolü - Sadece dosyayı yükleyen kullanıcı veya admin/proje yöneticisi silebilir
    if request.user != attachment.uploaded_by and request.user.role not in ['admin', 'project_manager']:
        messages.error(request, 'Bu dosyayı silme yetkiniz yok. Sadece dosyayı yükleyen kullanıcı silebilir.')
        
        # Proje veya görev detayına yönlendir
        if attachment.project:
            return redirect('projects:project_detail', project_id=attachment.project.id)
        elif attachment.task:
            return redirect('tasks:task_detail', task_id=attachment.task.id)
        else:
            return redirect('dashboard:index')
    
    # Silme işlemi onaylandığında
    if request.method == 'POST':
        # Yönlendirme için hedef sayfayı belirle
        if attachment.project:
            redirect_url = reverse('projects:project_detail', kwargs={'project_id': attachment.project.id})
        elif attachment.task:
            redirect_url = reverse('tasks:task_detail', kwargs={'task_id': attachment.task.id})
        else:
            redirect_url = reverse('dashboard:index')
        
        # Dosya adını kaydet
        file_name = attachment.name
        
        # Dosyayı sil
        attachment.delete()
        
        messages.success(request, f'"{file_name}" dosyası başarıyla silindi.')
        return HttpResponseRedirect(redirect_url)
    
    # Silme onayı sayfasını göster
    context = {
        'attachment': attachment,
        'title': f'{attachment.name} - Dosya Sil',
    }
    
    return render(request, 'projects/attachment_confirm_delete.html', context)

@login_required
def prd_list(request):
    """
    Tüm PRD'leri listeler.
    """
    # Filtreleme parametreleri
    status = request.GET.get('status')
    search = request.GET.get('search')
    assigned_to = request.GET.get('assigned_to')  # project veya task
    project_id = request.GET.get('project')
    task_id = request.GET.get('task')
    
    # Temel sorgu
    prds = PRD.objects.all().select_related('created_by', 'assigned_by', 'project', 'task')
    
    # Kullanıcı rolüne göre filtreleme
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        # Yönetici değilse, sadece kendi oluşturduğu veya atandığı PRD'leri görebilir
        prds = prds.filter(
            Q(created_by=request.user) | Q(assigned_by=request.user)
        )
    
    # Diğer filtreleri uygulama
    if status:
        prds = prds.filter(status=status)
    
    if search:
        prds = prds.filter(
            Q(title__icontains=search) | 
            Q(product_summary__icontains=search) |
            Q(target_audience__icontains=search) |
            Q(functional_requirements__icontains=search)
        )
    
    if assigned_to:
        if assigned_to == 'project':
            prds = prds.filter(project__isnull=False)
        elif assigned_to == 'task':
            prds = prds.filter(task__isnull=False)
        elif assigned_to == 'unassigned':
            prds = prds.filter(project__isnull=True, task__isnull=True)
    
    if project_id:
        prds = prds.filter(project_id=project_id)
    
    if task_id:
        prds = prds.filter(task_id=task_id)
    
    # Sayfalama
    paginator = Paginator(prds, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # İstatistikler
    total_prds = prds.count()
    draft_prds = prds.filter(status='draft').count()
    review_prds = prds.filter(status='review').count()
    approved_prds = prds.filter(status='approved').count()
    
    # Filtreleme için projeleri getir
    projects = Project.objects.all()
    
    context = {
        'prds': page_obj,
        'total_prds': total_prds,
        'draft_prds': draft_prds,
        'review_prds': review_prds,
        'approved_prds': approved_prds,
        'projects': projects,
        'status_choices': PRD.STATUS_CHOICES,
        'title': 'PRD\'ler',
    }
    
    return render(request, 'projects/prd_list.html', context)

@login_required
def prd_detail(request, prd_id):
    """
    PRD detaylarını gösterir.
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != prd.created_by and request.user != prd.assigned_by:
            messages.error(request, 'Bu PRD\'yi görüntüleme yetkiniz yok.')
            return redirect('projects:prd_list')
    
    context = {
        'prd': prd,
        'title': prd.title,
    }
    
    return render(request, 'projects/prd_detail.html', context)

@login_required
def prd_create(request):
    """
    Yeni PRD oluşturur.
    """
    if request.method == 'POST':
        title = request.POST.get('title')
        product_summary = request.POST.get('product_summary', '')
        target_audience = request.POST.get('target_audience', '')
        functional_requirements = request.POST.get('functional_requirements', '')
        non_functional_requirements = request.POST.get('non_functional_requirements', '')
        user_stories = request.POST.get('user_stories', '')
        acceptance_criteria = request.POST.get('acceptance_criteria', '')
        technical_requirements = request.POST.get('technical_requirements', '')
        design_constraints = request.POST.get('design_constraints', '')
        project_id = request.POST.get('project')
        task_id = request.POST.get('task')
        document = request.FILES.get('document')
        
        # Validasyon
        if not title:
            messages.error(request, 'PRD başlığı gereklidir.')
            return redirect('projects:prd_create')
        
        # PRD oluştur
        prd = PRD.objects.create(
            title=title,
            product_summary=product_summary,
            target_audience=target_audience,
            functional_requirements=functional_requirements,
            non_functional_requirements=non_functional_requirements,
            user_stories=user_stories,
            acceptance_criteria=acceptance_criteria,
            technical_requirements=technical_requirements,
            design_constraints=design_constraints,
            created_by=request.user,
            document=document
        )
        
        # Proje veya göreve ata (opsiyonel)
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            prd.project = project
        elif task_id:
            task = get_object_or_404(Task, id=task_id)
            prd.task = task
        
        prd.save()
        
        messages.success(request, 'PRD başarıyla oluşturuldu.')
        return redirect('projects:prd_detail', prd_id=prd.id)
    
    # GET isteği - form göster
    projects = Project.objects.all()
    tasks = Task.objects.all()
    
    # URL'den proje ve görev parametrelerini al
    project_id = request.GET.get('project')
    task_id = request.GET.get('task')
    selected_project = None
    selected_task = None
    
    if project_id:
        try:
            selected_project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            pass
    
    if task_id:
        try:
            selected_task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            pass
    
    context = {
        'projects': projects,
        'tasks': tasks,
        'selected_project': selected_project,
        'selected_task': selected_task,
        'title': 'Yeni PRD Oluştur',
    }
    
    return render(request, 'projects/prd_form.html', context)

@login_required
def prd_edit(request, prd_id):
    """
    PRD düzenler.
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user != prd.created_by and request.user.role not in ['admin', 'project_manager']:
        messages.error(request, 'Bu PRD\'yi düzenleme yetkiniz yok.')
        return redirect('projects:prd_detail', prd_id=prd.id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        product_summary = request.POST.get('product_summary', '')
        target_audience = request.POST.get('target_audience', '')
        functional_requirements = request.POST.get('functional_requirements', '')
        non_functional_requirements = request.POST.get('non_functional_requirements', '')
        user_stories = request.POST.get('user_stories', '')
        acceptance_criteria = request.POST.get('acceptance_criteria', '')
        technical_requirements = request.POST.get('technical_requirements', '')
        design_constraints = request.POST.get('design_constraints', '')
        status = request.POST.get('status', 'draft')
        document = request.FILES.get('document')
        
        # Atama bilgilerini al
        assignment_type = request.POST.get('assignment_type')
        project_id = request.POST.get('project')
        task_id = request.POST.get('task')
        
        # Validasyon
        if not title:
            messages.error(request, 'PRD başlığı gereklidir.')
            return redirect('projects:prd_edit', prd_id=prd.id)
        
        # PRD güncelle
        prd.title = title
        prd.product_summary = product_summary
        prd.target_audience = target_audience
        prd.functional_requirements = functional_requirements
        prd.non_functional_requirements = non_functional_requirements
        prd.user_stories = user_stories
        prd.acceptance_criteria = acceptance_criteria
        prd.technical_requirements = technical_requirements
        prd.design_constraints = design_constraints
        prd.status = status
        
        if document:
            prd.document = document
        
        # Atama işlemi
        if assignment_type == 'project' and project_id:
            project = get_object_or_404(Project, id=project_id)
            prd.project = project
            prd.task = None  # Görev atamasını temizle
        elif assignment_type == 'task' and task_id:
            task = get_object_or_404(Task, id=task_id)
            prd.task = task
            prd.project = None  # Proje atamasını temizle
        elif assignment_type == 'none':
            # Atama yapma seçeneği seçildiyse mevcut atamaları koru
            # (kullanıcı sadece PRD içeriğini güncellemek istiyor olabilir)
            pass
        
        prd.save()
        
        messages.success(request, 'PRD başarıyla güncellendi.')
        return redirect('projects:prd_detail', prd_id=prd.id)
    
    # GET isteği - form göster
    # Proje ve görev listelerini al
    projects = Project.objects.all().order_by('name')
    tasks = Task.objects.all().order_by('title')
    
    context = {
        'prd': prd,
        'projects': projects,
        'tasks': tasks,
        'status_choices': PRD.STATUS_CHOICES,
        'title': 'PRD Düzenle',
    }
    
    return render(request, 'projects/prd_form.html', context)

@login_required
def prd_assign(request, prd_id):
    """
    PRD'yi bir projeye veya göreve atar.
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager']:
        messages.error(request, 'PRD atama yetkiniz yok.')
        return redirect('projects:prd_detail', prd_id=prd.id)
    
    if request.method == 'POST':
        project_id = request.POST.get('project')
        task_id = request.POST.get('task')
        
        # Mevcut atamayı temizle
        prd.project = None
        prd.task = None
        
        # Yeni atama yap
        if project_id:
            project = get_object_or_404(Project, id=project_id)
            prd.project = project
        elif task_id:
            task = get_object_or_404(Task, id=task_id)
            prd.task = task
        
        prd.assigned_by = request.user
        prd.assigned_at = timezone.now()
        prd.save()
        
        messages.success(request, 'PRD başarıyla atandı.')
        return redirect('projects:prd_detail', prd_id=prd.id)
    
    # GET isteği - form göster
    projects = Project.objects.all()
    tasks = Task.objects.all()
    
    context = {
        'prd': prd,
        'projects': projects,
        'tasks': tasks,
        'title': 'PRD Ata',
    }
    
    return render(request, 'projects/prd_assign.html', context)

@login_required
@require_POST
def prd_status_change(request, prd_id):
    """
    PRD durumunu değiştirir (AJAX).
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager']:
        return JsonResponse({'success': False, 'message': 'Yetkiniz yok.'})
    
    new_status = request.POST.get('status')
    
    if new_status not in dict(PRD.STATUS_CHOICES):
        return JsonResponse({'success': False, 'message': 'Geçersiz durum.'})
    
    prd.status = new_status
    if new_status == 'review':
        prd.reviewed_at = timezone.now()
    prd.save()
    
    return JsonResponse({
        'success': True, 
        'message': 'PRD durumu güncellendi.',
        'status': new_status,
        'status_display': dict(PRD.STATUS_CHOICES)[new_status]
    })

@login_required
def prd_toggle_assign(request, prd_id):
    """
    PRD atamasını açıp kapatır (AJAX).
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager']:
        return JsonResponse({'success': False, 'message': 'Yetkiniz yok.'})
    
    if prd.project or prd.task:
        # Atamayı kaldır
        prd.project = None
        prd.task = None
        prd.assigned_by = None
        prd.assigned_at = None
        action = 'removed'
    else:
        # Atama yapılabilir duruma getir
        action = 'ready'
    
    prd.save()
    
    return JsonResponse({
        'success': True,
        'action': action,
        'message': 'PRD ataması güncellendi.'
    })

@login_required
def prd_detail_ajax(request, prd_id):
    """
    PRD detaylarını AJAX için döndürür (modal içeriği).
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != prd.created_by and request.user != prd.assigned_by:
            return JsonResponse({'error': 'Bu PRD\'yi görüntüleme yetkiniz yok.'}, status=403)
    
    context = {
        'prd': prd,
    }
    
    return render(request, 'projects/prd_detail_ajax.html', context)

@login_required
def prd_delete(request, prd_id):
    """
    PRD'yi siler.
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role not in ['admin', 'project_manager']:
        if request.user != prd.created_by:
            messages.error(request, 'Bu PRD\'yi silme yetkiniz yok.')
            return redirect('projects:prd_list')
    
    if request.method == 'POST':
        # Silme işlemi
        prd.delete()
        messages.success(request, 'PRD başarıyla silindi.')
        return redirect('projects:prd_list')
    
    # GET isteği - onay sayfası göster
    context = {
        'prd': prd,
        'title': 'PRD Sil',
    }
    
    return render(request, 'projects/prd_delete.html', context)

@login_required
def prd_document_view(request, prd_id):
    """
    PRD dosyasını yeni sayfada gösterir. Markdown dosyaları için özel render desteği.
    """
    prd = get_object_or_404(PRD, id=prd_id)
    
    # Yetkilendirme kontrolü
    if request.user.role != 'admin' and request.user.role != 'project_manager':
        if request.user != prd.created_by and request.user != prd.assigned_by:
            messages.error(request, 'Bu PRD\'yi görüntüleme yetkiniz yok.')
            return redirect('projects:prd_list')
    
    if not prd.document:
        raise Http404("PRD dosyası bulunamadı.")
    
    # Dosya yolunu al
    file_path = prd.document.path
    
    # Dosya uzantısını kontrol et
    file_extension = os.path.splitext(file_path)[1].lower()
    
    # Markdown dosyası ise
    if file_extension in ['.md', '.markdown']:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # Markdown'ı HTML'e çevir
            md = markdown.Markdown(extensions=['extra', 'codehilite', 'toc'])
            html_content = md.convert(content)
            
            context = {
                'prd': prd,
                'content': mark_safe(html_content),
                'is_markdown': True,
                'title': f"{prd.title} - Doküman Görüntüleyici"
            }
            
            return render(request, 'projects/prd_document_view.html', context)
            
        except Exception as e:
            messages.error(request, f'Dosya okuma hatası: {str(e)}')
            return redirect('projects:prd_detail', prd_id=prd.id)
    
    # PDF dosyası ise
    elif file_extension == '.pdf':
        try:
            with open(file_path, 'rb') as file:
                response = HttpResponse(file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
                return response
        except Exception as e:
            messages.error(request, f'PDF dosyası okuma hatası: {str(e)}')
            return redirect('projects:prd_detail', prd_id=prd.id)
    
    # Diğer dosya türleri için basit metin görüntüleme
    else:
        try:
            # MIME tipini belirle
            mime_type, _ = mimetypes.guess_type(file_path)
            
            if mime_type and mime_type.startswith('text/'):
                # Metin dosyası
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                
                context = {
                    'prd': prd,
                    'content': content,
                    'is_markdown': False,
                    'is_text': True,
                    'title': f"{prd.title} - Doküman Görüntüleyici"
                }
                
                return render(request, 'projects/prd_document_view.html', context)
            else:
                # İndirilebilir dosya
                with open(file_path, 'rb') as file:
                    response = HttpResponse(file.read(), content_type=mime_type or 'application/octet-stream')
                    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
                    return response
                    
        except Exception as e:
            messages.error(request, f'Dosya okuma hatası: {str(e)}')
            return redirect('projects:prd_detail', prd_id=prd.id)
