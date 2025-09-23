from django.contrib import admin
from django.utils.html import format_html
from .models import Article, ArticleComment


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'category', 'status', 'view_count', 'created_at', 'is_featured']
    list_filter = ['status', 'category', 'is_featured', 'created_at', 'author']
    search_fields = ['title', 'content', 'tags', 'author__username']
    list_editable = ['status', 'is_featured']
    readonly_fields = ['slug', 'view_count', 'created_at', 'updated_at', 'published_at']
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('title', 'slug', 'author', 'category', 'status')
        }),
        ('İçerik', {
            'fields': ('content', 'excerpt', 'tags')
        }),
        ('Görsel ve Öne Çıkarma', {
            'fields': ('featured_image', 'is_featured')
        }),
        ('İstatistikler', {
            'fields': ('view_count', 'created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Yeni makale oluşturuluyorsa
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(ArticleComment)
class ArticleCommentAdmin(admin.ModelAdmin):
    list_display = ['article', 'author', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at', 'article__status']
    search_fields = ['content', 'author__username', 'article__title']
    list_editable = ['is_approved']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('article', 'author')