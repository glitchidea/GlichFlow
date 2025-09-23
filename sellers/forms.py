from django import forms
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Row, Column, Submit, Div, HTML
from crispy_forms.bootstrap import FormActions

from .models import Customer, ProjectSale, ProjectFile, SaleExtraService, AdditionalCost, PaymentReceipt
from accounting.models import Package, ExtraService

User = get_user_model()


class CustomerForm(forms.ModelForm):
    """Müşteri formu"""
    
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'first_name', 'last_name', 'company_name', 
            'tax_number', 'email', 'phone', 'address', 'city', 'country', 'notes'
        ]
        widgets = {
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('customer_type', css_class='col-md-6'),
                Column(HTML('<div id="individual-fields">'), css_class='col-md-6'),
            ),
            Row(
                Column('first_name', css_class='col-md-6'),
                Column('last_name', css_class='col-md-6'),
                css_class='individual-fields'
            ),
            Row(
                Column('company_name', css_class='col-md-8'),
                Column('tax_number', css_class='col-md-4'),
                css_class='company-fields'
            ),
            Row(
                Column('email', css_class='col-md-6'),
                Column('phone', css_class='col-md-6'),
            ),
            Row(
                Column('address', css_class='col-md-12'),
            ),
            Row(
                Column('city', css_class='col-md-6'),
                Column('country', css_class='col-md-6'),
            ),
            Row(
                Column('notes', css_class='col-md-12'),
            ),
            FormActions(
                Submit('submit', 'Kaydet', css_class='btn btn-primary'),
                HTML('<a href="{% url "sellers:customer_list" %}" class="btn btn-secondary">İptal</a>')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        customer_type = cleaned_data.get('customer_type')
        
        if customer_type == 'individual':
            if not cleaned_data.get('first_name') or not cleaned_data.get('last_name'):
                raise forms.ValidationError('Bireysel müşteriler için ad ve soyad zorunludur.')
        
        if customer_type == 'company':
            if not cleaned_data.get('company_name'):
                raise forms.ValidationError('Şirket müşterileri için şirket adı zorunludur.')
        
        return cleaned_data


class ProjectSaleForm(forms.ModelForm):
    """Proje satış formu"""
    
    class Meta:
        model = ProjectSale
        fields = [
            'project_name', 'project_description', 'project_type', 'customer',
            'linked_project', 'base_package', 'base_price', 'estimated_duration_days',
            'quote_date', 'start_date', 'end_date', 'delivery_date', 'status'
        ]
        widgets = {
            'project_name': forms.TextInput(attrs={'class': 'form-control'}),
            'project_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'project_type': forms.TextInput(attrs={'class': 'form-control'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'linked_project': forms.Select(attrs={'class': 'form-select'}),
            'base_package': forms.Select(attrs={'class': 'form-select'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estimated_duration_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'quote_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'format': '%Y-%m-%d'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'format': '%Y-%m-%d'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'format': '%Y-%m-%d'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'format': '%Y-%m-%d'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Sadece kullanıcının müşterilerini göster
        if user:
            self.fields['customer'].queryset = Customer.objects.filter(created_by=user)
        
        # Tarih alanları için format ayarla
        date_fields = ['quote_date', 'start_date', 'end_date', 'delivery_date']
        for field_name in date_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.format = '%Y-%m-%d'
                self.fields[field_name].input_formats = ['%Y-%m-%d']
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('project_name', css_class='col-md-8'),
                Column('project_type', css_class='col-md-4'),
            ),
            Row(
                Column('project_description', css_class='col-md-12'),
            ),
            Row(
                Column('customer', css_class='col-md-6'),
                Column('linked_project', css_class='col-md-6'),
            ),
            Row(
                Column('base_package', css_class='col-md-6'),
                Column('base_price', css_class='col-md-6'),
            ),
            Row(
                Column('estimated_duration_days', css_class='col-md-4'),
                Column('quote_date', css_class='col-md-4'),
                Column('status', css_class='col-md-4'),
            ),
            Row(
                Column('start_date', css_class='col-md-4'),
                Column('end_date', css_class='col-md-4'),
                Column('delivery_date', css_class='col-md-4'),
            ),
            FormActions(
                Submit('submit', 'Kaydet', css_class='btn btn-primary'),
                HTML('<a href="{% url "sellers:sale_list" %}" class="btn btn-secondary">İptal</a>')
            )
        )


class ProjectFileForm(forms.ModelForm):
    """Proje dosya formu"""
    
    class Meta:
        model = ProjectFile
        fields = ['file_type', 'version_number', 'file', 'description']
        widgets = {
            'file_type': forms.Select(attrs={'class': 'form-select'}),
            'version_number': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={
                'class': 'form-control', 
                'accept': '.zip,.rar,.7z,.tar,.gz,.jpg,.jpeg,.png,.gif,.webp,.bmp,.svg,.mp4,.webm,.ogg,.mov,.mp3,.wav,.opus,.m4a,.aac,.flac,.txt,.log,.csv,.json,.md,.markdown,.docx,.pptx'
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Row(
                Column('file_type', css_class='col-md-6'),
                Column('version_number', css_class='col-md-6'),
            ),
            Row(
                Column('file', css_class='col-md-12'),
            ),
            Row(
                Column(HTML('''
                    <div class="alert alert-info" id="file-type-hint">
                        <small>
                            <strong>Desteklenen Dosya Türleri:</strong><br>
                            <span id="hint-content">
                                📁 Arşiv: ZIP, RAR, 7Z, TAR, GZ (her kategori için)<br>
                                📄 Diğer türler seçilen kategoriye göre değişir
                            </span><br>
                            <em>Maksimum dosya boyutu: 100MB</em>
                        </small>
                    </div>
                '''), css_class='col-md-12'),
            ),
            Row(
                Column('description', css_class='col-md-12'),
            ),
        )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        file_type = self.cleaned_data.get('file_type')
        
        if file:
            # Dosya boyutu kontrolü (100MB limit)
            if file.size > 100 * 1024 * 1024:
                raise forms.ValidationError('Dosya boyutu 100MB\'dan büyük olamaz.')
            
            # Dosya türü kontrolü - seçilen kategoriye göre
            allowed_extensions = self.get_allowed_extensions(file_type)
            
            if not any(file.name.lower().endswith(ext) for ext in allowed_extensions):
                file_type_name = self.get_file_type_display_name(file_type)
                raise forms.ValidationError(
                    f'Bu dosya türü "{file_type_name}" kategorisi için desteklenmiyor. '
                    f'Lütfen uygun bir dosya seçin.'
                )
        return file
    
    def get_allowed_extensions(self, file_type):
        """Dosya türüne göre izin verilen uzantıları döndür"""
        extensions_map = {
            'source_code': [
                # Arşiv dosyaları (her zaman desteklenir)
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Kaynak kod dosyaları
                '.py', '.js', '.html', '.css', '.php', '.java', '.cpp', '.c', '.h', '.hpp',
                '.cs', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.ts', '.tsx', '.jsx',
                '.vue', '.svelte', '.dart', '.r', '.m', '.pl', '.sh', '.bash', '.ps1',
                # Konfigürasyon dosyaları
                '.yml', '.yaml', '.json', '.xml', '.toml', '.ini', '.cfg', '.conf',
                '.env', '.gitignore', '.dockerfile', '.dockerignore', '.gitattributes',
                # Veritabanı dosyaları
                '.sql', '.sqlite', '.db', '.sqlite3',
                # Diğer
                '.md', '.txt', '.log', '.license', '.readme'
            ],
            'design': [
                # Arşiv dosyaları
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Tasarım dosyaları
                '.psd', '.ai', '.sketch', '.fig', '.xd', '.indd', '.eps', '.pdf',
                # Görsel dosyaları
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico',
                # Video dosyaları
                '.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv',
                # Diğer
                '.md', '.txt'
            ],
            'documentation': [
                # Arşiv dosyaları
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Dokümantasyon dosyaları
                '.md', '.markdown', '.txt', '.rtf', '.doc', '.docx', '.pdf',
                '.ppt', '.pptx', '.odt', '.ods', '.odp',
                # Görsel dosyaları (diagramlar için)
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
                # Diğer
                '.json', '.xml', '.yaml', '.yml'
            ],
            'database': [
                # Arşiv dosyaları
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Veritabanı dosyaları
                '.sql', '.sqlite', '.sqlite3', '.db', '.mdb', '.accdb',
                '.dump', '.backup', '.bak',
                # Konfigürasyon dosyaları
                '.yml', '.yaml', '.json', '.xml', '.ini', '.cfg', '.conf',
                # Diğer
                '.md', '.txt', '.log'
            ],
            'assets': [
                # Arşiv dosyaları
                '.zip', '.rar', '.7z', '.tar', '.gz',
                # Görsel dosyaları
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico', '.tiff', '.tif',
                # Video dosyaları
                '.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v',
                # Ses dosyaları
                '.mp3', '.wav', '.opus', '.m4a', '.aac', '.flac', '.ogg', '.wma',
                # Diğer medya
                '.gif', '.webp'
            ],
            'other': [
                # Tüm dosya türlerini destekle
                '.zip', '.rar', '.7z', '.tar', '.gz',
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
                '.mp4', '.webm', '.ogg', '.mov',
                '.mp3', '.wav', '.opus', '.m4a', '.aac', '.flac',
                '.txt', '.log', '.csv', '.json', '.md', '.markdown',
                '.docx', '.pptx', '.pdf', '.py', '.js', '.html', '.css',
                '.sql', '.sqlite', '.db', '.yml', '.yaml', '.env', '.gitignore'
            ]
        }
        
        return extensions_map.get(file_type, extensions_map['other'])
    
    def get_file_type_display_name(self, file_type):
        """Dosya türü için görüntüleme adını döndür"""
        display_names = {
            'source_code': 'Kaynak Kod',
            'design': 'Tasarım Dosyaları',
            'documentation': 'Dokümantasyon',
            'database': 'Veritabanı',
            'assets': 'Varlıklar',
            'other': 'Diğer'
        }
        return display_names.get(file_type, 'Bilinmeyen')


class SaleExtraServiceForm(forms.ModelForm):
    """Satış ek hizmet formu"""
    
    # Özel hizmet alanları
    custom_service_name = forms.CharField(
        max_length=200,
        required=False,
        label='Özel Hizmet Adı',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Özel hizmet adını yazın...'})
    )
    use_custom_service = forms.BooleanField(
        required=False,
        label='Özel hizmet kullan',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'use_custom_service'})
    )
    
    class Meta:
        model = SaleExtraService
        fields = ['extra_service', 'quantity', 'unit_price', 'is_approved', 'notes']
        widgets = {
            'extra_service': forms.Select(attrs={'class': 'form-select', 'id': 'id_extra_service'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('use_custom_service', css_class='col-md-12'),
            ),
            Row(
                Column('extra_service', css_class='col-md-6', css_id='extra_service_column'),
                Column('custom_service_name', css_class='col-md-6', css_id='custom_service_column'),
            ),
            Row(
                Column('quantity', css_class='col-md-3'),
                Column('unit_price', css_class='col-md-3'),
            ),
            Row(
                Column('is_approved', css_class='col-md-12'),
            ),
            Row(
                Column('notes', css_class='col-md-12'),
            ),
            FormActions(
                Submit('submit', 'Kaydet', css_class='btn btn-primary'),
                HTML('<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">İptal</button>')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        use_custom_service = cleaned_data.get('use_custom_service')
        extra_service = cleaned_data.get('extra_service')
        custom_service_name = cleaned_data.get('custom_service_name')
        
        if use_custom_service:
            if not custom_service_name:
                raise forms.ValidationError('Özel hizmet kullanıyorsanız hizmet adını girmelisiniz.')
            # Özel hizmet kullanılıyorsa extra_service'ı None yap
            cleaned_data['extra_service'] = None
        else:
            if not extra_service:
                raise forms.ValidationError('Mevcut hizmetlerden birini seçmelisiniz.')
            # Mevcut hizmet kullanılıyorsa custom_service_name'ı temizle
            cleaned_data['custom_service_name'] = None
        
        return cleaned_data


class AdditionalCostForm(forms.ModelForm):
    """Ek maliyet formu"""
    
    class Meta:
        model = AdditionalCost
        fields = ['cost_type', 'name', 'description', 'cost', 'is_customer_paid', 'is_approved', 'notes']
        widgets = {
            'cost_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_customer_paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('cost_type', css_class='col-md-6'),
                Column('name', css_class='col-md-6'),
            ),
            Row(
                Column('description', css_class='col-md-12'),
            ),
            Row(
                Column('cost', css_class='col-md-6'),
                Column(HTML('<div class="form-check mt-4">'), css_class='col-md-6'),
            ),
            Row(
                Column('is_customer_paid', css_class='col-md-6'),
                Column('is_approved', css_class='col-md-6'),
            ),
            Row(
                Column('notes', css_class='col-md-12'),
            ),
            FormActions(
                Submit('submit', 'Kaydet', css_class='btn btn-primary'),
                HTML('<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">İptal</button>')
            )
        )


class PriceCalculatorForm(forms.Form):
    """Fiyat hesaplayıcı formu"""
    
    base_package = forms.ModelChoiceField(
        queryset=Package.objects.all(),
        empty_label="Paket Seçin",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'base-package'})
    )
    
    extra_services = forms.ModelMultipleChoiceField(
        queryset=ExtraService.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    additional_costs = forms.DecimalField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'additional-costs'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('base_package', css_class='col-md-12'),
            ),
            Row(
                Column('extra_services', css_class='col-md-12'),
            ),
            Row(
                Column('additional_costs', css_class='col-md-12'),
            ),
            FormActions(
                Submit('calculate', 'Hesapla', css_class='btn btn-primary'),
                HTML('<button type="button" class="btn btn-secondary" onclick="resetCalculator()">Sıfırla</button>')
            )
        )


