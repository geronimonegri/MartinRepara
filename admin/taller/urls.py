from django.urls import path

from . import views

app_name = 'taller'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('trabajos/', views.trabajos_list, name='trabajos_list'),
    path('trabajos/nuevo/', views.trabajo_create, name='trabajo_create'),
    path('trabajos/<int:pk>/editar/', views.trabajo_edit, name='trabajo_edit'),
    path('trabajos/<int:pk>/eliminar/', views.trabajo_delete, name='trabajo_delete'),
    path('trabajos/<int:pk>/estado/', views.trabajo_estado_update, name='trabajo_estado_update'),
    path('gastos/', views.gasto_create, name='gasto_create'),
    path('pagos/', views.pago_create, name='pago_create'),
    path('pagos/<int:pk>/editar/', views.pago_edit, name='pago_edit'),
    path('balance/', views.balance, name='balance'),
]
