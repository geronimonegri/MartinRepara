from django.db import migrations

_REPARACIONES_CELULAR_TABLET = [
    'Cambio de tapa', 'Cambio de flex/pin de carga', 'Cambio de flex',
    'Arreglo/cambio de chasis', 'Cambio de glass', 'Cambio de módulo',
    'Cambio de batería', 'Software', 'Microsoldadura', 'Otro',
]

TIPOS_REPARACION = {
    'Celular': _REPARACIONES_CELULAR_TABLET,
    'Tablet': _REPARACIONES_CELULAR_TABLET,
    'Consola': ['Limpieza', 'Microsoldadura', 'Cambio de disco', 'Cambio de cooler', 'Otro'],
    'Joystick': ['Cambio de módulo analógico', 'Limpieza', 'Otro'],
    'Notebook': ['Cambio de bisagra', 'Memoria RAM', 'Elemento electrónico', 'Otro'],
    'Dispositivo de audio': ['Elemento electrónico', 'Bisagra', 'Otro'],
}

# Los viejos códigos de subtipo_dispositivo guardaban el choice-value
# ('ps4'), no la etiqueta ('PS4'): hay que traducirlos antes de
# comparar contra el nombre de una Marca.
SUBTIPO_DISPLAY = {
    'android': 'Android',
    'ios': 'iOS',
    'ps4': 'PS4',
    'ps5': 'PS5',
    'xbox': 'Xbox',
    'otro': 'Otro',
}


def cargar_tipos_reparacion(apps, schema_editor):
    TipoDispositivo = apps.get_model('taller', 'TipoDispositivo')
    TipoReparacion = apps.get_model('taller', 'TipoReparacion')

    tipos_dispositivo = {t.nombre: t for t in TipoDispositivo.objects.all()}
    for tipo_nombre, reparaciones in TIPOS_REPARACION.items():
        tipo_dispositivo = tipos_dispositivo[tipo_nombre]
        for i, nombre in enumerate(reparaciones):
            TipoReparacion.objects.create(nombre=nombre, tipo_dispositivo=tipo_dispositivo, orden=i)


def migrar_subtipo_a_marca_o_descripcion(apps, schema_editor):
    Trabajo = apps.get_model('taller', 'Trabajo')
    Marca = apps.get_model('taller', 'Marca')

    for trabajo in Trabajo.objects.exclude(subtipo_dispositivo='').order_by('pk'):
        display = SUBTIPO_DISPLAY.get(trabajo.subtipo_dispositivo, trabajo.subtipo_dispositivo)
        marca = Marca.objects.filter(
            tipo_dispositivo_id=trabajo.tipo_dispositivo_id, nombre__iexact=display
        ).first()
        if marca:
            trabajo.marca = marca
        else:
            trabajo.descripcion_problema = f'{trabajo.descripcion_problema} ({display})'
        trabajo.save(update_fields=['marca', 'descripcion_problema'])


def revertir_tipos_reparacion(apps, schema_editor):
    apps.get_model('taller', 'TipoReparacion').objects.all().delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0014_campos_nuevos'),
    ]

    operations = [
        migrations.RunPython(cargar_tipos_reparacion, revertir_tipos_reparacion),
        migrations.RunPython(migrar_subtipo_a_marca_o_descripcion, noop),
        migrations.RemoveField(
            model_name='trabajo',
            name='subtipo_dispositivo',
        ),
    ]
