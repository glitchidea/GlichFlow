from django.urls import path
from . import views

app_name = 'communications'

urlpatterns = [
    # Yeni direkt mesajlaşma sistemi URL'leri
    path('dm/', views.direct_messages_list, name='direct_messages_list'),
    path('dm/<int:dm_id>/', views.direct_message_detail, name='direct_message_detail'),
    path('dm/new/', views.new_direct_message, name='new_direct_message'),
    path('dm/start/<int:user_id>/', views.start_direct_message, name='start_direct_message'),
    path('dm/<int:dm_id>/delete/', views.delete_direct_message, name='delete_direct_message'),
    path('api/dm/<int:dm_id>/messages/', views.load_more_direct_messages, name='load_more_direct_messages'),
    path('api/dm/unread-count/', views.get_unread_dm_count, name='get_unread_dm_count'),
    
    # Mevcut mesajlaşma sistemi URL'leri
    path('messages/', views.inbox, name='inbox'),
    path('messages/sent/', views.sent, name='sent'),
    path('messages/<int:message_id>/', views.message_detail, name='message_detail'),
    path('messages/create/', views.message_create, name='message_create'),
    path('messages/<int:message_id>/delete/', views.message_delete, name='message_delete'),

    path('chat/', views.chat_list, name='chat_list'),
    path('chat/<int:group_id>/', views.chat_detail, name='chat_detail'),
    path('chat/<int:group_id>/send/', views.create_message, name='create_message'),
    path('chat/group/create/', views.create_group, name='create_group'),
    path('chat/group/<int:group_id>/edit/', views.edit_group, name='edit_group'),
    path('chat/group/<int:group_id>/leave/', views.leave_group, name='leave_group'),
    path('chat/group/<int:group_id>/delete/', views.delete_group, name='delete_group'),
    path('chat/direct/new/', views.create_direct_message_page, name='create_direct_message_page'),
    path('chat/direct/<int:user_id>/', views.create_direct_message, name='create_direct_message'),
    path('chat/direct/<int:group_id>/delete/', views.request_delete_direct_chat, name='request_delete_direct_chat'),
    
    path('api/unread-count/', views.get_unread_count, name='get_unread_count'),
    path('api/chat/<int:group_id>/messages/', views.load_more_messages, name='load_more_messages'),
    path('api/notifications/unread/', views.get_unread_notifications, name='get_unread_notifications'),

    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:notification_id>/', views.notification_detail, name='notification_detail'),
    path('notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
] 