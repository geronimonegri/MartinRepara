from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from . import analytics
from .forms import (
    GastoForm,
    MarcaForm,
    ModeloForm,
    PagoForm,
    RepuestoUsadoForm,
    SubcategoriaGastoForm,
    TrabajoForm,
    _sincronizar_gasto_tercerizado,
)
from .models import (
    CategoriaGasto,
    Cliente,
    Correlativo,
    Gasto,
    Marca,
    Modelo,
    Pago,
    Proveedor,
    RepuestoUsado,
    SubcategoriaGasto,
    Tercero,
    TipoDispositivo,
    TipoReparacion,
    TipoRepuesto,
    Trabajo,
)


class TotalPagadoTests(TestCase):
    """Trabajo.total_pagado() / esta_pagado() con pagos parciales y sobrepago."""

    def setUp(self):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cliente = Cliente.objects.create(nombre='Ana Ruiz', telefono='11-1111-1111')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=tipo_celular,
            descripcion_problema='Pantalla rota', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('10000'), fecha_ingreso=date(2026, 7, 1),
        )

    def test_sin_pagos(self):
        self.assertEqual(self.trabajo.total_pagado(), Decimal('0'))
        self.assertFalse(self.trabajo.esta_pagado())

    def test_pago_parcial(self):
        Pago.objects.create(trabajo=self.trabajo, monto=Decimal('4000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 5))
        self.assertEqual(self.trabajo.total_pagado(), Decimal('4000'))
        self.assertFalse(self.trabajo.esta_pagado())

    def test_sobrepago_queda_marcado_como_pagado(self):
        Pago.objects.create(trabajo=self.trabajo, monto=Decimal('6000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 5))
        Pago.objects.create(trabajo=self.trabajo, monto=Decimal('6000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 6))
        self.assertEqual(self.trabajo.total_pagado(), Decimal('12000'))
        self.assertTrue(self.trabajo.esta_pagado())


class TrabajoDeleteTests(TestCase):
    """Un trabajo con pagos no se puede borrar: sin 500, con mensaje, sin borrarlo."""

    def setUp(self):
        self.user = User.objects.create_user(username='martin', password='x')
        self.client.force_login(self.user)
        self.tipo_consola = TipoDispositivo.objects.get(nombre='Consola')
        self.tipo_notebook = TipoDispositivo.objects.get(nombre='Notebook')
        cliente = Cliente.objects.create(nombre='Bruno Aquino', telefono='11-2222-2222')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_consola,
            descripcion_problema='Limpieza', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('10000'), fecha_ingreso=date(2026, 7, 1),
            fecha_entrega=date(2026, 7, 2),
        )
        Pago.objects.create(trabajo=self.trabajo, monto=Decimal('10000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 2))

    def test_no_tira_500_y_no_borra(self):
        response = self.client.post(
            reverse('taller:trabajo_delete', args=[self.trabajo.pk]), follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Trabajo.objects.filter(pk=self.trabajo.pk).exists())

    def test_muestra_mensaje_de_error(self):
        response = self.client.post(
            reverse('taller:trabajo_delete', args=[self.trabajo.pk]), follow=True
        )
        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(any('no se puede eliminar' in m for m in mensajes))

    def test_trabajo_sin_pagos_si_se_puede_borrar(self):
        cliente = Cliente.objects.create(nombre='Otro Cliente', telefono='11-3333-3333')
        trabajo_sin_pagos = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_notebook,
            descripcion_problema='Revisión', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('5000'), fecha_ingreso=date(2026, 7, 1),
        )
        self.client.post(reverse('taller:trabajo_delete', args=[trabajo_sin_pagos.pk]))
        self.assertFalse(Trabajo.objects.filter(pk=trabajo_sin_pagos.pk).exists())


class BalanceAnalyticsTests(TestCase):
    """balance_mensual / comparacion_mes_anterior en cruce de año y balance anterior = 0."""

    def setUp(self):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        cliente = Cliente.objects.create(nombre='Lucía Fernández', telefono='11-4444-4444')
        trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=tipo_celular,
            descripcion_problema='Batería', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('9000'), fecha_ingreso=date(2025, 12, 20),
            fecha_entrega=date(2025, 12, 28),
        )
        Pago.objects.create(trabajo=trabajo, monto=Decimal('9000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2025, 12, 28))
        Gasto.objects.create(descripcion='Repuesto', monto=Decimal('3000'),
                              categoria=cat_repuestos, fecha=date(2025, 12, 22))

    def test_cruce_de_anio_diciembre_a_enero(self):
        # Enero 2026 no tiene datos; el mes anterior (diciembre 2025) sí.
        self.assertEqual(analytics.mes_anterior(2026, 1), (2025, 12))
        balance_enero = analytics.balance_mensual(2026, 1)
        balance_diciembre = analytics.balance_mensual(2025, 12)
        self.assertEqual(balance_enero, Decimal('0'))
        self.assertEqual(balance_diciembre, Decimal('6000'))

    def test_comparacion_con_mes_anterior_sin_datos_no_divide_por_cero(self):
        # Diciembre 2025 es el primer mes con datos: noviembre 2025 esta en 0.
        comparacion = analytics.comparacion_mes_anterior(2025, 12)
        self.assertEqual(comparacion['balance_anterior'], Decimal('0'))
        self.assertIsNone(comparacion['variacion_pct'])

    def test_comparacion_cruzando_a_enero(self):
        comparacion = analytics.comparacion_mes_anterior(2026, 1)
        self.assertEqual(comparacion['anio_anterior'], 2025)
        self.assertEqual(comparacion['mes_anterior'], 12)
        self.assertEqual(comparacion['balance_anterior'], Decimal('6000'))


class MesFueraDeRangoTests(TestCase):
    """?mes= fuera de 1-12 en balance/gasto_create/pago_create/trabajos_list:
    sin 500, redirige."""

    def setUp(self):
        self.user = User.objects.create_user(username='martin', password='x')
        self.client.force_login(self.user)

    def test_balance_mes_13_redirige(self):
        response = self.client.get(reverse('taller:balance'), {'mes': '2026-13'})
        self.assertEqual(response.status_code, 302)

    def test_balance_mes_00_redirige(self):
        response = self.client.get(reverse('taller:balance'), {'mes': '2026-00'})
        self.assertEqual(response.status_code, 302)

    def test_gasto_create_mes_13_redirige(self):
        response = self.client.get(reverse('taller:gasto_create'), {'mes': '2026-13'})
        self.assertEqual(response.status_code, 302)

    def test_pago_create_mes_13_redirige(self):
        response = self.client.get(reverse('taller:pago_create'), {'mes': '2026-13'})
        self.assertEqual(response.status_code, 302)

    def test_pago_create_mes_00_redirige(self):
        response = self.client.get(reverse('taller:pago_create'), {'mes': '2026-00'})
        self.assertEqual(response.status_code, 302)

    def test_trabajos_list_mes_entregados_13_redirige(self):
        response = self.client.get(
            reverse('taller:trabajos_list'), {'mes_entregados': '2026-13'}
        )
        self.assertEqual(response.status_code, 302)

    def test_balance_mes_invalido_redirige_a_pagina_usable(self):
        response = self.client.get(
            reverse('taller:balance'), {'mes': '2026-13'}, follow=True
        )
        self.assertEqual(response.status_code, 200)


class MontoNegativoTests(TestCase):
    """Los formularios rechazan montos negativos (pero no montos en 0)."""

    def setUp(self):
        self.tipo_notebook = TipoDispositivo.objects.get(nombre='Notebook')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        cliente = Cliente.objects.create(nombre='Sofía Medina', telefono='11-5555-5555')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_notebook,
            descripcion_problema='SSD', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('20000'), fecha_ingreso=date(2026, 7, 1),
        )

    def test_trabajo_precio_negativo_invalido(self):
        form = TrabajoForm(data={
            'cliente_nombre': 'Test', 'cliente_telefono': '11-9999-9999',
            'tipo_dispositivo': self.tipo_notebook.pk,
            'descripcion_problema': 'test', 'precio_acordado': '-500',
            'fecha_ingreso': '2026-07-01',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('precio_acordado', form.errors)

    def test_gasto_monto_negativo_invalido(self):
        form = GastoForm(data={
            'descripcion': 'x', 'monto': '-100',
            'categoria': self.cat_otro.pk, 'fecha': '2026-07-01',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('monto', form.errors)

    def test_pago_monto_negativo_invalido(self):
        form = PagoForm(data={
            'monto': '-50', 'forma_pago': 'efectivo', 'fecha': '2026-07-01',
            'trabajo': self.trabajo.pk, 'detalle': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('monto', form.errors)

    def test_gasto_monto_cero_es_valido(self):
        # 0 no es negativo: el validador es >= 0, no debe romper este caso limite.
        form = GastoForm(data={
            'descripcion': 'x', 'monto': '0',
            'categoria': self.cat_otro.pk, 'fecha': '2026-07-01',
        })
        self.assertTrue(form.is_valid(), form.errors)


class PagoFormSinNMasUnoTests(TestCase):
    """PagoForm ya no dispara un query aparte por cada trabajo del <select>.

    En vez de fijar un número exacto de queries (frágil ante detalles
    internos del ORM), compara la cantidad de queries con pocos y con
    muchos trabajos: si no escala con N, no hay N+1.
    """

    @staticmethod
    def _crear_trabajos(cantidad):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cliente = Cliente.objects.create(nombre='Rodrigo Paz', telefono='11-6666-6666')
        for i in range(cantidad):
            Trabajo.objects.create(
                cliente=cliente, tipo_dispositivo=tipo_celular,
                descripcion_problema=f'Trabajo {i}', estado=Trabajo.Estado.EN_REPARACION,
                precio_acordado=Decimal('1000'), fecha_ingreso=date(2026, 7, 1),
            )

    def test_renderizar_select_de_trabajo_no_escala_con_la_cantidad(self):
        self._crear_trabajos(3)
        with CaptureQueriesContext(connection) as pocas:
            str(PagoForm()['trabajo'])

        Trabajo.objects.all().delete()
        Cliente.objects.all().delete()
        self._crear_trabajos(20)
        with CaptureQueriesContext(connection) as muchas:
            str(PagoForm()['trabajo'])

        self.assertEqual(len(pocas.captured_queries), len(muchas.captured_queries))


class NumeracionCorrelativaTests(TestCase):
    """T-0001/G-0001/P-0001: correlativos, únicos, y no se reutilizan al borrar."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.cliente = Cliente.objects.create(nombre='Nico Bianchi', telefono='11-7777-7777')

    def _nuevo_trabajo(self):
        return Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('1000'), fecha_ingreso=date(2026, 7, 1),
        )

    def test_numeros_correlativos_y_con_prefijo(self):
        t1 = self._nuevo_trabajo()
        t2 = self._nuevo_trabajo()
        t3 = self._nuevo_trabajo()
        self.assertEqual([t1.numero, t2.numero, t3.numero], ['T-0001', 'T-0002', 'T-0003'])

    def test_numero_no_editable_por_el_usuario(self):
        trabajo = self._nuevo_trabajo()
        trabajo.numero = 'T-9999'
        trabajo.save()
        trabajo.refresh_from_db()
        # save() solo asigna numero si estaba vacío: al ya tener uno, no lo pisa,
        # pero tampoco lo dejamos como campo editable desde un form (editable=False).
        self.assertEqual(trabajo.numero, 'T-9999')
        self.assertNotIn('numero', TrabajoForm().fields)

    def test_no_se_reutiliza_el_numero_al_borrar(self):
        t1 = self._nuevo_trabajo()
        numero_t1 = t1.numero
        t1.delete()
        t2 = self._nuevo_trabajo()
        # T-0001 quedó "retirado" (como un talonario real): el siguiente es
        # T-0002, no vuelve a ser T-0001.
        self.assertNotEqual(t2.numero, numero_t1)
        self.assertEqual(t2.numero, 'T-0002')

    def test_numeracion_independiente_por_tipo(self):
        Correlativo.objects.filter(tipo=Correlativo.GASTO).delete()
        gasto = Gasto.objects.create(
            descripcion='x', monto=Decimal('100'), categoria=self.cat_otro, fecha=date(2026, 7, 1),
        )
        trabajo = self._nuevo_trabajo()
        self.assertTrue(gasto.numero.startswith('G-'))
        self.assertTrue(trabajo.numero.startswith('T-'))

    def test_numeros_unicos(self):
        numeros = {self._nuevo_trabajo().numero for _ in range(5)}
        self.assertEqual(len(numeros), 5)


class GastoRepuestoTests(TestCase):
    """Categoría Repuestos: monto = cantidad × precio unitario, y campos requeridos."""

    def setUp(self):
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tipo_repuesto = TipoRepuesto.objects.filter(
            tipo_dispositivo=self.tipo_celular
        ).first()
        self.marca = Marca.objects.filter(tipo_dispositivo=self.tipo_celular).first()
        self.proveedor = Proveedor.objects.create(nombre='Distribuidora Test')

    def _datos_repuesto(self, **overrides):
        datos = {
            'fecha': '2026-07-01',
            'categoria': self.cat_repuestos.pk,
            'descripcion': 'Glass iPhone 11',
            'proveedor': self.proveedor.pk,
            'tipo_dispositivo': self.tipo_celular.pk,
            'tipo_repuesto': self.tipo_repuesto.pk,
            'marca': self.marca.pk,
            'cantidad': '3',
            'precio_unitario': '1500',
        }
        datos.update(overrides)
        return datos

    def test_monto_se_calcula_cantidad_por_precio_unitario(self):
        form = GastoForm(data=self._datos_repuesto())
        self.assertTrue(form.is_valid(), form.errors)
        gasto = form.save()
        self.assertEqual(gasto.monto, Decimal('4500'))

    def test_stock_disponible_arranca_igual_a_cantidad(self):
        form = GastoForm(data=self._datos_repuesto(cantidad='5'))
        self.assertTrue(form.is_valid(), form.errors)
        gasto = form.save()
        self.assertEqual(gasto.stock_disponible, 5)

    def test_repuestos_sin_proveedor_es_invalido(self):
        form = GastoForm(data=self._datos_repuesto(proveedor=''))
        self.assertFalse(form.is_valid())
        self.assertIn('proveedor', form.errors)

    def test_repuestos_sin_cantidad_es_invalido(self):
        form = GastoForm(data=self._datos_repuesto(cantidad=''))
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad', form.errors)

    def test_categoria_otro_no_exige_campos_de_repuesto(self):
        form = GastoForm(data={
            'fecha': '2026-07-01', 'categoria': self.cat_otro.pk,
            'descripcion': 'Alquiler', 'monto': '2000',
        })
        self.assertTrue(form.is_valid(), form.errors)
        gasto = form.save()
        self.assertIsNone(gasto.proveedor)
        self.assertIsNone(gasto.cantidad)
        self.assertIsNone(gasto.stock_disponible)


class RepuestoUsadoStockTests(TestCase):
    """Alta descuenta stock, edición ajusta la diferencia, borrado devuelve
    (incluido el borrado en cascada cuando se borra el Trabajo)."""

    def setUp(self):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        cliente = Cliente.objects.create(nombre='Cliente Stock', telefono='11-0000-0001')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        self.gasto = Gasto.objects.create(
            descripcion='Glass', categoria=cat_repuestos, fecha=date(2026, 7, 1),
            cantidad=10, precio_unitario=Decimal('1000'), monto=Decimal('10000'),
        )

    def test_alta_descuenta_stock(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=3)
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 7)

    def test_editar_cantidad_ajusta_la_diferencia(self):
        ru = RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=3)
        ru.cantidad = 5
        ru.save()
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 5)  # 10 - 5

    def test_borrar_devuelve_stock(self):
        ru = RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=4)
        ru.delete()
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 10)

    def test_borrar_trabajo_devuelve_stock_en_cascada(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=4)
        self.trabajo.delete()
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 10)
        self.assertFalse(RepuestoUsado.objects.filter(gasto=self.gasto).exists())

    def test_cambiar_de_repuesto_ajusta_los_dos_stocks(self):
        gasto2 = Gasto.objects.create(
            descripcion='Batería', categoria=self.gasto.categoria, fecha=date(2026, 7, 1),
            cantidad=5, precio_unitario=Decimal('2000'), monto=Decimal('10000'),
        )
        ru = RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=2)
        ru.gasto = gasto2
        ru.cantidad = 1
        ru.save()
        self.gasto.refresh_from_db()
        gasto2.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 10)
        self.assertEqual(gasto2.stock_disponible, 4)


class RepuestoUsadoValidacionStockTests(TestCase):
    """El formulario no deja usar más repuestos de los que hay disponibles."""

    def setUp(self):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.gasto = Gasto.objects.create(
            descripcion='Glass', categoria=cat_repuestos, fecha=date(2026, 7, 1),
            cantidad=2, precio_unitario=Decimal('1000'), monto=Decimal('2000'),
        )

    def test_no_permite_pedir_mas_stock_del_disponible(self):
        form = RepuestoUsadoForm(data={'gasto': self.gasto.pk, 'cantidad': '5'})
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad', form.errors)

    def test_permite_usar_exactamente_el_stock_disponible(self):
        form = RepuestoUsadoForm(data={'gasto': self.gasto.pk, 'cantidad': '2'})
        self.assertTrue(form.is_valid(), form.errors)


class TercerizadoGastoTests(TestCase):
    """El Gasto "Tercerizado" se crea/actualiza/borra solo, según
    tercerizado_monto, y no se puede editar desde Gastos (linkea al
    trabajo)."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tercero = Tercero.objects.create(nombre='Juan')
        self.cliente = Cliente.objects.create(nombre='Cliente Tercero', telefono='11-0000-0002')

    def _crear_trabajo(self, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_crea_gasto_tercerizado_al_sincronizar(self):
        trabajo = self._crear_trabajo(
            tercero=self.tercero, tercerizado_detalle='cambio de módulo',
            tercerizado_monto=Decimal('3000'),
        )
        _sincronizar_gasto_tercerizado(trabajo)
        gasto = Gasto.objects.get(trabajo=trabajo)
        self.assertEqual(gasto.categoria.nombre, 'Tercerizado')
        self.assertEqual(gasto.monto, Decimal('3000'))
        self.assertIn(trabajo.numero, gasto.descripcion)
        self.assertIn('Juan', gasto.descripcion)
        self.assertIn('cambio de módulo', gasto.descripcion)

    def test_actualiza_el_gasto_si_cambia_el_monto(self):
        trabajo = self._crear_trabajo(tercero=self.tercero, tercerizado_monto=Decimal('3000'))
        _sincronizar_gasto_tercerizado(trabajo)

        trabajo.tercerizado_monto = Decimal('5000')
        trabajo.save()
        _sincronizar_gasto_tercerizado(trabajo)

        self.assertEqual(Gasto.objects.filter(trabajo=trabajo).count(), 1)
        self.assertEqual(Gasto.objects.get(trabajo=trabajo).monto, Decimal('5000'))

    def test_borra_el_gasto_si_se_vacia_el_monto(self):
        trabajo = self._crear_trabajo(tercero=self.tercero, tercerizado_monto=Decimal('3000'))
        _sincronizar_gasto_tercerizado(trabajo)
        self.assertTrue(Gasto.objects.filter(trabajo=trabajo).exists())

        trabajo.tercerizado_monto = None
        trabajo.save()
        _sincronizar_gasto_tercerizado(trabajo)

        self.assertFalse(Gasto.objects.filter(trabajo=trabajo).exists())

    def test_sin_monto_no_crea_gasto(self):
        trabajo = self._crear_trabajo()
        _sincronizar_gasto_tercerizado(trabajo)
        self.assertFalse(Gasto.objects.filter(trabajo=trabajo).exists())


class GananciaTests(TestCase):
    """ganancia = precio_acordado - costo de repuestos usados - tercerizado_monto."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.cliente = Cliente.objects.create(nombre='Cliente Ganancia', telefono='11-0000-0003')

    def _crear_trabajo(self, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_ganancia_sin_repuestos_ni_tercerizado(self):
        trabajo = self._crear_trabajo()
        self.assertEqual(trabajo.ganancia, Decimal('10000'))

    def test_ganancia_descuenta_costo_de_repuestos(self):
        trabajo = self._crear_trabajo()
        gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 7, 1),
            cantidad=5, precio_unitario=Decimal('1000'), monto=Decimal('5000'),
        )
        RepuestoUsado.objects.create(trabajo=trabajo, gasto=gasto, cantidad=2)
        self.assertEqual(trabajo.ganancia, Decimal('8000'))  # 10000 - 2*1000

    def test_ganancia_descuenta_tercerizado(self):
        trabajo = self._crear_trabajo(tercerizado_monto=Decimal('2500'))
        self.assertEqual(trabajo.ganancia, Decimal('7500'))

    def test_ganancia_descuenta_repuestos_y_tercerizado_juntos(self):
        trabajo = self._crear_trabajo(tercerizado_monto=Decimal('1000'))
        gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 7, 1),
            cantidad=5, precio_unitario=Decimal('500'), monto=Decimal('2500'),
        )
        RepuestoUsado.objects.create(trabajo=trabajo, gasto=gasto, cantidad=3)
        self.assertEqual(trabajo.ganancia, Decimal('7500'))  # 10000 - 1500 - 1000

    def test_ganancia_none_sin_precio_acordado(self):
        trabajo = self._crear_trabajo(precio_acordado=None)
        self.assertIsNone(trabajo.ganancia)


class GastoRepuestoUsadoProteccionTests(TestCase):
    """Un Gasto de categoría Repuestos con unidades usadas en algún trabajo
    no se puede eliminar ni sacar de la categoría Repuestos; sí se puede
    editar la cantidad, manteniendo lo ya usado."""

    def setUp(self):
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tipo_repuesto = TipoRepuesto.objects.filter(tipo_dispositivo=self.tipo_celular).first()
        self.marca = Marca.objects.filter(tipo_dispositivo=self.tipo_celular).first()
        self.proveedor = Proveedor.objects.create(nombre='Distribuidora Test')
        self.gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 7, 1),
            proveedor=self.proveedor, tipo_dispositivo=self.tipo_celular,
            tipo_repuesto=self.tipo_repuesto, marca=self.marca,
            cantidad=10, precio_unitario=Decimal('1000'), monto=Decimal('10000'),
        )
        cliente = Cliente.objects.create(nombre='Cliente Repuesto', telefono='11-0000-0009')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 1),
        )

    def _datos_base(self, **overrides):
        datos = {
            'fecha': '2026-07-01',
            'categoria': self.cat_repuestos.pk,
            'descripcion': 'Glass',
            'proveedor': self.proveedor.pk,
            'tipo_dispositivo': self.tipo_celular.pk,
            'tipo_repuesto': self.tipo_repuesto.pk,
            'marca': self.marca.pk,
            'cantidad': '10',
            'precio_unitario': '1000',
        }
        datos.update(overrides)
        return datos

    def test_no_se_puede_eliminar_si_tiene_usos(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=3)
        response = self.client.post(
            reverse('taller:gasto_delete', args=[self.gasto.pk]), follow=True
        )
        self.assertTrue(Gasto.objects.filter(pk=self.gasto.pk).exists())
        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(any(
            self.trabajo.numero in m and 'no se puede eliminar' in m for m in mensajes
        ))

    def test_se_puede_eliminar_sin_usos(self):
        self.client.post(reverse('taller:gasto_delete', args=[self.gasto.pk]))
        self.assertFalse(Gasto.objects.filter(pk=self.gasto.pk).exists())

    def test_editar_cantidad_recalcula_stock_manteniendo_lo_usado(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=3)
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.stock_disponible, 7)  # 10 - 3

        form = GastoForm(data=self._datos_base(cantidad='15'), instance=self.gasto)
        self.assertTrue(form.is_valid(), form.errors)
        gasto = form.save()
        self.assertEqual(gasto.cantidad, 15)
        self.assertEqual(gasto.stock_disponible, 12)  # 15 - 3 ya usadas

    def test_no_permite_bajar_cantidad_por_debajo_de_lo_usado(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=8)
        form = GastoForm(data=self._datos_base(cantidad='5'), instance=self.gasto)
        self.assertFalse(form.is_valid())
        self.assertIn('cantidad', form.errors)

    def test_no_permite_cambiar_de_categoria_si_tiene_usos(self):
        RepuestoUsado.objects.create(trabajo=self.trabajo, gasto=self.gasto, cantidad=2)
        form = GastoForm(
            data={
                'fecha': '2026-07-01', 'categoria': self.cat_otro.pk,
                'descripcion': 'Glass', 'monto': '5000',
            },
            instance=self.gasto,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('categoria', form.errors)


class GastoTercerizadoEditarEliminarTests(TestCase):
    """Los gastos "Tercerizado" no se editan ni eliminan desde Gastos: se
    generan solos desde un Trabajo, y el ícono lleva a ese trabajo."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tercero = Tercero.objects.create(nombre='Juan')
        cliente = Cliente.objects.create(nombre='Cliente Terc Edit', telefono='11-0000-0010')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
            tercero=self.tercero, tercerizado_monto=Decimal('3000'),
        )
        _sincronizar_gasto_tercerizado(self.trabajo)
        self.gasto = Gasto.objects.get(trabajo=self.trabajo)

    def test_editar_redirige_al_trabajo(self):
        response = self.client.get(reverse('taller:gasto_edit', args=[self.gasto.pk]))
        self.assertRedirects(response, reverse('taller:trabajo_edit', args=[self.trabajo.pk]))

    def test_no_se_puede_eliminar(self):
        response = self.client.post(
            reverse('taller:gasto_delete', args=[self.gasto.pk]), follow=True
        )
        self.assertTrue(Gasto.objects.filter(pk=self.gasto.pk).exists())
        mensajes = [str(m) for m in response.context['messages']]
        self.assertTrue(any('no se puede eliminar' in m for m in mensajes))

    def test_no_aparece_en_el_select_de_categoria_de_gastos(self):
        nombres = [c.nombre for c in GastoForm().fields['categoria'].queryset]
        self.assertNotIn('Tercerizado', nombres)


class PagoHistorialMesTests(TestCase):
    """Historial de pagos: filtro por mes (?mes=), redirección al mes de
    la fecha del pago guardado/editado (no al mes actual), y el
    comportamiento de ?trabajo=ID (abre el mes correcto, y si el pago
    resaltado queda más allá del 5° también hay que poder detectarlo
    para expandir la lista)."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cliente = Cliente.objects.create(nombre='Cliente Historial Pagos', telefono='11-0010-0001')

    def _trabajo(self, precio, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=precio,
            fecha_ingreso=date(2026, 7, 1),
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_filtro_por_mes_solo_trae_pagos_de_ese_mes(self):
        trabajo_julio = self._trabajo(Decimal('5000'))
        trabajo_agosto = self._trabajo(Decimal('5000'))
        Pago.objects.create(trabajo=trabajo_julio, monto=Decimal('5000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 10))
        Pago.objects.create(trabajo=trabajo_agosto, monto=Decimal('5000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 8, 10))

        response = self.client.get(reverse('taller:pago_create'), {'mes': '2026-07'})
        pagos_mes = list(response.context['pagos_mes'])
        self.assertEqual(len(pagos_mes), 1)
        self.assertEqual(pagos_mes[0].trabajo_id, trabajo_julio.pk)

    def test_redirige_al_mes_de_la_fecha_del_pago_guardado(self):
        trabajo = self._trabajo(Decimal('8000'))
        response = self.client.post(reverse('taller:pago_create'), data={
            'monto': '8000', 'forma_pago': Pago.FormaPago.EFECTIVO,
            'fecha': '2026-05-15', 'trabajo': trabajo.pk, 'detalle': '',
        })
        self.assertRedirects(response, f"{reverse('taller:pago_create')}?mes=2026-05")

    def test_editar_redirige_al_nuevo_mes_de_la_fecha(self):
        trabajo = self._trabajo(Decimal('8000'))
        pago = Pago.objects.create(trabajo=trabajo, monto=Decimal('8000'),
                                    forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 1))
        response = self.client.post(reverse('taller:pago_edit', args=[pago.pk]), data={
            'monto': '8000', 'forma_pago': Pago.FormaPago.EFECTIVO,
            'fecha': '2026-03-20', 'trabajo': trabajo.pk, 'detalle': '',
        })
        self.assertRedirects(response, f"{reverse('taller:pago_create')}?mes=2026-03")

    def test_eliminar_redirige_al_mes_de_la_fecha_del_pago(self):
        trabajo = self._trabajo(Decimal('8000'))
        pago = Pago.objects.create(trabajo=trabajo, monto=Decimal('8000'),
                                    forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 4, 12))
        response = self.client.post(reverse('taller:pago_delete', args=[pago.pk]))
        self.assertRedirects(response, f"{reverse('taller:pago_create')}?mes=2026-04")

    def test_trabajo_resaltado_abre_el_mes_del_pago_mas_reciente(self):
        trabajo = self._trabajo(Decimal('3000'))
        Pago.objects.create(trabajo=trabajo, monto=Decimal('3000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 6, 18))

        response = self.client.get(reverse('taller:pago_create'), {'trabajo': trabajo.pk})
        self.assertEqual(response.context['mes_fecha'], date(2026, 6, 1))
        self.assertEqual(response.context['trabajo_resaltado'], trabajo.pk)

    def test_trabajo_resaltado_mas_alla_del_quinto_queda_marcado_como_extra(self):
        trabajo_objetivo = self._trabajo(Decimal('1000'))
        Pago.objects.create(trabajo=trabajo_objetivo, monto=Decimal('1000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 1))
        # 5 pagos de otros trabajos, con fecha más reciente: quedan antes
        # que el del trabajo resaltado (orden por -fecha), empujándolo a
        # la posición 6.
        for i in range(5):
            otro = self._trabajo(Decimal('1000'))
            Pago.objects.create(trabajo=otro, monto=Decimal('1000'),
                                 forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 15))

        response = self.client.get(reverse('taller:pago_create'), {'trabajo': trabajo_objetivo.pk})
        pagos_mes = list(response.context['pagos_mes'])
        self.assertEqual(len(pagos_mes), 6)
        self.assertEqual(pagos_mes[5].trabajo_id, trabajo_objetivo.pk)
        # La fila combina las dos clases: resaltada (es el trabajo pedido)
        # y "extra" (más allá del 5°, la que el JS debe des-ocultar).
        self.assertContains(response, 'gasto-history-row-activa gasto-history-row-extra')


class PagoEditarEliminarTests(TestCase):
    """Pago se puede editar y eliminar libremente; el estado de pago del
    trabajo (parcial/completo) no se guarda aparte: sale de sumar los
    Pago existentes, así que se recalcula solo al borrar/editar uno."""

    def setUp(self):
        tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cliente = Cliente.objects.create(nombre='Cliente Pago Edit', telefono='11-0000-0011')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        self.pago = Pago.objects.create(
            trabajo=self.trabajo, monto=Decimal('10000'),
            forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 2),
        )

    def test_trabajo_pagado_por_completo_antes_de_tocar_nada(self):
        self.assertTrue(self.trabajo.esta_pagado())

    def test_eliminar_pago_recalcula_el_estado_a_no_pagado(self):
        numero_borrado = self.pago.numero
        self.client.post(reverse('taller:pago_delete', args=[self.pago.pk]))
        self.assertFalse(Pago.objects.filter(pk=self.pago.pk).exists())

        self.trabajo.refresh_from_db()
        self.assertFalse(self.trabajo.esta_pagado())
        self.assertEqual(self.trabajo.total_pagado(), Decimal('0'))

        nuevo_pago = Pago.objects.create(
            trabajo=self.trabajo, monto=Decimal('1000'),
            forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 3),
        )
        self.assertNotEqual(nuevo_pago.numero, numero_borrado)

    def test_editar_monto_recalcula_estado_de_pago(self):
        self.client.post(reverse('taller:pago_edit', args=[self.pago.pk]), data={
            'monto': '4000', 'forma_pago': Pago.FormaPago.EFECTIVO,
            'fecha': '2026-07-02', 'trabajo': self.trabajo.pk, 'detalle': '',
        })
        self.pago.refresh_from_db()
        self.assertEqual(self.pago.monto, Decimal('4000'))
        self.trabajo.refresh_from_db()
        self.assertFalse(self.trabajo.esta_pagado())


class SelectVaciosConTextoClaroTests(TestCase):
    """Los <select> obligatorios muestran una opción vacía con texto claro
    en vez del "---------" por defecto de Django."""

    def test_categoria_de_gasto(self):
        self.assertEqual(GastoForm().fields['categoria'].empty_label, 'Elegí una categoría')

    def test_categoria_de_subcategoria(self):
        self.assertEqual(SubcategoriaGastoForm().fields['categoria'].empty_label, 'Elegí una categoría')

    def test_tipo_dispositivo_de_marca(self):
        self.assertEqual(MarcaForm().fields['tipo_dispositivo'].empty_label, 'Elegí un tipo de dispositivo')


class RangoPeriodoTests(TestCase):
    """rango_periodo() para cada opción del selector, con un 'hoy' fijo
    (2026-09-15) para que el test no dependa de la fecha real."""

    def setUp(self):
        self.hoy = date(2026, 9, 15)

    def test_este_mes(self):
        desde, hasta = analytics.rango_periodo('mes', hoy=self.hoy)
        self.assertEqual((desde, hasta), (date(2026, 9, 1), self.hoy))

    def test_ultimos_3_meses(self):
        desde, hasta = analytics.rango_periodo('3m', hoy=self.hoy)
        # este mes + 2 anteriores = julio, agosto, septiembre
        self.assertEqual((desde, hasta), (date(2026, 7, 1), self.hoy))

    def test_ultimos_6_meses(self):
        desde, hasta = analytics.rango_periodo('6m', hoy=self.hoy)
        self.assertEqual((desde, hasta), (date(2026, 4, 1), self.hoy))

    def test_este_anio(self):
        desde, hasta = analytics.rango_periodo('anio', hoy=self.hoy)
        self.assertEqual((desde, hasta), (date(2026, 1, 1), self.hoy))

    def test_todo_sin_piso(self):
        self.assertEqual(analytics.rango_periodo('todo', hoy=self.hoy), (None, None))

    def test_cruce_de_anio_en_ultimos_3_meses(self):
        desde, hasta = analytics.rango_periodo('3m', hoy=date(2026, 1, 20))
        self.assertEqual((desde, hasta), (date(2025, 11, 1), date(2026, 1, 20)))


class EstadisticasFiltroPeriodoTests(TestCase):
    """Los trabajos se cuentan por fecha_ingreso y los gastos por su propia
    fecha: un trabajo/gasto fuera del rango no debe aparecer en el resumen."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.cliente = Cliente.objects.create(nombre='Cliente Periodo', telefono='11-0001-0001')

    def test_trabajo_fuera_de_rango_no_se_cuenta(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='dentro', precio_acordado=Decimal('1000'),
            fecha_ingreso=date(2026, 7, 15),
        )
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='fuera', precio_acordado=Decimal('99999'),
            fecha_ingreso=date(2026, 6, 30),
        )
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resumen['trabajos_realizados'], 1)
        self.assertEqual(resumen['ingresos'], Decimal('1000'))

    def test_gasto_fuera_de_rango_no_se_cuenta(self):
        Gasto.objects.create(
            descripcion='dentro', monto=Decimal('500'), categoria=self.cat_otro,
            fecha=date(2026, 7, 10),
        )
        Gasto.objects.create(
            descripcion='fuera', monto=Decimal('88888'), categoria=self.cat_otro,
            fecha=date(2026, 8, 1),
        )
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resumen['gastos'], Decimal('500'))

    def test_periodo_todo_no_filtra_nada(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='viejo', precio_acordado=Decimal('1000'),
            fecha_ingreso=date(2020, 1, 1),
        )
        resumen = analytics.resumen_periodo(None, None)
        self.assertEqual(resumen['trabajos_realizados'], 1)


class GananciaPromedioYMargenTests(TestCase):
    """ganancia_promedio (resumen) y margen_pct (reparaciones_mas_frecuentes),
    incluyendo los casos borde de ingresos/ganancias en cero."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.cliente = Cliente.objects.create(nombre='Cliente Margen', telefono='11-0002-0002')
        self.rep_glass = TipoReparacion.objects.get(nombre='Cambio de glass', tipo_dispositivo=self.tipo_celular)
        self.rep_bateria = TipoReparacion.objects.get(nombre='Cambio de batería', tipo_dispositivo=self.tipo_celular)

    def _trabajo(self, precio, tipo_reparacion=None, fecha=date(2026, 7, 10)):
        return Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            tipo_reparacion=tipo_reparacion,
            descripcion_problema='test', precio_acordado=precio, fecha_ingreso=fecha,
        )

    def test_ganancia_promedio_del_resumen(self):
        self._trabajo(Decimal('10000'), self.rep_bateria)
        self._trabajo(Decimal('20000'), self.rep_glass)
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        # sin repuestos ni tercerizado: ganancia = precio_acordado
        self.assertEqual(resumen['ganancia_total'], Decimal('30000'))
        self.assertEqual(resumen['ganancia_promedio'], Decimal('15000'))

    def test_ganancia_promedio_ignora_trabajos_sin_precio(self):
        self._trabajo(Decimal('10000'), self.rep_bateria)
        self._trabajo(None, self.rep_glass)
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        # el trabajo sin precio no tiene ganancia definida: no entra en el promedio
        self.assertEqual(resumen['ganancia_promedio'], Decimal('10000'))

    def test_ganancia_promedio_cero_sin_trabajos(self):
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resumen['ganancia_promedio'], Decimal('0'))

    def test_margen_pct_con_costo(self):
        trabajo = self._trabajo(Decimal('20000'), self.rep_glass)
        gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 7, 5),
            cantidad=5, precio_unitario=Decimal('2000'), monto=Decimal('10000'),
        )
        RepuestoUsado.objects.create(trabajo=trabajo, gasto=gasto, cantidad=3)
        filas = analytics.reparaciones_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        fila = filas[0]
        # ganancia = 20000 - 3*2000 = 14000; margen = 14000/20000 = 70%
        self.assertEqual(fila['ganancia_total'], Decimal('14000'))
        self.assertEqual(fila['margen_pct'], Decimal('70'))

    def test_margen_pct_none_sin_ingresos(self):
        self._trabajo(None, self.rep_bateria)
        filas = analytics.reparaciones_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertIsNone(filas[0]['margen_pct'])


class SinEspecificarAgrupacionTests(TestCase):
    """Los trabajos sin tipo de reparación, marca o modelo van a "Sin
    especificar" en los rankings, no se descartan."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.marca_apple = Marca.objects.get(nombre='Apple', tipo_dispositivo=self.tipo_celular)
        self.cliente = Cliente.objects.create(nombre='Cliente Sin Especificar', telefono='11-0003-0003')

    def test_reparaciones_sin_tipo_reparacion(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        filas = analytics.reparaciones_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['nombre'], analytics.SIN_ESPECIFICAR)
        self.assertEqual(filas[0]['cantidad'], 1)

    def test_marcas_sin_marca(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        filas = analytics.marcas_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['nombre'], analytics.SIN_ESPECIFICAR)

    def test_modelos_sin_modelo_dentro_de_una_marca_con_datos(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular, marca=self.marca_apple,
            descripcion_problema='test', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        filas = analytics.marcas_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas[0]['nombre'], 'Apple')
        self.assertEqual(filas[0]['modelos'][0]['nombre'], analytics.SIN_ESPECIFICAR)

    def test_no_se_descartan_trabajos_sin_especificar(self):
        # dos trabajos: uno con marca, uno sin -> ambos deben contarse
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular, marca=self.marca_apple,
            descripcion_problema='con marca', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='sin marca', precio_acordado=Decimal('5000'),
            fecha_ingreso=date(2026, 7, 2),
        )
        resumen = analytics.resumen_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resumen['trabajos_realizados'], 2)
        filas = analytics.marcas_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(len(filas), 2)


class GastosPorCategoriaPeriodoTests(TestCase):
    """gastos_por_categoria_periodo (barras) y detalle_categoria_periodo
    (subcategoría, o tipo de repuesto para "Repuestos")."""

    def setUp(self):
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.cat_alquiler = CategoriaGasto.objects.get(nombre='Alquiler')
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tr_glass = TipoRepuesto.objects.get(nombre='Glass', tipo_dispositivo=self.tipo_celular)
        self.tr_bateria = TipoRepuesto.objects.get(nombre='Batería', tipo_dispositivo=self.tipo_celular)

    def test_pct_sobre_el_total(self):
        Gasto.objects.create(descripcion='a', monto=Decimal('3000'), categoria=self.cat_repuestos,
                              fecha=date(2026, 7, 1), cantidad=1, precio_unitario=Decimal('3000'))
        Gasto.objects.create(descripcion='b', monto=Decimal('1000'), categoria=self.cat_alquiler,
                              fecha=date(2026, 7, 2))
        filas = analytics.gastos_por_categoria_periodo(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas[0]['nombre'], 'Repuestos')
        self.assertEqual(filas[0]['total'], Decimal('3000'))
        self.assertEqual(filas[0]['pct'], 75)
        self.assertEqual(filas[1]['pct'], 25)

    def test_detalle_repuestos_por_tipo_de_repuesto(self):
        Gasto.objects.create(descripcion='a', monto=Decimal('2000'), categoria=self.cat_repuestos,
                              fecha=date(2026, 7, 1), tipo_repuesto=self.tr_glass,
                              cantidad=1, precio_unitario=Decimal('2000'))
        Gasto.objects.create(descripcion='b', monto=Decimal('1000'), categoria=self.cat_repuestos,
                              fecha=date(2026, 7, 2), tipo_repuesto=self.tr_bateria,
                              cantidad=1, precio_unitario=Decimal('1000'))
        categoria_id = CategoriaGasto.objects.get(nombre='Repuestos').pk
        detalle = analytics.detalle_categoria_periodo(date(2026, 7, 1), date(2026, 7, 31), categoria_id)
        nombres = [d['nombre'] for d in detalle]
        self.assertIn('Glass', nombres)
        self.assertIn('Batería', nombres)

    def test_detalle_otra_categoria_por_subcategoria(self):
        cat_herramientas = CategoriaGasto.objects.get(nombre='Herramientas')
        sub = SubcategoriaGasto.objects.filter(categoria=cat_herramientas).first()
        Gasto.objects.create(descripcion='pinza', monto=Decimal('1500'), categoria=cat_herramientas,
                              subcategoria=sub, fecha=date(2026, 7, 1))
        detalle = analytics.detalle_categoria_periodo(date(2026, 7, 1), date(2026, 7, 31), cat_herramientas.pk)
        self.assertEqual(detalle[0]['nombre'], sub.nombre)

    def test_sin_gastos_en_el_periodo_devuelve_vacio(self):
        self.assertEqual(analytics.gastos_por_categoria_periodo(date(2026, 7, 1), date(2026, 7, 31)), [])


class RepuestosMasUsadosTests(TestCase):
    """repuestos_mas_usados: unidades consumidas por tipo de repuesto,
    filtrado por dispositivo y contado por fecha_ingreso del trabajo."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tipo_consola = TipoDispositivo.objects.get(nombre='Consola')
        self.cat_repuestos = CategoriaGasto.objects.get(nombre='Repuestos')
        self.tr_glass = TipoRepuesto.objects.get(nombre='Glass', tipo_dispositivo=self.tipo_celular)
        self.cliente = Cliente.objects.create(nombre='Cliente Repuestos Usados', telefono='11-0004-0004')

    def test_cuenta_unidades_usadas_por_tipo_de_repuesto(self):
        trabajo1 = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='t1', precio_acordado=Decimal('5000'), fecha_ingreso=date(2026, 7, 1),
        )
        trabajo2 = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='t2', precio_acordado=Decimal('5000'), fecha_ingreso=date(2026, 7, 2),
        )
        gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 6, 20),
            tipo_repuesto=self.tr_glass, cantidad=10, precio_unitario=Decimal('1000'),
            monto=Decimal('10000'),
        )
        RepuestoUsado.objects.create(trabajo=trabajo1, gasto=gasto, cantidad=2)
        RepuestoUsado.objects.create(trabajo=trabajo2, gasto=gasto, cantidad=3)

        filas = analytics.repuestos_mas_usados(date(2026, 7, 1), date(2026, 7, 31), self.tipo_celular)
        self.assertEqual(filas[0]['nombre'], 'Glass')
        self.assertEqual(filas[0]['cantidad'], 5)
        self.assertEqual(filas[0]['costo'], Decimal('5000'))

    def test_filtra_por_dispositivo(self):
        trabajo_consola = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_consola,
            descripcion_problema='consola', precio_acordado=Decimal('5000'), fecha_ingreso=date(2026, 7, 1),
        )
        gasto = Gasto.objects.create(
            descripcion='Glass', categoria=self.cat_repuestos, fecha=date(2026, 6, 20),
            tipo_repuesto=self.tr_glass, cantidad=10, precio_unitario=Decimal('1000'),
            monto=Decimal('10000'),
        )
        RepuestoUsado.objects.create(trabajo=trabajo_consola, gasto=gasto, cantidad=2)

        filas_celular = analytics.repuestos_mas_usados(date(2026, 7, 1), date(2026, 7, 31), self.tipo_celular)
        self.assertEqual(filas_celular, [])

    def test_marca_de_modelo(self):
        self.assertEqual(ModeloForm().fields['marca'].empty_label, 'Elegí una marca')


class TrabajoFechaEntregaModeloTests(TestCase):
    """Validación de modelo: fecha_entrega solo puede tener valor si el
    estado es "Entregado"."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cliente = Cliente.objects.create(nombre='Cliente Fecha Entrega', telefono='11-0005-0005')

    def _trabajo(self, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('10000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        datos.update(kwargs)
        return Trabajo(**datos)

    def test_fecha_entrega_sin_estado_entregado_es_invalida(self):
        trabajo = self._trabajo(estado=Trabajo.Estado.LISTO, fecha_entrega=date(2026, 7, 5))
        with self.assertRaises(ValidationError):
            trabajo.full_clean()

    def test_fecha_entrega_con_estado_entregado_es_valida(self):
        trabajo = self._trabajo(estado=Trabajo.Estado.ENTREGADO, fecha_entrega=date(2026, 7, 5))
        trabajo.full_clean()  # no debe lanzar

    def test_sin_fecha_entrega_es_valido_en_cualquier_estado(self):
        trabajo = self._trabajo(estado=Trabajo.Estado.RECIBIDO, fecha_entrega=None)
        trabajo.full_clean()  # no debe lanzar


class TrabajoEstadoUpdateFechaEntregaTests(TestCase):
    """Cambio de estado inline: la fecha de entrega es la que manda el
    popup (no se autocompleta), y se limpia sola al retroceder el estado."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        cliente = Cliente.objects.create(nombre='Cliente Estado Inline', telefono='11-0006-0006')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 1),
        )

    def test_entregado_usa_la_fecha_manual_del_popup(self):
        self.client.post(
            reverse('taller:trabajo_estado_update', args=[self.trabajo.pk]),
            data={'estado': 'entregado', 'fecha_entrega': '2026-07-10'},
        )
        self.trabajo.refresh_from_db()
        self.assertEqual(self.trabajo.estado, Trabajo.Estado.ENTREGADO)
        self.assertEqual(self.trabajo.fecha_entrega, date(2026, 7, 10))

    def test_entregado_sin_fecha_en_el_post_usa_hoy(self):
        self.client.post(
            reverse('taller:trabajo_estado_update', args=[self.trabajo.pk]),
            data={'estado': 'entregado'},
        )
        self.trabajo.refresh_from_db()
        self.assertEqual(self.trabajo.fecha_entrega, timezone.now().date())

    def test_retroceder_estado_limpia_fecha_entrega(self):
        self.trabajo.estado = Trabajo.Estado.ENTREGADO
        self.trabajo.fecha_entrega = date(2026, 7, 10)
        self.trabajo.save()

        self.client.post(
            reverse('taller:trabajo_estado_update', args=[self.trabajo.pk]),
            data={'estado': 'listo'},
        )
        self.trabajo.refresh_from_db()
        self.assertEqual(self.trabajo.estado, Trabajo.Estado.LISTO)
        self.assertIsNone(self.trabajo.fecha_entrega)


class TrabajoFormFechaEntregaTests(TestCase):
    """TrabajoForm: fecha_entrega obligatoria solo si el trabajo ya está
    Entregado; si no, se ignora aunque venga cargada en el POST."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cliente = Cliente.objects.create(nombre='Cliente Form Entrega', telefono='11-0007-0007')

    def _datos_base(self, **overrides):
        datos = {
            'cliente_nombre': self.cliente.nombre, 'cliente_telefono': self.cliente.telefono,
            'tipo_dispositivo': self.tipo_celular.pk, 'descripcion_problema': 'test',
            'precio_acordado': '15000', 'fecha_ingreso': '2026-07-01',
        }
        datos.update(overrides)
        return datos

    def test_entregado_sin_fecha_es_invalido(self):
        trabajo = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 1),
            fecha_entrega=date(2026, 7, 3),
        )
        form = TrabajoForm(data=self._datos_base(), instance=trabajo)
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_entrega', form.errors)

    def test_entregado_con_fecha_es_valido_y_se_guarda(self):
        trabajo = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 1),
            fecha_entrega=date(2026, 7, 3),
        )
        form = TrabajoForm(data=self._datos_base(fecha_entrega='2026-07-04'), instance=trabajo)
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertEqual(guardado.fecha_entrega, date(2026, 7, 4))

    def test_no_entregado_ignora_fecha_entrega_cargada(self):
        trabajo = Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.LISTO,
            precio_acordado=Decimal('15000'), fecha_ingreso=date(2026, 7, 1),
        )
        # Alguien manda fecha_entrega en el POST (a mano, o un campo viejo
        # en caché) aunque el trabajo no esté Entregado: se guarda vacío.
        form = TrabajoForm(data=self._datos_base(fecha_entrega='2026-07-04'), instance=trabajo)
        self.assertTrue(form.is_valid(), form.errors)
        guardado = form.save()
        self.assertIsNone(guardado.fecha_entrega)


class BalanceNoDependeDeFechaEntregaTests(TestCase):
    """El Balance de un mes se calcula solo con fecha de Pago y fecha de
    Gasto: cambiar fecha_entrega de un trabajo no debe alterarlo."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        cliente = Cliente.objects.create(nombre='Cliente Balance Fecha', telefono='11-0008-0008')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('20000'), fecha_ingreso=date(2026, 7, 1),
            fecha_entrega=date(2026, 7, 3),
        )
        Pago.objects.create(trabajo=self.trabajo, monto=Decimal('20000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2026, 7, 3))
        Gasto.objects.create(descripcion='Repuesto', monto=Decimal('5000'),
                              categoria=self.cat_otro, fecha=date(2026, 7, 2))

    def test_balance_del_mes_no_cambia_al_modificar_fecha_entrega(self):
        balance_antes = analytics.balance_mensual(2026, 7)

        # Cambia la fecha de entrega a otro mes por completo; el Pago y el
        # Gasto (lo único de lo que depende Balance) no se tocan.
        self.trabajo.fecha_entrega = date(2026, 8, 15)
        self.trabajo.save()

        balance_despues = analytics.balance_mensual(2026, 7)
        self.assertEqual(balance_antes, balance_despues)
        self.assertEqual(balance_antes, Decimal('15000'))  # 20000 - 5000

    def test_ingresos_por_dispositivo_usa_fecha_de_pago_no_de_entrega(self):
        # Pago cargado en julio: cuenta en julio aunque fecha_entrega
        # apunte a agosto.
        self.trabajo.fecha_entrega = date(2026, 8, 15)
        self.trabajo.save()

        filas_julio = list(analytics.pagos_por_categoria_dispositivo(2026, 7))
        filas_agosto = list(analytics.pagos_por_categoria_dispositivo(2026, 8))
        self.assertEqual(len(filas_julio), 1)
        self.assertEqual(filas_julio[0]['total'], Decimal('20000'))
        self.assertEqual(len(filas_agosto), 0)


class TercerizadoMensualTests(TestCase):
    """tercerizado_mensual (usado en la tarjeta "Gastos" de Balance): monto
    y % sobre el total de gastos del mes, ambos por Gasto.fecha."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_tercerizado = CategoriaGasto.objects.get(nombre='Tercerizado')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.tercero = Tercero.objects.create(nombre='Taller Test')
        self.cliente = Cliente.objects.create(nombre='Cliente Tercerizado Mes', telefono='11-0009-0001')

    def test_monto_y_pct_con_gastos_tercerizados(self):
        Gasto.objects.create(descripcion='Otro gasto', monto=Decimal('7000'),
                              categoria=self.cat_otro, fecha=date(2026, 7, 5))
        Gasto.objects.create(descripcion='T-0001 · Taller Test', monto=Decimal('3000'),
                              categoria=self.cat_tercerizado, fecha=date(2026, 7, 10))

        resultado = analytics.tercerizado_mensual(2026, 7)
        self.assertEqual(resultado['monto'], Decimal('3000'))
        self.assertEqual(resultado['pct'], Decimal('30'))  # 3000 / 10000 * 100

    def test_sin_gastos_tercerizados_monto_cero_pero_pct_definido(self):
        Gasto.objects.create(descripcion='Otro gasto', monto=Decimal('5000'),
                              categoria=self.cat_otro, fecha=date(2026, 7, 5))
        resultado = analytics.tercerizado_mensual(2026, 7)
        self.assertEqual(resultado['monto'], Decimal('0'))
        self.assertEqual(resultado['pct'], Decimal('0'))

    def test_sin_ningun_gasto_pct_es_none(self):
        resultado = analytics.tercerizado_mensual(2026, 7)
        self.assertEqual(resultado['monto'], Decimal('0'))
        self.assertIsNone(resultado['pct'])


class TercerizacionResumenTests(TestCase):
    """tercerizacion_resumen (tarjeta del bloque Resumen de Estadísticas)."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.cat_otro = CategoriaGasto.objects.get(nombre='Otro')
        self.tercero = Tercero.objects.create(nombre='Taller Test')
        self.cliente = Cliente.objects.create(nombre='Cliente Resumen Terc', telefono='11-0009-0002')

    def _trabajo(self, tercerizado_monto=None, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('20000'),
            fecha_ingreso=date(2026, 7, 1), tercero=self.tercero if tercerizado_monto else None,
            tercerizado_monto=tercerizado_monto,
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_monto_cantidad_y_porcentajes(self):
        self._trabajo(Decimal('3000'))
        self._trabajo(Decimal('2000'))
        self._trabajo(None)  # no tercerizado, cuenta para el total de trabajos
        Gasto.objects.create(descripcion='x', monto=Decimal('5000'),
                              categoria=self.cat_otro, fecha=date(2026, 7, 1))

        resultado = analytics.tercerizacion_resumen(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resultado['monto'], Decimal('5000'))
        self.assertEqual(resultado['cantidad'], 2)
        self.assertEqual(resultado['pct_trabajos'], Decimal('200') / 3)  # 2/3 * 100
        # Trabajo.objects.create() directo no pasa por _sincronizar_gasto_tercerizado,
        # así que el único Gasto del período es el "Otro" de 5000: 5000/5000 * 100.
        self.assertEqual(resultado['pct_gastos'], Decimal('100'))

    def test_sin_trabajos_todo_en_cero_y_pct_trabajos_none(self):
        resultado = analytics.tercerizacion_resumen(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resultado['monto'], Decimal('0'))
        self.assertEqual(resultado['cantidad'], 0)
        self.assertIsNone(resultado['pct_trabajos'])
        self.assertIsNone(resultado['pct_gastos'])

    def test_sin_gastos_en_el_periodo_pct_gastos_none(self):
        # tercerizado_monto seteado a mano, sin pasar por
        # _sincronizar_gasto_tercerizado: no se genera ningún Gasto.
        self._trabajo(Decimal('3000'))
        resultado = analytics.tercerizacion_resumen(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(resultado['monto'], Decimal('3000'))
        self.assertIsNone(resultado['pct_gastos'])


class TercerizacionPorTerceroTests(TestCase):
    """tercerizacion_por_tercero: cantidad, total y promedio por tercero."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tercero_a = Tercero.objects.create(nombre='Taller A')
        self.tercero_b = Tercero.objects.create(nombre='Taller B')
        self.cliente = Cliente.objects.create(nombre='Cliente Por Tercero', telefono='11-0009-0003')

    def _trabajo(self, tercero, monto, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            descripcion_problema='test', precio_acordado=Decimal('20000'),
            fecha_ingreso=date(2026, 7, 1), tercero=tercero, tercerizado_monto=monto,
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_agrupa_cantidad_total_y_promedio(self):
        self._trabajo(self.tercero_a, Decimal('3000'))
        self._trabajo(self.tercero_a, Decimal('5000'))
        self._trabajo(self.tercero_b, Decimal('1000'))

        filas = analytics.tercerizacion_por_tercero(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(len(filas), 2)
        # ordenado por total desc: Taller A (8000) antes que Taller B (1000)
        self.assertEqual(filas[0]['nombre'], 'Taller A')
        self.assertEqual(filas[0]['cantidad'], 2)
        self.assertEqual(filas[0]['total'], Decimal('8000'))
        self.assertEqual(filas[0]['promedio'], Decimal('4000'))
        self.assertEqual(filas[1]['nombre'], 'Taller B')

    def test_trabajos_no_tercerizados_no_se_cuentan(self):
        self._trabajo(None, None)
        filas = analytics.tercerizacion_por_tercero(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas, [])

    def test_sin_tercero_va_a_sin_especificar(self):
        self._trabajo(None, Decimal('4000'))
        filas = analytics.tercerizacion_por_tercero(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas[0]['nombre'], analytics.SIN_ESPECIFICAR)


class TercerizacionPorReparacionTests(TestCase):
    """tercerizacion_por_reparacion: cantidad, total pagado al tercero y
    ganancia promedio propia en esos trabajos."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tercero = Tercero.objects.create(nombre='Taller Test')
        self.rep_software = TipoReparacion.objects.get(nombre='Software', tipo_dispositivo=self.tipo_celular)
        self.cliente = Cliente.objects.create(nombre='Cliente Por Reparacion', telefono='11-0009-0004')

    def _trabajo(self, precio, monto, tipo_reparacion, **kwargs):
        datos = dict(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular,
            tipo_reparacion=tipo_reparacion,
            descripcion_problema='test', precio_acordado=precio,
            fecha_ingreso=date(2026, 7, 1), tercero=self.tercero, tercerizado_monto=monto,
        )
        datos.update(kwargs)
        return Trabajo.objects.create(**datos)

    def test_total_y_ganancia_promedio(self):
        self._trabajo(Decimal('20000'), Decimal('8000'), self.rep_software)
        self._trabajo(Decimal('10000'), Decimal('4000'), self.rep_software)

        filas = analytics.tercerizacion_por_reparacion(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila['nombre'], 'Software')
        self.assertEqual(fila['cantidad'], 2)
        self.assertEqual(fila['total'], Decimal('12000'))  # 8000 + 4000
        # ganancia: (20000-8000) + (10000-4000) = 12000 + 6000 = 18000 / 2 = 9000
        self.assertEqual(fila['ganancia_promedio'], Decimal('9000'))

    def test_sin_tipo_reparacion_va_a_sin_especificar(self):
        self._trabajo(Decimal('15000'), Decimal('5000'), None)
        filas = analytics.tercerizacion_por_reparacion(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas[0]['nombre'], analytics.SIN_ESPECIFICAR)

    def test_sin_tercerizados_devuelve_vacio(self):
        self._trabajo(Decimal('15000'), None, self.rep_software, tercero=None)
        filas = analytics.tercerizacion_por_reparacion(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas, [])


class ReparacionesMasFrecuentesColumnaTercerizadoTests(TestCase):
    """La tabla de reparaciones más frecuentes suma el monto tercerizado
    por grupo, para comparar costo propio vs. tercerizado."""

    def setUp(self):
        self.tipo_celular = TipoDispositivo.objects.get(nombre='Celular')
        self.tercero = Tercero.objects.create(nombre='Taller Test')
        self.rep_software = TipoReparacion.objects.get(nombre='Software', tipo_dispositivo=self.tipo_celular)
        self.cliente = Cliente.objects.create(nombre='Cliente Col Tercerizado', telefono='11-0009-0005')

    def test_suma_tercerizado_solo_de_los_tercerizados_del_grupo(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular, tipo_reparacion=self.rep_software,
            descripcion_problema='test', precio_acordado=Decimal('20000'),
            fecha_ingreso=date(2026, 7, 1), tercero=self.tercero, tercerizado_monto=Decimal('8000'),
        )
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular, tipo_reparacion=self.rep_software,
            descripcion_problema='test', precio_acordado=Decimal('15000'),
            fecha_ingreso=date(2026, 7, 2),
        )

        filas = analytics.reparaciones_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        fila = next(f for f in filas if f['nombre'] == 'Software')
        self.assertEqual(fila['cantidad'], 2)
        self.assertEqual(fila['tercerizado'], Decimal('8000'))

    def test_tercerizado_cero_cuando_nada_se_tercerizo(self):
        Trabajo.objects.create(
            cliente=self.cliente, tipo_dispositivo=self.tipo_celular, tipo_reparacion=self.rep_software,
            descripcion_problema='test', precio_acordado=Decimal('15000'),
            fecha_ingreso=date(2026, 7, 1),
        )
        filas = analytics.reparaciones_mas_frecuentes(date(2026, 7, 1), date(2026, 7, 31))
        self.assertEqual(filas[0]['tercerizado'], Decimal('0'))
