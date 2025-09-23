from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from projects.models import Project
from tasks.models import Task

class GitHubProfile(models.Model):
    """
    Kullanıcının GitHub profil bilgilerini ve kimlik doğrulama verilerini tutar.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='github_profile',
        verbose_name=_('Kullanıcı')
    )
    github_username = models.CharField(
        max_length=100,
        verbose_name=_('GitHub Kullanıcı Adı')
    )
    access_token = models.CharField(
        max_length=255,
        verbose_name=_('Erişim Tokeni')
    )
    refresh_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Yenileme Tokeni')
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Token Son Geçerlilik Tarihi')
    )
    # Kullanıcının kendi GitHub uygulama bilgileri
    client_id = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name=_('Kişisel GitHub Client ID')
    )
    client_secret = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name=_('Kişisel GitHub Client Secret')
    )
    redirect_uri = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        verbose_name=_('Kişisel GitHub Redirect URI')
    )
    use_personal_oauth = models.BooleanField(
        default=False,
        verbose_name=_('Kişisel OAuth Kullan')
    )
    last_sync = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Son Senkronizasyon')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Oluşturulma Tarihi')
    )
    
    class Meta:
        verbose_name = _('GitHub Profili')
        verbose_name_plural = _('GitHub Profilleri')
    
    def __str__(self):
        return f"{self.user.username} - {self.github_username}"
    
    @property
    def is_token_valid(self):
        """Token hala geçerli mi kontrol eder."""
        if not self.token_expires_at:
            return True
        return timezone.now() < self.token_expires_at

class GitHubRepository(models.Model):
    """
    Proje ile ilişkilendirilmiş GitHub repository bilgilerini tutar.
    """
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='github_repository',
        verbose_name=_('Proje')
    )
    repository_owner = models.CharField(
        max_length=100,
        verbose_name=_('Repository Sahibi')
    )
    repository_name = models.CharField(
        max_length=100,
        verbose_name=_('Repository Adı')
    )
    repository_url = models.URLField(
        verbose_name=_('Repository URL')
    )
    is_private = models.BooleanField(
        default=False,
        verbose_name=_('Özel Repository')
    )
    default_branch = models.CharField(
        max_length=100,
        default='main',
        verbose_name=_('Varsayılan Branch')
    )
    last_synced = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Son Senkronizasyon')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Oluşturulma Tarihi')
    )
    
    class Meta:
        verbose_name = _('GitHub Repository')
        verbose_name_plural = _('GitHub Repositories')
        unique_together = ('repository_owner', 'repository_name')
    
    def __str__(self):
        return f"{self.repository_owner}/{self.repository_name}"
    
    @property
    def full_name(self):
        return f"{self.repository_owner}/{self.repository_name}"

class GitHubIssue(models.Model):
    """
    GitHub repository'den içe aktarılan veya senkronize edilen issue'ları tutar.
    """
    STATUS_CHOICES = (
        ('open', _('Açık')),
        ('closed', _('Kapalı')),
    )
    
    repository = models.ForeignKey(
        GitHubRepository,
        on_delete=models.CASCADE,
        related_name='issues',
        verbose_name=_('Repository')
    )
    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='github_issue',
        null=True,
        blank=True,
        verbose_name=_('İlişkili Görev')
    )
    issue_number = models.PositiveIntegerField(
        verbose_name=_('Issue Numarası')
    )
    issue_title = models.CharField(
        max_length=255,
        verbose_name=_('Başlık')
    )
    issue_body = models.TextField(
        blank=True,
        verbose_name=_('İçerik')
    )
    issue_url = models.URLField(
        verbose_name=_('Issue URL')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name=_('Durum')
    )
    github_created_at = models.DateTimeField(
        verbose_name=_('GitHub Oluşturulma Tarihi')
    )
    github_updated_at = models.DateTimeField(
        verbose_name=_('GitHub Güncellenme Tarihi')
    )
    last_synced = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Son Senkronizasyon')
    )
    
    class Meta:
        verbose_name = _('GitHub Issue')
        verbose_name_plural = _('GitHub Issues')
        unique_together = ('repository', 'issue_number')
    
    def __str__(self):
        return f"{self.repository} - #{self.issue_number}: {self.issue_title}"

class SyncLog(models.Model):
    """
    GitHub senkronizasyon işlemlerinin kayıtlarını tutar.
    """
    ACTION_CHOICES = (
        ('create_repo', _('Repository Oluşturma')),
        ('sync_repo', _('Repository Senkronizasyon')),
        ('create_issue', _('Issue Oluşturma')),
        ('update_issue', _('Issue Güncelleme')),
        ('close_issue', _('Issue Kapatma')),
        ('import_issues', _('Issue İçe Aktarma')),
    )
    
    STATUS_CHOICES = (
        ('success', _('Başarılı')),
        ('failed', _('Başarısız')),
        ('pending', _('Beklemede')),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='github_sync_logs',
        verbose_name=_('Kullanıcı')
    )
    repository = models.ForeignKey(
        GitHubRepository,
        on_delete=models.CASCADE,
        related_name='sync_logs',
        verbose_name=_('Repository')
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name=_('İşlem')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_('Durum')
    )
    message = models.TextField(
        blank=True,
        verbose_name=_('Mesaj')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Oluşturulma Tarihi')
    )
    
    class Meta:
        verbose_name = _('Senkronizasyon Kaydı')
        verbose_name_plural = _('Senkronizasyon Kayıtları')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.get_status_display()} - {self.created_at}"

class GitHubIssueComment(models.Model):
    """
    GitHub issue yorumlarını ve ilişkili mesajları takip eden model.
    """
    github_issue = models.ForeignKey(
        GitHubIssue,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('GitHub Issue')
    )
    comment_id = models.PositiveIntegerField(
        verbose_name=_('Yorum ID')
    )
    user_login = models.CharField(
        max_length=100,
        verbose_name=_('GitHub Kullanıcı Adı')
    )
    user_avatar = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Kullanıcı Avatar URL')
    )
    body = models.TextField(
        verbose_name=_('Yorum İçeriği')
    )
    html_url = models.URLField(
        max_length=255,
        verbose_name=_('Yorum URL')
    )
    github_created_at = models.DateTimeField(
        verbose_name=_('GitHub Oluşturulma Tarihi')
    )
    github_updated_at = models.DateTimeField(
        verbose_name=_('GitHub Güncellenme Tarihi')
    )
    
    # İlişkili sistem mesajı
    system_message = models.ForeignKey(
        'communications.Message',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='github_comment',
        verbose_name=_('Sistem Mesajı')
    )
    
    last_synced = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Son Senkronizasyon')
    )
    
    class Meta:
        verbose_name = _('GitHub Issue Yorumu')
        verbose_name_plural = _('GitHub Issue Yorumları')
        unique_together = ('github_issue', 'comment_id')
        ordering = ['github_created_at']
    
    def __str__(self):
        return f"{self.github_issue} - Yorum #{self.comment_id}"
