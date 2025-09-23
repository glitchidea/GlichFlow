from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from datetime import datetime
from dateutil.parser import parse as parse_datetime

from .models import GitHubRepository, GitHubIssue, SyncLog, GitHubIssueComment
from .github_api import GitHubAPI
from projects.models import Project
from tasks.models import Task
from communications.models import MessageGroup, Message, MessageGroupMember, Notification

import logging
import traceback

logger = logging.getLogger(__name__)


def sync_project_with_github(project, github_profile, create_if_not_exists=False):
    """
    Bir projeyi GitHub repository'si ile senkronize eder.
    
    Parametreler:
        project: Proje objesi
        github_profile: GitHubProfile objesi
        create_if_not_exists: Eğer repository yoksa oluşturulsun mu?
        
    Dönüş:
        (bool, str): (Başarılı mı?, Mesaj)
    """
    # Demo mod kontrolü
    if getattr(settings, 'GITHUB_DEMO_MODE', False):
        # Projenin bir GitHub repository'si olup olmadığını kontrol et
        try:
            repository = GitHubRepository.objects.get(project=project)
            repository_exists = True
        except GitHubRepository.DoesNotExist:
            repository_exists = False
            
        if not repository_exists:
            # Demo repository oluştur
            repository = GitHubRepository.objects.create(
                project=project,
                repository_owner="demo-user",
                repository_name=f"demo-{project.slug}",
                repository_url=f"https://github.com/demo-user/demo-{project.slug}",
                is_private=False,
                default_branch="main",
                synced_at=timezone.now(),
                last_synced=timezone.now()
            )
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='create_repo',
                status='success',
                message=_("Demo modu: Repository oluşturuldu: {}").format(repository)
            )
            
            return True, _("Demo modu: Proje, GitHub repository'si {} ile senkronize edildi.").format(repository)
        else:
            # Repository bilgilerini güncelle
            repository.last_synced = timezone.now()
            repository.save()
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='sync_repo',
                status='success',
                message=_("Demo modu: Repository bilgileri güncellendi: {}").format(repository)
            )
            
            return True, _("Demo modu: Proje, GitHub repository'si {} ile senkronize edildi.").format(repository)
    
    # Gerçek API ile senkronizasyon
    try:
        # GitHub API istemcisi oluştur
        api = GitHubAPI(github_profile=github_profile)
        
        # Projenin zaten GitHub repository'si var mı kontrol et
        try:
            repository = GitHubRepository.objects.get(project=project)
            repository_exists = True
        except GitHubRepository.DoesNotExist:
            repository_exists = False
            
        if repository_exists:
            # Repository bilgilerini güncelle
            repo_info = api.get_repository(repository.repository_owner, repository.repository_name)
            
            if not repo_info:
                return False, _("GitHub repository bilgileri alınamadı.")
            
            # Repository bilgilerini güncelle
            repository.repository_url = repo_info.get('html_url', repository.repository_url)
            repository.is_private = repo_info.get('private', repository.is_private)
            repository.default_branch = repo_info.get('default_branch', repository.default_branch)
            repository.last_synced = timezone.now()
            repository.save()
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='sync_repo',
                status='success',
                message=_("Repository bilgileri güncellendi: {}").format(repository)
            )
            
            return True, _("Proje, GitHub repository'si {} ile senkronize edildi.").format(repository)
            
        elif create_if_not_exists:
            # Yeni repository oluştur
            repo_name = project.name.replace(' ', '-').lower()
            repo_info = api.create_repository(
                name=repo_name,
                description=project.description,
                private=True  # Varsayılan olarak özel repository
            )
            
            if not repo_info:
                return False, _("GitHub repository oluşturulamadı.")
            
            # Repository kaydını oluştur
            repository = GitHubRepository.objects.create(
                project=project,
                repository_owner=repo_info.get('owner', {}).get('login'),
                repository_name=repo_info.get('name'),
                repository_url=repo_info.get('html_url', ''),
                is_private=repo_info.get('private', True),
                default_branch=repo_info.get('default_branch', 'main'),
                last_synced=timezone.now()
            )
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='create_repo',
                status='success',
                message=_("Yeni repository oluşturuldu: {}").format(repository)
            )
            
            return True, _("Proje için yeni GitHub repository'si oluşturuldu: {}").format(repository)
            
        else:
            return False, _("Proje henüz GitHub'a bağlanmamış. Önce bir repository bağlayın.")
            
    except Exception as e:
        logger.error(f"Proje senkronizasyon hatası: {str(e)}", exc_info=True)
        return False, _("Senkronizasyon sırasında bir hata oluştu: {}").format(str(e))


