from datetime import timedelta
from decimal import Decimal, InvalidOperation
import re

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection, transaction
from django.db.models import Count, Sum
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import LoteAdminForm, MermaAdminForm, PlatoAdminForm, RecetaAdminForm, UsuarioAdminForm

from .models import (
    Comanda,
    ConsumoInsumo,
    AjusteMerma,
    DetalleComanda,
    DetalleFactura,
    Factura,
    LoteInsumo,
    Plato,
    RegistroSesion,
    RegistroActividad,
    RecetaPlato,
    Usuario,
)
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


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
    sql = 'SELECT id, usuario_id, fecha_hora, estado, CAST(total AS TEXT) FROM core_comanda ORDER BY fecha_hora DESC'
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
    sql = 'SELECT id, usuario_id, cliente, fecha_hora, CAST(subtotal AS TEXT), CAST(impuesto AS TEXT), CAST(total AS TEXT), metodo_pago, estado, observacion FROM core_factura ORDER BY fecha_hora DESC'
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


def _mesa_value(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _active_comanda_for_mesa(mesa):
    mesa_num = _mesa_value(mesa)
    if mesa_num is None:
        return None
    return (
        Comanda.objects.filter(
            mesa=mesa_num,
            estado__in=[Comanda.Estado.PENDIENTE, Comanda.Estado.ENVIADA],
        )
        .select_related('usuario')
        .order_by('-fecha_hora')
        .first()
    )


def _get_or_create_comanda_for_mesa(usuario, mesa):
    mesa_num = _mesa_value(mesa)
    if mesa_num is None:
        return None, 'Mesa inválida.'

    with transaction.atomic():
        comanda = _active_comanda_for_mesa(mesa_num)
        if comanda is not None:
            return comanda, None

        comanda = Comanda.objects.create(
            usuario=usuario or Usuario.objects.order_by('id').first(),
            mesa=mesa_num,
            estado=Comanda.Estado.PENDIENTE,
            total=Decimal('0'),
        )
        return comanda, None


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


def _vista_inventario_legacy(request):
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


def _admin_activity(request, usuario, accion, detalle=''):
    RegistroActividad.objects.create(
        usuario=usuario,
        accion=accion,
        detalle=detalle,
        ip_address=request.META.get('REMOTE_ADDR') or '0.0.0.0',
    )


def _reporte_admin(fecha):
    comandas = Comanda.objects.filter(fecha_hora__date=fecha)
    pagadas = comandas.filter(estado=Comanda.Estado.PAGADA)
    ventas = Factura.objects.filter(fecha_hora__date=fecha, estado=Factura.Estado.PAGADA).aggregate(total=Sum('total'))['total'] or Decimal('0')
    detalles = DetalleComanda.objects.filter(comanda__in=pagadas)
    costo = sum((consumo.cantidad * consumo.costo_unitario for consumo in ConsumoInsumo.objects.filter(detalle_comanda__in=detalles)), Decimal('0'))
    mermas = AjusteMerma.objects.filter(fecha_hora__date=fecha).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
    return {'fecha': fecha, 'ventas': ventas, 'pagadas': pagadas.count(), 'canceladas': comandas.filter(estado=Comanda.Estado.CANCELADA).count(), 'platos': detalles.aggregate(total=Sum('cantidad'))['total'] or 0, 'costo': costo, 'ganancia': ventas - costo, 'mermas': mermas}


def _descontar_fifo(comanda):
    consumos = []
    for detalle in comanda.detalles.select_related('plato').all():
        for receta in detalle.plato.receta.select_related('insumo').all():
            requerido = receta.cantidad_requerida * detalle.cantidad
            lotes = LoteInsumo.objects.filter(
                nombre_insumo=receta.insumo.nombre_insumo,
                cantidad_disponible__gt=0,
            ).order_by('fecha_ingreso', 'id')
            restante = requerido
            for lote in lotes:
                usado = min(restante, lote.cantidad_disponible)
                if usado <= 0:
                    continue
                lote.cantidad_disponible -= usado
                lote.save(update_fields=['cantidad_disponible'])
                consumos.append(ConsumoInsumo(detalle_comanda=detalle, lote=lote, cantidad=usado, costo_unitario=lote.precio_unitario))
                restante -= usado
                if restante <= 0:
                    break
            if restante > 0:
                raise ValueError(f'Stock insuficiente para {receta.insumo.nombre_insumo}.')
    ConsumoInsumo.objects.bulk_create(consumos)


def reporte_admin_exportar(request, formato):
    if request.session.get('rol') != Usuario.Rol.ADMIN:
        return redirect('iniciar_sesion')
    fecha = request.GET.get('fecha') or str(timezone.localdate())
    reporte = _reporte_admin(fecha)
    if formato == 'excel':
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Cierre del día'
        sheet.append(['Indicador', 'Valor'])
        for key, value in reporte.items():
            sheet.append([key, str(value)])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="reporte-{fecha}.xlsx"'
        workbook.save(response)
        return response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte-{fecha}.pdf"'
    pdf = canvas.Canvas(response, pagesize=letter)
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(60, 750, f'Reporte administrativo - {fecha}')
    pdf.setFont('Helvetica', 11)
    y = 720
    for key, value in reporte.items():
        pdf.drawString(70, y, f'{key}: {value}')
        y -= 22
    pdf.save()
    return response


def vista_admin(request):
    if request.session.get('rol') != Usuario.Rol.ADMIN:
        return redirect('iniciar_sesion')

    usuario = Usuario.objects.filter(id=request.session.get('usuario_id'), rol=Usuario.Rol.ADMIN, estado=True).first()
    seccion = request.GET.get('seccion', 'dashboard')
    if seccion == 'inventario' and request.method == 'POST' and request.POST.get('accion') == 'stock':
        lote = LoteInsumo.objects.get(pk=request.POST['lote_id'])
        cantidad = Decimal(request.POST.get('cantidad', '0'))
        if cantidad > 0:
            lote.cantidad_disponible += cantidad
            lote.save(update_fields=['cantidad_disponible'])
            _admin_activity(request, usuario, 'Actualizar stock', f'Lote {lote.id}: +{cantidad}')
        return redirect('vista_admin')

    if request.method == 'POST' and request.POST.get('accion') == 'toggle_usuario':
        item = Usuario.objects.get(pk=request.POST['usuario_id'])
        if item.pk != usuario.pk:
            item.estado = not item.estado
            item.save(update_fields=['estado'])
            _admin_activity(request, usuario, 'Cambiar estado de usuario', item.nombre)
        return redirect('/admin/inicio/?seccion=usuarios')

    form_targets = {
        'guardar_usuario': (UsuarioAdminForm, 'usuarios'),
        'guardar_lote': (LoteAdminForm, 'lotes'),
        'guardar_plato': (PlatoAdminForm, 'platos'),
        'guardar_receta': (RecetaAdminForm, 'recetas'),
        'guardar_merma': (MermaAdminForm, 'mermas'),
    }
    if request.method == 'POST' and request.POST.get('accion') in form_targets:
        form_class, target = form_targets[request.POST['accion']]
        form = form_class(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            if request.POST['accion'] == 'guardar_merma':
                if obj.cantidad <= 0 or obj.cantidad > obj.lote.cantidad_disponible:
                    return render(request, 'AdminPanel.html', {'seccion': 'mermas', 'form_merma': form, 'error': 'La cantidad de merma supera el stock disponible.'})
                obj.usuario = usuario
                obj.lote.cantidad_disponible -= obj.cantidad
                obj.lote.save(update_fields=['cantidad_disponible'])
            obj.save()
            _admin_activity(request, usuario, request.POST['accion'], str(obj))
            return redirect(f'/admin/inicio/?seccion={target}')

    hoy = timezone.localdate()
    comandas_hoy = Comanda.objects.filter(fecha_hora__date=hoy)
    ventas = Factura.objects.filter(fecha_hora__date=hoy, estado=Factura.Estado.PAGADA)
    context = {
        'seccion': seccion,
        'ventas_dia': ventas.aggregate(total=Sum('total'))['total'] or Decimal('0'),
        'comandas_dia': comandas_hoy.count(),
        'pendientes': comandas_hoy.filter(estado=Comanda.Estado.PENDIENTE).count(),
        'enviadas': comandas_hoy.filter(estado=Comanda.Estado.ENVIADA).count(),
        'pagadas': comandas_hoy.filter(estado=Comanda.Estado.PAGADA).count(),
        'canceladas': comandas_hoy.filter(estado=Comanda.Estado.CANCELADA).count(),
        'valor_inventario': sum((lote.cantidad_disponible * lote.precio_unitario for lote in LoteInsumo.objects.all()), Decimal('0')),
        'stock_critico': LoteInsumo.objects.filter(cantidad_disponible__lte=5).order_by('cantidad_disponible')[:10],
        'por_vencer': LoteInsumo.objects.filter(fecha_vencimiento__gte=hoy, fecha_vencimiento__lte=hoy + timedelta(days=30)).order_by('fecha_vencimiento')[:10],
        'usuarios': Usuario.objects.order_by('nombre'),
        'lotes': LoteInsumo.objects.order_by('-fecha_ingreso'),
        'platos': Plato.objects.order_by('categoria', 'nombre_plato'),
        'recetas': RecetaPlato.objects.select_related('plato', 'insumo'),
        'mermas': AjusteMerma.objects.select_related('lote', 'usuario')[:50],
        'sesiones': RegistroSesion.objects.select_related('usuario')[:100],
        'actividades': RegistroActividad.objects.select_related('usuario')[:100],
        'mesas': [{'numero': n, 'comanda': _active_comanda_for_mesa(n)} for n in range(1, 11)],
        'comandas': Comanda.objects.select_related('usuario').prefetch_related('detalles__plato')[:100],
        'form_usuario': UsuarioAdminForm(),
        'form_lote': LoteAdminForm(),
        'form_plato': PlatoAdminForm(),
        'form_receta': RecetaAdminForm(),
        'form_merma': MermaAdminForm(),
    }
    if seccion == 'reportes':
        context['fecha_reporte'] = request.GET.get('fecha') or str(hoy)
        context['reporte'] = _reporte_admin(context['fecha_reporte'])
    context['mesas_ocupadas'] = sum(1 for mesa in context['mesas'] if mesa['comanda'])
    context['inventario'] = []
    for plato in Plato.objects.filter(estado=True).prefetch_related('receta__insumo').order_by('categoria', 'nombre_plato'):
        porciones, insumo = _porciones_disponibles(plato)
        estado, clase = _estado_inventario(porciones)
        context['inventario'].append({'plato': plato, 'insumo_critico': insumo, 'porciones_disponibles': porciones, 'estado_titulo': estado, 'estado_clase': clase})
    if seccion == 'inventario':
        platos = Plato.objects.filter(estado=True).prefetch_related('receta__insumo').order_by('categoria', 'nombre_plato')
        context['inventario'] = []
        for plato in platos:
            porciones, insumo = _porciones_disponibles(plato)
            estado, clase = _estado_inventario(porciones)
            context['inventario'].append({'plato': plato, 'insumo_critico': insumo, 'porciones_disponibles': porciones, 'estado_titulo': estado, 'estado_clase': clase})
    return render(request, 'AdminPanel.html', context)


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
    if request.session.get('rol') not in [Usuario.Rol.ADMIN, Usuario.Rol.EMPLEADO]:
        return redirect('inicio')

    selected_mesa = request.POST.get('mesa') or request.GET.get('mesa') or request.session.get('mesa_actual')
    selected_mesa = _mesa_value(selected_mesa)
    request.session['mesa_actual'] = selected_mesa if selected_mesa is not None else None

    usuario_actual = Usuario.objects.filter(id=request.session.get('usuario_id')).first()
    if not usuario_actual:
        usuario_actual = Usuario.objects.filter(rol=Usuario.Rol.EMPLEADO).order_by('id').first()

    error = None
    info = None

    if request.method == 'POST':
        accion = request.POST.get('accion')
        mesa = request.POST.get('mesa') or request.session.get('mesa_actual')
        plato_id = request.POST.get('plato_id')
        comanda_id = request.POST.get('comanda_id')
        detalle_id = request.POST.get('detalle_id')
        codigo = (request.POST.get('codigo') or '').strip()
        cantidad = request.POST.get('cantidad', '1')

        try:
            cantidad = max(1, int(cantidad or '1'))
        except (TypeError, ValueError):
            cantidad = 1

        if accion in ['seleccionar', 'seleccionar_mesa', 'abrir_mesa'] and mesa:
            request.session['mesa_actual'] = _mesa_value(mesa)
            return redirect('vista_mesero')

        if accion == 'cerrar_mesa':
            request.session['mesa_actual'] = None
            return redirect('vista_mesero')

        if accion in ['agregar', 'crear'] and plato_id and mesa:
            plato = Plato.objects.filter(pk=plato_id).first()
            if not plato:
                error = 'Producto no encontrado.'
            else:
                comanda, comanda_error = _get_or_create_comanda_for_mesa(usuario_actual, mesa)
                if comanda_error:
                    error = comanda_error
                else:
                    if comanda.mesa != _mesa_value(mesa):
                        comanda.mesa = _mesa_value(mesa)
                        comanda.save(update_fields=['mesa'])

                    detalle, created = DetalleComanda.objects.get_or_create(
                        comanda=comanda,
                        plato=plato,
                        defaults={
                            'cantidad': cantidad,
                            'precio_unitario': plato.precio_venta,
                            'comentario': f'Mesa {comanda.mesa}',
                            'lote_descontado': plato.receta.first().insumo if plato.receta.exists() else None,
                        },
                    )
                    if not created:
                        detalle.cantidad += cantidad
                        detalle.precio_unitario = plato.precio_venta
                        detalle.comentario = f'Mesa {comanda.mesa}'
                        detalle.lote_descontado = plato.receta.first().insumo if plato.receta.exists() else detalle.lote_descontado
                        detalle.save()

                    comanda.total = sum((d.subtotal for d in comanda.detalles.all()), Decimal('0'))
                    comanda.save(update_fields=['total'])
                    request.session['mesa_actual'] = comanda.mesa
                    info = 'Producto agregado correctamente.'
                    return redirect('vista_mesero')

        if accion in ['incrementar', 'disminuir', 'eliminar'] and detalle_id:
            detalle = DetalleComanda.objects.filter(pk=detalle_id).select_related('comanda', 'plato').first()
            if detalle is None:
                error = 'No se encontró el detalle de la comanda.'
            else:
                if accion == 'incrementar':
                    detalle.cantidad += 1
                    detalle.save(update_fields=['cantidad'])
                    info = 'Cantidad aumentada.'
                elif accion == 'disminuir':
                    if detalle.cantidad > 1:
                        detalle.cantidad -= 1
                        detalle.save(update_fields=['cantidad'])
                        info = 'Cantidad reducida.'
                    else:
                        detalle.delete()
                        info = 'Producto eliminado.'
                elif accion == 'eliminar':
                    detalle.delete()
                    info = 'Producto eliminado.'

                comanda = detalle.comanda
                comanda.total = sum((d.subtotal for d in comanda.detalles.all()), Decimal('0'))
                if not comanda.detalles.exists():
                    comanda.estado = Comanda.Estado.CANCELADA
                    comanda.save(update_fields=['total', 'estado'])
                else:
                    comanda.save(update_fields=['total'])
                request.session['mesa_actual'] = detalle.comanda.mesa
                return redirect('vista_mesero')

        if accion in ['enviar_facturacion', 'finalizar'] and comanda_id:
            comanda = Comanda.objects.filter(pk=comanda_id).prefetch_related('detalles__plato__receta__insumo').first()
            if comanda is None:
                error = 'La comanda no existe.'
            else:
                if not ConsumoInsumo.objects.filter(detalle_comanda__comanda=comanda).exists():
                    try:
                        with transaction.atomic():
                            _descontar_fifo(comanda)
                            comanda.estado = Comanda.Estado.ENVIADA
                            comanda.save(update_fields=['estado'])
                    except ValueError as exc:
                        error = str(exc)
                        return redirect('vista_mesero')
                else:
                    comanda.estado = Comanda.Estado.ENVIADA
                    comanda.save(update_fields=['estado'])

                factura_existente = Factura.objects.filter(observacion__icontains=f'Comanda #{comanda.id}').first()
                if not factura_existente:
                    usuario_factura = usuario_actual or Usuario.objects.filter(rol=Usuario.Rol.CAJERO).order_by('id').first() or Usuario.objects.order_by('id').first()
                    factura = Factura.objects.create(
                        usuario=usuario_factura,
                        cliente=f'Mesa {comanda.mesa}',
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
                info = f'Comanda #{comanda.id} enviada a facturación.'
                return redirect('vista_mesero')

        if codigo:
            plato_buscar = Plato.objects.filter(estado=True).filter(Q(codigo__icontains=codigo) | Q(nombre_plato__icontains=codigo)).first()
            if plato_buscar is not None:
                info = f'Producto encontrado: {plato_buscar.nombre_plato}'

    mesas = list(range(1, 11))
    mesa_statuses = []
    for mesa_num in mesas:
        comanda = _active_comanda_for_mesa(mesa_num)
        mesa_statuses.append({
            'mesa': mesa_num,
            'ocupada': comanda is not None,
            'comanda': comanda,
        })

    mesa_comanda = _active_comanda_for_mesa(selected_mesa) if selected_mesa is not None else None
    if mesa_comanda is not None:
        mesa_detalles = list(mesa_comanda.detalles.select_related('plato').all())
    else:
        mesa_detalles = []

    categoria_actual = request.GET.get('categoria') or request.POST.get('categoria') or 'Todos'
    categorias = ['Todos'] + sorted({plato.categoria for plato in Plato.objects.filter(estado=True).only('categoria')})
    platos = Plato.objects.filter(estado=True).order_by('categoria', 'nombre_plato')
    if categoria_actual and categoria_actual != 'Todos':
        platos = platos.filter(categoria__icontains=categoria_actual)

    query_codigo = request.GET.get('codigo', '').strip() or request.POST.get('codigo', '').strip()
    if query_codigo:
        platos = platos.filter(Q(codigo__icontains=query_codigo) | Q(nombre_plato__icontains=query_codigo))

    command_log = _safe_comandas()
    for item in command_log:
        first_detalle = item.detalles.all()[0] if item.detalles.all() else None
        item.mesa_texto = _mesa_label(first_detalle.comentario if first_detalle else '')

    return render(request, 'Comandas.html', {
        'mesas': mesas,
        'mesa_statuses': mesa_statuses,
        'mesa_actual': selected_mesa,
        'mesa_comanda': mesa_comanda,
        'mesa_detalles': mesa_detalles,
        'platos': platos,
        'categorias': categorias,
        'categoria_actual': categoria_actual,
        'codigo_busqueda': query_codigo,
        'error': error,
        'info': info,
        'comandas': command_log,
        'total_mesa': mesa_comanda.total if mesa_comanda else Decimal('0'),
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

            referencia = re.search(r'\bComanda\s+#(\d+)\b', factura.observacion or '', re.IGNORECASE)
            if referencia:
                Comanda.objects.filter(
                    pk=int(referencia.group(1)),
                    estado=Comanda.Estado.ENVIADA,
                ).update(estado=Comanda.Estado.PAGADA)
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

