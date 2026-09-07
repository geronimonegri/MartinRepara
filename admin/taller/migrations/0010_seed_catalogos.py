from django.db import migrations

TIPOS_DISPOSITIVO = [
    ('Celular', '#1c1c1a'),
    ('Tablet', '#7c3aed'),
    ('Consola', '#c9a24b'),
    ('Joystick', '#be185d'),
    ('Dispositivo de audio', '#1d4ed8'),
    ('Notebook', '#047857'),
    ('Otro', '#8891a5'),
]

CATEGORIAS_GASTO = [
    ('Repuestos', '#1c1c1a'),
    ('Herramientas', '#c9a24b'),
    ('Membresías', '#7c3aed'),
    ('Publicidad', '#1d4ed8'),
    ('Alquiler', '#047857'),
    ('Accesorios', '#b45309'),
    ('Tercerizado', '#be185d'),
    ('Otro', '#8891a5'),
]

SUBCATEGORIAS_GASTO = {
    'Herramientas': ['Equipo', 'De mano', 'Otro'],
    'Membresías': ['Canva', 'Claude', 'CapCut', 'Curso', 'Otro'],
    'Publicidad': ['Meta Ads', 'Instagram', 'WhatsApp', 'Otro'],
}

_REPUESTOS_CELULAR_TABLET = [
    'Chasis', 'Flex/pin de carga', 'Glass', 'Módulo', 'Flex', 'Tapa',
    'Speaker', 'Batería', 'Software', 'Microsoldadura', 'Otro',
]

TIPOS_REPUESTO = {
    'Celular': _REPUESTOS_CELULAR_TABLET,
    'Tablet': _REPUESTOS_CELULAR_TABLET,
    'Consola': ['Limpieza', 'Microsoldadura', 'Disco', 'Cooler', 'Otro'],
    'Notebook': ['Elemento electrónico', 'Bisagra', 'Memoria RAM', 'Otro'],
    'Dispositivo de audio': ['Elemento electrónico', 'Bisagra', 'Otro'],
}

MARCAS = {
    'Celular': ['Apple', 'Samsung', 'Otro'],
    'Tablet': ['Apple', 'Samsung', 'Otro'],
    'Consola': ['PS4', 'Xbox', 'Nintendo', 'Otro'],
    'Notebook': ['Otro'],
}


def cargar_catalogos(apps, schema_editor):
    TipoDispositivo = apps.get_model('taller', 'TipoDispositivo')
    CategoriaGasto = apps.get_model('taller', 'CategoriaGasto')
    SubcategoriaGasto = apps.get_model('taller', 'SubcategoriaGasto')
    TipoRepuesto = apps.get_model('taller', 'TipoRepuesto')
    Marca = apps.get_model('taller', 'Marca')

    tipos_dispositivo = {}
    for i, (nombre, color) in enumerate(TIPOS_DISPOSITIVO):
        tipos_dispositivo[nombre] = TipoDispositivo.objects.create(
            nombre=nombre, color=color, orden=i,
        )

    categorias_gasto = {}
    for i, (nombre, color) in enumerate(CATEGORIAS_GASTO):
        categorias_gasto[nombre] = CategoriaGasto.objects.create(
            nombre=nombre, color=color, orden=i,
        )

    for categoria_nombre, subcategorias in SUBCATEGORIAS_GASTO.items():
        categoria = categorias_gasto[categoria_nombre]
        for i, nombre in enumerate(subcategorias):
            SubcategoriaGasto.objects.create(nombre=nombre, categoria=categoria, orden=i)

    for tipo_nombre, repuestos in TIPOS_REPUESTO.items():
        tipo_dispositivo = tipos_dispositivo[tipo_nombre]
        for i, nombre in enumerate(repuestos):
            TipoRepuesto.objects.create(nombre=nombre, tipo_dispositivo=tipo_dispositivo, orden=i)

    for tipo_nombre, marcas in MARCAS.items():
        tipo_dispositivo = tipos_dispositivo[tipo_nombre]
        for i, nombre in enumerate(marcas):
            Marca.objects.create(nombre=nombre, tipo_dispositivo=tipo_dispositivo, orden=i)


def revertir_catalogos(apps, schema_editor):
    apps.get_model('taller', 'TipoRepuesto').objects.all().delete()
    apps.get_model('taller', 'Marca').objects.all().delete()
    apps.get_model('taller', 'SubcategoriaGasto').objects.all().delete()
    apps.get_model('taller', 'CategoriaGasto').objects.all().delete()
    apps.get_model('taller', 'TipoDispositivo').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('taller', '0009_catalogos'),
    ]

    operations = [
        migrations.RunPython(cargar_catalogos, revertir_catalogos),
    ]
