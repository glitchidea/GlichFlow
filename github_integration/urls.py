from django.urls import path
from . import views

app_name = 'github_integration'

urlpatterns = [
    # GitHub hesap yönetimi
    path('connect/', views.github_connect, name='github_connect'),
    path('callback/', views.github_callback, name='github_callback'),
    path('profile/', views.github_profile, name='github_profile'),
    path('disconnect/', views.github_disconnect, name='github_disconnect'),
    path('oauth-settings/', views.github_oauth_settings, name='github_oauth_settings'),
    
    # Proje entegrasyonu
    path('project/<int:project_id>/connect/', views.project_github_connect, name='project_github_connect'),
    path('project/<int:project_id>/sync/', views.project_github_sync, name='project_github_sync'),
    path('project/<int:project_id>/import-issues/', views.project_github_issues_import, name='project_github_issues_import'),
    path('project/<int:project_id>/webhook/', views.project_github_webhook, name='project_github_webhook'),
    
    # Görev entegrasyonu
    path('task/<int:task_id>/sync/', views.task_github_sync, name='task_github_sync'),
    
    # GitHub issue yorumları
    path('issue/<int:issue_id>/comments/', views.issue_comments, name='issue_comments'),
    path('issue/<int:issue_id>/sync-comments/', views.issue_sync_comments, name='issue_sync_comments'),
    
    # GitHub issue işlemleri
    path('issue/<int:issue_id>/update/', views.issue_update, name='issue_update'),
    path('issue/<int:issue_id>/close/', views.issue_close, name='issue_close'),
    path('issue/<int:issue_id>/reopen/', views.issue_reopen, name='issue_reopen'),
    
    # GitHub Mesajları
    path('messages/', views.github_messages_list, name='github_messages_list'),
    
    # Senkronizasyon kayıtları
    path('sync-logs/', views.sync_logs, name='sync_logs'),
    
    # Webhook
    path('webhook/', views.github_webhook, name='github_webhook'),
] 