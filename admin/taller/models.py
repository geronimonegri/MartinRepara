from django.db import models


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

    cliente_nombre = models.CharField('nombre del cliente', max_length=150)
    cliente_telefono = models.CharField('teléfono del cliente', max_length=30)
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

    class Meta:
        verbose_name = 'trabajo'
        verbose_name_plural = 'trabajos'
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f'{self.cliente_nombre} - {self.get_dispositivo_tipo_display()} ({self.get_estado_display()})'


class Gasto(models.Model):
    class Categoria(models.TextChoices):
        REPUESTO = 'repuesto', 'Repuesto'
        HERRAMIENTA = 'herramienta', 'Herramienta'
        OTRO = 'otro', 'Otro'

    descripcion = models.CharField(max_length=255)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    fecha = models.DateField()

    class Meta:
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.descripcion} - ${self.monto} ({self.fecha})'
