from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.signals import pre_delete
from django.dispatch import receiver

MONTO_NEGATIVO_MSG = 'Este monto no puede ser negativo.'


class Correlativo(models.Model):
    """Contador de numeración de comprobantes (T-0001, G-0001, P-0001).

    Vive en su propia tabla en vez de calcularse con MAX(numero)+1 sobre
    Trabajo/Gasto/Pago: así un número nunca se reutiliza, ni siquiera si
    se borra el registro que lo tenía (como un talonario real — la
    numeración queda correlativa sin duplicados, aunque quede un hueco
    donde estaba el borrado).
    """
    TRABAJO = 'trabajo'
    GASTO = 'gasto'
    PAGO = 'pago'

    PREFIJOS = {TRABAJO: 'T', GASTO: 'G', PAGO: 'P'}

    tipo = models.CharField(max_length=20, unique=True)
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'correlativo'
        verbose_name_plural = 'correlativos'

    def __str__(self):
        return f'{self.tipo}: {self.ultimo_numero}'

    @classmethod
    def siguiente_numero(cls, tipo):
        with transaction.atomic():
            correlativo, _ = cls.objects.select_for_update().get_or_create(tipo=tipo)
            correlativo.ultimo_numero += 1
            correlativo.save(update_fields=['ultimo_numero'])
            return f'{cls.PREFIJOS[tipo]}-{correlativo.ultimo_numero:04d}'


class CatalogoBase(models.Model):
    """Base común para los catálogos editables desde Configuración.

    Los ítems se desactivan (activo=False) en vez de borrarse, para no
    romper registros viejos que ya los referencian.
    """
    nombre = models.CharField('nombre', max_length=100)
    activo = models.BooleanField('activo', default=True)
    orden = models.PositiveIntegerField('orden', default=0)

    class Meta:
        abstract = True
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class TipoDispositivo(CatalogoBase):
    color = models.CharField('color', max_length=7, default='#8891a5')

    class Meta(CatalogoBase.Meta):
        verbose_name = 'tipo de dispositivo'
        verbose_name_plural = 'tipos de dispositivo'


class CategoriaGasto(CatalogoBase):
    color = models.CharField('color', max_length=7, default='#8891a5')

    class Meta(CatalogoBase.Meta):
        verbose_name = 'categoría de gasto'
        verbose_name_plural = 'categorías de gasto'


class SubcategoriaGasto(CatalogoBase):
    categoria = models.ForeignKey(
        CategoriaGasto, verbose_name='categoría', on_delete=models.PROTECT,
        related_name='subcategorias',
    )

    class Meta(CatalogoBase.Meta):
        verbose_name = 'subcategoría de gasto'
        verbose_name_plural = 'subcategorías de gasto'


class TipoRepuesto(CatalogoBase):
    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo, verbose_name='tipo de dispositivo', on_delete=models.PROTECT,
        related_name='tipos_repuesto',
    )

    class Meta(CatalogoBase.Meta):
        verbose_name = 'tipo de repuesto'
        verbose_name_plural = 'tipos de repuesto'


class Marca(CatalogoBase):
    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo, verbose_name='tipo de dispositivo', on_delete=models.PROTECT,
        related_name='marcas',
    )

    class Meta(CatalogoBase.Meta):
        verbose_name = 'marca'
        verbose_name_plural = 'marcas'


class Modelo(CatalogoBase):
    marca = models.ForeignKey(
        Marca, verbose_name='marca', on_delete=models.PROTECT, related_name='modelos',
    )

    class Meta(CatalogoBase.Meta):
        verbose_name = 'modelo'
        verbose_name_plural = 'modelos'


class Proveedor(models.Model):
    nombre = models.CharField('nombre', max_length=150)
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    activo = models.BooleanField('activo', default=True)
    orden = models.PositiveIntegerField('orden', default=0)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'proveedor'
        verbose_name_plural = 'proveedores'

    def __str__(self):
        return self.nombre


class TipoReparacion(CatalogoBase):
    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo, verbose_name='tipo de dispositivo', on_delete=models.PROTECT,
        related_name='tipos_reparacion',
    )

    class Meta(CatalogoBase.Meta):
        verbose_name = 'tipo de reparación'
        verbose_name_plural = 'tipos de reparación'


