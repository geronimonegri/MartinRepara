from django.contrib import admin

from .models import Cliente, Gasto, Trabajo


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email')
    search_fields = ('nombre', 'telefono')


@admin.register(Trabajo)
class TrabajoAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'dispositivo_tipo',
        'estado',
        'precio_acordado',
        'fecha_ingreso',
        'fecha_entrega',
    )
    list_filter = ('dispositivo_tipo', 'estado', 'fecha_ingreso')
    search_fields = (
        'cliente__nombre',
        'cliente__telefono',
        'descripcion_problema',
    )
    autocomplete_fields = ('cliente',)
    date_hierarchy = 'fecha_ingreso'


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('descripcion', 'categoria', 'monto', 'fecha')
    list_filter = ('categoria', 'fecha')
    search_fields = ('descripcion',)
    date_hierarchy = 'fecha'
