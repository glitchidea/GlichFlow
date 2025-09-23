from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Team(models.Model):
    """
    Ekip modeli. Kullanıcıları ekipler halinde gruplandırır.
    """
    name = models.CharField(_('Ekip Adı'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True)
    
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='led_teams',
        verbose_name=_('Ekip Lideri'),
        null=True,
        blank=True
    )
    
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='TeamMember',
        related_name='teams',
        verbose_name=_('Üyeler')
    )
    
    projects = models.ManyToManyField(
        'projects.Project',
        related_name='teams',
        verbose_name=_('Projeler'),
        blank=True
    )
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Ekip')
        verbose_name_plural = _('Ekipler')
        ordering = ['name']
    
    def __str__(self):
        return self.name


class TeamMember(models.Model):
    """
    Ekip üyeliği ara modeli. Kullanıcıların ekiplerdeki rollerini tanımlar.
    """
    ROLE_CHOICES = (
        ('member', _('Üye')),
        ('lead', _('Lider')),
        ('manager', _('Yönetici')),
        ('observer', _('Gözlemci')),
    )
    
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='team_members',
        verbose_name=_('Ekip')
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships',
        verbose_name=_('Kullanıcı')
    )
    
    role = models.CharField(_('Rol'), max_length=20, choices=ROLE_CHOICES, default='member')
    join_date = models.DateField(_('Katılma Tarihi'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Ekip Üyesi')
        verbose_name_plural = _('Ekip Üyeleri')
        unique_together = ('team', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.team.name} ({self.get_role_display()})"
