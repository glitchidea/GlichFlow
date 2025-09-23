import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from celery.schedules import crontab
from django.db import models

from .models import GitHubRepository, GitHubIssue, SyncLog, GitHubProfile, GitHubIssueComment
from .github_api import GitHubAPI
from .sync import sync_project_with_github, sync_task_with_github_issue, import_github_issues, sync_issue_comments

logger = logging.getLogger(__name__)

@shared_task
def sync_all_repositories():
    """
    Tüm GitHub repository'lerini periyodik olarak senkronize eder.
    """
    logger.info("Starting scheduled sync of all GitHub repositories")
    
    # Son 24 saat içinde senkronize edilmemiş repository'leri al
    last_day = timezone.now() - timedelta(days=1)
    repositories = GitHubRepository.objects.filter(
        last_synced__lt=last_day
    ).select_related('project')
    
    sync_count = 0
    error_count = 0
    
    for repository in repositories:
        try:
            # Projenin sahibinin GitHub profil bilgilerini al
            github_profile = GitHubProfile.objects.filter(
                user=repository.project.manager
            ).first()
            
            if not github_profile:
                logger.warning(f"No GitHub profile found for project manager of {repository}")
                continue
            
            # Repository'yi senkronize et
            success, message = sync_project_with_github(repository.project, github_profile)
            
            if success:
                sync_count += 1
                logger.info(f"Successfully synced repository: {repository}")
            else:
                error_count += 1
                logger.error(f"Failed to sync repository: {repository}. Error: {message}")
                
        except Exception as e:
            error_count += 1
            logger.exception(f"Error syncing repository {repository}: {str(e)}")
    
    logger.info(f"Completed sync of all repositories. Success: {sync_count}, Errors: {error_count}")
    return f"Synced {sync_count} repositories, {error_count} errors"

