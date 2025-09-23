from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Count
import os

# Yeni direkt mesajlaşma sistemi için modeller
class DirectMessage(models.Model):
    """
    Kullanıcılar arasında birebir mesajlaşma için ana model.
    Bu model, iki kullanıcı arasındaki bir mesajlaşma oturumunu temsil eder.
    """
    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='direct_messages_as_user1',
        verbose_name=_('Kullanıcı 1')
    )
    
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='direct_messages_as_user2',
        verbose_name=_('Kullanıcı 2')
    )
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Son Mesaj Tarihi'), auto_now=True)
    
    # İstatistikler
    user1_unread = models.PositiveIntegerField(_('Kullanıcı 1 Okunmamış'), default=0)
    user2_unread = models.PositiveIntegerField(_('Kullanıcı 2 Okunmamış'), default=0)
    
    class Meta:
        verbose_name = _('Direkt Mesajlaşma')
        verbose_name_plural = _('Direkt Mesajlaşmalar')
        # Aynı kullanıcı çifti için sadece bir kayıt olmasını sağlar
        # (kim user1/user2 olduğu önemli değil)
        constraints = [
            models.UniqueConstraint(
                fields=['user1', 'user2'],
                name='unique_users_direct_message'
            ),
            models.CheckConstraint(
                check=~models.Q(user1=models.F('user2')),
                name='different_users_direct_message'
            )
        ]
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user1} - {self.user2}"
    
    def get_display_name(self, user):
        """Mesajlaşmanın diğer tarafının adını döndürür"""
        if user == self.user1:
            return self.user2.get_full_name() or self.user2.username
        else:
            return self.user1.get_full_name() or self.user1.username
    
    def get_other_user(self, user):
        """Mesajlaşmanın diğer tarafını döndürür"""
        if user == self.user1:
            return self.user2
        else:
            return self.user1
    
    def mark_as_read(self, user):
        """Kullanıcı için mesajları okundu olarak işaretler"""
        if user == self.user1 and self.user1_unread > 0:
            self.user1_unread = 0
            self.save(update_fields=['user1_unread'])
            # İlgili içerikleri de okundu olarak işaretle
            self.messages.filter(is_read=False, sender=self.user2).update(
                is_read=True, 
                read_at=timezone.now()
            )
        elif user == self.user2 and self.user2_unread > 0:
            self.user2_unread = 0
            self.save(update_fields=['user2_unread'])
            # İlgili içerikleri de okundu olarak işaretle
            self.messages.filter(is_read=False, sender=self.user1).update(
                is_read=True, 
                read_at=timezone.now()
            )
    
    def get_unread_count(self, user):
        """Kullanıcı için okunmamış mesaj sayısını döndürür"""
        if user == self.user1:
            return self.user1_unread
        else:
            return self.user2_unread
    
    def get_last_message(self):
        """Son mesajı döndürür"""
        return self.messages.order_by('-sent_at').first()
    
    def get_absolute_url(self):
        """Mesajlaşma detay sayfasının URL'sini döndürür"""
        return reverse('communications:direct_message_detail', kwargs={'dm_id': self.id})


