from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    path('', views.team_list, name='team_list'),
    path('<int:team_id>/', views.team_detail, name='team_detail'),
    path('create/', views.team_create, name='team_create'),
    path('<int:team_id>/update/', views.team_update, name='team_update'),
    path('<int:team_id>/delete/', views.team_delete, name='team_delete'),
] 