from django.urls import path
from . import views

app_name = 'ideas'

urlpatterns = [
    path('', views.idea_list, name='idea_list'),
    path('create/', views.idea_create, name='idea_create'),
    path('<int:pk>/', views.idea_detail, name='idea_detail'),
    path('<int:pk>/edit/', views.idea_update, name='idea_update'),
    path('<int:pk>/delete/', views.idea_delete, name='idea_delete'),
    path('quick-add/', views.idea_quick_add, name='idea_quick_add'),
    path('<int:pk>/connect-to-project/', views.idea_connect_to_project, name='idea_connect_to_project'),
    path('<int:pk>/disconnect-from-project/', views.idea_disconnect_from_project, name='idea_disconnect_from_project'),
]

