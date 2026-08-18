"""Funciones de análisis para armar el futuro dashboard.

Todas devuelven datos "crudos" (Decimal, dict, querysets) listos para
que una vista los formatee. No hay lógica de presentación acá.
"""

from decimal import Decimal

from django.db.models import Avg, Count, Sum

from .models import Gasto, Pago, Trabajo


def balance_mensual(anio, mes):
    """Ingresos (pagos registrados en el mes) menos gastos del mes."""
    return Pago.objects.total_mes(anio, mes) - Gasto.objects.total_mes(anio, mes)


def gastos_por_categoria(anio, mes):
    """Total de gastos del mes, agrupado por categoría."""
    return Gasto.objects.por_categoria_mes(anio, mes)


def pagos_por_categoria_dispositivo(anio, mes):
    """Total de pagos del mes, agrupado por categoría de dispositivo del trabajo asociado."""
    return Pago.objects.por_categoria_dispositivo_mes(anio, mes)


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


def ticket_promedio(anio, mes):
    """Precio promedio de los trabajos entregados en el mes/año dado."""
    promedio = Trabajo.objects.filter(
        fecha_entrega__year=anio, fecha_entrega__month=mes
    ).aggregate(promedio=Avg('precio_acordado'))['promedio']
    return promedio or Decimal('0')


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


def trabajos_por_estado():
    """Cantidad de trabajos agrupados por estado, sin filtro de fecha."""
    return (
        Trabajo.objects.values('estado')
        .annotate(cantidad=Count('id'))
        .order_by('estado')
    )
