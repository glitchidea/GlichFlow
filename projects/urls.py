from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('create/', views.project_create, name='project_create'),
    path('<int:project_id>/update/', views.project_update, name='project_update'),
    path('<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('<int:project_id>/attachment/', views.attachment_upload, name='attachment_upload'),
    path('attachment/<int:attachment_id>/delete/', views.attachment_delete, name='attachment_delete'),
    
    # PRD URL'leri
    path('prd/', views.prd_list, name='prd_list'),
    path('prd/create/', views.prd_create, name='prd_create'),
    path('prd/<int:prd_id>/', views.prd_detail, name='prd_detail'),
    path('prd/<int:prd_id>/edit/', views.prd_edit, name='prd_edit'),
    path('prd/<int:prd_id>/delete/', views.prd_delete, name='prd_delete'),
    path('prd/<int:prd_id>/assign/', views.prd_assign, name='prd_assign'),
    path('prd/<int:prd_id>/status/', views.prd_status_change, name='prd_status_change'),
    path('prd/<int:prd_id>/toggle-assign/', views.prd_toggle_assign, name='prd_toggle_assign'),
    path('prd/<int:prd_id>/detail/', views.prd_detail_ajax, name='prd_detail_ajax'),
    path('prd/<int:prd_id>/document/', views.prd_document_view, name='prd_document_view'),
] 