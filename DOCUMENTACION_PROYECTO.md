# MarioBRos

## Descripcion

Aplicacion web Django para la operacion de un restaurante: autenticacion por roles, inventario por lotes, menu, comandas, facturacion y reportes.

Roles disponibles: `admin`, `empleado` (mesero) y `cajero`.

## Tecnologias

- Python 3.13
- Django 6.1
- SQLite
- Templates HTML de Django
- openpyxl para exportacion Excel
- ReportLab para exportacion PDF

Las dependencias se encuentran en [requirements.txt](requirements.txt).

## Estructura

```text
MarioBRos/
├── config/                 # Configuracion, ASGI, WSGI y URLs
├── core/                   # Modelos, vistas, admin, pruebas y migraciones
├── plantillas/             # Templates HTML
├── db.sqlite3             # Base de datos local
├── db.sqlite3.before-repair.bak
├── manage.py
├── requirements.txt
└── DOCUMENTACION_PROYECTO.md
```

Templates actuales: `Inicio.html`, `IniciarSesion.html`, `Inventario.html`,
`Comandas.html`, `Cajero.html`, `Facturacion.html`, `Factura.html`, `Menu.html`,
`base.html`, `Usuarios.html`, `Lotes.html`, `Platos.html`, `Recetas.html` y
`Reportes.html`.

## Funcionalidades

### Autenticacion

El sistema valida usuario, rol, contrasena y estado. Las credenciales de
 demostracion creadas automaticamente son:

| Usuario | Rol | Contrasena |
| --- | --- | --- |
| `admin` | Administrador | `admin123` |
| `mesero` | Empleado/Mesero | `mesero123` |
| `cajero` | Cajero | `cajero123` |

Las contrasenas se guardan con `make_password` y se verifican con
`check_password`. El login registra el evento y el logout registra el cierre
antes de limpiar la sesion.

### Inventario y catalogo

El administrador puede consultar y filtrar platos, registrar existencias,
crear lotes, editar catalogo y asociar recetas. Las referencias de lotes se
generan como `REF-YYYYMMDD-XXX` cuando no se proporciona una referencia.

El sistema muestra stock bajo, agotados, lotes proximos a vencer y valor del
inventario. Las entradas de stock y las mermas rechazan cantidades negativas,
invalidas o superiores a la existencia disponible. Cada merma queda auditada
en `AjusteMerma` con usuario, motivo, observacion y fecha.

### Comandas e inventario PEPS/FIFO

El mesero selecciona mesas del 1 al 10, crea comandas, agrega cantidades y
puede enviarlas o cancelarlas. Al enviar una comanda:

1. Se valida el estado pendiente.
2. Se descuenta el inventario por fecha de ingreso y luego por ID.
3. Se registra cada descuento en `MovimientoInventario`.
4. Si falta stock, se revierte la operacion y se informa el error.
5. Se crea una factura pendiente con sus detalles.

Al cancelar una comanda enviada, los movimientos no revertidos se devuelven
a sus lotes originales y quedan marcados como revertidos.

### Caja, facturacion y reportes

El cajero puede consultar facturas y confirmar pagos seleccionando el metodo
de pago. La facturacion muestra ventas y pendientes, y el detalle de factura
muestra sus conceptos. Los reportes estan disponibles en pantalla y pueden
exportarse a PDF o Excel. La API `GET /api/resumen/` devuelve ventas pagadas,
pendientes y valor del inventario para usuarios autenticados.

## Modelos

Los modelos estan en [core/models.py](core/models.py):

- `Usuario`: cuenta, rol, estado y contrasena hasheada.
- `RegistroSesion`: login/logout, fecha e IP.
- `LoteInsumo`: existencias, precio, categoria y fechas.
- `Plato`: nombre, precio, categoria y estado.
- `RecetaPlato`: insumos requeridos por plato.
- `Comanda` y `DetalleComanda`: orden, platos, cantidades y totales.
- `MovimientoInventario`: descuento por lote, cantidad y estado de reversion.
- `AjusteMerma`: ajuste manual auditado.
- `Factura` y `DetalleFactura`: comprobantes, pagos y conceptos.

Estados de comanda: `pendiente`, `enviada`, `cancelada`, `pagada`.
Estados de factura: `pendiente`, `pagada`, `cancelada`.
Metodos de pago: `efectivo`, `tarjeta`, `transferencia`, `mixto`.

## Rutas

Las rutas estan en [config/urls.py](config/urls.py):

| Ruta | Uso |
| --- | --- |
| `/` | Pantalla inicial |
| `/login/` y `/login/<rol>/` | Inicio de sesion |
| `/logout/` | Cierre de sesion auditado |
| `/dashboard/` | Redireccion segun rol |
| `/admin/inicio/` | Inventario y mermas |
| `/admin/usuarios/` | CRUD de usuarios |
| `/admin/lotes/` | CRUD de lotes |
| `/admin/platos/` | CRUD de platos |
| `/admin/recetas/` | CRUD de recetas |
| `/menu/` | Menu activo |
| `/mesero/inicio/` | Comandas |
| `/cajero/inicio/` | Caja y pagos |
| `/facturacion/` | Facturacion |
| `/factura/<id>/` | Detalle de factura |
| `/reportes/` | Ventas y exportaciones |
| `/reportes/excel/` | Descarga Excel |
| `/reportes/pdf/` | Descarga PDF |
| `/api/resumen/` | Resumen JSON autenticado |
| `/admin/` | Administracion de Django |

## Seguridad y tolerancia a errores

Las vistas comprueban el rol y el usuario activo antes de modificar datos.
Los IDs se resuelven con `get_object_or_404`; las cantidades se normalizan y
se limitan; los formularios controlan valores vacios, negativos, no numericos,
fechas invalidas y conflictos de integridad. Las operaciones de inventario
usan transacciones para evitar descuentos parciales.

Para produccion, definir `DJANGO_SECRET_KEY`, usar `DJANGO_DEBUG=0`, configurar
`ALLOWED_HOSTS` y no usar las credenciales de demostracion.

## Migraciones

Las migraciones de `core` llegan hasta `0005` e incluyen el historial de
movimientos, el lote opcional en detalles de comanda y el rol cajero.

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

## Pruebas y ejecucion

Las pruebas estan en [core/tests.py](core/tests.py). Para ejecutar las
comprobaciones:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

Para iniciar el servidor:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir `http://127.0.0.1:8000/`.

## Archivos de referencia

- [config/settings.py](config/settings.py)
- [config/urls.py](config/urls.py)
- [core/models.py](core/models.py)
- [core/views.py](core/views.py)
- [core/tests.py](core/tests.py)
- [plantillas/](plantillas/)

## Autor

Proyecto MarioBRos
