import os
import json
import requests
import logging
import hmac
import hashlib
from urllib.parse import urlencode
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseBadRequest, JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.utils.crypto import get_random_string
from django.db.models import Q

from .models import GitHubProfile, GitHubRepository, GitHubIssue, SyncLog
from .forms import GitHubAuthForm, GitHubRepositoryForm, GitHubIssueImportForm, GitHubOAuthSettingsForm
from .github_api import GitHubAPI
from .sync import sync_project_with_github, sync_task_with_github_issue, import_github_issues
from .tasks import sync_repository_with_github, update_issue_from_github

from projects.models import Project
from tasks.models import Task
from communications.models import MessageGroup, Message, MessageGroupMember

logger = logging.getLogger(__name__)

@login_required
def github_oauth_settings(request):
    """
    Kullanıcının kişisel GitHub OAuth ayarlarını yapılandırmasını sağlar.
    """
    # Kullanıcının GitHub profilini al veya oluştur
    github_profile, created = GitHubProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'github_username': '',
            'access_token': '',
            'use_personal_oauth': False
        }
    )
    
    # Sistem genelinde OAuth bilgilerinin yapılandırılıp yapılandırılmadığını kontrol et
    system_oauth_ready = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
    
    # Site URL'sini context'e ekle
    site_url = request.build_absolute_uri('/').rstrip('/')
    
    if request.method == 'POST':
        form = GitHubOAuthSettingsForm(request.POST, instance=github_profile)
        if form.is_valid():
            # Formu kaydet
            github_profile = form.save(commit=False)
            
            # Eğer kişisel OAuth kullanılmıyorsa, OAuth bilgilerini temizle
            if not github_profile.use_personal_oauth:
                github_profile.client_id = None
                github_profile.client_secret = None
                github_profile.redirect_uri = None
            
            github_profile.save()
            
            # Eğer kişisel OAuth kullanılmaya başlandıysa ve bir token varsa, token artık geçersiz olabilir
            if github_profile.use_personal_oauth and github_profile.access_token:
                messages.warning(request, _("OAuth ayarlarınızı değiştirdiğiniz için GitHub'a yeniden bağlanmanız gerekiyor."))
                return redirect('github_integration:github_connect')
            else:
                messages.success(request, _("GitHub OAuth ayarlarınız başarıyla kaydedildi."))
                
                # Kişisel OAuth kullanılıyorsa ve bilgiler tam ise bağlantı sayfasına yönlendir
                if github_profile.use_personal_oauth and github_profile.client_id and github_profile.client_secret:
                    messages.info(request, _("Kişisel OAuth bilgileriniz kaydedildi. Şimdi GitHub hesabınızı bağlayabilirsiniz."))
                    return redirect('github_integration:github_connect')
                
                return redirect('github_integration:github_profile' if github_profile.access_token else 'github_integration:github_connect')
    else:
        form = GitHubOAuthSettingsForm(instance=github_profile)
    
    # Sistem OAuth bilgileri yoksa, kullanıcıya kişisel OAuth yapılandırmasını daha belirgin bir şekilde öner
    show_oauth_instructions = not system_oauth_ready and (created or not github_profile.use_personal_oauth or not (github_profile.client_id and github_profile.client_secret))
    
    return render(request, 'github_integration/github_oauth_settings.html', {
        'form': form,
        'site_url': site_url,
        'system_oauth_ready': system_oauth_ready,
        'show_oauth_instructions': show_oauth_instructions,
        'callback_url': f"{site_url}/github/callback/",
    })

@login_required
def github_connect(request):
    """
    Kullanıcının GitHub hesabını bağlamasını sağlar.
    """
    # Sistem genelinde OAuth bilgilerinin yapılandırılıp yapılandırılmadığını kontrol et
    system_oauth_ready = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
    
    # Kullanıcının GitHub profil bilgilerini al veya oluştur
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
        
        # Eğer token geçerliyse profil sayfasına yönlendir
        if github_profile.access_token and github_profile.is_token_valid:
            # Token geçerli ama kullanıcı yine de bağlanmaya çalışıyor
            messages.info(request, _("GitHub hesabınız zaten bağlı."))
            return redirect('github_integration:github_profile')
            
    except GitHubProfile.DoesNotExist:
        github_profile = GitHubProfile(
            user=request.user,
            github_username='',
            access_token='',
            use_personal_oauth=not system_oauth_ready  # Sistem OAuth yoksa kişisel kullanımı öner
        )
        github_profile.save()
    
    # Kullanıcının kişisel OAuth bilgilerini kontrol et
    has_personal_oauth = github_profile.use_personal_oauth and github_profile.client_id and github_profile.client_secret
    
    # Herhangi bir OAuth yapılandırması yoksa, kullanıcıyı OAuth ayarlarına yönlendir
    if not system_oauth_ready and not has_personal_oauth:
        messages.warning(request, _(
            "Sistem genelinde GitHub OAuth bilgileri yapılandırılmamış. "
            "Her kullanıcının kendi GitHub uygulamasını oluşturup kişisel OAuth bilgilerini girmesi gerekiyor. "
            "Lütfen önce OAuth ayarlarınızı yapılandırın."
        ))
        return redirect('github_integration:github_oauth_settings')
    
    if request.method == 'POST':
        form = GitHubAuthForm(request.POST)
        if form.is_valid():
            # Kullanıcı kişisel OAuth bilgilerini mi kullanacak?
            use_personal_oauth = github_profile.use_personal_oauth
            
            if use_personal_oauth:
                # Kişisel OAuth bilgilerini kontrol et
                if not (github_profile.client_id and github_profile.client_secret):
                    messages.error(request, _("GitHub OAuth bilgileriniz eksik. Lütfen önce OAuth ayarlarınızı yapılandırın."))
                    return redirect('github_integration:github_oauth_settings')
                
                client_id = github_profile.client_id
                redirect_uri = github_profile.redirect_uri or settings.GITHUB_REDIRECT_URI
            else:
                # Sistem genelinde OAuth bilgileri yapılandırılmamışsa ve kişisel OAuth kullanılmıyorsa
                if not system_oauth_ready:
                    messages.error(request, _("Sistem genelinde GitHub OAuth bilgileri yapılandırılmamış. Lütfen kişisel OAuth bilgilerinizi girin."))
                    return redirect('github_integration:github_oauth_settings')
                
                client_id = settings.GITHUB_CLIENT_ID
                redirect_uri = settings.GITHUB_REDIRECT_URI
            
            # State parametresi oluştur (CSRF koruması için)
            state = get_random_string(length=32)
            request.session['github_oauth_state'] = state
            
            # Kişisel OAuth kullanılıp kullanılmayacağını oturumda sakla
            request.session['github_personal_oauth'] = use_personal_oauth
            
            # GitHub OAuth URL'ini oluştur
            scope = 'repo user'
            oauth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
            
            # Kullanıcıyı GitHub'a yönlendir
            return redirect(oauth_url)
    else:
        form = GitHubAuthForm()
    
    return render(request, 'github_integration/github_connect.html', {
        'form': form,
        'system_oauth_ready': system_oauth_ready,
        'has_personal_oauth': has_personal_oauth,
    })

