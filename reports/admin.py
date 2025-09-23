from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Report, ReportSubscription

class ReportSubscriptionInline(admin.TabularInline):
    """
    Report modelinde inline olarak ReportSubscription modelini göstermek için.
    """
    model = ReportSubscription
    extra = 1
    fields = ('user', 'email_notification', 'system_notification')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """
    Report modeli için admin arayüzü.
    """
    list_display = ('title', 'report_type', 'project', 'created_by', 'is_scheduled', 'created_at')
    list_filter = ('report_type', 'is_scheduled', 'created_at')
    search_fields = ('title', 'description', 'project__name', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'report_type')
        }),
        (_('İlişkiler'), {
            'fields': ('project', 'created_by')
        }),
        (_('Tarih Aralığı'), {
            'fields': ('date_from', 'date_to')
        }),
        (_('Veri ve Ayarlar'), {
            'fields': ('data', 'settings'),
            'classes': ('collapse',)
        }),
        (_('Zamanlama'), {
            'fields': ('is_scheduled', 'schedule_interval', 'last_run', 'next_run'),
            'classes': ('collapse',)
        }),
        (_('Sistem'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ReportSubscriptionInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni rapor oluşturulduğunda
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(admin.ModelAdmin):
    """
    ReportSubscription modeli için admin arayüzü.
    """
    list_display = ('report', 'user', 'email_notification', 'system_notification')
    list_filter = ('email_notification', 'system_notification', 'created_at')
    search_fields = ('report__title', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
