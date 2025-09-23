from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('<int:task_id>/', views.task_detail, name='task_detail'),
    path('create/', views.task_create, name='task_create'),
    path('create/<int:project_id>/', views.task_create, name='task_create_for_project'),
    path('<int:task_id>/update/', views.task_update, name='task_update'),
    path('<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('<int:task_id>/time-log/', views.add_time_log, name='add_time_log'),
    path('<int:task_id>/comment/', views.add_comment, name='add_comment'),
    path('<int:task_id>/update-status/', views.update_status, name='update_status'),
    path('<int:task_id>/attachment/', views.attachment_upload, name='attachment_upload'),
] 