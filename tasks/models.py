from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Task(models.Model):
    """
    Görev modeli. Projelere ait görevleri temsil eder.
    """
    STATUS_CHOICES = (
        ('todo', _('Yapılacak')),
        ('in_progress', _('Devam Ediyor')),
        ('review', _('İncelemede')),
        ('completed', _('Tamamlandı')),
        ('cancelled', _('İptal Edildi')),
    )
    
    PRIORITY_CHOICES = (
        ('low', _('Düşük')),
        ('medium', _('Orta')),
        ('high', _('Yüksek')),
        ('urgent', _('Acil')),
    )
    
    title = models.CharField(_('Başlık'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_('Proje')
    )
    
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='created_tasks',
        verbose_name=_('Oluşturan'),
        null=True
    )
    
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_tasks',
        verbose_name=_('Atanan Kişi'),
        null=True,
        blank=True
    )
    
    status = models.CharField(_('Durum'), max_length=20, choices=STATUS_CHOICES, default='todo')
    priority = models.CharField(_('Öncelik'), max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    estimate_hours = models.DecimalField(
        _('Tahmini Süre (Saat)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    actual_hours = models.DecimalField(
        _('Gerçekleşen Süre (Saat)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    start_date = models.DateField(_('Başlangıç Tarihi'), null=True, blank=True)
    due_date = models.DateField(_('Son Tarih'), null=True, blank=True)
    completed_date = models.DateField(_('Tamamlanma Tarihi'), null=True, blank=True)
    
    # Alt görevler için parent_task ilişkisi
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        related_name='subtasks',
        verbose_name=_('Üst Görev'),
        null=True,
        blank=True
    )
    
    # Görev bağımlılıkları - Bu görevi başlamadan önce tamamlanması gereken görevler
    dependencies = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='dependent_tasks',
        verbose_name=_('Bağımlılıklar'),
        blank=True
    )
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Görev')
        verbose_name_plural = _('Görevler')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def is_overdue(self):
        """
        Görevin son tarihinin geçip geçmediğini kontrol eder.
        """
        from django.utils import timezone
        if self.due_date and self.status not in ['completed', 'cancelled']:
            return self.due_date < timezone.now().date()
        return False


class TimeLog(models.Model):
    """
    Görevler için zaman kaydı. Kullanıcıların görevlere harcadıkları zamanı takip eder.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='time_logs',
        verbose_name=_('Görev')
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_logs',
        verbose_name=_('Kullanıcı')
    )
    
    date = models.DateField(_('Tarih'))
    hours = models.DecimalField(_('Saat'), max_digits=5, decimal_places=2)
    description = models.TextField(_('Açıklama'), blank=True)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Zaman Kaydı')
        verbose_name_plural = _('Zaman Kayıtları')
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.task.title} - {self.user.username} - {self.date}"


class Comment(models.Model):
    """
    Görev yorumları. Kullanıcılar görevler hakkında yorum yapabilir.
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Görev')
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_comments',
        verbose_name=_('Yazar')
    )
    
    content = models.TextField(_('İçerik'))
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Yorum')
        verbose_name_plural = _('Yorumlar')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.title} - {self.author.username}"
