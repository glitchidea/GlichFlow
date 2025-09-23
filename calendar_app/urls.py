from django.urls import path
from . import views

app_name = 'calendar'

urlpatterns = [
    # Ana takvim sayfası
    path('', views.calendar_view, name='calendar'),
    
    # AJAX API'ler
    path('api/events/', views.calendar_events_api, name='events_api'),
    path('api/events/<int:event_id>/toggle/', views.toggle_event_completion, name='toggle_event'),
    
    # Etkinlik detayları
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    
    # Ayarlar
    path('settings/', views.calendar_settings, name='settings'),
    
    # Ajanda görünümü
    path('agenda/', views.agenda_view, name='agenda'),
    
    # Senkronizasyon
    path('sync/', views.sync_calendar, name='sync'),
]
