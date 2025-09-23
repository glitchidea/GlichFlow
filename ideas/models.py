from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Projects modelini import etmek için
try:
    from projects.models import Project
except ImportError:
    Project = None

class Idea(models.Model):
    """
    Kullanıcıların proje fikirlerini not ettiği model.
    """
    PRIORITY_CHOICES = (
        ('low', 'Düşük'),
        ('medium', 'Orta'),
        ('high', 'Yüksek'),
        ('urgent', 'Acil'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Taslak'),
        ('active', 'Aktif'),
        ('on_hold', 'Beklemede'),
        ('completed', 'Tamamlandı'),
        ('cancelled', 'İptal Edildi'),
    )
    
    title = models.CharField('Başlık', max_length=200)
    description = models.TextField('Açıklama', blank=True)
    requirements = models.TextField('Gereksinimler', blank=True, help_text='Proje için gerekli olan şeyler')
    working_principle = models.TextField('Çalışma Prensibi', blank=True, help_text='Projenin nasıl çalışacağı')
    technologies = models.TextField('Kullanılacak Teknolojiler', blank=True, help_text='Hangi teknolojiler kullanılacak')
    priority = models.CharField('Öncelik', max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('Durum', max_length=10, choices=STATUS_CHOICES, default='draft')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ideas', verbose_name='Yazar')
    project = models.ForeignKey('projects.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='ideas', verbose_name='Bağlı Proje')
    created_at = models.DateTimeField('Oluşturulma Tarihi', auto_now_add=True)
    updated_at = models.DateTimeField('Güncellenme Tarihi', auto_now=True)
    
    class Meta:
        verbose_name = 'Fikir'
        verbose_name_plural = 'Fikirler'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def priority_color(self):
        """Öncelik seviyesine göre renk döndürür"""
        colors = {
            'low': 'success',
            'medium': 'info',
            'high': 'warning',
            'urgent': 'danger'
        }
        return colors.get(self.priority, 'secondary')
    
    @property
    def status_color(self):
        """Durum seviyesine göre renk döndürür"""
        colors = {
            'draft': 'secondary',
            'active': 'primary',
            'on_hold': 'warning',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return colors.get(self.status, 'secondary')
    
    @property
    def is_connected_to_project(self):
        """Fikrin projeye bağlı olup olmadığını kontrol eder"""
        return self.project is not None
    
    def can_be_converted_to_project(self):
        """Fikrin projeye dönüştürülebilir olup olmadığını kontrol eder"""
        return not self.is_connected_to_project and self.status in ['draft', 'active']