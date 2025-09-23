from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model

from .models import Idea
from .forms import IdeaForm
from accounts.models import CustomUser

# Projects modelini import et
try:
    from projects.models import Project
    PROJECTS_AVAILABLE = True
except ImportError:
    PROJECTS_AVAILABLE = False

User = get_user_model()

def _user_has_idea_tag(user: CustomUser) -> bool:
    """Kullanıcının idea tagına sahip olup olmadığını kontrol eder"""
    return getattr(user, 'has_tag', lambda t: False)('idea')

@login_required
def idea_list(request):
    """Fikir listesi görünümü"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    # Arama ve filtreleme
    search_query = request.GET.get('search', '')
    priority_filter = request.GET.get('priority', '')
    status_filter = request.GET.get('status', '')
    
    ideas = Idea.objects.filter(author=request.user)
    
    if search_query:
        ideas = ideas.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(technologies__icontains=search_query)
        )
    
    if priority_filter:
        ideas = ideas.filter(priority=priority_filter)
    
    if status_filter:
        ideas = ideas.filter(status=status_filter)
    
    # Sayfalama
    paginator = Paginator(ideas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'priority_filter': priority_filter,
        'status_filter': status_filter,
        'priority_choices': Idea.PRIORITY_CHOICES,
        'status_choices': Idea.STATUS_CHOICES,
    }
    
    return render(request, 'ideas/idea_list.html', context)

@login_required
def idea_detail(request, pk):
    """Fikir detay görünümü"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    idea = get_object_or_404(Idea, pk=pk, author=request.user)
    return render(request, 'ideas/idea_detail.html', {'idea': idea})

@login_required
def idea_create(request):
    """Fikir oluşturma görünümü"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = IdeaForm(request.POST)
        if form.is_valid():
            idea = form.save(commit=False)
            idea.author = request.user
            idea.save()
            messages.success(request, 'Fikriniz başarıyla kaydedildi!')
            return redirect('ideas:idea_detail', pk=idea.pk)
    else:
        form = IdeaForm()
    
    return render(request, 'ideas/idea_form.html', {
        'form': form,
        'title': 'Yeni Fikir Ekle',
        'submit_text': 'Kaydet'
    })

@login_required
def idea_update(request, pk):
    """Fikir güncelleme görünümü"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    idea = get_object_or_404(Idea, pk=pk, author=request.user)
    
    if request.method == 'POST':
        form = IdeaForm(request.POST, instance=idea)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fikriniz başarıyla güncellendi!')
            return redirect('ideas:idea_detail', pk=idea.pk)
    else:
        form = IdeaForm(instance=idea)
    
    return render(request, 'ideas/idea_form.html', {
        'form': form,
        'idea': idea,
        'title': 'Fikri Düzenle',
        'submit_text': 'Güncelle'
    })

@login_required
def idea_delete(request, pk):
    """Fikir silme görünümü"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    idea = get_object_or_404(Idea, pk=pk, author=request.user)
    
    if request.method == 'POST':
        idea.delete()
        messages.success(request, 'Fikriniz başarıyla silindi!')
        return redirect('ideas:idea_list')
    
    return render(request, 'ideas/idea_confirm_delete.html', {'idea': idea})

@login_required
def idea_quick_add(request):
    """Hızlı fikir ekleme (AJAX)"""
    if not _user_has_idea_tag(request.user):
        return JsonResponse({'error': 'Yetkiniz bulunmamaktadır.'}, status=403)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not title:
            return JsonResponse({'error': 'Başlık gereklidir.'}, status=400)
        
        try:
            idea = Idea.objects.create(
                title=title,
                description=description,
                author=request.user
            )
            
            # AJAX isteği mi kontrol et
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'idea_id': idea.id,
                    'message': 'Fikriniz başarıyla kaydedildi!',
                    'redirect_url': f'/ideas/{idea.id}/'
                })
            else:
                # Normal form submit ise redirect yap
                messages.success(request, 'Fikriniz başarıyla kaydedildi!')
                return redirect('ideas:idea_detail', pk=idea.pk)
                
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Bir hata oluştu: {str(e)}'}, status=500)
            else:
                messages.error(request, f'Bir hata oluştu: {str(e)}')
                return redirect('ideas:idea_list')
    
    return JsonResponse({'error': 'Geçersiz istek.'}, status=400)


@login_required
def idea_connect_to_project(request, pk):
    """Fikri mevcut projeye bağla"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    if not PROJECTS_AVAILABLE:
        messages.error(request, 'Proje modülü mevcut değil.')
        return redirect('ideas:idea_detail', pk=pk)
    
    idea = get_object_or_404(Idea, pk=pk, author=request.user)
    
    if idea.is_connected_to_project:
        messages.error(request, 'Bu fikir zaten bir projeye bağlı.')
        return redirect('ideas:idea_detail', pk=pk)
    
    # Kullanıcının projelerini al
    user_projects = Project.objects.filter(
        Q(manager=request.user) | Q(team_members=request.user)
    ).distinct()
    
    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        if project_id:
            try:
                project = get_object_or_404(Project, pk=project_id)
                idea.project = project
                idea.status = 'active'  # Aktif olarak işaretle
                idea.save()
                
                messages.success(request, f'Fikir "{project.name}" projesine başarıyla bağlandı!')
                return redirect('ideas:idea_detail', pk=pk)
                
            except Exception as e:
                messages.error(request, f'Proje bağlantısında hata oluştu: {str(e)}')
    
    return render(request, 'ideas/idea_connect_to_project.html', {
        'idea': idea,
        'user_projects': user_projects
    })

@login_required
def idea_disconnect_from_project(request, pk):
    """Fikri projeden ayır"""
    if not _user_has_idea_tag(request.user):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    idea = get_object_or_404(Idea, pk=pk, author=request.user)
    
    if not idea.is_connected_to_project:
        messages.error(request, 'Bu fikir zaten bir projeye bağlı değil.')
        return redirect('ideas:idea_detail', pk=pk)
    
    if request.method == 'POST':
        project_name = idea.project.name
        idea.project = None
        idea.status = 'draft'  # Taslak olarak işaretle
        idea.save()
        
        messages.success(request, f'Fikir "{project_name}" projesinden başarıyla ayrıldı!')
        return redirect('ideas:idea_detail', pk=pk)
    
    return render(request, 'ideas/idea_disconnect_from_project.html', {'idea': idea})