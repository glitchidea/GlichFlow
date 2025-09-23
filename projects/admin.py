from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Project, Attachment, PRD

class AttachmentInline(admin.TabularInline):
    """
    Project modelinde inline olarak Attachment modelini göstermek için.
    """
    model = Attachment
    extra = 1
    fields = ('name', 'file', 'uploaded_by', 'upload_date')
    readonly_fields = ('upload_date',)

class PRDInline(admin.TabularInline):
    """
    Project modelinde inline olarak PRD modelini göstermek için.
    """
    model = PRD
    extra = 1
    fields = ('title', 'status', 'priority', 'created_by', 'assigned_by')
    readonly_fields = ('created_at', 'assigned_at')

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """
    Project modeli için admin arayüzü.
    """
    list_display = ('name', 'status', 'priority', 'manager', 'start_date', 'end_date', 'progress', 'is_overdue')
    list_filter = ('status', 'priority', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'manager__username')
    readonly_fields = ('created_at', 'updated_at', 'progress')
    filter_horizontal = ('team_members',)
    date_hierarchy = 'start_date'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        (_('Durum Bilgileri'), {
            'fields': ('status', 'priority', 'progress')
        }),
        (_('Tarihler'), {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at')
        }),
        (_('Atamalar'), {
            'fields': ('manager', 'team_members')
        }),
        (_('Bütçe Bilgileri'), {
            'fields': ('budget', 'cost'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [AttachmentInline, PRDInline]

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    """
    Attachment modeli için admin arayüzü.
    """
    list_display = ('name', 'project', 'task', 'uploaded_by', 'upload_date')
    list_filter = ('upload_date', 'project')
    search_fields = ('name', 'description', 'project__name', 'task__title')
    readonly_fields = ('upload_date',)

@admin.register(PRD)
class PRDAdmin(admin.ModelAdmin):
    """
    PRD modeli için admin arayüzü.
    """
    list_display = ('title', 'status', 'created_by', 'assigned_by', 'project', 'task', 'created_at')
    list_filter = ('status', 'created_at', 'assigned_at')
    search_fields = ('title', 'product_summary', 'target_audience', 'functional_requirements', 'created_by__username', 'assigned_by__username')
    readonly_fields = ('created_at', 'updated_at', 'assigned_at', 'reviewed_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'status')
        }),
        (_('Ürün Bilgileri'), {
            'fields': ('product_summary', 'target_audience')
        }),
        (_('Gereksinimler'), {
            'fields': ('functional_requirements', 'non_functional_requirements')
        }),
        (_('Kullanıcı Deneyimi'), {
            'fields': ('user_stories', 'acceptance_criteria')
        }),
        (_('Teknik Gereksinimler'), {
            'fields': ('technical_requirements', 'design_constraints')
        }),
        (_('Dosya'), {
            'fields': ('document',),
            'classes': ('collapse',)
        }),
        (_('Atama'), {
            'fields': ('project', 'task', 'assigned_by')
        }),
        (_('Tarihler'), {
            'fields': ('created_at', 'updated_at', 'assigned_at', 'reviewed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """
        Admin panelinde PRD'leri filtrelemek için.
        """
        qs = super().get_queryset(request)
        return qs.select_related('created_by', 'assigned_by', 'project', 'task')
