from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('session/<int:session_id>/', views.chat_session, name='chat_session'),
    path('session/new/', views.chat_session, name='new_chat_session'),
    path('session/<int:session_id>/delete/', views.delete_session, name='delete_session'),
    path('session/<int:session_id>/rename/', views.rename_session, name='rename_session'),
    path('send-message/', views.send_message, name='send_message'),
    path('widget/', views.chat_widget, name='chat_widget'),
    path('api/get-session/', views.get_session, name='get_session'),
    path('api/history/', views.get_chat_history, name='get_chat_history'),
    path('api/clear-history/', views.clear_chat_history, name='clear_chat_history'),
    path('settings/', views.ollama_settings, name='ollama_settings'),
] 