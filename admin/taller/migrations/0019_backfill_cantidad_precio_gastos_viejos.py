from django.db import migrations, models


def backfill(apps, schema_editor):
    """Antes de esta tanda, cantidad/precio_unitario solo existían para
    gastos de Repuestos: el resto quedó en NULL. Ahora que cantidad ×
    precio_unitario calcula el monto en cualquier categoría, se completan
    los viejos con cantidad=1 y precio_unitario=monto — matemáticamente
    fiel al monto que ya tenían (1 × monto = monto), sin inventar nada,
    así siguen siendo editables sin pedir de golpe un dato que no tenían."""
    Gasto = apps.get_model('taller', 'Gasto')
    Gasto.objects.filter(cantidad__isnull=True, precio_unitario__isnull=True).update(
        cantidad=1, precio_unitario=models.F('monto'),
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0018_limpiar_tercerizado_huerfano'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
