from datetime import date
from decimal import Decimal

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import analytics
from .forms import GastoForm, PagoForm, TrabajoForm
from .models import Gasto, Pago, Trabajo


def dashboard(request):
    pendientes = (
        Trabajo.objects.exclude(estado=Trabajo.Estado.ENTREGADO)
        .select_related('cliente')
        .order_by('fecha_ingreso')
    )
    ultimos_gastos = Gasto.objects.all()[:5]
    return render(request, 'taller/dashboard.html', {
        'pendientes': pendientes,
        'ultimos_gastos': ultimos_gastos,
    })


def trabajos_list(request):
    query = request.GET.get('q', '').strip()
    estado_filter = request.GET.get('estado', '').strip()

    trabajos = Trabajo.objects.select_related('cliente').prefetch_related('pagos').all()
    if query:
        trabajos = trabajos.filter(cliente__nombre__icontains=query)
    if estado_filter:
        trabajos = trabajos.filter(estado=estado_filter)

    trabajos = list(trabajos)
    for trabajo in trabajos:
        pagos = list(trabajo.pagos.all())
        trabajo.total_pagado_calc = sum((p.monto for p in pagos), Decimal('0'))
        trabajo.ultimo_pago = pagos[0] if pagos else None
        trabajo.esta_pagado_calc = (
            trabajo.precio_acordado is not None
            and trabajo.total_pagado_calc >= trabajo.precio_acordado
        )

    return render(request, 'taller/trabajos_list.html', {
        'trabajos': trabajos,
        'query': query,
        'estado_filter': estado_filter,
        'estados': Trabajo.Estado.choices,
    })


@require_POST
def trabajo_estado_update(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)
    nuevo_estado = request.POST.get('estado')

    if nuevo_estado in Trabajo.Estado.values:
        trabajo.estado = nuevo_estado
        if nuevo_estado == Trabajo.Estado.ENTREGADO and trabajo.fecha_entrega is None:
            trabajo.fecha_entrega = timezone.now().date()
        trabajo.save()

    next_url = request.POST.get('next') or reverse('taller:trabajos_list')
    return redirect(next_url)


def trabajo_create(request):
    if request.method == 'POST':
        form = TrabajoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('taller:trabajos_list')
    else:
        form = TrabajoForm(initial={'fecha_ingreso': timezone.now().date()})
    return render(request, 'taller/trabajo_form.html', {'form': form})


def trabajo_edit(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)

    if request.method == 'POST':
        form = TrabajoForm(request.POST, instance=trabajo)
        if form.is_valid():
            form.save()
            return redirect('taller:trabajos_list')
    else:
        form = TrabajoForm(instance=trabajo, initial={
            'cliente_nombre': trabajo.cliente.nombre,
            'cliente_telefono': trabajo.cliente.telefono,
        })
    return render(request, 'taller/trabajo_form.html', {'form': form, 'trabajo': trabajo})


@require_POST
def trabajo_delete(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)
    trabajo.delete()
    return redirect('taller:trabajos_list')


def gasto_create(request):
    hoy = timezone.now().date()

    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            gasto = form.save()
            mes_valor = f'{gasto.fecha.year:04d}-{gasto.fecha.month:02d}'
            return redirect(f"{reverse('taller:gasto_create')}?mes={mes_valor}")
    else:
        form = GastoForm(initial={'fecha': hoy})

    mes_param = request.GET.get('mes')
    anio, mes = hoy.year, hoy.month
    if mes_param:
        try:
            anio_str, mes_str = mes_param.split('-')
            anio, mes = int(anio_str), int(mes_str)
        except (ValueError, TypeError):
            anio, mes = hoy.year, hoy.month

    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    gastos_mes = Gasto.objects.filter(fecha__year=anio, fecha__month=mes)

    return render(request, 'taller/gasto_form.html', {
        'form': form,
        'mes_fecha': date(anio, mes, 1),
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'gastos_mes': gastos_mes,
        'total_mes': Gasto.objects.total_mes(anio, mes),
    })


def _mes_desde_request(request, fecha_default):
    mes_param = request.GET.get('mes')
    anio, mes = fecha_default.year, fecha_default.month
    if mes_param:
        try:
            anio_str, mes_str = mes_param.split('-')
            anio, mes = int(anio_str), int(mes_str)
        except (ValueError, TypeError):
            anio, mes = fecha_default.year, fecha_default.month
    return anio, mes


def _pago_mes_context(request, fecha_default):
    anio, mes = _mes_desde_request(request, fecha_default)
    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    return {
        'mes_fecha': date(anio, mes, 1),
        'mes_actual_valor': f'{anio:04d}-{mes:02d}',
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'pagos_mes': Pago.objects.select_related('trabajo__cliente').filter(
            fecha__year=anio, fecha__month=mes
        ),
        'total_mes': Pago.objects.total_mes(anio, mes),
    }


def pago_create(request):
    if request.method == 'POST':
        form = PagoForm(request.POST)
        if form.is_valid():
            pago = form.save()
            mes_valor = f'{pago.fecha.year:04d}-{pago.fecha.month:02d}'
            return redirect(f"{reverse('taller:pago_create')}?mes={mes_valor}")
    else:
        form = PagoForm(initial={'fecha': timezone.now().date()})

    context = {'form': form}
    context.update(_pago_mes_context(request, timezone.now().date()))
    return render(request, 'taller/pago_form.html', context)


