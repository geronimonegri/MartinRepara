import calendar
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from taller import analytics
from taller.forms import _sincronizar_gasto_tercerizado
from taller.models import (
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

# Semilla fija: mismo resultado cada vez que se corre (para las capturas).
SEED = 20260907

NOMBRES = [
    'Nahuel', 'Marcos', 'Ezequiel', 'Lucía', 'Franco', 'Valentina', 'Camila', 'Rocío',
    'Bruno', 'Julieta', 'Agustín', 'Milagros', 'Tomás', 'Sofía', 'Federico', 'Micaela',
    'Ignacio', 'Florencia', 'Matías', 'Antonella', 'Joaquín', 'Candela', 'Gonzalo', 'Martina',
    'Leandro', 'Abril', 'Emiliano', 'Delfina', 'Santiago', 'Guadalupe', 'Maximiliano', 'Catalina',
    'Ramiro', 'Victoria', 'Facundo', 'Ayelén', 'Lautaro', 'Morena', 'Agustina', 'Thiago',
]
APELLIDOS = [
    'Torres', 'Díaz', 'Sosa', 'Fernández', 'Gómez', 'Ruiz', 'López', 'Medina',
    'Aquino', 'González', 'Rodríguez', 'Martínez', 'Pérez', 'García', 'Romero', 'Sánchez',
    'Álvarez', 'Suárez', 'Molina', 'Acosta', 'Herrera', 'Benítez', 'Ledesma', 'Correa',
    'Ríos', 'Ojeda', 'Cabrera', 'Paz', 'Silva', 'Vega',
]
CODIGOS_AREA = [('11', 70), ('351', 12), ('341', 10), ('261', 8)]

FORMAS_PAGO = [Pago.FormaPago.EFECTIVO, Pago.FormaPago.TRANSFERENCIA, Pago.FormaPago.TARJETA]

DISPOSITIVOS_DEF = [
    ('Celular', 55), ('Consola', 20), ('Joystick', 10), ('Notebook', 10),
    ('Tablet', 3), ('Dispositivo de audio', 2),
]

CELULAR_MARCAS_DEF = [('Samsung', 45), ('Apple', 40), ('Otro', 15)]
CONSOLA_MARCAS_DEF = [('PS4', 30), ('PS5', 30), ('Xbox', 22), ('Nintendo Switch', 18)]
NOTEBOOK_MARCAS_DEF = [('Otro', 30), ('Lenovo', 25), ('HP', 20), ('Dell', 15), ('Acer', 10)]
MARCAS_DEF_POR_DISPOSITIVO = {
    'Celular': CELULAR_MARCAS_DEF, 'Tablet': CELULAR_MARCAS_DEF,
    'Consola': CONSOLA_MARCAS_DEF, 'Notebook': NOTEBOOK_MARCAS_DEF,
}

SAMSUNG_MODELOS = ['Galaxy A52', 'Galaxy A34', 'Galaxy S23', 'Galaxy A32']
APPLE_MODELOS = ['iPhone 11', 'iPhone 12', 'iPhone 13', 'iPhone 14', 'iPhone 15']

# (nombre_tipo_reparacion, peso, precio_min, precio_max, nombre_tipo_repuesto_o_None, [descripciones])
CELULAR_REPARACIONES_DEF = [
    ('Cambio de módulo', 26, 80000, 150000, 'Módulo', [
        'no responde al tacto en una zona de la pantalla',
        'la pantalla no toca bien, hay que reiniciarlo',
        'toca solo, sin que lo toquen',
    ]),
    ('Cambio de batería', 22, 35000, 60000, 'Batería', [
        'se descarga muy rápido',
        'se apaga solo aunque tenga batería',
        'la batería está hinchada',
    ]),
    ('Cambio de glass', 16, 40000, 70000, 'Glass', [
        'se cayó y se rompió el vidrio',
        'pantalla rota pero prende bien',
        'se rajó el glass, la pantalla anda',
    ]),
    ('Software', 12, 15000, 30000, None, [
        'no arranca, se queda en el logo',
        'muy lento, se cuelga todo el tiempo',
        'se reinicia solo',
    ]),
    ('Cambio de flex/pin de carga', 9, 25000, 45000, 'Flex/pin de carga', [
        'no carga',
        'carga mal, hay que mover el cable para que entre',
        'no reconoce el cargador',
    ]),
    ('Microsoldadura', 8, 60000, 120000, None, [
        'se mojó y no prende',
        'no prende después de una caída',
        'se apagó de golpe y no arranca más',
    ]),
    ('Cambio de tapa', 4, 20000, 35000, 'Tapa', [
        'la tapa trasera está rota',
        'se rompió el vidrio de atrás',
    ]),
    ('Arreglo/cambio de chasis', 2, 50000, 90000, 'Chasis', [
        'el marco está doblado',
        'se dobló en una caída',
    ]),
    ('Cambio de flex', 1, 30000, 55000, 'Flex', [
        'no funciona el botón de volumen',
        'falla el flex de la cámara',
    ]),
]

CONSOLA_REPARACIONES_DEF = [
    ('Limpieza', 38, 25000, 40000, None, [
        'hace mucho ruido el ventilador',
        'se calienta y se apaga',
        'junta mucho polvo, quiere una limpieza',
    ]),
    ('Cambio de disco', 32, 40000, 70000, 'Disco', [
        'no lee discos',
        'hace ruido raro al leer un disco',
        'expulsa el disco solo',
    ]),
    ('Cambio de cooler', 15, 30000, 50000, 'Cooler', [
        'se apaga por calor',
        'el ventilador hace un ruido feo',
    ]),
    ('Microsoldadura', 15, 70000, 130000, None, [
        'no prende, luz roja',
        'se apagó de golpe y no prende más',
    ]),
]

JOYSTICK_REPARACIONES_DEF = [
    ('Cambio de módulo analógico', 70, 15000, 30000, 'Módulo analógico', [
        'el stick se mueve solo',
        'hace drift para un lado',
        'el joystick no responde bien de un lado',
    ]),
    ('Limpieza', 22, 12000, 20000, None, [
        'los botones están duros',
        'no responde bien algún botón',
    ]),
    ('Otro', 8, 10000, 20000, None, [
        'revisión general',
    ]),
]

NOTEBOOK_REPARACIONES_DEF = [
    ('Elemento electrónico', 32, 90000, 200000, 'Elemento electrónico', [
        'no prende',
        'se apaga solo',
        'no carga la batería',
    ]),
    ('Cambio de bisagra', 28, 60000, 100000, 'Bisagra', [
        'la bisagra está rota',
        'la pantalla no se sostiene, se cae',
    ]),
    ('Memoria RAM', 24, 70000, 120000, 'Memoria RAM', [
        'quiere agregarle más memoria, anda lento',
        'va muy lento con varios programas abiertos',
    ]),
    ('Otro', 16, 60000, 100000, None, [
        'revisión general',
        'limpieza y cambio de pasta térmica',
    ]),
]

AUDIO_REPARACIONES_DEF = [
    ('Elemento electrónico', 50, 20000, 45000, 'Elemento electrónico', [
        'no suena de un lado',
        'no prende',
    ]),
    ('Bisagra', 20, 15000, 30000, 'Bisagra', [
        'se rompió donde se dobla',
    ]),
    ('Otro', 30, 15000, 35000, None, [
        'revisión general',
    ]),
]

REPARACIONES_DEF_POR_DISPOSITIVO = {
    'Celular': CELULAR_REPARACIONES_DEF, 'Tablet': CELULAR_REPARACIONES_DEF,
    'Consola': CONSOLA_REPARACIONES_DEF, 'Joystick': JOYSTICK_REPARACIONES_DEF,
    'Notebook': NOTEBOOK_REPARACIONES_DEF, 'Dispositivo de audio': AUDIO_REPARACIONES_DEF,
}

# Costo de compra del repuesto: siempre bien por debajo del precio cobrado
# en la reparación correspondiente, para que quede un margen razonable.
PRECIO_COMPRA_REPUESTO = {
    ('Celular', 'Módulo'): (45000, 65000), ('Tablet', 'Módulo'): (45000, 65000),
    ('Celular', 'Batería'): (15000, 25000), ('Tablet', 'Batería'): (15000, 25000),
    ('Celular', 'Glass'): (18000, 30000), ('Tablet', 'Glass'): (18000, 30000),
    ('Celular', 'Flex/pin de carga'): (12000, 20000), ('Tablet', 'Flex/pin de carga'): (12000, 20000),
    ('Celular', 'Tapa'): (8000, 15000), ('Tablet', 'Tapa'): (8000, 15000),
    ('Celular', 'Chasis'): (20000, 35000), ('Tablet', 'Chasis'): (20000, 35000),
    ('Celular', 'Flex'): (12000, 22000), ('Tablet', 'Flex'): (12000, 22000),
    ('Consola', 'Disco'): (18000, 28000),
    ('Consola', 'Cooler'): (12000, 20000),
    ('Joystick', 'Módulo analógico'): (5000, 9000),
    ('Notebook', 'Bisagra'): (20000, 32000), ('Dispositivo de audio', 'Bisagra'): (10000, 16000),
    ('Notebook', 'Memoria RAM'): (35000, 55000),
    ('Notebook', 'Elemento electrónico'): (40000, 70000),
    ('Dispositivo de audio', 'Elemento electrónico'): (8000, 18000),
}

TERCERIZABLES = {'Software', 'Microsoldadura'}
DETALLE_TERCERIZADO = {
    'Software': ['reinstalación de sistema y respaldo de datos', 'diagnóstico y reparación de software'],
    'Microsoldadura': [
        'microsoldadura de la placa', 'cambio de IC de carga por microsoldadura',
        'reparación de pista dañada',
    ],
}


def _elegir(rng, pares):
    valores = [v for v, _ in pares]
    pesos = [w for _, w in pares]
    return rng.choices(valores, weights=pesos, k=1)[0]


def _precio(rng, minimo, maximo, paso=500):
    pasos = max((maximo - minimo) // paso, 0)
    return Decimal(minimo + rng.randint(0, pasos) * paso)


def _redondear(monto, paso=500):
    return Decimal(int(monto / paso) * paso)


def _capitalizar(texto):
    return texto[0].upper() + texto[1:]


def _sumar_meses(anio, mes, n):
    total = (anio * 12 + (mes - 1)) + n
    return total // 12, total % 12 + 1


def _dict_por_nombre(queryset):
    return {obj.nombre: obj for obj in queryset}


def _compilar_reparaciones(definiciones, dic_reparacion, dic_repuesto):
    compiladas = []
    for nombre, peso, pmin, pmax, repuesto_nombre, descripciones in definiciones:
        compiladas.append({
            'tipo_reparacion': dic_reparacion[nombre],
            'peso': peso,
            'precio_min': pmin, 'precio_max': pmax,
            'repuesto_nombre': repuesto_nombre,
            'descripciones': descripciones,
        })
    return compiladas


class _StockRepuestos:
    """Sigue el stock disponible de cada (tipo_dispositivo, tipo_repuesto)
    a medida que se van comprando/usando repuestos durante la generación,
    en el mismo orden cronológico en que se van creando los registros."""

    def __init__(self):
        self._por_tipo = {}

    def agregar(self, tipo_dispositivo_id, nombre_repuesto, gasto, cantidad):
        clave = (tipo_dispositivo_id, nombre_repuesto)
        self._por_tipo.setdefault(clave, []).append([gasto, cantidad])

    def disponible(self, tipo_dispositivo_id, nombre_repuesto):
        clave = (tipo_dispositivo_id, nombre_repuesto)
        return sum(restante for _, restante in self._por_tipo.get(clave, []))

    def usar(self, tipo_dispositivo_id, nombre_repuesto, fecha_limite):
        clave = (tipo_dispositivo_id, nombre_repuesto)
        for par in self._por_tipo.get(clave, []):
            gasto, restante = par
            if restante > 0 and gasto.fecha <= fecha_limite:
                par[1] -= 1
                return gasto
        return None


def _cargar_catalogos():
    tipos = {
        nombre: TipoDispositivo.objects.get(nombre=nombre)
        for nombre in ['Celular', 'Tablet', 'Consola', 'Joystick', 'Notebook', 'Dispositivo de audio']
    }

    # Ajustes de catálogo ad-hoc (mismo mecanismo que el botón "+" de los
    # formularios): PS5 no estaba seedeada, "Nintendo" pasa a "Nintendo
    # Switch", y Joystick/Audio no tenían marca propia (necesaria para
    # cargar un Gasto de categoría Repuestos, que la exige siempre).
    Marca.objects.filter(nombre='Nintendo', tipo_dispositivo=tipos['Consola']).update(nombre='Nintendo Switch')
    Marca.objects.get_or_create(nombre='PS5', tipo_dispositivo=tipos['Consola'], defaults={'orden': 10})
    for nombre in ['Lenovo', 'HP', 'Dell', 'Acer']:
        Marca.objects.get_or_create(nombre=nombre, tipo_dispositivo=tipos['Notebook'], defaults={'orden': 10})
    marca_generica_joystick, _ = Marca.objects.get_or_create(nombre='Genérico', tipo_dispositivo=tipos['Joystick'])
    marca_generica_audio, _ = Marca.objects.get_or_create(
        nombre='Genérico', tipo_dispositivo=tipos['Dispositivo de audio']
    )
    TipoRepuesto.objects.get_or_create(
        nombre='Módulo analógico', tipo_dispositivo=tipos['Joystick'], defaults={'orden': 0}
    )

    marcas = {nombre: _dict_por_nombre(Marca.objects.filter(tipo_dispositivo=tipo)) for nombre, tipo in tipos.items()}
    reparaciones_raw = {
        nombre: _dict_por_nombre(TipoReparacion.objects.filter(tipo_dispositivo=tipo))
        for nombre, tipo in tipos.items()
    }
    repuestos_raw = {
        nombre: _dict_por_nombre(TipoRepuesto.objects.filter(tipo_dispositivo=tipo))
        for nombre, tipo in tipos.items()
    }

    reparaciones = {
        nombre: _compilar_reparaciones(REPARACIONES_DEF_POR_DISPOSITIVO[nombre], reparaciones_raw[nombre], repuestos_raw[nombre])
        for nombre in tipos
    }

    modelos = {}
    for nombre_marca, modelos_nombres in [('Samsung', SAMSUNG_MODELOS), ('Apple', APPLE_MODELOS)]:
        marca_obj = marcas['Celular'][nombre_marca]
        modelos[('Celular', nombre_marca)] = [
            Modelo.objects.get_or_create(nombre=m, marca=marca_obj)[0] for m in modelos_nombres
        ]
    modelos[('Tablet', 'Apple')] = [Modelo.objects.get_or_create(nombre='iPad', marca=marcas['Tablet']['Apple'])[0]]
    modelos[('Tablet', 'Samsung')] = [
        Modelo.objects.get_or_create(nombre='Galaxy Tab A8', marca=marcas['Tablet']['Samsung'])[0]
    ]

    marcas_repuesto = {
        'Celular': list(marcas['Celular'].values()),
        'Tablet': list(marcas['Tablet'].values()),
        'Consola': list(marcas['Consola'].values()),
        'Notebook': list(marcas['Notebook'].values()),
        'Joystick': [marca_generica_joystick],
        'Dispositivo de audio': [marca_generica_audio],
    }

    proveedores_repuesto = [
        Proveedor.objects.get_or_create(nombre='Distribuidora Norte')[0],
        Proveedor.objects.get_or_create(nombre='RepuestosYa')[0],
        Proveedor.objects.get_or_create(nombre='ImportCel')[0],
        Proveedor.objects.get_or_create(nombre='TecnoPartes')[0],
    ]
    terceros = [
        Tercero.objects.get_or_create(nombre='Taller Amigo', defaults={'telefono': '11-9988-7766'})[0],
        Tercero.objects.get_or_create(nombre='ElectroFix', defaults={'telefono': '11-2233-4400'})[0],
        Tercero.objects.get_or_create(nombre='TecnoService', defaults={'telefono': '11-5566-7700'})[0],
    ]

    categorias = {
        nombre: CategoriaGasto.objects.get(nombre=nombre)
        for nombre in ['Repuestos', 'Alquiler', 'Membresías', 'Publicidad', 'Herramientas', 'Accesorios']
    }
    subcategorias_membresias = _dict_por_nombre(SubcategoriaGasto.objects.filter(categoria=categorias['Membresías']))
    subcategorias_publicidad = _dict_por_nombre(SubcategoriaGasto.objects.filter(categoria=categorias['Publicidad']))

    return {
        'tipos': tipos, 'marcas': marcas, 'reparaciones': reparaciones, 'modelos': modelos,
        'marcas_repuesto': marcas_repuesto, 'repuestos': repuestos_raw,
        'proveedores_repuesto': proveedores_repuesto, 'terceros': terceros,
        'categorias': categorias,
        'subcategorias_membresias': subcategorias_membresias,
        'subcategorias_publicidad': subcategorias_publicidad,
        'tipos_por_id': {t.id: t for t in tipos.values()},
    }


def _generar_pool_clientes(rng):
    nombres = list(NOMBRES)
    rng.shuffle(nombres)
    pool = []
    for nombre in nombres[:40]:
        apellido = rng.choice(APELLIDOS)
        codigo = _elegir(rng, CODIGOS_AREA)
        telefono = f'{codigo}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}'
        pool.append((f'{nombre} {apellido}', telefono))
    return pool


def _elegir_cliente(rng, clientes_pool, clientes_creados):
    if len(clientes_creados) < len(clientes_pool) and (not clientes_creados or rng.random() < 0.55):
        nombre, telefono = clientes_pool[len(clientes_creados)]
        cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)
        clientes_creados.append(cliente)
        return cliente
    return rng.choice(clientes_creados)


def _calcular_meses(hoy):
    meses = []
    anio, mes = 2025, 9
    while (anio, mes) <= (hoy.year, hoy.month):
        meses.append((anio, mes))
        anio, mes = _sumar_meses(anio, mes, 1)
    return meses


def _calcular_objetivos_por_mes(meses, hoy):
    n = len(meses)
    objetivos = []
    for i, (anio, mes) in enumerate(meses):
        base = 8 + (25 - 8) * i / max(n - 1, 1)
        objetivo = round(base)
        if (anio, mes) == (hoy.year, hoy.month):
            dias_en_mes = calendar.monthrange(anio, mes)[1]
            objetivo = max(1, round(objetivo * hoy.day / dias_en_mes))
        objetivos.append(objetivo)
    return objetivos


def _estado_trabajo(fecha_ingreso, hoy, rng):
    dias = (hoy - fecha_ingreso).days
    if dias > 30:
        return Trabajo.Estado.ENTREGADO if rng.random() < 0.95 else Trabajo.Estado.LISTO
    if dias <= 2:
        return Trabajo.Estado.RECIBIDO
    if dias <= 6:
        return rng.choices(
            [Trabajo.Estado.RECIBIDO, Trabajo.Estado.EN_REPARACION], weights=[30, 70]
        )[0]
    if dias <= 14:
        return rng.choices(
            [Trabajo.Estado.EN_REPARACION, Trabajo.Estado.LISTO], weights=[40, 60]
        )[0]
    if dias <= 25:
        return rng.choices(
            [Trabajo.Estado.LISTO, Trabajo.Estado.ENTREGADO], weights=[35, 65]
        )[0]
    return rng.choices([Trabajo.Estado.LISTO, Trabajo.Estado.ENTREGADO], weights=[15, 85])[0]


def _crear_pagos(rng, trabajo, hoy):
    if trabajo.estado == Trabajo.Estado.ENTREGADO:
        precio = trabajo.precio_acordado
        if rng.random() < 0.3:
            sena = _redondear(precio * Decimal(str(round(rng.uniform(0.3, 0.5), 2))))
            resto = precio - sena
            fecha_sena = min(trabajo.fecha_ingreso + timedelta(days=rng.randint(0, 2)), hoy)
            Pago.objects.create(
                trabajo=trabajo, monto=sena, forma_pago=rng.choice(FORMAS_PAGO), fecha=fecha_sena
            )
            Pago.objects.create(
                trabajo=trabajo, monto=resto, forma_pago=rng.choice(FORMAS_PAGO),
                fecha=trabajo.fecha_entrega,
            )
        else:
            Pago.objects.create(
                trabajo=trabajo, monto=precio, forma_pago=rng.choice(FORMAS_PAGO),
                fecha=trabajo.fecha_entrega,
            )
    elif trabajo.estado == Trabajo.Estado.LISTO and rng.random() < 0.6:
        precio = trabajo.precio_acordado
        sena = _redondear(precio * Decimal(str(round(rng.uniform(0.3, 0.6), 2))))
        fecha_pago = min(trabajo.fecha_ingreso + timedelta(days=rng.randint(0, 3)), hoy)
        Pago.objects.create(
            trabajo=trabajo, monto=sena, forma_pago=rng.choice(FORMAS_PAGO), fecha=fecha_pago
        )


def _reponer_stock(rng, ctx, stock, tipo_dispositivo, repuesto_nombre, cantidad_necesaria, fecha_compra):
    # Reposición "justo a tiempo": solo compra lo que falta para cubrir la
    # demanda del mes, descontando lo que ya quedó de compras anteriores
    # (si no, se reponen unidades de más todos los meses y los gastos de
    # Repuestos quedan inflados sin ingresos que los acompañen).
    ya_disponible = stock.disponible(tipo_dispositivo.id, repuesto_nombre)
    faltante = cantidad_necesaria + rng.randint(1, 5) - ya_disponible
    if faltante <= 0:
        return
    restante = faltante
    marcas_disponibles = ctx['marcas_repuesto'].get(tipo_dispositivo.nombre)
    tipo_repuesto = ctx['repuestos'][tipo_dispositivo.nombre][repuesto_nombre]
    precio_min, precio_max = PRECIO_COMPRA_REPUESTO[(tipo_dispositivo.nombre, repuesto_nombre)]
    while restante > 0:
        lote = min(restante, rng.randint(2, 10))
        proveedor = rng.choice(ctx['proveedores_repuesto'])
        marca = rng.choice(marcas_disponibles) if marcas_disponibles else None
        precio_unitario = _precio(rng, precio_min, precio_max)
        gasto = Gasto.objects.create(
            descripcion=f'{repuesto_nombre} para {tipo_dispositivo.nombre.lower()}',
            categoria=ctx['categorias']['Repuestos'], proveedor=proveedor, fecha=fecha_compra,
            tipo_dispositivo=tipo_dispositivo, tipo_repuesto=tipo_repuesto, marca=marca,
            cantidad=lote, precio_unitario=precio_unitario, monto=lote * precio_unitario,
        )
        stock.agregar(tipo_dispositivo.id, repuesto_nombre, gasto, lote)
        restante -= lote


def _generar_mes(rng, ctx, anio, mes, cantidad_objetivo, hoy, stock, clientes_pool, clientes_creados):
    dias_en_mes = calendar.monthrange(anio, mes)[1]
    dia_max = hoy.day if (anio, mes) == (hoy.year, hoy.month) else dias_en_mes

    plan = []
    for _ in range(cantidad_objetivo):
        tipo_disp_nombre = _elegir(rng, DISPOSITIVOS_DEF)
        tipo_dispositivo = ctx['tipos'][tipo_disp_nombre]
        opciones = ctx['reparaciones'][tipo_disp_nombre]
        elegida = _elegir(rng, [(op, op['peso']) for op in opciones])
        precio = _precio(rng, elegida['precio_min'], elegida['precio_max'])
        descripcion = rng.choice(elegida['descripciones'])

        marca = None
        modelo = None
        marcas_def = MARCAS_DEF_POR_DISPOSITIVO.get(tipo_disp_nombre)
        if marcas_def:
            nombre_marca = _elegir(rng, marcas_def)
            marca = ctx['marcas'][tipo_disp_nombre][nombre_marca]
            modelos_posibles = ctx['modelos'].get((tipo_disp_nombre, nombre_marca))
            if modelos_posibles and rng.random() < 0.7:
                modelo = rng.choice(modelos_posibles)

        fecha_ingreso = date(anio, mes, rng.randint(1, dia_max))

        plan.append({
            'tipo_dispositivo': tipo_dispositivo, 'marca': marca, 'modelo': modelo,
            'tipo_reparacion': elegida['tipo_reparacion'], 'repuesto_nombre': elegida['repuesto_nombre'],
            'precio': precio, 'descripcion': descripcion, 'fecha_ingreso': fecha_ingreso,
        })

    plan.sort(key=lambda item: item['fecha_ingreso'])

    necesidad = {}
    for item in plan:
        if item['repuesto_nombre']:
            clave = (item['tipo_dispositivo'].id, item['repuesto_nombre'])
            necesidad[clave] = necesidad.get(clave, 0) + 1

    fecha_compra = date(anio, mes, 1)
    for (tipo_disp_id, repuesto_nombre), cantidad_necesaria in necesidad.items():
        _reponer_stock(
            rng, ctx, stock, ctx['tipos_por_id'][tipo_disp_id], repuesto_nombre,
            cantidad_necesaria, fecha_compra,
        )

    for item in plan:
        cliente = _elegir_cliente(rng, clientes_pool, clientes_creados)
        estado = _estado_trabajo(item['fecha_ingreso'], hoy, rng)
        fecha_entrega = None
        if estado == Trabajo.Estado.ENTREGADO:
            dias = (hoy - item['fecha_ingreso']).days
            fecha_entrega = item['fecha_ingreso'] + timedelta(days=rng.randint(1, max(1, min(6, dias))))

        trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=item['tipo_dispositivo'],
            marca=item['marca'], modelo=item['modelo'], tipo_reparacion=item['tipo_reparacion'],
            descripcion_problema=_capitalizar(item['descripcion']), estado=estado,
            precio_acordado=item['precio'], fecha_ingreso=item['fecha_ingreso'], fecha_entrega=fecha_entrega,
        )

        if item['repuesto_nombre']:
            gasto_repuesto = stock.usar(
                item['tipo_dispositivo'].id, item['repuesto_nombre'], item['fecha_ingreso']
            )
            if gasto_repuesto:
                RepuestoUsado.objects.create(trabajo=trabajo, gasto=gasto_repuesto, cantidad=1)

        if item['tipo_reparacion'].nombre in TERCERIZABLES and rng.random() < 0.9:
            tercero = rng.choice(ctx['terceros'])
            monto = _redondear(trabajo.precio_acordado * Decimal(str(round(rng.uniform(0.3, 0.55), 2))))
            trabajo.tercero = tercero
            trabajo.tercerizado_detalle = rng.choice(DETALLE_TERCERIZADO[item['tipo_reparacion'].nombre])
            trabajo.tercerizado_monto = monto
            trabajo.save()
            _sincronizar_gasto_tercerizado(trabajo)

        _crear_pagos(rng, trabajo, hoy)

    return len(plan)


