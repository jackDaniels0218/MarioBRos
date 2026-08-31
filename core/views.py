from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect, render

from .models import Factura, Plato, RegistroSesion, Usuario


def _ensure_default_users():
    usuarios = [
        ('admin', Usuario.Rol.ADMIN, 'admin123'),
        ('mesero', Usuario.Rol.EMPLEADO, 'mesero123'),
    ]

    for nombre, rol, password in usuarios:
        if not Usuario.objects.filter(nombre=nombre, estado=True).exists():
            Usuario.objects.create(
                nombre=nombre,
                rol=rol,
                password_hash=make_password(password),
                estado=True,
            )


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


def inicio(request):
    return render(request, 'Inicio.html')


def iniciar_sesion(request, rol='admin'):
    error = None
    rol = request.POST.get('rol', request.GET.get('rol', rol or 'admin'))
    _ensure_default_users()

    if request.method == 'POST':
        nombre = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')

        if rol == 'cajero':
            request.session['usuario_id'] = None
            request.session['rol'] = 'cajero'
            return redirect('vista_facturacion')

        usuario = Usuario.objects.filter(nombre=nombre, rol=rol, estado=True).first()

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
            return redirect('vista_mesero')

        error = 'Usuario o contraseña incorrectos.'

    if rol == 'admin':
        titulo = 'Administrador'
    elif rol == 'mesero':
        titulo = 'Mesero'
    else:
        titulo = 'Cajero'

    return render(request, 'IniciarSesion.html', {'error': error, 'rol': rol, 'titulo_rol': titulo})


def vista_admin(request):
    if request.session.get('rol') != Usuario.Rol.ADMIN:
        return redirect('iniciar_sesion')

    platos = Plato.objects.filter(estado=True).prefetch_related('receta__insumo').order_by('categoria', 'nombre_plato')
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
    }
    return render(request, 'Inventario.html', context)


def vista_menu(request):
    platos = Plato.objects.filter(estado=True).order_by('categoria', 'nombre_plato')
    return render(request, 'Menu.html', {'platos': platos})


def vista_mesero(request):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')
    return render(request, 'Comandas.html')


def vista_cajero(request):
    if request.session.get('rol') != 'cajero':
        return redirect('inicio')
    return render(request, 'Cajero.html', {'rol': 'cajero'})


def vista_facturacion(request):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, 'cajero']:
        return redirect('inicio')

    facturas = Factura.objects.select_related('usuario').order_by('-fecha_hora')[:10]
    total_ventas = sum((factura.total for factura in facturas), Decimal('0'))
    pendientes = Factura.objects.filter(estado=Factura.Estado.PENDIENTE).count()
    context = {
        'facturas': facturas,
        'total_ventas': total_ventas,
        'pendientes': pendientes,
    }
    return render(request, 'Facturacion.html', context)


def detalle_factura(request, factura_id):
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, 'cajero']:
        return redirect('inicio')

    factura = Factura.objects.select_related('usuario').get(pk=factura_id)
    return render(request, 'Factura.html', {'factura': factura})