def sync_task_with_github_issue(task, github_profile, create_if_not_exists=False):
    """
    Görevi GitHub issue ile senkronize eder.
    Eğer görev henüz GitHub'a bağlı değilse ve create_if_not_exists=True ise, 
    yeni bir issue oluşturur.
    
    Parametreler:
        task (Task): Senkronize edilecek görev objesi
        github_profile (GitHubProfile): Kullanıcının GitHub profil objesi
        create_if_not_exists (bool): Issue yoksa oluşturulsun mu?
        
    Dönüş:
        tuple: (success, message) - işlemin başarılı olup olmadığı ve mesaj
    """
    try:
        # Projenin GitHub repository'si var mı kontrol et
        try:
            repository = GitHubRepository.objects.get(project=task.project)
        except GitHubRepository.DoesNotExist:
            return False, _("Görevin bağlı olduğu projenin GitHub repository'si bulunamadı.")
        
        # GitHub API istemcisi oluştur
        api = GitHubAPI(github_profile=github_profile)
        
        # Görevin zaten GitHub issue'su var mı kontrol et
        try:
            issue = GitHubIssue.objects.get(task=task)
            issue_exists = True
        except GitHubIssue.DoesNotExist:
            issue_exists = False
        
        if issue_exists:
            # Issue bilgilerini güncelle
            issue_info = api.get_issue(repository.repository_owner, repository.repository_name, issue.issue_number)
            
            if not issue_info:
                return False, _("GitHub issue bilgileri alınamadı.")
            
            # Issue durumunu görev durumuna göre güncelle
            if task.status == 'completed' and issue_info.get('state') != 'closed':
                api.close_issue(repository.repository_owner, repository.repository_name, issue.issue_number)
                issue_action = 'close_issue'
                issue_info['state'] = 'closed'
            elif task.status != 'completed' and issue_info.get('state') == 'closed':
                api.reopen_issue(repository.repository_owner, repository.repository_name, issue.issue_number)
                issue_action = 'update_issue'
                issue_info['state'] = 'open'
            else:
                # Issue başlık ve içeriğini görev bilgileriyle güncelle
                api.update_issue(
                    repository.repository_owner,
                    repository.repository_name,
                    issue.issue_number,
                    title=task.title,
                    body=task.description
                )
                issue_action = 'update_issue'
            
            # Issue bilgilerini güncelle
            issue.issue_title = issue_info.get('title', issue.issue_title)
            issue.issue_body = issue_info.get('body', '') or ''
            issue.status = issue_info.get('state', issue.status)
            issue.github_updated_at = datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
            issue.save()
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action=issue_action,
                status='success',
                message=_("Issue güncellendi: #{}").format(issue.issue_number)
            )
            
            return True, _("Görev, GitHub issue #{} ile senkronize edildi.").format(issue.issue_number)
            
        elif create_if_not_exists:
            # Yeni issue oluştur
            issue_info = api.create_issue(
                repository.repository_owner,
                repository.repository_name,
                title=task.title,
                body=task.description
            )
            
            if not issue_info:
                return False, _("GitHub issue oluşturulamadı.")
            
            # Issue kaydını oluştur
            issue = GitHubIssue.objects.create(
                task=task,
                repository=repository,
                issue_number=issue_info.get('number'),
                issue_title=issue_info.get('title'),
                issue_body=issue_info.get('body', '') or '',
                issue_url=issue_info.get('html_url', ''),
                status=issue_info.get('state', 'open'),
                github_created_at=datetime.fromisoformat(issue_info.get('created_at').replace('Z', '+00:00')),
                github_updated_at=datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
            )
            
            # Görev tamamlandıysa issue'yu kapat
            if task.status == 'completed':
                api.close_issue(repository.repository_owner, repository.repository_name, issue.issue_number)
                issue.status = 'closed'
                issue.save()
            
            # Senkronizasyon kaydı oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='create_issue',
                status='success',
                message=_("Yeni issue oluşturuldu: #{}").format(issue.issue_number)
            )
            
            return True, _("Görev için yeni GitHub issue #{} oluşturuldu.").format(issue.issue_number)
            
        else:
            return False, _("Görev henüz GitHub'a bağlanmamış. Önce bir issue oluşturun.")
            
    except Exception as e:
        logger.error(f"Görev senkronizasyon hatası: {str(e)}", exc_info=True)
        return False, _("Senkronizasyon sırasında bir hata oluştu: {}").format(str(e))


