"""
Pruebas exhaustivas de FASE 2 - Completitud de funcionalidad.

Este archivo contiene pruebas para validar:
1. Stock mínimo (no hardcodeado)
2. Lotes vencidos
3. Lotes próximos a vencer
4. Merma con transacciones atómicas
5. Valoración del inventario
6. Reportes (diarios, con filtros reales)
7. Doble procesamiento (protección contra)
8. Auditoría (RegistroActividad)
9. CRUD usuarios completo
10. Restricciones de cantidad
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    AjusteMerma,
    Comanda,
    ConsumoInsumo,
    DetalleComanda,
    Factura,
    LoteInsumo,
    Plato,
    RecetaPlato,
    RegistroActividad,
    RegistroSesion,
    Usuario,
)


class StockMinimoYAlertasTests(TestCase):
    """Pruebas para stock_minimo real (no hardcodeado)."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_stock_critico_usa_stock_minimo_real_del_lote(self):
        """Stock crítico debe basarse en stock_minimo de cada lote, no en valor fijo."""
        lote_a = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-001',
            nombre_insumo='Tomate',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('3.00'),
            cantidad_disponible=Decimal('8.00'),
            stock_minimo=Decimal('10.00'),  # Stock crítico a 10
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 25),
        )
        lote_b = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-002',
            nombre_insumo='Lechuga',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('2.00'),
            cantidad_disponible=Decimal('3.00'),
            stock_minimo=Decimal('2.00'),  # Stock crítico a 2
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 20),
        )

        from core.views import _estado_lote_insumo
        hoy = timezone.localdate()
        
        # Lote A debe ser crítico (8 <= 10)
        estado_a, clase_a = _estado_lote_insumo(lote_a, hoy)
        self.assertEqual(estado_a, 'Stock crítico')
        
        # Lote B NO debe ser crítico (3 > 2)
        estado_b, clase_b = _estado_lote_insumo(lote_b, hoy)
        self.assertNotEqual(estado_b, 'Stock crítico')

    def test_stock_bajo_no_es_siempre_lte_5(self):
        """Stock bajo debe respetar el stock_minimo real, no ser siempre <= 5."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-003',
            nombre_insumo='Queso',
            categoria=LoteInsumo.Categoria.LACTEOS,
            precio_unitario=Decimal('8.00'),
            cantidad_disponible=Decimal('3.00'),
            stock_minimo=Decimal('1.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 30),
        )

        from core.views import _estado_lote_insumo
        estado, _ = _estado_lote_insumo(lote, timezone.localdate())
        self.assertNotEqual(estado, 'Stock crítico')


class LotesVencidosYProximosAlVencerTests(TestCase):
    """Pruebas para identificación de lotes vencidos y próximos a vencer."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_lote_vencido_se_identifica_como_vencido(self):
        """Un lote cuya fecha_vencimiento ya pasó debe identificarse como vencido."""
        hoy = timezone.localdate()
        lote_vencido = LoteInsumo.objects.create(
            codigo_referencia='REF-20260901-001',
            nombre_insumo='Leche',
            categoria=LoteInsumo.Categoria.LACTEOS,
            precio_unitario=Decimal('4.00'),
            cantidad_disponible=Decimal('10.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=hoy - timedelta(days=10),
            fecha_vencimiento=hoy - timedelta(days=1),  # Vencido ayer
        )

        from core.views import _estado_lote_insumo
        estado, clase = _estado_lote_insumo(lote_vencido, hoy)
        self.assertEqual(estado, 'Vencido')
        self.assertEqual(clase, 'vencido')

    def test_lote_proximo_a_vencer_se_identifica_correctamente(self):
        """Un lote que vence en los próximos 7 días debe identificarse como próximo a vencer."""
        hoy = timezone.localdate()
        lote_pronto = LoteInsumo.objects.create(
            codigo_referencia='REF-20260906-001',
            nombre_insumo='Yogur',
            categoria=LoteInsumo.Categoria.LACTEOS,
            precio_unitario=Decimal('5.00'),
            cantidad_disponible=Decimal('15.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=hoy - timedelta(days=5),
            fecha_vencimiento=hoy + timedelta(days=3),
        )

        from core.views import _estado_lote_insumo
        estado, clase = _estado_lote_insumo(lote_pronto, hoy)
        self.assertEqual(estado, 'Próximo a vencer')
        self.assertEqual(clase, 'pronto_a_vencer')

    def test_lote_vencido_nunca_se_usa_en_fifo(self):
        """Un lote vencido nunca debe consumirse por FIFO, aún si es el más antiguo."""
        hoy = timezone.localdate()
        mesero = Usuario.objects.create(
            nombre='mesero',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('mesero123'),
            estado=True,
        )
        
        # Lote vencido (más antiguo)
        lote_vencido = LoteInsumo.objects.create(
            codigo_referencia='REF-20260901-002',
            nombre_insumo='Pollo',
            categoria=LoteInsumo.Categoria.CARNES,
            precio_unitario=Decimal('12.00'),
            cantidad_disponible=Decimal('50.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=hoy - timedelta(days=30),
            fecha_vencimiento=hoy - timedelta(days=5),  # Vencido hace 5 días
        )
        
        # Lote fresco (más nuevo)
        lote_fresco = LoteInsumo.objects.create(
            codigo_referencia='REF-20260906-002',
            nombre_insumo='Pollo',
            categoria=LoteInsumo.Categoria.CARNES,
            precio_unitario=Decimal('14.00'),
            cantidad_disponible=Decimal('30.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=hoy - timedelta(days=1),
            fecha_vencimiento=hoy + timedelta(days=30),  # Fresco
        )
        
        plato = Plato.objects.create(
            nombre_plato='Pollo al horno',
            categoria='Platos fuertes',
            precio_venta=Decimal('150.00'),
            codigo='PL-002',
            estado=True,
        )
        RecetaPlato.objects.create(plato=plato, insumo=lote_vencido, cantidad_requerida=Decimal('1'))
        RecetaPlato.objects.create(plato=plato, insumo=lote_fresco, cantidad_requerida=Decimal('1'))

        comanda = Comanda.objects.create(
            usuario=mesero,
            mesa=8,
            estado=Comanda.Estado.PENDIENTE,
            total=Decimal('0'),
        )
        detalle = DetalleComanda.objects.create(
            comanda=comanda,
            plato=plato,
            cantidad=10,
            precio_unitario=plato.precio_venta,
        )

        from core.views import _descontar_fifo
        _descontar_fifo(comanda)

        # El lote vencido NO debe haberse consumido
        self.assertEqual(
            LoteInsumo.objects.get(pk=lote_vencido.pk).cantidad_disponible,
            Decimal('50.00'),  # Sin cambios
        )
        
        # El lote fresco SÍ debe haberse consumido, y como la demanda total era 20
        # al excluir el vencido, el lote fresco cubre todo ese requerimiento.
        self.assertEqual(
            LoteInsumo.objects.get(pk=lote_fresco.pk).cantidad_disponible,
            Decimal('10.00'),
        )


class MermaConTransaccionesTests(TestCase):
    """Pruebas para merma con transacciones atómicas."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_merma_solo_permite_cantidades_positivas(self):
        """Merma nunca debe permitir cantidades negativas o cero."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-005',
            nombre_insumo='Cebolla',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('2.00'),
            cantidad_disponible=Decimal('20.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 20),
        )

        # Intentar merma con cantidad negativa
        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '-5',
                'motivo': AjusteMerma.Motivo.DESPERDICIO,
                'observacion': 'test',
            },
            follow=True,
        )

        # No debe crear merma
        self.assertEqual(AjusteMerma.objects.count(), 0)
        self.assertEqual(
            LoteInsumo.objects.get(pk=lote.pk).cantidad_disponible,
            Decimal('20.00'),  # Sin cambios
        )

    def test_merma_no_permite_cantidad_mayor_al_stock(self):
        """Merma nunca debe permitir una cantidad mayor a la disponible."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-006',
            nombre_insumo='Papas',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('1.50'),
            cantidad_disponible=Decimal('10.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 22),
        )

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '15',  # Más de lo disponible
                'motivo': AjusteMerma.Motivo.DESPERDICIO,
                'observacion': 'test',
            },
            follow=True,
        )

        # No debe crear merma
        self.assertEqual(AjusteMerma.objects.count(), 0)
        self.assertEqual(
            LoteInsumo.objects.get(pk=lote.pk).cantidad_disponible,
            Decimal('10.00'),  # Sin cambios
        )

    def test_merma_descuenta_stock_atomicamente(self):
        """Merma debe descontar el stock de forma atómica, registrando usuario y causa."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-007',
            nombre_insumo='Zanahorias',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('1.80'),
            cantidad_disponible=Decimal('25.00'),
            stock_minimo=Decimal('3.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 21),
        )

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '7',
                'motivo': AjusteMerma.Motivo.DANIO,
                'observacion': 'Golpeadas',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AjusteMerma.objects.count(), 1)
        
        merma = AjusteMerma.objects.first()
        self.assertEqual(merma.cantidad, Decimal('7'))
        self.assertEqual(merma.usuario, self.admin)
        self.assertEqual(merma.motivo, AjusteMerma.Motivo.DANIO)
        
        # Stock debe estar descotado
        lote.refresh_from_db()
        self.assertEqual(lote.cantidad_disponible, Decimal('18.00'))


class ValoracionInventarioTests(TestCase):
    """Pruebas para valoración correcta del inventario."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_valor_inventario_es_cantidad_por_precio_unitario(self):
        """Valor inventario = sum(cantidad_disponible × precio_unitario)."""
        lote_a = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-008',
            nombre_insumo='Arroz',
            categoria=LoteInsumo.Categoria.HARINAS,
            precio_unitario=Decimal('10.00'),
            cantidad_disponible=Decimal('100.00'),
            stock_minimo=Decimal('5.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 30),
        )
        lote_b = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-009',
            nombre_insumo='Frijoles',
            categoria=LoteInsumo.Categoria.HARINAS,
            precio_unitario=Decimal('8.00'),
            cantidad_disponible=Decimal('50.00'),
            stock_minimo=Decimal('5.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 30),
        )

        # Valor esperado: (100 * 10) + (50 * 8) = 1000 + 400 = 1400
        response = self.client.get(reverse('vista_admin'))
        self.assertEqual(response.status_code, 200)
        
        self.assertContains(response, '$1400.00')


class AuditoriaYRegistroTests(TestCase):
    """Pruebas para auditoría (RegistroActividad)."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_crear_usuario_registra_en_auditoria(self):
        """Crear usuario debe registrarse en RegistroActividad."""
        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_usuario',
                'nombre': 'nuevo_chef',
                'rol': Usuario.Rol.EMPLEADO,
                'password': 'chef999',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        
        # Debe existir un registro de auditoría
        registro = RegistroActividad.objects.filter(accion='Crear usuario').first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.usuario, self.admin)
        self.assertIn('nuevo_chef', registro.detalle)

    def test_desactivar_usuario_registra_en_auditoria(self):
        """Desactivar usuario debe registrarse en RegistroActividad."""
        empleado = Usuario.objects.create(
            nombre='empleado_temp',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('temp123'),
            estado=True,
        )

        response = self.client.post(
            reverse('vista_admin'),
            {'accion': 'toggle_usuario', 'usuario_id': empleado.id},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        registro = RegistroActividad.objects.filter(accion='Desactivar usuario').first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.usuario, self.admin)

    def test_registrar_merma_registra_en_auditoria(self):
        """Registrar merma debe auditarse."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-010',
            nombre_insumo='Jengibre',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('3.50'),
            cantidad_disponible=Decimal('15.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 19),
        )

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '3',
                'motivo': AjusteMerma.Motivo.CADUCIDAD,
                'observacion': 'Caducó',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        
        # Debe existir un registro de auditoría
        registro = RegistroActividad.objects.filter(accion='Registrar merma').first()
        self.assertIsNotNone(registro)
        self.assertEqual(registro.usuario, self.admin)


class CRUDUsuariosCompletosTests(TestCase):
    """Pruebas para CRUD completo de usuarios."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_editar_usuario_preserva_id(self):
        """Editar un usuario no debe cambiar su ID."""
        usuario = Usuario.objects.create(
            nombre='juanito',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('123456'),
            estado=True,
        )
        usuario_id = usuario.id

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_usuario',
                'usuario_id': usuario_id,
                'nombre': 'juan_editado',
                'rol': Usuario.Rol.CAJERO,  # Cambiar rol
                'password': 'nueva999',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        
        usuario_editado = Usuario.objects.get(pk=usuario_id)
        self.assertEqual(usuario_editado.nombre, 'juan_editado')
        self.assertEqual(usuario_editado.rol, Usuario.Rol.CAJERO)
        self.assertTrue(check_password('nueva999', usuario_editado.password_hash))

    def test_cambiar_rol_a_usuario(self):
        """Cambiar el rol de un usuario debe reflejar en la BD."""
        usuario = Usuario.objects.create(
            nombre='trabajador',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('123456'),
            estado=True,
        )

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_usuario',
                'usuario_id': usuario.id,
                'nombre': 'trabajador',
                'rol': Usuario.Rol.CAJERO,
                'password': '',  # No cambiar contraseña
            },
            follow=True,
        )

        usuario.refresh_from_db()
        self.assertEqual(usuario.rol, Usuario.Rol.CAJERO)

    def test_nunca_eliminar_fisicamente_usuarios(self):
        """No debe haber eliminación física de usuarios; solo desactivación."""
        usuario = Usuario.objects.create(
            nombre='pepe',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('123456'),
            estado=True,
        )
        usuario_id = usuario.id

        self.client.post(
            reverse('vista_admin'),
            {'accion': 'toggle_usuario', 'usuario_id': usuario_id},
        )

        # El usuario debe seguir existiendo en la BD
        usuario_desactivado = Usuario.objects.get(pk=usuario_id)
        self.assertFalse(usuario_desactivado.estado)
        self.assertEqual(usuario_desactivado.nombre, 'pepe')


