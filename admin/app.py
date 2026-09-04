"""Punto de entrada de la app de escritorio (Windows).

Levanta Django embebido (sin manage.py runserver) y lo muestra en una
ventana nativa con pywebview. Esto es lo que empaqueta PyInstaller para
generar MartinRepara.exe (ver MartinRepara.spec / build.bat).

Para desarrollo web normal seguí usando manage.py runserver: este
script es solo para la app de escritorio.
"""
import datetime
import os
import shutil
import socket
import sys
import threading
from pathlib import Path

BACKUPS_A_CONSERVAR = 30


def _base_dir():
    """Carpeta del proyecto Django (contiene config/, taller/, staticfiles/).

    - Corriendo desde código fuente: admin/ (donde vive este archivo).
    - Empaquetado con PyInstaller (onefile): sys._MEIPASS, la carpeta
      temporal donde PyInstaller extrae los "datas" del build en cada
      arranque. MartinRepara.spec bundlea config/, taller/, staticfiles/
      y martinrepara.ico ahí, con la misma estructura que admin/, así que
      todo el código que resuelve rutas relativas a BASE_DIR (incluido
      config/settings.py) funciona igual en los dos casos.
    """
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


BASE_DIR = _base_dir()
APPDATA_DIR = Path(os.environ.get('APPDATA', str(Path.home()))) / 'MartinRepara'
BACKUPS_DIR = APPDATA_DIR / 'backups'
DB_PATH = APPDATA_DIR / 'db.sqlite3'
ICON_PATH = BASE_DIR / 'martinrepara.ico'


def preparar_carpetas():
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def hacer_backup_diario():
    """Copia la base a backups/db_YYYY-MM-DD.sqlite3 y conserva las últimas 30.

    Si es la primera vez que se abre la app todavía no hay base (la crea
    `migrate` más adelante), así que no hay nada que respaldar todavía.
    """
    if not DB_PATH.exists():
        return

    hoy = datetime.date.today().isoformat()
    destino = BACKUPS_DIR / f'db_{hoy}.sqlite3'
    shutil.copy2(DB_PATH, destino)

    backups = sorted(BACKUPS_DIR.glob('db_*.sqlite3'))
    de_mas = len(backups) - BACKUPS_A_CONSERVAR
    for viejo in backups[:max(de_mas, 0)]:
        viejo.unlink(missing_ok=True)


def puerto_libre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def iniciar_django():
    """Configura Django, migra, y devuelve la app WSGI lista para servir."""
    sys.path.insert(0, str(BASE_DIR))

    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    os.environ['DB_PATH'] = str(DB_PATH)
    os.environ['MODO_ESCRITORIO'] = 'True'
    os.environ.setdefault('DEBUG', 'False')
    os.environ.setdefault('ALLOWED_HOSTS', '127.0.0.1,localhost')

    import django
    django.setup()

    from django.core.management import call_command
    call_command('migrate', verbosity=0, interactive=False)

    from django.core.wsgi import get_wsgi_application
    return get_wsgi_application()


def iniciar_servidor(application, port):
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIRequestHandler, WSGIServer

    class HandlerSilencioso(WSGIRequestHandler):
        def log_message(self, *args):
            pass

    class ServidorConHilos(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    httpd = ServidorConHilos(('127.0.0.1', port), HandlerSilencioso)
    httpd.set_app(application)

    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    return httpd


class ApiVentana:
    """Puente JS -> Python. Se expone en la página como window.pywebview.api.

    El botón "Salir" del sidebar (solo visible en modo escritorio, ver
    taller/context_processors.py) llama a cerrar_app() después de que el
    usuario confirma en un window.confirm() de JS.
    """

    def cerrar_app(self):
        import webview
        if webview.windows:
            webview.windows[0].destroy()


def main():
    preparar_carpetas()
    hacer_backup_diario()

    application = iniciar_django()
    port = puerto_libre()
    httpd = iniciar_servidor(application, port)

    import webview

    webview.create_window(
        'Martín repara',
        f'http://127.0.0.1:{port}/',
        width=1280,
        height=800,
        min_size=(960, 640),
        js_api=ApiVentana(),
    )

    try:
        webview.start(icon=str(ICON_PATH) if ICON_PATH.exists() else None)
    except TypeError:
        # Algunas versiones/backends de pywebview no aceptan `icon`.
        webview.start()

    httpd.shutdown()
    httpd.server_close()


if __name__ == '__main__':
    main()
