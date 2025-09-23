from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
import os


def project_file_upload_path(instance, filename):
    """
    Dinamik dosya yükleme yolu: müşteri/proje/dosya
    Örnek: ali/saas/sql.zip veya sabancı/saas/sql.zip
    """
    # Müşteri adını temizle (özel karakterleri kaldır)
    customer_name = instance.sale.customer.display_name
    # Özel karakterleri kaldır ve boşlukları alt çizgi ile değiştir
    customer_name = "".join(c for c in customer_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    customer_name = customer_name.replace(' ', '_')
    
    # Proje adını temizle
    project_name = instance.sale.project_name
    project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    project_name = project_name.replace(' ', '_')
    
    # Dosya adını temizle
    filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).rstrip()
    
    # Yolu oluştur: seller/müşteri/proje/dosya
    return os.path.join('seller', customer_name, project_name, filename)


class Customer(models.Model):
    """
    Müşteri modeli - Bireysel ve şirket müşterilerini destekler
    """
    CUSTOMER_TYPE_CHOICES = (
        ('individual', 'Bireysel'),
        ('company', 'Şirket'),
    )
    
    # Temel Bilgiler
    customer_type = models.CharField(
        _('Müşteri Türü'), 
        max_length=20, 
        choices=CUSTOMER_TYPE_CHOICES,
        default='individual'
    )
    
    # Bireysel Müşteri Bilgileri
    first_name = models.CharField(_('Ad'), max_length=100, blank=True)
    last_name = models.CharField(_('Soyad'), max_length=100, blank=True)
    
    # Şirket Bilgileri
    company_name = models.CharField(_('Şirket Adı'), max_length=255, blank=True)
    tax_number = models.CharField(_('Vergi Numarası'), max_length=20, blank=True)
    
    # İletişim Bilgileri
    email = models.EmailField(_('E-posta'))
    phone = models.CharField(_('Telefon'), max_length=20, blank=True)
    address = models.TextField(_('Adres'), blank=True)
    city = models.CharField(_('Şehir'), max_length=100, blank=True)
    country = models.CharField(_('Ülke'), max_length=100, default='Türkiye')
    
    # Ek Bilgiler
    notes = models.TextField(_('Notlar'), blank=True)
    is_active = models.BooleanField(_('Aktif'), default=True)
    
    # İlişkiler
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_customers',
        verbose_name=_('Oluşturan')
    )
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Müşteri')
        verbose_name_plural = _('Müşteriler')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.display_name
    
    @property
    def display_name(self):
        """Müşterinin görüntüleme adını döndürür"""
        if self.customer_type == 'company':
            return self.company_name or f"Şirket - {self.email}"
        return f"{self.first_name} {self.last_name}".strip() or f"Bireysel - {self.email}"
    
    @property
    def total_projects(self):
        """Toplam proje sayısını döndürür"""
        return self.projects.count()
    
    @property
    def total_revenue(self):
        """Toplam geliri döndürür"""
        from django.db.models import Sum
        result = self.projects.aggregate(total=Sum('final_price'))
        return result['total'] or 0
    
    def clean(self):
        """Model validasyonu"""
        from django.core.exceptions import ValidationError
        
        # Bireysel müşteri için ad ve soyad zorunlu
        if self.customer_type == 'individual':
            if not self.first_name or not self.last_name:
                raise ValidationError(_('Bireysel müşteriler için ad ve soyad zorunludur.'))
        
        # Şirket müşterisi için şirket adı zorunlu
        if self.customer_type == 'company':
            if not self.company_name:
                raise ValidationError(_('Şirket müşterileri için şirket adı zorunludur.'))


