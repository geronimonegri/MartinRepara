from decimal import Decimal

from django import forms
from django.db.models import F, Q, Sum

from .models import Cliente, Gasto, Pago, Trabajo


class TrabajoForm(forms.ModelForm):
    """Formulario de alta de Trabajo.

    El mockup pide campos sueltos "Cliente" y "Teléfono" en vez de elegir
    un Cliente existente. Se resuelve en save(): se reutiliza un Cliente
    existente solo si coinciden teléfono Y nombre (sin distinguir
    mayúsculas ni espacios); si el teléfono ya existe pero con otro
    nombre, se crea un Cliente nuevo en vez de renombrar el existente
    (mismo teléfono no implica misma persona: puede ser un número
    compartido en una familia, o un error de tipeo).
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
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '11-2345-6789',
        }),
    )
    subtipo_dispositivo = forms.ChoiceField(
        label='Subtipo',
        required=False,
        choices=(
            [('', '—')]
            + Trabajo.SubtipoCelular.choices
            + Trabajo.SubtipoConsola.choices
        ),
    )

    class Meta:
        model = Trabajo
        fields = [
            'categoria_dispositivo', 'subtipo_dispositivo',
            'descripcion_problema', 'precio_acordado', 'fecha_ingreso',
        ]
        labels = {
            'categoria_dispositivo': 'Categoría de dispositivo',
            'subtipo_dispositivo': 'Subtipo',
            'descripcion_problema': 'Descripción del problema',
            'precio_acordado': 'Precio acordado',
            'fecha_ingreso': 'Fecha de ingreso',
        }
        widgets = {
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
        }

    field_order = [
        'cliente_nombre', 'cliente_telefono', 'categoria_dispositivo', 'subtipo_dispositivo',
        'descripcion_problema', 'precio_acordado', 'fecha_ingreso',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['precio_acordado'].required = True
        self.fields['categoria_dispositivo'].choices = Trabajo.CategoriaDispositivo.choices

    @property
    def subtipos_celular(self):
        return Trabajo.SubtipoCelular.choices

    @property
    def subtipos_consola(self):
        return Trabajo.SubtipoConsola.choices

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria_dispositivo')
        subtipo = cleaned_data.get('subtipo_dispositivo')
        subtipo_choices = Trabajo.SUBTIPOS_POR_CATEGORIA.get(categoria)
        if subtipo_choices:
            if not subtipo or subtipo not in subtipo_choices.values:
                self.add_error('subtipo_dispositivo', 'Elegí un subtipo para esta categoría.')
        else:
            cleaned_data['subtipo_dispositivo'] = ''
        return cleaned_data

    def save(self, commit=True):
        nombre = ' '.join(self.cleaned_data['cliente_nombre'].split())
        telefono = self.cleaned_data['cliente_telefono'].strip()

        cliente = Cliente.objects.filter(
            telefono=telefono, nombre__iexact=nombre
        ).first()
        if cliente is None:
            cliente = Cliente.objects.create(nombre=nombre, telefono=telefono)

        trabajo = super().save(commit=False)
        trabajo.cliente = cliente
        if commit:
            trabajo.save()
        return trabajo


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ['descripcion', 'monto', 'proveedor', 'categoria', 'fecha']
        labels = {
            'descripcion': 'Descripción',
            'monto': 'Monto',
            'proveedor': 'Proveedor',
            'categoria': 'Categoría',
            'fecha': 'Fecha',
        }
        widgets = {
            'descripcion': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: pantalla iPhone 11',
            }),
            'monto': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': '0',
                'step': '0.01',
            }),
            'proveedor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: distribuidora local',
            }),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['monto'].required = True
        self.fields['categoria'].choices = Gasto.Categoria.choices


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
            Trabajo.objects.select_related('cliente')
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
        base = f'{trabajo.cliente.nombre} - {trabajo.get_categoria_dispositivo_display()}'
        if trabajo.precio_acordado is None:
            return base
        pagado = trabajo.pagado or Decimal('0')
        saldo = trabajo.precio_acordado - pagado
        if saldo <= 0:
            return f'{base} (pagado)'
        formateado = f'{int(round(saldo)):,}'.replace(',', '.')
        return f'{base} (falta ${formateado})'
