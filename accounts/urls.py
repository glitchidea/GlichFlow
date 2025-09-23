from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
    path('settings/', views.user_settings, name='user_settings'),
    path('settings/security/', views.security_settings, name='security_settings'),
    # Add more URL patterns for the accounts app
] 