class Tercero(models.Model):
    nombre = models.CharField('nombre', max_length=150)
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    activo = models.BooleanField('activo', default=True)
    orden = models.PositiveIntegerField('orden', default=0)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'tercero'
        verbose_name_plural = 'terceros'

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    email = models.EmailField('email', blank=True)

    class Meta:
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Trabajo(models.Model):
    class Estado(models.TextChoices):
        RECIBIDO = 'recibido', 'Recibido'
        EN_REPARACION = 'en_reparacion', 'En reparación'
        LISTO = 'listo', 'Listo'
        ENTREGADO = 'entregado', 'Entregado'

    numero = models.CharField('número', max_length=20, unique=True, editable=False, blank=True)
    cliente = models.ForeignKey(
        Cliente,
        verbose_name='cliente',
        on_delete=models.PROTECT,
        related_name='trabajos',
    )
    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo, verbose_name='tipo de dispositivo', on_delete=models.PROTECT,
        related_name='trabajos',
    )
    marca = models.ForeignKey(
        Marca, verbose_name='marca', on_delete=models.PROTECT,
        related_name='trabajos', null=True, blank=True,
    )
    modelo = models.ForeignKey(
        Modelo, verbose_name='modelo', on_delete=models.PROTECT,
        related_name='trabajos', null=True, blank=True,
    )
    tipo_reparacion = models.ForeignKey(
        TipoReparacion, verbose_name='tipo de reparación', on_delete=models.PROTECT,
        related_name='trabajos', null=True, blank=True,
    )
    descripcion_problema = models.TextField('descripción del problema', blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.RECIBIDO
    )
    precio_acordado = models.DecimalField(
        'precio acordado', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0, message=MONTO_NEGATIVO_MSG)],
    )
    fecha_ingreso = models.DateField('fecha de ingreso')
    fecha_entrega = models.DateField('fecha de entrega', null=True, blank=True)

    # Tercerización (opcional): si tercerizado_monto > 0 se crea/actualiza
    # solo un Gasto de categoría "Tercerizado" vinculado (ver
    # forms._sincronizar_gasto_tercerizado).
    tercero = models.ForeignKey(
        Tercero, verbose_name='tercero', on_delete=models.PROTECT,
        related_name='trabajos', null=True, blank=True,
    )
    tercerizado_detalle = models.CharField(
        'detalle de tercerización', max_length=255, blank=True,
    )
    tercerizado_monto = models.DecimalField(
        'monto tercerizado', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0, message=MONTO_NEGATIVO_MSG)],
    )

    class Meta:
        verbose_name = 'trabajo'
        verbose_name_plural = 'trabajos'
        ordering = ['-fecha_ingreso']

    def clean(self):
        super().clean()
        if self.fecha_entrega and self.estado != self.Estado.ENTREGADO:
            raise ValidationError({
                'fecha_entrega': 'Solo puede tener fecha de entrega si el estado es "Entregado".',
            })

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Correlativo.siguiente_numero(Correlativo.TRABAJO)
        super().save(*args, **kwargs)

    def total_pagado(self):
        total = self.pagos.aggregate(total=Sum('monto'))['total']
        return total or Decimal('0')

    def esta_pagado(self):
        if self.precio_acordado is None:
            return False
        return self.total_pagado() >= self.precio_acordado

    def costo_repuestos(self):
        return sum((r.costo for r in self.repuestos_usados.all()), Decimal('0'))

    @property
    def ganancia(self):
        """precio_acordado - costo de repuestos usados - monto tercerizado.

        None si todavía no se acordó un precio (no hay nada que calcular).
        """
        if self.precio_acordado is None:
            return None
        return (
            self.precio_acordado
            - self.costo_repuestos()
            - (self.tercerizado_monto or Decimal('0'))
        )

    def __str__(self):
        return f'{self.numero} - {self.cliente.nombre} - {self.tipo_dispositivo.nombre} ({self.get_estado_display()})'


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
    numero = models.CharField('número', max_length=20, unique=True, editable=False, blank=True)
    descripcion = models.CharField('descripción', max_length=255, blank=True)
    monto = models.DecimalField(
        'monto', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0, message=MONTO_NEGATIVO_MSG)],
    )
    categoria = models.ForeignKey(
        CategoriaGasto, verbose_name='categoría', on_delete=models.PROTECT,
        related_name='gastos',
    )
    subcategoria = models.ForeignKey(
        SubcategoriaGasto, verbose_name='subcategoría', on_delete=models.PROTECT,
        related_name='gastos', null=True, blank=True,
    )
    fecha = models.DateField('fecha')

    # Los siguientes campos solo se completan cuando categoria es
    # "Repuestos" (lo validan GastoForm/la vista); para el resto de las
    # categorías quedan en null. stock_disponible arranca igual a
    # cantidad al crear el gasto y no se vuelve a tocar acá — la
    # próxima tanda (trabajos con repuestos/stock) lo va a ir
    # descontando a medida que se usen.
    proveedor = models.ForeignKey(
        Proveedor, verbose_name='proveedor', on_delete=models.PROTECT,
        related_name='gastos', null=True, blank=True,
    )
    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo, verbose_name='tipo de dispositivo', on_delete=models.PROTECT,
        related_name='gastos_repuesto', null=True, blank=True,
    )
    tipo_repuesto = models.ForeignKey(
        TipoRepuesto, verbose_name='tipo de repuesto', on_delete=models.PROTECT,
        related_name='gastos', null=True, blank=True,
    )
    marca = models.ForeignKey(
        Marca, verbose_name='marca', on_delete=models.PROTECT,
        related_name='gastos', null=True, blank=True,
    )
    modelo = models.ForeignKey(
        Modelo, verbose_name='modelo', on_delete=models.PROTECT,
        related_name='gastos', null=True, blank=True,
    )
    cantidad = models.PositiveIntegerField(
        'cantidad', null=True, blank=True, default=1,
        validators=[MinValueValidator(1, message='La cantidad debe ser al menos 1.')],
    )
    precio_unitario = models.DecimalField(
        'precio unitario', max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0, message=MONTO_NEGATIVO_MSG)],
    )
    stock_disponible = models.PositiveIntegerField('stock disponible', null=True, blank=True)

    # Solo se completa en los gastos "Tercerizado" que se generan solos
    # desde un Trabajo (ver forms._sincronizar_gasto_tercerizado). No es
    # un campo del formulario de Gastos: nunca lo carga el usuario a mano.
    # CASCADE: el trabajo es el dueño de este gasto (lo crea/actualiza/
    # borra _sincronizar_gasto_tercerizado según su propio estado), así
    # que si se borra el trabajo este gasto se borra con él — dejarlo
    # vivo con trabajo=NULL lo volvía un gasto huérfano que seguía
    # sumando en Balance sin poder borrarse desde Gastos.
    trabajo = models.ForeignKey(
        Trabajo, verbose_name='trabajo asociado', on_delete=models.CASCADE,
        related_name='gastos_generados', null=True, blank=True,
    )

    objects = GastoManager()

    class Meta:
        verbose_name = 'gasto'
        verbose_name_plural = 'gastos'
        ordering = ['-fecha']

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Correlativo.siguiente_numero(Correlativo.GASTO)
        # cantidad/precio_unitario se usan para calcular el monto en
        # cualquier categoría (ver GastoForm), pero el stock es exclusivo
        # de Repuestos: sin este chequeo, un gasto de Accesorios con
        # cantidad tendría un "stock disponible" que no significa nada.
        if (
            self.pk is None
            and self.cantidad is not None
            and self.stock_disponible is None
            and self.categoria_id
            and self.categoria.nombre == 'Repuestos'
        ):
            self.stock_disponible = self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.numero} - {self.descripcion} - ${self.monto} ({self.fecha})'


