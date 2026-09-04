from django.conf import settings


def escritorio(request):
    """Expone si estamos corriendo como app de escritorio (app.py + pywebview)
    o como sitio web normal (manage.py runserver), para mostrar u ocultar
    en los templates lo que solo tiene sentido en uno de los dos modos
    (ej: el botón "Salir" que cierra la ventana)."""
    return {'modo_escritorio': settings.MODO_ESCRITORIO}
