from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    """
    Custom user model that extends Django's built-in AbstractUser.
    Adds additional fields needed for the project.
    """
    ROLE_CHOICES = (
        ('admin', _('Admin')),
        ('project_manager', _('Proje Yöneticisi')),
        ('team_member', _('Takım Üyesi')),
        ('guest', _('Misafir')),
    )
    
    role = models.CharField(_('Rol'), max_length=20, choices=ROLE_CHOICES, default='team_member')
    department = models.CharField(_('Departman'), max_length=100, blank=True)
    profile_picture = models.ImageField(_('Profil Resmi'), upload_to='profile_pics/', blank=True, null=True)
    phone = models.CharField(_('Telefon'), max_length=20, blank=True)
    bio = models.TextField(_('Biyografi'), blank=True)
    
    # Muhasebe gibi yan yetkiler için etiket sistemi
    # Ör: muhasebeci, muhasebeadmin
    # Tag modeli aşağıda tanımlanır ve kullanıcıya M2M ilişki ile bağlanır.
    # Not: Migration gerektirir.
    
    
    # Additional permission fields
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        related_name='custom_user_set',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        related_name='custom_user_set',
        related_query_name='user',
    )
    
    class Meta:
        verbose_name = _('Kullanıcı')
        verbose_name_plural = _('Kullanıcılar')
        
    def __str__(self):
        return self.get_full_name() or self.username

class Tag(models.Model):
    """
    Kullanıcılara ek yetki/rol sağlamak için basit etiket modeli.
    Örn: muhasebeci, muhasebeadmin gibi.
    """
    ALLOWED_TAGS = ('muhasebeci', 'muhasebeadmin', 'idea', 'makale', 'adminmakale', 'seller', 'ai')
    name = models.CharField(_('Etiket Adı'), max_length=50, unique=True)
    description = models.CharField(_('Açıklama'), max_length=255, blank=True)

    class Meta:
        verbose_name = _('Etiket')
        verbose_name_plural = _('Etiketler')
        constraints = [
            models.CheckConstraint(
                check=models.Q(name__in=('muhasebeci', 'muhasebeadmin', 'idea', 'makale', 'adminmakale', 'seller')),
                name='accounts_tag_name_in_allowed'
            )
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Sadece tanımlı etiketlere izin ver (geçici olarak devre dışı)
        # if self.name not in self.ALLOWED_TAGS:
        #     raise ValueError('Yalnızca muhasebeci, muhasebeadmin, idea, makale, adminmakale, seller ve ai etiketlerine izin verilir.')
        super().save(*args, **kwargs)

# CustomUser.tags alanını Tag tanımından sonra ekliyoruz
def _add_tags_field():
    # Bu fonksiyon sadece type checker'lar için; gerçek alan tanımı aşağıda yapılır
    pass

# Field declaration placed after Tag class definition to avoid forward reference issues
CustomUser.add_to_class(
    'tags',
    models.ManyToManyField(
        Tag,
        verbose_name=_('Etiketler'),
        blank=True,
        related_name='users'
    )
)

# Yardımcı metodlar
def user_has_tag(self, tag_name: str) -> bool:
    """Kullanıcının belirli bir etikete sahip olup olmadığını kontrol eder."""
    if not hasattr(self, 'tags'):
        return False
    try:
        return self.tags.filter(name=tag_name).exists()
    except Exception:
        return False

CustomUser.add_to_class('has_tag', user_has_tag)
