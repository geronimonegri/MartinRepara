from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from taller.forms import _sincronizar_gasto_tercerizado
from taller.models import (
    CategoriaGasto,
    Cliente,
    Correlativo,
    Gasto,
    Marca,
    Modelo,
    Pago,
    Proveedor,
    RepuestoUsado,
    Tercero,
    TipoDispositivo,
    TipoReparacion,
    TipoRepuesto,
    Trabajo,
)


class Command(BaseCommand):
    """Carga datos de demostración/prueba.

    Se implementa como management command (en vez de un script pasado por
    `manage.py shell < archivo.py`) a propósito: Python siempre decodifica
    los archivos .py como UTF-8 al importarlos (PEP 3120), sin importar el
    codepage de la consola. Pasar un script por stdin en Windows, en
    cambio, usa la codificación de la consola (normalmente cp1252), lo que
    corrompía los nombres con tildes/eñes (mojibake por doble codificación).

    No toca los catálogos (TipoDispositivo, CategoriaGasto, Marca, etc.):
    esos los carga la migración de datos y sobreviven a los reseed.
    """

    help = 'Carga (o recarga) datos de demostración para Trabajo/Gasto/Cliente/Pago.'

    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='martin', email='', password='martinrepara2026'
            )
            self.stdout.write(self.style.SUCCESS(
                'Superusuario creado: usuario "martin" / contraseña '
                '"martinrepara2026" (cambiarla en producción).'
            ))

        RepuestoUsado.objects.all().delete()
        Pago.objects.all().delete()
        Trabajo.objects.all().delete()
        Gasto.objects.all().delete()
        Cliente.objects.all().delete()
        # Reiniciar la numeración para que el demo siempre arranque en 0001.
        Correlativo.objects.filter(
            tipo__in=[Correlativo.TRABAJO, Correlativo.GASTO, Correlativo.PAGO]
        ).update(ultimo_numero=0)

        def cliente(nombre, telefono):
            return Cliente.objects.create(nombre=nombre, telefono=telefono)

        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        tipo_consola = TipoDispositivo.objects.get(nombre='Consola')
        tipo_notebook = TipoDispositivo.objects.get(nombre='Notebook')

        cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        cat_herramientas = CategoriaGasto.objects.get(nombre='Herramientas')
        cat_alquiler = CategoriaGasto.objects.get(nombre='Alquiler')
        cat_otro = CategoriaGasto.objects.get(nombre='Otro')

        prov_norte = Proveedor.objects.get_or_create(nombre='Distribuidora Norte')[0]
        prov_repuestosya = Proveedor.objects.get_or_create(nombre='RepuestosYa')[0]
        prov_ferreteria = Proveedor.objects.get_or_create(nombre='Ferretería Sur')[0]
        tercero_taller_amigo = Tercero.objects.get_or_create(
            nombre='Taller Amigo', defaults={'telefono': '11-9988-7766'}
        )[0]

        tr_otro_consola = TipoRepuesto.objects.get(nombre='Otro', tipo_dispositivo=tipo_consola)
        tr_glass = TipoRepuesto.objects.get(nombre='Glass', tipo_dispositivo=tipo_celular)
        tr_bateria = TipoRepuesto.objects.get(nombre='Batería', tipo_dispositivo=tipo_celular)
        tr_elemento_notebook = TipoRepuesto.objects.get(
            nombre='Elemento electrónico', tipo_dispositivo=tipo_notebook
        )
        marca_apple = Marca.objects.get(nombre='Apple', tipo_dispositivo=tipo_celular)
        marca_samsung = Marca.objects.get(nombre='Samsung', tipo_dispositivo=tipo_celular)
        marca_ps4 = Marca.objects.get(nombre='PS4', tipo_dispositivo=tipo_consola)
        marca_xbox = Marca.objects.get(nombre='Xbox', tipo_dispositivo=tipo_consola)

        rep_glass = TipoReparacion.objects.get(nombre='Cambio de glass', tipo_dispositivo=tipo_celular)
        rep_bateria = TipoReparacion.objects.get(nombre='Cambio de batería', tipo_dispositivo=tipo_celular)
        rep_modulo = TipoReparacion.objects.get(nombre='Cambio de módulo', tipo_dispositivo=tipo_celular)
        rep_teclado = TipoReparacion.objects.get(nombre='Elemento electrónico', tipo_dispositivo=tipo_notebook)

        def gasto_repuesto(descripcion, proveedor, cantidad, precio_unitario, fecha,
                            tipo_dispositivo, tipo_repuesto, marca=None):
            return Gasto.objects.create(
                descripcion=descripcion, categoria=cat_repuestos, proveedor=proveedor,
                monto=cantidad * precio_unitario, fecha=fecha, tipo_dispositivo=tipo_dispositivo,
                tipo_repuesto=tipo_repuesto, marca=marca,
                cantidad=cantidad, precio_unitario=precio_unitario,
            )

        nahuel = cliente('Nahuel Torres', '11-6677-8899')
        marcos = cliente('Marcos Díaz', '11-2345-6789')
        ezequiel = cliente('Ezequiel Sosa', '11-8899-0011')
        lucia = cliente('Lucía Fernández', '11-3344-5566')
        franco = cliente('Franco Gómez', '11-4455-6677')
        valentina = cliente('Valentina Ruiz', '11-5566-7788')
        camila = cliente('Camila López', '11-7788-9900')

        Trabajo.objects.create(
            cliente=nahuel, tipo_dispositivo=tipo_notebook,
            descripcion_problema='No enciende, posible fuente', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('18000'), fecha_ingreso=date(2026, 7, 22),
        )
        Trabajo.objects.create(
            cliente=marcos, tipo_dispositivo=tipo_celular, marca=marca_samsung,
            descripcion_problema='Pantalla rota, no enciende', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 20),
        )
        Trabajo.objects.create(
            cliente=ezequiel, tipo_dispositivo=tipo_consola,
            descripcion_problema='No conecta por bluetooth', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('6000'), fecha_ingreso=date(2026, 7, 19),
        )
        Trabajo.objects.create(
            cliente=lucia, tipo_dispositivo=tipo_consola,
            descripcion_problema='Joystick derecho hace drift', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('8000'), fecha_ingreso=date(2026, 7, 18),
        )
        Trabajo.objects.create(
            cliente=franco, tipo_dispositivo=tipo_consola, marca=marca_ps4,
            descripcion_problema='No lee discos', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('22000'), fecha_ingreso=date(2026, 7, 15),
        )
        trabajo_valentina = Trabajo.objects.create(
            cliente=valentina, tipo_dispositivo=tipo_celular, marca=marca_apple,
            tipo_reparacion=rep_bateria,
            descripcion_problema='Batería se agota muy rápido', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('12000'), fecha_ingreso=date(2026, 7, 10),
            fecha_entrega=date(2026, 7, 14),
        )
        Pago.objects.create(trabajo=trabajo_valentina, monto=Decimal('12000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 14))

        trabajo_camila = Trabajo.objects.create(
            cliente=camila, tipo_dispositivo=tipo_celular, marca=marca_samsung,
            tipo_reparacion=rep_glass, detalle='Se cambió el glass, quedó como nuevo.',
            descripcion_problema='Cambio de pantalla', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('20000'), fecha_ingreso=date(2026, 7, 5),
            fecha_entrega=date(2026, 7, 8),
        )
        Pago.objects.create(trabajo=trabajo_camila, monto=Decimal('20000'),
                             forma_pago=Pago.FormaPago.TRANSFERENCIA, fecha=date(2026, 7, 9))

        gasto_pantalla = gasto_repuesto('Pantalla Samsung A52', prov_norte, 3, Decimal('8000'), date(2026, 7, 19),
                                         tipo_celular, tr_glass, marca_samsung)
        gasto_repuesto('Módulo analógico joystick', prov_repuestosya, 5, Decimal('700'), date(2026, 7, 17),
                        tipo_consola, tr_otro_consola)
        Gasto.objects.create(descripcion='Pasta térmica', monto=Decimal('900'),
                              categoria=cat_otro, fecha=date(2026, 7, 15))
        Gasto.objects.create(descripcion='Alcohol isopropílico', monto=Decimal('1200'),
                              categoria=cat_otro, fecha=date(2026, 7, 12))
        Gasto.objects.create(descripcion='Kit destornilladores de precisión', monto=Decimal('5200'),
                              categoria=cat_herramientas, fecha=date(2026, 7, 10))
        Gasto.objects.create(descripcion='Alquiler del local', monto=Decimal('2100'),
                              categoria=cat_alquiler, fecha=date(2026, 7, 5))

        # Ejemplo de repuesto usado: descuenta stock del gasto de arriba
        # (compró 3 pantallas a $8.000, esta usa 1 -> quedan 2 en Stock).
        RepuestoUsado.objects.create(trabajo=trabajo_camila, gasto=gasto_pantalla, cantidad=1)

        # Historial de meses previos, solo para que el gráfico de evolución
        # (últimos 6 meses) tenga variación en vez de mostrarse plano.
        trabajo_nahuel_abril = Trabajo.objects.create(
            cliente=nahuel, tipo_dispositivo=tipo_celular, marca=marca_samsung,
            tipo_reparacion=rep_bateria,
            descripcion_problema='Cambio de batería', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('9000'), fecha_ingreso=date(2026, 4, 3),
            fecha_entrega=date(2026, 4, 5),
        )
        Pago.objects.create(trabajo=trabajo_nahuel_abril, monto=Decimal('9000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 4, 5))
        gasto_repuesto('Batería Samsung A52', prov_repuestosya, 2, Decimal('1500'), date(2026, 4, 4),
                        tipo_celular, tr_bateria, marca_samsung)

        trabajo_lucia_mayo = Trabajo.objects.create(
            cliente=lucia, tipo_dispositivo=tipo_consola, marca=marca_ps4,
            descripcion_problema='Limpieza y cambio de pasta térmica', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('14000'), fecha_ingreso=date(2026, 5, 8),
            fecha_entrega=date(2026, 5, 10),
        )
        Pago.objects.create(trabajo=trabajo_lucia_mayo, monto=Decimal('14000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 5, 10))
        Gasto.objects.create(descripcion='Pasta térmica y limpieza', monto=Decimal('4500'),
                              categoria=cat_otro, fecha=date(2026, 5, 9))

        # Ejemplo de tercerización: el trabajo se manda a un tercero y eso
        # genera solo un Gasto "Tercerizado" vinculado (igual que haría el
        # formulario de Trabajo).
        trabajo_ezequiel_junio = Trabajo.objects.create(
            cliente=ezequiel, tipo_dispositivo=tipo_notebook, tipo_reparacion=rep_teclado,
            descripcion_problema='Cambio de teclado', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('26000'), fecha_ingreso=date(2026, 6, 2),
            fecha_entrega=date(2026, 6, 6),
            tercero=tercero_taller_amigo, tercerizado_detalle='microsoldadura del conector',
            tercerizado_monto=Decimal('6000'),
        )
        _sincronizar_gasto_tercerizado(trabajo_ezequiel_junio)
        Pago.objects.create(trabajo=trabajo_ezequiel_junio, monto=Decimal('26000'),
                             forma_pago=Pago.FormaPago.TARJETA, fecha=date(2026, 6, 6))
        gasto_repuesto('Teclado notebook', prov_norte, 1, Decimal('7000'), date(2026, 6, 3),
                        tipo_notebook, tr_elemento_notebook)
        Gasto.objects.create(descripcion='Alquiler del local', monto=Decimal('2100'),
                              categoria=cat_alquiler, fecha=date(2026, 6, 5))

        # Modelos (catálogo sin seed propio: se cargan ad-hoc, como haría el
        # botón "+" del formulario) para que el ranking de marcas/modelos
        # tenga de dónde sacar variedad.
        modelo_iphone11 = Modelo.objects.get_or_create(nombre='iPhone 11', marca=marca_apple)[0]
        modelo_iphone12 = Modelo.objects.get_or_create(nombre='iPhone 12', marca=marca_apple)[0]
        modelo_a52 = Modelo.objects.get_or_create(nombre='Galaxy A52', marca=marca_samsung)[0]
        modelo_a32 = Modelo.objects.get_or_create(nombre='Galaxy A32', marca=marca_samsung)[0]

        # Agosto: otro ejemplo de tercerización (distinto mes/dispositivo del
        # de junio) y más variedad de marca/modelo para el ranking.
        rocio = cliente('Rocío Medina', '11-1122-3344')
        trabajo_rocio_agosto = Trabajo.objects.create(
            cliente=rocio, tipo_dispositivo=tipo_celular, marca=marca_apple, modelo=modelo_iphone11,
            tipo_reparacion=rep_modulo,
            descripcion_problema='No carga, conector dañado', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('17000'), fecha_ingreso=date(2026, 8, 6),
            fecha_entrega=date(2026, 8, 9),
        )
        Pago.objects.create(trabajo=trabajo_rocio_agosto, monto=Decimal('17000'),
                             forma_pago=Pago.FormaPago.TRANSFERENCIA, fecha=date(2026, 8, 9))

        bruno = cliente('Bruno Aquino', '11-2233-4455')
        trabajo_bruno_agosto = Trabajo.objects.create(
            cliente=bruno, tipo_dispositivo=tipo_consola, marca=marca_xbox,
            descripcion_problema='Se apaga solo, sobrecalentamiento', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('19000'), fecha_ingreso=date(2026, 8, 14),
            fecha_entrega=date(2026, 8, 18),
            tercero=tercero_taller_amigo, tercerizado_detalle='cambio de pasta y limpieza de disipador',
            tercerizado_monto=Decimal('5000'),
        )
        _sincronizar_gasto_tercerizado(trabajo_bruno_agosto)
        Pago.objects.create(trabajo=trabajo_bruno_agosto, monto=Decimal('19000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 8, 18))

        # Trabajo sin marca ni tipo de reparación: cae en "Sin especificar"
        # en los rankings, no se descarta.
        Trabajo.objects.create(
            cliente=nahuel, tipo_dispositivo=tipo_notebook,
            descripcion_problema='Revisión general, hace ruido el cooler', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('10000'), fecha_ingreso=date(2026, 8, 22),
        )

        # Septiembre (mes actual de la demo): así el período por defecto
        # ("Este mes") de Estadísticas no arranca vacío.
        gasto_glass_sept = gasto_repuesto('Pantalla Galaxy A32', prov_norte, 2, Decimal('7500'),
                                           date(2026, 9, 2), tipo_celular, tr_glass, marca_samsung)
        trabajo_marcos_sept = Trabajo.objects.create(
            cliente=marcos, tipo_dispositivo=tipo_celular, marca=marca_samsung, modelo=modelo_a32,
            tipo_reparacion=rep_glass,
            descripcion_problema='Glass roto', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('16000'), fecha_ingreso=date(2026, 9, 3),
            fecha_entrega=date(2026, 9, 4),
        )
        RepuestoUsado.objects.create(trabajo=trabajo_marcos_sept, gasto=gasto_glass_sept, cantidad=1)
        Pago.objects.create(trabajo=trabajo_marcos_sept, monto=Decimal('16000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 9, 4))

        Trabajo.objects.create(
            cliente=valentina, tipo_dispositivo=tipo_celular, marca=marca_apple, modelo=modelo_iphone12,
            tipo_reparacion=rep_bateria,
            descripcion_problema='Batería inflada', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('13000'), fecha_ingreso=date(2026, 9, 5),
        )

        # Otro trabajo con Samsung pero sin modelo cargado, y sin tipo de
        # reparación: prueba "Sin especificar" en la vista por defecto.
        Trabajo.objects.create(
            cliente=camila, tipo_dispositivo=tipo_celular, marca=marca_samsung,
            descripcion_problema='No prende', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('14000'), fecha_ingreso=date(2026, 9, 6),
        )

        Trabajo.objects.create(
            cliente=franco, tipo_dispositivo=tipo_notebook,
            descripcion_problema='Presupuesto para cambio de pantalla', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=None, fecha_ingreso=date(2026, 9, 7),
        )

        Gasto.objects.create(descripcion='Alquiler del local', monto=Decimal('2100'),
                              categoria=cat_alquiler, fecha=date(2026, 9, 5))

        self.stdout.write(self.style.SUCCESS(
            f'Seed OK: {Cliente.objects.count()} clientes, '
            f'{Trabajo.objects.count()} trabajos, {Gasto.objects.count()} gastos, '
            f'{Pago.objects.count()} pagos'
        ))
