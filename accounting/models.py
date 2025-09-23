from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


class PackageGroup(models.Model):
    """
    Üst seviye paket grubu: Örn: WordPress, Server, Açık Kaynak, SaaS vb.
    """
    name = models.CharField(_('Grup Adı'), max_length=100, unique=True)
    description = models.TextField(_('Açıklama'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_package_groups'
    )

    class Meta:
        verbose_name = _('Paket Grubu')
        verbose_name_plural = _('Paket Grupları')
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Package(models.Model):
    """
    Bir gruba ait fiyatlandırılabilir paket. Örn: Temel, Orta, Büyük vb.
    """
    group = models.ForeignKey(PackageGroup, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(_('Paket Adı'), max_length=100)
    base_price = models.DecimalField(_('Temel Fiyat'), max_digits=12, decimal_places=2)
    extra_pages_multiplier = models.DecimalField(_('Ek Sayfa Katsayısı'), max_digits=6, decimal_places=2, default=0)
    is_active = models.BooleanField(_('Aktif'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_packages'
    )

    class Meta:
        verbose_name = _('Paket')
        verbose_name_plural = _('Paketler')
        unique_together = ('group', 'name')
        ordering = ['group__name', 'name']

    def __str__(self) -> str:
        return f"{self.group.name} - {self.name}"


class ExtraService(models.Model):
    """
    Tamamen modüler ek hizmet sistemi - kullanıcılar kendi hizmetlerini özelleştirebilir
    """
    PRICING_TYPE_CHOICES = (
        ('fixed', _('Sabit Fiyat')),
        ('percentage', _('Yüzde (%)')),
        ('per_unit', _('Birim Başına')),
        ('per_page', _('Sayfa Başına')),
        ('per_hour', _('Saat Başına')),
        ('per_day', _('Gün Başına')),
        ('per_month', _('Aylık')),
        ('per_year', _('Yıllık')),
    )
    
    INPUT_TYPE_CHOICES = (
        ('checkbox', _('Seçmeli (On/Off)')),
        ('radio', _('Tek Seçim')),
        ('number', _('Sayı Girişi')),
        ('select', _('Açılır Liste')),
    )
    
    group = models.ForeignKey(PackageGroup, on_delete=models.CASCADE, related_name='extra_services')
    
    # Temel Bilgiler
    name = models.CharField(_('Hizmet Adı'), max_length=100, help_text=_('Örn: SSL Sertifikası, Logo Tasarımı, API Entegrasyonu'))
    description = models.TextField(_('Açıklama'), blank=True, help_text=_('Hizmetin detaylı açıklaması'))
    
    # Fiyatlandırma
    pricing_type = models.CharField(_('Fiyatlandırma Türü'), max_length=20, choices=PRICING_TYPE_CHOICES, default='fixed')
    price = models.DecimalField(_('Fiyat'), max_digits=12, decimal_places=2, default=0, help_text=_('Sabit fiyat veya birim fiyatı'))
    percentage = models.DecimalField(_('Yüzde (%)'), max_digits=5, decimal_places=2, default=0, help_text=_('Paket fiyatının yüzdesi (örn: 15.00 = %15)'))
    
    # Giriş Türü
    input_type = models.CharField(_('Giriş Türü'), max_length=20, choices=INPUT_TYPE_CHOICES, default='checkbox')
    
    # Birim ve Miktar Ayarları
    unit_label = models.CharField(_('Birim Etiketi'), max_length=50, blank=True, help_text=_('Örn: sayfa, saat, gün, ay, yıl'))
    min_quantity = models.PositiveIntegerField(_('Minimum Miktar'), default=1)
    max_quantity = models.PositiveIntegerField(_('Maksimum Miktar'), default=100)
    default_quantity = models.PositiveIntegerField(_('Varsayılan Miktar'), default=1)
    
    # Seçenekler (Select türü için)
    options = models.JSONField(_('Seçenekler'), default=list, blank=True, help_text=_('Açılır liste için seçenekler: [{"value": "basic", "label": "Temel", "price": 100}]'))
    
    # Durum ve Sıralama
    is_required = models.BooleanField(_('Zorunlu'), default=False, help_text=_('Bu hizmet zorunlu mu?'))
    is_active = models.BooleanField(_('Aktif'), default=True)
    order = models.PositiveIntegerField(_('Sıra'), default=0)
    
    # Oluşturma Bilgileri
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_extra_services'
    )

    class Meta:
        verbose_name = _('Ek Hizmet')
        verbose_name_plural = _('Ek Hizmetler')
        ordering = ['group__name', 'order', 'name']

    def __str__(self) -> str:
        return f"{self.group.name} - {self.name}"

    def get_display_price(self):
        """Fiyatlandırma türüne göre görüntüleme fiyatını döndürür"""
        if self.pricing_type == 'fixed':
            return f"{self.price} ₺"
        elif self.pricing_type == 'percentage':
            return f"%{self.percentage}"
        elif self.pricing_type == 'per_unit':
            return f"{self.price} ₺/{self.unit_label or 'birim'}"
        elif self.pricing_type == 'per_page':
            return f"{self.price} ₺/sayfa"
        elif self.pricing_type == 'per_hour':
            return f"{self.price} ₺/saat"
        elif self.pricing_type == 'per_day':
            return f"{self.price} ₺/gün"
        elif self.pricing_type == 'per_month':
            return f"{self.price} ₺/ay"
        elif self.pricing_type == 'per_year':
            return f"{self.price} ₺/yıl"
        return f"{self.price} ₺"

    def calculate_price(self, base_price=0, quantity=1):
        """Verilen parametrelere göre fiyat hesaplar"""
        if self.pricing_type == 'fixed':
            return self.price
        elif self.pricing_type == 'percentage':
            return (base_price * self.percentage / 100) * quantity
        elif self.pricing_type in ['per_unit', 'per_page', 'per_hour', 'per_day', 'per_month', 'per_year']:
            return self.price * quantity
        return 0


class PackageFeature(models.Model):
    """
    Paketlere ait madde madde özellikler.
    """
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='features')
    text = models.CharField(_('Özellik'), max_length=255)
    order = models.PositiveIntegerField(_('Sıra'), default=0)

    class Meta:
        verbose_name = _('Paket Özelliği')
        verbose_name_plural = _('Paket Özellikleri')
        ordering = ['package', 'order', 'id']

    def __str__(self) -> str:
        return f"{self.package}: {self.text}"


