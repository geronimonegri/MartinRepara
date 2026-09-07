# MartinRepara

Aplicación de escritorio para la gestión integral de un taller de reparación de celulares, tablets, consolas, joysticks y notebooks. Reemplaza el cuaderno y las planillas sueltas por un solo lugar donde registrar trabajos, gastos, pagos y stock, y saber qué reparaciones dejan más ganancia.

Desarrollada a pedido de un emprendimiento real, para uso de una sola persona, sin depender de internet.

## Funcionalidades

**Trabajos**
- Alta de trabajos con cliente, tipo de dispositivo, marca, modelo, problema y tipo de reparación.
- Estados: Recibido → En reparación → Listo → Entregado, con cambio inline desde la lista.
- Repuestos usados por trabajo (descuentan stock automáticamente).
- Tercerización opcional: a quién se derivó, qué hizo y cuánto se le pagó (genera el gasto solo).
- Ganancia por trabajo calculada: precio − repuestos − tercerizado.
- Sección de entregados por mes, filtros por estado y dispositivo, búsqueda por cliente.

**Gastos y stock**
- Categorías y subcategorías (Repuestos, Herramientas, Membresías, Publicidad, Alquiler, Accesorios, Otro).
- Repuestos con proveedor, tipo, marca, modelo, cantidad y precio unitario.
- Pantalla de Stock con disponible por repuesto y total valorizado.

**Pagos**
- Pagos parciales o totales por trabajo, con forma de pago (efectivo, transferencia, tarjeta).
- Indicador de pago parcial / completo en cada trabajo.

**Balance y estadísticas**
- Balance mensual: ingresos, gastos, resultado, variación contra el mes anterior, ingresos pendientes.
- Evolución del balance en 6 meses, gastos por categoría, ingresos por dispositivo.
- Estadísticas por período: reparaciones más frecuentes con margen %, ranking de marcas y modelos, repuestos más usados, y un tablero por tipo de dispositivo.

**Otros**
- Comprobantes numerados automáticamente: `T-0001` (trabajos), `G-0001` (gastos), `P-0001` (pagos).
- Catálogos editables desde Configuración: dispositivos, categorías, marcas, modelos, tipos de reparación, proveedores.
- Copias de seguridad automáticas al abrir y exportación manual a cualquier carpeta.
- Exportación a Excel (trabajos, gastos y pagos).
- Funciona completamente sin conexión.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3, Django |
| Base de datos | SQLite (archivo local) |
| Frontend | Django templates, CSS propio, Chart.js (servido local) |
| Ventana de escritorio | pywebview |
| Empaquetado | PyInstaller (único `.exe` para Windows) |
| Excel | openpyxl |
| Tests | Django TestCase (más de 100 tests) |

## Cómo funciona la app de escritorio

`admin/app.py` es el punto de entrada. Al ejecutar el `.exe`:

1. Levanta Django embebido en un puerto libre de `127.0.0.1` (no usa `runserver`).
2. Aplica las migraciones pendientes, así las actualizaciones nunca requieren pasos manuales.
3. Guarda una copia de la base en `%APPDATA%\MartinRepara\backups\db_YYYY-MM-DD.sqlite3` (conserva las últimas 30).
4. Abre una ventana nativa de 1280×800 apuntando al Dashboard.
5. Al cerrar la ventana, apaga el servidor.

La base de datos vive **fuera** del ejecutable, en `%APPDATA%\MartinRepara\db.sqlite3`. Reemplazar el `.exe` por una versión nueva nunca toca los datos cargados.

## Desarrollo local

```bash
git clone https://github.com/geronimonegri/MartinRepara.git
cd MartinRepara
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

cd admin
python manage.py migrate
python manage.py seed_demo     # opcional: datos de prueba
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/`. En modo web la base se guarda en `admin/db.sqlite3` (ignorada por Git) y los ítems exclusivos de escritorio (Copia de seguridad, Exportar a Excel, Salir) se ocultan o avisan que no están disponibles.

`admin/.env.example` documenta las variables de entorno (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_PATH`) por si algún día se despliega como sitio web.

### Tests

```bash
cd admin
python manage.py test
```

## Generar el ejecutable

Desde `admin/`, con el venv activado:

```bash
build.bat
```

El script corre `collectstatic` y después PyInstaller. El resultado queda en `admin/dist/MartinRepara.exe`: un único archivo, sin consola, con el ícono del logo.

Notas:
- `MartinRepara.spec` define qué se empaqueta (`datas`, `hiddenimports`, ícono, modo ventana). Si se agregan estáticos o apps de Django nuevas, puede haber que ajustarlo.
- Los estáticos se toman de `admin/staticfiles/`, generada por `collectstatic`. Si se edita el CSS y se corre PyInstaller a mano sin ese paso, el `.exe` queda con la versión vieja; por eso conviene usar siempre `build.bat`.
- `martinrepara.ico` se genera a partir de `taller/static/taller/img/logo.jpeg`; solo hay que regenerarlo si cambia el logo.

## Instalación en la PC del usuario

1. Copiar `MartinRepara.exe` a una carpeta fija, por ejemplo `C:\MartinRepara\`.
2. Crear un acceso directo en el escritorio.
3. La primera vez Windows puede mostrar "Windows protegió su PC" porque el ejecutable no está firmado: *Más información → Ejecutar de todas formas*.
4. Para actualizar, reemplazar el `.exe`. Los datos quedan intactos en `%APPDATA%`.

## Estructura del proyecto

```
MartinRepara/
└── admin/
    ├── app.py                 # Punto de entrada de la app de escritorio
    ├── build.bat              # Genera el .exe
    ├── MartinRepara.spec      # Configuración de PyInstaller
    ├── config/                # Settings y URLs del proyecto Django
    └── taller/                # App principal
        ├── models.py          # Cliente, Trabajo, Gasto, Pago, RepuestoUsado, catálogos
        ├── analytics.py       # Cálculos de balance y estadísticas
        ├── views.py, forms.py, urls.py
        ├── templates/taller/
        ├── static/taller/     # CSS, JS (Chart.js local), logo
        └── tests.py
```

## Roadmap

- Sitio web público del taller (presentación de servicios y contacto).
- Comprobante imprimible para entregar al cliente.
- Recordatorios de trabajos demorados.
