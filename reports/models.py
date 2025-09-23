from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Report(models.Model):
    """
    Rapor modeli. Proje ve görev raporlarını temsil eder.
    """
    REPORT_TYPE_CHOICES = (
        ('project_progress', _('Proje İlerleme Raporu')),
        ('time_usage', _('Zaman Kullanım Raporu')),
        ('user_performance', _('Kullanıcı Performans Raporu')),
        ('workload', _('İş Yükü Analizi')),
        ('custom', _('Özel Rapor')),
    )
    
    title = models.CharField(_('Başlık'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    report_type = models.CharField(_('Rapor Tipi'), max_length=20, choices=REPORT_TYPE_CHOICES)
    
    # İlgili bağlantılar (opsiyonel)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='reports',
        verbose_name=_('Proje'),
        null=True,
        blank=True
    )
    
    # Raporun oluşturulduğu kullanıcı
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_reports',
        verbose_name=_('Oluşturan')
    )
    
    # Tarih aralığı
    date_from = models.DateField(_('Başlangıç Tarihi'), null=True, blank=True)
    date_to = models.DateField(_('Bitiş Tarihi'), null=True, blank=True)
    
    # Rapor verileri (JSON olarak saklanabilir)
    data = models.JSONField(_('Rapor Verileri'), default=dict, blank=True)
    
    # Rapor ayarları (JSON olarak saklanabilir)
    settings = models.JSONField(_('Rapor Ayarları'), default=dict, blank=True)
    
    # Planlama
    is_scheduled = models.BooleanField(_('Zamanlanmış'), default=False)
    schedule_interval = models.CharField(_('Zamanlama Aralığı'), max_length=50, blank=True)
    last_run = models.DateTimeField(_('Son Çalıştırma'), null=True, blank=True)
    next_run = models.DateTimeField(_('Sonraki Çalıştırma'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Rapor')
        verbose_name_plural = _('Raporlar')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def generate(self):
        """
        Raporu oluşturur ve verileri günceller.
        Bu metot, özel rapor oluşturma mantığı için bir kancadır.
        Alt sınıflar veya servisler tarafından uygulanabilir.
        """
        # Burada rapor oluşturma mantığı uygulanacak
        pass


class ReportSubscription(models.Model):
    """
    Rapor aboneliği modeli. Kullanıcıların raporlara abone olmasını sağlar.
    """
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name=_('Rapor')
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='report_subscriptions',
        verbose_name=_('Kullanıcı')
    )
    
    # Bildirim ayarları
    email_notification = models.BooleanField(_('E-posta Bildirimi'), default=True)
    system_notification = models.BooleanField(_('Sistem Bildirimi'), default=True)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Rapor Aboneliği')
        verbose_name_plural = _('Rapor Abonelikleri')
        unique_together = ('report', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.report.title}"
