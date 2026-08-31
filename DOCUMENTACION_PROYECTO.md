# MarioBRos

## Descripción general
MarioBRos es un proyecto web desarrollado en Django para gestionar un restaurante, con módulos de autenticación por roles, inventario, comandas, facturación y control de usuarios.

El sistema está orientado a tres perfiles principales:
- Administrador
- Mesero/Empleado
- Cajero

## Estructura del proyecto

```text
MarioBRos/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── core/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── tests.py
│   ├── views.py
│   └── migrations/
├── plantillas/
│   ├── Inicio.html
│   ├── IniciarSesion.html
│   ├── IniciarSesionAdmin.html
│   ├── IniciarSesionMesero.html
│   ├── Inventario.html
│   ├── Comandas.html
│   ├── Cajero.html
│   ├── Facturacion.html
│   ├── Factura.html
│   └── Menu.html
├── db.sqlite3
├── db.sqlite3.before-repair.bak
├── manage.py
├── README.md
├── DOCUMENTACION_PROYECTO.md
└── .gitignore
```

## Tecnologías usadas
- Python 3.13
- Django 6.1
- SQLite
- HTML + CSS + Django Templates
- ORM de Django

## Funcionalidades principales

### 1. Autenticación y roles
El sistema permite iniciar sesión según el tipo de usuario:
- Administrador
- Mesero
- Cajero

Las credenciales por defecto configuradas en la lógica del proyecto son:
- Administrador: `admin` / `admin123`
- Mesero: `mesero` / `mesero123`
- Cajero: `cajero` / `cajero123`

La validación se hace por nombre de usuario + rol + contraseña, y se guarda información de sesión y registro de inicio de sesión.

### 2. Inventario
El administrador puede gestionar:
- Platos activos
- Recetas por plato
- Existencias por insumo
- Alertas de stock bajo o agotado
- Suma de porciones disponibles

### 3. Mesero / Comandas
El mesero puede:
- Seleccionar una mesa
- Crear o modificar comandas
- Agregar platos
- Finalizar la comanda
- Enviar la comanda a facturación

### 4. Cajero
El cajero puede:
- Revisar facturas pendientes
- Confirmar pagos
- Ver comandas activas
- Marcar facturas como pagadas

### 5. Facturación
Cuenta con:
- Listado de facturas
- Total de ventas
- Detalle de factura por número
- Estado de la factura (pendiente, pagada, cancelada)

## Modelos principales

### Usuario
Representa a cada usuario del sistema.

Campos relevantes:
- nombre
- rol
- password_hash
- estado
- fecha_creacion

Roles disponibles:
- admin
- empleado (mesero)
- cajero

### RegistroSesion
Registra eventos de acceso:
- login
- logout

### LoteInsumo
Representa los insumos disponibles del restaurante.

Campos:
- codigo_referencia
- nombre_insumo
- categoria
- precio_unitario
- cantidad_disponible
- stock_minimo
- fecha_ingreso
- fecha_vencimiento

### Plato
Representa los platillos del menú.

Campos:
- nombre_plato
- precio_venta
- categoria
- estado

### RecetaPlato
Relación entre plato e insumo con su cantidad requerida.

### Comanda
Representa una comanda de mesa.

Campos:
- usuario
- fecha_hora
- estado
- total

### DetalleComanda
Detalle de cada plato incluido en una comanda.

### Factura
Representa la factura emitida por el restaurante.

Campos:
- numero
- usuario
- cliente
- fecha_hora
- subtotal
- impuesto
- total
- metodo_pago
- estado
- observacion

### DetalleFactura
Detalle de cada producto o servicio dentro de la factura.

## Vistas principales
En el archivo `core/views.py` se implementan las vistas siguientes:

- `inicio`
- `iniciar_sesion`
- `vista_admin`
- `vista_menu`
- `vista_mesero`
- `vista_cajero`
- `vista_facturacion`
- `detalle_factura`

## Rutas configuradas
En `config/urls.py` se registran las rutas principales:

- `/` → Inicio
- `/login/` → Login general
- `/login/<rol>/` → Login según rol
- `/admin/inicio/` → Vista admin
- `/menu/` → Menú
- `/mesero/inicio/` → Vista mesero
- `/cajero/inicio/` → Vista cajero
- `/facturacion/` → Facturación
- `/factura/<id>/` → Detalle de factura

## Plantillas principales
Las plantillas principales están en la carpeta `plantillas/`:

- `Inicio.html`
- `IniciarSesion.html`
- `Inventario.html`
- `Comandas.html`
- `Cajero.html`
- `Facturacion.html`
- `Factura.html`
- `Menu.html`

## Cómo ejecutar el proyecto
Desde la raíz del proyecto:

```bash
python manage.py migrate
python manage.py runserver
```

Luego abrir en el navegador:

```text
http://127.0.0.1:8000/
```

## Flujo recomendado
1. Entrar a la pantalla principal
2. Ir al login del rol correspondiente
3. Iniciar sesión con las credenciales asignadas
4. Usar la vista según el perfil

## Observaciones de desarrollo
- El proyecto está estructurado con lógica de roles por sesión.
- La base de datos utilizada es SQLite local.
- El proyecto tiene un enfoque de restauración de datos y validación para evitar inconsistencias en valores numéricos.
- Se añadieron validaciones para manejar datos corruptos o vacíos en campos monetarios.

## Estado actual
El proyecto está en una etapa funcional con estructura de roles, gestión de inventario, comandas y facturación. Se han realizado correcciones para mejorar la estabilidad en login, acceso por usuario y carga de datos en las vistas principales.

## Archivos relevantes
- `config/settings.py` → configuración principal del proyecto
- `config/urls.py` → rutas del sistema
- `core/models.py` → modelos de datos
- `core/views.py` → lógica de negocio y rutas
- `core/tests.py` → pruebas del sistema
- `plantillas/` → templates HTML

## Código completo

