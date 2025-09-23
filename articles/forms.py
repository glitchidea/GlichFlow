from django import forms
from django.contrib.auth import get_user_model
from .models import Article, ArticleComment

User = get_user_model()


class ArticleForm(forms.ModelForm):
    """Makale oluşturma/düzenleme formu"""
    
    class Meta:
        model = Article
        fields = [
            'title', 'content', 'excerpt', 'category', 'status', 
            'tags', 'featured_image', 'is_featured'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Makale başlığını girin...',
                'required': True
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control markdown-editor',
                'rows': 20,
                'placeholder': 'Markdown formatında makale içeriğinizi yazın...\n\nÖrnek:\n# Başlık\n\n## Alt Başlık\n\n**Kalın metin** ve *italik metin*\n\n```python\nprint("Kod bloğu")\n```'
            }),
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Makale özeti (opsiyonel)...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'linux, ubuntu, kurulum (virgülle ayırın)'
            }),
            'featured_image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Content alanını required olmaktan çıkar (CodeMirror ile uyumluluk için)
        self.fields['content'].required = False
        
        # Kullanıcı adminmakale tag'ına sahip değilse bazı alanları gizle
        if self.user and not self.user.tags.filter(name='adminmakale').exists():
            # Normal makale yazarları sadece draft oluşturabilir
            self.fields['status'].widget = forms.HiddenInput()
            self.fields['is_featured'].widget = forms.HiddenInput()
            self.fields['featured_image'].widget = forms.HiddenInput()
    
    def clean_tags(self):
        """Etiketleri temizle ve doğrula"""
        tags = self.cleaned_data.get('tags', '')
        if tags:
            # Virgülle ayrılmış etiketleri temizle
            tag_list = [tag.strip().lower() for tag in tags.split(',') if tag.strip()]
            # Boş etiketleri kaldır
            tag_list = [tag for tag in tag_list if tag]
            # Tekrar eden etiketleri kaldır
            tag_list = list(set(tag_list))
            return ', '.join(tag_list)
        return tags
    
    def clean_content(self):
        """İçerik doğrulama"""
        content = self.cleaned_data.get('content', '')
        if not content or len(content.strip()) < 10:
            raise forms.ValidationError('Makale içeriği en az 10 karakter olmalıdır.')
        return content


class ArticleCommentForm(forms.ModelForm):
    """Makale yorum formu"""
    
    class Meta:
        model = ArticleComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Yorumunuzu yazın...',
                'maxlength': 1000
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].required = True


class ArticleSearchForm(forms.Form):
    """Makale arama formu"""
    
    SEARCH_CHOICES = [
        ('title', 'Başlık'),
        ('content', 'İçerik'),
        ('tags', 'Etiketler'),
        ('author', 'Yazar'),
    ]
    
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Arama yapın...',
            'id': 'search-query'
        })
    )
    
    search_in = forms.ChoiceField(
        choices=SEARCH_CHOICES,
        initial='title',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'search-in'
        })
    )
    
    category = forms.ChoiceField(
        choices=[('', 'Tüm Kategoriler')] + Article.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'search-category'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'Tüm Durumlar')] + Article.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'search-status'
        })
    )
    
    author = forms.ModelChoiceField(
        queryset=User.objects.filter(articles__isnull=False).distinct(),
        required=False,
        empty_label="Tüm Yazarlar",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'search-author'
        })
    )
