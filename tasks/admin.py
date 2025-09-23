from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Task, TimeLog, Comment

class TimeLogInline(admin.TabularInline):
    """
    Task modelinde inline olarak TimeLog modelini göstermek için.
    """
    model = TimeLog
    extra = 1
    fields = ('user', 'date', 'hours', 'description')

class CommentInline(admin.TabularInline):
    """
    Task modelinde inline olarak Comment modelini göstermek için.
    """
    model = Comment
    extra = 1
    fields = ('author', 'content', 'created_at')
    readonly_fields = ('created_at',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Task modeli için admin arayüzü.
    """
    list_display = ('title', 'project', 'creator', 'assignee', 'status', 'priority', 'due_date', 'is_overdue')
    list_filter = ('status', 'priority', 'due_date', 'project', 'creator', 'assignee')
    search_fields = ('title', 'description', 'assignee__username', 'creator__username', 'project__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'due_date'
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'project')
        }),
        (_('Atamalar'), {
            'fields': ('creator', 'assignee',)
        }),
        (_('Durum Bilgileri'), {
            'fields': ('status', 'priority')
        }),
        (_('Zaman Bilgileri'), {
            'fields': ('estimate_hours', 'actual_hours', 'start_date', 'due_date', 'completed_date')
        }),
        (_('Bağlantılar'), {
            'fields': ('parent_task', 'dependencies'),
            'classes': ('collapse',)
        }),
        (_('Sistem'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TimeLogInline, CommentInline]

@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    """
    TimeLog modeli için admin arayüzü.
    """
    list_display = ('task', 'user', 'date', 'hours')
    list_filter = ('date', 'user', 'task__project')
    search_fields = ('description', 'task__title', 'user__username')
    date_hierarchy = 'date'

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Comment modeli için admin arayüzü.
    """
    list_display = ('task', 'author', 'created_at')
    list_filter = ('created_at', 'author', 'task__project')
    search_fields = ('content', 'task__title', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