class DirectMessageContent(models.Model):
    """
    Direkt mesajlaşma içeriklerini tutan model.
    """
    MESSAGE_TYPE_CHOICES = (
        ('text', _('Metin')),
        ('image', _('Resim')),
        ('file', _('Dosya')),
        ('system', _('Sistem Mesajı')),
    )
    
    direct_message = models.ForeignKey(
        DirectMessage,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Mesajlaşma')
    )
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_direct_messages',
        verbose_name=_('Gönderen')
    )
    
    # İçerik
    message_type = models.CharField(_('Mesaj Tipi'), max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField(_('İçerik'))
    file = models.FileField(_('Dosya'), upload_to='uploads/direct_messages/', null=True, blank=True)
    
    # Okunma durumu
    is_read = models.BooleanField(_('Okundu'), default=False)
    read_at = models.DateTimeField(_('Okunma Tarihi'), null=True, blank=True)
    
    # Zaman bilgileri
    sent_at = models.DateTimeField(_('Gönderim Tarihi'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Direkt Mesaj İçeriği')
        verbose_name_plural = _('Direkt Mesaj İçerikleri')
        ordering = ['sent_at']
    
    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"
    
    def save(self, *args, **kwargs):
        # Mesaj gönderildiğinde, karşı tarafın okunmamış mesaj sayısını arttır
        is_new = self.pk is None
        if is_new:
            dm = self.direct_message
            recipient = None
            
            if self.sender == dm.user1:
                dm.user2_unread += 1
                dm.save(update_fields=['user2_unread', 'updated_at'])
                recipient = dm.user2
            else:
                dm.user1_unread += 1
                dm.save(update_fields=['user1_unread', 'updated_at'])
                recipient = dm.user1
            
            super().save(*args, **kwargs)
            
            # Sistem mesajları için bildirim oluşturma
            if self.message_type != 'system' and recipient:
                # create_direct_message_notification fonksiyonunu çağır
                create_direct_message_notification(self, recipient)
        else:
            super().save(*args, **kwargs)

# Mevcut modeller devam ediyor
class MessageGroup(models.Model):
    """
    Mesaj grupları için model. Direkt mesajlar ve grup sohbetleri için kullanılır.
    """
    GROUP_TYPE_CHOICES = (
        ('direct', _('Direkt Mesaj')),
        ('group', _('Grup')),
        ('project', _('Proje Grubu')),
        ('task', _('Görev Grubu')),
    )
    
    # Grup bilgileri
    name = models.CharField(_('Grup Adı'), max_length=255)
    description = models.TextField(_('Açıklama'), blank=True, null=True)
    type = models.CharField(_('Grup Tipi'), max_length=20, choices=GROUP_TYPE_CHOICES, default='group')
    image = models.ImageField(_('Grup Resmi'), upload_to='uploads/groups/', null=True, blank=True)
    
    # Grup üyeleri
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MessageGroupMember',
        related_name='message_groups',
        verbose_name=_('Üyeler')
    )
    
    # İlişkili projeler/görevler
    related_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.SET_NULL,
        related_name='message_groups',
        verbose_name=_('İlgili Proje'),
        null=True,
        blank=True
    )
    
    related_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        related_name='message_groups',
        verbose_name=_('İlgili Görev'),
        null=True,
        blank=True
    )
    
    # Tarih bilgileri
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Mesaj Grubu')
        verbose_name_plural = _('Mesaj Grupları')
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name

