from decimal import Decimal

from django import forms
from django.db.models import F, Q, Sum

from .models import (
    CategoriaGasto,
    Cliente,
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


def _sincronizar_gasto_tercerizado(trabajo):
    """Crea/actualiza/borra el Gasto "Tercerizado" ligado a este trabajo,
    según tercerizado_monto.

    No es un gasto que el usuario cargue a mano desde Gastos: se genera
    solo acá, y desde la lista de Gastos no se puede editar (linkea al
    trabajo en cambio).
    """
    gasto_existente = Gasto.objects.filter(
        trabajo=trabajo, categoria__nombre='Tercerizado'
    ).first()

    monto = trabajo.tercerizado_monto
    if monto and monto > 0:
        partes = [trabajo.numero]
        if trabajo.tercero:
            partes.append(trabajo.tercero.nombre)
        if trabajo.tercerizado_detalle:
            partes.append(trabajo.tercerizado_detalle)
        descripcion = ' · '.join(partes)

        if gasto_existente:
            gasto_existente.descripcion = descripcion
            gasto_existente.monto = monto
            gasto_existente.save(update_fields=['descripcion', 'monto'])
        else:
            categoria = CategoriaGasto.objects.get(nombre='Tercerizado')
            Gasto.objects.create(
                descripcion=descripcion, monto=monto, categoria=categoria,
                fecha=trabajo.fecha_ingreso, trabajo=trabajo,
            )
    elif gasto_existente:
        gasto_existente.delete()


class TrabajoForm(forms.ModelForm):
    """Formulario de alta/edición de Trabajo.

    El mockup pide campos sueltos "Cliente" y "Teléfono" en vez de elegir
    un Cliente existente. Se resuelve en save(): se reutiliza un Cliente
    existente solo si coinciden teléfono Y nombre (sin distinguir
    mayúsculas ni espacios); si el teléfono ya existe pero con otro
    nombre, se crea un Cliente nuevo en vez de renombrar el existente
    (mismo teléfono no implica misma persona: puede ser un número
    compartido en una familia, o un error de tipeo). El teléfono es
    opcional: sin él, la búsqueda/reutilización se hace solo por nombre.
    """

    cliente_nombre = forms.CharField(
        label='Cliente',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre y apellido',
        }),
    )
    cliente_telefono = forms.CharField(
        label='Teléfono',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '11-2345-6789 (opcional)',
        }),
    )
    tipo_dispositivo = forms.ModelChoiceField(
        label='Tipo de dispositivo',
        queryset=TipoDispositivo.objects.filter(activo=True),
    )

    class Meta:
        model = Trabajo
        fields = [
            'tipo_dispositivo', 'marca', 'modelo', 'tipo_reparacion',
            'descripcion_problema', 'precio_acordado', 'fecha_ingreso',
            'fecha_entrega', 'tercero', 'tercerizado_detalle', 'tercerizado_monto',
        ]
        labels = {
            'marca': 'Marca',
            'modelo': 'Modelo',
            'tipo_reparacion': 'Tipo de reparación',
            'descripcion_problema': 'Descripción del problema',
            'precio_acordado': 'Precio acordado',
            'fecha_ingreso': 'Fecha de ingreso',
            'fecha_entrega': 'Fecha de entrega',
            'tercero': 'Tercero',
            'tercerizado_detalle': 'Detalle de tercerización',
            'tercerizado_monto': 'Monto tercerizado',
        }
        widgets = {
            'marca': forms.Select(attrs={'class': 'form-control'}),
            'modelo': forms.Select(attrs={'class': 'form-control'}),
            'tipo_reparacion': forms.Select(attrs={'class': 'form-control'}),
            'descripcion_problema': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ej: pantalla rota, no enciende...',
            }),
            'precio_acordado': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': '0',
                'step': '0.01',
            }),
            'fecha_ingreso': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'fecha_entrega': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'tercero': forms.Select(attrs={'class': 'form-control'}),
            'tercerizado_detalle': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: cambio de módulo',
            }),
            'tercerizado_monto': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': '0', 'min': '0', 'step': '0.01',
            }),
        }

    field_order = [
        'cliente_nombre', 'cliente_telefono', 'tipo_dispositivo', 'marca', 'modelo',
        'tipo_reparacion', 'descripcion_problema', 'precio_acordado', 'fecha_ingreso',
        'fecha_entrega', 'tercero', 'tercerizado_detalle', 'tercerizado_monto',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['precio_acordado'].required = True

        self.fields['marca'].queryset = Marca.objects.filter(activo=True)
        self.fields['marca'].required = False
        self.fields['marca'].empty_label = 'Elegí una marca'

        self.fields['modelo'].queryset = Modelo.objects.filter(activo=True)
        self.fields['modelo'].required = False
        self.fields['modelo'].empty_label = 'Sin modelo'

        self.fields['tipo_reparacion'].queryset = TipoReparacion.objects.filter(activo=True)
        self.fields['tipo_reparacion'].required = False
        self.fields['tipo_reparacion'].empty_label = 'Elegí un tipo de reparación'

        # No es un required=True fijo porque solo hace falta cuando el
        # trabajo está Entregado (se valida en clean(), según el estado
        # actual de la instancia: este form no permite cambiar el estado).
        self.fields['fecha_entrega'].required = False

        self.fields['tercero'].queryset = Tercero.objects.filter(activo=True)
        self.fields['tercero'].required = False
        self.fields['tercero'].empty_label = 'Elegí un tercero'

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.estado == Trabajo.Estado.ENTREGADO:
            if not cleaned_data.get('fecha_entrega'):
                self.add_error('fecha_entrega', 'Ingresá la fecha de entrega.')
        else:
            # Se limpia acá (no solo en save()): construct_instance() arma
            # la instancia con esto ANTES de correr Trabajo.clean(), así
            # que si quedara la fecha cargada, la validación del modelo
            # (fecha_entrega solo con estado Entregado) la rechazaría.
            cleaned_data['fecha_entrega'] = None
        return cleaned_data

    def save(self, commit=True):
        nombre = ' '.join(self.cleaned_data['cliente_nombre'].split())
        telefono = self.cleaned_data['cliente_telefono'].strip()

        if telefono:
            cliente = Cliente.objects.filter(telefono=telefono, nombre__iexact=nombre).first()
        else:
            # Sin teléfono no hay con qué cruzar: se busca solo por nombre.
            cliente = Cliente.objects.filter(nombre__iexact=nombre).first()
        if cliente is None:
            cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)

        trabajo = super().save(commit=False)
        trabajo.cliente = cliente
        # El estado no se edita desde este form (eso pasa en la lista de
        # Trabajos): si no está Entregado, cualquier fecha_entrega cargada
        # se ignora y no se guarda.
        if trabajo.estado != Trabajo.Estado.ENTREGADO:
            trabajo.fecha_entrega = None
        if commit:
            trabajo.save()
            _sincronizar_gasto_tercerizado(trabajo)
        return trabajo