def _crear_gastos_fijos_del_mes(rng, ctx, anio, mes):
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    Gasto.objects.create(
        descripcion='Alquiler del local', monto=_precio(rng, 90000, 110000),
        categoria=ctx['categorias']['Alquiler'], fecha=date(anio, mes, min(5, ultimo_dia)),
    )
    for nombre_sub in ['Canva', 'Claude', 'CapCut']:
        Gasto.objects.create(
            descripcion=f'Suscripción {nombre_sub}', monto=_precio(rng, 3000, 9000),
            categoria=ctx['categorias']['Membresías'],
            subcategoria=ctx['subcategorias_membresias'].get(nombre_sub),
            fecha=date(anio, mes, min(10, ultimo_dia)),
        )
    Gasto.objects.create(
        descripcion='Meta Ads', monto=_precio(rng, 15000, 35000),
        categoria=ctx['categorias']['Publicidad'],
        subcategoria=ctx['subcategorias_publicidad'].get('Meta Ads'),
        fecha=date(anio, mes, min(8, ultimo_dia)),
    )
    if rng.random() < 0.35:
        Gasto.objects.create(
            descripcion=rng.choice(
                ['Kit de destornilladores', 'Estación de soldadura', 'Pistola de calor', 'Multímetro']
            ),
            monto=_precio(rng, 8000, 40000), categoria=ctx['categorias']['Herramientas'],
            fecha=date(anio, mes, rng.randint(1, ultimo_dia)),
        )
    if rng.random() < 0.3:
        Gasto.objects.create(
            descripcion=rng.choice(['Fundas y protectores', 'Cables varios', 'Cargadores genéricos']),
            monto=_precio(rng, 5000, 20000), categoria=ctx['categorias']['Accesorios'],
            fecha=date(anio, mes, rng.randint(1, ultimo_dia)),
        )