class PagoManager(models.Manager):
    def total_mes(self, anio, mes):
        total = self.filter(fecha__year=anio, fecha__month=mes).aggregate(
            total=Sum('monto')
        )['total']
        return total or Decimal('0')

    def por_categoria_dispositivo_mes(self, anio, mes):
        return (
            self.filter(fecha__year=anio, fecha__month=mes)
            .values('trabajo__tipo_dispositivo')
            .annotate(total=Sum('monto'))
            .order_by('-total')
        )


class Pago(models.Model):
    class FormaPago(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        TARJETA = 'tarjeta', 'Tarjeta'
        OTRO = 'otro', 'Otro'

    numero = models.CharField('número', max_length=20, unique=True, editable=False, blank=True)
    monto = models.DecimalField(
        'monto', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0, message=MONTO_NEGATIVO_MSG)],
    )
    forma_pago = models.CharField(
        'forma de pago', max_length=20, choices=FormaPago.choices
    )
    fecha = models.DateField()
    # CASCADE: el trabajo es el dueño de sus pagos. Al borrar un trabajo
    # se borran también sus pagos (junto con el gasto tercerizado y la
    # devolución de stock de sus repuestos usados) — ver trabajo_delete.
    trabajo = models.ForeignKey(
        Trabajo,
        verbose_name='trabajo',
        on_delete=models.CASCADE,
        related_name='pagos',
    )
    detalle = models.TextField('detalle', blank=True)

    objects = PagoManager()

    class Meta:
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'
        ordering = ['-fecha', '-id']

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = Correlativo.siguiente_numero(Correlativo.PAGO)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.numero} - {self.trabajo.cliente.nombre} - ${self.monto} ({self.fecha})'


