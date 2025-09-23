from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class CalendarEvent(models.Model):
    """
    Takvim etkinlikleri için genel model.
    Farklı modellerden gelen etkinlikleri tek bir yerde toplar.
    """
    EVENT_TYPE_CHOICES = (
        ('task', _('Görev')),
        ('project', _('Proje')),
        ('payment', _('Ödeme')),
        ('deadline', _('Son Tarih')),
        ('meeting', _('Toplantı')),
        ('milestone', _('Kilometre Taşı')),
        ('custom', _('Özel Etkinlik')),
    )
    
    PRIORITY_CHOICES = (
        ('low', _('Düşük')),
        ('medium', _('Orta')),
        ('high', _('Yüksek')),
        ('urgent', _('Acil')),
    )
    
    # Temel bilgiler
    title = models.CharField(_('Başlık'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    event_type = models.CharField(_('Etkinlik Türü'), max_length=20, choices=EVENT_TYPE_CHOICES)
    priority = models.CharField(_('Öncelik'), max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Tarih bilgileri
    start_date = models.DateTimeField(_('Başlangıç Tarihi'))
    end_date = models.DateTimeField(_('Bitiş Tarihi'), null=True, blank=True)
    is_all_day = models.BooleanField(_('Tüm Gün'), default=False)
    
    # Renk ve görsel
    color = models.CharField(_('Renk'), max_length=7, default='#007bff', help_text=_('Hex renk kodu'))
    icon = models.CharField(_('İkon'), max_length=50, blank=True, help_text=_('Font Awesome ikon sınıfı'))
    
    # Kullanıcı ve yetki
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_events',
        verbose_name=_('Kullanıcı')
    )
    
    # Generic foreign key - farklı modellere referans
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Durum
    is_completed = models.BooleanField(_('Tamamlandı'), default=False)
    is_visible = models.BooleanField(_('Görünür'), default=True)
    
    # Oluşturma bilgileri
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Takvim Etkinliği')
        verbose_name_plural = _('Takvim Etkinlikleri')
        ordering = ['start_date', 'priority']
        indexes = [
            models.Index(fields=['user', 'start_date']),
            models.Index(fields=['event_type', 'start_date']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    @property
    def is_overdue(self):
        """Etkinliğin süresinin geçip geçmediğini kontrol eder."""
        from django.utils import timezone
        if self.end_date and not self.is_completed:
            return self.end_date < timezone.now()
        return False
    
    @property
    def duration_hours(self):
        """Etkinliğin süresini saat cinsinden döndürür."""
        if self.end_date and self.start_date:
            delta = self.end_date - self.start_date
            return delta.total_seconds() / 3600
        return None
    
    def get_absolute_url(self):
        """Etkinliğin detay sayfasına yönlendirme URL'si."""
        if self.content_object:
            # Generic foreign key varsa, o objenin URL'sini döndür
            if hasattr(self.content_object, 'get_absolute_url'):
                return self.content_object.get_absolute_url()
            else:
                # Model türüne göre URL oluştur
                if self.content_type.model == 'task':
                    from django.urls import reverse
                    return reverse('tasks:task_detail', kwargs={'task_id': self.object_id})
                elif self.content_type.model == 'project':
                    from django.urls import reverse
                    return reverse('projects:project_detail', kwargs={'project_id': self.object_id})
                elif self.content_type.model == 'paymentreceipt':
                    from django.urls import reverse
                    return reverse('sellers:sale_detail', kwargs={'pk': self.content_object.sale.id})
                elif self.content_type.model == 'projectsale':
                    from django.urls import reverse
                    return reverse('sellers:sale_detail', kwargs={'pk': self.object_id})
        return None


class CalendarSettings(models.Model):
    """
    Kullanıcı takvim ayarları.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_settings',
        verbose_name=_('Kullanıcı')
    )
    
    # Görünürlük ayarları
    show_tasks = models.BooleanField(_('Görevleri Göster'), default=True)
    show_projects = models.BooleanField(_('Projeleri Göster'), default=True)
    show_payments = models.BooleanField(_('Ödemeleri Göster'), default=False)
    show_deadlines = models.BooleanField(_('Son Tarihleri Göster'), default=True)
    show_meetings = models.BooleanField(_('Toplantıları Göster'), default=True)
    
    # Takvim görünümü
    default_view = models.CharField(
        _('Varsayılan Görünüm'),
        max_length=20,
        choices=[
            ('month', _('Aylık')),
            ('week', _('Haftalık')),
            ('day', _('Günlük')),
            ('agenda', _('Ajanda')),
        ],
        default='month'
    )
    
    # Renk ayarları
    task_color = models.CharField(_('Görev Rengi'), max_length=7, default='#28a745')
    project_color = models.CharField(_('Proje Rengi'), max_length=7, default='#007bff')
    payment_color = models.CharField(_('Ödeme Rengi'), max_length=7, default='#ffc107')
    deadline_color = models.CharField(_('Son Tarih Rengi'), max_length=7, default='#dc3545')
    meeting_color = models.CharField(_('Toplantı Rengi'), max_length=7, default='#6f42c1')
    
    # Bildirim ayarları
    email_notifications = models.BooleanField(_('E-posta Bildirimleri'), default=True)
    reminder_minutes = models.PositiveIntegerField(_('Hatırlatma Süresi (Dakika)'), default=15)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Takvim Ayarı')
        verbose_name_plural = _('Takvim Ayarları')
    
    def __str__(self):
        return f"{self.user.username} - Takvim Ayarları"
