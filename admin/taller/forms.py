from django import forms

from .models import Cliente, Gasto, Trabajo


class TrabajoForm(forms.ModelForm):
    """Formulario de alta de Trabajo.

    El mockup pide campos sueltos "Cliente" y "Teléfono" en vez de elegir
    un Cliente existente. Se resuelve en save(): si ya existe un Cliente
    con ese teléfono se reutiliza, si no se crea uno nuevo.
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

    class Meta:
        model = Trabajo
        fields = ['dispositivo_tipo', 'descripcion_problema', 'precio_acordado', 'fecha_ingreso']
        labels = {
            'dispositivo_tipo': 'Tipo de dispositivo',
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
            'fecha_ingreso': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
        }

    field_order = [
        'cliente_nombre', 'cliente_telefono', 'dispositivo_tipo',
        'descripcion_problema', 'precio_acordado', 'fecha_ingreso',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['precio_acordado'].required = True

    def save(self, commit=True):
        cliente, _ = Cliente.objects.get_or_create(
            telefono=self.cleaned_data['cliente_telefono'],
            defaults={'nombre': self.cleaned_data['cliente_nombre']},
        )
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
            'fecha': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['monto'].required = True
