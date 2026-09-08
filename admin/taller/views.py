import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from . import analytics
from .forms import (
    CategoriaGastoForm,
    GastoForm,
    MarcaForm,
    ModeloForm,
    PagoForm,
    ProveedorForm,
    RepuestoUsadoFormSet,
    SubcategoriaGastoForm,
    TerceroForm,
    TipoDispositivoForm,
    TipoReparacionForm,
    TipoRepuestoForm,
    TrabajoForm,
    _sincronizar_gasto_tercerizado,
)
from .models import (
    CategoriaGasto,
    Gasto,
    Marca,
    Modelo,
    Pago,
    Proveedor,
    SubcategoriaGasto,
    Tercero,
    TipoDispositivo,
    TipoReparacion,
    TipoRepuesto,
    Trabajo,
)


def _parse_mes_param(mes_param):
    """Parsea un parámetro 'mes' con formato YYYY-MM.

    Devuelve (anio, mes) si es válido (mes entre 1 y 12), o None si el
    formato es incorrecto o el mes está fuera de rango.
    """
    if not mes_param:
        return None
    try:
        anio_str, mes_str = mes_param.split('-')
        anio, mes = int(anio_str), int(mes_str)
    except (ValueError, TypeError):
        return None
    if not 1 <= mes <= 12:
        return None
    return anio, mes


def dashboard(request):
    pendientes = (
        Trabajo.objects.exclude(estado=Trabajo.Estado.ENTREGADO)
        .select_related('cliente', 'tipo_dispositivo')
        .order_by('fecha_ingreso')
    )
    ultimos_gastos = Gasto.objects.select_related('categoria').all()[:5]
    return render(request, 'taller/dashboard.html', {
        'pendientes': pendientes,
        'ultimos_gastos': ultimos_gastos,
    })


def _con_indicador_pago(trabajos_qs):
    """Anota cada Trabajo con sus datos de pago ya calculados (sin N+1)."""
    trabajos = list(trabajos_qs)
    for trabajo in trabajos:
        pagos = list(trabajo.pagos.all())
        trabajo.total_pagado_calc = sum((p.monto for p in pagos), Decimal('0'))
        trabajo.esta_pagado_calc = (
            trabajo.precio_acordado is not None
            and trabajo.total_pagado_calc >= trabajo.precio_acordado
        )
    return trabajos


def trabajos_list(request):
    query = request.GET.get('q', '').strip()
    estado_filter = request.GET.get('estado', '').strip()
    categoria_filter = request.GET.get('categoria', '').strip()

    trabajos = (
        Trabajo.objects.select_related('cliente', 'tipo_dispositivo', 'marca', 'modelo')
        .prefetch_related('pagos', 'repuestos_usados__gasto')
        .exclude(estado=Trabajo.Estado.ENTREGADO)
    )
    if query:
        trabajos = trabajos.filter(cliente__nombre__icontains=query)
    if estado_filter:
        trabajos = trabajos.filter(estado=estado_filter)
    if categoria_filter:
        trabajos = trabajos.filter(tipo_dispositivo_id=categoria_filter)

    hoy = timezone.now().date()
    mes_param = request.GET.get('mes_entregados')
    if mes_param:
        parsed = _parse_mes_param(mes_param)
        if parsed is None:
            return redirect(request.path)
        anio_e, mes_e = parsed
    else:
        anio_e, mes_e = hoy.year, hoy.month
    anio_e_prev, mes_e_prev = analytics.mes_anterior(anio_e, mes_e)
    anio_e_next, mes_e_next = analytics.mes_siguiente(anio_e, mes_e)

    entregados = (
        Trabajo.objects.select_related('cliente', 'tipo_dispositivo', 'marca', 'modelo')
        .prefetch_related('pagos', 'repuestos_usados__gasto')
        .filter(
            estado=Trabajo.Estado.ENTREGADO,
            fecha_entrega__year=anio_e, fecha_entrega__month=mes_e,
        )
    )

    estados_filtro = [
        (value, label) for value, label in Trabajo.Estado.choices
        if value != Trabajo.Estado.ENTREGADO
    ]
    dispositivo_choices = [
        (str(t.pk), t.nombre) for t in TipoDispositivo.objects.filter(activo=True)
    ]

    return render(request, 'taller/trabajos_list.html', {
        'trabajos': _con_indicador_pago(trabajos),
        'entregados': _con_indicador_pago(entregados),
        'query': query,
        'estado_filter': estado_filter,
        'categoria_filter': categoria_filter,
        'estados': Trabajo.Estado.choices,
        'estados_filtro': estados_filtro,
        'dispositivo_choices': dispositivo_choices,
        'mes_entregados_fecha': date(anio_e, mes_e, 1),
        'mes_entregados_anterior_valor': f'{anio_e_prev:04d}-{mes_e_prev:02d}',
        'mes_entregados_siguiente_valor': f'{anio_e_next:04d}-{mes_e_next:02d}',
        'puede_avanzar_entregados': (anio_e, mes_e) < (hoy.year, hoy.month),
    })