### config/urls.py
```python
"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('login/', views.iniciar_sesion, name='iniciar_sesion'),
    path('login/<str:rol>/', views.iniciar_sesion, name='iniciar_sesion_rol'),
    path('admin/inicio/', views.vista_admin, name='vista_admin'),
    path('menu/', views.vista_menu, name='vista_menu'),
    path('mesero/inicio/', views.vista_mesero, name='vista_mesero'),
    path('cajero/inicio/', views.vista_cajero, name='vista_cajero'),
    path('facturacion/', views.vista_facturacion, name='vista_facturacion'),
    path('factura/<int:factura_id>/', views.detalle_factura, name='detalle_factura'),
    path('admin/', admin.site.urls),
]
```

### core/models.py
```python
import uuid

from django.db import models
from django.utils import timezone


class Usuario(models.Model):
    class Rol(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        EMPLEADO = 'empleado', 'Empleado/Mesero'
        CAJERO = 'cajero', 'Cajero'

    nombre = models.CharField(max_length=100)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.EMPLEADO)
    password_hash = models.CharField(max_length=255)
    estado = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.nombre


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


class LoteInsumo(models.Model):
    class Categoria(models.TextChoices):
        CARNES = 'carnes', 'Carnes'
        PULPAS_FRUTA = 'pulpas_fruta', 'Pulpas de Fruta'
        VERDURAS = 'verduras', 'Verduras'
        HARINAS = 'harinas', 'Harinas'
        LACTEOS = 'lacteos', 'Lácteos'
        BEBIDAS = 'bebidas', 'Bebidas'
        OTROS = 'otros', 'Otros Insumos'

    codigo_referencia = models.CharField(max_length=20, unique=True)
    nombre_insumo = models.CharField(max_length=100)
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad_disponible = models.DecimalField(max_digits=10, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha_ingreso = models.DateField()
    fecha_vencimiento = models.DateField()

    class Meta:
        verbose_name = "Lote de insumo"
        verbose_name_plural = "Lotes de insumos"
        ordering = ['fecha_ingreso']

    def __str__(self):
        return self.codigo_referencia


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


class RecetaPlato(models.Model):
    plato = models.ForeignKey(Plato, on_delete=models.CASCADE, related_name='receta')
    insumo = models.ForeignKey(LoteInsumo, on_delete=models.CASCADE, related_name='usado_en_recetas')
    cantidad_requerida = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Receta de plato"
        verbose_name_plural = "Recetas de platos"
        unique_together = ('plato', 'insumo')

    def __str__(self):
        return f"{self.plato} - {self.insumo}"


class Comanda(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ENVIADA = 'enviada', 'Enviada'
        CANCELADA = 'cancelada', 'Cancelada'
        PAGADA = 'pagada', 'Pagada'

    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='comandas')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Comanda {self.id}"


class DetalleComanda(models.Model):
    comanda = models.ForeignKey(Comanda, on_delete=models.CASCADE, related_name='detalles')
    plato = models.ForeignKey(Plato, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
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


class Factura(models.Model):
    class MetodoPago(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TARJETA = 'tarjeta', 'Tarjeta'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        MIXTO = 'mixto', 'Mixto'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PAGADA = 'pagada', 'Pagada'
        CANCELADA = 'cancelada', 'Cancelada'

    numero = models.CharField(max_length=30, unique=True, blank=True, default='')
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='facturas')
    cliente = models.CharField(max_length=150, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    impuesto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    metodo_pago = models.CharField(max_length=20, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PAGADA)
    observacion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ['-fecha_hora']

    def save(self, *args, **kwargs):
        if not self.numero:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            unique = uuid.uuid4().hex[:6].upper()
            self.numero = f'FAC-{timestamp}-{unique}'
        super().save(*args, **kwargs)

    @property
    def subtotal_detallado(self):
        return sum((detalle.subtotal for detalle in self.detalles.all()), 0)

    def __str__(self):
        return f"Factura {self.numero}"


class DetalleFactura(models.Model):
    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name='detalles')
    descripcion = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Detalle de factura"
        verbose_name_plural = "Detalles de factura"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.factura.numero} - {self.descripcion}"
```