def _ajustar_balance_meses(rng, ctx, meses, objetivo_negativos=2):
    """Deja exactamente `objetivo_negativos` meses con balance negativo (el
    resto de la actividad ya sale creíble sola; esto solo pule los casos
    límite): a los meses positivos más ajustados les agrega una compra
    grande de herramientas para que pasen a negativo, y a los meses
    negativos "de más" les agrega un trabajo puntual de buen precio (con
    su pago) para que vuelvan a positivo, dejando negativos solo los
    peores."""
    balances = [(anio, mes, analytics.balance_mensual(anio, mes)) for anio, mes in meses]
    negativos = [b for b in balances if b[2] < 0]
    positivos = sorted((b for b in balances if b[2] >= 0), key=lambda b: b[2])

    faltan = objetivo_negativos - len(negativos)
    if faltan > 0:
        for anio, mes, balance in positivos[:faltan]:
            extra = balance + Decimal(rng.randint(8000, 25000))
            dia = min(20, calendar.monthrange(anio, mes)[1])
            Gasto.objects.create(
                descripcion='Compra de equipamiento de diagnóstico', monto=extra,
                categoria=ctx['categorias']['Herramientas'], fecha=date(anio, mes, dia),
            )
    elif faltan < 0:
        a_corregir = sorted(negativos, key=lambda b: b[2], reverse=True)[: -faltan]
        cliente_comodin = Cliente.objects.create(
            nombre='Estudio Contable Rivadavia', telefono='11-4444-5555'
        )
        tipo_reparacion_software = next(
            op['tipo_reparacion'] for op in ctx['reparaciones']['Celular']
            if op['tipo_reparacion'].nombre == 'Software'
        )
        for anio, mes, balance in a_corregir:
            ultimo_dia = calendar.monthrange(anio, mes)[1]
            dia = min(15, ultimo_dia)
            fecha = date(anio, mes, dia)
            precio = abs(balance) + Decimal(rng.randint(5000, 20000))
            trabajo = Trabajo.objects.create(
                cliente=cliente_comodin, tipo_dispositivo=ctx['tipos']['Celular'],
                tipo_reparacion=tipo_reparacion_software,
                descripcion_problema='Actualización y mantenimiento de varios equipos de una empresa',
                estado=Trabajo.Estado.ENTREGADO, precio_acordado=precio,
                fecha_ingreso=fecha, fecha_entrega=fecha,
            )
            Pago.objects.create(
                trabajo=trabajo, monto=precio, forma_pago=Pago.FormaPago.TRANSFERENCIA, fecha=fecha,
            )