def import_github_issues(repository, github_profile, import_params=None):
    """
    GitHub repository'sindeki issue'ları task olarak içe aktarır.
    
    Parametreler:
        repository: GitHubRepository objesi
        github_profile: GitHubProfile objesi
        import_params: İçe aktarma parametreleri (dict)
            - import_all: Tüm issue'ları içe aktar (boolean)
            - import_closed: Kapalı issue'ları içe aktar (boolean)
            - issue_numbers: Belirli issue'ları içe aktar (list of int)
            
    Dönüş:
        (imported_issues, skipped_issues, errors): (İçe aktarılan issue'lar, Atlanan issue'lar, Hatalar)
    """
    import_params = import_params or {}
    
    from tasks.models import Task
    from github_integration.models import SyncLog
    
    imported_issues = []
    skipped_issues = []
    errors = []
    
    # Demo mod kontrolü
    if getattr(settings, 'GITHUB_DEMO_MODE', False):
        # Demo için issue'ları oluştur
        demo_issues = [
            {
                'number': 1,
                'title': 'Demo Issue 1: User authentication',
                'body': 'Implement user authentication with JWT tokens',
                'state': 'open',
                'labels': [{'name': 'enhancement'}, {'name': 'frontend'}],
                'user': {'login': 'demo-user'},
                'html_url': f'https://github.com/{repository.repository_owner}/{repository.repository_name}/issues/1'
            },
            {
                'number': 2,
                'title': 'Demo Issue 2: Responsive design',
                'body': 'Fix responsive layout issues on mobile devices',
                'state': 'open',
                'labels': [{'name': 'bug'}, {'name': 'frontend'}],
                'user': {'login': 'demo-contributor'},
                'html_url': f'https://github.com/{repository.repository_owner}/{repository.repository_name}/issues/2'
            },
            {
                'number': 3,
                'title': 'Demo Issue 3: Performance optimization',
                'body': 'Optimize database queries for better performance',
                'state': 'closed',
                'labels': [{'name': 'enhancement'}, {'name': 'backend'}],
                'user': {'login': 'demo-user'},
                'html_url': f'https://github.com/{repository.repository_owner}/{repository.repository_name}/issues/3'
            }
        ]
        
        # İçe aktarma parametrelerini al
        import_all = import_params.get('import_all', True)
        import_closed = import_params.get('import_closed', False)
        issue_numbers = import_params.get('issue_numbers', [])
        
        # Parametrelere göre issue'ları filtrele
        if len(issue_numbers) > 0:
            # Belirli issue'ları al
            filtered_issues = [issue for issue in demo_issues if issue['number'] in issue_numbers]
        else:
            # Tüm issue'ları al
            if not import_closed:
                # Sadece açık issue'ları al
                filtered_issues = [issue for issue in demo_issues if issue['state'] == 'open']
            else:
                # Tüm issue'ları al
                filtered_issues = demo_issues
        
        # Repository'nin bağlı olduğu proje
        project = repository.project
        
        # İssue'ları döngüyle işle
        for issue in filtered_issues:
            issue_number = issue['number']
            
            # Bu issue zaten task olarak eklenmiş mi kontrol et
            existing_task = Task.objects.filter(
                project=project,
                github_issue_number=issue_number,
                github_issue_url=issue['html_url']
            ).first()
            
            if existing_task:
                # Task zaten var, atlayalım
                skipped_issues.append((issue_number, issue['title'], "Bu issue zaten task olarak eklenmiş."))
                continue
            
            # Label'ları düzenle
            labels = [label['name'] for label in issue.get('labels', [])]
            
            # Task tipi belirle
            task_type = 'bug' if 'bug' in labels else 'feature'
            
            # Task önceliği belirle
            priority = 'high' if 'high' in labels else 'medium'
            
            # Durumu belirle
            status = 'closed' if issue['state'] == 'closed' else 'open'
            
            # Task oluştur
            task = Task.objects.create(
                project=project,
                title=issue['title'],
                description=issue['body'] or '',
                created_by=github_profile.user,
                status=status,
                task_type=task_type,
                priority=priority,
                github_issue_number=issue_number,
                github_issue_url=issue['html_url'],
                github_sync_status='synced',
                github_last_synced=timezone.now()
            )
            
            # Senkronizasyon log'u oluştur
            SyncLog.objects.create(
                user=github_profile.user,
                repository=repository,
                action='import_issue',
                status='success',
                message=_("Demo modu: Task oluşturuldu: Issue #{} - {}").format(issue_number, issue['title'])
            )
            
            imported_issues.append((issue_number, issue['title'], task))
        
        return imported_issues, skipped_issues, "Demo modu: {} issue başarıyla içe aktarıldı. {} issue atlandı.".format(len(imported_issues), len(skipped_issues))
    
    try:
        # GitHub API istemcisi oluştur
        api = GitHubAPI(github_profile=github_profile)
        
        # Repository'nin bağlı olduğu projeyi al
        project = repository.project
        
        # İçe aktarma parametrelerini al
        import_all = import_params.get('import_all', True)
        import_closed = import_params.get('import_closed', False)
        issue_numbers = import_params.get('issue_numbers', [])
        
        # Repository'deki issue'ları al
        if len(issue_numbers) > 0:
            # Belirli issue'ları al
            issues = []
            for issue_number in issue_numbers:
                issue_info = api.get_issue(repository.repository_owner, repository.repository_name, issue_number)
                if issue_info:
                    issues.append(issue_info)
        else:
            # Tüm issue'ları al
            issues = api.get_issues(repository.repository_owner, repository.repository_name, state='all' if import_closed else 'open')
        
        if not issues:
            return imported_issues, skipped_issues, "GitHub issue'ları alınamadı veya repository'de hiç issue yok."
        
        with transaction.atomic():
            for issue_info in issues:
                # Pull request'leri atla (bunlar issue API'sinde de görünür)
                if 'pull_request' in issue_info:
                    skipped_issues.append(issue_info.get('number'))
                    continue
                
                # Kapalı issue'ları atla (eğer import_closed=False ise)
                if not import_closed and issue_info.get('state') == 'closed':
                    skipped_issues.append(issue_info.get('number'))
                    continue
                
                issue_number = issue_info.get('number')
                
                # Bu issue zaten içe aktarılmış mı kontrol et
                try:
                    issue = GitHubIssue.objects.get(
                        repository=repository,
                        issue_number=issue_number
                    )
                    
                    # İlişkilendirilmiş görev varsa güncelle
                    if issue.task:
                        task = issue.task
                        
                        # Görevi güncelle
                        task.title = issue_info.get('title')
                        task.description = issue_info.get('body', '') or ''
                        
                        if issue_info.get('state') == 'closed':
                            task.status = 'completed'
                        
                        task.save()
                        
                        # Issue'yu güncelle
                        issue.issue_title = issue_info.get('title')
                        issue.issue_body = issue_info.get('body', '') or ''
                        issue.status = issue_info.get('state')
                        issue.github_updated_at = datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
                        issue.save()
                        
                        skipped_issues.append(issue_number)
                    else:
                        # Yeni görev oluştur
                        task = Task.objects.create(
                            project=project,
                            title=issue_info.get('title'),
                            description=issue_info.get('body', '') or '',
                            creator=github_profile.user,
                            status='completed' if issue_info.get('state') == 'closed' else 'todo'
                        )
                        
                        # Issue'yu görevle ilişkilendir
                        issue.task = task
                        issue.issue_title = issue_info.get('title')
                        issue.issue_body = issue_info.get('body', '') or ''
                        issue.status = issue_info.get('state')
                        issue.github_updated_at = datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
                        issue.save()
                        
                        imported_issues.append(issue_number)
                        
                except GitHubIssue.DoesNotExist:
                    # Yeni görev oluştur
                    task = Task.objects.create(
                        project=project,
                        title=issue_info.get('title'),
                        description=issue_info.get('body', '') or '',
                        creator=github_profile.user,
                        status='completed' if issue_info.get('state') == 'closed' else 'todo'
                    )
                    
                    # Issue kaydını oluştur
                    GitHubIssue.objects.create(
                        task=task,
                        repository=repository,
                        issue_number=issue_number,
                        issue_title=issue_info.get('title'),
                        issue_body=issue_info.get('body', '') or '',
                        issue_url=issue_info.get('html_url', ''),
                        status=issue_info.get('state'),
                        github_created_at=datetime.fromisoformat(issue_info.get('created_at').replace('Z', '+00:00')),
                        github_updated_at=datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
                    )
                    
                    imported_issues.append(issue_number)
            
        # Senkronizasyon kaydı oluştur
        SyncLog.objects.create(
            user=github_profile.user,
            repository=repository,
            action='import_issues',
            status='success',
            message=f"{len(imported_issues)} yeni issue içe aktarıldı, {len(skipped_issues)} issue atlandı."
        )
        
        repository.last_synced = timezone.now()
        repository.save()
        
        return imported_issues, skipped_issues, None
        
    except Exception as e:
        logger.error(f"Issue içe aktarma hatası: {str(e)}", exc_info=True)
        return [], [], str(e)


