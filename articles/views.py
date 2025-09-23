from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth import get_user_model

from .models import Article, ArticleComment
from .forms import ArticleForm, ArticleCommentForm, ArticleSearchForm
from accounts.models import CustomUser

User = get_user_model()


def _user_has_makale_tag(user):
    """Kullanıcının makale tag'ına sahip olup olmadığını kontrol et"""
    return user.is_authenticated and user.tags.filter(name='makale').exists()


def _user_has_adminmakale_tag(user):
    """Kullanıcının adminmakale tag'ına sahip olup olmadığını kontrol et"""
    return user.is_authenticated and user.tags.filter(name='adminmakale').exists()


def _user_can_edit_article(user, article):
    """Kullanıcının makaleyi düzenleyip düzenleyemeyeceğini kontrol et"""
    if not user.is_authenticated:
        return False
    
    # Sadece adminmakale tag'ı olanlar makale düzenleyebilir
    if _user_has_adminmakale_tag(user):
        return True
    
    return False


def article_list(request):
    """Makale listesi"""
    if not (_user_has_makale_tag(request.user) or _user_has_adminmakale_tag(request.user)):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    # Arama formu
    search_form = ArticleSearchForm(request.GET)
    articles = Article.objects.all()
    
    # Arama filtreleri
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        search_in = search_form.cleaned_data.get('search_in', 'title')
        category = search_form.cleaned_data.get('category')
        status = search_form.cleaned_data.get('status')
        author = search_form.cleaned_data.get('author')
        
        if query:
            if search_in == 'title':
                articles = articles.filter(title__icontains=query)
            elif search_in == 'content':
                articles = articles.filter(content__icontains=query)
            elif search_in == 'tags':
                articles = articles.filter(tags__icontains=query)
            elif search_in == 'author':
                articles = articles.filter(author__username__icontains=query)
        
        if category:
            articles = articles.filter(category=category)
        
        if status:
            articles = articles.filter(status=status)
        
        if author:
            articles = articles.filter(author=author)
    
    # Kullanıcı adminmakale tag'ına sahip değilse sadece yayınlanmış makaleleri göster
    if not _user_has_adminmakale_tag(request.user):
        articles = articles.filter(status='published')
    
    # Sayfalama
    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'can_create': _user_has_adminmakale_tag(request.user),
        'can_manage': _user_has_adminmakale_tag(request.user),
    }
    
    return render(request, 'articles/article_list.html', context)


def article_detail(request, slug):
    """Makale detayı"""
    if not (_user_has_makale_tag(request.user) or _user_has_adminmakale_tag(request.user)):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    article = get_object_or_404(Article, slug=slug)
    
    # Kullanıcı adminmakale tag'ına sahip değilse sadece yayınlanmış makaleleri görebilir
    if not _user_has_adminmakale_tag(request.user) and article.status != 'published':
        messages.error(request, 'Bu makale henüz yayınlanmamış.')
        return redirect('articles:article_list')
    
    # Görüntülenme sayısını artır
    article.increment_view_count()
    
    # Yorum formu
    comment_form = ArticleCommentForm()
    
    # Yorumlar (sadece onaylanmış olanlar)
    comments = article.comments.filter(is_approved=True)
    
    # Benzer makaleler
    similar_articles = Article.objects.filter(
        category=article.category,
        status='published'
    ).exclude(id=article.id)[:3]
    
    context = {
        'article': article,
        'comment_form': comment_form,
        'comments': comments,
        'similar_articles': similar_articles,
        'can_edit': _user_can_edit_article(request.user, article),
        'can_delete': _user_can_edit_article(request.user, article),
    }
    
    return render(request, 'articles/article_detail.html', context)


@login_required
def article_create(request):
    """Makale oluştur"""
    if not _user_has_adminmakale_tag(request.user):
        messages.error(request, 'Makale oluşturma yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            messages.success(request, 'Makale başarıyla oluşturuldu!')
            return redirect('articles:article_detail', slug=article.slug)
        else:
            # Form hatalarını göster
            for field, errors in form.errors.items():
                messages.error(request, f'{field}: {", ".join(errors)}')
    else:
        form = ArticleForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Yeni Makale Oluştur',
        'is_admin': _user_has_adminmakale_tag(request.user),
        'article': None,  # Yeni makale oluştururken article yok
    }
    
    return render(request, 'articles/article_form.html', context)


