from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Message, Notification, MessageGroup, MessageGroupMember, MessageReadStatus, 
    DirectMessage, DirectMessageContent
)

class MessageReadStatusInline(admin.TabularInline):
    """
    Message modelinde inline olarak MessageReadStatus modelini göstermek için.
    """
    model = MessageReadStatus
    extra = 0
    readonly_fields = ('user', 'is_read', 'read_at')

class MessageGroupMemberInline(admin.TabularInline):
    """
    MessageGroup modelinde inline olarak MessageGroupMember modelini göstermek için.
    """
    model = MessageGroupMember
    extra = 0
    readonly_fields = ('user', 'role', 'joined_at')

class MessageInline(admin.TabularInline):
    """
    MessageGroup modelinde inline olarak Message modelini göstermek için.
    """
    model = Message
    fk_name = 'group'
    extra = 0
    readonly_fields = ('sender', 'message_type', 'content', 'created_at')

class DirectMessageContentInline(admin.TabularInline):
    model = DirectMessageContent
    extra = 0
    readonly_fields = ('sent_at', 'read_at')
    fields = ('sender', 'content', 'is_read', 'sent_at', 'read_at')

@admin.register(MessageGroup)
class MessageGroupAdmin(admin.ModelAdmin):
    """
    MessageGroup modeli için admin arayüzü.
    """
    list_display = ('name', 'type', 'get_member_count', 'get_message_count', 'created_at', 'updated_at')
    list_filter = ('type', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [MessageGroupMemberInline, MessageInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'type', 'image')
        }),
        (_('İlişkili Öğeler'), {
            'fields': ('related_project', 'related_task'),
            'classes': ('collapse',),
        }),
        (_('Tarih Bilgileri'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = _('Üye Sayısı')
    
    def get_message_count(self, obj):
        return obj.messages.count()
    get_message_count.short_description = _('Mesaj Sayısı')

@admin.register(MessageGroupMember)
class MessageGroupMemberAdmin(admin.ModelAdmin):
    """
    MessageGroupMember modeli için admin arayüzü.
    """
    list_display = ('group', 'user', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('group__name', 'user__username')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Message modeli için admin arayüzü.
    """
    list_display = ('sender', 'recipient', 'group', 'message_type', 'created_at', 'is_read')
    list_filter = ('message_type', 'is_read', 'created_at')
    search_fields = ('content', 'sender__username', 'recipient__username', 'group__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at')

@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    """
    MessageReadStatus modeli için admin arayüzü.
    """
    list_display = ('message', 'user', 'is_read', 'read_at')
    list_filter = ('is_read', 'read_at')
    search_fields = ('message__content', 'user__username')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Notification modeli için admin arayüzü.
    """
    list_display = ('recipient', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'content', 'recipient__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('recipient', 'sender', 'title', 'content', 'notification_type')
        }),
        (_('İlişkili Öğeler'), {
            'fields': ('related_project', 'related_task', 'related_message_group'),
            'classes': ('collapse',),
        }),
        (_('Okunma Bilgileri'), {
            'fields': ('is_read', 'read_at'),
            'classes': ('collapse',),
        }),
        (_('Tarih Bilgileri'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user1', 'user2', 'user1_unread', 'user2_unread', 'updated_at')
    list_filter = ('updated_at',)
    search_fields = ('user1__username', 'user2__username', 'user1__first_name', 'user2__first_name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [DirectMessageContentInline]

@admin.register(DirectMessageContent)
class DirectMessageContentAdmin(admin.ModelAdmin):
    list_display = ('id', 'direct_message', 'sender', 'message_type', 'is_read', 'sent_at')
    list_filter = ('message_type', 'is_read', 'sent_at')
    search_fields = ('content', 'sender__username')
    readonly_fields = ('sent_at', 'read_at')
