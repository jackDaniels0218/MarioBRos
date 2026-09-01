from django.contrib import admin
from .models import (
    Usuario,
    RegistroSesion,
    RegistroActividad,
    LoteInsumo,
    Plato,
    RecetaPlato,
    Comanda,
    DetalleComanda,
    AjusteMerma,
    Factura,
    DetalleFactura,
    ConsumoInsumo,
)

admin.site.register(Usuario)
admin.site.register(RegistroSesion)
admin.site.register(RegistroActividad)
admin.site.register(LoteInsumo)
admin.site.register(Plato)
admin.site.register(RecetaPlato)
admin.site.register(Comanda)
admin.site.register(DetalleComanda)
admin.site.register(AjusteMerma)
admin.site.register(Factura)
admin.site.register(DetalleFactura)
admin.site.register(ConsumoInsumo)