### core/views.py
```python
from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.shortcuts import redirect, render

from .models import (
    Comanda,
    DetalleComanda,
    Factura,
    LoteInsumo,
    Plato,
    RegistroSesion,
    Usuario,
)


def format_money(value):
    if value is None:
        value = Decimal('0')
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal('0')
    return f'{value:,.2f}'


def _safe_decimal(value, default='0'):
    if value in (None, ''):
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _repair_corrupted_decimal_rows():
    with connection.cursor() as cursor:
        cursor.execute('SELECT id, total FROM core_comanda')
        for comanda_id, total in cursor.fetchall():
            try:
                Decimal(str(total))
            except (InvalidOperation, TypeError, ValueError):
                cursor.execute('UPDATE core_comanda SET total = 0 WHERE id = ?', [comanda_id])

        cursor.execute('SELECT id, precio_unitario FROM core_detallecomanda')
        for detalle_id, precio in cursor.fetchall():
            try:
                Decimal(str(precio))
            except (InvalidOperation, TypeError, ValueError):
                cursor.execute('UPDATE core_detallecomanda SET precio_unitario = 0 WHERE id = ?', [detalle_id])


class _SafeDetalleCollection:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


def _safe_comandas(limit=None):
    queryset = Comanda.objects.select_related('usuario').order_by('-fecha_hora')
    if limit is not None:
        queryset = queryset[:int(limit)]

    comandas = []
    for comanda in queryset:
        comanda.total = _safe_decimal(comanda.total)
        detalles = []
        for detalle in comanda.detalles.select_related('plato').all():
            detalle.precio_unitario = _safe_decimal(detalle.precio_unitario)
            detalles.append(detalle)

        comanda.detalles = _SafeDetalleCollection(detalles)
        comandas.append(comanda)

    return comandas


def _safe_facturas(limit=None):
    queryset = Factura.objects.select_related('usuario').order_by('-fecha_hora')
    if limit is not None:
        queryset = queryset[:int(limit)]

    facturas = []
    for factura in queryset:
        factura.subtotal = _safe_decimal(factura.subtotal)
        factura.impuesto = _safe_decimal(factura.impuesto)
        factura.total = _safe_decimal(factura.total)
        facturas.append(factura)

    return facturas


def _ensure_default_users():
    defaults = [
        ('admin', Usuario.Rol.ADMIN, 'admin123'),
        ('mesero', Usuario.Rol.EMPLEADO, 'mesero123'),
        ('cajero', Usuario.Rol.CAJERO, 'cajero123'),
    ]

    for nombre, rol, password in defaults:
        usuarios = Usuario.objects.filter(nombre=nombre).order_by('id')
        usuario = usuarios.first()

        if usuario is None:
            Usuario.objects.create(
                nombre=nombre,
                rol=rol,
                password_hash=make_password(password),
                estado=True,
            )
            continue

        if usuarios.count() > 1:
            usuarios.exclude(pk=usuario.pk).delete()

        usuario.rol = rol
        usuario.password_hash = make_password(password)
        usuario.estado = True
        usuario.save(update_fields=['rol', 'password_hash', 'estado'])


def _estado_inventario(porciones_disponibles):
    if porciones_disponibles <= 0:
        return 'Agotado', 'agotado'
    if porciones_disponibles <= 5:
        return 'Stock bajo', 'bajo'
    return 'Disponible', 'disponible'


def _porciones_disponibles(plato):
    receta = plato.receta.select_related('insumo').all()
    if not receta:
        return 0, 'Sin receta'

    porciones = []
    insumo_critico = None

    for detalle in receta:
        insumo = detalle.insumo
        if detalle.cantidad_requerida <= 0:
            continue

        try:
            disponible = Decimal(str(insumo.cantidad_disponible))
            requerido = Decimal(str(detalle.cantidad_requerida))
        except (InvalidOperation, TypeError, ValueError):
            continue

        if requerido == 0:
            continue

        porciones.append(disponible / requerido)

        if insumo_critico is None or insumo.cantidad_disponible < detalle.insumo.cantidad_disponible:
            insumo_critico = insumo

    if not porciones:
        return 0, 'Sin receta'

    cantidad = min(porciones)
    return int(cantidad), insumo_critico.nombre_insumo if insumo_critico else 'Sin receta'


def _mesa_label(comentario):
    if not comentario:
        return 'Mesa sin asignar'
    text = str(comentario).strip()
    if text.lower().startswith('mesa '):
        return text
    return f'Mesa {text}'


def _get_role_title(rol):
    mapping = {
        'admin': 'Administrador',
        'mesero': 'Mesero',
        'cajero': 'Cajero',
    }
    return mapping.get(rol, 'Usuario')


def _resolve_role(rol):
    if rol == 'mesero':
        return Usuario.Rol.EMPLEADO
    if rol == 'cajero':
        return Usuario.Rol.CAJERO
    if rol == 'admin':
        return Usuario.Rol.ADMIN
    return rol


def inicio(request):
    return render(request, 'Inicio.html')


def iniciar_sesion(request, rol='admin'):
    error = None
    rol = request.POST.get('rol', request.GET.get('rol', rol or 'admin'))
    _ensure_default_users()

    if request.method == 'POST':
        nombre = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')
        rol_db = _resolve_role(rol)
        usuario = Usuario.objects.filter(nombre=nombre, rol=rol_db, estado=True).first()

        if usuario and check_password(password, usuario.password_hash):
            request.session['usuario_id'] = usuario.id
            request.session['rol'] = usuario.rol
            RegistroSesion.objects.create(
                usuario=usuario,
                tipo_evento=RegistroSesion.TipoEvento.LOGIN,
                ip_address=request.META.get('REMOTE_ADDR') or '0.0.0.0',
            )
            if usuario.rol == Usuario.Rol.ADMIN:
                return redirect('vista_admin')
            if usuario.rol == Usuario.Rol.CAJERO:
                return redirect('vista_cajero')
            return redirect('vista_mesero')

        error = 'Usuario o contraseña incorrectos.'

    return render(request, 'IniciarSesion.html', {'error': error, 'rol': rol, 'titulo_rol': _get_role_title(rol)})


def vista_admin(request):
    if request.session.get('rol') != Usuario.Rol.ADMIN:
        return redirect('iniciar_sesion')

    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()

    if request.method == 'POST' and request.POST.get('accion') == 'stock':
        lote_id = request.POST.get('lote_id')
        cantidad = Decimal(str(request.POST.get('cantidad', '0') or '0'))
        if lote_id:
            lote = LoteInsumo.objects.get(pk=lote_id)
            lote.cantidad_disponible = Decimal(str(lote.cantidad_disponible)) + cantidad
            lote.save(update_fields=['cantidad_disponible'])
        return redirect('vista_admin')

    platos = Plato.objects.filter(estado=True).prefetch_related('receta__insumo').order_by('categoria', 'nombre_plato')
    if q:
        platos = platos.filter(nombre_plato__icontains=q)
    if categoria:
        platos = platos.filter(categoria__icontains=categoria)

    inventario = []
    for plato in platos:
        porciones, insumo = _porciones_disponibles(plato)
        estado, clase = _estado_inventario(porciones)
        inventario.append({
            'plato': plato,
            'insumo_critico': insumo,
            'porciones_disponibles': porciones,
            'estado_titulo': estado,
            'estado_clase': clase,
            'lotes': plato.receta.select_related('insumo').all(),
        })

    total_porciones = sum(item['porciones_disponibles'] for item in inventario)
    stock_bajo = sum(1 for item in inventario if item['estado_titulo'] == 'Stock bajo')
    agotados = sum(1 for item in inventario if item['estado_titulo'] == 'Agotado')

    context = {
        'platos_activos': len(inventario),
        'porciones_totales': total_porciones,
        'stock_bajo': stock_bajo,
        'agotados': agotados,
        'inventario': inventario,
        'q': q,
        'categoria': categoria,
        'categorias': ['Fuertes', 'Parrilla', 'Mariscos', 'Sopas', 'Entradas'],
        'total_porciones_display': format_money(total_porciones),
    }
    return render(request, 'Inventario.html', context)


def vista_menu(request):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')

    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    platos = Plato.objects.filter(estado=True).order_by('categoria', 'nombre_plato')

    if q:
        platos = platos.filter(nombre_plato__icontains=q)
    if categoria:
        platos = platos.filter(categoria__icontains=categoria)

    return render(request, 'Menu.html', {
        'platos': platos,
        'q': q,
        'categoria': categoria,
        'categorias': ['Fuertes', 'Parrilla', 'Mariscos', 'Sopas', 'Entradas'],
    })


def vista_mesero(request):
    _repair_corrupted_decimal_rows()

    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')

    if request.method == 'POST':
        accion = request.POST.get('accion')
        mesa = request.POST.get('mesa') or request.session.get('mesa_actual')
        plato_id = request.POST.get('plato_id')
        comanda_id = request.POST.get('comanda_id')
        cantidad = max(1, int(request.POST.get('cantidad', '1') or '1'))

        if accion in ['seleccionar', 'seleccionar_mesa'] and mesa:
            request.session['mesa_actual'] = mesa
            return redirect('vista_mesero')

        usuario_actual = Usuario.objects.filter(id=request.session.get('usuario_id')).first()
        if not usuario_actual:
            usuario_actual = Usuario.objects.filter(rol=Usuario.Rol.EMPLEADO).order_by('id').first()

        if accion in ['agregar', 'crear'] and plato_id and mesa:
            plato = Plato.objects.get(pk=plato_id)
            comanda = Comanda.objects.filter(pk=comanda_id).first() if comanda_id else None
            if comanda is None:
                comanda = Comanda.objects.create(
                    usuario=usuario_actual or Usuario.objects.order_by('id').first(),
                    estado=Comanda.Estado.PENDIENTE,
                    total=0,
                )

            detalle, created = DetalleComanda.objects.get_or_create(
                comanda=comanda,
                plato=plato,
                defaults={
                    'cantidad': cantidad,
                    'precio_unitario': plato.precio_venta,
                    'comentario': f'Mesa {mesa}',
                    'lote_descontado': plato.receta.first().insumo if plato.receta.exists() else LoteInsumo.objects.order_by('id').first(),
                },
            )
            if not created:
                detalle.cantidad += cantidad
                detalle.precio_unitario = plato.precio_venta
                detalle.comentario = f'Mesa {mesa}'
                detalle.lote_descontado = plato.receta.first().insumo if plato.receta.exists() else detalle.lote_descontado
                detalle.save()

            comanda.total = sum((d.subtotal for d in comanda.detalles.all()), Decimal('0'))
            comanda.save(update_fields=['total'])
            return redirect('vista_mesero')

        if accion in ['enviar_facturacion', 'finalizar'] and comanda_id:
            comanda = Comanda.objects.get(pk=comanda_id)
            comanda.estado = Comanda.Estado.ENVIADA
            comanda.save(update_fields=['estado'])

            factura_existente = Factura.objects.filter(observacion__icontains=f'Comanda #{comanda.id}').first()
            if not factura_existente:
                usuario_factura = usuario_actual or Usuario.objects.filter(rol=Usuario.Rol.CAJERO).order_by('id').first() or Usuario.objects.order_by('id').first()
                factura = Factura.objects.create(
                    usuario=usuario_factura,
                    cliente=f'Mesa {request.session.get("mesa_actual", "general")}',
                    subtotal=comanda.total,
                    impuesto=Decimal('0'),
                    total=comanda.total,
                    estado=Factura.Estado.PENDIENTE,
                    observacion=f'Comanda #{comanda.id}',
                )
                for detalle in comanda.detalles.all():
                    Factura.detalles.related.model.objects.create(
                        factura=factura,
                        descripcion=detalle.plato.nombre_plato,
                        cantidad=detalle.cantidad,
                        precio_unitario=detalle.precio_unitario,
                    )
            return redirect('vista_mesero')

    mesas = list(range(1, 11))
    command_log = _safe_comandas()
    for item in command_log:
        first_detalle = item.detalles.all()[0] if item.detalles.all() else None
        item.mesa_texto = _mesa_label(first_detalle.comentario if first_detalle else '')

    return render(request, 'Comandas.html', {
        'mesas': mesas,
        'mesa_actual': request.session.get('mesa_actual'),
        'comandas': command_log,
        'platos': Plato.objects.filter(estado=True).order_by('categoria', 'nombre_plato'),
    })


def vista_cajero(request):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO]:
        return redirect('inicio')

    if request.method == 'POST' and request.POST.get('accion') == 'pagar':
        factura_id = request.POST.get('factura_id')
        if factura_id:
            factura = Factura.objects.get(pk=factura_id)
            factura.estado = Factura.Estado.PAGADA
            factura.observacion = factura.observacion or 'Pagada por caja'
            factura.save(update_fields=['estado', 'observacion'])
        return redirect('vista_cajero')

    facturas = _safe_facturas(15)
    comandas = _safe_comandas(10)
    for item in comandas:
        first_detalle = item.detalles.all()[0] if item.detalles.all() else None
        item.mesa_texto = _mesa_label(first_detalle.comentario if first_detalle else '')

    return render(request, 'Cajero.html', {
        'rol': 'cajero',
        'facturas': facturas,
        'comandas': comandas,
    })


def vista_facturacion(request):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')

    if request.method == 'POST' and request.POST.get('accion') == 'crear_factura':
        usuario_factura = Usuario.objects.filter(rol=Usuario.Rol.CAJERO).order_by('id').first() or Usuario.objects.filter(rol=Usuario.Rol.ADMIN).order_by('id').first()
        factura = Factura.objects.create(
            usuario=usuario_factura,
            cliente='Cliente general',
            subtotal=Decimal('0'),
            impuesto=Decimal('0'),
            total=Decimal('0'),
            estado=Factura.Estado.PENDIENTE,
            observacion='Factura creada desde caja',
        )
        return redirect('detalle_factura', factura_id=factura.id)

    facturas = _safe_facturas(10)
    total_ventas = sum((factura.total for factura in facturas), Decimal('0'))
    pendientes = Factura.objects.filter(estado=Factura.Estado.PENDIENTE).count()

    facturas_con_formato = []
    for factura in facturas:
        factura.total_display = format_money(factura.total)
        facturas_con_formato.append(factura)

    return render(request, 'Facturacion.html', {
        'facturas': facturas_con_formato,
        'total_ventas': total_ventas,
        'total_ventas_display': format_money(total_ventas),
        'pendientes': pendientes,
    })


def detalle_factura(request, factura_id):
    rol = request.session.get('rol')
    if rol and rol not in [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')

    factura = Factura.objects.select_related('usuario').get(pk=factura_id)
    factura.total_display = format_money(factura.total)
    factura.subtotal_display = format_money(factura.subtotal)
    factura.impuesto_display = format_money(factura.impuesto)
    return render(request, 'Factura.html', {'factura': factura})
```