class RepuestoUsado(models.Model):
    """Un repuesto (Gasto de categoría "Repuestos") consumido en un Trabajo.

    No genera un Gasto nuevo (ya se contó cuando se compró el repuesto):
    solo descuenta stock_disponible del Gasto de origen. save()/delete()
    ajustan ese stock automáticamente (alta descuenta, edición ajusta la
    diferencia, borrado devuelve) — ver también la señal pre_delete más
    abajo, que cubre el borrado en cascada cuando se borra el Trabajo.
    """
    trabajo = models.ForeignKey(
        Trabajo, verbose_name='trabajo', on_delete=models.CASCADE,
        related_name='repuestos_usados',
    )
    gasto = models.ForeignKey(
        Gasto, verbose_name='repuesto', on_delete=models.PROTECT,
        related_name='usos',
    )
    cantidad = models.PositiveIntegerField(
        'cantidad', validators=[MinValueValidator(1, message='La cantidad debe ser al menos 1.')],
    )

    class Meta:
        verbose_name = 'repuesto usado'
        verbose_name_plural = 'repuestos usados'

    @property
    def costo(self):
        precio = self.gasto.precio_unitario or Decimal('0')
        return self.cantidad * precio

    def save(self, *args, **kwargs):
        if self.pk is None:
            Gasto.objects.filter(pk=self.gasto_id).update(
                stock_disponible=models.F('stock_disponible') - self.cantidad
            )
        else:
            anterior = RepuestoUsado.objects.get(pk=self.pk)
            if anterior.gasto_id != self.gasto_id:
                Gasto.objects.filter(pk=anterior.gasto_id).update(
                    stock_disponible=models.F('stock_disponible') + anterior.cantidad
                )
                Gasto.objects.filter(pk=self.gasto_id).update(
                    stock_disponible=models.F('stock_disponible') - self.cantidad
                )
            elif anterior.cantidad != self.cantidad:
                delta = anterior.cantidad - self.cantidad
                Gasto.objects.filter(pk=self.gasto_id).update(
                    stock_disponible=models.F('stock_disponible') + delta
                )
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.gasto.numero} x{self.cantidad} en {self.trabajo.numero}'


@receiver(pre_delete, sender=RepuestoUsado)
def _restaurar_stock_al_borrar_repuesto_usado(sender, instance, **kwargs):
    """Devuelve el stock al borrar un RepuestoUsado.

    Se usa una señal (en vez de solo un override de delete()) porque
    cuando se borra un Trabajo, Django borra sus RepuestoUsado en
    cascada por SQL directo sin pasar por el método delete() de cada
    instancia — pero sí dispara pre_delete/post_delete para cada una.
    """
    Gasto.objects.filter(pk=instance.gasto_id).update(
        stock_disponible=models.F('stock_disponible') + instance.cantidad
    )
