from django.contrib import admin

from .models import Gasto, Trabajo


@admin.register(Trabajo)
class TrabajoAdmin(admin.ModelAdmin):
    list_display = (
        'cliente_nombre',
        'dispositivo_tipo',
        'estado',
        'precio_acordado',
        'fecha_ingreso',
        'fecha_entrega',
    )
    list_filter = ('dispositivo_tipo', 'estado', 'fecha_ingreso')
    search_fields = ('cliente_nombre', 'cliente_telefono', 'descripcion_problema')
    date_hierarchy = 'fecha_ingreso'


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'categoria', 'monto', 'fecha')
    list_filter = ('categoria', 'fecha')
    search_fields = ('descripcion',)
    date_hierarchy = 'fecha'
