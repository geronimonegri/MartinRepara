"""Funciones de análisis para armar el futuro dashboard.

Todas devuelven datos "crudos" (Decimal, dict, querysets) listos para
que una vista los formatee. No hay lógica de presentación acá.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import CategoriaGasto, Gasto, Pago, RepuestoUsado, Trabajo


def balance_mensual(anio, mes):
    """Ingresos (pagos registrados en el mes) menos gastos del mes."""
    return Pago.objects.total_mes(anio, mes) - Gasto.objects.total_mes(anio, mes)


def gastos_por_categoria(anio, mes):
    """Total de gastos del mes, agrupado por categoría."""
    return Gasto.objects.por_categoria_mes(anio, mes)


def pagos_por_categoria_dispositivo(anio, mes):
    """Total de pagos del mes, agrupado por categoría de dispositivo del trabajo asociado."""
    return Pago.objects.por_categoria_dispositivo_mes(anio, mes)


def tercerizado_mensual(anio, mes):
    """Gasto de categoría "Tercerizado" del mes y su porcentaje sobre el
    total de gastos del mes (ambos por Gasto.fecha, igual que el resto de
    Balance — no depende de fecha_ingreso ni fecha_entrega). pct queda en
    None si no hubo gastos ese mes (no está definida la división)."""
    monto = Gasto.objects.filter(
        categoria__nombre='Tercerizado', fecha__year=anio, fecha__month=mes
    ).aggregate(total=Sum('monto'))['total'] or Decimal('0')
    gastos_total = Gasto.objects.total_mes(anio, mes)
    pct = (monto / gastos_total * 100) if gastos_total else None
    return {'monto': monto, 'pct': pct}


def mes_anterior(anio, mes):
    """Año/mes inmediatamente anterior al dado (maneja el cruce de año)."""
    if mes == 1:
        return anio - 1, 12
    return anio, mes - 1


def mes_siguiente(anio, mes):
    """Año/mes inmediatamente siguiente al dado (maneja el cruce de año)."""
    if mes == 12:
        return anio + 1, 1
    return anio, mes + 1


def comparacion_mes_anterior(anio, mes):
    """Balance del mes consultado vs. el mes inmediatamente anterior.

    variacion_pct queda en None cuando el balance del mes anterior es 0,
    ya que la variación porcentual no está definida en ese caso.
    """
    anio_prev, mes_prev = mes_anterior(anio, mes)

    balance_actual = balance_mensual(anio, mes)
    balance_anterior = balance_mensual(anio_prev, mes_prev)

    if balance_anterior == 0:
        variacion_pct = None
    else:
        variacion_pct = (
            (balance_actual - balance_anterior) / abs(balance_anterior) * 100
        )

    return {
        'anio': anio,
        'mes': mes,
        'balance_actual': balance_actual,
        'anio_anterior': anio_prev,
        'mes_anterior': mes_prev,
        'balance_anterior': balance_anterior,
        'variacion_pct': variacion_pct,
    }


def ingresos_pendientes():
    """Suma de precio_acordado de trabajos en estado 'listo' (sin filtro de fecha)."""
    total = Trabajo.objects.filter(estado=Trabajo.Estado.LISTO).aggregate(
        total=Sum('precio_acordado')
    )['total']
    return total or Decimal('0')


def balance_ultimos_n_meses(anio, mes, n=6):
    """Balance mensual de los últimos `n` meses, terminando en anio/mes (inclusive).

    Devuelve una lista ordenada del más antiguo al más reciente:
    [{'anio': .., 'mes': .., 'balance': Decimal(..)}, ...]
    """
    periodos = []
    a, m = anio, mes
    for _ in range(n):
        periodos.append((a, m))
        a, m = mes_anterior(a, m)
    periodos.reverse()

    return [
        {'anio': a, 'mes': m, 'balance': balance_mensual(a, m)}
        for a, m in periodos
    ]


# ---------------------------------------------------------------------------
# Estadísticas (Tanda 6): todo lo de acá abajo trabaja con un rango de fechas
# [desde, hasta] en vez de mes calendario. desde=None significa "sin piso"
# (opción de período "Todo"). Los trabajos se cuentan por fecha_ingreso, los
# gastos por su propia fecha (son ejes de tiempo independientes).
# ---------------------------------------------------------------------------

SIN_ESPECIFICAR = 'Sin especificar'

PERIODOS = [
    ('mes', 'Este mes'),
    ('3m', 'Últimos 3 meses'),
    ('6m', 'Últimos 6 meses'),
    ('anio', 'Este año'),
    ('todo', 'Todo'),
]
PERIODO_DEFAULT = 'mes'
PERIODO_VALORES = {clave for clave, _ in PERIODOS}


def _primer_dia_hace_n_meses(hoy, n):
    anio, mes = hoy.year, hoy.month
    for _ in range(n):
        anio, mes = mes_anterior(anio, mes)
    return date(anio, mes, 1)


def rango_periodo(clave, hoy=None):
    """(fecha_desde, fecha_hasta) inclusive para la clave de período elegida
    en el selector de Estadísticas. (None, None) para 'todo' (sin filtro)."""
    hoy = hoy or timezone.now().date()
    if clave == 'mes':
        return hoy.replace(day=1), hoy
    if clave == '3m':
        return _primer_dia_hace_n_meses(hoy, 2), hoy
    if clave == '6m':
        return _primer_dia_hace_n_meses(hoy, 5), hoy
    if clave == 'anio':
        return hoy.replace(month=1, day=1), hoy
    return None, None


def _trabajos_del_periodo(desde, hasta, tipo_dispositivo=None):
    qs = Trabajo.objects.select_related('tipo_reparacion', 'marca', 'modelo', 'tercero').prefetch_related(
        'repuestos_usados__gasto'
    )
    if desde is not None:
        qs = qs.filter(fecha_ingreso__gte=desde, fecha_ingreso__lte=hasta)
    if tipo_dispositivo is not None:
        qs = qs.filter(tipo_dispositivo=tipo_dispositivo)
    return list(qs)


def _gastos_del_periodo(desde, hasta, tipo_dispositivo=None):
    qs = Gasto.objects.all()
    if desde is not None:
        qs = qs.filter(fecha__gte=desde, fecha__lte=hasta)
    if tipo_dispositivo is not None:
        qs = qs.filter(tipo_dispositivo=tipo_dispositivo)
    return qs


def resumen_periodo(desde, hasta, tipo_dispositivo=None):
    """Bloque 1: trabajos realizados, ingresos, gastos, ganancia total y
    ganancia promedio por trabajo, para el rango de fechas dado (y,
    opcionalmente, filtrado a un solo tipo de dispositivo)."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)
    ingresos = sum((t.precio_acordado or Decimal('0') for t in trabajos), Decimal('0'))

    gastos_total = _gastos_del_periodo(desde, hasta, tipo_dispositivo).aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0')

    ganancias = [t.ganancia for t in trabajos if t.ganancia is not None]
    ganancia_total = sum(ganancias, Decimal('0'))
    ganancia_promedio = ganancia_total / len(ganancias) if ganancias else Decimal('0')

    return {
        'trabajos_realizados': len(trabajos),
        'ingresos': ingresos,
        'gastos': gastos_total,
        'ganancia_total': ganancia_total,
        'ganancia_promedio': ganancia_promedio,
    }


