from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_list, name='report_list'),
    path('<int:report_id>/', views.report_detail, name='report_detail'),
    path('create/', views.report_create, name='report_create'),
    path('<int:report_id>/update/', views.report_update, name='report_update'),
    path('<int:report_id>/delete/', views.report_delete, name='report_delete'),
    path('<int:report_id>/run/', views.report_run, name='report_run'),
] 