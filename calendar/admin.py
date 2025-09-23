from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import CalendarEvent, CalendarSettings


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'event_type', 'start_date', 'end_date', 'priority', 'is_completed', 'is_visible')
    list_filter = ('event_type', 'priority', 'is_completed', 'is_visible', 'start_date', 'user')
    search_fields = ('title', 'description', 'user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'start_date'
    ordering = ('-start_date',)
    
    fieldsets = (
        (_('Temel Bilgiler'), {
            'fields': ('title', 'description', 'event_type', 'priority')
        }),
        (_('Tarih Bilgileri'), {
            'fields': ('start_date', 'end_date', 'is_all_day')
        }),
        (_('Görsel Ayarlar'), {
            'fields': ('color', 'icon')
        }),
        (_('Kullanıcı ve Yetki'), {
            'fields': ('user', 'content_type', 'object_id')
        }),
        (_('Durum'), {
            'fields': ('is_completed', 'is_visible')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'content_type')


@admin.register(CalendarSettings)
class CalendarSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_view', 'email_notifications', 'reminder_minutes')
    list_filter = ('default_view', 'email_notifications', 'show_tasks', 'show_projects', 'show_payments')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    
    fieldsets = (
        (_('Kullanıcı'), {
            'fields': ('user',)
        }),
        (_('Görünürlük Ayarları'), {
            'fields': ('show_tasks', 'show_projects', 'show_payments', 'show_deadlines', 'show_meetings')
        }),
        (_('Takvim Görünümü'), {
            'fields': ('default_view',)
        }),
        (_('Renk Ayarları'), {
            'fields': ('task_color', 'project_color', 'payment_color', 'deadline_color', 'meeting_color')
        }),
        (_('Bildirim Ayarları'), {
            'fields': ('email_notifications', 'reminder_minutes')
        }),
    )
