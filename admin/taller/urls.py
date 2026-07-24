from django.urls import path

from . import views

app_name = 'taller'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('trabajos/', views.trabajos_list, name='trabajos_list'),
    path('trabajos/nuevo/', views.trabajo_create, name='trabajo_create'),
    path('trabajos/<int:pk>/estado/', views.trabajo_estado_update, name='trabajo_estado_update'),
    path('gastos/nuevo/', views.gasto_create, name='gasto_create'),
    path('balance/', views.balance, name='balance'),
]