@login_required
def github_callback(request):
    """
    GitHub OAuth2 callback işleyici.
    """
    # Demo mod kontrolü - gerçek sistemde artık kullanılmıyor
    if getattr(settings, 'GITHUB_DEMO_MODE', False):
        messages.success(request, _("Demo mod: GitHub hesabınız başarıyla bağlandı. (Not: Bu gerçek bir GitHub bağlantısı değil)"))
        return redirect('github_integration:github_profile')
    
    # Hata kontrolü
    error = request.GET.get('error')
    if error:
        error_description = request.GET.get('error_description', 'Bilinmeyen hata')
        # Kullanıcı reddettiğinde özel mesaj göster
        if error == 'access_denied':
            messages.warning(request, _("GitHub hesabınızı bağlamayı reddettiniz. GitHub özellikleri kullanılamayacak."))
        else:
            messages.error(request, _("GitHub yetkilendirme sırasında hata oluştu: %(error)s - %(description)s") % {
                'error': error,
                'description': error_description
            })
        
        logger.warning(f"GitHub OAuth hatası: {error} - {error_description} (Kullanıcı: {request.user.id})")
        return redirect('dashboard:index')

    # Code ve state kontrolü
    code = request.GET.get('code')
    state = request.GET.get('state')
    
    if not code:
        messages.error(request, _("GitHub yanıtında yetkilendirme kodu eksik."))
        logger.error(f"GitHub yetkilendirme kodu alınamadı (Kullanıcı: {request.user.id})")
        return redirect('dashboard:index')
    
    # State doğrulama (CSRF koruması)
    session_state = request.session.get('github_oauth_state')
    if not session_state or state != session_state:
        messages.error(request, _("Güvenlik doğrulaması başarısız oldu. Lütfen tekrar deneyin."))
        logger.error(f"GitHub OAuth state doğrulaması başarısız (Kullanıcı: {request.user.id})")
        return redirect('github_integration:github_connect')
    
    # Kullanıcı kendi OAuth bilgilerini mi kullanıyor?
    use_personal_oauth = request.session.get('github_personal_oauth', False)
    client_id = None
    client_secret = None
    redirect_uri = None
    
    # Kullanıcının GitHub profilini al veya oluştur
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        # Yeni profil oluştur
        github_profile = GitHubProfile(
            user=request.user,
            github_username='',  # API'den alınacak
            access_token='',
            use_personal_oauth=use_personal_oauth
        )
    
    if use_personal_oauth:
        # Kullanıcının kişisel OAuth bilgilerini kontrol et
        if github_profile.client_id and github_profile.client_secret:
            client_id = github_profile.client_id
            client_secret = github_profile.client_secret
            redirect_uri = github_profile.redirect_uri or settings.GITHUB_REDIRECT_URI
        else:
            messages.error(request, _("Kişisel OAuth bilgileriniz eksik. Lütfen ayarlarınızı kontrol edin."))
            return redirect('github_integration:github_oauth_settings')
    else:
        # Sistem genelindeki OAuth bilgilerini kullan
        client_id = settings.GITHUB_CLIENT_ID
        client_secret = settings.GITHUB_CLIENT_SECRET
        redirect_uri = settings.GITHUB_REDIRECT_URI
        
        # Eğer sistem genelinde OAuth bilgileri yapılandırılmamışsa
        if not client_id or not client_secret:
            messages.error(request, _("Sistem genelindeki GitHub OAuth bilgileri eksik. Lütfen kişisel OAuth bilgilerinizi girmeyi deneyin."))
            return redirect('github_integration:github_oauth_settings')
    
    # GitHub'dan token al
    try:
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
        }
        
        logger.info(f"GitHub token isteği gönderiliyor (Kullanıcı: {request.user.id})")
        
        response = requests.post(
            'https://github.com/login/oauth/access_token',
            data=token_data,
            headers={'Accept': 'application/json'},
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"GitHub token yanıtı başarısız: HTTP {response.status_code} - {response.text} (Kullanıcı: {request.user.id})")
            messages.error(request, _("GitHub'dan token alınırken bir hata oluştu. HTTP kodu: %(status_code)s") % {'status_code': response.status_code})
            return redirect('dashboard:index')
        
        token_info = response.json()
        
        if 'error' in token_info:
            error_message = token_info.get('error_description', token_info['error'])
            messages.error(request, _("GitHub token alınırken hata oluştu: %(error)s") % {'error': error_message})
            logger.error(f"GitHub token hatası: {token_info.get('error')} - {error_message} (Kullanıcı: {request.user.id})")
            return redirect('dashboard:index')
        
        if 'access_token' not in token_info:
            messages.error(request, _("GitHub yanıtında access_token bulunamadı. Lütfen daha sonra tekrar deneyin."))
            logger.error(f"GitHub yanıtında access_token yok: {token_info} (Kullanıcı: {request.user.id})")
            return redirect('dashboard:index')
            
        access_token = token_info.get('access_token')
        refresh_token = token_info.get('refresh_token', '')
        
        # Token türünü kontrol et (OAuth2 için 'bearer' olmalı)
        token_type = token_info.get('token_type', '').lower()
        if token_type != 'bearer':
            logger.warning(f"GitHub token türü beklenmeyen değer: {token_type} (Kullanıcı: {request.user.id})")
        
        # Token süresini hesapla (varsayılan 8 saat)
        expires_in = token_info.get('expires_in', 28800)  # GitHub default: 8 saat
        token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        logger.info(f"GitHub token başarıyla alındı (Kullanıcı: {request.user.id}, Token geçerlilik: {expires_in} saniye)")
        
    except requests.RequestException as e:
        messages.error(request, _("GitHub ile iletişim kurulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin."))
        logger.error(f"GitHub token isteği hatası: {str(e)} (Kullanıcı: {request.user.id})")
        return redirect('dashboard:index')
    except Exception as e:
        messages.error(request, _("GitHub bağlantısı sırasında beklenmeyen bir hata oluştu."))
        logger.error(f"GitHub callback beklenmeyen hata: {str(e)} (Kullanıcı: {request.user.id})")
        return redirect('dashboard:index')
    
    # GitHub API istemcisi oluştur
    api = GitHubAPI(access_token)
    
    try:
        # Kullanıcı bilgilerini al
        user_info = api.get_user_info()
        
        if not user_info:
            messages.error(request, _("GitHub'dan kullanıcı bilgileri alınamadı. API yanıt vermedi."))
            logger.error(f"GitHub API kullanıcı bilgileri boş yanıt (Kullanıcı: {request.user.id})")
            return redirect('dashboard:index')
            
        github_username = user_info.get('login')
        
        if not github_username:
            messages.error(request, _("GitHub kullanıcı bilgileri alınamadı."))
            logger.error(f"GitHub API yanıtında 'login' değeri bulunamadı: {user_info} (Kullanıcı: {request.user.id})")
            return redirect('dashboard:index')
        
        logger.info(f"GitHub kullanıcı bilgileri başarıyla alındı: {github_username} (Kullanıcı: {request.user.id})")
        
        # GitHub profil bilgilerini güncelle
        github_profile.github_username = github_username
        github_profile.access_token = access_token
        github_profile.refresh_token = refresh_token
        github_profile.token_expires_at = token_expires_at
        github_profile.last_sync = timezone.now()
        
        # Eğer kişisel OAuth kullanılıyorsa bilgileri güncelle
        if use_personal_oauth:
            github_profile.use_personal_oauth = True
            github_profile.client_id = client_id
            github_profile.client_secret = client_secret
            github_profile.redirect_uri = redirect_uri
            
        # Profil bilgilerini kaydet
        github_profile.save()
        
        # Oturum state'ini temizle
        for key in ['github_oauth_state', 'github_personal_oauth']:
            if key in request.session:
                del request.session[key]
        
        # Başarılı mesajı göster
        messages.success(request, _("GitHub hesabınız başarıyla bağlandı."))
        logger.info(f"GitHub profili güncellendi: {github_username} (Kullanıcı: {request.user.id})")
        
        return redirect('github_integration:github_profile')
        
    except Exception as e:
        messages.error(request, _("GitHub kullanıcı bilgileri alınırken bir hata oluştu: %s") % str(e))
        logger.error(f"GitHub API hatası: {str(e)} (Kullanıcı: {request.user.id})")
        return redirect('dashboard:index')