### plantillas/Inicio.html
```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inicio</title>
    <style>
        :root {
            --principal: #F75E54;
            --principal-oscuro: #de5249;
            --fondo: #fff7f6;
            --texto: #2d2d2d;
            --muted: #666666;
            --borde: #f1d9d7;
            --blanco: #ffffff;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: linear-gradient(135deg, #fff6f5 0%, #fefefe 100%);
            font-family: Arial, sans-serif;
            color: var(--texto);
        }

        .card {
            width: min(820px, 90vw);
            background: var(--blanco);
            border: 1px solid var(--borde);
            border-radius: 18px;
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.06);
            padding: 42px 36px;
        }

        h1 {
            margin: 0 0 10px;
            font-size: clamp(28px, 4vw, 42px);
            text-align: center;
            color: var(--texto);
        }

        .subtitulo {
            margin: 0 0 32px;
            text-align: center;
            color: var(--muted);
            font-size: 16px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(180px, 1fr));
            gap: 22px;
        }

        .option {
            display: block;
            text-decoration: none;
            color: inherit;
            border: 1px solid #f1d2cf;
            border-radius: 18px;
            padding: 30px 18px;
            background: linear-gradient(180deg, #fffdfd 0%, #fff5f4 100%);
            transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
            text-align: center;
        }

        .option:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 22px rgba(247, 94, 84, 0.09);
            border-color: var(--principal);
        }

        .icon {
            width: 72px;
            height: 72px;
            margin: 0 auto 18px;
            border-radius: 18px;
            background: var(--principal);
            color: #fff;
            display: grid;
            place-items: center;
            font-size: 28px;
            font-weight: bold;
        }

        .option h2 {
            margin: 0 0 8px;
            font-size: 22px;
            color: var(--texto);
        }

        .option p {
            margin: 0;
            color: var(--muted);
            font-size: 14px;
            line-height: 1.5;
        }

        @media (max-width: 700px) {
            .grid {
                grid-template-columns: 1fr;
            }

            .card {
                padding: 28px 20px;
            }
        }
    </style>
</head>
<body>
    <main class="card">
        <h1>MarioBRos</h1>
        <p class="subtitulo">Selecciona el acceso que deseas</p>

        <div class="grid">
            <a class="option" href="{% url 'iniciar_sesion_rol' 'admin' %}">
                <div class="icon">A</div>
                <h2>Administrador</h2>
                <p>Gestión de inventario, menús y control del sistema.</p>
            </a>

            <a class="option" href="{% url 'iniciar_sesion_rol' 'mesero' %}">
                <div class="icon">M</div>
                <h2>Mesero</h2>
                <p>Atención al cliente y registro de comandas.</p>
            </a>

            <a class="option" href="{% url 'iniciar_sesion_rol' 'cajero' %}">
                <div class="icon">C</div>
                <h2>Cajero</h2>
                <p>Facturación y cierre de ventas.</p>
            </a>
        </div>
    </main>
</body>
</html>
```

