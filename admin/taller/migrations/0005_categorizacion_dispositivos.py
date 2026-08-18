from django.db import migrations, models


DISPOSITIVO_MAP = {
    'celular': ('celular', ''),
    'joystick': ('consola', 'otro'),
    'ps4': ('consola', 'ps4'),
    'notebook': ('notebook', ''),
}


def migrar_dispositivos(apps, schema_editor):
    Trabajo = apps.get_model('taller', 'Trabajo')
    for trabajo in Trabajo.objects.all():
        categoria, subtipo = DISPOSITIVO_MAP.get(trabajo.dispositivo_tipo, ('otro', ''))
        trabajo.categoria_dispositivo = categoria
        trabajo.subtipo_dispositivo = subtipo
        trabajo.save(update_fields=['categoria_dispositivo', 'subtipo_dispositivo'])


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0004_alter_gasto_categoria'),
    ]

    operations = [
        migrations.AddField(
            model_name='trabajo',
            name='categoria_dispositivo',
            field=models.CharField(
                choices=[
                    ('celular', 'Celular'),
                    ('consola', 'Consola'),
                    ('notebook', 'Notebook'),
                    ('otro', 'Otro'),
                ],
                default='otro',
                max_length=20,
                verbose_name='categoría de dispositivo',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='trabajo',
            name='subtipo_dispositivo',
            field=models.CharField(
                blank=True, default='', max_length=20, verbose_name='subtipo de dispositivo'
            ),
            preserve_default=False,
        ),
        migrations.RunPython(migrar_dispositivos, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='trabajo',
            name='dispositivo_tipo',
        ),
    ]
