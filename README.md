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

