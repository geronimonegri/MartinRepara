import django.db.models.deletion
from django.db import migrations, models


def migrar_fecha_pago_a_pagos(apps, schema_editor):
    Trabajo = apps.get_model('taller', 'Trabajo')
    Pago = apps.get_model('taller', 'Pago')
    for trabajo in Trabajo.objects.filter(fecha_pago__isnull=False, precio_acordado__isnull=False):
        Pago.objects.create(
            trabajo=trabajo,
            monto=trabajo.precio_acordado,
            forma_pago='efectivo',
            fecha=trabajo.fecha_pago,
            detalle='Migrado automáticamente desde fecha_pago.',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0005_categorizacion_dispositivos'),
    ]

    operations = [
        migrations.CreateModel(
            name='Pago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=10)),
                ('forma_pago', models.CharField(
                    choices=[
                        ('efectivo', 'Efectivo'),
                        ('transferencia', 'Transferencia'),
                        ('tarjeta', 'Tarjeta'),
                        ('otro', 'Otro'),
                    ],
                    max_length=20,
                    verbose_name='forma de pago',
                )),
                ('fecha', models.DateField()),
                ('detalle', models.TextField(blank=True, verbose_name='detalle')),
                ('trabajo', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='pagos',
                    to='taller.trabajo',
                    verbose_name='trabajo',
                )),
            ],
            options={
                'verbose_name': 'pago',
                'verbose_name_plural': 'pagos',
                'ordering': ['-fecha', '-id'],
            },
        ),
        migrations.RunPython(migrar_fecha_pago_a_pagos, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='trabajo',
            name='fecha_pago',
        ),
    ]
