from django import forms
from .models import PackageGroup, Package, ExtraService, PackageFeature


class PackageGroupForm(forms.ModelForm):
    class Meta:
        model = PackageGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PackageForm(forms.ModelForm):
    class Meta:
        model = Package
        fields = ['group', 'name', 'base_price', 'extra_pages_multiplier', 'is_active']
        widgets = {
            'group': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'extra_pages_multiplier': forms.NumberInput(attrs={
                'class': 'form-control', 
                'step': '0.01',
                'placeholder': '0.00 (opsiyonel)',
                'min': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ek sayfa katsayısını opsiyonel yap
        self.fields['extra_pages_multiplier'].required = False
        self.fields['extra_pages_multiplier'].help_text = "Web sitesi projeleri için her ek sayfa başına eklenecek fiyat"
        
        # Form etiketlerini özelleştir
        self.fields['group'].label = "Kategori"
        self.fields['name'].label = "Paket Adı"
        self.fields['base_price'].label = "Temel Fiyat (₺)"
        self.fields['extra_pages_multiplier'].label = "Ek Sayfa Katsayısı"
        self.fields['is_active'].label = "Aktif"


class ExtraServiceForm(forms.ModelForm):
    class Meta:
        model = ExtraService
        fields = [
            'group', 'name', 'description', 
            'pricing_type', 'price', 'percentage',
            'input_type', 'unit_label',
            'min_quantity', 'max_quantity', 'default_quantity',
            'options', 'is_required', 'is_active', 'order'
        ]
        widgets = {
            'group': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: SSL Sertifikası, Logo Tasarımı'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Hizmetin detaylı açıklaması'}),
            'pricing_type': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'input_type': forms.Select(attrs={'class': 'form-select'}),
            'unit_label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: sayfa, saat, gün'}),
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'default_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'options': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'JSON formatında seçenekler'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Form etiketlerini özelleştir
        self.fields['group'].label = "Kategori"
        self.fields['name'].label = "Hizmet Adı"
        self.fields['description'].label = "Açıklama"
        self.fields['pricing_type'].label = "Fiyatlandırma Türü"
        self.fields['price'].label = "Fiyat"
        self.fields['percentage'].label = "Yüzde (%)"
        self.fields['input_type'].label = "Giriş Türü"
        self.fields['unit_label'].label = "Birim Etiketi"
        self.fields['min_quantity'].label = "Minimum Miktar"
        self.fields['max_quantity'].label = "Maksimum Miktar"
        self.fields['default_quantity'].label = "Varsayılan Miktar"
        self.fields['options'].label = "Seçenekler (JSON)"
        self.fields['is_required'].label = "Zorunlu"
        self.fields['is_active'].label = "Aktif"
        self.fields['order'].label = "Sıra"
        
        # Help text'leri özelleştir
        self.fields['options'].help_text = "Açılır liste için: [{'value': 'basic', 'label': 'Temel', 'price': 100}, {'value': 'premium', 'label': 'Premium', 'price': 200}]"


class PackageFeatureForm(forms.ModelForm):
    class Meta:
        model = PackageFeature
        fields = ['package', 'text', 'order']
        widgets = {
            'package': forms.Select(attrs={'class': 'form-select'}),
            'text': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }


