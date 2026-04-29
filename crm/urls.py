from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'crm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('deals/', views.deals_list, name='deals_list'),
    path('deals/<int:pk>/', views.deal_detail, name='deal_detail'),
    path('deals/<int:pk>/edit/', views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/change-amount/', views.deal_change_amount, name='deal_change_amount'),
    path('deals/<int:pk>/add-product/', views.deal_add_product, name='deal_add_product'),
    path('deals/<int:pk>/remove-product/<int:product_pk>/', views.deal_remove_product, name='deal_remove_product'),
    path('deals/<int:pk>/status/<str:new_status>/', views.deal_change_status, name='deal_change_status'),
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/create/', views.client_create, name='client_create'),
path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),


    # Задачи
    path('tasks/', views.tasks_list, name='tasks_list'),
    path('tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:pk>/status/<str:new_status>/', views.task_change_status, name='task_change_status'),

    # Заявки
    path('lead/create/', views.public_lead_form, name='public_lead_form'),
    path('lead/from-email/', views.create_lead_from_email, name='create_lead_from_email'),
    path('api/lead/create/', views.api_create_lead, name='api_create_lead'),
]