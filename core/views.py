from datetime import timedelta
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Sum
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LoteAdminForm, MermaAdminForm, PlatoAdminForm, RecetaAdminForm, UsuarioAdminForm, ResetPasswordForm

from .models import (
    Comanda,
    ConsumoInsumo,
    AjusteMerma,
    DetalleComanda,
    DetalleFactura,
    Factura,
    LoteInsumo,
    MovimientoInventario,
    Plato,
    RegistroSesion,
    RegistroActividad,
    RecetaPlato,
    Usuario,
)
from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

CATEGORIES = ['Fuertes', 'Parrilla', 'Mariscos', 'Sopas', 'Entradas']


def _current_user(request):
    usuario = Usuario.objects.filter(
        id=request.session.get('usuario_id'), estado=True
    ).first()
    if usuario is None and request.session.get('rol'):
        usuario = Usuario.objects.filter(
            rol=request.session.get('rol'), estado=True
        ).order_by('id').first()
    return usuario


def _has_role(request, roles):
    usuario = _current_user(request)
    return usuario is not None and usuario.rol in roles


def _ip(request):
    return request.META.get('REMOTE_ADDR') or '0.0.0.0'


def _safe_int(value, default=1, minimum=1, maximum=1000):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(result, maximum))


def _safe_positive_decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or result <= 0:
        return None
    return result


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
                'plato': Plato.objects.filter(pk=plato_id).first(),
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
    """Calcula estado de disponibilidad basado en porciones.
    NO USAR PARA ALERTAS DE STOCK BAJO - usar _estado_lote_insumo en su lugar."""
    if porciones_disponibles <= 0:
        return 'Agotado', 'agotado'
    if porciones_disponibles <= 5:
        return 'Stock bajo', 'bajo'
    return 'Disponible', 'disponible'


def _estado_lote_insumo(lote, hoy=None):
    """Calcula estado de un lote de insumo basado en stock_minimo y vencimiento.
    
    Returns:
        (estado_titulo, clase_css) donde:
        - 'Vencido' si ya pasó fecha_vencimiento
        - 'Próximo a vencer' si vence en los próximos 7 días
        - 'Stock crítico' si cantidad_disponible <= stock_minimo
        - 'Disponible' en caso contrario
    """
    if hoy is None:
        hoy = timezone.localdate()
    
    # Verificar vencimiento
    if lote.fecha_vencimiento < hoy:
        return 'Vencido', 'vencido'
    
    # Verificar próximo a vencer (próximos 7 días)
    if lote.fecha_vencimiento <= hoy + timedelta(days=7):
        return 'Próximo a vencer', 'pronto_a_vencer'
    
    # Verificar stock crítico basado en stock_minimo real del lote
    if lote.cantidad_disponible <= lote.stock_minimo:
        return 'Stock crítico', 'stock_critico'
    
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


def logout_view(request):
    usuario = None
    usuario_id = request.session.get('usuario_id')
    if usuario_id:
        usuario = Usuario.objects.filter(pk=usuario_id).first()

    if usuario:
        RegistroSesion.objects.create(
            usuario=usuario,
            tipo_evento=RegistroSesion.TipoEvento.LOGOUT,
            ip_address=request.META.get('REMOTE_ADDR') or '0.0.0.0',
        )

    request.session.flush()
    return redirect('inicio')


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


def _handle_usuario_crud(request, usuario_actual):
    """Maneja creación y edición de usuarios con auditoría.
    
    Returns:
        (usuario_editado, error_message) o (None, None) si es POST y redirige
    """
    usuario_id = request.POST.get('usuario_id', '')
    
    # Si tiene ID, es edición
    if usuario_id:
        try:
            usuario_a_editar = Usuario.objects.get(pk=int(usuario_id))
        except (ValueError, Usuario.DoesNotExist):
            return None, 'Usuario no encontrado.'
    else:
        usuario_a_editar = None
    
    # Crear formulario
    form = UsuarioAdminForm(request.POST, instance=usuario_a_editar)
    if form.is_valid():
        usuario_guardado = form.save(commit=False)
        
        # Validar que no se intente desactivar a sí mismo
        if usuario_guardado.pk == usuario_actual.pk and not usuario_guardado.estado:
            return usuario_guardado, 'No puedes desactivar tu propio usuario.'
        
        usuario_guardado.save()
        
        # Auditar
        if usuario_a_editar:
            _admin_activity(request, usuario_actual, 'Editar usuario', f'{usuario_guardado.nombre} (Rol: {usuario_guardado.rol}, Estado: {"Activo" if usuario_guardado.estado else "Inactivo"})')
        else:
            _admin_activity(request, usuario_actual, 'Crear usuario', f'{usuario_guardado.nombre} (Rol: {usuario_guardado.rol})')
        
        return usuario_guardado, None
    
    return None, 'Error en los datos del formulario.'


