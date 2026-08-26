from django.db import models


# ---------------------------------------------------------------------------
# Actividad #4 - CRUD Usuarios
# ---------------------------------------------------------------------------
class Usuario(models.Model):
    # Actividad #1: el login debe permitir solo dos roles -> Administrador y
    # Empleado/Mesero. Antes "rol" era texto libre; ahora queda restringido.
    class Rol(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        EMPLEADO = 'empleado', 'Empleado/Mesero'

    nombre = models.CharField(max_length=100)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.EMPLEADO)
    password_hash = models.CharField(max_length=255)  # Actividad #27: se guarda hasheado (bcrypt/PBKDF2)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.nombre


# ---------------------------------------------------------------------------
# Actividad #2 - Registro (log) inviolable de inicio y cierre de sesión
# Este modelo no existía en la versión anterior y era un requisito explícito.
# ---------------------------------------------------------------------------
class RegistroSesion(models.Model):
    class TipoEvento(models.TextChoices):
        LOGIN = 'login', 'Inicio de sesión'
        LOGOUT = 'logout', 'Cierre de sesión'

    usuario = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name='registros_sesion'
    )
    tipo_evento = models.CharField(max_length=10, choices=TipoEvento.choices)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    class Meta:
        verbose_name = "Registro de sesión"
        verbose_name_plural = "Registros de sesión"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.usuario} - {self.tipo_evento} - {self.fecha_hora}"


# ---------------------------------------------------------------------------
# Actividad #5 / #10 / #11 / #14 - CRUD Insumos Lotes
# ---------------------------------------------------------------------------
class LoteInsumo(models.Model):
    # Actividad #11: categorías estandarizadas de insumos.
    class Categoria(models.TextChoices):
        CARNES = 'carnes', 'Carnes'
        PULPAS_FRUTA = 'pulpas_fruta', 'Pulpas de Fruta'
        VERDURAS = 'verduras', 'Verduras'
        HARINAS = 'harinas', 'Harinas'
        LACTEOS = 'lacteos', 'Lácteos'
        BEBIDAS = 'bebidas', 'Bebidas'
        OTROS = 'otros', 'Otros Insumos'

    # Actividad #10: formato REF-YYYYMMDD-XXX (17 caracteres) -> se generaría
    # automáticamente en la capa de negocio a partir de fecha_ingreso.
    codigo_referencia = models.CharField(max_length=20, unique=True)
    nombre_insumo = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_disponible = models.DecimalField(max_digits=10, decimal_places=2)
    # Actividad #14: alerta de stock crítico -> hace falta un umbral por lote.
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha_ingreso = models.DateField()
    fecha_vencimiento = models.DateField()

    class Meta:
        verbose_name = "Lote de insumo"
        verbose_name_plural = "Lotes de insumos"
        ordering = ['fecha_ingreso']  # soporta el descuento PEPS/FIFO (Actividad #12)

    def __str__(self):
        return self.codigo_referencia


# ---------------------------------------------------------------------------
# Actividad #6 - CRUD Platos
# ---------------------------------------------------------------------------
class Plato(models.Model):
    nombre_plato = models.CharField(max_length=100)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    categoria = models.CharField(max_length=100)
    estado = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Plato"
        verbose_name_plural = "Platos"

    def __str__(self):
        return self.nombre_plato


# ---------------------------------------------------------------------------
# Actividad #7 - CRUD Receta Plato (N:M entre Plato e Insumo)
# ---------------------------------------------------------------------------
class RecetaPlato(models.Model):
    plato = models.ForeignKey(Plato, on_delete=models.CASCADE, related_name='receta')
    insumo = models.ForeignKey(LoteInsumo, on_delete=models.CASCADE, related_name='usado_en_recetas')
    cantidad_requerida = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Receta de plato"
        verbose_name_plural = "Recetas de platos"
        # Evita registrar dos veces el mismo insumo para el mismo plato.
        unique_together = ('plato', 'insumo')

    def __str__(self):
        return f"{self.plato} - {self.insumo}"


# ---------------------------------------------------------------------------
# Actividad #8 - CRUD Comandas
# ---------------------------------------------------------------------------
class Comanda(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ENVIADA = 'enviada', 'Enviada'
        CANCELADA = 'cancelada', 'Cancelada'
        PAGADA = 'pagada', 'Pagada'

    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='comandas')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    # Actividad #20: el total se calcula automáticamente en tiempo real,
    # por lo que necesita un valor por defecto en lugar de ser obligatorio.
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Comanda {self.id}"


# ---------------------------------------------------------------------------
# Actividad #9 - CRUD Detalle Comanda
# ---------------------------------------------------------------------------
class DetalleComanda(models.Model):
    comanda = models.ForeignKey(Comanda, on_delete=models.CASCADE, related_name='detalles')
    plato = models.ForeignKey(Plato, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    # Actividad #20/#21: se guarda el precio del plato al momento de la venta
    # para que reportes y totales históricos no cambien si el precio del
    # plato se actualiza después.
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    comentario = models.TextField(blank=True)
    lote_descontado = models.ForeignKey(
        LoteInsumo, on_delete=models.PROTECT, related_name='detalles_descontados'
    )

    class Meta:
        verbose_name = "Detalle de comanda"
        verbose_name_plural = "Detalles de comanda"

    def __str__(self):
        return f"Detalle {self.id}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


# ---------------------------------------------------------------------------
# Actividad #15 - Ajuste manual de merma (solo Admin)
# Modelo nuevo: no existía y era un requisito explícito del documento.
# ---------------------------------------------------------------------------
class AjusteMerma(models.Model):
    class Motivo(models.TextChoices):
        DESPERDICIO = 'desperdicio', 'Desperdicio'
        DANIO = 'danio', 'Daño'
        CADUCIDAD = 'caducidad', 'Caducidad'
        ERROR_CONTEO = 'error_conteo', 'Error de conteo'

    lote = models.ForeignKey(LoteInsumo, on_delete=models.PROTECT, related_name='ajustes_merma')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='ajustes_merma')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    observacion = models.TextField(blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ajuste de merma"
        verbose_name_plural = "Ajustes de merma"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Merma {self.id} - {self.lote}"