@login_required
def github_profile(request):
    """
    Kullanıcının GitHub profil sayfasını görüntüler.
    """
    # Sistem genelinde OAuth bilgilerinin yapılandırılıp yapılandırılmadığını kontrol et
    system_oauth_ready = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
    
    # Kullanıcının GitHub profili var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
        
        # Token yoksa veya süresi dolmuşsa, kullanıcıyı bilgilendir ve yönlendir
        if not github_profile.access_token:
            messages.warning(request, _("GitHub hesabınız henüz bağlanmamış. Lütfen GitHub hesabınızı bağlayın."))
        
            # Sistem genelinde OAuth yapılandırılmışsa direkt bağlantı sayfasına yönlendir
            if system_oauth_ready:
                return redirect('github_integration:github_connect')
            else:
                # Kişisel OAuth gerekiyorsa önce ayarlar sayfasına yönlendir
                messages.info(request, _(
                    "Sistem genelinde GitHub OAuth yapılandırılmamış olduğundan, kendi GitHub OAuth uygulamanızı "
                    "oluşturmanız ve bilgilerinizi girmeniz gerekiyor."
                ))
                return redirect('github_integration:github_oauth_settings')
                
        # POST isteği kontrol et - Repository'yi projeye bağla
        if request.method == 'POST' and 'repository_name' in request.POST and 'repository_owner' in request.POST and 'project_id' in request.POST:
            repository_name = request.POST.get('repository_name')
            repository_owner = request.POST.get('repository_owner')
            project_id = request.POST.get('project_id')
            
            try:
                # Projeyi kontrol et
                project = Project.objects.get(id=project_id)
                
                # Kullanıcının projeye erişim izni var mı kontrol et
                if not request.user.is_superuser and request.user != project.manager:
                    messages.error(request, _("Bu projeye GitHub repository'si bağlama izniniz yok."))
                    return redirect('github_integration:github_profile')
                
                # Projenin zaten bir GitHub repository'si var mı kontrol et
                if GitHubRepository.objects.filter(project=project).exists():
                    messages.warning(request, _("Bu projeye zaten bir GitHub repository'si bağlı."))
                    return redirect('github_integration:github_profile')
                
                # GitHub API istemcisini oluştur
                api = GitHubAPI(github_profile=github_profile)
                
                # Repository bilgilerini al
                repo_data = api.get_repository(repository_owner, repository_name)
                
                if not repo_data:
                    messages.error(request, _("Repository bilgileri alınamadı."))
                    return redirect('github_integration:github_profile')
                
                # Repository oluştur
                repository = GitHubRepository.objects.create(
                    project=project,
                    repository_owner=repository_owner,
                    repository_name=repository_name,
                    repository_url=repo_data.get('html_url', ''),
                    is_private=repo_data.get('private', False),
                    default_branch=repo_data.get('default_branch', 'main')
                )
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='sync_repo',
                    status='success',
                    message=_("Repository başarıyla bağlandı: {}").format(repository)
                )
                
                messages.success(request, _("Repository başarıyla projeye bağlandı: {}").format(repository))
                return redirect('projects:project_detail', project_id=project_id)
                
            except Project.DoesNotExist:
                messages.error(request, _("Belirtilen proje bulunamadı."))
            except Exception as e:
                logger.exception(f"Error connecting repository: {str(e)}")
                messages.error(request, _("Repository bağlanırken bir hata oluştu: {}").format(str(e)))
            
            return redirect('github_integration:github_profile')
        
        # GitHub API istemcisini oluştur
        api = GitHubAPI(github_profile=github_profile)
        
        # Demo mod kontrolü (artık sistem genelinde false olmalı)
        demo_mode = getattr(settings, 'GITHUB_DEMO_MODE', False)
        
        try:
            if demo_mode:
                # Demo mod - sahte veriler göster
                user_info = api.get_user_info()
                repositories = api.get_repositories()
                
                # Demo bilgisi mesajı
                messages.info(request, _("Demo modunda çalışıyorsunuz. Gerçek GitHub hesap bilgileri gösterilmiyor."))
            else:
                # Kullanıcı bilgilerini al
                user_info = api.get_user_info()
                
                # Eğer kullanıcı bilgileri alınamazsa (401 hatası olabilir)
                if not user_info:
                    # Token'ın artık geçersiz olduğunu işaretle
                    github_profile.token_expires_at = timezone.now() - timedelta(seconds=1)
                    github_profile.save()
                    
                    messages.warning(request, _("GitHub erişim tokenınız geçersiz olmuş veya yetkisi reddedilmiş. Lütfen yeniden bağlantı kurun."))
                    
                    # Sistem genelinde OAuth yapılandırılmamışsa, kişisel OAuth öner
                    if not system_oauth_ready or github_profile.use_personal_oauth:
                        messages.info(request, _("GitHub OAuth ayarlarınızı kontrol edin ve yeniden bağlanmayı deneyin."))
                        return redirect('github_integration:github_oauth_settings')
                    
                    return redirect('github_integration:github_connect')
                
                # Repository'leri al
                repositories = api.get_repositories(visibility='all')
                
                if not isinstance(repositories, list):
                    repositories = []
                
                # Son 5 pull request'i getir
                recent_prs = []
                for repo in repositories[:5]:  # Sadece ilk 5 repo için kontrol et
                    repo_prs = api.get_pull_requests(
                        owner=repo['owner']['login'],
                        repo=repo['name'],
                        state='all',
                        max_prs=3
                    )
                    if repo_prs:
                        for pr in repo_prs:
                            pr['repository'] = repo
                        recent_prs.extend(repo_prs)
                
                # Son 5 PR'ı göster
                recent_prs = sorted(recent_prs, key=lambda x: x.get('updated_at', ''), reverse=True)[:5]
            
            # Bağlı repository'leri al
            linked_repos = GitHubRepository.objects.filter(
                repository_owner=github_profile.github_username
            ).select_related('project')
            
            return render(request, 'github_integration/github_profile.html', {
                'github_profile': github_profile,
                'user_info': user_info,
                'repositories': repositories,
                'linked_repos': linked_repos,
                'recent_prs': recent_prs if not demo_mode else [],
                'demo_mode': demo_mode
            })
        
        except Exception as e:
            # Hata durumunda detaylı hata mesajı göster
            messages.error(request, _("GitHub profil bilgileri alınırken bir hata oluştu: %s") % str(e))
            logger.error(f"GitHub profil hatası: {str(e)} (Kullanıcı: {request.user.id})")
            
            # Token hatası ise (401 Unauthorized), yeniden bağlanmayı öner
            if '401' in str(e):
                # Token'ın artık geçersiz olduğunu işaretle
                github_profile.token_expires_at = timezone.now() - timedelta(seconds=1)
                github_profile.save()
                
                messages.warning(request, _("GitHub kimlik doğrulama hatası. Lütfen tekrar bağlanmayı deneyin."))
                
                # Sistem genelinde OAuth yapılandırılmamışsa, kişisel OAuth öner
                if not system_oauth_ready or github_profile.use_personal_oauth:
                    return redirect('github_integration:github_oauth_settings')
                
                return redirect('github_integration:github_connect')
                
            return redirect('dashboard:index')
            
    except GitHubProfile.DoesNotExist:
        # GitHub hesabı bağlı değil, kullanıcıyı bilgilendir ve yönlendir
        messages.warning(request, _("GitHub hesabınız henüz bağlanmamış. Lütfen GitHub hesabınızı bağlayın."))
        
        # Sistem genelinde OAuth yapılandırılmamışsa, kişisel OAuth ayarlarına yönlendir
        if not system_oauth_ready:
            messages.info(request, _(
                "Sistem genelinde GitHub OAuth yapılandırılmamış olduğundan, kendi GitHub OAuth uygulamanızı "
                "oluşturmanız ve bilgilerinizi girmeniz gerekiyor."
            ))
            return redirect('github_integration:github_oauth_settings')
        
        # Sistem OAuth bilgileri varsa direkt bağlantı sayfasına yönlendir
        return redirect('github_integration:github_connect')

@login_required
def github_disconnect(request):
    """
    Kullanıcının GitHub hesap bağlantısını kaldırır.
    """
    return render(request, 'github_integration/github_disconnect.html', {
        'title': _('GitHub Hesap Bağlantısını Kaldır')
    })

