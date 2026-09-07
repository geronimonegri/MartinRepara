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
    path('gastos/<int:pk>/editar/', views.gasto_edit, name='gasto_edit'),
    path('gastos/<int:pk>/eliminar/', views.gasto_delete, name='gasto_delete'),
    path('stock/', views.stock_list, name='stock_list'),
    path('pagos/', views.pago_create, name='pago_create'),
    path('pagos/<int:pk>/editar/', views.pago_edit, name='pago_edit'),
    path('pagos/<int:pk>/eliminar/', views.pago_delete, name='pago_delete'),
    path('balance/', views.balance, name='balance'),
    path('estadisticas/', views.estadisticas, name='estadisticas'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('configuracion/<str:tab>/', views.configuracion, name='configuracion_tab'),
    path('configuracion/<str:tab>/<int:pk>/editar/', views.configuracion, name='configuracion_editar'),
    path('configuracion/<str:tab>/<int:pk>/toggle/', views.catalogo_toggle_activo, name='catalogo_toggle_activo'),
    path('catalogos/<str:tipo>/crear-rapido/', views.catalogo_crear_rapido, name='catalogo_crear_rapido'),
    path('backup/exportar/', views.backup_exportar, name='backup_exportar'),
    path('exportar/excel/', views.exportar_excel, name='exportar_excel'),
]
