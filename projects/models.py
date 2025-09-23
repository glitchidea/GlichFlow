from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Project(models.Model):
    """
    Proje modeli. Şirket/ekip projelerini temsil eder.
    """
    STATUS_CHOICES = (
        ('not_started', _('Başlamadı')),
        ('in_progress', _('Devam Ediyor')),
        ('on_hold', _('Beklemede')),
        ('completed', _('Tamamlandı')),
        ('cancelled', _('İptal Edildi')),
    )
    
    PRIORITY_CHOICES = (
        ('low', _('Düşük')),
        ('medium', _('Orta')),
        ('high', _('Yüksek')),
        ('urgent', _('Acil')),
    )
    
    name = models.CharField(_('Proje Adı'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    start_date = models.DateField(_('Başlangıç Tarihi'))
    end_date = models.DateField(_('Bitiş Tarihi'), null=True, blank=True)
    status = models.CharField(_('Durum'), max_length=20, choices=STATUS_CHOICES, default='not_started')
    priority = models.CharField(_('Öncelik'), max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        related_name='managed_projects',
        verbose_name=_('Proje Yöneticisi'),
        null=True,
        blank=True
    )
    
    team_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_projects',
        verbose_name=_('Takım Üyeleri'),
        blank=True
    )
    
    budget = models.DecimalField(_('Bütçe'), max_digits=10, decimal_places=2, null=True, blank=True)
    cost = models.DecimalField(_('Maliyet'), max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Proje')
        verbose_name_plural = _('Projeler')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def progress(self):
        """
        Projenin ilerleme durumunu hesaplar.
        """
        tasks = self.tasks.all()
        if not tasks:
            return 0
        
        completed_tasks = tasks.filter(status='completed').count()
        return int((completed_tasks / tasks.count()) * 100)
    
    @property
    def is_overdue(self):
        """
        Projenin son tarihinin geçip geçmediğini kontrol eder.
        """
        from django.utils import timezone
        if self.end_date and self.status != 'completed':
            return self.end_date < timezone.now().date()
        return False


class PRD(models.Model):
    """
    Product Requirements Document (Ürün Gereksinim Belgesi) modeli.
    Projelere ve görevlere atanabilir.
    """
    title = models.CharField(_('PRD Başlığı'), max_length=255)
    
    # Ürün Özeti
    product_summary = models.TextField(_('Ürün Özeti'), blank=True, 
                                     help_text=_('Ürünün genel açıklaması ve amacı'))
    
    # Hedef Kitle
    target_audience = models.TextField(_('Hedef Kitle'), blank=True,
                                     help_text=_('Ürünün hedef kullanıcıları ve kullanım senaryoları'))
    
    # Fonksiyonel Gereksinimler
    functional_requirements = models.TextField(_('Fonksiyonel Gereksinimler'), blank=True,
                                            help_text=_('Ürünün ne yapacağını açıklayan gereksinimler'))
    
    # Fonksiyonel Olmayan Gereksinimler
    non_functional_requirements = models.TextField(_('Fonksiyonel Olmayan Gereksinimler'), blank=True,
                                                 help_text=_('Performans, güvenlik, ölçeklenebilirlik gereksinimleri'))
    
    # Kullanıcı Hikayeleri
    user_stories = models.TextField(_('Kullanıcı Hikayeleri'), blank=True,
                                  help_text=_('User story formatında kullanıcı senaryoları'))
    
    # Kabul Kriterleri
    acceptance_criteria = models.TextField(_('Kabul Kriterleri'), blank=True,
                                         help_text=_('Her özellik için kabul kriterleri'))
    
    # Teknik Gereksinimler
    technical_requirements = models.TextField(_('Teknik Gereksinimler'), blank=True,
                                            help_text=_('Teknik altyapı ve teknoloji gereksinimleri'))
    
    # Tasarım Kısıtlamaları
    design_constraints = models.TextField(_('Tasarım Kısıtlamaları'), blank=True,
                                        help_text=_('UI/UX tasarım gereksinimleri ve kısıtlamaları'))
    
    # PRD dosyası (opsiyonel)
    document = models.FileField(
        _('PRD Dosyası'), 
        upload_to='prd_documents/',
        null=True, 
        blank=True
    )
    
    # PRD'nin atandığı proje (opsiyonel)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='prds',
        verbose_name=_('Proje'),
        null=True,
        blank=True
    )
    
    # PRD'nin atandığı görev (opsiyonel)
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='prds',
        verbose_name=_('Görev'),
        null=True,
        blank=True
    )
    
    # PRD'yi oluşturan kullanıcı
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_prds',
        verbose_name=_('Oluşturan')
    )
    
    # PRD'yi atayan kullanıcı
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='assigned_prds',
        verbose_name=_('Atayan'),
        null=True,
        blank=True
    )
    
    # PRD durumu
    STATUS_CHOICES = (
        ('draft', _('Taslak')),
        ('review', _('İncelemede')),
        ('approved', _('Onaylandı')),
        ('rejected', _('Reddedildi')),
        ('archived', _('Arşivlendi')),
    )
    
    status = models.CharField(
        _('Durum'), 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft'
    )
    
    # Tarih alanları
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    assigned_at = models.DateTimeField(_('Atanma Tarihi'), null=True, blank=True)
    reviewed_at = models.DateTimeField(_('İncelenme Tarihi'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('PRD')
        verbose_name_plural = _('PRD\'ler')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def clean(self):
        """
        PRD'nin ya bir projeye ya da bir göreve atanmış olması gerekir.
        """
        from django.core.exceptions import ValidationError
        if not self.project and not self.task:
            raise ValidationError(_('PRD bir projeye veya göreve atanmalıdır.'))
        if self.project and self.task:
            raise ValidationError(_('PRD aynı anda hem projeye hem de göreve atanamaz.'))
    
    @property
    def assigned_to(self):
        """
        PRD'nin atandığı proje veya görevi döndürür.
        """
        return self.project or self.task
    
    @property
    def assigned_to_type(self):
        """
        PRD'nin atandığı türü döndürür (project veya task).
        """
        if self.project:
            return 'project'
        elif self.task:
            return 'task'
        return None


class Attachment(models.Model):
    """
    Projelere ve görevlere eklenebilen dosya ekleri.
    """
    file = models.FileField(_('Dosya'), upload_to='attachments/')
    name = models.CharField(_('Dosya Adı'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_attachments',
        verbose_name=_('Yükleyen')
    )
    upload_date = models.DateTimeField(_('Yükleme Tarihi'), auto_now_add=True)
    
    # İlişkili proje (opsiyonel)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('Proje'),
        null=True,
        blank=True
    )
    
    # İlişkili görev (opsiyonel) - görev modeli oluşturulduktan sonra uncomment edilecek
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('Görev'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('Dosya Eki')
        verbose_name_plural = _('Dosya Ekleri')
        ordering = ['-upload_date']
    
    def __str__(self):
        return self.name
