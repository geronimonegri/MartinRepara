from django.contrib import admin

from .models import Cliente, Gasto, Pago, Trabajo


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email')
    search_fields = ('nombre', 'telefono')


@admin.register(Trabajo)
class TrabajoAdmin(admin.ModelAdmin):
    list_display = (
        'cliente',
        'categoria_dispositivo',
        'subtipo_dispositivo',
        'estado',
        'precio_acordado',
        'fecha_ingreso',
        'fecha_entrega',
    )
    list_filter = ('categoria_dispositivo', 'estado', 'fecha_ingreso')
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


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('trabajo', 'monto', 'forma_pago', 'fecha')
    list_filter = ('forma_pago', 'fecha')
    search_fields = ('trabajo__cliente__nombre', 'detalle')
    date_hierarchy = 'fecha'
