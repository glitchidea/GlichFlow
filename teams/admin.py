from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Team, TeamMember

class TeamMemberInline(admin.TabularInline):
    """
    Team modelinde inline olarak TeamMember modelini göstermek için.
    """
    model = TeamMember
    extra = 1
    fields = ('user', 'role', 'join_date')
    readonly_fields = ('join_date',)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """
    Team modeli için admin arayüzü.
    """
    list_display = ('name', 'leader', 'get_member_count')
    list_filter = ('created_at',)
    search_fields = ('name', 'description', 'leader__username')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('projects',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        (_('Atamalar'), {
            'fields': ('leader', 'projects')
        }),
        (_('Sistem'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TeamMemberInline]
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = _('Üye Sayısı')

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    """
    TeamMember modeli için admin arayüzü.
    """
    list_display = ('user', 'team', 'role', 'join_date')
    list_filter = ('role', 'join_date', 'team')
    search_fields = ('user__username', 'team__name')
    readonly_fields = ('join_date',)
