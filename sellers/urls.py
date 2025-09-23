from django.urls import path
from . import views

app_name = 'sellers'

urlpatterns = [
    # Ana sayfa
    path('', views.index, name='index'),
    
    # Müşteri yönetimi
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/create/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    
    # Proje satış yönetimi
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sales/create/', views.sale_create, name='sale_create'),
    path('sales/<int:pk>/edit/', views.sale_update, name='sale_update'),
    path('sales/<int:sale_id>/delete/', views.delete_sale, name='delete_sale'),
    
    # Dosya yönetimi
    path('sales/<int:sale_pk>/files/upload/', views.file_upload, name='file_upload'),
    path('files/<int:pk>/delete/', views.file_delete, name='file_delete'),
    path('files/<int:pk>/preview/', views.file_preview, name='file_preview'),
    
    # Fiyatlandırma
    path('sales/<int:sale_pk>/pricing/', views.price_calculator, name='price_calculator'),
    path('sales/<int:sale_pk>/extra-services/add/', views.add_extra_service, name='add_extra_service'),
    path('extra-services/<int:service_pk>/edit/', views.edit_extra_service, name='edit_extra_service'),
    path('extra-services/<int:service_pk>/delete/', views.delete_extra_service, name='delete_extra_service'),
    path('sales/<int:sale_pk>/additional-costs/add/', views.add_additional_cost, name='add_additional_cost'),
    path('additional-costs/<int:cost_pk>/edit/', views.edit_additional_cost, name='edit_additional_cost'),
    path('additional-costs/<int:cost_pk>/delete/', views.delete_additional_cost, name='delete_additional_cost'),
    
    # Payment Receipt Management
    path('sales/<int:sale_id>/payments/add/', views.add_payment_receipt, name='add_payment_receipt'),
    path('payments/<int:receipt_id>/edit/', views.edit_payment_receipt, name='edit_payment_receipt'),
    path('payments/<int:receipt_id>/delete/', views.delete_payment_receipt, name='delete_payment_receipt'),
    
    # Reports
    path('reports/revenue/', views.revenue_report, name='revenue_report'),
    
    # AJAX endpoints
    path('api/package-price/', views.get_package_price, name='get_package_price'),
    path('api/extra-service-price/', views.get_extra_service_price, name='get_extra_service_price'),
    path('api/project-data/', views.get_project_data, name='get_project_data'),
]