def create_issue_data_from_task(task):
    """
    Görev bilgilerinden GitHub issue verisi oluşturur.
    """
    # Issue başlığı
    title = task.title
    
    # Issue açıklaması
    body = f"## {task.title}\n\n"
    
    if task.description:
        body += f"{task.description}\n\n"
    
    body += "### Görev Bilgileri\n\n"
    body += f"* **Durum:** {dict(Task.STATUS_CHOICES).get(task.status, task.status)}\n"
    body += f"* **Öncelik:** {dict(Task.PRIORITY_CHOICES).get(task.priority, task.priority)}\n"
    
    if task.start_date:
        body += f"* **Başlangıç Tarihi:** {task.start_date.strftime('%Y-%m-%d')}\n"
    
    if task.due_date:
        body += f"* **Son Tarih:** {task.due_date.strftime('%Y-%m-%d')}\n"
    
    if task.estimate_hours:
        body += f"* **Tahmini Süre:** {task.estimate_hours} saat\n"
    
    if task.assignee:
        body += f"* **Atanan Kişi:** {task.assignee.get_full_name() or task.assignee.username}\n"
    
    body += f"\n---\n*Bu issue, {settings.SITE_NAME} üzerindeki görev yönetim sisteminden otomatik olarak senkronize edilmiştir.*"
    
    return {
        "title": title,
        "body": body
    }


