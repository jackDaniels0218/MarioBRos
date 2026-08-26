from django.contrib import admin
from .models import (
    Usuario,
    RegistroSesion,
    LoteInsumo,
    Plato,
    RecetaPlato,
    Comanda,
    DetalleComanda,
    AjusteMerma,
)

admin.site.register(Usuario)
admin.site.register(RegistroSesion)
admin.site.register(LoteInsumo)
admin.site.register(Plato)
admin.site.register(RecetaPlato)
admin.site.register(Comanda)
admin.site.register(DetalleComanda)
admin.site.register(AjusteMerma)