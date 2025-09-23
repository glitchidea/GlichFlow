from django.contrib import admin
from .models import ChatSession, ChatMessage, OllamaSettings

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'ai_model', 'language', 'created_at', 'updated_at')
    list_filter = ('user', 'ai_model', 'language', 'created_at')
    search_fields = ('title', 'user__username')
    date_hierarchy = 'created_at'
    fields = ('user', 'title', 'ai_model', 'language', 'session_id')

@admin.register(OllamaSettings)
class OllamaSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'api_url', 'default_model', 'default_language', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'default_language', 'created_at')
    search_fields = ('user__username', 'api_url', 'default_model')
    fields = ('user', 'api_url', 'default_model', 'default_language', 'is_active')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'sender', 'content_preview', 'timestamp')
    list_filter = ('sender', 'timestamp', 'session__user')
    search_fields = ('content', 'session__title', 'session__user__username')
    date_hierarchy = 'timestamp'
    
    def content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    content_preview.short_description = 'Content'