def _create_notification_for_comment(issue, github_comment, message_group=None):
    """
    GitHub issue yorumu için bildirim oluşturur ve ilgili kullanıcılara gönderir.
    
    Parametreler:
        issue: GitHubIssue objesi
        github_comment: GitHubIssueComment objesi
        message_group: İlişkili MessageGroup objesi (varsa)
    """
    if not issue.task or not issue.task.project:
        return
    
    task = issue.task
    project = task.project
    
    # Bildirim alacak kullanıcılar
    recipients = set()
    
    # 1. Görevin sahibi
    if task.assignee:
        recipients.add(task.assignee)
    
    # 2. Görevin oluşturucusu
    if task.creator:
        recipients.add(task.creator)
    
    # 3. Proje yöneticisi
    if project.manager:
        recipients.add(project.manager)
    
    # 4. Mesaj grubunda olan kişiler
    if message_group:
        for member in message_group.group_members.all():
            recipients.add(member.user)
    
    # 5. Ekip üyeleri
    for team_member in project.team_members.all():
        recipients.add(team_member)
    
    # Bildirim başlığı ve içeriği
    notification_title = f"GitHub Issue #{issue.issue_number} - Yeni Yorum"
    notification_content = f"{github_comment.user_login} yeni bir yorum yaptı: {github_comment.body[:100]}{'...' if len(github_comment.body) > 100 else ''}"
    
    # Her alıcı için bildirim oluştur
    for recipient in recipients:
        notification = Notification.objects.create(
            recipient=recipient,
            title=notification_title,
            content=notification_content,
            notification_type='info',
            related_task=task,
            related_message_group=message_group
        )