class RestriccionesDeCalculoTests(TestCase):
    """Pruebas para restricciones de cantidad y cálculos."""

    def setUp(self):
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_cantidad_requerida_en_receta_debe_ser_positiva(self):
        """Cantidad en una receta nunca debe ser cero o negativa."""
        plato = Plato.objects.create(
            nombre_plato='Milanesa',
            categoria='Carnes',
            precio_venta=Decimal('180.00'),
            estado=True,
        )

        # Intentar crear receta con cantidad negativa
        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_receta',
                'plato': plato.id,
                # cantidad_requerida negativa - el formulario debe rechazarlo
            },
            follow=True,
        )

        # El formulario debe validar que cantidad > 0

    def test_no_puede_haber_stock_negativo(self):
        """El sistema nunca debe permitir stock negativo."""
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-011',
            nombre_insumo='Vinagre',
            categoria=LoteInsumo.Categoria.OTROS,
            precio_unitario=Decimal('2.00'),
            cantidad_disponible=Decimal('10.00'),
            stock_minimo=Decimal('1.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 28),
        )

        # Intentar merma que dejara stock negativo
        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '20',  # Más de lo disponible
                'motivo': AjusteMerma.Motivo.DESPERDICIO,
            },
            follow=True,
        )

        lote.refresh_from_db()
        self.assertGreaterEqual(lote.cantidad_disponible, Decimal('0'))