class Command(BaseCommand):
    """Genera datos de demostración abundantes y realistas (12 meses de
    actividad, ~180 trabajos) para mostrar la app en capturas/README.

    Usa una semilla fija (random.Random(SEED)) para que el resultado sea
    reproducible corrida tras corrida. No toca los catálogos (TipoDispositivo,
    CategoriaGasto, Marca, etc. — salvo agregar/renombrar algunos ítems ad-hoc,
    igual que haría el botón "+" de un formulario): esos sobreviven al reseed.
    """

    help = 'Genera datos de demostración abundantes (12 meses, ~180 trabajos) para Trabajo/Gasto/Cliente/Pago.'

    def handle(self, *args, **options):
        rng = random.Random(SEED)
        hoy = timezone.now().date()

        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(username='martin', email='', password='martinrepara2026')
            self.stdout.write(self.style.SUCCESS(
                'Superusuario creado: usuario "martin" / contraseña "martinrepara2026".'
            ))

        RepuestoUsado.objects.all().delete()
        Pago.objects.all().delete()
        Trabajo.objects.all().delete()
        Gasto.objects.all().delete()
        Cliente.objects.all().delete()
        Correlativo.objects.filter(
            tipo__in=[Correlativo.TRABAJO, Correlativo.GASTO, Correlativo.PAGO]
        ).update(ultimo_numero=0)

        ctx = _cargar_catalogos()
        clientes_pool = _generar_pool_clientes(rng)
        clientes_creados = []
        stock = _StockRepuestos()

        meses = _calcular_meses(hoy)
        objetivos = _calcular_objetivos_por_mes(meses, hoy)

        total_trabajos = 0
        for (anio, mes), objetivo in zip(meses, objetivos):
            total_trabajos += _generar_mes(
                rng, ctx, anio, mes, objetivo, hoy, stock, clientes_pool, clientes_creados
            )
            _crear_gastos_fijos_del_mes(rng, ctx, anio, mes)

        _ajustar_balance_meses(rng, ctx, meses)

        self.stdout.write(self.style.SUCCESS(
            f'Seed OK: {Cliente.objects.count()} clientes, {Trabajo.objects.count()} trabajos, '
            f'{Gasto.objects.count()} gastos, {Pago.objects.count()} pagos, '
            f'{RepuestoUsado.objects.count()} repuestos usados.'
        ))