@require_POST
def trabajo_estado_update(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)
    nuevo_estado = request.POST.get('estado')

    if nuevo_estado in Trabajo.Estado.values:
        trabajo.estado = nuevo_estado
        if nuevo_estado == Trabajo.Estado.ENTREGADO:
            # La fecha la elige quien entrega (con la de hoy precargada en
            # el popup de la lista): nunca se autocompleta acá.
            fecha_entrega = parse_date(request.POST.get('fecha_entrega') or '')
            trabajo.fecha_entrega = fecha_entrega or timezone.now().date()
        else:
            # Bug corregido: al retroceder el estado, la fecha de entrega
            # vieja quedaba pegada y el trabajo seguía contando como
            # "entregado" en pantallas que miran esa fecha.
            trabajo.fecha_entrega = None
        trabajo.save()

    next_url = request.POST.get('next') or reverse('taller:trabajos_list')
    return redirect(next_url)


def trabajo_create(request):
    if request.method == 'POST':
        form = TrabajoForm(request.POST)
        if form.is_valid():
            trabajo = form.save(commit=False)
            formset = RepuestoUsadoFormSet(request.POST, instance=trabajo)
            if formset.is_valid():
                trabajo.save()
                _sincronizar_gasto_tercerizado(trabajo)
                formset.instance = trabajo
                formset.save()
                return redirect('taller:trabajos_list')
        else:
            formset = RepuestoUsadoFormSet(request.POST)
    else:
        form = TrabajoForm(initial={'fecha_ingreso': timezone.now().date()})
        formset = RepuestoUsadoFormSet()
    return render(request, 'taller/trabajo_form.html', {'form': form, 'formset': formset})


def trabajo_edit(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)

    if request.method == 'POST':
        form = TrabajoForm(request.POST, instance=trabajo)
        formset = RepuestoUsadoFormSet(request.POST, instance=trabajo)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('taller:trabajos_list')
    else:
        form = TrabajoForm(instance=trabajo, initial={
            'cliente_nombre': trabajo.cliente.nombre,
            'cliente_telefono': trabajo.cliente.telefono,
        })
        formset = RepuestoUsadoFormSet(instance=trabajo)
    return render(request, 'taller/trabajo_form.html', {
        'form': form, 'formset': formset, 'trabajo': trabajo,
    })


@require_POST
def trabajo_delete(request, pk):
    trabajo = get_object_or_404(Trabajo, pk=pk)
    try:
        trabajo.delete()
    except ProtectedError:
        messages.error(
            request,
            f'El trabajo de {trabajo.cliente.nombre} tiene pagos registrados '
            'y no se puede eliminar.',
        )
    return redirect('taller:trabajos_list')


