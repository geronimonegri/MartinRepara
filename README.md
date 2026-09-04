# MartinRepara
Sistema de gestión para [MartinRepara] — reparación de celulares, joysticks, PS4 y notebooks. Panel administrativo interno (Django), pensado para uso de una sola persona.

Se puede usar de dos formas: como sitio web local (`manage.py runserver`, para desarrollo) o como **app de escritorio para Windows** (un único `.exe`, sin depender de un navegador ni de tener el servidor corriendo a mano).

## Desarrollo web

```
cd admin
..\venv\Scripts\python.exe manage.py migrate
..\venv\Scripts\python.exe manage.py runserver
```

La base se guarda en `admin\db.sqlite3` (gitignoreada). `admin\.env.example` documenta las variables de entorno para producción (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`).

## App de escritorio (Windows)

### Generar el .exe

Desde `admin\`, con el venv del proyecto instalado (`pip install -r requirements.txt`):

```
build.bat
```

Esto corre `collectstatic` y después PyInstaller. El resultado queda en `admin\dist\MartinRepara.exe` — un único archivo, sin consola, con el ícono del logo. Para reconstruirlo después de cualquier cambio de código, volvé a correr `build.bat`.

### Cómo funciona

- `app.py` es el punto de entrada: levanta Django embebido (sin `manage.py runserver`) en un puerto libre de `127.0.0.1`, aplica `migrate` automáticamente, y abre una ventana nativa (pywebview) apuntando al Dashboard.
- **La base de datos vive fuera del .exe**, en `%APPDATA%\MartinRepara\db.sqlite3`. Así las actualizaciones (generar un `.exe` nuevo con `build.bat`) nunca pisan los datos cargados.
- Cada vez que se abre la app se guarda una copia de la base en `%APPDATA%\MartinRepara\backups\db_YYYY-MM-DD.sqlite3` (se conservan las últimas 30). Desde el ítem **"Copia de seguridad"** al pie del menú también se puede exportar la base a cualquier carpeta (pendrive, Drive, etc.) cuando se quiera.
- `MartinRepara.spec` es la configuración de PyInstaller (qué se empaqueta, ícono, modo ventana sin consola). Si se agregan archivos estáticos nuevos o apps de Django nuevas, puede ser necesario ajustar la lista `datas`/`hiddenimports` ahí.

### Iconos y estáticos

`martinrepara.ico` se genera una vez a partir de `taller/static/taller/img/logo.jpeg` (no hace falta regenerarlo salvo que cambie el logo). Los estáticos (CSS, logo) se empaquetan desde `admin\staticfiles\`, por eso `build.bat` corre `collectstatic` antes de PyInstaller — si se edita el CSS y se corre PyInstaller solo, el `.exe` va a tener la versión vieja.