class RepuestoUsadoForm(forms.ModelForm):
    class Meta:
        model = RepuestoUsado
        fields = ['gasto', 'cantidad']
        widgets = {
            'gasto': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'step': '1',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pks_permitidos = set(
            Gasto.objects.filter(categoria__nombre='Repuestos', stock_disponible__gt=0)
            .values_list('pk', flat=True)
        )
        if self.instance.pk and self.instance.gasto_id:
            pks_permitidos.add(self.instance.gasto_id)

        self.fields['gasto'].queryset = (
            Gasto.objects.select_related('tipo_repuesto', 'marca', 'modelo', 'tipo_dispositivo')
            .filter(pk__in=pks_permitidos)
        )
        self.fields['gasto'].label_from_instance = self._gasto_label
        self.fields['gasto'].empty_label = '— Elegí un repuesto —'
        self.fields['gasto'].required = False
        self.fields['cantidad'].required = False

    @staticmethod
    def _gasto_label(gasto):
        from .templatetags.taller_extras import moneda

        tipo_repuesto = gasto.tipo_repuesto.nombre if gasto.tipo_repuesto else '—'
        marca_modelo = gasto.marca.nombre if gasto.marca else ''
        if gasto.modelo:
            marca_modelo = f'{marca_modelo} {gasto.modelo.nombre}'.strip()

        partes = [gasto.numero, tipo_repuesto]
        if marca_modelo:
            partes.append(marca_modelo)
        partes.append(moneda(gasto.precio_unitario))
        partes.append(f'quedan {gasto.stock_disponible}')
        return ' · '.join(partes)

    def clean(self):
        cleaned_data = super().clean()
        gasto = cleaned_data.get('gasto')
        cantidad = cleaned_data.get('cantidad')

        if not gasto and not cantidad:
            return cleaned_data

        if gasto and not cantidad:
            self.add_error('cantidad', 'Falta la cantidad.')
            return cleaned_data

        if not gasto and cantidad:
            self.add_error('gasto', 'Elegí un repuesto.')
            return cleaned_data

        disponible = gasto.stock_disponible or 0
        if self.instance.pk and self.instance.gasto_id == gasto.pk:
            disponible += self.instance.cantidad
        if cantidad > disponible:
            self.add_error('cantidad', f'Solo quedan {disponible} disponibles de {gasto.numero}.')

        return cleaned_data


RepuestoUsadoFormSet = forms.inlineformset_factory(
    Trabajo, RepuestoUsado, form=RepuestoUsadoForm,
    fields=['gasto', 'cantidad'], extra=1, can_delete=True,
)


class GastoForm(forms.ModelForm):
    """Formulario de alta/edición de Gasto.

    cantidad × precio unitario calcula el monto para CUALQUIER categoría
    (default cantidad=1, para un gasto de un solo ítem) — ver clean().
    Si la categoría elegida es "Repuestos" se piden además proveedor,
    tipo de dispositivo, subcategoría (que para esta categoría muestra
    los tipos de repuesto) y marca, modelo (opcional); esos campos no
    aplican a otras categorías y se limpian por si venían cargados de una
    edición previa. El stock (stock_disponible) sigue siendo exclusivo
    de Repuestos.
    """

    class Meta:
        model = Gasto
        fields = [
            'fecha', 'categoria', 'subcategoria', 'descripcion', 'monto',
            'proveedor', 'tipo_dispositivo', 'tipo_repuesto', 'marca', 'modelo',
            'cantidad', 'precio_unitario',
        ]
        labels = {
            'fecha': 'Fecha',
            'categoria': 'Categoría',
            'subcategoria': 'Subcategoría',
            'descripcion': 'Descripción',
            'monto': 'Monto',
            'proveedor': 'Proveedor',
            'tipo_dispositivo': 'Tipo de dispositivo',
            'tipo_repuesto': 'Tipo de repuesto',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio unitario',
        }
        widgets = {
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control', 'type': 'date',
            }),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'subcategoria': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: pantalla iPhone 11',
            }),
            'monto': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': '0', 'min': '0', 'step': '0.01',
            }),
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'tipo_dispositivo': forms.Select(attrs={'class': 'form-control'}),
            'tipo_repuesto': forms.Select(attrs={'class': 'form-control'}),
            'marca': forms.Select(attrs={'class': 'form-control'}),
            'modelo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'step': '1',
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': '0', 'min': '0', 'step': '0.01',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['monto'].required = False
        # "Tercerizado" no se elige a mano: lo genera sólo
        # _sincronizar_gasto_tercerizado() desde un Trabajo.
        self.fields['categoria'].queryset = (
            CategoriaGasto.objects.filter(activo=True).exclude(nombre='Tercerizado')
        )
        self.fields['categoria'].empty_label = 'Elegí una categoría'
        self.fields['subcategoria'].queryset = SubcategoriaGasto.objects.filter(activo=True)
        self.fields['subcategoria'].required = False
        self.fields['subcategoria'].empty_label = 'Sin subcategoría'
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)
        self.fields['proveedor'].required = False
        self.fields['proveedor'].empty_label = 'Elegí un proveedor'
        self.fields['tipo_dispositivo'].queryset = TipoDispositivo.objects.filter(activo=True)
        self.fields['tipo_dispositivo'].required = False
        self.fields['tipo_dispositivo'].empty_label = 'Elegí un tipo de dispositivo'
        self.fields['tipo_repuesto'].queryset = TipoRepuesto.objects.filter(activo=True)
        self.fields['tipo_repuesto'].required = False
        self.fields['tipo_repuesto'].empty_label = 'Elegí un tipo de repuesto'
        self.fields['marca'].queryset = Marca.objects.filter(activo=True)
        self.fields['marca'].required = False
        self.fields['marca'].empty_label = 'Elegí una marca'
        self.fields['modelo'].queryset = Modelo.objects.filter(activo=True)
        self.fields['modelo'].required = False
        self.fields['modelo'].empty_label = 'Sin modelo'
        # cantidad/precio_unitario ahora aplican a cualquier categoría
        # (calculan el monto): son obligatorios siempre, no solo en
        # Repuestos.
        self.fields['cantidad'].required = True
        self.fields['precio_unitario'].required = True

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        es_repuesto = bool(categoria and categoria.nombre == 'Repuestos')

        # Si ya se usaron unidades de este repuesto en algún trabajo, no se
        # puede sacar de la categoría Repuestos (perdería tipo_repuesto/marca/
        # precio_unitario, de los que dependen el costo y la ganancia de esos
        # trabajos).
        tiene_usos = bool(self.instance.pk) and self.instance.usos.exists()
        if tiene_usos and not es_repuesto:
            self.add_error(
                'categoria',
                'Este repuesto ya se usó en un trabajo: no se puede cambiar de categoría.',
            )

        if es_repuesto:
            requeridos = {
                'proveedor': 'proveedor',
                'tipo_dispositivo': 'tipo de dispositivo',
                'tipo_repuesto': 'tipo de repuesto',
                'marca': 'marca',
            }
            for campo, etiqueta in requeridos.items():
                if not cleaned_data.get(campo):
                    self.add_error(campo, f'Elegí {etiqueta}: es obligatorio para gastos de Repuestos.')
        else:
            for campo in ('proveedor', 'tipo_dispositivo', 'tipo_repuesto', 'marca', 'modelo'):
                cleaned_data[campo] = None

        # cantidad × precio unitario calcula el monto para cualquier
        # categoría (son campos obligatorios siempre, ver __init__); el
        # stock sigue siendo exclusivo de Repuestos.
        cantidad = cleaned_data.get('cantidad')
        precio_unitario = cleaned_data.get('precio_unitario')

        if es_repuesto and self.instance.pk and cantidad is not None:
            usado = self.instance.usos.aggregate(total=Sum('cantidad'))['total'] or 0
            if cantidad < usado:
                self.add_error(
                    'cantidad',
                    f'Ya se usaron {usado} unidades en trabajos: no podés bajar la cantidad a menos de eso.',
                )

        if cantidad and precio_unitario is not None:
            cleaned_data['monto'] = Decimal(cantidad) * precio_unitario

        return cleaned_data

    def save(self, commit=True):
        gasto = super().save(commit=False)
        categoria = self.cleaned_data.get('categoria')
        es_repuesto = bool(categoria and categoria.nombre == 'Repuestos')
        if es_repuesto:
            # En el form, "Subcategoría" es el mismo campo visual que
            # "Tipo de repuesto" para esta categoría: el select real de
            # subcategoría queda oculto, así que su valor no aplica acá.
            gasto.subcategoria = None
            if gasto.pk:
                # Edición de un repuesto ya existente: mantiene lo ya usado
                # y recalcula el stock disponible sobre la cantidad nueva
                # (la creación ya la resuelve Gasto.save()).
                usado = gasto.usos.aggregate(total=Sum('cantidad'))['total'] or 0
                gasto.stock_disponible = (gasto.cantidad or 0) - usado
        else:
            # No alcanza con limpiar estos campos en cleaned_data:
            # construct_instance no toca un atributo que no vino en el
            # POST, así que sin esto una edición que saca la categoría de
            # "Repuestos" dejaría estos valores pegados de antes.
            gasto.proveedor = None
            gasto.tipo_dispositivo = None
            gasto.tipo_repuesto = None
            gasto.marca = None
            gasto.modelo = None
            gasto.stock_disponible = None
        if commit:
            gasto.save()
        return gasto


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['monto', 'forma_pago', 'fecha', 'trabajo', 'detalle']
        labels = {
            'monto': 'Monto',
            'forma_pago': 'Forma de pago',
            'fecha': 'Fecha',
            'trabajo': 'Trabajo asociado',
            'detalle': 'Detalle',
        }
        widgets = {
            'monto': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': '0',
                'step': '0.01',
            }),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'trabajo': forms.Select(attrs={'class': 'form-control'}),
            'detalle': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Opcional',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['monto'].required = True
        self.fields['forma_pago'].choices = Pago.FormaPago.choices

        trabajos_con_pagado = Trabajo.objects.annotate(pagado=Sum('pagos__monto'))
        con_saldo = trabajos_con_pagado.filter(
            Q(precio_acordado__isnull=True)
            | Q(pagado__isnull=True)
            | Q(pagado__lt=F('precio_acordado'))
        ).values_list('pk', flat=True)
        pks_permitidos = set(con_saldo)
        if self.instance.pk and self.instance.trabajo_id:
            pks_permitidos.add(self.instance.trabajo_id)

        self.fields['trabajo'].queryset = (
            Trabajo.objects.select_related('cliente', 'tipo_dispositivo')
            .annotate(pagado=Sum('pagos__monto'))
            .filter(pk__in=pks_permitidos)
            .order_by('-fecha_ingreso')
        )
        self.fields['trabajo'].label_from_instance = self._trabajo_label
        self.fields['trabajo'].empty_label = None

    @staticmethod
    def _trabajo_label(trabajo):
        # trabajo.pagado viene de la anotación Sum('pagos__monto') del
        # queryset de arriba: evita un query aparte por cada opción del
        # <select> (N+1) al renderizar el formulario.
        base = f'{trabajo.numero} - {trabajo.cliente.nombre} - {trabajo.tipo_dispositivo.nombre}'
        if trabajo.precio_acordado is None:
            return base
        pagado = trabajo.pagado or Decimal('0')
        saldo = trabajo.precio_acordado - pagado
        if saldo <= 0:
            return f'{base} (pagado)'
        formateado = f'{int(round(saldo)):,}'.replace(',', '.')
        return f'{base} (falta ${formateado})'