def _handle_reset_password(request, usuario_actual):
    """Maneja reset de contraseña sin conocer la actual.
    
    Returns:
        (success, message)
    """
    form = ResetPasswordForm(request.POST)
    if form.is_valid():
        try:
            usuario = Usuario.objects.get(pk=int(form.cleaned_data['usuario_id']))
        except (ValueError, Usuario.DoesNotExist):
            return False, 'Usuario no encontrado.'
        
        # Validar que no sea su propio usuario
        if usuario.pk == usuario_actual.pk:
            return False, 'No puedes resetear tu propia contraseña desde aquí. Contacta al administrador superior.'
        
        # Cambiar contraseña
        usuario.password_hash = make_password(form.cleaned_data['nueva_password'])
        usuario.save(update_fields=['password_hash'])
        
        _admin_activity(request, usuario_actual, 'Resetear contraseña', f'Usuario {usuario.nombre}')
        return True, 'Contraseña actualizada correctamente.'
    
    return False, 'Error en los datos del formulario.'



def _reporte_admin(fecha):
    comandas = Comanda.objects.filter(fecha_hora__date=fecha)
    pagadas = comandas.filter(estado=Comanda.Estado.PAGADA)
    ventas = Factura.objects.filter(fecha_hora__date=fecha, estado=Factura.Estado.PAGADA).aggregate(total=Sum('total'))['total'] or Decimal('0')
    detalles = DetalleComanda.objects.filter(comanda__in=pagadas)
    costo = sum((consumo.cantidad * consumo.costo_unitario for consumo in ConsumoInsumo.objects.filter(detalle_comanda__in=detalles)), Decimal('0'))
    mermas = AjusteMerma.objects.filter(fecha_hora__date=fecha).aggregate(total=Sum('cantidad'))['total'] or Decimal('0')
    return {'fecha': fecha, 'ventas': ventas, 'pagadas': pagadas.count(), 'canceladas': comandas.filter(estado=Comanda.Estado.CANCELADA).count(), 'platos': detalles.aggregate(total=Sum('cantidad'))['total'] or 0, 'costo': costo, 'ganancia': ventas - costo, 'mermas': mermas}


def _descontar_fifo(comanda):
    if comanda is None:
        return

    if ConsumoInsumo.objects.filter(detalle_comanda__comanda=comanda).exists():
        return

    with transaction.atomic():
        detalles = list(comanda.detalles.select_related('plato').prefetch_related('plato__receta__insumo').all())
        if not detalles:
            return

        requerimientos = {}
        for detalle in detalles:
            for receta in detalle.plato.receta.select_related('insumo').all():
                insumo_nombre = receta.insumo.nombre_insumo
                requerido = Decimal(str(receta.cantidad_requerida)) * Decimal(detalle.cantidad)
                requerimientos[insumo_nombre] = requerimientos.get(insumo_nombre, Decimal('0')) + requerido

        lotes_disponibles = {}
        nombres = list(requerimientos.keys())
        if nombres:
            hoy = timezone.localdate()
            lotes = list(
                LoteInsumo.objects.select_for_update().filter(
                    nombre_insumo__in=nombres,
                    cantidad_disponible__gt=0,
                    fecha_vencimiento__gte=hoy,  # Excluir lotes vencidos
                ).order_by('fecha_ingreso', 'id')
            )
            for lote in lotes:
                lotes_disponibles.setdefault(lote.nombre_insumo, []).append(lote)

        for nombre_insumo, requerido in requerimientos.items():
            disponible = sum((Decimal(str(lote.cantidad_disponible)) for lote in lotes_disponibles.get(nombre_insumo, [])), Decimal('0'))
            if disponible < requerido:
                raise ValueError(f'Stock insuficiente para {nombre_insumo}.')

        consumos = []
        for detalle in detalles:
            detalle_consumos = []
            for receta in detalle.plato.receta.select_related('insumo').all():
                insumo_nombre = receta.insumo.nombre_insumo
                restante = Decimal(str(receta.cantidad_requerida)) * Decimal(detalle.cantidad)
                lotes = list(lotes_disponibles.get(insumo_nombre, []))
                for lote in lotes:
                    if restante <= 0:
                        break
                    if Decimal(str(lote.cantidad_disponible)) <= 0:
                        continue
                    usado = min(restante, Decimal(str(lote.cantidad_disponible)))
                    if usado <= 0:
                        continue
                    lote.cantidad_disponible = Decimal(str(lote.cantidad_disponible)) - usado
                    detalle_consumos.append((lote, usado))
                    consumos.append(
                        ConsumoInsumo(
                            detalle_comanda=detalle,
                            lote=lote,
                            cantidad=usado,
                            costo_unitario=lote.precio_unitario,
                        )
                    )
                    restante -= usado
                if restante > 0:
                    raise ValueError(f'Stock insuficiente para {insumo_nombre}.')
            if detalle_consumos:
                detalle.lote_descontado = detalle_consumos[0][0]
                detalle.save(update_fields=['lote_descontado'])

        for lote in [lote for lotes in lotes_disponibles.values() for lote in lotes]:
            lote.save(update_fields=['cantidad_disponible'])

        if consumos:
            ConsumoInsumo.objects.bulk_create(consumos)