### plantillas/Comandas.html
```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comandas</title>
    <style>
        :root {
            --principal: #F75E54;
            --fondo: #f6f3f2;
            --panel: #ffffff;
            --texto: #2d2d2d;
            --muted: #6e6e6e;
            --borde: #e8e2df;
            --verde: #4caf78;
            --gris: #f0eeed;
            --sombra: 0 8px 18px rgba(0,0,0,0.04);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, sans-serif;
            background: var(--fondo);
            color: var(--texto);
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 220px; background: #f3f1f0; border-right: 1px solid var(--borde); padding: 18px 14px;
        }
        .brand { font-weight: 700; margin-bottom: 26px; }
        .nav-item {
            display: flex; align-items: center; gap: 10px; padding: 10px 12px; margin-bottom: 8px;
            border-radius: 8px; color: #333; text-decoration: none;
        }
        .nav-item.active {
            background: rgba(247, 94, 84, 0.08); color: var(--principal); border: 1px solid rgba(247, 94, 84, 0.15); font-weight: 700;
        }
        .content { flex: 1; padding: 30px 32px; }
        .topbar {
            display: flex; justify-content: space-between; align-items: end; gap: 20px; margin-bottom: 22px;
        }
        h1 { margin: 0; }
        .sub { color: var(--muted); margin: 8px 0 0; }
        .badge {
            display: inline-block; padding: 8px 12px; border-radius: 999px; background: #fff3f1; color: var(--principal);
            font-size: 12px; font-weight: 700; border: 1px solid #ffd8d2;
        }
        .grid {
            display: grid; grid-template-columns: 1.1fr 2fr; gap: 24px;
        }
        .panel {
            background: var(--panel); border: 1px solid var(--borde); border-radius: 14px; padding: 22px; box-shadow: var(--sombra);
        }
        .mesa-grid {
            display: grid; grid-template-columns: repeat(5, minmax(60px, 1fr)); gap: 12px; margin-top: 18px;
        }
        .mesa-btn {
            border: 1px solid var(--borde); background: var(--gris); color: var(--texto); border-radius: 10px;
            padding: 12px 8px; font-weight: 700; cursor: pointer;
        }
        .mesa-btn.active {
            background: var(--principal); border-color: var(--principal); color: #fff;
        }
        .menu-list {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px;
        }
        .menu-card {
            background: #fffaf9; border: 1px solid var(--borde); border-radius: 12px; padding: 14px; display: flex; flex-direction: column; gap: 10px;
        }
        .menu-card h3 { margin: 0; font-size: 16px; }
        .menu-card .precio { color: var(--verde); font-weight: 700; }
        .menu-card form { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
        .menu-card input, .menu-card textarea { width: 100%; padding: 8px 10px; border: 1px solid var(--borde); border-radius: 8px; }
        .menu-card button, .primary-btn {
            background: var(--principal); color: #fff; border: none; border-radius: 8px; padding: 10px 12px; font-weight: 700; cursor: pointer;
        }
        .command-list { margin-top: 18px; display: grid; gap: 16px; }
        .command-item {
            border: 1px solid var(--borde); border-radius: 12px; background: #fff; padding: 16px;
        }
        .command-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }
        .status { display: inline-block; padding: 5px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; }
        .status.pendiente { background: #fff1dc; color: #af7c1c; }
        .status.enviada { background: #e5f5ee; color: #2e7d5b; }
        .command-items { color: var(--muted); margin: 8px 0; }
        .footer-actions { margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
        .secondary-btn {
            background: #f6f3f2; border: 1px solid var(--borde); border-radius: 8px; padding: 9px 12px; color: var(--texto); font-weight: 700; cursor: pointer;
        }
        @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .sidebar { width: 100%; border-right: none; border-bottom: 1px solid var(--borde); } .content { padding: 20px 18px; } }
    </style>
</head>
<body>
    <div class="layout">
        <aside class="sidebar">
            <div class="brand">Sazón</div>
            <nav>
                <a class="nav-item" href="{% url 'vista_admin' %}">◫ Inventario</a>
                <a class="nav-item" href="{% url 'vista_menu' %}">☰ Menú</a>
                <a class="nav-item active" href="{% url 'vista_mesero' %}">☷ Comandas</a>
                <a class="nav-item" href="{% url 'vista_facturacion' %}">▣ Facturación</a>
                <a class="nav-item" href="{% url 'inicio' %}">↩ Volver a inicio</a>
            </nav>
        </aside>

        <main class="content">
            <div class="topbar">
                <div>
                    <h1>Vista de mesero</h1>
                    <p class="sub">Mesero: crea, ajusta y finaliza comandas por mesa.</p>
                </div>
                <span class="badge">Mesa actual: {% if mesa_actual %}{{ mesa_actual }}{% else %}Sin seleccionar{% endif %}</span>
            </div>

            <div class="grid">
                <section class="panel">
                    <h2>Mesas</h2>
                    <div class="mesa-grid">
                        {% for mesa in mesas %}
                        <form method="post">
                            {% csrf_token %}
                            <input type="hidden" name="mesa" value="{{ mesa }}">
                            <button class="mesa-btn {% if mesa_actual == mesa %}active{% endif %}" type="submit" name="accion" value="seleccionar">Mesa {{ mesa }}</button>
                        </form>
                        {% endfor %}
                    </div>
                </section>

                <section class="panel">
                    <h2>Menú disponible</h2>
                    <div class="menu-list">
                        {% for plato in platos %}
                        <div class="menu-card">
                            <div>
                                <h3>{{ plato.nombre_plato }}</h3>
                                <div class="precio">${{ plato.precio_venta }}</div>
                            </div>
                            <form method="post">
                                {% csrf_token %}
                                <input type="hidden" name="accion" value="crear">
                                <input type="hidden" name="mesa" value="{{ mesa_actual|default:'' }}">
                                <input type="hidden" name="plato_id" value="{{ plato.id }}">
                                <input type="number" name="cantidad" value="1" min="1" max="20">
                                <button type="submit">Agregar</button>
                            </form>
                        </div>
                        {% empty %}
                        <p>No hay platos activos para agregar.</p>
                        {% endfor %}
                    </div>
                </section>
            </div>

            <section class="panel" style="margin-top: 24px;">
                <h2>Comandas activas</h2>
                <div class="command-list">
                    {% for comanda in comandas %}
                    <div class="command-item">
                        <div class="command-head">
                            <strong>Comanda #{{ comanda.id }}</strong>
                            <span class="status {{ comanda.estado }}">{{ comanda.get_estado_display }}</span>
                        </div>
                        <div><strong>Mesa:</strong> {{ comanda.mesa_texto }}</div>
                        <div class="command-items">
                            {% for detalle in comanda.detalles.all %}
                                {{ detalle.plato.nombre_plato }} x{{ detalle.cantidad }}{% if not forloop.last %}, {% endif %}
                            {% empty %}
                                Sin platos agregados.
                            {% endfor %}
                        </div>
                        <div><strong>Total:</strong> ${{ comanda.total }}</div>
                        <div class="footer-actions">
                            <form method="post" style="display:inline;">
                                {% csrf_token %}
                                <input type="hidden" name="accion" value="crear">
                                <input type="hidden" name="mesa" value="{{ mesa_actual|default:'' }}">
                                <input type="hidden" name="comanda_id" value="{{ comanda.id }}">
                                <input type="hidden" name="plato_id" value="{{ platos.0.id|default:'' }}">
                                <button class="secondary-btn" type="submit">Agregar a esta comanda</button>
                            </form>
                            <form method="post" style="display:inline;">
                                {% csrf_token %}
                                <input type="hidden" name="accion" value="finalizar">
                                <input type="hidden" name="comanda_id" value="{{ comanda.id }}">
                                <button class="primary-btn" type="submit">Enviar</button>
                            </form>
                        </div>
                    </div>
                    {% empty %}
                    <p>No hay comandas registradas.</p>
                    {% endfor %}
                </div>
            </section>
        </main>
    </div>
</body>
</html>
```

