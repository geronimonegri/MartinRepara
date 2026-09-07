import django.db.models.deletion
from django.db import migrations, models


# La vieja categoría "taller" (alquiler del local, etc.) no tiene
# equivalente literal en el catálogo nuevo: el más parecido
# conceptualmente es "Alquiler".
MAPA_CATEGORIA_ANTIGUA = {
    'repuesto': 'Repuestos',
    'herramienta': 'Herramientas',
    'taller': 'Alquiler',
    'otro': 'Otro',
}


def migrar_categoria_y_proveedor(apps, schema_editor):
    Gasto = apps.get_model('taller', 'Gasto')
    CategoriaGasto = apps.get_model('taller', 'CategoriaGasto')
    Proveedor = apps.get_model('taller', 'Proveedor')

    categorias = {c.nombre: c for c in CategoriaGasto.objects.all()}

    for gasto in Gasto.objects.order_by('pk'):
        nombre_categoria = MAPA_CATEGORIA_ANTIGUA.get(gasto.categoria_antigua, 'Otro')
        gasto.categoria = categorias[nombre_categoria]

        if gasto.proveedor_antiguo:
            proveedor, _ = Proveedor.objects.get_or_create(
                nombre=gasto.proveedor_antiguo.strip(),
            )
            gasto.proveedor = proveedor

        if gasto.categoria_antigua == 'repuesto':
            gasto.cantidad = 1
            gasto.precio_unitario = gasto.monto
            gasto.stock_disponible = 1

        gasto.save(update_fields=[
            'categoria', 'proveedor', 'cantidad', 'precio_unitario', 'stock_disponible',
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0011_numeros_y_tipo_dispositivo'),
    ]

    operations = [
        migrations.RenameField(
            model_name='gasto', old_name='categoria', new_name='categoria_antigua',
        ),
        migrations.RenameField(
            model_name='gasto', old_name='proveedor', new_name='proveedor_antiguo',
        ),
        migrations.AddField(
            model_name='gasto',
            name='categoria',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.categoriagasto', verbose_name='categoría',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='subcategoria',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.subcategoriagasto', verbose_name='subcategoría',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='proveedor',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.proveedor', verbose_name='proveedor',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='tipo_dispositivo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos_repuesto', to='taller.tipodispositivo',
                verbose_name='tipo de dispositivo',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='tipo_repuesto',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.tiporepuesto', verbose_name='tipo de repuesto',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='marca',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.marca', verbose_name='marca',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='modelo',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.modelo', verbose_name='modelo',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='cantidad',
            field=models.PositiveIntegerField(blank=True, default=1, null=True, verbose_name='cantidad'),
        ),
        migrations.AddField(
            model_name='gasto',
            name='precio_unitario',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='precio unitario',
            ),
        ),
        migrations.AddField(
            model_name='gasto',
            name='stock_disponible',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='stock disponible'),
        ),
        migrations.RunPython(migrar_categoria_y_proveedor, noop),
        migrations.AlterField(
            model_name='gasto',
            name='categoria',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='gastos', to='taller.categoriagasto', verbose_name='categoría',
            ),
        ),
        migrations.RemoveField(model_name='gasto', name='categoria_antigua'),
        migrations.RemoveField(model_name='gasto', name='proveedor_antiguo'),
    ]
