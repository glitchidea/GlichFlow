from django import forms
from .models import OllamaSettings

class OllamaSettingsForm(forms.ModelForm):
    """Ollama API ayarları için form"""
    
    class Meta:
        model = OllamaSettings
        fields = ['api_url', 'default_model', 'default_language', 'is_active']
        widgets = {
            'api_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'http://192.168.1.100:11434',
                'help_text': 'Ollama server\'ınızın IP adresi ve portu'
            }),
            'default_model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'gemma3:4b',
                'list': 'available-models'
            }),
            'default_language': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'api_url': 'API URL',
            'default_model': 'Varsayılan Model',
            'default_language': 'Varsayılan Dil',
            'is_active': 'Aktif'
        }
        help_texts = {
            'api_url': 'Ollama server\'ınızın tam adresi (örn: http://192.168.1.100:11434)',
            'default_model': 'Varsayılan olarak kullanılacak model (boş bırakılırsa otomatik seçilir)',
            'default_language': 'AI yanıtlarının varsayılan dili',
            'is_active': 'Bu ayarların kullanılmasını istiyorsanız işaretleyin'
        }
    
    def clean_api_url(self):
        """API URL'yi doğrula"""
        api_url = self.cleaned_data.get('api_url')
        if api_url:
            # URL'nin geçerli olup olmadığını kontrol et
            if not api_url.startswith(('http://', 'https://')):
                raise forms.ValidationError('URL http:// veya https:// ile başlamalıdır.')
            
            # Port numarasının olup olmadığını kontrol et
            if ':' not in api_url.split('://')[1]:
                raise forms.ValidationError('URL port numarası içermelidir (örn: :11434).')
        
        return api_url
