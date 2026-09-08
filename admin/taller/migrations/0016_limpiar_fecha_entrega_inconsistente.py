from django.db import migrations


def limpiar_fecha_entrega(apps, schema_editor):
    """Trabajos que quedaron con fecha_entrega pero no están Entregados
    (el bug que esta tanda corrige: al retroceder el estado, la fecha
    vieja quedaba pegada)."""
    Trabajo = apps.get_model('taller', 'Trabajo')
    Trabajo.objects.exclude(estado='entregado').filter(
        fecha_entrega__isnull=False
    ).update(fecha_entrega=None)


def sin_operacion(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0015_seed_tipo_reparacion_y_subtipo'),
    ]

    operations = [
        migrations.RunPython(limpiar_fecha_entrega, sin_operacion),
    ]