class ProjectSale(models.Model):
    """
    Proje satış modeli - Müşteri projelerini ve fiyatlandırmalarını yönetir
    """
    STATUS_CHOICES = (
        ('draft', 'Taslak'),
        ('quoted', 'Teklif Verildi'),
        ('in_progress', 'Yapım Aşamasında'),
        ('completed', 'Tamamlandı'),
        ('cancelled', 'İptal Edildi'),
    )
    
    # Temel Bilgiler
    project_name = models.CharField(_('Proje Adı'), max_length=255)
    project_description = models.TextField(_('Proje Açıklaması'))
    project_type = models.CharField(
        _('Proje Türü'), 
        max_length=100,
        help_text=_('Örn: Web Site, SaaS, Mobil Uygulama, E-ticaret')
    )
    
    # Müşteri İlişkisi
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='projects',
        verbose_name=_('Müşteri')
    )
    
    # Proje Bağlantısı (Mevcut Project modeli ile)
    linked_project = models.ForeignKey(
        'projects.Project', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sales',
        verbose_name=_('Bağlı Proje')
    )
    
    # Fiyatlandırma
    base_package = models.ForeignKey(
        'accounting.Package', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_('Temel Paket')
    )
    base_price = models.DecimalField(
        _('Temel Fiyat'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    extra_services_total = models.DecimalField(
        _('Ek Hizmetler Toplamı'), 
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    additional_costs_total = models.DecimalField(
        _('Ek Maliyetler Toplamı'), 
        max_digits=12, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Domain, hosting, SSL vb. ek maliyetler')
    )
    final_price = models.DecimalField(
        _('Final Fiyat'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    # Süre Bilgileri
    estimated_duration_days = models.PositiveIntegerField(
        _('Tahmini Süre (Gün)'), 
        null=True, 
        blank=True,
        help_text=_('Projenin tahmini tamamlanma süresi')
    )
    actual_duration_days = models.PositiveIntegerField(
        _('Gerçek Süre (Gün)'), 
        null=True, 
        blank=True,
        help_text=_('Projenin gerçek tamamlanma süresi')
    )
    
    # Tarihler
    quote_date = models.DateField(_('Teklif Tarihi'), null=True, blank=True)
    start_date = models.DateField(_('Başlangıç Tarihi'), null=True, blank=True)
    end_date = models.DateField(_('Bitiş Tarihi'), null=True, blank=True)
    delivery_date = models.DateField(_('Teslim Tarihi'), null=True, blank=True)
    
    # Durum
    status = models.CharField(
        _('Durum'), 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft'
    )
    
    # İlişkiler
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sales',
        verbose_name=_('Satış Temsilcisi')
    )
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Proje Satışı')
        verbose_name_plural = _('Proje Satışları')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project_name} - {self.customer.display_name}"
    
    def calculate_actual_duration(self):
        """Gerçek süreyi hesaplar"""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.actual_duration_days = delta.days
            self.save()
    
    def get_project_files(self):
        """Aktif proje dosyalarını döndürür"""
        return self.project_files.filter(is_active=True).order_by('-version_number')
    
    def calculate_final_price(self):
        """Final fiyatı hesaplar"""
        return self.base_price + self.extra_services_total + self.additional_costs_total
    
    def save(self, *args, **kwargs):
        """Kaydetmeden önce final fiyatı ve gerçek süreyi hesapla"""
        self.final_price = self.calculate_final_price()
        # Gerçek süreyi hesapla
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.actual_duration_days = delta.days
        super().save(*args, **kwargs)


class ProjectFile(models.Model):
    """
    Proje dosya modeli - Versiyonlama ile dosya yönetimi
    """
    FILE_TYPE_CHOICES = (
        ('source_code', 'Kaynak Kod'),
        ('design', 'Tasarım Dosyaları'),
        ('documentation', 'Dokümantasyon'),
        ('database', 'Veritabanı'),
        ('assets', 'Varlıklar (Görsel, Video vb.)'),
        ('other', 'Diğer'),
    )
    
    sale = models.ForeignKey(
        ProjectSale, 
        on_delete=models.CASCADE, 
        related_name='project_files',
        verbose_name=_('Proje Satışı')
    )
    file_type = models.CharField(
        _('Dosya Türü'), 
        max_length=20, 
        choices=FILE_TYPE_CHOICES,
        default='source_code'
    )
    version_number = models.CharField(
        _('Versiyon'), 
        max_length=20, 
        default='v1',
        help_text=_('v1, v2, v3 vb.')
    )
    file = models.FileField(
        _('Dosya'), 
        upload_to=project_file_upload_path,
        help_text=_('ZIP, RAR veya diğer arşiv dosyaları')
    )
    file_name = models.CharField(_('Dosya Adı'), max_length=255)
    file_size = models.BigIntegerField(_('Dosya Boyutu (Bytes)'), default=0)
    description = models.TextField(_('Açıklama'), blank=True)
    
    # Metadata
    is_active = models.BooleanField(_('Aktif'), default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        verbose_name=_('Yükleyen')
    )
    uploaded_at = models.DateTimeField(_('Yükleme Tarihi'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Proje Dosyası')
        verbose_name_plural = _('Proje Dosyaları')
        ordering = ['-uploaded_at']
        unique_together = ['sale', 'version_number', 'file_type']
    
    def __str__(self):
        return f"{self.sale.project_name} - {self.version_number} ({self.file_type})"
    
    def save(self, *args, **kwargs):
        """Dosya boyutunu hesapla ve dosya adını otomatik doldur"""
        if self.file:
            self.file_size = self.file.size
            # Dosya adını otomatik olarak doldur
            if not self.file_name:
                self.file_name = self.file.name.split('/')[-1]  # Sadece dosya adını al
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Model silinirken fiziksel dosyayı da depolamadan kaldır."""
        stored_file = self.file
        super().delete(using=using, keep_parents=keep_parents)
        # Model silindikten sonra dosyayı depolamadan sil
        if stored_file:
            try:
                stored_file.delete(save=False)
            except Exception:
                pass
    
    def get_file_size_display(self):
        """Dosya boyutunu okunabilir formatta döndürür"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class SaleExtraService(models.Model):
    """
    Satış ek hizmet modeli - Ek hizmetleri ve onay durumlarını yönetir
    """
    sale = models.ForeignKey(
        ProjectSale, 
        on_delete=models.CASCADE, 
        related_name='extra_services',
        verbose_name=_('Proje Satışı')
    )
    extra_service = models.ForeignKey(
        'accounting.ExtraService', 
        on_delete=models.CASCADE,
        verbose_name=_('Ek Hizmet'),
        null=True,
        blank=True
    )
    custom_service_name = models.CharField(
        _('Özel Hizmet Adı'),
        max_length=200,
        blank=True,
        help_text=_('Mevcut hizmetler dışında özel hizmet adı')
    )
    quantity = models.PositiveIntegerField(_('Miktar'), default=1)
    unit_price = models.DecimalField(
        _('Birim Fiyat'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    total_price = models.DecimalField(
        _('Toplam Fiyat'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_approved = models.BooleanField(_('Onaylandı'), default=False)
    notes = models.TextField(_('Notlar'), blank=True)
    
    class Meta:
        verbose_name = _('Satış Ek Hizmeti')
        verbose_name_plural = _('Satış Ek Hizmetleri')
        # unique_together kaldırıldı çünkü custom_service_name ile çakışabilir
    
    def __str__(self):
        service_name = self.get_service_name()
        return f"{self.sale.project_name} - {service_name}"
    
    def get_service_name(self):
        """Hizmet adını döndür - mevcut hizmet veya özel hizmet"""
        if self.extra_service:
            return self.extra_service.name
        elif self.custom_service_name:
            return self.custom_service_name
        return "Bilinmeyen Hizmet"
    
    def save(self, *args, **kwargs):
        """Toplam fiyatı hesapla ve proje satışının toplam ek hizmet fiyatını güncelle"""
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        # Proje satışının toplam ek hizmet fiyatını güncelle
        from django.db.models import Sum
        self.sale.extra_services_total = self.sale.extra_services.aggregate(total=Sum('total_price'))['total'] or 0
        self.sale.save()
    
    def delete(self, *args, **kwargs):
        """Silmeden önce proje satışının toplam ek hizmet fiyatını güncelle"""
        sale = self.sale
        super().delete(*args, **kwargs)
        # Proje satışının toplam ek hizmet fiyatını güncelle
        from django.db.models import Sum
        sale.extra_services_total = sale.extra_services.aggregate(total=Sum('total_price'))['total'] or 0
        sale.save()


class AdditionalCost(models.Model):
    """
    Ek maliyet modeli - Domain, hosting, SSL vb. ek maliyetleri yönetir
    """
    COST_TYPE_CHOICES = (
        ('domain', 'Domain'),
        ('hosting', 'Hosting'),
        ('ssl', 'SSL Sertifikası'),
        ('software', 'Yazılım Lisansı'),
        ('third_party', '3. Parti Hizmet'),
        ('hardware', 'Donanım'),
        ('other', 'Diğer'),
    )
    
    sale = models.ForeignKey(
        ProjectSale, 
        on_delete=models.CASCADE, 
        related_name='additional_costs',
        verbose_name=_('Proje Satışı')
    )
    cost_type = models.CharField(
        _('Maliyet Türü'), 
        max_length=20, 
        choices=COST_TYPE_CHOICES,
        default='other'
    )
    name = models.CharField(_('Maliyet Adı'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    cost = models.DecimalField(
        _('Maliyet'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_customer_paid = models.BooleanField(
        _('Müşteri Ödeyecek'), 
        default=False,
        help_text=_('Bu maliyet müşteri tarafından ödenecek mi?')
    )
    is_approved = models.BooleanField(_('Onaylandı'), default=False)
    notes = models.TextField(_('Notlar'), blank=True)
    
    class Meta:
        verbose_name = _('Ek Maliyet')
        verbose_name_plural = _('Ek Maliyetler')
        ordering = ['cost_type', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.cost} ₺"
    
    def save(self, *args, **kwargs):
        """Kaydetmeden önce proje satışının toplam maliyetini güncelle"""
        super().save(*args, **kwargs)
        # Proje satışının toplam maliyetini güncelle
        from django.db.models import Sum
        self.sale.additional_costs_total = self.sale.additional_costs.aggregate(total=Sum('cost'))['total'] or 0
        self.sale.save()
    
    def delete(self, *args, **kwargs):
        """Silmeden önce proje satışının toplam maliyetini güncelle"""
        sale = self.sale
        super().delete(*args, **kwargs)
        # Proje satışının toplam maliyetini güncelle
        from django.db.models import Sum
        sale.additional_costs_total = sale.additional_costs.aggregate(total=Sum('cost'))['total'] or 0
        sale.save()


def payment_receipt_upload_path(instance, filename):
    """
    Ödeme makbuzu yükleme yolu: müşteri/proje/payments/makbuz
    """
    # Müşteri adını temizle
    customer_name = instance.sale.customer.display_name
    customer_name = "".join(c for c in customer_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    customer_name = customer_name.replace(' ', '_')
    
    # Proje adını temizle
    project_name = instance.sale.project_name
    project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    project_name = project_name.replace(' ', '_')
    
    # Dosya adını temizle
    filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).rstrip()
    
    # Yolu oluştur: seller/müşteri/proje/payments/makbuz
    return os.path.join('seller', customer_name, project_name, 'payments', filename)


class PaymentReceipt(models.Model):
    """
    Ödeme makbuzu modeli - Proje ödemelerini ve makbuzlarını yönetir
    """
    PAYMENT_TYPE_CHOICES = (
        ('advance', 'Avans Ödeme'),
        ('milestone', 'Aşama Ödemesi'),
        ('final', 'Final Ödeme'),
        ('partial', 'Kısmi Ödeme'),
        ('refund', 'İade'),
        ('other', 'Diğer'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Beklemede'),
        ('completed', 'Tamamlandı'),
        ('failed', 'Başarısız'),
        ('cancelled', 'İptal Edildi'),
    )
    
    sale = models.ForeignKey(
        ProjectSale, 
        on_delete=models.CASCADE, 
        related_name='payment_receipts',
        verbose_name=_('Proje Satışı')
    )
    
    # Ödeme Bilgileri
    payment_type = models.CharField(
        _('Ödeme Türü'), 
        max_length=20, 
        choices=PAYMENT_TYPE_CHOICES,
        default='partial'
    )
    amount = models.DecimalField(
        _('Ödeme Tutarı'), 
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_date = models.DateField(_('Ödeme Tarihi'))
    payment_method = models.CharField(
        _('Ödeme Yöntemi'), 
        max_length=100,
        help_text=_('Banka Havalesi, Kredi Kartı, Nakit vb.')
    )
    status = models.CharField(
        _('Durum'), 
        max_length=20, 
        choices=PAYMENT_STATUS_CHOICES,
        default='completed'
    )
    
    # Makbuz Bilgileri
    receipt_file = models.FileField(
        _('Makbuz Dosyası'), 
        upload_to=payment_receipt_upload_path,
        help_text=_('PDF, JPG, PNG formatında makbuz')
    )
    receipt_number = models.CharField(
        _('Makbuz Numarası'), 
        max_length=100,
        blank=True,
        help_text=_('Makbuz üzerindeki numara')
    )
    
    # Ek Bilgiler
    description = models.TextField(_('Açıklama'), blank=True)
    notes = models.TextField(_('Notlar'), blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        verbose_name=_('Ekleyen')
    )
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Ödeme Makbuzu')
        verbose_name_plural = _('Ödeme Makbuzları')
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.sale.project_name} - {self.payment_type} - {self.amount} ₺"
    
    def save(self, *args, **kwargs):
        """Kaydetmeden önce makbuz numarasını otomatik oluştur"""
        if not self.receipt_number:
            # Makbuz numarası otomatik oluştur: PRJ-YYYY-MM-DD-XXX
            from datetime import datetime
            date_str = self.payment_date.strftime('%Y%m%d')
            project_count = PaymentReceipt.objects.filter(
                sale=self.sale, 
                payment_date=self.payment_date
            ).count() + 1
            self.receipt_number = f"PRJ-{date_str}-{project_count:03d}"
        super().save(*args, **kwargs)
    
    def delete(self, using=None, keep_parents=False):
        """Model silinirken fiziksel dosyayı da depolamadan kaldır."""
        stored_file = self.receipt_file
        super().delete(using=using, keep_parents=keep_parents)
        # Model silindikten sonra dosyayı depolamadan sil
        if stored_file:
            try:
                stored_file.delete(save=False)
            except Exception:
                pass
    
    @property
    def total_paid_amount(self):
        """Bu proje için toplam ödenen tutarı döndürür"""
        from django.db.models import Sum
        result = self.sale.payment_receipts.filter(status='completed').aggregate(total=Sum('amount'))
        return result['total'] or 0
    
    @property
    def remaining_amount(self):
        """Kalan ödeme tutarını döndürür"""
        return self.sale.final_price - self.total_paid_amount