class MessageGroupMember(models.Model):
    """
    Mesaj grubu üyeliği tablosu. Kullanıcıların gruplardaki rollerini ve yetkilerini takip eder.
    """
    ROLE_CHOICES = (
        ('admin', _('Yönetici')),
        ('member', _('Üye')),
    )
    
    group = models.ForeignKey(
        MessageGroup,
        on_delete=models.CASCADE,
        related_name='group_members',
        verbose_name=_('Grup')
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships',
        verbose_name=_('Kullanıcı')
    )
    
    role = models.CharField(_('Rol'), max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(_('Katılma Tarihi'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Grup Üyesi')
        verbose_name_plural = _('Grup Üyeleri')
        unique_together = ('group', 'user')
    
    def __str__(self):
        return f"{self.user} - {self.group}"
    
    def get_role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

class Message(models.Model):
    """
    Mesajlar için model. Hem eski tip (kullanıcıdan kullanıcıya) hem de 
    yeni tip (grup içi) mesajları destekler.
    """
    MESSAGE_TYPE_CHOICES = (
        ('text', _('Metin')),
        ('image', _('Resim')),
        ('file', _('Dosya')),
        ('system', _('Sistem Mesajı')),
    )
    
    # Gönderici
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name=_('Gönderen')
    )
    
    # Alıcı (eski tip mesajlar için)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages',
        verbose_name=_('Alıcı'),
        null=True,
        blank=True
    )
    
    # Mesaj grubu (yeni tip mesajlar için)
    group = models.ForeignKey(
        MessageGroup,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('Grup'),
        null=True,
        blank=True
    )
    
    # Yanıtlanan mesaj
    parent_message = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_('Yanıtlanan Mesaj')
    )
    
    # Mesaj tipi ve içeriği
    message_type = models.CharField(_('Mesaj Tipi'), max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    subject = models.CharField(_('Konu'), max_length=255, null=True, blank=True)
    content = models.TextField(_('İçerik'))
    file = models.FileField(_('Dosya'), upload_to='uploads/messages/', null=True, blank=True)
    
    # Okunma durumu (eski tip mesajlar için) - yeni tip mesajlarda MessageReadStatus kullanılır
    is_read = models.BooleanField(_('Okundu'), default=False)
    read_at = models.DateTimeField(_('Okunma Tarihi'), null=True, blank=True)
    
    # Tarih bilgileri
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Güncellenme Tarihi'), auto_now=True)
    
    class Meta:
        verbose_name = _('Mesaj')
        verbose_name_plural = _('Mesajlar')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Mesaj: {self.content[:50]}"
    
    def mark_as_read(self):
        """Mesajı okundu olarak işaretler (eski tip mesajlar için)"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

class MessageReadStatus(models.Model):
    """
    Mesaj okunma durumlarını takip etmek için model. 
    Grup içindeki her kullanıcı için ayrı bir kayıt oluşturulur.
    """
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='read_status',
        verbose_name=_('Mesaj')
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_read_status',
        verbose_name=_('Kullanıcı')
    )
    
    is_read = models.BooleanField(_('Okundu'), default=False)
    read_at = models.DateTimeField(_('Okunma Tarihi'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('Mesaj Okunma Durumu')
        verbose_name_plural = _('Mesaj Okunma Durumları')
        unique_together = ('message', 'user')
    
    def __str__(self):
        return f"{self.user} - {self.message}"
    
    def mark_as_read(self):
        """Mesajı okundu olarak işaretler"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

class Notification(models.Model):
    """
    Kullanıcılara gönderilen bildirimler için model.
    """
    NOTIFICATION_TYPE_CHOICES = (
        ('info', _('Bilgi')),
        ('success', _('Başarı')),
        ('warning', _('Uyarı')),
        ('error', _('Hata')),
    )
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('Alıcı')
    )
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_notifications',
        verbose_name=_('Gönderen'),
        null=True,
        blank=True
    )
    
    title = models.CharField(_('Başlık'), max_length=255)
    content = models.TextField(_('İçerik'))
    notification_type = models.CharField(_('Bildirim Tipi'), max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='info')
    
    # İlgili bağlantılar (opsiyonel)
    related_project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='project_notifications',
        verbose_name=_('İlgili Proje'),
        null=True,
        blank=True
    )
    
    related_task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.CASCADE,
        related_name='task_notifications',
        verbose_name=_('İlgili Görev'),
        null=True,
        blank=True
    )
    
    related_message_group = models.ForeignKey(
        MessageGroup, 
        on_delete=models.CASCADE,
        related_name='group_notifications',
        verbose_name=_('İlgili Mesaj Grubu'),
        null=True,
        blank=True
    )
    
    # Okunma durumu
    is_read = models.BooleanField(_('Okundu'), default=False)
    read_at = models.DateTimeField(_('Okunma Tarihi'), null=True, blank=True)
    
    created_at = models.DateTimeField(_('Oluşturulma Tarihi'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Bildirim')
        verbose_name_plural = _('Bildirimler')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def mark_as_read(self):
        """Bildirimi okundu olarak işaretler"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            
    def get_absolute_url(self):
        """Bildirime ait detay sayfasının URL'sini döndürür"""
        return reverse('communications:notification_detail', kwargs={'notification_id': self.id})

@receiver(post_save, sender=Message)
def handle_message_save(sender, instance, created, **kwargs):
    """
    Mesaj oluşturulduğunda veya güncellendiğinde tetiklenen sinyal.
    GitHub ile ilişkili mesaj gruplarında otomatik olarak GitHub'a yorum gönderir.
    """
    if not created:
        # Sadece yeni mesajlar için işlem yap
        return
    
    # Mesajın bir gruba ait olduğunu kontrol et
    if not instance.group:
        return
    
    # İlişkili görev var mı kontrol et
    task = instance.group.related_task
    if not task:
        return
    
    # Bu mesajın GitHub ile ilgili olup olmadığını kontrol et
    # GitHub'dan otomatik olarak alınan mesajları geri gönderme
    if "Bu mesaj GitHub'dan otomatik olarak alındı" in instance.content:
        return
    
    # GitHub issue bağlantısı var mı kontrol et
    try:
        github_issue = task.github_issue
        
        if github_issue:
            # GitHub modülünü dinamik olarak import et
            from github_integration.sync import create_github_comment_from_message
            
            # Mesajı GitHub'a gönder
            success, comment, error = create_github_comment_from_message(instance, github_issue)
            
            if not success and error:
                # Hata varsa logla
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"GitHub yorum gönderme hatası: {error}")
    
    except Exception as e:
        # Hata varsa sessizce geç
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"GitHub mesaj-yorum senkronizasyon hatası: {str(e)}")

# Yardımcı fonksiyonlar
def create_direct_message_notification(message, recipient):
    """DirectMessage için bildirim oluşturur"""
    # İç içe import - circular import sorununu önlemek için
    from communications.models import Notification
    
    # Kısa mesaj içeriği oluştur
    short_content = message.content[:50]
    if len(message.content) > 50:
        short_content += '...'
    
    # Mesaj türüne göre başlık oluştur
    sender_name = message.sender.get_full_name() or message.sender.username
    
    if message.message_type == 'text':
        title = f"Yeni mesaj: {sender_name}"
    elif message.message_type == 'image':
        title = f"{sender_name} bir resim gönderdi"
    elif message.message_type == 'file':
        title = f"{sender_name} bir dosya gönderdi"
    else:
        title = "Yeni direkt mesaj"
    
    # Bildirim oluştur
    Notification.objects.create(
        recipient=recipient,
        sender=message.sender,
        title=title,
        content=short_content,
        notification_type='info'
    )
