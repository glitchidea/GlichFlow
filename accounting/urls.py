from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.index, name='index'),
    path('packages/', views.package_manager, name='package_manager'),
    # CRUD
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:pk>/edit/', views.group_update, name='group_update'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),

    path('package/new/', views.package_create, name='package_create'),
    path('package/<int:pk>/edit/', views.package_update, name='package_update'),
    path('package/<int:pk>/delete/', views.package_delete, name='package_delete'),

    path('extra/new/', views.extra_create, name='extra_create'),
    path('extra/<int:pk>/edit/', views.extra_update, name='extra_update'),
    path('extra/<int:pk>/delete/', views.extra_delete, name='extra_delete'),

    path('feature/new/', views.feature_create, name='feature_create'),
    path('feature/<int:pk>/edit/', views.feature_update, name='feature_update'),
    path('feature/<int:pk>/delete/', views.feature_delete, name='feature_delete'),
]