def pago_edit(request, pk):
    pago = get_object_or_404(Pago, pk=pk)

    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            pago = form.save()
            mes_valor = f'{pago.fecha.year:04d}-{pago.fecha.month:02d}'
            return redirect(f"{reverse('taller:pago_create')}?mes={mes_valor}")
    else:
        form = PagoForm(instance=pago)

    context = {'form': form}
    context.update(_pago_mes_context(request, pago.fecha))
    return render(request, 'taller/pago_form.html', context)


CATEGORIA_COLORES = {
    'repuesto': '#2563eb',
    'herramienta': '#f59e0b',
    'taller': '#8b5cf6',
    'otro': '#9ca3af',
}

CATEGORIA_DISPOSITIVO_COLORES = {
    'celular': '#2563eb',
    'consola': '#8b5cf6',
    'notebook': '#f59e0b',
    'otro': '#9ca3af',
}

MESES_ABREV = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
}


def balance(request):
    hoy = timezone.now().date()
    mes_param = request.GET.get('mes')
    anio, mes = hoy.year, hoy.month
    if mes_param:
        try:
            anio_str, mes_str = mes_param.split('-')
            anio, mes = int(anio_str), int(mes_str)
        except (ValueError, TypeError):
            anio, mes = hoy.year, hoy.month

    balance_total = analytics.balance_mensual(anio, mes)
    ingresos = Pago.objects.total_mes(anio, mes)
    gastos = Gasto.objects.total_mes(anio, mes)
    comparacion = analytics.comparacion_mes_anterior(anio, mes)

    totales_por_categoria = {
        row['categoria']: row['total'] for row in analytics.gastos_por_categoria(anio, mes)
    }
    categorias = []
    for value, label in Gasto.Categoria.choices:
        total = totales_por_categoria.get(value, Decimal('0'))
        pct = int(round((total / gastos) * 100)) if gastos else 0
        categorias.append({
            'categoria': value,
            'label': label,
            'total': total,
            'pct': pct,
            'color': CATEGORIA_COLORES.get(value, '#9ca3af'),
        })
    categorias_json = [
        {'label': c['label'], 'total': float(c['total']), 'color': c['color']}
        for c in categorias
    ]

    totales_por_dispositivo = {
        row['trabajo__categoria_dispositivo']: row['total']
        for row in analytics.pagos_por_categoria_dispositivo(anio, mes)
    }
    categorias_dispositivo = []
    for value, label in Trabajo.CategoriaDispositivo.choices:
        total = totales_por_dispositivo.get(value, Decimal('0'))
        pct = int(round((total / ingresos) * 100)) if ingresos else 0
        categorias_dispositivo.append({
            'categoria': value,
            'label': label,
            'total': total,
            'pct': pct,
            'color': CATEGORIA_DISPOSITIVO_COLORES.get(value, '#9ca3af'),
        })
    categorias_dispositivo_json = [
        {'label': c['label'], 'total': float(c['total']), 'color': c['color']}
        for c in categorias_dispositivo
    ]

    conteos_por_estado = {value: 0 for value, _ in Trabajo.Estado.choices}
    conteos_por_estado.update({
        row['estado']: row['cantidad'] for row in analytics.trabajos_por_estado()
    })
    estados_grid = [
        {'value': value, 'label': label, 'cantidad': conteos_por_estado[value]}
        for value, label in Trabajo.Estado.choices
    ]

    es_mes_actual = (anio, mes) == (hoy.year, hoy.month)

    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    evolucion = analytics.balance_ultimos_n_meses(anio, mes, n=6)
    evolucion_labels = [MESES_ABREV[e['mes']] for e in evolucion]
    evolucion_valores = [float(e['balance']) for e in evolucion]

    context = {
        'anio': anio,
        'mes': mes,
        'mes_fecha': date(anio, mes, 1),
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'balance_total': balance_total,
        'ingresos': ingresos,
        'gastos': gastos,
        'comparacion': comparacion,
        'categorias': categorias,
        'categorias_json': categorias_json,
        'categorias_dispositivo': categorias_dispositivo,
        'categorias_dispositivo_json': categorias_dispositivo_json,
        'estados_grid': estados_grid,
        'es_mes_actual': es_mes_actual,
        'ticket_promedio': analytics.ticket_promedio(anio, mes),
        'entregados_mes_count': Trabajo.objects.filter(
            fecha_entrega__year=anio, fecha_entrega__month=mes
        ).count(),
        'evolucion_labels': evolucion_labels,
        'evolucion_valores': evolucion_valores,
        'evolucion_indice_actual': len(evolucion) - 1,
    }
    if es_mes_actual:
        context['ingresos_pendientes'] = analytics.ingresos_pendientes()
        context['trabajos_listos_count'] = Trabajo.objects.filter(
            estado=Trabajo.Estado.LISTO
        ).count()

    return render(request, 'taller/balance.html', context)