def sync_issue_comments(issue, github_profile=None, create_messages=True, send_notifications=False):
    """
    GitHub issue'daki yorumları senkronize eder ve iletişim sistemindeki mesajları oluşturur/günceller.
    
    Parametreler:
        issue: GitHubIssue objesi
        github_profile: GitHubProfile objesi (None ise issue.repository.github_profile kullanılır)
        create_messages: Mesaj oluşturup oluşturmayacağını belirler
        send_notifications: Yeni yorumlar için bildirim gönderip göndermeyeceğini belirler
        
    Dönüş:
        Eğer eski biçim kullanılırsa: (imported_comments, new_comments, updated_comments, errors)
        Yeni biçim: Yeni yorum sayısı (int)
    """
    if not issue:
        return 0 if send_notifications else ([], [], [], ["Geçersiz issue"])
    
    # GitHub profili kullanıcı tarafından verilmediyse repository'den al
    if not github_profile:
        github_profile = issue.repository.github_profile
        
    if not github_profile:
        return 0 if send_notifications else ([], [], [], ["Geçersiz GitHub profili"])
    
    repository = issue.repository
    owner = repository.repository_owner
    repo = repository.repository_name
    issue_number = issue.issue_number
    
    imported_comments = []
    new_comments = []
    updated_comments = []
    errors = []
    
    # GitHub API üzerinden yorumları al
    github_api = GitHubAPI(github_profile=github_profile)
    
    try:
        # Issue yorumlarını al
        comments = github_api.get_issue_comments(owner, repo, issue_number)
        
        # Issue için bir mesaj grubu oluştur ya da mevcut olanı al
        message_group = None
        
        if create_messages:
            task = issue.task
            
            if task:
                # Görev mesaj grubu var mı kontrol et
                message_group = MessageGroup.objects.filter(related_task=task).first()
                
                # Yoksa oluştur
                if not message_group:
                    # İsim oluştur
                    group_name = f"GitHub Issue #{issue_number}: {issue.issue_title}"
                    
                    # Grup oluştur
                    message_group = MessageGroup.objects.create(
                        name=group_name,
                        type='task',
                        related_task=task
                    )
                    
                    # Proje yöneticisini ve görevi atandığı kişileri gruba ekle
                    if task.project and task.project.manager:
                        MessageGroupMember.objects.create(
                            group=message_group,
                            user=task.project.manager,
                            role='admin'
                        )
                    
                    if task.assignee:
                        MessageGroupMember.objects.create(
                            group=message_group,
                            user=task.assignee,
                            role='member'
                        )
                    
                    if task.creator:
                        MessageGroupMember.objects.create(
                            group=message_group,
                            user=task.creator,
                            role='member'
                        )
        
        with transaction.atomic():
            # Her yorum için
            for comment_data in comments:
                try:
                    comment_id = comment_data.get('id')
                    user_login = comment_data.get('user', {}).get('login')
                    user_avatar = comment_data.get('user', {}).get('avatar_url')
                    body = comment_data.get('body', '')
                    html_url = comment_data.get('html_url', '')
                    github_created_at = parse_datetime(comment_data.get('created_at'))
                    github_updated_at = parse_datetime(comment_data.get('updated_at'))
                    
                    # Yorum veritabanında var mı kontrol et
                    comment, created = GitHubIssueComment.objects.update_or_create(
                        github_issue=issue,
                        comment_id=comment_id,
                        defaults={
                            'user_login': user_login,
                            'user_avatar': user_avatar,
                            'body': body,
                            'html_url': html_url,
                            'github_created_at': github_created_at,
                            'github_updated_at': github_updated_at,
                        }
                    )
                    
                    if created:
                        # Yeni yorum
                        new_comments.append(comment)
                        
                        # Yeni yorum için bildirim oluştur
                        if send_notifications:
                            _create_notification_for_comment(issue, comment, message_group)
                    else:
                        # Var olan yorum güncellendi
                        updated_comments.append(comment)
                    
                    # İletişim sistemine mesaj olarak ekle
                    if create_messages and message_group:
                        # Mesaj var mı kontrol et
                        if comment.system_message:
                            # Varsa güncelle
                            system_message = comment.system_message
                            if system_message.content != body:
                                system_message.content = f"**GitHub {user_login}:** {body}\n\n*Bu mesaj GitHub'dan otomatik olarak alındı.*"
                                system_message.updated_at = timezone.now()
                                system_message.save(update_fields=['content', 'updated_at'])
                        else:
                            # Yoksa oluştur
                            system_message = Message.objects.create(
                                group=message_group,
                                sender=github_profile.user,
                                message_type='text',
                                content=f"**GitHub {user_login}:** {body}\n\n*Bu mesaj GitHub'dan otomatik olarak alındı.*",
                                created_at=github_created_at
                            )
                            
                            # GitHubIssueComment'e bağla
                            comment.system_message = system_message
                            comment.save(update_fields=['system_message'])
                    
                    imported_comments.append(comment)
                
                except Exception as e:
                    error_msg = f"Issue yorum senkronizasyon hatası: {str(e)}"
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())
                    errors.append(error_msg)
    
    except Exception as e:
        error_msg = f"Issue yorum senkronizasyon hatası: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        errors.append(error_msg)
    
    if send_notifications:
        return len(new_comments)
    
    return imported_comments, new_comments, updated_comments, errors


