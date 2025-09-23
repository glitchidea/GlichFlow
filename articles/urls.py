from django.urls import path
from . import views

app_name = 'articles'

urlpatterns = [
    path('', views.article_list, name='article_list'),
    path('create/', views.article_create, name='article_create'),
    path('<slug:slug>/', views.article_detail, name='article_detail'),
    path('<slug:slug>/edit/', views.article_update, name='article_update'),
    path('<slug:slug>/delete/', views.article_delete, name='article_delete'),
    path('<slug:slug>/comment/', views.article_comment_create, name='article_comment_create'),
    path('category/<str:category>/', views.article_category_list, name='article_category_list'),
    path('author/<str:username>/', views.article_author_list, name='article_author_list'),
]