def _revertir_consumos_comanda(comanda):
    if comanda is None:
        return

    with transaction.atomic():
        consumos = list(
            ConsumoInsumo.objects.select_for_update().filter(detalle_comanda__comanda=comanda).select_related('lote')
        )
        if not consumos:
            return

        for consumo in consumos:
            lote = consumo.lote
            lote.cantidad_disponible = Decimal(str(lote.cantidad_disponible)) + Decimal(str(consumo.cantidad))
            lote.save(update_fields=['cantidad_disponible'])

        ConsumoInsumo.objects.filter(detalle_comanda__comanda=comanda).delete()
        DetalleComanda.objects.filter(comanda=comanda).update(lote_descontado=None)


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
    if not usuario:
        return redirect('iniciar_sesion')
    
    seccion = request.GET.get('seccion', 'dashboard')
    error = None
    
    # ===== MANEJO DE USUARIOS =====
    if request.method == 'POST' and request.POST.get('accion') == 'guardar_usuario':
        usuario_guardado, error = _handle_usuario_crud(request, usuario)
        if error:
            context_error = {
                'seccion': 'usuarios',
                'error': error,
                'usuarios': Usuario.objects.order_by('nombre'),
                'form_usuario': UsuarioAdminForm(),
                'form_lote': LoteAdminForm(),
                'form_plato': PlatoAdminForm(),
                'form_receta': RecetaAdminForm(),
                'form_merma': MermaAdminForm(),
            }
            return render(request, 'AdminPanel.html', context_error)
        if usuario_guardado:
            return redirect('/admin/inicio/?seccion=usuarios')
    
    # ===== RESET DE CONTRASEÑA =====
    if request.method == 'POST' and request.POST.get('accion') == 'reset_password':
        success, message = _handle_reset_password(request, usuario)
        if success:
            return redirect('/admin/inicio/?seccion=usuarios')
        else:
            context_error = {
                'seccion': 'usuarios',
                'error': message,
                'usuarios': Usuario.objects.order_by('nombre'),
                'form_usuario': UsuarioAdminForm(),
                'form_lote': LoteAdminForm(),
                'form_plato': PlatoAdminForm(),
                'form_receta': RecetaAdminForm(),
                'form_merma': MermaAdminForm(),
            }
            return render(request, 'AdminPanel.html', context_error)
    
    # ===== ACTIVAR/DESACTIVAR USUARIO =====
    if request.method == 'POST' and request.POST.get('accion') == 'toggle_usuario':
        item = Usuario.objects.get(pk=request.POST['usuario_id'])
        if item.pk == usuario.pk:
            context_error = {
                'seccion': 'usuarios',
                'error': 'No puedes desactivar tu propio usuario.',
                'usuarios': Usuario.objects.order_by('nombre'),
                'form_usuario': UsuarioAdminForm(),
                'form_lote': LoteAdminForm(),
                'form_plato': PlatoAdminForm(),
                'form_receta': RecetaAdminForm(),
                'form_merma': MermaAdminForm(),
            }
            return render(request, 'AdminPanel.html', context_error)
        item.estado = not item.estado
        item.save(update_fields=['estado'])
        accion_texto = 'Activar usuario' if item.estado else 'Desactivar usuario'
        _admin_activity(request, usuario, accion_texto, item.nombre)
        return redirect('/admin/inicio/?seccion=usuarios')

    # ===== LOTES - NO permitir edición directa de cantidad =====
    if request.method == 'POST' and request.POST.get('accion') == 'guardar_lote':
        form = LoteAdminForm(request.POST)
        if form.is_valid():
            lote = form.save(commit=False)
            # Si es edición y ya existe, preservar cantidad_disponible
            if lote.pk:
                lote_anterior = LoteInsumo.objects.get(pk=lote.pk)
                lote.cantidad_disponible = lote_anterior.cantidad_disponible
            else:
                # Para creación, si no se especifica cantidad, asumir 0 (entraría por entrada de inventario)
                if not lote.cantidad_disponible:
                    lote.cantidad_disponible = Decimal('0')
            lote.save()
            accion_texto = 'Editar lote' if lote.pk else 'Crear lote'
            _admin_activity(request, usuario, accion_texto, f'{lote.codigo_referencia} - {lote.nombre_insumo}')
            return redirect('/admin/inicio/?seccion=lotes')
    
    # ===== PLATOS =====
    if request.method == 'POST' and request.POST.get('accion') == 'guardar_plato':
        form = PlatoAdminForm(request.POST)
        if form.is_valid():
            plato = form.save()
            accion_texto = 'Editar plato' if plato.pk else 'Crear plato'
            _admin_activity(request, usuario, accion_texto, plato.nombre_plato)
            return redirect('/admin/inicio/?seccion=platos')
    
    # ===== RECETAS =====
    if request.method == 'POST' and request.POST.get('accion') == 'guardar_receta':
        form = RecetaAdminForm(request.POST)
        if form.is_valid():
            receta = form.save()
            _admin_activity(request, usuario, 'Guardar receta', f'{receta.plato.nombre_plato} - {receta.insumo.nombre_insumo} ({receta.cantidad_requerida})')
            return redirect('/admin/inicio/?seccion=recetas')
    
    # ===== MERMAS CON TRANSACCIÓN =====
    if request.method == 'POST' and request.POST.get('accion') == 'guardar_merma':
        form = MermaAdminForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    merma = form.save(commit=False)
                    lote = merma.lote
                    
                    # Validaciones
                    if merma.cantidad <= 0:
                        raise ValueError('La cantidad debe ser mayor a cero.')
                    if merma.cantidad > lote.cantidad_disponible:
                        raise ValueError('La cantidad de merma supera el stock disponible.')
                    
                    merma.usuario = usuario
                    merma.save()
                    
                    # Descontar del inventario dentro de la transacción
                    lote.cantidad_disponible -= merma.cantidad
                    lote.save(update_fields=['cantidad_disponible'])
                    
                    _admin_activity(request, usuario, 'Registrar merma', f'Lote {lote.codigo_referencia}: {merma.cantidad} ({merma.motivo})')
                    return redirect('/admin/inicio/?seccion=mermas')
            except (ValueError, Exception) as e:
                error = str(e)
    
    # ===== CONTEXTO PARA DASHBOARD =====
    hoy = timezone.localdate()
    comandas_hoy = Comanda.objects.filter(fecha_hora__date=hoy)
    ventas = Factura.objects.filter(fecha_hora__date=hoy, estado=Factura.Estado.PAGADA)
    
    # Calcular stock crítico usando stock_minimo real de cada lote
    lotes_todos = LoteInsumo.objects.all()
    stock_critico = []
    por_vencer = []
    lotes_vencidos = []
    
    for lote in lotes_todos:
        estado, clase = _estado_lote_insumo(lote, hoy)
        if estado == 'Vencido':
            lotes_vencidos.append({'lote': lote, 'estado': estado, 'clase': clase})
        elif estado == 'Stock crítico':
            stock_critico.append({'lote': lote, 'estado': estado, 'clase': clase})
        elif estado == 'Próximo a vencer':
            por_vencer.append({'lote': lote, 'estado': estado, 'clase': clase})
    
    stock_critico = stock_critico[:10]
    por_vencer = por_vencer[:10]
    lotes_vencidos = lotes_vencidos[:10]
    
    context = {
        'seccion': seccion,
        'error': error,
        'ventas_dia': ventas.aggregate(total=Sum('total'))['total'] or Decimal('0'),
        'comandas_dia': comandas_hoy.count(),
        'pendientes': comandas_hoy.filter(estado=Comanda.Estado.PENDIENTE).count(),
        'enviadas': comandas_hoy.filter(estado=Comanda.Estado.ENVIADA).count(),
        'pagadas': comandas_hoy.filter(estado=Comanda.Estado.PAGADA).count(),
        'canceladas': comandas_hoy.filter(estado=Comanda.Estado.CANCELADA).count(),
        'valor_inventario': sum((lote.cantidad_disponible * lote.precio_unitario for lote in lotes_todos), Decimal('0')),
        'stock_critico': stock_critico,
        'por_vencer': por_vencer,
        'lotes_vencidos': lotes_vencidos,
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
    
    # Inventario de platos
    context['inventario'] = []
    for plato in Plato.objects.filter(estado=True).prefetch_related('receta__insumo').order_by('categoria', 'nombre_plato'):
        porciones, insumo = _porciones_disponibles(plato)
        estado, clase = _estado_inventario(porciones)
        context['inventario'].append({
            'plato': plato,
            'insumo_critico': insumo,
            'porciones_disponibles': porciones,
            'estado_titulo': estado,
            'estado_clase': clase
        })
    
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

        if accion in ['cancelar', 'cancelar_comanda'] and comanda_id:
            comanda = Comanda.objects.filter(pk=comanda_id).first()
            if comanda is None:
                error = 'La comanda no existe.'
            elif comanda.estado == Comanda.Estado.PAGADA:
                error = 'No se permite cancelar una comanda pagada.'
            else:
                if ConsumoInsumo.objects.filter(detalle_comanda__comanda=comanda).exists():
                    _revertir_consumos_comanda(comanda)
                comanda.total = Decimal('0')
                comanda.estado = Comanda.Estado.CANCELADA
                comanda.save(update_fields=['estado', 'total'])
                DetalleComanda.objects.filter(comanda=comanda).delete()
                request.session['mesa_actual'] = None
                info = f'Comanda #{comanda.id} cancelada.'
                return redirect('vista_mesero')

        if accion in ['incrementar', 'disminuir', 'eliminar'] and detalle_id:
            detalle = DetalleComanda.objects.filter(pk=detalle_id).select_related('comanda', 'plato').first()
            if detalle is None:
                error = 'No se encontró el detalle de la comanda.'
            else:
                comanda = detalle.comanda
                if comanda.estado in [Comanda.Estado.ENVIADA, Comanda.Estado.PAGADA]:
                    error = 'La comanda ya fue enviada; no se pueden modificar detalles.'
                    return redirect('vista_mesero')

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
            elif comanda.estado == Comanda.Estado.CANCELADA:
                error = 'No se puede enviar una comanda cancelada.'
            elif comanda.estado == Comanda.Estado.PAGADA:
                error = 'La comanda ya fue pagada.'
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
                elif comanda.estado == Comanda.Estado.PENDIENTE:
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


def logout_view(request):
    usuario = _current_user(request)
    if usuario:
        RegistroSesion.objects.create(
            usuario=usuario,
            tipo_evento=RegistroSesion.TipoEvento.LOGOUT,
            ip_address=_ip(request),
        )
    request.session.flush()
    messages.success(request, 'Sesion cerrada correctamente.')
    return redirect('inicio')


def dashboard(request):
    usuario = _current_user(request)
    if not usuario:
        return redirect('iniciar_sesion')
    destinos = {
        Usuario.Rol.ADMIN: 'vista_admin',
        Usuario.Rol.EMPLEADO: 'vista_mesero',
        Usuario.Rol.CAJERO: 'vista_cajero',
    }
    return redirect(destinos.get(usuario.rol, 'inicio'))


def _post_decimal(request, name, default=None):
    value = request.POST.get(name, '')
    if value in ('', None):
        return default
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    return result if result.is_finite() else default


def _inventory_data():
    data = []
    for plato in Plato.objects.filter(estado=True).prefetch_related('receta__insumo'):
        receta = list(plato.receta.all())
        porciones = [
            Decimal(str(item.insumo.cantidad_disponible)) / item.cantidad_requerida
            for item in receta
            if item.cantidad_requerida > 0
        ]
        cantidad = int(min(porciones)) if porciones else 0
        estado = 'Agotado' if cantidad <= 0 else (
            'Stock bajo' if cantidad <= 5 else 'Disponible'
        )
        data.append({
            'plato': plato,
            'porciones': cantidad,
            'porciones_disponibles': cantidad,
            'estado': estado,
            'estado_titulo': estado,
            'estado_clase': estado.lower().replace(' ', '-'),
            'receta': receta,
            'lotes': receta,
            'insumo_critico': receta[0].insumo.nombre_insumo if receta else 'Sin receta',
        })
    return data


def _fifo_descontar(detalle):
    movimientos = []
    for receta in detalle.plato.receta.select_related('insumo').order_by(
        'insumo__fecha_ingreso', 'insumo_id'
    ):
        restante = receta.cantidad_requerida * detalle.cantidad
        lotes = LoteInsumo.objects.select_for_update().filter(
            nombre_insumo=receta.insumo.nombre_insumo,
            categoria=receta.insumo.categoria,
            cantidad_disponible__gt=0,
        ).order_by('fecha_ingreso', 'id')
        for lote in lotes:
            if restante <= 0:
                break
            tomado = min(lote.cantidad_disponible, restante)
            lote.cantidad_disponible -= tomado
            lote.save(update_fields=['cantidad_disponible'])
            MovimientoInventario.objects.create(
                detalle=detalle, lote=lote, cantidad=tomado
            )
            movimientos.append((lote, tomado))
            restante -= tomado
        if restante > 0:
            for lote, tomado in reversed(movimientos):
                lote.cantidad_disponible += tomado
                lote.save(update_fields=['cantidad_disponible'])
            MovimientoInventario.objects.filter(
                detalle=detalle, revertido=False
            ).delete()
            raise ValueError(f'Stock insuficiente para {receta.insumo.nombre_insumo}.')
    return movimientos


@transaction.atomic
def enviar_comanda(comanda):
    if comanda.estado != Comanda.Estado.PENDIENTE:
        return
    for detalle in comanda.detalles.select_related('plato').all():
        _fifo_descontar(detalle)
    comanda.estado = Comanda.Estado.ENVIADA
    comanda.save(update_fields=['estado'])


def cancelar_comanda(comanda):
    with transaction.atomic():
        for movimiento in MovimientoInventario.objects.select_for_update().filter(
            detalle__comanda=comanda, revertido=False
        ):
            movimiento.lote.cantidad_disponible += movimiento.cantidad
            movimiento.lote.save(update_fields=['cantidad_disponible'])
            movimiento.revertido = True
            movimiento.save(update_fields=['revertido'])
        comanda.estado = Comanda.Estado.CANCELADA
        comanda.save(update_fields=['estado'])


def usuarios(request):
    if not _has_role(request, [Usuario.Rol.ADMIN]):
        return redirect('inicio')
    if request.method == 'POST':
        accion = request.POST.get('accion')
        usuario = get_object_or_404(Usuario, pk=request.POST.get('id')) if request.POST.get('id') else None
        nombre = request.POST.get('nombre', '').strip()
        if accion == 'crear' and nombre and request.POST.get('password'):
            Usuario.objects.create(
                nombre=nombre, rol=request.POST.get('rol', Usuario.Rol.EMPLEADO),
                password_hash=make_password(request.POST['password']), estado=True,
            )
        elif accion == 'editar' and usuario and nombre:
            usuario.nombre = nombre
            usuario.rol = request.POST.get('rol', usuario.rol)
            usuario.estado = 'estado' in request.POST
            usuario.save(update_fields=['nombre', 'rol', 'estado'])
        elif accion == 'password' and usuario and request.POST.get('password'):
            usuario.password_hash = make_password(request.POST['password'])
            usuario.save(update_fields=['password_hash'])
        else:
            messages.error(request, 'Datos de usuario invalidos.')
        return redirect('usuarios')
    return render(request, 'Usuarios.html', {
        'usuarios': Usuario.objects.all(), 'roles': Usuario.Rol.choices,
        'usuario': _current_user(request),
    })


def lotes(request):
    if not _has_role(request, [Usuario.Rol.ADMIN]):
        return redirect('inicio')
    if request.method == 'POST':
        try:
            cantidad = _post_decimal(request, 'cantidad')
            precio = _post_decimal(request, 'precio')
            minimo = _post_decimal(request, 'minimo', Decimal('0'))
            if not request.POST.get('nombre_insumo') or precio is None or cantidad is None or cantidad < 0 or precio < 0 or minimo < 0:
                raise ValueError
            LoteInsumo.objects.create(
                codigo_referencia='', nombre_insumo=request.POST['nombre_insumo'].strip(),
                categoria=request.POST.get('categoria', LoteInsumo.Categoria.OTROS),
                precio_unitario=precio, cantidad_disponible=cantidad, stock_minimo=minimo,
                fecha_ingreso=request.POST['ingreso'], fecha_vencimiento=request.POST['vencimiento'],
            )
            messages.success(request, 'Lote registrado.')
        except (KeyError, ValueError, TypeError, ValidationError, IntegrityError):
            messages.error(request, 'No se pudo registrar el lote. Revise los datos.')
        return redirect('lotes')
    return render(request, 'Lotes.html', {
        'lotes': LoteInsumo.objects.all(), 'categorias': LoteInsumo.Categoria.choices,
        'usuario': _current_user(request),
    })


def platos(request):
    if not _has_role(request, [Usuario.Rol.ADMIN]):
        return redirect('inicio')
    if request.method == 'POST':
        accion = request.POST.get('accion')
        plato = get_object_or_404(Plato, pk=request.POST.get('id')) if request.POST.get('id') else None
        precio = _post_decimal(request, 'precio')
        nombre = request.POST.get('nombre', '').strip()
        if precio is None or precio < 0 or not nombre:
            messages.error(request, 'Datos del plato invalidos.')
        elif accion == 'crear':
            Plato.objects.create(nombre_plato=nombre, precio_venta=precio, categoria=request.POST.get('categoria', ''), estado=True)
        elif accion == 'editar' and plato:
            plato.nombre_plato, plato.precio_venta = nombre, precio
            plato.categoria, plato.estado = request.POST.get('categoria', ''), 'estado' in request.POST
            plato.save()
        return redirect('platos')
    return render(request, 'Platos.html', {'platos': Plato.objects.all(), 'categorias': CATEGORIES, 'usuario': _current_user(request)})


def recetas(request):
    if not _has_role(request, [Usuario.Rol.ADMIN]):
        return redirect('inicio')
    if request.method == 'POST':
        cantidad = _post_decimal(request, 'cantidad')
        if cantidad is None or cantidad <= 0:
            messages.error(request, 'La cantidad debe ser mayor que cero.')
        else:
            RecetaPlato.objects.update_or_create(
                plato_id=request.POST.get('plato'), insumo_id=request.POST.get('insumo'),
                defaults={'cantidad_requerida': cantidad},
            )
        return redirect('recetas')
    return render(request, 'Recetas.html', {'recetas': RecetaPlato.objects.select_related('plato', 'insumo'), 'platos': Plato.objects.all(), 'lotes': LoteInsumo.objects.all(), 'usuario': _current_user(request)})


def reportes(request):
    if not _has_role(request, [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO]):
        return redirect('inicio')
    return render(request, 'Reportes.html', {'ventas': Factura.objects.filter(estado=Factura.Estado.PAGADA), 'usuario': _current_user(request)})


def reporte_excel(request):
    if not _has_role(request, [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO]):
        return redirect('inicio')
    try:
        from openpyxl import Workbook
    except ImportError:
        return HttpResponse('Dependencia openpyxl no instalada.', status=503)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['Factura', 'Fecha', 'Cliente', 'Subtotal', 'Impuesto', 'Total', 'Metodo'])
    for factura in Factura.objects.filter(estado=Factura.Estado.PAGADA):
        sheet.append([factura.numero, factura.fecha_hora.strftime('%Y-%m-%d %H:%M'), factura.cliente, float(factura.subtotal), float(factura.impuesto), float(factura.total), factura.get_metodo_pago_display()])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=ventas.xlsx'
    workbook.save(response)
    return response


