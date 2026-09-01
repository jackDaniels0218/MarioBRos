from django import forms
from django.contrib.auth.hashers import make_password

from .models import AjusteMerma, LoteInsumo, Plato, RecetaPlato, Usuario


class UsuarioAdminForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput)

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


class LoteAdminForm(forms.ModelForm):
    class Meta:
        model = LoteInsumo
        fields = ['codigo_referencia', 'nombre_insumo', 'categoria', 'precio_unitario', 'cantidad_disponible', 'stock_minimo', 'fecha_ingreso', 'fecha_vencimiento']
        widgets = {'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}), 'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_referencia'].required = False


class PlatoAdminForm(forms.ModelForm):
    class Meta:
        model = Plato
        fields = ['codigo', 'nombre_plato', 'precio_venta', 'categoria', 'estado']


class RecetaAdminForm(forms.ModelForm):
    class Meta:
        model = RecetaPlato
        fields = ['plato', 'insumo', 'cantidad_requerida']


class MermaAdminForm(forms.ModelForm):
    class Meta:
        model = AjusteMerma
        fields = ['lote', 'cantidad', 'motivo', 'observacion']
        widgets = {'observacion': forms.Textarea(attrs={'rows': 3})}