def gastos_por_categoria_periodo(desde, hasta):
    """Bloque 2 (barras): total de gastos del período agrupado por
    categoría, ordenado de mayor a menor, con el porcentaje sobre el total."""
    qs = _gastos_del_periodo(desde, hasta)
    agrupado = (
        qs.values('categoria', 'categoria__nombre', 'categoria__color')
        .annotate(total=Sum('monto'))
        .order_by('-total')
    )
    total_general = sum((fila['total'] for fila in agrupado), Decimal('0'))

    filas = []
    for fila in agrupado:
        pct = int(round((fila['total'] / total_general) * 100)) if total_general else 0
        filas.append({
            'id': fila['categoria'],
            'nombre': fila['categoria__nombre'],
            'color': fila['categoria__color'],
            'total': fila['total'],
            'pct': pct,
        })
    return filas


def detalle_categoria_periodo(desde, hasta, categoria_id):
    """Desglose de una categoría de gasto: por subcategoría, salvo para
    "Repuestos" (que no usa subcategoría) donde se desglosa por tipo de
    repuesto en su lugar."""
    categoria = CategoriaGasto.objects.get(pk=categoria_id)
    qs = _gastos_del_periodo(desde, hasta).filter(categoria_id=categoria_id)

    campo = 'tipo_repuesto__nombre' if categoria.nombre == 'Repuestos' else 'subcategoria__nombre'
    agrupado = qs.values(campo).annotate(total=Sum('monto')).order_by('-total')
    total_categoria = sum((fila['total'] for fila in agrupado), Decimal('0'))

    filas = []
    for fila in agrupado:
        nombre = fila[campo] or SIN_ESPECIFICAR
        pct = int(round((fila['total'] / total_categoria) * 100)) if total_categoria else 0
        filas.append({'nombre': nombre, 'total': fila['total'], 'pct': pct})
    return filas


