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


class TrabajoManager(models.Manager):
    def ingresos_mes(self, anio, mes):
        total = self.filter(
            fecha_entrega__year=anio, fecha_entrega__month=mes
        ).aggregate(total=Sum('precio_acordado'))['total']
        return total or Decimal('0')

    def balance_mensual(self, anio, mes):
        ingresos = self.ingresos_mes(anio, mes)
        gastos = Gasto.objects.total_mes(anio, mes)
        return ingresos - gastos


class Trabajo(models.Model):
    class TipoDispositivo(models.TextChoices):
        CELULAR = 'celular', 'Celular'
        JOYSTICK = 'joystick', 'Joystick'
        PS4 = 'ps4', 'PS4'
        NOTEBOOK = 'notebook', 'Notebook'

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
    dispositivo_tipo = models.CharField(
        'tipo de dispositivo', max_length=20, choices=TipoDispositivo.choices
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

    objects = TrabajoManager()

    class Meta:
        verbose_name = 'trabajo'
        verbose_name_plural = 'trabajos'
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f'{self.cliente.nombre} - {self.get_dispositivo_tipo_display()} ({self.get_estado_display()})'


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
        OTRO = 'otro', 'Otro'

    descripcion = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    fecha = models.DateField()

    objects = GastoManager()

    class Meta:
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.descripcion} - ${self.monto} ({self.fecha})'
