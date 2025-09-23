from django.contrib import admin
from .models import Customer, ProjectSale, ProjectFile, SaleExtraService, AdditionalCost

# Admin panel başlığını güncelle
admin.site.site_header = "GlichFlow Yönetim Paneli"
admin.site.site_title = "GlichFlow Admin"
admin.site.index_title = "Satış Yönetimi"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['get_display_name', 'customer_type', 'email', 'phone', 'is_active', 'created_at']
    list_filter = ['customer_type', 'is_active', 'created_at']
    search_fields = ['first_name', 'last_name', 'company_name', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_display_name(self, obj):
        """Admin listesinde görüntülenmek için display_name property'sini kullan"""
        return obj.display_name
    get_display_name.short_description = 'Müşteri Adı'
    get_display_name.admin_order_field = 'company_name'  # Sıralama için company_name kullan
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('customer_type', 'first_name', 'last_name', 'company_name', 'tax_number')
        }),
        ('İletişim Bilgileri', {
            'fields': ('email', 'phone', 'address', 'city', 'country')
        }),
        ('Ek Bilgiler', {
            'fields': ('notes', 'is_active')
        }),
        ('Sistem Bilgileri', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProjectSale)
class ProjectSaleAdmin(admin.ModelAdmin):
    list_display = ['project_name', 'customer', 'status', 'final_price', 'seller', 'created_at']
    list_filter = ['status', 'project_type', 'created_at', 'seller']
    search_fields = ['project_name', 'customer__first_name', 'customer__last_name', 'customer__company_name']
    readonly_fields = ['final_price', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Proje Bilgileri', {
            'fields': ('project_name', 'project_description', 'project_type', 'customer', 'linked_project')
        }),
        ('Fiyatlandırma', {
            'fields': ('base_package', 'base_price', 'extra_services_total', 'additional_costs_total', 'final_price')
        }),
        ('Süre Bilgileri', {
            'fields': ('estimated_duration_days', 'actual_duration_days')
        }),
        ('Tarihler', {
            'fields': ('quote_date', 'start_date', 'end_date', 'delivery_date')
        }),
        ('Durum', {
            'fields': ('status',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('seller', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProjectFile)
class ProjectFileAdmin(admin.ModelAdmin):
    list_display = ['sale', 'file_type', 'version_number', 'file_name', 'get_file_size_display', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'is_active', 'uploaded_at']
    search_fields = ['sale__project_name', 'file_name', 'description']
    readonly_fields = ['file_size', 'uploaded_at']
    
    fieldsets = (
        ('Dosya Bilgileri', {
            'fields': ('sale', 'file_type', 'version_number', 'file', 'file_name', 'file_size')
        }),
        ('Açıklama', {
            'fields': ('description',)
        }),
        ('Durum', {
            'fields': ('is_active',)
        }),
        ('Sistem Bilgileri', {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SaleExtraService)
class SaleExtraServiceAdmin(admin.ModelAdmin):
    list_display = ['sale', 'get_service_name', 'quantity', 'unit_price', 'total_price', 'is_approved']
    list_filter = ['is_approved', 'extra_service']
    search_fields = ['sale__project_name', 'extra_service__name', 'custom_service_name', 'notes']
    
    fieldsets = (
        ('Hizmet Bilgileri', {
            'fields': ('sale', 'extra_service', 'custom_service_name', 'quantity', 'unit_price', 'total_price')
        }),
        ('Durum', {
            'fields': ('is_approved',)
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
    )
    
    def get_service_name(self, obj):
        return obj.get_service_name()
    get_service_name.short_description = 'Hizmet Adı'


@admin.register(AdditionalCost)
class AdditionalCostAdmin(admin.ModelAdmin):
    list_display = ['sale', 'cost_type', 'name', 'cost', 'is_customer_paid', 'is_approved']
    list_filter = ['cost_type', 'is_customer_paid', 'is_approved']
    search_fields = ['sale__project_name', 'name', 'description', 'notes']
    
    fieldsets = (
        ('Maliyet Bilgileri', {
            'fields': ('sale', 'cost_type', 'name', 'description', 'cost')
        }),
        ('Ödeme Bilgileri', {
            'fields': ('is_customer_paid',)
        }),
        ('Durum', {
            'fields': ('is_approved',)
        }),
        ('Notlar', {
            'fields': ('notes',)
        }),
    )