class PaymentReceiptForm(forms.ModelForm):
    """
    Ödeme makbuzu formu
    """
    class Meta:
        model = PaymentReceipt
        fields = [
            'payment_type', 'amount', 'payment_date', 'payment_method', 
            'status', 'receipt_file', 'receipt_number', 'description', 'notes'
        ]
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date',
                'format': '%Y-%m-%d'
            }),
            'payment_method': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Banka Havalesi, Kredi Kartı, Nakit vb.'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'receipt_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.gif,.webp,.bmp'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Otomatik oluşturulur'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ödeme açıklaması...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ek notlar...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tarih formatını ayarla
        if 'payment_date' in self.fields:
            self.fields['payment_date'].widget.format = '%Y-%m-%d'
            self.fields['payment_date'].input_formats = ['%Y-%m-%d']
        
        # Layout ayarla
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Row(
                Column('payment_type', css_class='col-md-6'),
                Column('amount', css_class='col-md-6'),
            ),
            Row(
                Column('payment_date', css_class='col-md-6'),
                Column('payment_method', css_class='col-md-6'),
            ),
            Row(
                Column('status', css_class='col-md-6'),
                Column('receipt_number', css_class='col-md-6'),
            ),
            Row(
                Column('receipt_file', css_class='col-md-12'),
            ),
            Row(
                Column('description', css_class='col-md-12'),
            ),
            Row(
                Column('notes', css_class='col-md-12'),
            ),
        )
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError('Ödeme tutarı 0\'dan büyük olmalıdır.')
        return amount
    
    def clean_receipt_file(self):
        receipt_file = self.cleaned_data.get('receipt_file')
        if receipt_file:
            # Dosya boyutu kontrolü (10MB limit)
            if receipt_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Makbuz dosyası 10MB\'dan büyük olamaz.')
            
            # Dosya türü kontrolü
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
            if not any(receipt_file.name.lower().endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError(
                    'Makbuz dosyası PDF, JPG, PNG formatında olmalıdır.'
                )
        return receipt_file
