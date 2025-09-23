from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Tag

class CustomUserAdmin(UserAdmin):
    """
    CustomUser modeli için özel admin arayüzü.
    """
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Kişisel Bilgiler'), {'fields': ('first_name', 'last_name', 'email', 'profile_picture', 'phone', 'bio')}),
        (_('İzinler'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'role', 'department', 'tags', 'groups', 'user_permissions'),
        }),
        (_('Önemli Tarihler'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role', 'groups', 'tags')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'department')
    filter_horizontal = ('tags', 'groups', 'user_permissions')

admin.site.register(CustomUser, CustomUserAdmin)
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

    def has_add_permission(self, request):
        # Yeni tag eklenmesine izin ver
        return True

    def has_delete_permission(self, request, obj=None):
        # Tag silinmesine izin ver
        return True

    def get_model_perms(self, request):
        # Tag modelini admin ana menüsünde göster
        return {
            'add': self.has_add_permission(request),
            'change': self.has_change_permission(request),
            'delete': self.has_delete_permission(request),
            'view': self.has_view_permission(request),
        }