def _gasto_historial_context(request):
    """Datos de navegación por mes + historial filtrado, compartidos por
    gasto_create y gasto_edit. Devuelve None si el parámetro 'mes' de la
    URL es inválido (el caller debe redirigir a request.path en ese caso).
    """
    hoy = timezone.now().date()
    mes_param = request.GET.get('mes')
    if mes_param:
        parsed = _parse_mes_param(mes_param)
        if parsed is None:
            return None
        anio, mes = parsed
    else:
        anio, mes = hoy.year, hoy.month

    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    categoria_filter = request.GET.get('categoria', '').strip()
    gastos_mes = (
        Gasto.objects.select_related('categoria', 'subcategoria')
        .annotate(usos_count=Count('usos'))
        .filter(fecha__year=anio, fecha__month=mes)
    )
    if categoria_filter:
        gastos_mes = gastos_mes.filter(categoria_id=categoria_filter)

    return {
        'mes_fecha': date(anio, mes, 1),
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'puede_avanzar': (anio, mes) < (hoy.year, hoy.month),
        'gastos_mes': gastos_mes,
        'total_mes': Gasto.objects.total_mes(anio, mes),
        'categoria_filter': categoria_filter,
        'categorias_filtro': CategoriaGasto.objects.filter(activo=True),
    }


def _gasto_form_catalogos():
    """Catálogos que necesita el JS del form de Gasto (selects dependientes
    y botones '+'), compartidos por gasto_create y gasto_edit."""
    return {
        'categorias_gasto': CategoriaGasto.objects.filter(activo=True),
        'subcategorias_gasto': SubcategoriaGasto.objects.filter(activo=True).select_related('categoria'),
        'tipos_dispositivo': TipoDispositivo.objects.filter(activo=True),
        'tipos_repuesto': TipoRepuesto.objects.filter(activo=True).select_related('tipo_dispositivo'),
        'marcas': Marca.objects.filter(activo=True).select_related('tipo_dispositivo'),
        'modelos': Modelo.objects.filter(activo=True).select_related('marca'),
        'proveedores': Proveedor.objects.filter(activo=True),
    }


def gasto_create(request):
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            gasto = form.save()
            mes_valor = f'{gasto.fecha.year:04d}-{gasto.fecha.month:02d}'
            return redirect(f"{reverse('taller:gasto_create')}?mes={mes_valor}")
    else:
        form = GastoForm(initial={'fecha': timezone.now().date()})

    historial = _gasto_historial_context(request)
    if historial is None:
        return redirect(request.path)

    context = {'form': form}
    context.update(historial)
    context.update(_gasto_form_catalogos())
    return render(request, 'taller/gasto_form.html', context)


def gasto_edit(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)

    # Los gastos "Tercerizado" los genera solo _sincronizar_gasto_tercerizado()
    # desde un Trabajo: no se editan desde acá, se edita el trabajo.
    if gasto.categoria.nombre == 'Tercerizado':
        if gasto.trabajo_id:
            return redirect('taller:trabajo_edit', pk=gasto.trabajo_id)
        messages.error(
            request,
            'Este gasto se generó automáticamente desde un trabajo tercerizado y no se puede editar acá.',
        )
        return redirect('taller:gasto_create')

    if request.method == 'POST':
        form = GastoForm(request.POST, instance=gasto)
        if form.is_valid():
            gasto = form.save()
            mes_valor = f'{gasto.fecha.year:04d}-{gasto.fecha.month:02d}'
            return redirect(f"{reverse('taller:gasto_create')}?mes={mes_valor}")
    else:
        form = GastoForm(instance=gasto)

    historial = _gasto_historial_context(request)
    if historial is None:
        return redirect(request.path)

    context = {'form': form}
    context.update(historial)
    context.update(_gasto_form_catalogos())
    return render(request, 'taller/gasto_form.html', context)


@require_POST
def gasto_delete(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)
    next_url = request.POST.get('next') or reverse('taller:gasto_create')

    if gasto.categoria.nombre == 'Tercerizado':
        messages.error(
            request,
            'Este gasto se generó automáticamente desde un trabajo tercerizado y no se puede eliminar acá.',
        )
        return redirect(next_url)

    try:
        gasto.delete()
    except ProtectedError:
        numeros = ', '.join(sorted({
            uso.trabajo.numero for uso in gasto.usos.select_related('trabajo').all()
        }))
        messages.error(
            request,
            f'Este repuesto ya se usó en {numeros} y no se puede eliminar. Podés editarlo.',
        )
    return redirect(next_url)


