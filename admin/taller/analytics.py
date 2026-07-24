"""Funciones de análisis para armar el futuro dashboard.

Todas devuelven datos "crudos" (Decimal, dict, querysets) listos para
que una vista los formatee. No hay lógica de presentación acá.
"""

from decimal import Decimal

from django.db.models import Avg, Count, Sum

from .models import Gasto, Trabajo


def balance_mensual(anio, mes):
    """Ingresos (trabajos entregados en el mes) menos gastos del mes."""
    return Trabajo.objects.balance_mensual(anio, mes)


def gastos_por_categoria(anio, mes):
    """Total de gastos del mes, agrupado por categoría."""
    return Gasto.objects.por_categoria_mes(anio, mes)


def _mes_anterior(anio, mes):
    if mes == 1:
        return anio - 1, 12
    return anio, mes - 1


def comparacion_mes_anterior(anio, mes):
    """Balance del mes consultado vs. el mes inmediatamente anterior.

    variacion_pct queda en None cuando el balance del mes anterior es 0,
    ya que la variación porcentual no está definida en ese caso.
    """
    anio_prev, mes_prev = _mes_anterior(anio, mes)

    balance_actual = Trabajo.objects.balance_mensual(anio, mes)
    balance_anterior = Trabajo.objects.balance_mensual(anio_prev, mes_prev)

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


def trabajos_por_estado():
    """Cantidad de trabajos agrupados por estado, sin filtro de fecha."""
    return (
        Trabajo.objects.values('estado')
        .annotate(cantidad=Count('id'))
        .order_by('estado')
    )
