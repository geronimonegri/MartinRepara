from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand

from taller.models import Cliente, Gasto, Pago, Trabajo


class Command(BaseCommand):
    """Carga datos de demostración/prueba.

    Se implementa como management command (en vez de un script pasado por
    `manage.py shell < archivo.py`) a propósito: Python siempre decodifica
    los archivos .py como UTF-8 al importarlos (PEP 3120), sin importar el
    codepage de la consola. Pasar un script por stdin en Windows, en
    cambio, usa la codificación de la consola (normalmente cp1252), lo que
    corrompía los nombres con tildes/eñes (mojibake por doble codificación).
    """

    help = 'Carga (o recarga) datos de demostración para Trabajo/Gasto/Cliente.'

    def handle(self, *args, **options):
        Pago.objects.all().delete()
        Trabajo.objects.all().delete()
        Gasto.objects.all().delete()
        Cliente.objects.all().delete()

        def cliente(nombre, telefono):
            return Cliente.objects.create(nombre=nombre, telefono=telefono)

        nahuel = cliente('Nahuel Torres', '11-6677-8899')
        marcos = cliente('Marcos Díaz', '11-2345-6789')
        ezequiel = cliente('Ezequiel Sosa', '11-8899-0011')
        lucia = cliente('Lucía Fernández', '11-3344-5566')
        franco = cliente('Franco Gómez', '11-4455-6677')
        valentina = cliente('Valentina Ruiz', '11-5566-7788')
        camila = cliente('Camila López', '11-7788-9900')

        Trabajo.objects.create(
            cliente=nahuel, categoria_dispositivo=Trabajo.CategoriaDispositivo.NOTEBOOK,
            descripcion_problema='No enciende, posible fuente', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('18000'), fecha_ingreso=date(2026, 7, 22),
        )
        Trabajo.objects.create(
            cliente=marcos, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
            subtipo_dispositivo=Trabajo.SubtipoCelular.ANDROID,
            descripcion_problema='Pantalla rota, no enciende', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 20),
        )
        Trabajo.objects.create(
            cliente=ezequiel, categoria_dispositivo=Trabajo.CategoriaDispositivo.CONSOLA,
            subtipo_dispositivo=Trabajo.SubtipoConsola.OTRO,
            descripcion_problema='No conecta por bluetooth', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('6000'), fecha_ingreso=date(2026, 7, 19),
        )
        Trabajo.objects.create(
            cliente=lucia, categoria_dispositivo=Trabajo.CategoriaDispositivo.CONSOLA,
            subtipo_dispositivo=Trabajo.SubtipoConsola.OTRO,
            descripcion_problema='Joystick derecho hace drift', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('8000'), fecha_ingreso=date(2026, 7, 18),
        )
        Trabajo.objects.create(
            cliente=franco, categoria_dispositivo=Trabajo.CategoriaDispositivo.CONSOLA,
            subtipo_dispositivo=Trabajo.SubtipoConsola.PS4,
            descripcion_problema='No lee discos', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('22000'), fecha_ingreso=date(2026, 7, 15),
        )
        trabajo_valentina = Trabajo.objects.create(
            cliente=valentina, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
            subtipo_dispositivo=Trabajo.SubtipoCelular.IOS,
            descripcion_problema='Batería se agota muy rápido', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('12000'), fecha_ingreso=date(2026, 7, 10),
            fecha_entrega=date(2026, 7, 14),
        )
        Pago.objects.create(trabajo=trabajo_valentina, monto=Decimal('12000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 14))

        trabajo_camila = Trabajo.objects.create(
            cliente=camila, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
            subtipo_dispositivo=Trabajo.SubtipoCelular.ANDROID,
            descripcion_problema='Cambio de pantalla', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('20000'), fecha_ingreso=date(2026, 7, 5),
            fecha_entrega=date(2026, 7, 8),
        )
        Pago.objects.create(trabajo=trabajo_camila, monto=Decimal('20000'),
                             forma_pago=Pago.FormaPago.TRANSFERENCIA, fecha=date(2026, 7, 9))

        Gasto.objects.create(descripcion='Pantalla iPhone 11', proveedor='Distribuidora Norte',
                              monto=Decimal('8000'), categoria=Gasto.Categoria.REPUESTO, fecha=date(2026, 7, 19))
        Gasto.objects.create(descripcion='Módulo analógico joystick', proveedor='RepuestosYa',
                              monto=Decimal('3500'), categoria=Gasto.Categoria.REPUESTO, fecha=date(2026, 7, 17))
        Gasto.objects.create(descripcion='Pasta térmica', proveedor='',
                              monto=Decimal('900'), categoria=Gasto.Categoria.OTRO, fecha=date(2026, 7, 15))
        Gasto.objects.create(descripcion='Alcohol isopropílico', proveedor='',
                              monto=Decimal('1200'), categoria=Gasto.Categoria.OTRO, fecha=date(2026, 7, 12))
        Gasto.objects.create(descripcion='Kit destornilladores de precisión', proveedor='Ferretería Sur',
                              monto=Decimal('5200'), categoria=Gasto.Categoria.HERRAMIENTA, fecha=date(2026, 7, 10))
        Gasto.objects.create(descripcion='Alquiler del local', proveedor='',
                              monto=Decimal('2100'), categoria=Gasto.Categoria.TALLER, fecha=date(2026, 7, 5))

        # Historial de meses previos, solo para que el gráfico de evolución
        # (últimos 6 meses) tenga variación en vez de mostrarse plano.
        trabajo_nahuel_abril = Trabajo.objects.create(
            cliente=nahuel, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
            subtipo_dispositivo=Trabajo.SubtipoCelular.ANDROID,
            descripcion_problema='Cambio de batería', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('9000'), fecha_ingreso=date(2026, 4, 3),
            fecha_entrega=date(2026, 4, 5),
        )
        Pago.objects.create(trabajo=trabajo_nahuel_abril, monto=Decimal('9000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 4, 5))
        Gasto.objects.create(descripcion='Repuestos varios', proveedor='RepuestosYa',
                              monto=Decimal('3000'), categoria=Gasto.Categoria.REPUESTO, fecha=date(2026, 4, 4))

        trabajo_lucia_mayo = Trabajo.objects.create(
            cliente=lucia, categoria_dispositivo=Trabajo.CategoriaDispositivo.CONSOLA,
            subtipo_dispositivo=Trabajo.SubtipoConsola.PS4,
            descripcion_problema='Limpieza y cambio de pasta térmica', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('14000'), fecha_ingreso=date(2026, 5, 8),
            fecha_entrega=date(2026, 5, 10),
        )
        Pago.objects.create(trabajo=trabajo_lucia_mayo, monto=Decimal('14000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 5, 10))
        Gasto.objects.create(descripcion='Pasta térmica y limpieza', proveedor='',
                              monto=Decimal('4500'), categoria=Gasto.Categoria.OTRO, fecha=date(2026, 5, 9))

        trabajo_ezequiel_junio = Trabajo.objects.create(
            cliente=ezequiel, categoria_dispositivo=Trabajo.CategoriaDispositivo.NOTEBOOK,
            descripcion_problema='Cambio de teclado', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('26000'), fecha_ingreso=date(2026, 6, 2),
            fecha_entrega=date(2026, 6, 6),
        )
        Pago.objects.create(trabajo=trabajo_ezequiel_junio, monto=Decimal('26000'),
                             forma_pago=Pago.FormaPago.TARJETA, fecha=date(2026, 6, 6))
        Gasto.objects.create(descripcion='Teclado notebook', proveedor='Distribuidora Norte',
                              monto=Decimal('7000'), categoria=Gasto.Categoria.REPUESTO, fecha=date(2026, 6, 3))
        Gasto.objects.create(descripcion='Alquiler del local', proveedor='',
                              monto=Decimal('2100'), categoria=Gasto.Categoria.TALLER, fecha=date(2026, 6, 5))

        self.stdout.write(self.style.SUCCESS(
            f'Seed OK: {Cliente.objects.count()} clientes, '
            f'{Trabajo.objects.count()} trabajos, {Gasto.objects.count()} gastos, '
            f'{Pago.objects.count()} pagos'
        ))