### plantillas/Cajero.html
```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cajero</title>
    <style>
        :root {
            --principal: #F75E54;
            --fondo: #f7f4f2;
            --panel: #ffffff;
            --texto: #2d2d2d;
            --muted: #6e6e6e;
            --borde: #eaded9;
            --verde: #4caf78;
            --naranja: #f2a552;
            --rojo: #d95e5e;
            --gris: #f3f1f0;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0; min-height: 100vh; font-family: Arial, sans-serif; background: var(--fondo); color: var(--texto);
        }
        .layout { display: flex; min-height: 100vh; }
        .sidebar {
            width: 220px; background: #f2efee; border-right: 1px solid var(--borde); padding: 18px 14px;
        }
        .brand { font-weight: 700; margin-bottom: 24px; }
        .nav-item {
            display: flex; align-items: center; gap: 10px; padding: 10px 12px; margin-bottom: 8px; border-radius: 8px; color: #333; text-decoration: none;
        }
        .nav-item.active {
            background: rgba(247, 94, 84, 0.08); color: var(--principal); border: 1px solid rgba(247, 94, 84, 0.15); font-weight: 700;
        }
        .content { flex: 1; padding: 30px 32px; }
        .topbar { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 24px; }
        h1 { margin: 0; }
        .sub { margin: 8px 0 0; color: var(--muted); }
        .badge {
            display: inline-block; padding: 8px 12px; border-radius: 999px; background: #fff3f1; color: var(--principal);
            font-size: 12px; font-weight: 700; border: 1px solid #ffd8d2;
        }
        .panels {
            display: grid; grid-template-columns: 1.2fr 1fr; gap: 24px;
        }
        .card {
            background: var(--panel); border: 1px solid var(--borde); border-radius: 14px; padding: 22px; box-shadow: 0 6px 18px rgba(0,0,0,0.03);
        }
        table {
            width: 100%; border-collapse: collapse; margin-top: 18px;
        }
        th, td { padding: 12px 10px; border-bottom: 1px solid var(--borde); text-align: left; }
        th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
        .status {
            display: inline-block; padding: 6px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; border: 1px solid transparent;
        }
        .status.pagada { background: #e7f7ef; color: var(--verde); border-color: rgba(76, 175, 120, 0.2); }
        .status.pendiente { background: #fff2df; color: var(--naranja); border-color: rgba(242, 165, 82, 0.2); }
        .status.cancelada { background: #fde9e9; color: var(--rojo); border-color: rgba(217, 94, 94, 0.2); }
        .btn-pay {
            background: var(--principal); color: #fff; border: none; border-radius: 8px; padding: 8px 12px; font-weight: 700; cursor: pointer;
        }
        .order-list { display: grid; gap: 14px; }
        .order-item {
            border: 1px solid var(--borde); background: #fffaf9; border-radius: 12px; padding: 14px;
        }
        .meta { color: var(--muted); font-size: 12px; }
        .money { font-size: 18px; font-weight: 700; }
        @media (max-width: 900px) { .layout { flex-direction: column; } .sidebar { width: 100%; border-right: none; border-bottom: 1px solid var(--borde); } .content { padding: 20px 18px; } .panels { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="layout">
        <aside class="sidebar">
            <div class="brand">Sazón</div>
            <nav>
                <a class="nav-item" href="{% url 'vista_admin' %}">◫ Inventario</a>
                <a class="nav-item" href="{% url 'vista_menu' %}">☰ Menú</a>
                <a class="nav-item" href="{% url 'vista_mesero' %}">☷ Comandas</a>
                <a class="nav-item active" href="{% url 'vista_facturacion' %}">▣ Facturación</a>
                <a class="nav-item" href="{% url 'inicio' %}">↩ Volver a inicio</a>
            </nav>
        </aside>

        <main class="content">
            <div class="topbar">
                <div>
                    <h1>Cajero</h1>
                    <p class="sub">Verifica pagos y confirma la facturación de las comandas.</p>
                </div>
                <span class="badge">Caja</span>
            </div>

            <div class="panels">
                <section class="card">
                    <h2>Facturas pendientes</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Factura</th>
                                <th>Cliente</th>
                                <th>Total</th>
                                <th>Estado</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for factura in facturas %}
                            <tr>
                                <td>{{ factura.numero }}</td>
                                <td>{{ factura.cliente|default:'Cliente general' }}</td>
                                <td>${{ factura.total }}</td>
                                <td><span class="status {{ factura.estado }}">{{ factura.get_estado_display }}</span></td>
                                <td>
                                    <form method="post">
                                        {% csrf_token %}
                                        <input type="hidden" name="accion" value="pagar">
                                        <input type="hidden" name="factura_id" value="{{ factura.id }}">
                                        <button class="btn-pay" type="submit">Marcar pagada</button>
                                    </form>
                                </td>
                            </tr>
                            {% empty %}
                            <tr><td colspan="5">No hay facturas por pagar.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </section>

                <section class="card">
                    <h2>Comandas activas</h2>
                    <div class="order-list">
                        {% for comanda in comandas %}
                        <div class="order-item">
                            <div class="meta">Comanda #{{ comanda.id }} · {{ comanda.fecha_hora|date:'d/m/Y H:i' }}</div>
                            <div class="money">Total: ${{ comanda.total }}</div>
                            <div class="meta">Estado: {{ comanda.get_estado_display }}</div>
                            <div class="meta">Detalle: {% for detalle in comanda.detalles.all %}{{ detalle.plato.nombre_plato }} x{{ detalle.cantidad }}{% if not forloop.last %}, {% endif %}{% empty %}Sin detalles{% endfor %}</div>
                        </div>
                        {% empty %}
                        <p>No hay comandas registradas.</p>
                        {% endfor %}
                    </div>
                </section>
            </div>
        </main>
    </div>
</body>
</html>
```

