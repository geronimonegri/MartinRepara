from django.contrib import admin

from .models import (
    CategoriaGasto,
    Cliente,
    Correlativo,
    Gasto,
    Marca,
    Modelo,
    Pago,
    Proveedor,
    RepuestoUsado,
    SubcategoriaGasto,
    Tercero,
    TipoDispositivo,
    TipoReparacion,
    TipoRepuesto,
    Trabajo,
)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'email')
    search_fields = ('nombre', 'telefono')


class RepuestoUsadoInline(admin.TabularInline):
    model = RepuestoUsado
    extra = 0


@admin.register(Trabajo)
class TrabajoAdmin(admin.ModelAdmin):
    list_display = (
        'numero',
        'cliente',
        'tipo_dispositivo',
        'marca',
        'modelo',
        'estado',
        'precio_acordado',
        'ganancia',
        'fecha_ingreso',
        'fecha_entrega',
    )
    list_filter = ('tipo_dispositivo', 'estado', 'fecha_ingreso')
    search_fields = (
        'numero',
        'cliente__nombre',
        'cliente__telefono',
        'descripcion_problema',
    )
    autocomplete_fields = ('cliente',)
    date_hierarchy = 'fecha_ingreso'
    inlines = [RepuestoUsadoInline]


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'descripcion', 'categoria', 'subcategoria', 'monto', 'fecha')
    list_filter = ('categoria', 'fecha')
    search_fields = ('numero', 'descripcion')
    date_hierarchy = 'fecha'


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'trabajo', 'monto', 'forma_pago', 'fecha')
    list_filter = ('forma_pago', 'fecha')
    search_fields = ('numero', 'trabajo__cliente__nombre', 'detalle')
    date_hierarchy = 'fecha'


class CatalogoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'orden')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(TipoDispositivo)
class TipoDispositivoAdmin(CatalogoAdmin):
    list_display = ('nombre', 'color', 'activo', 'orden')


@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(CatalogoAdmin):
    list_display = ('nombre', 'color', 'activo', 'orden')


@admin.register(SubcategoriaGasto)
class SubcategoriaGastoAdmin(CatalogoAdmin):
    list_display = ('nombre', 'categoria', 'activo', 'orden')
    list_filter = ('categoria', 'activo')


@admin.register(TipoRepuesto)
class TipoRepuestoAdmin(CatalogoAdmin):
    list_display = ('nombre', 'tipo_dispositivo', 'activo', 'orden')
    list_filter = ('tipo_dispositivo', 'activo')


@admin.register(Marca)
class MarcaAdmin(CatalogoAdmin):
    list_display = ('nombre', 'tipo_dispositivo', 'activo', 'orden')
    list_filter = ('tipo_dispositivo', 'activo')


@admin.register(Modelo)
class ModeloAdmin(CatalogoAdmin):
    list_display = ('nombre', 'marca', 'activo', 'orden')
    list_filter = ('marca', 'activo')


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'activo', 'orden')
    search_fields = ('nombre',)


@admin.register(Correlativo)
class CorrelativoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'ultimo_numero')


@admin.register(TipoReparacion)
class TipoReparacionAdmin(CatalogoAdmin):
    list_display = ('nombre', 'tipo_dispositivo', 'activo', 'orden')
    list_filter = ('tipo_dispositivo', 'activo')


@admin.register(Tercero)
class TerceroAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'telefono', 'activo', 'orden')
    search_fields = ('nombre',)
