from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('personal-menu/', views.personal_menu, name='personal_menu'),
    # Add more URL patterns for the dashboard app
] 