### plantillas/IniciarSesion.html
```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Iniciar sesión</title>
    <style>
        :root {
            --principal: #F75E54;
            --fondo: #fff7f6;
            --texto: #2d2d2d;
            --borde: #dddddd;
            --gris: #6b7280;
        }

        * { box-sizing: border-box; }

        body {
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
            background: var(--fondo);
            color: var(--texto);
            font-family: Arial, sans-serif;
        }

        .login {
            width: 100%;
            max-width: 420px;
            padding: 32px;
            background: #ffffff;
            border-top: 5px solid var(--principal);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
            border-radius: 10px;
        }

        h1 { margin: 0 0 8px; font-size: 28px; }
        .subtitulo { margin: 0 0 18px; color: #666666; }
        .rol-tag {
            display: inline-block;
            margin-bottom: 16px;
            background: #fff1ef;
            color: var(--principal);
            border: 1px solid #ffd3ce;
            border-radius: 999px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        label { display: block; margin: 16px 0 6px; font-weight: bold; }

        input, select {
            width: 100%;
            padding: 12px;
            border: 1px solid var(--borde);
            border-radius: 6px;
            font-size: 16px;
        }

        input:focus, select:focus {
            outline: 2px solid var(--principal);
            border-color: var(--principal);
        }

        button {
            width: 100%;
            margin-top: 24px;
            padding: 12px;
            border: 0;
            border-radius: 6px;
            background: var(--principal);
            color: #ffffff;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }

        button:hover { background: #dc4e46; }
        .error { color: #b42318; margin: 0 0 16px; font-weight: bold; }
        .volver {
            display: inline-block;
            margin-top: 16px;
            color: var(--gris);
            text-decoration: none;
            font-size: 14px;
        }
        .volver:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <main class="login">
        <h1>Iniciar sesión</h1>
        <p class="subtitulo">Acceso para {{ titulo_rol }}</p>
        <span class="rol-tag">{{ rol }}</span>

        {% if error %}<p class="error">{{ error }}</p>{% endif %}

        <form method="post">
            {% csrf_token %}
            <input type="hidden" name="rol" value="{{ rol }}">

            <label for="usuario">Usuario</label>
            <input type="text" id="usuario" name="usuario" autocomplete="username" required>

            <label for="password">Contraseña</label>
            <input type="password" id="password" name="password" autocomplete="current-password" required>

            <button type="submit">Ingresar</button>
        </form>

        <a class="volver" href="{% url 'inicio' %}">← Volver al inicio</a>
    </main>
</body>
</html>
```