@shared_task
def sync_repository_with_github(repository_id):
    """
    Belirli bir repository'yi GitHub ile senkronize eder.
    Webhook'tan tetiklendiğinde veya manuel olarak kullanılabilir.
    """
    logger.info(f"Starting sync of repository with ID: {repository_id}")
    
    try:
        repository = GitHubRepository.objects.select_related('project').get(id=repository_id)
        
        # Projenin sahibinin GitHub profil bilgilerini al
        github_profile = GitHubProfile.objects.filter(
            user=repository.project.manager
        ).first()
        
        if not github_profile:
            logger.warning(f"No GitHub profile found for project manager of {repository}")
            SyncLog.objects.create(
                repository=repository,
                action='sync_repo',
                status='failed',
                message=f"No GitHub profile found for project manager"
            )
            return "No GitHub profile found"
        
        # Repository'yi senkronize et
        success, message = sync_project_with_github(repository.project, github_profile)
        
        if success:
            logger.info(f"Successfully synced repository: {repository}")
            return "Success"
        else:
            logger.error(f"Failed to sync repository: {repository}. Error: {message}")
            return f"Error: {message}"
            
    except GitHubRepository.DoesNotExist:
        logger.error(f"Repository with ID {repository_id} not found")
        return f"Repository not found"
    except Exception as e:
        logger.exception(f"Error syncing repository with ID {repository_id}: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def update_issue_from_github(repository_id, issue_number, action, event_type=None):
    """
    GitHub'dan gelen issue güncellemelerine göre görevi günceller.
    Webhook'tan tetiklendiğinde kullanılır.
    
    Parametreler:
        repository_id: GitHubRepository ID'si
        issue_number: GitHub Issue numarası
        action: Yapılan işlem (opened, closed, edited, reopened, created, deleted, vb.)
        event_type: GitHub webhook event tipi (issue, issue_comment, vb.)
    """
    logger.info(f"Processing GitHub issue update: Repo ID {repository_id}, Issue #{issue_number}, Action: {action}, Event: {event_type}")
    
    try:
        repository = GitHubRepository.objects.select_related('project').get(id=repository_id)
        
        # Projenin sahibinin GitHub profil bilgilerini al
        github_profile = GitHubProfile.objects.filter(
            user=repository.project.manager
        ).first()
        
        if not github_profile:
            logger.warning(f"No GitHub profile found for project manager of {repository}")
            SyncLog.objects.create(
                repository=repository,
                action='update_issue',
                status='failed',
                message=f"No GitHub profile found for project manager, Issue #{issue_number}"
            )
            return "No GitHub profile found"
        
        # GitHub API istemcisi oluştur
        api = GitHubAPI(github_profile=github_profile)
        
        # Issue yorumları ile ilgili bir event mi kontrol et
        if event_type in ['issue_comment', 'comment']:
            try:
                # İlgili GitHub issue'yu bul
                github_issue = GitHubIssue.objects.get(
                    repository=repository,
                    issue_number=issue_number
                )
                
                # Yorum senkronizasyonu yap ve bildirim gönder
                if action in ['created', 'edited']:
                    from github_integration.sync import sync_issue_comments
                    
                    # Yorumları senkronize et ve bildirim gönder
                    new_comments = sync_issue_comments(
                        github_issue, 
                        github_profile, 
                        create_messages=True,
                        send_notifications=True
                    )
                    
                    # Log kaydı oluştur
                    SyncLog.objects.create(
                        repository=repository,
                        action='sync_comments',
                        status='success',
                        message=f"Synced comments for issue #{issue_number}, found {new_comments} new comments"
                    )
                    
                    logger.info(f"Successfully synced comments for issue #{issue_number}, found {new_comments} new comments")
                    return f"Synced comments, found {new_comments} new comments"
                
                return "No action taken for this comment event"
            
            except GitHubIssue.DoesNotExist:
                logger.warning(f"Received comment for non-existing issue #{issue_number}")
                return "Issue not found in our system"
            
            except Exception as e:
                logger.exception(f"Error processing comment for issue #{issue_number}: {str(e)}")
                return f"Error processing comment: {str(e)}"
        
        # Issue bilgilerini al
        issue_info = api.get_issue(repository.repository_owner, repository.repository_name, issue_number)
        
        if not issue_info:
            logger.error(f"Failed to get issue info: Repo {repository}, Issue #{issue_number}")
            SyncLog.objects.create(
                repository=repository,
                action='update_issue',
                status='failed',
                message=f"Failed to get issue info from GitHub API, Issue #{issue_number}"
            )
            return f"Failed to get issue info"
        
        # Bu issue veritabanımızda var mı kontrol et
        try:
            github_issue = GitHubIssue.objects.get(
                repository=repository,
                issue_number=issue_number
            )
            
            # İlişkili bir görev var mı?
            if github_issue.task:
                task = github_issue.task
                
                with transaction.atomic():
                    # Issue bilgilerini güncelle
                    github_issue.issue_title = issue_info.get('title', github_issue.issue_title)
                    github_issue.issue_body = issue_info.get('body', '') or ''
                    github_issue.status = issue_info.get('state', github_issue.status)
                    github_issue.github_updated_at = datetime.fromisoformat(issue_info.get('updated_at').replace('Z', '+00:00'))
                    github_issue.save()
                    
                    # Görevi güncelle
                    task.title = issue_info.get('title')
                    task.description = issue_info.get('body', '') or ''
                    
                    # Issue kapatıldıysa görevi tamamla
                    if action == 'closed' and issue_info.get('state') == 'closed':
                        task.status = 'completed'
                    # Issue yeniden açıldıysa görev durumunu güncelle
                    elif action == 'reopened' and issue_info.get('state') == 'open':
                        task.status = 'in_progress'
                    
                    task.save()
                
                # Log kaydı oluştur
                SyncLog.objects.create(
                    repository=repository,
                    action='update_issue',
                    status='success',
                    message=f"Updated task from GitHub issue #{issue_number}: {action}"
                )
                
                # Issue yorumları da senkronize et
                if action in ['created', 'edited', 'opened', 'reopened']:
                    try:
                        from github_integration.sync import sync_issue_comments
                        sync_issue_comments(github_issue, github_profile, send_notifications=True)
                    except Exception as e:
                        logger.exception(f"Error syncing comments for issue #{issue_number}: {str(e)}")
                
                logger.info(f"Successfully updated task from issue: Repo {repository}, Issue #{issue_number}")
                return "Success"
            else:
                logger.warning(f"Issue #{issue_number} exists but no task is associated")
                return "Issue exists but no task is associated"
            
        except GitHubIssue.DoesNotExist:
            # Bu issue henüz içe aktarılmamış, yeni görev ve issue kaydı oluştur
            if action in ['opened', 'edited', 'reopened']:
                from tasks.models import Task
                
                with transaction.atomic():
                    # Yeni görev oluştur
                    task = Task.objects.create(
                        project=repository.project,
                        title=issue_info.get('title'),
                        description=issue_info.get('body', '') or '',
                        creator=repository.project.manager,
                        status='completed' if issue_info.get('state') == 'closed' else 'todo'
                    )
                    
                    # Issue kaydını oluştur
                    github_issue = GitHubIssue.objects.create(
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
                
                # Log kaydı oluştur
                SyncLog.objects.create(
                    repository=repository,
                    action='create_issue',
                    status='success',
                    message=f"Imported new GitHub issue #{issue_number} as task"
                )
                
                logger.info(f"Imported new issue as task: Repo {repository}, Issue #{issue_number}")
                return "Success"
            else:
                logger.info(f"Ignored action '{action}' for non-existing issue #{issue_number}")
                return f"Ignored action '{action}' for non-existing issue"
    
    except Exception as e:
        logger.exception(f"Error processing issue update: {str(e)}")
        return f"Error: {str(e)}"

@shared_task
def sync_stale_issues():
    """
    Son zamanlarda güncellenmemiş görevlerin GitHub issue'larını senkronize eder.
    """
    logger.info("Starting scheduled sync of stale issues")
    
    # Son 7 gün içinde güncellenmemiş issue'ları al
    last_week = timezone.now() - timedelta(days=7)
    github_issues = GitHubIssue.objects.filter(
        last_synced__lt=last_week,
        task__isnull=False
    ).select_related('repository', 'task')
    
    sync_count = 0
    error_count = 0
    
    for github_issue in github_issues:
        try:
            # Repository sahibinin GitHub profil bilgilerini al
            github_profile = GitHubProfile.objects.filter(
                user=github_issue.repository.project.manager
            ).first()
            
            if not github_profile:
                logger.warning(f"No GitHub profile found for project manager of issue #{github_issue.issue_number}")
                continue
            
            # Görevi senkronize et
            success, message = sync_task_with_github_issue(github_issue.task, github_profile)
            
            if success:
                sync_count += 1
                logger.info(f"Successfully synced issue: #{github_issue.issue_number}")
            else:
                error_count += 1
                logger.error(f"Failed to sync issue: #{github_issue.issue_number}. Error: {message}")
                
        except Exception as e:
            error_count += 1
            logger.exception(f"Error syncing issue #{github_issue.issue_number}: {str(e)}")
    
    logger.info(f"Completed sync of stale issues. Success: {sync_count}, Errors: {error_count}")
    return f"Synced {sync_count} issues, {error_count} errors"

@shared_task
def sync_recent_issue_comments():
    """
    Son 1 saat içinde güncellenen GitHub issue yorumlarını senkronize eder
    ve ilgili kullanıcılara bildirim gönderir.
    """
    logger.info("Son 1 saatte güncellenen GitHub issue yorumlarını senkronize etme işlemi başlatıldı")
    
    # Son 1 saat içinde güncellenen ya da açık durumda olan tasklar ile ilişkili issue'ları al
    one_hour_ago = timezone.now() - timedelta(hours=1)
    
    # Aktif durumda olan ve bir task ile ilişkilendirilmiş issue'ları getir
    issues = GitHubIssue.objects.filter(
        (models.Q(updated_at__gte=one_hour_ago) | models.Q(status='open')) & 
        models.Q(task__isnull=False)
    ).select_related('repository', 'task')
    
    logger.info(f"Toplam {issues.count()} issue için yorum senkronizasyonu yapılacak")
    
    success_count = 0
    error_count = 0
    
    for issue in issues:
        try:
            if not issue.repository.github_profile:
                logger.warning(f"Issue #{issue.issue_number} için repository'nin GitHub profili yok")
                continue
                
            # Issue'ın yorumlarını senkronize et ve bildirim gönder
            new_comments = sync_issue_comments(issue, send_notifications=True)
            
            if new_comments > 0:
                logger.info(f"Issue #{issue.issue_number} için {new_comments} yeni yorum senkronize edildi")
            
            success_count += 1
        except Exception as e:
            logger.error(f"Issue #{issue.issue_number} yorumları senkronize edilirken hata oluştu: {str(e)}")
            error_count += 1
    
    logger.info(f"GitHub issue yorumları senkronizasyonu tamamlandı. Başarılı: {success_count}, Hatalı: {error_count}")
    return f"İşlenen issue sayısı: {issues.count()}, Başarılı: {success_count}, Hatalı: {error_count}"

# GitHub periyodik görevlerini tanımlamak için beat_schedule yapılandırmasını
# projenin Celery yapılandırmasında tanımlamak daha doğrudur.
# Bu tanımlamayı config/celery.py dosyasına taşımanız önerilir.
# Örnek:
#
# from celery.schedules import crontab
#
# beat_schedule = {
#     'sync-repositories': {
#         'task': 'github_integration.tasks.sync_all_repositories',
#         'schedule': crontab(minute=0, hour='*/3'),  # Her 3 saatte bir
#     },
#     'sync-issues': {
#         'task': 'github_integration.tasks.sync_all_issues',
#         'schedule': crontab(minute=30, hour='*/2'),  # Her 2 saatte bir, 30. dakikada
#     },
#     'sync-issue-comments': {
#         'task': 'github_integration.tasks.sync_recent_issue_comments',
#         'schedule': crontab(minute=0, hour='*'),  # Her saatte bir
#     },
# }
#
# app.conf.beat_schedule = beat_schedule 