def reporte_pdf(request):
    if not _has_role(request, [Usuario.Rol.ADMIN, Usuario.Rol.CAJERO]):
        return redirect('inicio')
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return HttpResponse('Dependencia reportlab no instalada.', status=503)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=ventas.pdf'
    documento = canvas.Canvas(response, pagesize=letter)
    y = 750
    documento.drawString(50, y, 'MarioBRos - Reporte de ventas')
    for factura in Factura.objects.filter(estado=Factura.Estado.PAGADA)[:35]:
        y -= 18
        documento.drawString(50, y, f'{factura.numero} | {factura.cliente[:20]} | ${factura.total:,.2f}')
    documento.save()
    return response


def api_resumen(request):
    if not _current_user(request):
        return JsonResponse({'detail': 'No autorizado'}, status=401)
    return JsonResponse({
        'ventas': float(sum((f.total for f in Factura.objects.filter(estado=Factura.Estado.PAGADA)), Decimal('0'))),
        'pendientes': Factura.objects.filter(estado=Factura.Estado.PENDIENTE).count(),
        'valor_inventario': float(sum((l.cantidad_disponible * l.precio_unitario for l in LoteInsumo.objects.all()), Decimal('0'))),
    })


def vista_admin(request):
    if not _has_role(request, [Usuario.Rol.ADMIN]):
        return redirect('iniciar_sesion')
    if request.method == 'POST':
        accion = request.POST.get('accion')
        lote = get_object_or_404(LoteInsumo, pk=request.POST.get('lote_id')) if request.POST.get('lote_id') else None
        cantidad = _post_decimal(request, 'cantidad')
        if not lote or cantidad is None or cantidad < 0:
            messages.error(request, 'Cantidad o lote invalido.')
        elif accion == 'stock':
            lote.cantidad_disponible += cantidad
            lote.save(update_fields=['cantidad_disponible'])
            messages.success(request, 'Existencias actualizadas.')
        elif accion == 'merma':
            usuario = _current_user(request)
            if cantidad <= 0 or cantidad > lote.cantidad_disponible or not usuario:
                messages.error(request, 'Cantidad de merma invalida.')
            else:
                lote.cantidad_disponible -= cantidad
                lote.save(update_fields=['cantidad_disponible'])
                AjusteMerma.objects.create(
                    lote=lote, usuario=usuario, cantidad=cantidad,
                    motivo=request.POST.get('motivo', AjusteMerma.Motivo.DESPERDICIO),
                    observacion=request.POST.get('observacion', '').strip(),
                )
                messages.success(request, 'Merma registrada y auditada.')
        return redirect('vista_admin')
    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    inventario = _inventory_data()
    if q:
        inventario = [item for item in inventario if q.lower() in item['plato'].nombre_plato.lower()]
    if categoria:
        inventario = [item for item in inventario if item['plato'].categoria.lower() == categoria.lower()]
    lotes = LoteInsumo.objects.all()
    return render(request, 'Inventario.html', {
        'inventario': inventario, 'lotes': lotes,
        'platos_activos': len(inventario),
        'porciones_totales': sum(item['porciones'] for item in inventario),
        'stock_bajo': sum(l.cantidad_disponible <= l.stock_minimo for l in lotes),
        'agotados': sum(item['estado'] == 'Agotado' for item in inventario),
        'lotes_vencer': sum(l.fecha_vencimiento <= timezone.localdate() + timedelta(days=7) and l.cantidad_disponible > 0 for l in lotes),
        'valor_inventario': sum((l.cantidad_disponible * l.precio_unitario for l in lotes), Decimal('0')),
        'q': q, 'categoria': categoria, 'categorias': CATEGORIES,
    })


