from decimal import Decimal

from django.db import models
from django.db.models import Sum


class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField('teléfono', max_length=30)
    email = models.EmailField('email', blank=True)

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Trabajo(models.Model):
    class CategoriaDispositivo(models.TextChoices):
        CELULAR = 'celular', 'Celular'
        CONSOLA = 'consola', 'Consola'
        NOTEBOOK = 'notebook', 'Notebook'
        OTRO = 'otro', 'Otro'

    class SubtipoCelular(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'
        OTRO = 'otro', 'Otro'

    class SubtipoConsola(models.TextChoices):
        PS4 = 'ps4', 'PS4'
        PS5 = 'ps5', 'PS5'
        XBOX = 'xbox', 'Xbox'
        OTRO = 'otro', 'Otro'

    SUBTIPOS_POR_CATEGORIA = {
        CategoriaDispositivo.CELULAR: SubtipoCelular,
        CategoriaDispositivo.CONSOLA: SubtipoConsola,
    }

    class Estado(models.TextChoices):
        RECIBIDO = 'recibido', 'Recibido'
        EN_REPARACION = 'en_reparacion', 'En reparación'
        LISTO = 'listo', 'Listo'
        ENTREGADO = 'entregado', 'Entregado'

    cliente = models.ForeignKey(
        Cliente,
        verbose_name='cliente',
        on_delete=models.PROTECT,
        related_name='trabajos',
    )
    categoria_dispositivo = models.CharField(
        'categoría de dispositivo', max_length=20, choices=CategoriaDispositivo.choices
    )
    subtipo_dispositivo = models.CharField(
        'subtipo de dispositivo', max_length=20, blank=True
    )
    descripcion_problema = models.TextField('descripción del problema')
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.RECIBIDO
    )
    precio_acordado = models.DecimalField(
        'precio acordado', max_digits=10, decimal_places=2, null=True, blank=True
    )
    fecha_ingreso = models.DateField('fecha de ingreso')
    fecha_entrega = models.DateField('fecha de entrega', null=True, blank=True)

    class Meta:
        verbose_name = 'trabajo'
        verbose_name_plural = 'trabajos'
        ordering = ['-fecha_ingreso']

    def total_pagado(self):
        total = self.pagos.aggregate(total=Sum('monto'))['total']
        return total or Decimal('0')

    def esta_pagado(self):
        if self.precio_acordado is None:
            return False
        return self.total_pagado() >= self.precio_acordado

    def get_subtipo_dispositivo_display(self):
        subtipo_choices = self.SUBTIPOS_POR_CATEGORIA.get(self.categoria_dispositivo)
        if not subtipo_choices or not self.subtipo_dispositivo:
            return ''
        return dict(subtipo_choices.choices).get(self.subtipo_dispositivo, self.subtipo_dispositivo)

    def __str__(self):
        dispositivo = self.get_categoria_dispositivo_display()
        subtipo_label = self.get_subtipo_dispositivo_display()
        if subtipo_label:
            dispositivo += f' {subtipo_label}'
        return f'{self.cliente.nombre} - {dispositivo} ({self.get_estado_display()})'


class GastoManager(models.Manager):
    def total_mes(self, anio, mes):
        total = self.filter(fecha__year=anio, fecha__month=mes).aggregate(
            total=Sum('monto')
        )['total']
        return total or Decimal('0')

    def por_categoria_mes(self, anio, mes):
        return (
            self.filter(fecha__year=anio, fecha__month=mes)
            .values('categoria')
            .annotate(total=Sum('monto'))
            .order_by('-total')
        )


class Gasto(models.Model):
    class Categoria(models.TextChoices):
        REPUESTO = 'repuesto', 'Repuesto'
        HERRAMIENTA = 'herramienta', 'Herramienta'
        TALLER = 'taller', 'Taller'
        OTRO = 'otro', 'Otro'

    descripcion = models.CharField(max_length=255)
    proveedor = models.CharField('proveedor', max_length=150, blank=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    fecha = models.DateField()
    trabajo = models.ForeignKey(
        Trabajo,
        verbose_name='trabajo asociado',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gastos',
    )

    objects = GastoManager()

    class Meta:
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.descripcion} - ${self.monto} ({self.fecha})'


class PagoManager(models.Manager):
    def total_mes(self, anio, mes):
        total = self.filter(fecha__year=anio, fecha__month=mes).aggregate(
            total=Sum('monto')
        )['total']
        return total or Decimal('0')

    def por_categoria_dispositivo_mes(self, anio, mes):
        return (
            self.filter(fecha__year=anio, fecha__month=mes)
            .values('trabajo__categoria_dispositivo')
            .annotate(total=Sum('monto'))
            .order_by('-total')
        )


class Pago(models.Model):
    class FormaPago(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        TARJETA = 'tarjeta', 'Tarjeta'
        OTRO = 'otro', 'Otro'

    monto = models.DecimalField(max_digits=10, decimal_places=2)
    forma_pago = models.CharField(
        'forma de pago', max_length=20, choices=FormaPago.choices
    )
    fecha = models.DateField()
    trabajo = models.ForeignKey(
        Trabajo,
        verbose_name='trabajo',
        on_delete=models.PROTECT,
        related_name='pagos',
    )
    detalle = models.TextField('detalle', blank=True)

    objects = PagoManager()

    class Meta:
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'{self.trabajo.cliente.nombre} - ${self.monto} ({self.fecha})'
