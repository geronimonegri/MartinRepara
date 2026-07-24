from datetime import date

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import analytics
from .forms import GastoForm, TrabajoForm
from .models import Gasto, Trabajo


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

    trabajos = Trabajo.objects.select_related('cliente').all()
    if query:
        trabajos = trabajos.filter(cliente__nombre__icontains=query)
    if estado_filter:
        trabajos = trabajos.filter(estado=estado_filter)

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


def gasto_create(request):
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('taller:dashboard')
    else:
        form = GastoForm(initial={'fecha': timezone.now().date()})
    return render(request, 'taller/gasto_form.html', {'form': form})


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

    balance_total = Trabajo.objects.balance_mensual(anio, mes)
    ingresos = Trabajo.objects.ingresos_mes(anio, mes)
    gastos = Gasto.objects.total_mes(anio, mes)
    comparacion = analytics.comparacion_mes_anterior(anio, mes)

    categorias = list(analytics.gastos_por_categoria(anio, mes))
    categoria_labels = dict(Gasto.Categoria.choices)
    max_categoria = max((c['total'] for c in categorias), default=0)
    for c in categorias:
        c['label'] = categoria_labels.get(c['categoria'], c['categoria'])
        c['pct'] = int((c['total'] / max_categoria) * 100) if max_categoria else 0

    conteos_por_estado = {value: 0 for value, _ in Trabajo.Estado.choices}
    conteos_por_estado.update({
        row['estado']: row['cantidad'] for row in analytics.trabajos_por_estado()
    })
    estados_grid = [
        {'value': value, 'label': label, 'cantidad': conteos_por_estado[value]}
        for value, label in Trabajo.Estado.choices
    ]

    context = {
        'anio': anio,
        'mes': mes,
        'mes_input_value': f'{anio:04d}-{mes:02d}',
        'mes_fecha': date(anio, mes, 1),
        'balance_total': balance_total,
        'ingresos': ingresos,
        'gastos': gastos,
        'comparacion': comparacion,
        'categorias': categorias,
        'estados_grid': estados_grid,
        'ingresos_pendientes': analytics.ingresos_pendientes(),
        'trabajos_listos_count': Trabajo.objects.filter(estado=Trabajo.Estado.LISTO).count(),
        'ticket_promedio': analytics.ticket_promedio(anio, mes),
        'entregados_mes_count': Trabajo.objects.filter(
            fecha_entrega__year=anio, fecha_entrega__month=mes
        ).count(),
    }
    return render(request, 'taller/balance.html', context)