@login_required
def project_github_connect(request, project_id):
    """
    Bir projeyi GitHub repository'si ile ilişkilendirir.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if not request.user.is_superuser and request.user != project.manager:
        messages.error(request, _("Bu projeye GitHub repository'si bağlama izniniz yok."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        messages.warning(request, _("Önce GitHub hesabınızı bağlamanız gerekiyor."))
        return redirect('github_integration:github_connect')
    
    # Projenin zaten bir GitHub repository'si var mı kontrol et
    try:
        repository = GitHubRepository.objects.get(project=project)
        messages.info(request, _("Bu projeye zaten bir GitHub repository'si bağlı: {}").format(repository))
        return redirect('projects:project_detail', project_id=project_id)
    except GitHubRepository.DoesNotExist:
        pass
    
    # GitHub API istemcisini oluştur
    api = GitHubAPI(github_profile=github_profile)
    
    # GitHub'daki repository'leri al
    repositories = api.get_repositories()
    
    if repositories is None:
        messages.error(request, _("GitHub repository'leri alınamadı. Lütfen tekrar deneyin."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Form işleme
    if request.method == 'POST':
        form = GitHubRepositoryForm(request.POST, repositories=repositories)
        
        if form.is_valid():
            repository_choice = form.cleaned_data['repository_choice']
            
            if repository_choice == 'existing':
                # Mevcut bir repository'yi bağla
                repository_full_name = form.cleaned_data['existing_repository']
                if not repository_full_name:
                    messages.error(request, _("Lütfen bir repository seçin."))
                    return redirect('github_integration:project_github_connect', project_id=project_id)
                
                owner, repo_name = repository_full_name.split('/')
                
                # Repository bilgilerini al
                repo_data = api.get_repository(owner, repo_name)
                
                if not repo_data:
                    messages.error(request, _("Repository bilgileri alınamadı."))
                    return redirect('github_integration:project_github_connect', project_id=project_id)
                
                # Repository oluştur
                repository = GitHubRepository.objects.create(
                    project=project,
                    repository_owner=owner,
                    repository_name=repo_name,
                    repository_url=repo_data.get('html_url', ''),
                    is_private=repo_data.get('private', False),
                    default_branch=repo_data.get('default_branch', 'main')
                )
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='sync_repo',
                    status='success',
                    message=_("Repository başarıyla bağlandı: {}").format(repository)
                )
                
                messages.success(request, _("Proje, GitHub repository'si ile başarıyla ilişkilendirildi: {}").format(repository))
                
            elif repository_choice == 'new':
                # Yeni bir repository oluştur
                repo_name = form.cleaned_data['repository_name']
                is_private = form.cleaned_data['is_private']
                
                if not repo_name:
                    messages.error(request, _("Repository adı gerekli."))
                    return redirect('github_integration:project_github_connect', project_id=project_id)
                
                # Açıklama olarak proje açıklamasını kullan
                description = project.description if project.description else f"{project.name} projesi için repository"
                
                # Repository oluştur
                try:
                    repo_data = api.create_repository(
                        name=repo_name,
                        description=description,
                        private=is_private
                    )
                    
                    if not repo_data:
                        messages.error(request, _("Repository oluşturulamadı."))
                        return redirect('github_integration:project_github_connect', project_id=project_id)
                    
                    # Repository oluştur
                    repository = GitHubRepository.objects.create(
                        project=project,
                        repository_owner=github_profile.github_username,
                        repository_name=repo_name,
                        repository_url=repo_data.get('html_url', ''),
                        is_private=repo_data.get('private', False),
                        default_branch=repo_data.get('default_branch', 'main')
                    )
                    
                    # Senkronizasyon kaydı oluştur
                    SyncLog.objects.create(
                        user=request.user,
                        repository=repository,
                        action='create_repo',
                        status='success',
                        message=_("Yeni repository oluşturuldu: {}").format(repository)
                    )
                    
                    messages.success(request, _("Yeni GitHub repository'si başarıyla oluşturuldu ve projeye bağlandı: {}").format(repository))
                    
                except Exception as e:
                    logger.exception(f"Error creating repository: {str(e)}")
                    messages.error(request, _("Repository oluşturulurken bir hata oluştu: {}").format(str(e)))
                    return redirect('github_integration:project_github_connect', project_id=project_id)
            
            # Proje detay sayfasına yönlendir
            return redirect('projects:project_detail', project_id=project_id)
    else:
        form = GitHubRepositoryForm(repositories=repositories)
    
    return render(request, 'github_integration/project_github_connect.html', {
        'project': project,
        'form': form,
        'title': _('GitHub Repository Bağla')
    })

@login_required
def project_github_sync(request, project_id):
    """
    Projeyi GitHub repository'si ile senkronize eder.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if not request.user.is_superuser and request.user != project.manager:
        messages.error(request, _("Bu projeyi GitHub ile senkronize etme izniniz yok."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        messages.warning(request, _("Önce GitHub hesabınızı bağlamanız gerekiyor."))
        return redirect('github_integration:github_connect')
    
    # Projenin GitHub repository'si var mı kontrol et
    try:
        repository = GitHubRepository.objects.get(project=project)
    except GitHubRepository.DoesNotExist:
        messages.error(request, _("Bu projeye bağlı bir GitHub repository'si bulunamadı."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Senkronizasyon işlemini gerçekleştir
    try:
        success, message = sync_project_with_github(project, github_profile)
        
        if success:
            # Senkronizasyon başarılı oldu
            messages.success(request, _("Proje GitHub repository'si ile başarıyla senkronize edildi."))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='sync_repo',
                status='success',
                message=message
            )
        else:
            # Senkronizasyon başarısız oldu
            messages.error(request, _("Senkronizasyon sırasında bir hata oluştu: {}").format(message))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='sync_repo',
                status='failed',
                message=message
            )
    except Exception as e:
        logger.exception(f"Error syncing project with GitHub: {str(e)}")
        messages.error(request, _("Senkronizasyon sırasında bir hata oluştu: {}").format(str(e)))
        
        # Senkronizasyon kaydı oluştur
        SyncLog.objects.create(
            user=request.user,
            repository=repository,
            action='sync_repo',
            status='failed',
            message=str(e)
        )
    
    return redirect('projects:project_detail', project_id=project_id)

@login_required
def project_github_issues_import(request, project_id):
    """
    GitHub repository'sindeki issue'ları görev olarak içe aktarır.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if not request.user.is_superuser and request.user != project.manager:
        messages.error(request, _("Bu projeye GitHub issue'larını içe aktarma izniniz yok."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        messages.warning(request, _("Önce GitHub hesabınızı bağlamanız gerekiyor."))
        return redirect('github_integration:github_connect')
    
    # Projenin GitHub repository'si var mı kontrol et
    try:
        repository = GitHubRepository.objects.get(project=project)
    except GitHubRepository.DoesNotExist:
        messages.error(request, _("Bu projeye bağlı bir GitHub repository'si bulunamadı."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Form işleme
    if request.method == 'POST':
        form = GitHubIssueImportForm(request.POST)
        
        if form.is_valid():
            import_all = form.cleaned_data['import_all']
            import_closed = form.cleaned_data['import_closed']
            issue_numbers_str = form.cleaned_data['issue_numbers']
            
            # Issue numaralarını parse et
            issue_numbers = []
            if issue_numbers_str:
                try:
                    issue_numbers = [int(num.strip()) for num in issue_numbers_str.split(',') if num.strip().isdigit()]
                except Exception as e:
                    logger.exception(f"Error parsing issue numbers: {str(e)}")
                    messages.error(request, _("Issue numaraları işlenirken bir hata oluştu. Lütfen geçerli sayılar girdiğinizden emin olun."))
                    return redirect('github_integration:project_github_issues_import', project_id=project_id)
            
            # İçe aktarma parametrelerini oluştur
            import_params = {
                'import_all': import_all,
                'import_closed': import_closed,
                'issue_numbers': issue_numbers,
            }
            
            # İçe aktarma işlemini gerçekleştir
            try:
                imported_issues, skipped_issues, errors = import_github_issues(repository, github_profile, import_params)
                
                if errors:
                    # Hatalar oluştu
                    messages.error(request, _("İçe aktarma sırasında bazı hatalar oluştu: {}").format(errors))
                    
                    # Senkronizasyon kaydı oluştur
                    SyncLog.objects.create(
                        user=request.user,
                        repository=repository,
                        action='import_issues',
                        status='failed',
                        message=f"Hatalar: {errors}"
                    )
                
                if imported_issues:
                    # Başarılı içe aktarma
                    messages.success(request, _("{} adet issue başarıyla içe aktarıldı.").format(len(imported_issues)))
                    
                    # Senkronizasyon kaydı oluştur
                    SyncLog.objects.create(
                        user=request.user,
                        repository=repository,
                        action='import_issues',
                        status='success',
                        message=f"{len(imported_issues)} issue içe aktarıldı, {len(skipped_issues)} issue atlandı."
                    )
                else:
                    messages.info(request, _("İçe aktarılacak yeni issue bulunamadı."))
                
                # Proje detay sayfasına yönlendir
                return redirect('projects:project_detail', project_id=project_id)
                
            except Exception as e:
                logger.exception(f"Error importing GitHub issues: {str(e)}")
                messages.error(request, _("GitHub issue'ları içe aktarılırken bir hata oluştu: {}").format(str(e)))
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='import_issues',
                    status='failed',
                    message=str(e)
                )
    else:
        form = GitHubIssueImportForm()
    
    return render(request, 'github_integration/project_github_issues_import.html', {
        'project': project,
        'repository': repository,
        'form': form,
        'title': _('GitHub Issue\'larını İçe Aktar')
    })

@login_required
def task_github_sync(request, task_id):
    """
    Görevi GitHub issue ile senkronize eder.
    """
    task = get_object_or_404(Task, id=task_id)
    
    # Yetkilendirme kontrolü - Sadece admin ve proje yöneticisi GitHub issue oluşturabilir/senkronize edebilir
    if not request.user.is_superuser and request.user != task.project.manager and request.user.role != 'project_manager':
        messages.error(request, _("Bu görevi GitHub issue ile senkronize etme izniniz yok. Bu işlem yalnızca proje yöneticileri veya sistem yöneticileri tarafından yapılabilir."))
        return redirect('tasks:task_detail', task_id=task_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        messages.warning(request, _("Önce GitHub hesabınızı bağlamanız gerekiyor."))
        return redirect('github_integration:github_connect')
    
    # Projenin GitHub repository'si var mı kontrol et
    try:
        repository = GitHubRepository.objects.get(project=task.project)
    except GitHubRepository.DoesNotExist:
        messages.error(request, _("Bu göreve ait projeye bağlı bir GitHub repository'si bulunamadı."))
        return redirect('tasks:task_detail', task_id=task_id)
    
    # Senkronizasyon işlemini gerçekleştir
    try:
        success, message = sync_task_with_github_issue(task, github_profile, create_if_not_exists=True)
        
        if success:
            # Senkronizasyon başarılı oldu
            messages.success(request, _("Görev GitHub issue ile başarıyla senkronize edildi."))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='update_issue',
                status='success',
                message=message
            )
        else:
            # Senkronizasyon başarısız oldu
            messages.error(request, _("Senkronizasyon sırasında bir hata oluştu: {}").format(message))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='update_issue',
                status='failed',
                message=message
            )
    except Exception as e:
        logger.exception(f"Error syncing task with GitHub: {str(e)}")
        messages.error(request, _("Senkronizasyon sırasında bir hata oluştu: {}").format(str(e)))
        
        # Senkronizasyon kaydı oluştur
        SyncLog.objects.create(
            user=request.user,
            repository=repository,
            action='update_issue',
            status='failed',
            message=str(e)
        )
    
    return redirect('tasks:task_detail', task_id=task_id)

@login_required
def sync_logs(request):
    """
    GitHub senkronizasyon kayıtlarını gösterir.
    """
    # Giriş yapan kullanıcıya ait veya kullanıcının yönettiği projelere ait senkronizasyon kayıtları
    user_repositories = GitHubRepository.objects.filter(
        project__manager=request.user
    ).values_list('id', flat=True)
    
    # Filtrele
    action_filter = request.GET.get('action', '')
    status_filter = request.GET.get('status', '')
    
    logs_query = SyncLog.objects.select_related('repository', 'user')
    
    # Erişim kontrolü: Sadece kullanıcının kendi kayıtları, kullanıcının yönettiği projelere ait kayıtlar
    logs_query = logs_query.filter(
        models.Q(user=request.user) | models.Q(repository__id__in=user_repositories)
    )
    
    # Filtre uygula
    if action_filter:
        logs_query = logs_query.filter(action=action_filter)
    if status_filter:
        logs_query = logs_query.filter(status=status_filter)
    
    # Sırala
    logs = logs_query.order_by('-created_at')
    
    # Seçim listeleri oluştur
    action_choices = SyncLog.ACTION_CHOICES
    status_choices = SyncLog.STATUS_CHOICES
    
    return render(request, 'github_integration/sync_logs.html', {
        'logs': logs,
        'action_choices': action_choices,
        'status_choices': status_choices,
        'action_filter': action_filter,
        'status_filter': status_filter,
        'title': _('GitHub Senkronizasyon Kayıtları')
    })

@csrf_exempt
def github_webhook(request):
    """
    GitHub webhook'ları işler.
    Bu endpoint, GitHub'daki değişiklikleri gerçek zamanlı olarak almak için kullanılır.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Method not allowed')
    
    # GitHub imza doğrulaması (webhook güvenliği için)
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature and settings.GITHUB_WEBHOOK_SECRET:
        logger.warning("Webhook signature missing")
        return HttpResponseBadRequest('Signature missing')
    
    if settings.GITHUB_WEBHOOK_SECRET:
        # İmza doğrulaması
        payload = request.body
        digest = hmac.new(
            settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'),
            payload, 
            hashlib.sha256
        ).hexdigest()
        expected_signature = f"sha256={digest}"
        
        if not hmac.compare_digest(signature, expected_signature):
            logger.warning("Webhook signature verification failed")
            return HttpResponseBadRequest('Invalid signature')
    
    # Event türü
    event_type = request.headers.get('X-GitHub-Event')
    if not event_type:
        return HttpResponseBadRequest('Event type missing')
    
    # Webhook payload'ını parse et
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON payload')
    
    # Repository bilgisini al
    repository_data = payload.get('repository')
    if not repository_data:
        return HttpResponseBadRequest('Repository information missing')
    
    repository_owner = repository_data.get('owner', {}).get('login')
    repository_name = repository_data.get('name')
    
    if not repository_owner or not repository_name:
        return HttpResponseBadRequest('Repository owner or name missing')
    
    # Repository'yi veritabanında bul
    try:
        repository = GitHubRepository.objects.get(
            repository_owner=repository_owner,
            repository_name=repository_name
        )
    except GitHubRepository.DoesNotExist:
        # Bu repository sistemde kayıtlı değil, webhook'u yoksay
        logger.info(f"Received webhook for unregistered repository: {repository_owner}/{repository_name}")
        return HttpResponse('Repository not registered', status=200)
    
    # Event türüne göre işlemler
    if event_type == 'ping':
        # Webhook kurulumu testi
        logger.info(f"Received ping event from {repository_owner}/{repository_name}")
        return JsonResponse({'message': 'pong'})
    
    elif event_type == 'push':
        # Push event'i, kod repository'de bir değişiklik olduğunu gösterir
        # Repository son güncelleme tarihini güncelle
        repository.last_synced = timezone.now()
        repository.save()
        
        # Push yapılan branch'ı kontrol et
        ref = payload.get('ref')  # refs/heads/main gibi
        if ref and ref.startswith('refs/heads/') and ref[11:] == repository.default_branch:
            # Default branch'e yapılan commit, async senkronizasyon görevi başlat
            sync_repository_with_github.delay(repository.id)
            
            # Log kaydı oluştur
            SyncLog.objects.create(
                repository=repository,
                action='sync_repo',
                status='pending',
                message=f"Push event detected on {repository.default_branch}, scheduled sync task"
            )
        
        return JsonResponse({'status': 'push event processed'})
    
    elif event_type == 'issues':
        # Issue event'i, bir issue'da değişiklik olduğunu gösterir
        action = payload.get('action')
        issue_data = payload.get('issue')
        
        if not issue_data:
            return HttpResponseBadRequest('Issue information missing')
        
        issue_number = issue_data.get('number')
        if not issue_number:
            return HttpResponseBadRequest('Issue number missing')
        
        # Async görev başlat
        update_issue_from_github.delay(repository.id, issue_number, action)
        
        # Log kaydı oluştur
        SyncLog.objects.create(
            repository=repository,
            action='update_issue',
            status='pending',
            message=f"Issue #{issue_number} {action} event received, scheduled update task"
        )
        
        return JsonResponse({'status': 'issue event processed'})
    
    # Diğer event türleri şimdilik işlenmeyecek
    return JsonResponse({'status': 'event received but not processed'})

@login_required
def project_github_webhook(request, project_id):
    """
    Projeye GitHub webhook ekler veya günceller.
    """
    project = get_object_or_404(Project, id=project_id)
    
    # Yetkilendirme kontrolü
    if not request.user.is_superuser and request.user != project.manager:
        messages.error(request, _("Bu projeye GitHub webhook'u ekleme izniniz yok."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Projenin repository'si var mı kontrol et
    try:
        repository = GitHubRepository.objects.get(project=project)
    except GitHubRepository.DoesNotExist:
        messages.error(request, _("Bu projeye bağlı bir GitHub repository'si bulunamadı."))
        return redirect('projects:project_detail', project_id=project_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    try:
        github_profile = GitHubProfile.objects.get(user=request.user)
    except GitHubProfile.DoesNotExist:
        messages.warning(request, _("Önce GitHub hesabınızı bağlamanız gerekiyor."))
        return redirect('github_integration:github_connect')
    
    # GitHub API istemcisini oluştur
    api = GitHubAPI(github_profile=github_profile)
    
    # Repository'deki mevcut webhook'ları kontrol et
    webhooks = api.get_webhooks(repository.repository_owner, repository.repository_name)
    
    # Webhook URL'ini oluştur
    webhook_url = request.build_absolute_uri(reverse('github_integration:github_webhook'))
    
    # Bizim sistemimizin webhook'u var mı kontrol et
    our_webhook = None
    if webhooks:
        for hook in webhooks:
            if hook.get('config', {}).get('url') == webhook_url:
                our_webhook = hook
                break
    
    # Form işleme
    if request.method == 'POST':
        webhook_action = request.POST.get('webhook_action')
        
        if webhook_action == 'create':
            # Webhook oluştur
            try:
                api.create_webhook(
                    repository.repository_owner,
                    repository.repository_name,
                    webhook_url,
                    secret=settings.GITHUB_WEBHOOK_SECRET,
                    events=['push', 'pull_request', 'issues']
                )
                
                messages.success(request, _("GitHub webhook başarıyla oluşturuldu."))
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='sync_repo',
                    status='success',
                    message=_("GitHub webhook oluşturuldu")
                )
                
            except Exception as e:
                logger.exception(f"Error creating webhook: {str(e)}")
                messages.error(request, _("Webhook oluşturulurken bir hata oluştu: {}").format(str(e)))
                
            return redirect('github_integration:project_github_webhook', project_id=project_id)
            
        elif webhook_action == 'delete' and our_webhook:
            # Webhook sil
            try:
                api.delete_webhook(
                    repository.repository_owner,
                    repository.repository_name,
                    our_webhook.get('id')
                )
                
                messages.success(request, _("GitHub webhook başarıyla silindi."))
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='sync_repo',
                    status='success',
                    message=_("GitHub webhook silindi")
                )
                
            except Exception as e:
                logger.exception(f"Error deleting webhook: {str(e)}")
                messages.error(request, _("Webhook silinirken bir hata oluştu: {}").format(str(e)))
                
            return redirect('github_integration:project_github_webhook', project_id=project_id)
    
    # Sayfayı render et
    return render(request, 'github_integration/project_github_webhook.html', {
        'project': project,
        'repository': repository,
        'webhook': our_webhook,
        'webhook_url': webhook_url,
        'title': _('GitHub Webhook Ayarları')
    })

@login_required
def issue_comments(request, issue_id):
    """
    GitHub issue yorumlarını gösterir ve yanıtlama imkanı sunar.
    """
    # GitHubIssue objesini al
    try:
        github_issue = GitHubIssue.objects.get(id=issue_id)
    except GitHubIssue.DoesNotExist:
        messages.error(request, _('GitHub issue bulunamadı.'))
        return redirect('github_integration:sync_logs')
    
    # Erişim kontrolü ve yetki kontrolü
    can_view = False
    can_modify_github = False  # GitHub üzerinde değişiklik yapabilme yetkisi
    
    if github_issue.task and github_issue.task.project:
        project = github_issue.task.project
        
        # Admin ve proje yöneticisi her şeyi yapabilir
        if request.user.is_superuser or request.user == project.manager:
            can_view = True
            can_modify_github = True
        # Takım üyeleri, göreve atanan kişi ve oluşturan sadece görüntüleyebilir
        elif (project.team_members.filter(id=request.user.id).exists() or 
              github_issue.task.assignee == request.user or 
              github_issue.task.creator == request.user):
            can_view = True
        
        if not can_view:
            messages.error(request, _('Bu GitHub issue\'a erişim izniniz yok. Bu kaynağa erişmek için proje yöneticisi veya takım üyesi olmanız gerekmektedir.'))
            return redirect('dashboard:index')
    
    # Mesaj grubu
    message_group = None
    if github_issue.task:
        message_group = MessageGroup.objects.filter(related_task=github_issue.task).first()
        
        # Mesaj grubu yoksa oluştur
        if not message_group:
            group_name = f"GitHub Issue #{github_issue.issue_number}: {github_issue.issue_title}"
            message_group = MessageGroup.objects.create(
                name=group_name,
                type='task',
                related_task=github_issue.task
            )
            
            # Proje yöneticisini ve göreve atanan kişileri gruba ekle
            if github_issue.task.project and github_issue.task.project.manager:
                MessageGroupMember.objects.create(
                    group=message_group,
                    user=github_issue.task.project.manager,
                    role='admin'
                )
            
            if github_issue.task.assignee:
                MessageGroupMember.objects.create(
                    group=message_group,
                    user=github_issue.task.assignee,
                    role='member'
                )
            
            # Kullanıcıyı da ekle
            MessageGroupMember.objects.create(
                group=message_group,
                user=request.user,
                role='member'
            )
    
    # GitHub yorumlarını senkronize et - sadece yöneticiler ve proje yöneticileri
    if 'sync' in request.GET and can_modify_github:
        if not hasattr(request.user, 'github_profile'):
            messages.warning(request, _('GitHub hesabınızı bağlamadan yorumları senkronize edemezsiniz.'))
        else:
            try:
                from github_integration.sync import sync_issue_comments
                
                imported_comments, new_comments, updated_comments, errors = sync_issue_comments(
                    github_issue, 
                    request.user.github_profile
                )
                
                if errors:
                    messages.error(request, _('Yorum senkronizasyonu sırasında hatalar oluştu: {0}').format(", ".join(errors)))
                else:
                    messages.success(
                        request, 
                        _('Yorumlar başarıyla senkronize edildi. Toplam: {0}, Yeni: {1}, Güncellenen: {2}').format(
                            len(imported_comments), len(new_comments), len(updated_comments)
                        )
                    )
            except Exception as e:
                messages.error(request, _('Yorumları senkronize ederken bir hata oluştu: {0}').format(str(e)))
    elif 'sync' in request.GET and not can_modify_github:
        messages.warning(request, _('GitHub yorumlarını senkronize etme yetkiniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
    
    # İlgili yorumları getir
    issue_comments = github_issue.comments.all()
    
    # İlgili mesajları getir
    messages_list = []
    if message_group:
        messages_list = Message.objects.filter(group=message_group).order_by('created_at')
    
    # AJAX yenileme isteği mi kontrol et
    if request.GET.get('refresh') == 'true' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Sadece mesajları JSON olarak döndür
        messages_json = []
        for msg in messages_list:
            is_github_comment = "Bu mesaj GitHub'dan otomatik olarak alındı" in msg.content
            messages_json.append({
                'id': msg.id,
                'sender_name': msg.sender.username,
                'has_github_profile': hasattr(msg.sender, 'github_profile'),
                'is_self': msg.sender == request.user,
                'content': msg.content,
                'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M'),
                'is_from_github': is_github_comment
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_json,
            'timestamp': timezone.now().timestamp()
        })
    
    # Yeni mesaj formu - sadece yöneticiler ve proje yöneticileri
    if message_group and can_modify_github:
        if request.method == 'POST':
            content = request.POST.get('content', '').strip()
            
            if content:
                # Mesaj oluştur
                new_message = Message.objects.create(
                    group=message_group,
                    sender=request.user,
                    message_type='text',
                    content=content
                )
                
                # GitHub issue yorumu oluştur
                try:
                    from github_integration.sync import create_github_comment_from_message
                    success, comment, error = create_github_comment_from_message(new_message, github_issue)
                    
                    if success:
                        messages.success(request, _('Mesajınız gönderildi ve GitHub issue yorumu olarak eklendi.'))
                    else:
                        messages.warning(
                            request, 
                            _('Mesajınız gönderildi ancak GitHub yorumu olarak eklenemedi: {0}').format(error)
                        )
                except Exception as e:
                    messages.warning(
                        request, 
                        _('Mesajınız gönderildi ancak GitHub yorumu olarak eklenemedi: {0}').format(str(e))
                    )
                
                # AJAX isteği değilse sayfaya yönlendir
                if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return redirect('github_integration:issue_comments', issue_id=issue_id)
                
                # AJAX isteği ise JSON yanıt gönder
                return JsonResponse({
                    'success': True,
                    'message': str(_('Mesajınız gönderildi.'))
                })
    elif message_group and request.method == 'POST' and not can_modify_github:
        messages.warning(request, _('GitHub issue\'larına yorum yapma yetkiniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
        return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # Normal sayfa görünümü
    return render(request, 'github_integration/issue_comments.html', {
        'github_issue': github_issue,
        'message_group': message_group,
        'messages_list': messages_list,
        'issue_comments': issue_comments,
        'title': f"GitHub Issue #{github_issue.issue_number}: {github_issue.issue_title}",
        'can_modify_github': can_modify_github
    })

@login_required
def issue_sync_comments(request, issue_id):
    """
    GitHub issue yorumlarını senkronize eder.
    """
    # GitHubIssue objesini al
    try:
        github_issue = GitHubIssue.objects.get(id=issue_id)
    except GitHubIssue.DoesNotExist:
        messages.error(request, _('GitHub issue bulunamadı.'))
        return redirect('github_integration:sync_logs')
    
    # Erişim kontrolü ve yetki kontrolü
    can_view = False
    can_modify_github = False  # GitHub üzerinde değişiklik yapabilme yetkisi
    
    if github_issue.task and github_issue.task.project:
        project = github_issue.task.project
        
        # Admin ve proje yöneticisi her şeyi yapabilir
        if request.user.is_superuser or request.user == project.manager:
            can_view = True
            can_modify_github = True
        # Takım üyeleri, göreve atanan kişi ve oluşturan sadece görüntüleyebilir
        elif (project.team_members.filter(id=request.user.id).exists() or 
              github_issue.task.assignee == request.user or 
              github_issue.task.creator == request.user):
            can_view = True
        
        if not can_view:
            messages.error(request, _('Bu GitHub issue\'a erişim izniniz yok. Bu kaynağa erişmek için proje yöneticisi veya takım üyesi olmanız gerekmektedir.'))
            return redirect('dashboard:index')
        
        # Yetkisi yoksa engelle
        if not can_modify_github:
            messages.warning(request, _('GitHub yorumlarını senkronize etme yetkiniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
            if github_issue.task:
                return redirect('tasks:task_detail', task_id=github_issue.task.id)
            return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    if not hasattr(request.user, 'github_profile'):
        messages.warning(request, _('GitHub hesabınızı bağlamadan yorumları senkronize edemezsiniz.'))
    else:
        try:
            from github_integration.sync import sync_issue_comments
            
            imported_comments, new_comments, updated_comments, errors = sync_issue_comments(
                github_issue, 
                request.user.github_profile
            )
            
            if errors:
                messages.error(request, _('Yorum senkronizasyonu sırasında hatalar oluştu: {0}').format(", ".join(errors)))
            else:
                messages.success(
                    request, 
                    _('Yorumlar başarıyla senkronize edildi. Toplam: {0}, Yeni: {1}, Güncellenen: {2}').format(
                        len(imported_comments), len(new_comments), len(updated_comments)
                    )
                )
        except Exception as e:
            messages.error(request, _('Yorumları senkronize ederken bir hata oluştu: {0}').format(str(e)))
    
    # GitHub issue sayfa yerine görev sayfasına yönlendir
    if github_issue.task:
        return redirect('tasks:task_detail', task_id=github_issue.task.id)
    
    return redirect('github_integration:issue_comments', issue_id=issue_id)

@login_required
def issue_update(request, issue_id):
    """
    GitHub issue güncelleme işlemi.
    """
    # GitHubIssue objesini al
    try:
        github_issue = GitHubIssue.objects.get(id=issue_id)
    except GitHubIssue.DoesNotExist:
        messages.error(request, _('GitHub issue bulunamadı.'))
        return redirect('github_integration:sync_logs')
    
    # Erişim kontrolü ve yetki kontrolü
    can_modify_github = False
    
    if github_issue.task and github_issue.task.project:
        project = github_issue.task.project
        
        # Admin ve proje yöneticisi her şeyi yapabilir
        if request.user.is_superuser or request.user == project.manager:
            can_modify_github = True
        
        if not can_modify_github:
            messages.error(request, _('Bu GitHub issue\'ı güncelleme izniniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
            return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # GET isteği - form göster
    if request.method == 'GET':
        context = {
            'github_issue': github_issue,
            'title': f'GitHub Issue Güncelle: #{github_issue.issue_number}',
        }
        return render(request, 'github_integration/issue_update_form.html', context)
    
    # POST isteği - issue güncelle
    elif request.method == 'POST':
        title = request.POST.get('title')
        body = request.POST.get('body')
        
        if not title:
            messages.error(request, _('Issue başlığı gerekli.'))
            return redirect('github_integration:issue_update', issue_id=issue_id)
        
        # Kullanıcının GitHub hesabı var mı kontrol et
        if not hasattr(request.user, 'github_profile'):
            messages.warning(request, _('GitHub hesabınızı bağlamadan issue güncelleyemezsiniz.'))
            return redirect('github_integration:github_connect')
        
        # GitHub API ile issue güncelle
        try:
            github_api = GitHubAPI(github_profile=request.user.github_profile)
            repository = github_issue.repository
            
            result = github_api.update_issue(
                repository.repository_owner,
                repository.repository_name,
                github_issue.issue_number,
                title=title,
                body=body
            )
            
            if result:
                # Issue bilgilerini veritabanında güncelle
                github_issue.issue_title = title
                github_issue.issue_body = body
                github_issue.github_updated_at = timezone.now()
                github_issue.save()
                
                # Senkronizasyon kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='update_issue',
                    status='success',
                    message=f'Issue #{github_issue.issue_number} başarıyla güncellendi.'
                )
                
                messages.success(request, _('GitHub issue başarıyla güncellendi.'))
            else:
                messages.error(request, _('GitHub issue güncellenirken bir hata oluştu.'))
                
                # Hata kaydı oluştur
                SyncLog.objects.create(
                    user=request.user,
                    repository=repository,
                    action='update_issue',
                    status='failed',
                    message=f'Issue #{github_issue.issue_number} güncellenirken hata oluştu.'
                )
        except Exception as e:
            messages.error(request, _('GitHub issue güncellenirken bir hata oluştu: {0}').format(str(e)))
            
            # Hata kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=github_issue.repository,
                action='update_issue',
                status='failed',
                message=f'Issue #{github_issue.issue_number} güncellenirken hata oluştu: {str(e)}'
            )
        
        return redirect('github_integration:issue_comments', issue_id=issue_id)

@login_required
def issue_close(request, issue_id):
    """
    GitHub issue kapatma işlemi.
    """
    # GitHubIssue objesini al
    try:
        github_issue = GitHubIssue.objects.get(id=issue_id)
    except GitHubIssue.DoesNotExist:
        messages.error(request, _('GitHub issue bulunamadı.'))
        return redirect('github_integration:sync_logs')
    
    # Erişim kontrolü ve yetki kontrolü
    can_modify_github = False
    
    if github_issue.task and github_issue.task.project:
        project = github_issue.task.project
        
        # Admin ve proje yöneticisi her şeyi yapabilir
        if request.user.is_superuser or request.user == project.manager:
            can_modify_github = True
        
        if not can_modify_github:
            messages.error(request, _('Bu GitHub issue\'ı kapatma izniniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
            return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # Issue zaten kapalıysa
    if github_issue.status == 'closed':
        messages.warning(request, _('Bu GitHub issue zaten kapalı.'))
        return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    if not hasattr(request.user, 'github_profile'):
        messages.warning(request, _('GitHub hesabınızı bağlamadan issue kapatamazsınız.'))
        return redirect('github_integration:github_connect')
    
    # GitHub API ile issue kapat
    try:
        github_api = GitHubAPI(github_profile=request.user.github_profile)
        repository = github_issue.repository
        
        result = github_api.close_issue(
            repository.repository_owner,
            repository.repository_name,
            github_issue.issue_number
        )
        
        if result:
            # Issue durumunu veritabanında güncelle
            github_issue.status = 'closed'
            github_issue.github_updated_at = timezone.now()
            github_issue.save()
            
            # Görevi de kapatma onayı istenirse
            if request.GET.get('close_task') == 'yes' and github_issue.task:
                github_issue.task.status = 'completed'
                github_issue.task.completed_date = timezone.now().date()
                github_issue.task.save()
                
                # Görev kapatma bildirimi
                messages.success(request, _('İlişkili görev de tamamlandı olarak işaretlendi.'))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='close_issue',
                status='success',
                message=f'Issue #{github_issue.issue_number} başarıyla kapatıldı.'
            )
            
            messages.success(request, _('GitHub issue başarıyla kapatıldı.'))
        else:
            messages.error(request, _('GitHub issue kapatılırken bir hata oluştu.'))
            
            # Hata kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='close_issue',
                status='failed',
                message=f'Issue #{github_issue.issue_number} kapatılırken hata oluştu.'
            )
    except Exception as e:
        messages.error(request, _('GitHub issue kapatılırken bir hata oluştu: {0}').format(str(e)))
        
        # Hata kaydı oluştur
        SyncLog.objects.create(
            user=request.user,
            repository=github_issue.repository,
            action='close_issue',
            status='failed',
            message=f'Issue #{github_issue.issue_number} kapatılırken hata oluştu: {str(e)}'
        )
    
    # Başarılı kapama sonrası yönlendirme
    if github_issue.task:
        return redirect('tasks:task_detail', task_id=github_issue.task.id)
    
    return redirect('github_integration:issue_comments', issue_id=issue_id)

@login_required
def issue_reopen(request, issue_id):
    """
    Kapalı GitHub issue'ı yeniden açma işlemi.
    """
    # GitHubIssue objesini al
    try:
        github_issue = GitHubIssue.objects.get(id=issue_id)
    except GitHubIssue.DoesNotExist:
        messages.error(request, _('GitHub issue bulunamadı.'))
        return redirect('github_integration:sync_logs')
    
    # Erişim kontrolü ve yetki kontrolü
    can_modify_github = False
    
    if github_issue.task and github_issue.task.project:
        project = github_issue.task.project
        
        # Admin ve proje yöneticisi her şeyi yapabilir
        if request.user.is_superuser or request.user == project.manager:
            can_modify_github = True
        
        if not can_modify_github:
            messages.error(request, _('Bu GitHub issue\'ı yeniden açma izniniz yok. Bu işlemi yalnızca proje yöneticisi veya sistem yöneticisi yapabilir.'))
            return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # Issue zaten açıksa
    if github_issue.status == 'open':
        messages.warning(request, _('Bu GitHub issue zaten açık.'))
        return redirect('github_integration:issue_comments', issue_id=issue_id)
    
    # Kullanıcının GitHub hesabı var mı kontrol et
    if not hasattr(request.user, 'github_profile'):
        messages.warning(request, _('GitHub hesabınızı bağlamadan issue yeniden açamazsınız.'))
        return redirect('github_integration:github_connect')
    
    # GitHub API ile issue yeniden aç
    try:
        github_api = GitHubAPI(github_profile=request.user.github_profile)
        repository = github_issue.repository
        
        result = github_api.reopen_issue(
            repository.repository_owner,
            repository.repository_name,
            github_issue.issue_number
        )
        
        if result:
            # Issue durumunu veritabanında güncelle
            github_issue.status = 'open'
            github_issue.github_updated_at = timezone.now()
            github_issue.save()
            
            # Görevi de yeniden açma onayı istenirse
            if request.GET.get('reopen_task') == 'yes' and github_issue.task and github_issue.task.status == 'completed':
                github_issue.task.status = 'in_progress'
                github_issue.task.completed_date = None
                github_issue.task.save()
                
                # Görev yeniden açma bildirimi
                messages.success(request, _('İlişkili görev de devam ediyor olarak işaretlendi.'))
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='update_issue',
                status='success',
                message=f'Issue #{github_issue.issue_number} başarıyla yeniden açıldı.'
            )
            
            messages.success(request, _('GitHub issue başarıyla yeniden açıldı.'))
        else:
            messages.error(request, _('GitHub issue yeniden açılırken bir hata oluştu.'))
            
            # Hata kaydı oluştur
            SyncLog.objects.create(
                user=request.user,
                repository=repository,
                action='update_issue',
                status='failed',
                message=f'Issue #{github_issue.issue_number} yeniden açılırken hata oluştu.'
            )
    except Exception as e:
        messages.error(request, _('GitHub issue yeniden açılırken bir hata oluştu: {0}').format(str(e)))
        
        # Hata kaydı oluştur
        SyncLog.objects.create(
            user=request.user,
            repository=github_issue.repository,
            action='update_issue',
            status='failed',
            message=f'Issue #{github_issue.issue_number} yeniden açılırken hata oluştu: {str(e)}'
        )
    
    # Başarılı yeniden açma sonrası yönlendirme
    if github_issue.task:
        return redirect('tasks:task_detail', task_id=github_issue.task.id)
    
    return redirect('github_integration:issue_comments', issue_id=issue_id)

@login_required
def github_messages_list(request):
    """
    Kullanıcının erişim iznine sahip olduğu GitHub issue'larının yorum ve mesajlarını listeler.
    """
    # Kullanıcının erişebileceği GitHub issue'larını ve ilgili mesaj gruplarını al
    if request.user.is_superuser:
        # Admin kullanıcı tüm GitHub issue'larını görebilir
        github_issues = GitHubIssue.objects.all().select_related('repository', 'task__project')
    else:
        # Diğer kullanıcılar için sadece erişilebilir issue'lar
        github_issues = []
        
        # 1. Kullanıcının yöneticisi olduğu projelerdeki issue'lar
        manager_projects = request.user.managed_projects.all()
        manager_project_issues = GitHubIssue.objects.filter(
            task__project__in=manager_projects
        ).select_related('repository', 'task__project')
        github_issues.extend(list(manager_project_issues))
        
        # 2. Kullanıcının takım üyesi olduğu projelerdeki issue'lar
        # ÖNCEKİ HATALI KOD: team_projects = request.user.team_projects.all()
        # Kullanıcının üye olduğu takımlara bağlı projeler veya doğrudan atandığı projeler
        team_projects = Project.objects.filter(
            Q(teams__members=request.user) | Q(team_members=request.user)
        ).distinct()
        
        team_project_issues = GitHubIssue.objects.filter(
            task__project__in=team_projects
        ).select_related('repository', 'task__project')
        github_issues.extend(list(team_project_issues))
        
        # 3. Kullanıcıya atanan görevlerin issue'ları
        assigned_task_issues = GitHubIssue.objects.filter(
            task__assignee=request.user
        ).select_related('repository', 'task__project')
        github_issues.extend(list(assigned_task_issues))
        
        # 4. Kullanıcının oluşturduğu görevlerin issue'ları
        created_task_issues = GitHubIssue.objects.filter(
            task__creator=request.user
        ).select_related('repository', 'task__project')
        github_issues.extend(list(created_task_issues))
        
        # Tekrarlanan issue'ları kaldır
        github_issues = list({issue.id: issue for issue in github_issues}.values())
    
    # İlgili mesaj gruplarını ve mesajları al
    issue_message_groups = {}
    for issue in github_issues:
        if issue.task:
            # Issue ile ilişkili görevin mesaj grubunu bul
            message_group = MessageGroup.objects.filter(related_task=issue.task).first()
            if message_group:
                # Son mesajı al
                last_message = Message.objects.filter(group=message_group).order_by('-created_at').first()
                if last_message:
                    issue_message_groups[issue.id] = {
                        'issue': issue,
                        'message_group': message_group,
                        'last_message': last_message,
                        'unread_count': Message.objects.filter(
                            group=message_group,
                            created_at__gt=request.user.last_login
                        ).exclude(sender=request.user).count() if request.user.last_login else 0
                    }
    
    # Context'e aktarılacak veriler
    context = {
        'github_issues': github_issues,
        'issue_message_groups': issue_message_groups,
        'title': 'GitHub Mesajlar',
    }
    
    return render(request, 'github_integration/github_messages_list.html', context)