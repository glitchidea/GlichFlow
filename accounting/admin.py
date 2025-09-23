from django.contrib import admin
from .models import PackageGroup, Package, ExtraService


@admin.register(PackageGroup)
class PackageGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'created_by')
    search_fields = ('name',)


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'base_price', 'extra_pages_multiplier', 'is_active', 'created_at')
    list_filter = ('group', 'is_active')
    search_fields = ('name',)


@admin.register(ExtraService)
class ExtraServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'pricing_type', 'input_type', 'price', 'is_active', 'order')
    list_filter = ('group', 'pricing_type', 'input_type', 'is_active')
    search_fields = ('name', 'description')
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('group', 'name', 'description')
        }),
        ('Fiyatlandırma', {
            'fields': ('pricing_type', 'price', 'percentage')
        }),
        ('Giriş Türü', {
            'fields': ('input_type', 'unit_label', 'min_quantity', 'max_quantity', 'default_quantity', 'options')
        }),
        ('Ayarlar', {
            'fields': ('is_required', 'is_active', 'order')
        })
    )


