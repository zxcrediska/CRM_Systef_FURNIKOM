from django.urls import path
from . import views

app_name = 'crm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('deals/', views.deals_list, name='deals_list'),
    path('deals/<int:pk>/', views.deal_detail, name='deal_detail'),
    path('deals/<int:pk>/edit/', views.deal_edit, name='deal_edit'),
    path('deals/<int:pk>/add-product/', views.deal_add_product, name='deal_add_product'),
    path('deals/<int:pk>/remove-product/<int:product_pk>/', views.deal_remove_product, name='deal_remove_product'),
    path('deals/<int:pk>/status/<str:new_status>/', views.deal_change_status, name='deal_change_status'),
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('tasks/', views.tasks_list, name='tasks_list'),

    # Заявки
    path('lead/create/', views.public_lead_form, name='public_lead_form'),
    path('lead/from-email/', views.create_lead_from_email, name='create_lead_from_email'),
    path('api/lead/create/', views.api_create_lead, name='api_create_lead'),
]