### core/tests.py
```python
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import Factura, LoteInsumo, Plato, RecetaPlato, Usuario


class InventarioViewTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session.save()

        self.arroz = LoteInsumo.objects.create(
            codigo_referencia='REF-20240101-001',
            nombre_insumo='Arroz',
            categoria=LoteInsumo.Categoria.HARINAS,
            precio_unitario=Decimal('12.50'),
            cantidad_disponible=Decimal('20.00'),
            stock_minimo=Decimal('5.00'),
            fecha_ingreso='2024-01-01',
            fecha_vencimiento='2024-01-30',
        )
        self.pollo = LoteInsumo.objects.create(
            codigo_referencia='REF-20240102-001',
            nombre_insumo='Pollo',
            categoria=LoteInsumo.Categoria.CARNES,
            precio_unitario=Decimal('35.00'),
            cantidad_disponible=Decimal('30.00'),
            stock_minimo=Decimal('10.00'),
            fecha_ingreso='2024-01-02',
            fecha_vencimiento='2024-02-05',
        )

        self.plato = Plato.objects.create(
            nombre_plato='Arroz chino',
            categoria='granos',
            precio_venta=Decimal('120.00'),
            estado=True,
        )
        RecetaPlato.objects.create(
            plato=self.plato,
            insumo=self.arroz,
            cantidad_requerida=Decimal('10.00'),
        )
        RecetaPlato.objects.create(
            plato=self.plato,
            insumo=self.pollo,
            cantidad_requerida=Decimal('15.00'),
        )

        self.plato_disponible = Plato.objects.create(
            nombre_plato='Pollo a la colombiana',
            categoria='carnes',
            precio_venta=Decimal('180.00'),
            estado=True,
        )
        RecetaPlato.objects.create(
            plato=self.plato_disponible,
            insumo=self.pollo,
            cantidad_requerida=Decimal('5.00'),
        )

    def test_vista_admin_muestra_inventario(self):
        response = self.client.get(reverse('vista_admin'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inventario de platos')
        self.assertContains(response, 'Platos activos')
        self.assertContains(response, 'Arroz chino')
        self.assertContains(response, 'Pollo a la colombiana')
        self.assertContains(response, 'Disponible')
        self.assertContains(response, 'Stock bajo')

    def test_login_admin_desde_raiz_usa_credenciales_fijas(self):
        response = self.client.post(
            reverse('iniciar_sesion'),
            {'usuario': 'admin', 'password': 'admin123'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('vista_admin'))
        self.assertContains(response, 'Inventario de platos')

    def test_iniciar_sesion_rol_no_falla_si_existen_usuarios_duplicados(self):
        Usuario.objects.create(
            nombre='cajero',
            rol=Usuario.Rol.CAJERO,
            password_hash=make_password('cajero123'),
            estado=True,
        )
        Usuario.objects.create(
            nombre='cajero',
            rol=Usuario.Rol.CAJERO,
            password_hash=make_password('cajero123'),
            estado=True,
        )

        response = self.client.get(reverse('iniciar_sesion_rol', args=['cajero']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Usuario.objects.filter(nombre='cajero').count(), 1)


class RolLoginTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.mesero = Usuario.objects.create(
            nombre='mesero',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('mesero123'),
            estado=True,
        )
        self.cajero = Usuario.objects.create(
            nombre='cajero',
            rol=Usuario.Rol.CAJERO,
            password_hash=make_password('cajero123'),
            estado=True,
        )

    def test_login_mesero_usa_credenciales_de_mesero(self):
        response = self.client.post(
            reverse('iniciar_sesion_rol', args=['mesero']),
            {'usuario': 'mesero', 'password': 'mesero123'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('vista_mesero'))
        self.assertContains(response, 'Comandas')

    def test_login_cajero_usa_credenciales_de_cajero(self):
        response = self.client.post(
            reverse('iniciar_sesion_rol', args=['cajero']),
            {'usuario': 'cajero', 'password': 'cajero123'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('vista_cajero'))
        self.assertContains(response, 'Cajero')
```

## Autor
Proyecto MarioBRos
