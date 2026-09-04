import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import analytics
from .forms import GastoForm, PagoForm, TrabajoForm
from .models import Gasto, Pago, Trabajo


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
        .select_related('cliente')
        .order_by('fecha_ingreso')
    )
    ultimos_gastos = Gasto.objects.all()[:5]
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
        Trabajo.objects.select_related('cliente').prefetch_related('pagos')
        .exclude(estado=Trabajo.Estado.ENTREGADO)
    )
    if query:
        trabajos = trabajos.filter(cliente__nombre__icontains=query)
    if estado_filter:
        trabajos = trabajos.filter(estado=estado_filter)
    if categoria_filter:
        trabajos = trabajos.filter(categoria_dispositivo=categoria_filter)

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
        Trabajo.objects.select_related('cliente').prefetch_related('pagos')
        .filter(
            estado=Trabajo.Estado.ENTREGADO,
            fecha_entrega__year=anio_e, fecha_entrega__month=mes_e,
        )
    )

    estados_filtro = [
        (value, label) for value, label in Trabajo.Estado.choices
        if value != Trabajo.Estado.ENTREGADO
    ]

    return render(request, 'taller/trabajos_list.html', {
        'trabajos': _con_indicador_pago(trabajos),
        'entregados': _con_indicador_pago(entregados),
        'query': query,
        'estado_filter': estado_filter,
        'categoria_filter': categoria_filter,
        'estados': Trabajo.Estado.choices,
        'estados_filtro': estados_filtro,
        'dispositivo_choices': Trabajo.CategoriaDispositivo.choices,
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
    try:
        trabajo.delete()
    except ProtectedError:
        messages.error(
            request,
            f'El trabajo de {trabajo.cliente.nombre} tiene pagos registrados '
            'y no se puede eliminar.',
        )
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
    if mes_param:
        parsed = _parse_mes_param(mes_param)
        if parsed is None:
            return redirect(request.path)
        anio, mes = parsed
    else:
        anio, mes = hoy.year, hoy.month

    anio_prev, mes_prev = analytics.mes_anterior(anio, mes)
    anio_next, mes_next = analytics.mes_siguiente(anio, mes)

    gastos_mes = Gasto.objects.filter(fecha__year=anio, fecha__month=mes)

    return render(request, 'taller/gasto_form.html', {
        'form': form,
        'mes_fecha': date(anio, mes, 1),
        'mes_anterior_valor': f'{anio_prev:04d}-{mes_prev:02d}',
        'mes_siguiente_valor': f'{anio_next:04d}-{mes_next:02d}',
        'puede_avanzar': (anio, mes) < (hoy.year, hoy.month),
        'gastos_mes': gastos_mes,
        'total_mes': Gasto.objects.total_mes(anio, mes),
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


def _pago_context(request):
    return {
        'pagos_historial': Pago.objects.select_related('trabajo__cliente').all(),
        'trabajo_resaltado': _trabajo_resaltado_desde_request(request),
    }


def pago_create(request):
    if request.method == 'POST':
        form = PagoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('taller:pago_create')
    else:
        form = PagoForm(initial={'fecha': timezone.now().date()})

    context = {'form': form}
    context.update(_pago_context(request))
    return render(request, 'taller/pago_form.html', context)


def pago_edit(request, pk):
    pago = get_object_or_404(Pago, pk=pk)

    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            form.save()
            return redirect('taller:pago_create')
    else:
        form = PagoForm(instance=pago)

    context = {'form': form}
    context.update(_pago_context(request))
    return render(request, 'taller/pago_form.html', context)


CATEGORIA_COLORES = {
    'repuesto': '#1c1c1a',
    'herramienta': '#c9a24b',
    'taller': '#7c3aed',
    'otro': '#8891a5',
}

CATEGORIA_DISPOSITIVO_COLORES = {
    'celular': '#1c1c1a',
    'consola': '#c9a24b',
    'notebook': '#7c3aed',
    'otro': '#8891a5',
}

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
            'color': CATEGORIA_COLORES.get(value, '#8891a5'),
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
            'color': CATEGORIA_DISPOSITIVO_COLORES.get(value, '#8891a5'),
        })
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
        'Cliente', 'Teléfono', 'Categoría', 'Subtipo', 'Problema', 'Estado',
        'Precio', 'Fecha ingreso', 'Fecha entrega', 'Total pagado', 'Estado de pago',
    ])
    trabajos = Trabajo.objects.select_related('cliente').prefetch_related('pagos').all()
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
            t.cliente.nombre,
            t.cliente.telefono,
            t.get_categoria_dispositivo_display(),
            t.get_subtipo_dispositivo_display() or '—',
            t.descripcion_problema,
            t.get_estado_display(),
            moneda(t.precio_acordado),
            fecha_fmt(t.fecha_ingreso),
            fecha_fmt(t.fecha_entrega),
            moneda(total_pagado),
            estado_pago,
        ])

    ws_gastos = wb.create_sheet('Gastos')
    ws_gastos.append(['Descripción', 'Proveedor', 'Categoría', 'Monto', 'Fecha'])
    for g in Gasto.objects.all():
        ws_gastos.append([
            g.descripcion,
            g.proveedor or '—',
            g.get_categoria_display(),
            moneda(g.monto),
            fecha_fmt(g.fecha),
        ])

    ws_pagos = wb.create_sheet('Pagos')
    ws_pagos.append(['Número', 'Cliente', 'Monto', 'Forma de pago', 'Fecha', 'Detalle'])
    for p in Pago.objects.select_related('trabajo__cliente').all():
        ws_pagos.append([
            f'Pago #{p.pk}',
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