# Django muestra "---------" por defecto en cualquier ModelChoiceField
# requerido que no tenga empty_label propio; acá se lo reemplaza por un
# texto que diga qué hay que elegir, según el nombre del campo.
_EMPTY_LABELS_CATALOGO = {
    'categoria': 'Elegí una categoría',
    'tipo_dispositivo': 'Elegí un tipo de dispositivo',
    'marca': 'Elegí una marca',
}


class _CatalogoFormBase(forms.ModelForm):
    """Base para los formularios de catálogo de Configuración: mismos
    widgets/clases en todos, solo cambia Meta.fields por subclase."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre == 'activo':
                campo.widget.attrs.setdefault('class', 'catalogo-checkbox')
            elif nombre == 'color':
                campo.widget = forms.TextInput(attrs={'class': 'form-control', 'type': 'color'})
            else:
                campo.widget.attrs.setdefault('class', 'form-control')
            if isinstance(campo, forms.ModelChoiceField) and nombre in _EMPTY_LABELS_CATALOGO:
                campo.empty_label = _EMPTY_LABELS_CATALOGO[nombre]


class TipoDispositivoForm(_CatalogoFormBase):
    class Meta:
        model = TipoDispositivo
        fields = ['nombre', 'color', 'orden', 'activo']


class CategoriaGastoForm(_CatalogoFormBase):
    class Meta:
        model = CategoriaGasto
        fields = ['nombre', 'color', 'orden', 'activo']


class SubcategoriaGastoForm(_CatalogoFormBase):
    class Meta:
        model = SubcategoriaGasto
        fields = ['nombre', 'categoria', 'orden', 'activo']


class TipoRepuestoForm(_CatalogoFormBase):
    class Meta:
        model = TipoRepuesto
        fields = ['nombre', 'tipo_dispositivo', 'orden', 'activo']


class MarcaForm(_CatalogoFormBase):
    class Meta:
        model = Marca
        fields = ['nombre', 'tipo_dispositivo', 'orden', 'activo']


class ModeloForm(_CatalogoFormBase):
    class Meta:
        model = Modelo
        fields = ['nombre', 'marca', 'orden', 'activo']


class ProveedorForm(_CatalogoFormBase):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'telefono', 'orden', 'activo']


class TipoReparacionForm(_CatalogoFormBase):
    class Meta:
        model = TipoReparacion
        fields = ['nombre', 'tipo_dispositivo', 'orden', 'activo']


class TerceroForm(_CatalogoFormBase):
    class Meta:
        model = Tercero
        fields = ['nombre', 'telefono', 'orden', 'activo']