def vista_mesero(request):
    if not _has_role(request, [Usuario.Rol.ADMIN, Usuario.Rol.EMPLEADO]):
        return redirect('inicio')
    usuario = _current_user(request)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        mesa = request.POST.get('mesa') or request.session.get('mesa_actual')
        if accion in ('seleccionar', 'seleccionar_mesa'):
            if mesa and str(mesa).isdigit() and 1 <= int(mesa) <= 10:
                request.session['mesa_actual'] = str(mesa)
            else:
                messages.error(request, 'Mesa invalida.')
            return redirect('vista_mesero')
        if accion in ('crear', 'agregar'):
            plato = get_object_or_404(Plato, pk=request.POST.get('plato_id'), estado=True)
            cantidad = _safe_int(request.POST.get('cantidad'), maximum=100)
            comanda = get_object_or_404(Comanda, pk=request.POST.get('comanda_id'), estado=Comanda.Estado.PENDIENTE) if request.POST.get('comanda_id') else Comanda.objects.create(usuario=usuario)
            detalle = comanda.detalles.filter(plato=plato).first() if accion == 'agregar' else None
            if detalle:
                detalle.cantidad += cantidad
                detalle.comentario = request.POST.get('comentario', detalle.comentario)
                detalle.save(update_fields=['cantidad', 'comentario'])
            else:
                detalle = DetalleComanda.objects.create(
                    comanda=comanda, plato=plato, cantidad=cantidad,
                    precio_unitario=plato.precio_venta,
                    comentario=request.POST.get('comentario') or f'Mesa {mesa or "sin asignar"}',
                )
            comanda.total = sum((item.subtotal for item in comanda.detalles.all()), Decimal('0'))
            comanda.save(update_fields=['total'])
            return redirect('vista_mesero')
        comanda = get_object_or_404(Comanda, pk=request.POST.get('comanda_id'))
        if accion in ('enviar', 'finalizar', 'enviar_facturacion'):
            try:
                enviar_comanda(comanda)
                if not Factura.objects.filter(observacion__icontains=f'Comanda #{comanda.id}').exists():
                    factura = Factura.objects.create(
                        usuario=usuario,
                        cliente=f'Mesa {mesa or "general"}',
                        subtotal=comanda.total,
                        impuesto=Decimal('0'),
                        total=comanda.total,
                        estado=Factura.Estado.PENDIENTE,
                        observacion=f'Comanda #{comanda.id}',
                    )
                    DetalleFactura.objects.bulk_create([
                        DetalleFactura(
                            factura=factura,
                            descripcion=detalle.plato.nombre_plato,
                            cantidad=detalle.cantidad,
                            precio_unitario=detalle.precio_unitario,
                        )
                        for detalle in comanda.detalles.select_related('plato').all()
                    ])
                messages.success(request, 'Comanda enviada y stock descontado por PEPS/FIFO.')
            except ValueError as error:
                messages.error(request, str(error))
            return redirect('vista_mesero')
        if accion == 'cancelar':
            cancelar_comanda(comanda)
            messages.success(request, 'Comanda cancelada y stock revertido.')
            return redirect('vista_mesero')
    comandas = _safe_comandas(20)
    for comanda in comandas:
        detalle = comanda.detalles.all()[0] if comanda.detalles.all() else None
        comanda.mesa_texto = _mesa_label(detalle.comentario if detalle else '')
    return render(request, 'Comandas.html', {
        'mesas': range(1, 11), 'mesa_actual': request.session.get('mesa_actual'),
        'comandas': comandas, 'platos': Plato.objects.filter(estado=True),
    })