def create_github_comment_from_message(message, github_issue):
    """
    İletişim sistemindeki bir mesajı GitHub issue yorumu olarak oluşturur.
    
    Parametreler:
        message: Message objesi
        github_issue: GitHubIssue objesi
        
    Dönüş:
        (success, created_comment, error_message)
    """
    if not message or not github_issue:
        return False, None, "Geçersiz mesaj veya GitHub issue"
    
    # GitHub bağlantısı var mı kontrol et
    repository = github_issue.repository
    if not repository:
        return False, None, "Issue bir GitHub repository'e bağlı değil"
    
    # Görev bağlantısı
    task = github_issue.task
    if not task:
        return False, None, "Issue bir göreve bağlı değil"
    
    # Proje ve kullanıcı kontrolü
    project = task.project
    if not project:
        return False, None, "Görev bir projeye bağlı değil"
    
    # Mesajı gönderen kullanıcının GitHub profili var mı kontrol et
    try:
        github_profile = message.sender.github_profile
    except Exception:
        return False, None, "Mesajı gönderen kullanıcının GitHub profili bulunamadı"
    
    # GitHub API üzerinden yorum gönder
    github_api = GitHubAPI(github_profile=github_profile)
    owner = repository.repository_owner
    repo = repository.repository_name
    issue_number = github_issue.issue_number
    
    try:
        # Bu mesaj zaten GitHub'a gönderilmiş mi kontrol et
        existing_comment = GitHubIssueComment.objects.filter(
            github_issue=github_issue,
            system_message=message
        ).first()
        
        if existing_comment:
            # Eğer varsa ve farklıysa güncelle
            if existing_comment.body != message.content:
                comment_data = github_api.update_issue_comment(
                    owner, 
                    repo, 
                    existing_comment.comment_id, 
                    message.content
                )
                
                # Yorum bilgilerini güncelle
                if comment_data:
                    existing_comment.body = comment_data.get('body', '')
                    existing_comment.github_updated_at = parse_datetime(comment_data.get('updated_at'))
                    existing_comment.save(update_fields=['body', 'github_updated_at'])
                    
                    return True, existing_comment, None
            else:
                # Zaten aynı, güncelleme yapmaya gerek yok
                return True, existing_comment, None
        else:
            # Yeni yorum oluştur
            comment_data = github_api.create_issue_comment(
                owner, 
                repo, 
                issue_number, 
                message.content
            )
            
            if comment_data:
                # Yorumu veritabanına kaydet
                comment = GitHubIssueComment.objects.create(
                    github_issue=github_issue,
                    comment_id=comment_data.get('id'),
                    user_login=comment_data.get('user', {}).get('login', github_profile.github_username),
                    user_avatar=comment_data.get('user', {}).get('avatar_url', ''),
                    body=comment_data.get('body', ''),
                    html_url=comment_data.get('html_url', ''),
                    github_created_at=parse_datetime(comment_data.get('created_at')),
                    github_updated_at=parse_datetime(comment_data.get('updated_at')),
                    system_message=message
                )
                
                return True, comment, None
    
    except Exception as e:
        error_msg = f"GitHub yorum oluşturma hatası: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        return False, None, error_msg
    
    return False, None, "GitHub yorumu oluşturulamadı" 