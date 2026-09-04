from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .forms import GastoForm, PagoForm, TrabajoForm
from .models import Cliente, Gasto, Pago, Trabajo
from . import analytics


class TotalPagadoTests(TestCase):
    """Trabajo.total_pagado() / esta_pagado() con pagos parciales y sobrepago."""

    def setUp(self):
        cliente = Cliente.objects.create(nombre='Ana Ruiz', telefono='11-1111-1111')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
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
        cliente = Cliente.objects.create(nombre='Bruno Aquino', telefono='11-2222-2222')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.CONSOLA,
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
            cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.NOTEBOOK,
            descripcion_problema='Revisión', estado=Trabajo.Estado.RECIBIDO,
            precio_acordado=Decimal('5000'), fecha_ingreso=date(2026, 7, 1),
        )
        self.client.post(reverse('taller:trabajo_delete', args=[trabajo_sin_pagos.pk]))
        self.assertFalse(Trabajo.objects.filter(pk=trabajo_sin_pagos.pk).exists())


class BalanceAnalyticsTests(TestCase):
    """balance_mensual / comparacion_mes_anterior en cruce de año y balance anterior = 0."""

    def setUp(self):
        cliente = Cliente.objects.create(nombre='Lucía Fernández', telefono='11-4444-4444')
        trabajo = Trabajo.objects.create(
            cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
            descripcion_problema='Batería', estado=Trabajo.Estado.ENTREGADO,
            precio_acordado=Decimal('9000'), fecha_ingreso=date(2025, 12, 20),
            fecha_entrega=date(2025, 12, 28),
        )
        Pago.objects.create(trabajo=trabajo, monto=Decimal('9000'),
                             forma_pago=Pago.FormaPago.EFECTIVO, fecha=date(2025, 12, 28))
        Gasto.objects.create(descripcion='Repuesto', monto=Decimal('3000'),
                              categoria=Gasto.Categoria.REPUESTO, fecha=date(2025, 12, 22))

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
    """?mes= fuera de 1-12 en balance/gasto_create/trabajos_list: sin 500, redirige.

    pago_create ya no tiene selector de mes (el historial de pagos
    muestra todo, sin filtrar) así que no aplica acá.
    """

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
    """Los formularios rechazan montos negativos."""

    def setUp(self):
        cliente = Cliente.objects.create(nombre='Sofía Medina', telefono='11-5555-5555')
        self.trabajo = Trabajo.objects.create(
            cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.NOTEBOOK,
            descripcion_problema='SSD', estado=Trabajo.Estado.EN_REPARACION,
            precio_acordado=Decimal('20000'), fecha_ingreso=date(2026, 7, 1),
        )

    def test_trabajo_precio_negativo_invalido(self):
        form = TrabajoForm(data={
            'cliente_nombre': 'Test', 'cliente_telefono': '11-9999-9999',
            'categoria_dispositivo': 'celular', 'subtipo_dispositivo': 'android',
            'descripcion_problema': 'test', 'precio_acordado': '-500',
            'fecha_ingreso': '2026-07-01',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('precio_acordado', form.errors)

    def test_gasto_monto_negativo_invalido(self):
        form = GastoForm(data={
            'descripcion': 'x', 'monto': '-100',
            'categoria': 'repuesto', 'fecha': '2026-07-01',
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
            'categoria': 'otro', 'fecha': '2026-07-01',
        })
        self.assertTrue(form.is_valid())


class PagoFormSinNMasUnoTests(TestCase):
    """PagoForm ya no dispara un query aparte por cada trabajo del <select>.

    En vez de fijar un número exacto de queries (frágil ante detalles
    internos del ORM), compara la cantidad de queries con pocos y con
    muchos trabajos: si no escala con N, no hay N+1.
    """

    @staticmethod
    def _crear_trabajos(cantidad):
        cliente = Cliente.objects.create(nombre='Rodrigo Paz', telefono='11-6666-6666')
        for i in range(cantidad):
            Trabajo.objects.create(
                cliente=cliente, categoria_dispositivo=Trabajo.CategoriaDispositivo.CELULAR,
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
