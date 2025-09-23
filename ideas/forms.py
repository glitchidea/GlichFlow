from django import forms
from .models import Idea

class IdeaForm(forms.ModelForm):
    """Fikir oluşturma ve düzenleme formu"""
    
    class Meta:
        model = Idea
        fields = [
            'title', 'description', 'requirements', 
            'working_principle', 'technologies', 
            'priority', 'status'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Fikir başlığını girin...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Fikrinizi detaylı olarak açıklayın...'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Proje için gerekli olan şeyleri listeleyin...'
            }),
            'working_principle': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Projenin nasıl çalışacağını açıklayın...'
            }),
            'technologies': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Kullanılacak teknolojileri yazın (örn: Python, Django, React)...'
            }),
            'priority': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Form alanlarına label ekle
        self.fields['title'].label = 'Başlık'
        self.fields['description'].label = 'Açıklama'
        self.fields['requirements'].label = 'Gereksinimler'
        self.fields['working_principle'].label = 'Çalışma Prensibi'
        self.fields['technologies'].label = 'Teknolojiler'
        self.fields['priority'].label = 'Öncelik'
        self.fields['status'].label = 'Durum'

