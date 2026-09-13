from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_SVG_OPEN = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
)

_DEVICE_ICONS = {
    'celular': (
        _SVG_OPEN
        + '<rect x="6" y="2" width="12" height="20" rx="2"/>'
        + '<line x1="12" y1="18" x2="12.01" y2="18"/></svg>'
    ),
    'tablet': (
        _SVG_OPEN
        + '<rect x="4" y="3" width="16" height="18" rx="2"/>'
        + '<line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    ),
    'consola': (
        _SVG_OPEN
        + '<rect x="2" y="7" width="20" height="11" rx="5.5"/>'
        + '<line x1="7" y1="12" x2="11" y2="12"/>'
        + '<line x1="9" y1="10" x2="9" y2="14"/>'
        + '<circle cx="16" cy="10.5" r="0.9" fill="currentColor"/>'
        + '<circle cx="18" cy="13" r="0.9" fill="currentColor"/></svg>'
    ),
    'joystick': (
        _SVG_OPEN
        + '<path d="M6 9h12l2 9a2.5 2.5 0 0 1-4.5 1.5L14 17h-4l-1.5 2.5A2.5 2.5 0 0 1 4 18z"/>'
        + '<line x1="8" y1="12" x2="8" y2="15"/>'
        + '<line x1="6.5" y1="13.5" x2="9.5" y2="13.5"/>'
        + '<circle cx="16" cy="12.5" r="0.9" fill="currentColor"/>'
        + '<circle cx="18" cy="14.5" r="0.9" fill="currentColor"/></svg>'
    ),
    'dispositivo de audio': (
        _SVG_OPEN
        + '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/>'
        + '<rect x="2" y="14" width="5" height="7" rx="1.5"/>'
        + '<rect x="17" y="14" width="5" height="7" rx="1.5"/></svg>'
    ),
    'notebook': (
        _SVG_OPEN
        + '<rect x="3" y="4" width="18" height="12" rx="2"/>'
        + '<line x1="2" y1="20" x2="22" y2="20"/></svg>'
    ),
    'otro': (
        _SVG_OPEN
        + '<circle cx="12" cy="12" r="9"/>'
        + '<path d="M9.5 9a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2.2-2.4 2.2"/>'
        + '<line x1="12" y1="16.5" x2="12.01" y2="16.5"/></svg>'
    ),
}

_NAV_ICONS = {
    'dashboard': (
        _SVG_OPEN
        + '<rect x="3" y="3" width="7" height="7" rx="1.5"/>'
        + '<rect x="14" y="3" width="7" height="7" rx="1.5"/>'
        + '<rect x="14" y="14" width="7" height="7" rx="1.5"/>'
        + '<rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>'
    ),
    'list': (
        _SVG_OPEN
        + '<line x1="8" y1="6" x2="21" y2="6"/>'
        + '<line x1="8" y1="12" x2="21" y2="12"/>'
        + '<line x1="8" y1="18" x2="21" y2="18"/>'
        + '<line x1="3" y1="6" x2="3.01" y2="6"/>'
        + '<line x1="3" y1="12" x2="3.01" y2="12"/>'
        + '<line x1="3" y1="18" x2="3.01" y2="18"/></svg>'
    ),
    'bar-chart': (
        _SVG_OPEN
        + '<line x1="18" y1="20" x2="18" y2="10"/>'
        + '<line x1="12" y1="20" x2="12" y2="4"/>'
        + '<line x1="6" y1="20" x2="6" y2="14"/></svg>'
    ),
    'wrench': (
        _SVG_OPEN
        + '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77'
        + 'a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91'
        + 'a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>'
    ),
    'file-text': (
        _SVG_OPEN
        + '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        + '<polyline points="14 2 14 8 20 8"/>'
        + '<line x1="16" y1="13" x2="8" y2="13"/>'
        + '<line x1="16" y1="17" x2="8" y2="17"/></svg>'
    ),
    'plus': (
        _SVG_OPEN
        + '<line x1="12" y1="5" x2="12" y2="19"/>'
        + '<line x1="5" y1="12" x2="19" y2="12"/></svg>'
    ),
    'edit': (
        _SVG_OPEN
        + '<path d="M12 20h9"/>'
        + '<path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>'
    ),
    'dollar-sign': (
        _SVG_OPEN
        + '<line x1="12" y1="1" x2="12" y2="23"/>'
        + '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
    ),
    'trash': (
        _SVG_OPEN
        + '<polyline points="3 6 5 6 21 6"/>'
        + '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        + '<line x1="10" y1="11" x2="10" y2="17"/>'
        + '<line x1="14" y1="11" x2="14" y2="17"/></svg>'
    ),
    'logout': (
        _SVG_OPEN
        + '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
        + '<polyline points="16 17 21 12 16 7"/>'
        + '<line x1="21" y1="12" x2="9" y2="12"/></svg>'
    ),
    'backup': (
        _SVG_OPEN
        + '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        + '<polyline points="7 10 12 15 17 10"/>'
        + '<line x1="12" y1="15" x2="12" y2="3"/></svg>'
    ),
    'box': (
        _SVG_OPEN
        + '<path d="M21 8 12 3 3 8l9 5 9-5z"/>'
        + '<path d="M3 8v8l9 5 9-5V8"/>'
        + '<line x1="12" y1="13" x2="12" y2="21"/></svg>'
    ),
    'settings': (
        _SVG_OPEN
        + '<circle cx="12" cy="12" r="3"/>'
        + '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>'
    ),
    'table': (
        _SVG_OPEN
        + '<rect x="3" y="3" width="18" height="18" rx="2"/>'
        + '<line x1="3" y1="9" x2="21" y2="9"/>'
        + '<line x1="3" y1="15" x2="21" y2="15"/>'
        + '<line x1="9" y1="9" x2="9" y2="21"/>'
        + '<line x1="15" y1="9" x2="15" y2="21"/></svg>'
    ),
    'trending-up': (
        _SVG_OPEN
        + '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
        + '<polyline points="17 6 23 6 23 12"/></svg>'
    ),
}


@register.simple_tag
def device_icon(tipo):
    clave = str(tipo).lower() if tipo else ''
    return mark_safe(_DEVICE_ICONS.get(clave, _DEVICE_ICONS['otro']))


@register.simple_tag
def nav_icon(nombre):
    return mark_safe(_NAV_ICONS.get(nombre, ''))


@register.filter
def moneda(value):
    if value is None:
        value = 0
    entero = int(round(value))
    signo = '-' if entero < 0 else ''
    formateado = f'{abs(entero):,}'.replace(',', '.')
    return f'{signo}${formateado}'


@register.filter
def gasto_repuesto_label(gasto):
    """"G-0012 · Batería · Samsung A52 · $9.000 · quedan 3" para el
    <select> de repuestos usados. Misma fórmula que
    forms.RepuestoUsadoForm._gasto_label (duplicada a propósito para no
    acoplar templatetags con forms)."""
    if not gasto:
        return ''
    tipo_repuesto = gasto.tipo_repuesto.nombre if gasto.tipo_repuesto_id else '—'
    marca_modelo = gasto.marca.nombre if gasto.marca_id else ''
    if gasto.modelo_id:
        marca_modelo = f'{marca_modelo} {gasto.modelo.nombre}'.strip()
    partes = [gasto.numero, tipo_repuesto]
    if marca_modelo:
        partes.append(marca_modelo)
    partes.append(moneda(gasto.precio_unitario))
    partes.append(f'quedan {gasto.stock_disponible}')
    return ' · '.join(partes)


@register.filter
def repuesto_usado_chip(repuesto_usado):
    """"Batería · Samsung A52" para el chip debajo de "Problema" en la
    lista de Trabajos (mismo repuesto que gasto_repuesto_label, pero sin
    número/precio/stock — acá interesa qué se usó, no de dónde salió)."""
    gasto = repuesto_usado.gasto
    tipo_repuesto = gasto.tipo_repuesto.nombre if gasto.tipo_repuesto_id else 'Repuesto'
    marca_modelo = gasto.marca.nombre if gasto.marca_id else ''
    if gasto.modelo_id:
        marca_modelo = f'{marca_modelo} {gasto.modelo.nombre}'.strip()
    if marca_modelo:
        return f'{tipo_repuesto} · {marca_modelo}'
    return tipo_repuesto
