from django.contrib import admin
from .models import Idea

@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'priority', 'status', 'created_at')
    list_filter = ('priority', 'status', 'created_at', 'author')
    search_fields = ('title', 'description', 'author__username', 'author__first_name', 'author__last_name')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'author', 'description')
        }),
        ('Proje Detayları', {
            'fields': ('requirements', 'working_principle', 'technologies')
        }),
        ('Durum ve Öncelik', {
            'fields': ('priority', 'status')
        }),
        ('Tarihler', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author')