def gastos_por_categoria_con_detalle(desde, hasta):
    """Bloque 2 completo: cada categoría con su desglose ya calculado, para
    desplegar al hacer click sin pegarle a la base de nuevo."""
    categorias = gastos_por_categoria_periodo(desde, hasta)
    for cat in categorias:
        cat['detalle'] = detalle_categoria_periodo(desde, hasta, cat['id'])
    return categorias


def reparaciones_mas_frecuentes(desde, hasta, tipo_dispositivo=None, top=10):
    """Bloque 3: top de tipos de reparación por cantidad de trabajos, con
    ingresos, costo (repuestos + tercerizado), ganancia total, ganancia
    promedio, margen % y cuánto de ese costo fue tercerizado (para
    comparar costo propio vs. tercerizado). Los trabajos sin tipo de
    reparación van a "Sin especificar" en vez de descartarse. margen_pct
    queda en None cuando no hubo ingresos (no está definido dividir por
    cero)."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)

    grupos = {}
    for t in trabajos:
        clave = t.tipo_reparacion.nombre if t.tipo_reparacion else SIN_ESPECIFICAR
        grupo = grupos.setdefault(clave, {
            'nombre': clave, 'cantidad': 0,
            'ingresos': Decimal('0'), 'costo': Decimal('0'), 'ganancia_total': Decimal('0'),
            'tercerizado': Decimal('0'),
        })
        grupo['cantidad'] += 1
        grupo['ingresos'] += t.precio_acordado or Decimal('0')
        grupo['costo'] += t.costo_repuestos() + (t.tercerizado_monto or Decimal('0'))
        grupo['tercerizado'] += t.tercerizado_monto or Decimal('0')
        if t.ganancia is not None:
            grupo['ganancia_total'] += t.ganancia

    filas = []
    for grupo in grupos.values():
        cantidad = grupo['cantidad']
        ingresos = grupo['ingresos']
        ganancia_total = grupo['ganancia_total']
        filas.append({
            'nombre': grupo['nombre'],
            'cantidad': cantidad,
            'ingresos': ingresos,
            'costo': grupo['costo'],
            'ganancia_total': ganancia_total,
            'ganancia_promedio': ganancia_total / cantidad if cantidad else Decimal('0'),
            'margen_pct': (ganancia_total / ingresos * 100) if ingresos else None,
            'tercerizado': grupo['tercerizado'],
        })

    filas.sort(key=lambda f: f['ganancia_total'], reverse=True)
    return filas[:top]


def tercerizacion_resumen(desde, hasta, tipo_dispositivo=None):
    """Tarjeta "Tercerización" del bloque Resumen: monto total tercerizado,
    su % sobre los gastos del período (el mismo valor que ya se muestra en
    el resumen), cantidad de trabajos tercerizados y su % sobre el total
    de trabajos del período. Ambos porcentajes quedan en None cuando el
    denominador es 0."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)
    tercerizados = [t for t in trabajos if t.tercerizado_monto and t.tercerizado_monto > 0]

    monto_total = sum((t.tercerizado_monto for t in tercerizados), Decimal('0'))
    gastos_total = _gastos_del_periodo(desde, hasta, tipo_dispositivo).aggregate(
        total=Sum('monto')
    )['total'] or Decimal('0')

    return {
        'monto': monto_total,
        'pct_gastos': (monto_total / gastos_total * 100) if gastos_total else None,
        'cantidad': len(tercerizados),
        'pct_trabajos': (Decimal(len(tercerizados)) / len(trabajos) * 100) if trabajos else None,
    }


