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
    'consola': (
        _SVG_OPEN
        + '<rect x="2" y="7" width="20" height="11" rx="5.5"/>'
        + '<line x1="7" y1="12" x2="11" y2="12"/>'
        + '<line x1="9" y1="10" x2="9" y2="14"/>'
        + '<circle cx="16" cy="10.5" r="0.9" fill="currentColor"/>'
        + '<circle cx="18" cy="13" r="0.9" fill="currentColor"/></svg>'
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
}


@register.simple_tag
def device_icon(tipo):
    return mark_safe(_DEVICE_ICONS.get(tipo, ''))


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