def stock_list(request):
    categoria_filter = request.GET.get('categoria', '').strip()

    items = (
        Gasto.objects.filter(categoria__nombre='Repuestos', stock_disponible__gt=0)
        .select_related('tipo_repuesto', 'marca', 'modelo', 'proveedor', 'tipo_dispositivo')
    )
    if categoria_filter:
        items = items.filter(tipo_dispositivo_id=categoria_filter)
    items = items.order_by('tipo_dispositivo__orden', 'tipo_repuesto__orden', 'numero')

    total_valorizado = sum(
        ((g.precio_unitario or Decimal('0')) * (g.stock_disponible or 0) for g in items),
        Decimal('0'),
    )

    dispositivo_choices = [
        (str(t.pk), t.nombre) for t in TipoDispositivo.objects.filter(activo=True)
    ]

    return render(request, 'taller/stock_list.html', {
        'items': items,
        'categoria_filter': categoria_filter,
        'dispositivo_choices': dispositivo_choices,
        'total_valorizado': total_valorizado,
    })


def _trabajo_resaltado_desde_request(request):
    """Lee ?trabajo=<id> para resaltar todos los pagos de ese trabajo."""
    valor = request.GET.get('trabajo')
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


def _pago_historial_context(request, fecha_default=None):
    """Datos de navegación por mes + historial filtrado, compartidos por
    pago_create y pago_edit. Devuelve None si el parámetro 'mes' de la
    URL es inválido (el caller debe redirigir a request.path en ese caso).

    Si no hay 'mes' en la URL: usa fecha_default (pago_edit pasa la fecha
    del pago que se está editando) o, si hay un ?trabajo=<id> de resaltado
    y ese trabajo tiene pagos, el mes del pago más reciente de ese trabajo
    — para que el trabajo resaltado sea visible sin que el usuario tenga
    que navegar manualmente hasta su mes.
    """
    hoy = timezone.now().date()
    trabajo_resaltado = _trabajo_resaltado_desde_request(request)

    mes_param = request.GET.get('mes')
    if mes_param:
        parsed = _parse_mes_param(mes_param)
        if parsed is None:
            return None
        anio, mes = parsed
    elif fecha_default is not None:
        anio, mes = fecha_default.year, fecha_default.month
    elif trabajo_resaltado:
        ultimo_pago = (
            Pago.objects.filter(trabajo_id=trabajo_resaltado)
            .order_by('-fecha', '-id')
            .first()
        )
        anio, mes = (ultimo_pago.fecha.year, ultimo_pago.fecha.month) if ultimo_pago else (hoy.year, hoy.month)
    else:
        anio, mes = hoy.year, hoy.month

    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    pagos_mes = (
        Pago.objects.select_related('trabajo__cliente')
        .filter(fecha__year=anio, fecha__month=mes)
    )

    return {
        'mes_fecha': date(anio, mes, 1),
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'puede_avanzar': (anio, mes) < (hoy.year, hoy.month),
        'pagos_mes': pagos_mes,
        'total_mes': Pago.objects.total_mes(anio, mes),
        'trabajo_resaltado': trabajo_resaltado,
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

    historial = _pago_historial_context(request)
    if historial is None:
        return redirect(request.path)

    context = {'form': form}
    context.update(historial)
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

    historial = _pago_historial_context(request, fecha_default=pago.fecha)
    if historial is None:
        return redirect(request.path)

    context = {'form': form}
    context.update(historial)
    return render(request, 'taller/pago_form.html', context)


@require_POST
def pago_delete(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    # El estado de pago del trabajo (parcial/completo) no se guarda aparte:
    # sale de total_pagado()/esta_pagado(), que suman los Pago existentes
    # al vuelo. Al borrar uno, se recalcula solo la próxima vez que se lea.
    pago.delete()
    next_url = request.POST.get('next') or reverse('taller:pago_create')
    return redirect(next_url)


def estadisticas(request):
    periodo = request.GET.get('periodo', analytics.PERIODO_DEFAULT)
    if periodo not in analytics.PERIODO_VALORES:
        periodo = analytics.PERIODO_DEFAULT
    desde, hasta = analytics.rango_periodo(periodo)

    dispositivos = list(TipoDispositivo.objects.filter(activo=True))
    tabs = []
    for tipo in dispositivos:
        tabs.append({
            'tipo': tipo,
            'resumen': analytics.resumen_periodo(desde, hasta, tipo_dispositivo=tipo),
            'reparaciones': analytics.reparaciones_mas_frecuentes(desde, hasta, tipo_dispositivo=tipo),
            'marcas': analytics.marcas_mas_frecuentes(desde, hasta, tipo_dispositivo=tipo),
            'repuestos': analytics.repuestos_mas_usados(desde, hasta, tipo_dispositivo=tipo),
            'tercerizacion': analytics.tercerizacion_resumen(desde, hasta, tipo_dispositivo=tipo),
            'tercerizacion_por_tercero': analytics.tercerizacion_por_tercero(desde, hasta, tipo_dispositivo=tipo),
            'tercerizacion_por_reparacion': analytics.tercerizacion_por_reparacion(desde, hasta, tipo_dispositivo=tipo),
        })
    tab_default = next((t['tipo'].pk for t in tabs if t['tipo'].nombre == 'Celular'), tabs[0]['tipo'].pk if tabs else None)

    categorias_gasto = analytics.gastos_por_categoria_con_detalle(desde, hasta)
    categorias_gasto_json = [
        {'nombre': c['nombre'], 'total': float(c['total']), 'color': c['color']}
        for c in categorias_gasto
    ]

    return render(request, 'taller/estadisticas.html', {
        'periodos': analytics.PERIODOS,
        'periodo_actual': periodo,
        'resumen': analytics.resumen_periodo(desde, hasta),
        'categorias_gasto': categorias_gasto,
        'categorias_gasto_json': categorias_gasto_json,
        'categorias_gasto_chart_height': max(180, 40 * len(categorias_gasto) + 40),
        'reparaciones': analytics.reparaciones_mas_frecuentes(desde, hasta),
        'marcas': analytics.marcas_mas_frecuentes(desde, hasta),
        'tercerizacion': analytics.tercerizacion_resumen(desde, hasta),
        'tercerizacion_por_tercero': analytics.tercerizacion_por_tercero(desde, hasta),
        'tercerizacion_por_reparacion': analytics.tercerizacion_por_reparacion(desde, hasta),
        'tabs': tabs,
        'tab_default': tab_default,
    })


MESES_ABREV = {
    1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic',
}


def balance(request):
    hoy = timezone.now().date()
    mes_param = request.GET.get('mes')
    if mes_param:
        parsed = _parse_mes_param(mes_param)
        if parsed is None:
            return redirect(request.path)
        anio, mes = parsed
    else:
        anio, mes = hoy.year, hoy.month

    balance_total = analytics.balance_mensual(anio, mes)
    ingresos = Pago.objects.total_mes(anio, mes)
    gastos = Gasto.objects.total_mes(anio, mes)
    comparacion = analytics.comparacion_mes_anterior(anio, mes)
    tercerizado = analytics.tercerizado_mensual(anio, mes)

    totales_por_categoria = {
        row['categoria']: row['total'] for row in analytics.gastos_por_categoria(anio, mes)
    }
    categorias = []
    for cat in CategoriaGasto.objects.filter(activo=True):
        total = totales_por_categoria.get(cat.pk, Decimal('0'))
        pct = int(round((total / gastos) * 100)) if gastos else 0
        categorias.append({'label': cat.nombre, 'total': total, 'pct': pct, 'color': cat.color})
    categorias_json = [
        {'label': c['label'], 'total': float(c['total']), 'color': c['color']}
        for c in categorias
    ]

    totales_por_dispositivo = {
        row['trabajo__tipo_dispositivo']: row['total']
        for row in analytics.pagos_por_categoria_dispositivo(anio, mes)
    }
    categorias_dispositivo = []
    for tipo in TipoDispositivo.objects.filter(activo=True):
        total = totales_por_dispositivo.get(tipo.pk, Decimal('0'))
        pct = int(round((total / ingresos) * 100)) if ingresos else 0
        categorias_dispositivo.append({'label': tipo.nombre, 'total': total, 'pct': pct, 'color': tipo.color})
    categorias_dispositivo_json = [
        {'label': c['label'], 'total': float(c['total']), 'color': c['color']}
        for c in categorias_dispositivo
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
        'puede_avanzar': (anio, mes) < (hoy.year, hoy.month),
        'balance_total': balance_total,
        'ingresos': ingresos,
        'gastos': gastos,
        'comparacion': comparacion,
        'tercerizado': tercerizado,
        'categorias': categorias,
        'categorias_json': categorias_json,
        'categorias_dispositivo': categorias_dispositivo,
        'categorias_dispositivo_json': categorias_dispositivo_json,
        'es_mes_actual': es_mes_actual,
        'evolucion_labels': evolucion_labels,
        'evolucion_valores': evolucion_valores,
        'evolucion_indice_actual': len(evolucion) - 1,
        # Ingresos pendientes es siempre el estado actual (trabajos "listo"
        # ahora mismo), sin importar qué mes se esté mirando: no tiene
        # fecha propia, así que se muestra igual en cualquier mes.
        'ingresos_pendientes': analytics.ingresos_pendientes(),
        'trabajos_listos_count': Trabajo.objects.filter(
            estado=Trabajo.Estado.LISTO
        ).count(),
    }

    return render(request, 'taller/balance.html', context)


CATALOGOS = {
    'tipo_dispositivo': {'model': TipoDispositivo, 'form': TipoDispositivoForm, 'label': 'Tipos de dispositivo'},
    'categoria_gasto': {'model': CategoriaGasto, 'form': CategoriaGastoForm, 'label': 'Categorías de gasto'},
    'subcategoria_gasto': {
        'model': SubcategoriaGasto, 'form': SubcategoriaGastoForm, 'label': 'Subcategorías de gasto',
        'select_related': ['categoria'],
    },
    'tipo_repuesto': {
        'model': TipoRepuesto, 'form': TipoRepuestoForm, 'label': 'Tipos de repuesto',
        'select_related': ['tipo_dispositivo'],
    },
    'marca': {
        'model': Marca, 'form': MarcaForm, 'label': 'Marcas',
        'select_related': ['tipo_dispositivo'],
    },
    'modelo': {
        'model': Modelo, 'form': ModeloForm, 'label': 'Modelos',
        'select_related': ['marca'],
    },
    'proveedor': {'model': Proveedor, 'form': ProveedorForm, 'label': 'Proveedores'},
    'tipo_reparacion': {
        'model': TipoReparacion, 'form': TipoReparacionForm, 'label': 'Tipos de reparación',
        'select_related': ['tipo_dispositivo'],
    },
    'tercero': {'model': Tercero, 'form': TerceroForm, 'label': 'Terceros'},
}
ORDEN_TABS = [
    'tipo_dispositivo', 'categoria_gasto', 'subcategoria_gasto',
    'tipo_repuesto', 'marca', 'modelo', 'proveedor',
    'tipo_reparacion', 'tercero',
]


def configuracion(request, tab='tipo_dispositivo', pk=None):
    if tab not in CATALOGOS:
        return redirect('taller:configuracion')

    info = CATALOGOS[tab]
    FormClass = info['form']
    Modelo_ = info['model']

    instancia = get_object_or_404(Modelo_, pk=pk) if pk else None

    if request.method == 'POST':
        form = FormClass(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('taller:configuracion_tab', tab=tab)
    else:
        form = FormClass(instance=instancia)

    items = Modelo_.objects.select_related(*info.get('select_related', [])).all()

    return render(request, 'taller/configuracion.html', {
        'tabs': [(clave, CATALOGOS[clave]['label']) for clave in ORDEN_TABS],
        'tab_actual': tab,
        'label_actual': info['label'],
        'form': form,
        'editando': instancia,
        'items': items,
    })


@require_POST
def catalogo_toggle_activo(request, tab, pk):
    if tab not in CATALOGOS:
        return redirect('taller:configuracion')
    obj = get_object_or_404(CATALOGOS[tab]['model'], pk=pk)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    return redirect('taller:configuracion_tab', tab=tab)


@require_POST
def catalogo_crear_rapido(request, tipo):
    """Crea un ítem de catálogo desde el botón '+' de un formulario, sin
    salir de la página (marca/modelo/proveedor nuevos). Devuelve JSON
    {id, nombre} para que el JS lo agregue al <select> correspondiente."""
    nombre = request.POST.get('nombre', '').strip()
    if not nombre:
        return JsonResponse({'error': 'Falta el nombre.'}, status=400)

    if tipo == 'marca':
        tipo_dispositivo_id = request.POST.get('tipo_dispositivo')
        if not tipo_dispositivo_id:
            return JsonResponse({'error': 'Elegí primero el tipo de dispositivo.'}, status=400)
        tipo_dispositivo = get_object_or_404(TipoDispositivo, pk=tipo_dispositivo_id)
        obj, _ = Marca.objects.get_or_create(nombre=nombre, tipo_dispositivo=tipo_dispositivo)
    elif tipo == 'modelo':
        marca_id = request.POST.get('marca')
        if not marca_id:
            return JsonResponse({'error': 'Elegí primero la marca.'}, status=400)
        marca = get_object_or_404(Marca, pk=marca_id)
        obj, _ = Modelo.objects.get_or_create(nombre=nombre, marca=marca)
    elif tipo == 'proveedor':
        telefono = request.POST.get('telefono', '').strip()
        obj, _ = Proveedor.objects.get_or_create(nombre=nombre, defaults={'telefono': telefono})
    elif tipo == 'tercero':
        telefono = request.POST.get('telefono', '').strip()
        obj, _ = Tercero.objects.get_or_create(nombre=nombre, defaults={'telefono': telefono})
    else:
        return JsonResponse({'error': 'Tipo inválido.'}, status=400)

    return JsonResponse({'id': obj.pk, 'nombre': obj.nombre})


def _elegir_carpeta(request):
    """Abre el selector de carpetas nativo de pywebview y devuelve la
    carpeta elegida (Path) o None.

    Solo funciona corriendo como app de escritorio (app.py); si se
    accede desde el navegador (manage.py runserver) no hay ventana
    pywebview y se deja cargado un mensaje avisando que no está
    disponible ahí. Si el usuario cancela el diálogo también devuelve
    None, con un mensaje informativo distinto.
    """
    try:
        import webview
    except ImportError:
        webview = None

    if not webview or not webview.windows:
        messages.error(
            request,
            'Esta función solo está disponible en la app de escritorio.',
        )
        return None

    carpeta = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
    if not carpeta:
        messages.info(request, 'Operación cancelada.')
        return None
    return Path(carpeta[0])


@require_POST
def backup_exportar(request):
    """Copia la base de datos a una carpeta elegida por el usuario."""
    next_url = request.META.get('HTTP_REFERER') or reverse('taller:dashboard')

    carpeta = _elegir_carpeta(request)
    if carpeta is None:
        return redirect(next_url)

    origen = Path(settings.DATABASES['default']['NAME'])
    if not origen.exists():
        messages.error(request, 'No se encontró la base de datos para copiar.')
        return redirect(next_url)

    destino = carpeta / f'martinrepara_backup_{date.today().isoformat()}.sqlite3'
    shutil.copy2(origen, destino)
    messages.success(request, f'Copia guardada en {destino}')
    return redirect(next_url)


def _construir_excel():
    """Arma el .xlsx con Trabajos/Gastos/Pagos, mismos formatos que la app."""
    import openpyxl
    from openpyxl.styles import Font

    from .templatetags.taller_extras import moneda

    def fecha_fmt(f):
        return f.strftime('%d/%m/%Y') if f else '—'

    wb = openpyxl.Workbook()

    ws_trabajos = wb.active
    ws_trabajos.title = 'Trabajos'
    ws_trabajos.append([
        'Número', 'Cliente', 'Teléfono', 'Tipo de dispositivo', 'Marca', 'Modelo',
        'Tipo de reparación', 'Problema', 'Detalle', 'Estado', 'Precio',
        'Fecha ingreso', 'Fecha entrega', 'Total pagado', 'Estado de pago',
        'Costo repuestos', 'Tercero', 'Monto tercerizado', 'Ganancia',
    ])
    trabajos = (
        Trabajo.objects.select_related(
            'cliente', 'tipo_dispositivo', 'marca', 'modelo', 'tipo_reparacion', 'tercero',
        ).prefetch_related('pagos', 'repuestos_usados__gasto').all()
    )
    for t in trabajos:
        pagos = list(t.pagos.all())
        total_pagado = sum((p.monto for p in pagos), Decimal('0'))
        if t.precio_acordado is not None and total_pagado >= t.precio_acordado:
            estado_pago = 'Pagado por completo'
        elif total_pagado > 0 and t.precio_acordado:
            estado_pago = f'Pago parcial: {moneda(total_pagado)} de {moneda(t.precio_acordado)}'
        elif total_pagado > 0:
            estado_pago = f'Pago parcial: {moneda(total_pagado)}'
        else:
            estado_pago = '—'
        ws_trabajos.append([
            t.numero,
            t.cliente.nombre,
            t.cliente.telefono,
            t.tipo_dispositivo.nombre,
            t.marca.nombre if t.marca else '—',
            t.modelo.nombre if t.modelo else '—',
            t.tipo_reparacion.nombre if t.tipo_reparacion else '—',
            t.descripcion_problema,
            t.detalle or '—',
            t.get_estado_display(),
            moneda(t.precio_acordado),
            fecha_fmt(t.fecha_ingreso),
            fecha_fmt(t.fecha_entrega),
            moneda(total_pagado),
            estado_pago,
            moneda(t.costo_repuestos()),
            t.tercero.nombre if t.tercero else '—',
            moneda(t.tercerizado_monto) if t.tercerizado_monto is not None else '—',
            moneda(t.ganancia) if t.ganancia is not None else '—',
        ])

    ws_gastos = wb.create_sheet('Gastos')
    ws_gastos.append([
        'Número', 'Fecha', 'Categoría', 'Subcategoría', 'Descripción', 'Monto',
        'Proveedor', 'Tipo de dispositivo', 'Tipo de repuesto', 'Marca', 'Modelo',
        'Cantidad', 'Precio unitario', 'Stock disponible',
    ])
    gastos = Gasto.objects.select_related(
        'categoria', 'subcategoria', 'proveedor', 'tipo_dispositivo', 'tipo_repuesto', 'marca', 'modelo',
    ).all()
    for g in gastos:
        ws_gastos.append([
            g.numero,
            fecha_fmt(g.fecha),
            g.categoria.nombre,
            g.subcategoria.nombre if g.subcategoria else '—',
            g.descripcion,
            moneda(g.monto),
            g.proveedor.nombre if g.proveedor else '—',
            g.tipo_dispositivo.nombre if g.tipo_dispositivo else '—',
            g.tipo_repuesto.nombre if g.tipo_repuesto else '—',
            g.marca.nombre if g.marca else '—',
            g.modelo.nombre if g.modelo else '—',
            g.cantidad if g.cantidad is not None else '—',
            moneda(g.precio_unitario) if g.precio_unitario is not None else '—',
            g.stock_disponible if g.stock_disponible is not None else '—',
        ])

    ws_pagos = wb.create_sheet('Pagos')
    ws_pagos.append(['Número', 'Cliente', 'Monto', 'Forma de pago', 'Fecha', 'Detalle'])
    for p in Pago.objects.select_related('trabajo__cliente').all():
        ws_pagos.append([
            p.numero,
            p.trabajo.cliente.nombre,
            moneda(p.monto),
            p.get_forma_pago_display(),
            fecha_fmt(p.fecha),
            p.detalle or '—',
        ])

    for hoja in (ws_trabajos, ws_gastos, ws_pagos):
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for columna in hoja.columns:
            valores = [len(str(c.value)) for c in columna if c.value is not None]
            ancho = max(valores) + 2 if valores else 12
            hoja.column_dimensions[columna[0].column_letter].width = min(ancho, 40)

    return wb


@require_POST
def exportar_excel(request):
    """Exporta Trabajos/Gastos/Pagos a un .xlsx en una carpeta elegida por el usuario."""
    next_url = request.META.get('HTTP_REFERER') or reverse('taller:dashboard')

    carpeta = _elegir_carpeta(request)
    if carpeta is None:
        return redirect(next_url)

    destino = carpeta / f'martinrepara_export_{date.today().isoformat()}.xlsx'
    _construir_excel().save(destino)
    messages.success(request, f'Excel guardado en {destino}')
    return redirect(next_url)