@login_required
def article_update(request, slug):
    """Makale güncelle"""
    article = get_object_or_404(Article, slug=slug)
    
    if not _user_can_edit_article(request.user, article):
        messages.error(request, 'Bu makaleyi düzenleme yetkiniz bulunmamaktadır.')
        return redirect('articles:article_detail', slug=article.slug)
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, instance=article, user=request.user)
        if form.is_valid():
            article = form.save()
            messages.success(request, 'Makale başarıyla güncellendi!')
            return redirect('articles:article_detail', slug=article.slug)
    else:
        form = ArticleForm(instance=article, user=request.user)
    
    context = {
        'form': form,
        'article': article,
        'title': 'Makale Düzenle',
        'is_admin': _user_has_adminmakale_tag(request.user),
    }
    
    return render(request, 'articles/article_form.html', context)


@login_required
def article_delete(request, slug):
    """Makale sil"""
    article = get_object_or_404(Article, slug=slug)
    
    if not _user_can_edit_article(request.user, article):
        messages.error(request, 'Bu makaleyi silme yetkiniz bulunmamaktadır.')
        return redirect('articles:article_detail', slug=article.slug)
    
    if request.method == 'POST':
        article_title = article.title
        article.delete()
        messages.success(request, f'"{article_title}" makalesi başarıyla silindi!')
        return redirect('articles:article_list')
    
    context = {
        'article': article,
    }
    
    return render(request, 'articles/article_delete.html', context)


@login_required
def article_comment_create(request, slug):
    """Makale yorumu oluştur"""
    if not (_user_has_makale_tag(request.user) or _user_has_adminmakale_tag(request.user)):
        return JsonResponse({'error': 'Yetkiniz bulunmamaktadır.'}, status=403)
    
    article = get_object_or_404(Article, slug=slug)
    
    if request.method == 'POST':
        form = ArticleCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.article = article
            comment.author = request.user
            
            # Adminmakale tag'ı olanların yorumları otomatik onaylanır
            if _user_has_adminmakale_tag(request.user):
                comment.is_approved = True
            
            comment.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Yorumunuz başarıyla eklendi!' + (' (Onay bekliyor)' if not comment.is_approved else ''),
                    'comment_id': comment.id,
                    'is_approved': comment.is_approved
                })
            else:
                messages.success(request, 'Yorumunuz başarıyla eklendi!' + (' (Onay bekliyor)' if not comment.is_approved else ''))
                return redirect('articles:article_detail', slug=article.slug)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Yorum formunda hata var.'}, status=400)
            else:
                messages.error(request, 'Yorum formunda hata var.')
                return redirect('articles:article_detail', slug=article.slug)
    
    return JsonResponse({'error': 'Geçersiz istek.'}, status=400)


def article_category_list(request, category):
    """Kategoriye göre makale listesi"""
    if not (_user_has_makale_tag(request.user) or _user_has_adminmakale_tag(request.user)):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    # Kategori seçeneklerini kontrol et
    valid_categories = [choice[0] for choice in Article.CATEGORY_CHOICES]
    if category not in valid_categories:
        messages.error(request, 'Geçersiz kategori.')
        return redirect('articles:article_list')
    
    articles = Article.objects.filter(category=category)
    
    # Kullanıcı adminmakale tag'ına sahip değilse sadece yayınlanmış makaleleri göster
    if not _user_has_adminmakale_tag(request.user):
        articles = articles.filter(status='published')
    
    # Sayfalama
    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Kategori adını al
    category_name = dict(Article.CATEGORY_CHOICES)[category]
    
    context = {
        'page_obj': page_obj,
        'category': category,
        'category_name': category_name,
        'can_create': _user_has_adminmakale_tag(request.user),
        'can_manage': _user_has_adminmakale_tag(request.user),
    }
    
    return render(request, 'articles/article_category_list.html', context)


def article_author_list(request, username):
    """Yazara göre makale listesi"""
    if not (_user_has_makale_tag(request.user) or _user_has_adminmakale_tag(request.user)):
        messages.error(request, 'Bu sayfaya erişim yetkiniz bulunmamaktadır.')
        return redirect('dashboard:index')
    
    author = get_object_or_404(User, username=username)
    articles = Article.objects.filter(author=author)
    
    # Kullanıcı adminmakale tag'ına sahip değilse sadece yayınlanmış makaleleri göster
    if not _user_has_adminmakale_tag(request.user):
        articles = articles.filter(status='published')
    
    # Sayfalama
    paginator = Paginator(articles, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'author': author,
        'can_create': _user_has_adminmakale_tag(request.user),
        'can_manage': _user_has_adminmakale_tag(request.user),
    }
    
    return render(request, 'articles/article_author_list.html', context)