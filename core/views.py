from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.shortcuts import redirect, render

from .models import (
    Comanda,
    DetalleComanda,
    DetalleFactura,
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
                value = Decimal(str(total))
                if not value.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                cursor.execute(f'UPDATE core_comanda SET total = 0 WHERE id = {int(comanda_id)}')
                continue

            if total != value:
                cursor.execute(f'UPDATE core_comanda SET total = {value} WHERE id = {int(comanda_id)}')

        cursor.execute('SELECT id, precio_unitario FROM core_detallecomanda')
        for detalle_id, precio in cursor.fetchall():
            try:
                value = Decimal(str(precio))
                if not value.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, TypeError, ValueError):
                cursor.execute(f'UPDATE core_detallecomanda SET precio_unitario = 0 WHERE id = {int(detalle_id)}')
                continue

            if precio != value:
                cursor.execute(
                    f'UPDATE core_detallecomanda SET precio_unitario = {value} WHERE id = {int(detalle_id)}'
                )


class _SafeDetalleCollection:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _SafeComandaView:
    def __init__(self, comanda, detalles):
        self.id = comanda.id
        self.usuario = comanda.usuario
        self.usuario_id = comanda.usuario_id
        self.fecha_hora = comanda.fecha_hora
        self.estado = comanda.estado
        self.total = _safe_decimal(comanda.total)
        self.detalles = _SafeDetalleCollection(detalles)
        self.mesa_texto = ''
        self.get_estado_display = comanda.get_estado_display


def _safe_comandas(limit=None):
    _repair_corrupted_decimal_rows()

    sql = 'SELECT id, usuario_id, fecha_hora, estado, total FROM core_comanda ORDER BY fecha_hora DESC'
    if limit is not None:
        sql += f' LIMIT {int(limit)}'

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    comandas = []
    for comanda_id, usuario_id, fecha_hora, estado, total in rows:
        comanda = type('TmpComanda', (), {
            'id': comanda_id,
            'usuario_id': usuario_id,
            'fecha_hora': fecha_hora,
            'estado': estado,
            'total': _safe_decimal(total),
            'get_estado_display': lambda self, s=estado: s,
            'usuario': None,
        })()

        detalle_sql = f'SELECT id, plato_id, cantidad, precio_unitario, comentario FROM core_detallecomanda WHERE comanda_id = {int(comanda_id)} ORDER BY id'
        with connection.cursor() as cursor_detalle:
            cursor_detalle.execute(detalle_sql)
            detalle_rows = cursor_detalle.fetchall()

        detalles = []
        for detalle_id, plato_id, cantidad, precio_unitario, comentario in detalle_rows:
            detalle = type('TmpDetalle', (), {
                'id': detalle_id,
                'comanda': comanda,
                'plato_id': plato_id,
                'cantidad': cantidad or 0,
                'precio_unitario': _safe_decimal(precio_unitario),
                'comentario': comentario or '',
                'plato': None,
            })()
            detalles.append(detalle)

        comandas.append(_SafeComandaView(comanda, detalles))

    return comandas


def _safe_facturas(limit=None):
    sql = 'SELECT id, usuario_id, cliente, fecha_hora, subtotal, impuesto, total, metodo_pago, estado, observacion FROM core_factura ORDER BY fecha_hora DESC'
    if limit is not None:
        sql += f' LIMIT {int(limit)}'

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

    facturas = []
    for row in rows:
        factura_id, usuario_id, cliente, fecha_hora, subtotal, impuesto, total, metodo_pago, estado, observacion = row
        factura = Factura(
            id=factura_id,
            usuario_id=usuario_id,
            cliente=cliente,
            fecha_hora=fecha_hora,
            subtotal=_safe_decimal(subtotal),
            impuesto=_safe_decimal(impuesto),
            total=_safe_decimal(total),
            metodo_pago=metodo_pago,
            estado=estado,
            observacion=observacion,
        )
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
                    DetalleFactura.objects.create(
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

