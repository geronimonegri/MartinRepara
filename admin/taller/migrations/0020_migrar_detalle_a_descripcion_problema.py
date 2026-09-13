from django.db import migrations


def migrar_detalle(apps, schema_editor):
    """El campo "Detalle" de Trabajo se elimina: si tenía texto, se
    agrega al final de la descripción del problema para no perder el
    dato (en vez de descripcion_problema="X" y detalle="Y", queda
    descripcion_problema="X\n\nY")."""
    Trabajo = apps.get_model('taller', 'Trabajo')
    for trabajo in Trabajo.objects.exclude(detalle=''):
        trabajo.descripcion_problema = f'{trabajo.descripcion_problema}\n\n{trabajo.detalle}'
        trabajo.save(update_fields=['descripcion_problema'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0019_backfill_cantidad_precio_gastos_viejos'),
    ]

    operations = [
        migrations.RunPython(migrar_detalle, noop),
    ]
