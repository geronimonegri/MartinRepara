import django.db.models.deletion
from django.db import migrations, models


def backfill_numeros_y_tipo_dispositivo(apps, schema_editor):
    Trabajo = apps.get_model('taller', 'Trabajo')
    Gasto = apps.get_model('taller', 'Gasto')
    Pago = apps.get_model('taller', 'Pago')
    Correlativo = apps.get_model('taller', 'Correlativo')
    TipoDispositivo = apps.get_model('taller', 'TipoDispositivo')

    def siguiente_numero(tipo, prefijo):
        correlativo, _ = Correlativo.objects.get_or_create(tipo=tipo)
        correlativo.ultimo_numero += 1
        correlativo.save(update_fields=['ultimo_numero'])
        return f'{prefijo}-{correlativo.ultimo_numero:04d}'

    tipos_dispositivo = {t.nombre: t for t in TipoDispositivo.objects.all()}
    mapa_categoria_antigua = {
        'celular': 'Celular',
        'consola': 'Consola',
        'notebook': 'Notebook',
        'otro': 'Otro',
    }

    # Orden por pk: es el mejor proxy disponible al orden real de alta,
    # ya que estos modelos no tenían un timestamp de creación.
    for trabajo in Trabajo.objects.order_by('pk'):
        trabajo.numero = siguiente_numero('trabajo', 'T')
        nombre_tipo = mapa_categoria_antigua.get(trabajo.categoria_dispositivo, 'Otro')
        trabajo.tipo_dispositivo = tipos_dispositivo[nombre_tipo]
        trabajo.save(update_fields=['numero', 'tipo_dispositivo'])

    for gasto in Gasto.objects.order_by('pk'):
        gasto.numero = siguiente_numero('gasto', 'G')
        gasto.save(update_fields=['numero'])

    for pago in Pago.objects.order_by('pk'):
        pago.numero = siguiente_numero('pago', 'P')
        pago.save(update_fields=['numero'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0010_seed_catalogos'),
    ]

    operations = [
        migrations.AddField(
            model_name='trabajo',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, null=True, verbose_name='número'),
        ),
        migrations.AddField(
            model_name='gasto',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, null=True, verbose_name='número'),
        ),
        migrations.AddField(
            model_name='pago',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, null=True, verbose_name='número'),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='tipo_dispositivo',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='trabajos', to='taller.tipodispositivo',
                verbose_name='tipo de dispositivo',
            ),
        ),
        migrations.RunPython(backfill_numeros_y_tipo_dispositivo, noop),
        migrations.AlterField(
            model_name='trabajo',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True, verbose_name='número'),
        ),
        migrations.AlterField(
            model_name='gasto',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True, verbose_name='número'),
        ),
        migrations.AlterField(
            model_name='pago',
            name='numero',
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True, verbose_name='número'),
        ),
        migrations.AlterField(
            model_name='trabajo',
            name='tipo_dispositivo',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='trabajos', to='taller.tipodispositivo',
                verbose_name='tipo de dispositivo',
            ),
        ),
        migrations.RemoveField(
            model_name='trabajo',
            name='categoria_dispositivo',
        ),
    ]