def tercerizacion_por_tercero(desde, hasta, tipo_dispositivo=None):
    """Bloque Tercerización, tabla (a): por tercero, cantidad de trabajos,
    total pagado y promedio por trabajo."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)

    grupos = {}
    for t in trabajos:
        if not (t.tercerizado_monto and t.tercerizado_monto > 0):
            continue
        nombre = t.tercero.nombre if t.tercero else SIN_ESPECIFICAR
        grupo = grupos.setdefault(t.tercero_id, {'nombre': nombre, 'cantidad': 0, 'total': Decimal('0')})
        grupo['cantidad'] += 1
        grupo['total'] += t.tercerizado_monto

    filas = []
    for grupo in grupos.values():
        cantidad = grupo['cantidad']
        filas.append({
            'nombre': grupo['nombre'],
            'cantidad': cantidad,
            'total': grupo['total'],
            'promedio': grupo['total'] / cantidad if cantidad else Decimal('0'),
        })

    filas.sort(key=lambda f: f['total'], reverse=True)
    return filas


def tercerizacion_por_reparacion(desde, hasta, tipo_dispositivo=None):
    """Bloque Tercerización, tabla (b): por tipo de reparación tercerizada,
    cantidad, total pagado al tercero y la ganancia promedio que le quedó
    a Martín en esos trabajos (para decidir si conviene seguir
    tercerizando o aprender a hacerlo él)."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)

    grupos = {}
    for t in trabajos:
        if not (t.tercerizado_monto and t.tercerizado_monto > 0):
            continue
        nombre = t.tipo_reparacion.nombre if t.tipo_reparacion else SIN_ESPECIFICAR
        grupo = grupos.setdefault(nombre, {
            'nombre': nombre, 'cantidad': 0, 'total': Decimal('0'), 'ganancia': Decimal('0'),
        })
        grupo['cantidad'] += 1
        grupo['total'] += t.tercerizado_monto
        if t.ganancia is not None:
            grupo['ganancia'] += t.ganancia

    filas = []
    for grupo in grupos.values():
        cantidad = grupo['cantidad']
        filas.append({
            'nombre': grupo['nombre'],
            'cantidad': cantidad,
            'total': grupo['total'],
            'ganancia_promedio': grupo['ganancia'] / cantidad if cantidad else Decimal('0'),
        })

    filas.sort(key=lambda f: f['total'], reverse=True)
    return filas


def marcas_mas_frecuentes(desde, hasta, tipo_dispositivo=None):
    """Bloque 4: ranking de marcas por cantidad de trabajos, cada una con
    su ganancia promedio y el ranking de sus modelos (mismo criterio). Las
    marcas/modelos sin especificar en el trabajo van a "Sin especificar"."""
    trabajos = _trabajos_del_periodo(desde, hasta, tipo_dispositivo)

    marcas = {}
    for t in trabajos:
        ganancia = t.ganancia if t.ganancia is not None else Decimal('0')

        marca = marcas.setdefault(t.marca_id, {
            'nombre': t.marca.nombre if t.marca else SIN_ESPECIFICAR,
            'cantidad': 0, 'ganancia': Decimal('0'), 'modelos': {},
        })
        marca['cantidad'] += 1
        marca['ganancia'] += ganancia

        modelo = marca['modelos'].setdefault(t.modelo_id, {
            'nombre': t.modelo.nombre if t.modelo else SIN_ESPECIFICAR,
            'cantidad': 0, 'ganancia': Decimal('0'),
        })
        modelo['cantidad'] += 1
        modelo['ganancia'] += ganancia

    filas = []
    for marca in marcas.values():
        cantidad = marca['cantidad']
        modelos = []
        for modelo in marca['modelos'].values():
            cant_modelo = modelo['cantidad']
            modelos.append({
                'nombre': modelo['nombre'],
                'cantidad': cant_modelo,
                'ganancia_promedio': modelo['ganancia'] / cant_modelo if cant_modelo else Decimal('0'),
            })
        modelos.sort(key=lambda m: m['cantidad'], reverse=True)
        filas.append({
            'nombre': marca['nombre'],
            'cantidad': cantidad,
            'ganancia_promedio': marca['ganancia'] / cantidad if cantidad else Decimal('0'),
            'modelos': modelos,
        })

    filas.sort(key=lambda f: f['cantidad'], reverse=True)
    return filas


def repuestos_mas_usados(desde, hasta, tipo_dispositivo, top=10):
    """Bloque 5 (por dispositivo): repuestos más usados por tipo de
    repuesto, contando unidades consumidas en trabajos de ese dispositivo
    dentro del período (se cuentan por fecha_ingreso del trabajo)."""
    qs = RepuestoUsado.objects.select_related('gasto__tipo_repuesto').filter(
        trabajo__tipo_dispositivo=tipo_dispositivo,
    )
    if desde is not None:
        qs = qs.filter(trabajo__fecha_ingreso__gte=desde, trabajo__fecha_ingreso__lte=hasta)

    grupos = {}
    for ru in qs:
        nombre = ru.gasto.tipo_repuesto.nombre if ru.gasto.tipo_repuesto else SIN_ESPECIFICAR
        grupo = grupos.setdefault(nombre, {'nombre': nombre, 'cantidad': 0, 'costo': Decimal('0')})
        grupo['cantidad'] += ru.cantidad
        grupo['costo'] += ru.costo

    filas = sorted(grupos.values(), key=lambda g: g['cantidad'], reverse=True)
    return filas[:top]
