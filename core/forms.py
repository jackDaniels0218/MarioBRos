from django import forms
from django.contrib.auth.hashers import make_password

from .models import AjusteMerma, LoteInsumo, Plato, RecetaPlato, Usuario


class UsuarioAdminForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput, help_text="Dejar en blanco para mantener la contraseña actual. Solo llenar para cambiar.")

    class Meta:
        model = Usuario
        fields = ['nombre', 'rol', 'estado']

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            usuario.password_hash = make_password(password)
        if commit:
            usuario.save()
        return usuario


class ResetPasswordForm(forms.Form):
    """Formulario para resetear contraseña de un usuario sin conocer la actual."""
    usuario_id = forms.IntegerField(widget=forms.HiddenInput())
    nueva_password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput,
        label="Nueva contraseña",
        help_text="Mínimo 6 caracteres"
    )
    confirmar_password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput,
        label="Confirmar contraseña"
    )

    def clean(self):
        cleaned_data = super().clean()
        nueva = cleaned_data.get('nueva_password')
        confirmar = cleaned_data.get('confirmar_password')
        if nueva and confirmar and nueva != confirmar:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data


class LoteAdminForm(forms.ModelForm):
    class Meta:
        model = LoteInsumo
        fields = ['codigo_referencia', 'nombre_insumo', 'categoria', 'precio_unitario', 'stock_minimo', 'fecha_ingreso', 'fecha_vencimiento']
        widgets = {'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}), 'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_referencia'].required = False
        # NO permitir editar cantidad_disponible directamente
        if 'cantidad_disponible' in self.fields:
            del self.fields['cantidad_disponible']


class PlatoAdminForm(forms.ModelForm):
    class Meta:
        model = Plato
        fields = ['codigo', 'nombre_plato', 'precio_venta', 'categoria', 'estado']


class RecetaAdminForm(forms.ModelForm):
    class Meta:
        model = RecetaPlato
        fields = ['plato', 'insumo', 'cantidad_requerida']

    def clean_cantidad_requerida(self):
        cantidad = self.cleaned_data.get('cantidad_requerida')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a cero.")
        return cantidad


class MermaAdminForm(forms.ModelForm):
    class Meta:
        model = AjusteMerma
        fields = ['lote', 'cantidad', 'motivo', 'observacion']

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError("La cantidad debe ser mayor a cero.")
        return cantidad

        widgets = {'observacion': forms.Textarea(attrs={'rows': 3})}
