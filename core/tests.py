from datetime import date
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import AjusteMerma, Comanda, ConsumoInsumo, DetalleComanda, Factura, LoteInsumo, Plato, RecetaPlato, RegistroSesion, Usuario


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
        self.session['usuario_id'] = self.admin.id
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


class ComandaMesaFlowTests(TestCase):
    def setUp(self):
        self.mesero = Usuario.objects.create(
            nombre='mesero',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('mesero123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.EMPLEADO
        self.session['usuario_id'] = self.mesero.id
        self.session.save()

        self.plato = Plato.objects.create(
            nombre_plato='Hamburguesa Especial',
            categoria='Hamburguesas',
            precio_venta=Decimal('180.00'),
            codigo='1025',
            estado=True,
        )
        self.gaseosa = Plato.objects.create(
            nombre_plato='Gaseosa',
            categoria='Bebidas',
            precio_venta=Decimal('50.00'),
            codigo='2001',
            estado=True,
        )

    def test_crea_y_reutiliza_comanda_activa_por_mesa(self):
        response = self.client.post(
            reverse('vista_mesero'),
            {'accion': 'agregar', 'mesa': '5', 'plato_id': self.plato.id, 'cantidad': '2'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comanda.objects.filter(mesa=5).count(), 1)

        self.client.post(
            reverse('vista_mesero'),
            {'accion': 'agregar', 'mesa': '5', 'plato_id': self.gaseosa.id, 'cantidad': '1'},
        )

        comanda = Comanda.objects.get(mesa=5)
        self.assertEqual(comanda.detalles.count(), 2)
        self.assertEqual(comanda.total, Decimal('410.00'))

    def test_no_crea_dos_comandas_activas_para_la_misma_mesa(self):
        comanda_1 = Comanda.objects.create(
            usuario=self.mesero,
            mesa=7,
            estado=Comanda.Estado.PENDIENTE,
            total=Decimal('100.00'),
        )
        DetalleComanda.objects.create(
            comanda=comanda_1,
            plato=self.plato,
            cantidad=1,
            precio_unitario=self.plato.precio_venta,
            comentario='Mesa 7',
            lote_descontado=self.plato.receta.first().insumo if self.plato.receta.exists() else None,
        )

        self.client.post(
            reverse('vista_mesero'),
            {'accion': 'agregar', 'mesa': '7', 'plato_id': self.gaseosa.id, 'cantidad': '1'},
        )

        self.assertEqual(Comanda.objects.filter(mesa=7, estado__in=[Comanda.Estado.PENDIENTE, Comanda.Estado.ENVIADA]).count(), 1)

    def test_busca_plato_por_codigo_y_calcula_total(self):
        response = self.client.get(reverse('vista_mesero'), {'mesa': '3', 'codigo': '2001'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gaseosa')
        self.assertContains(response, '2001')

    def test_eliminar_ultimo_plato_libera_la_mesa(self):
        self.client.post(
            reverse('vista_mesero'),
            {'accion': 'agregar', 'mesa': '6', 'plato_id': self.plato.id, 'cantidad': '1'},
        )
        comanda = Comanda.objects.get(mesa=6)
        detalle = comanda.detalles.get()

        response = self.client.post(
            reverse('vista_mesero'),
            {'accion': 'eliminar', 'mesa': '6', 'detalle_id': detalle.id},
            follow=True,
        )

        comanda.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(comanda.estado, Comanda.Estado.CANCELADA)
        self.assertEqual(comanda.total, Decimal('0.00'))
        self.assertFalse(comanda.detalles.exists())
        self.assertFalse(
            Comanda.objects.filter(
                mesa=6,
                estado__in=[Comanda.Estado.PENDIENTE, Comanda.Estado.ENVIADA],
            ).exists()
        )


class InventarioTransaccionalTests(TestCase):
    def setUp(self):
        self.mesero = Usuario.objects.create(
            nombre='mesero',
            rol=Usuario.Rol.EMPLEADO,
            password_hash=make_password('mesero123'),
            estado=True,
        )
        self.admin = Usuario.objects.create(
            nombre='admin',
            rol=Usuario.Rol.ADMIN,
            password_hash=make_password('admin123'),
            estado=True,
        )
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.EMPLEADO
        self.session['usuario_id'] = self.mesero.id
        self.session.save()

    def test_fifo_consumo_usa_dos_lotes_en_orden(self):
        lote_a = LoteInsumo.objects.create(
            codigo_referencia='REF-20260901-001',
            nombre_insumo='Pollo',
            categoria=LoteInsumo.Categoria.CARNES,
            precio_unitario=Decimal('12.00'),
            cantidad_disponible=Decimal('10.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso='2026-09-01',
            fecha_vencimiento='2026-09-30',
        )
        lote_b = LoteInsumo.objects.create(
            codigo_referencia='REF-20260902-001',
            nombre_insumo='Pollo',
            categoria=LoteInsumo.Categoria.CARNES,
            precio_unitario=Decimal('14.00'),
            cantidad_disponible=Decimal('20.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso='2026-09-02',
            fecha_vencimiento='2026-10-02',
        )

        plato = Plato.objects.create(
            nombre_plato='Pollo al horno',
            categoria='Platos fuertes',
            precio_venta=Decimal('150.00'),
            codigo='PL-001',
            estado=True,
        )
        RecetaPlato.objects.create(plato=plato, insumo=lote_a, cantidad_requerida=Decimal('1'))

        comanda = Comanda.objects.create(usuario=self.mesero, mesa=8, estado=Comanda.Estado.PENDIENTE, total=Decimal('0'))
        detalle = DetalleComanda.objects.create(comanda=comanda, plato=plato, cantidad=15, precio_unitario=plato.precio_venta)

        from core.views import _descontar_fifo
        _descontar_fifo(comanda)

        self.assertEqual(ConsumoInsumo.objects.filter(detalle_comanda=detalle).count(), 2)
        self.assertEqual(LoteInsumo.objects.get(pk=lote_a.pk).cantidad_disponible, Decimal('0'))
        self.assertEqual(LoteInsumo.objects.get(pk=lote_b.pk).cantidad_disponible, Decimal('15'))

    def test_stock_insuficiente_hace_rollback_total(self):
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260901-002',
            nombre_insumo='Arroz',
            categoria=LoteInsumo.Categoria.HARINAS,
            precio_unitario=Decimal('5.00'),
            cantidad_disponible=Decimal('4.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso='2026-09-01',
            fecha_vencimiento='2026-09-30',
        )
        plato = Plato.objects.create(
            nombre_plato='Arroz con pollo',
            categoria='Platos fuertes',
            precio_venta=Decimal('120.00'),
            codigo='AR-001',
            estado=True,
        )
        RecetaPlato.objects.create(plato=plato, insumo=lote, cantidad_requerida=Decimal('1'))

        comanda = Comanda.objects.create(usuario=self.mesero, mesa=9, estado=Comanda.Estado.PENDIENTE, total=Decimal('0'))
        DetalleComanda.objects.create(comanda=comanda, plato=plato, cantidad=5, precio_unitario=plato.precio_venta)

        from core.views import _descontar_fifo
        with self.assertRaises(ValueError):
            _descontar_fifo(comanda)

        self.assertEqual(LoteInsumo.objects.get(pk=lote.pk).cantidad_disponible, Decimal('4.00'))
        self.assertEqual(ConsumoInsumo.objects.filter(detalle_comanda__comanda=comanda).count(), 0)

    def test_cancelacion_reversa_consumos_anteriores(self):
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260901-003',
            nombre_insumo='Salsa',
            categoria=LoteInsumo.Categoria.OTROS,
            precio_unitario=Decimal('3.00'),
            cantidad_disponible=Decimal('12.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso='2026-09-01',
            fecha_vencimiento='2026-09-30',
        )
        plato = Plato.objects.create(
            nombre_plato='Pasta',
            categoria='Platos fuertes',
            precio_venta=Decimal('90.00'),
            codigo='PA-001',
            estado=True,
        )
        RecetaPlato.objects.create(plato=plato, insumo=lote, cantidad_requerida=Decimal('1'))

        comanda = Comanda.objects.create(usuario=self.mesero, mesa=10, estado=Comanda.Estado.ENVIADA, total=Decimal('90.00'))
        detalle = DetalleComanda.objects.create(comanda=comanda, plato=plato, cantidad=3, precio_unitario=plato.precio_venta)

        from core.views import _descontar_fifo, _revertir_consumos_comanda
        _descontar_fifo(comanda)
        _revertir_consumos_comanda(comanda)

        self.assertEqual(LoteInsumo.objects.get(pk=lote.pk).cantidad_disponible, Decimal('12.00'))
        self.assertEqual(ConsumoInsumo.objects.filter(detalle_comanda=detalle).count(), 0)

    def test_logout_registra_sesion_y_cierra_sesion(self):
        self.client.login = lambda *args, **kwargs: True
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroSesion.objects.filter(tipo_evento=RegistroSesion.TipoEvento.LOGOUT).count() >= 1, True)

    def test_generacion_ref_automatico_usa_formato(self):
        lote = LoteInsumo.objects.create(
            codigo_referencia='',
            nombre_insumo='Queso',
            categoria=LoteInsumo.Categoria.LACTEOS,
            precio_unitario=Decimal('8.00'),
            cantidad_disponible=Decimal('8.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=date(2026, 9, 1),
            fecha_vencimiento=date(2026, 9, 28),
        )
        self.assertRegex(lote.codigo_referencia, r'^REF-20260901-\d{3}$')


class AdminPermissionsAndUsersTests(TestCase):
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
        self.session = self.client.session
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session['usuario_id'] = self.admin.id
        self.session.save()

    def test_admin_puede_crear_usuario(self):
        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_usuario',
                'nombre': 'chef',
                'rol': Usuario.Rol.EMPLEADO,
                'estado': 'on',
                'password': 'chef123',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Usuario.objects.filter(nombre='chef', rol=Usuario.Rol.EMPLEADO).exists())

    def test_admin_no_se_puede_inactivar_a_si_mismo(self):
        response = self.client.post(
            reverse('vista_admin'),
            {'accion': 'toggle_usuario', 'usuario_id': self.admin.id},
            follow=True,
        )

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.estado)
        self.assertContains(response, 'No puedes desactivar')

    def test_mesero_no_puede_registrar_merma(self):
        lote = LoteInsumo.objects.create(
            codigo_referencia='REF-20260905-001',
            nombre_insumo='Tomate',
            categoria=LoteInsumo.Categoria.VERDURAS,
            precio_unitario=Decimal('3.00'),
            cantidad_disponible=Decimal('10.00'),
            stock_minimo=Decimal('2.00'),
            fecha_ingreso=date(2026, 9, 5),
            fecha_vencimiento=date(2026, 9, 25),
        )
        self.session['rol'] = Usuario.Rol.EMPLEADO
        self.session.save()

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_merma',
                'lote': lote.id,
                'cantidad': '2',
                'motivo': AjusteMerma.Motivo.DESPERDICIO,
                'observacion': 'prueba',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AjusteMerma.objects.count(), 0)

    def test_cajero_no_puede_crear_usuarios(self):
        self.session['rol'] = Usuario.Rol.CAJERO
        self.session['usuario_id'] = self.cajero.id
        self.session.save()

        response = self.client.post(
            reverse('vista_admin'),
            {
                'accion': 'guardar_usuario',
                'nombre': 'otro',
                'rol': Usuario.Rol.EMPLEADO,
                'estado': 'on',
                'password': 'otro123',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Usuario.objects.filter(nombre='otro').exists())


class FacturacionViewTests(TestCase):
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

    def test_vista_facturacion_carga(self):
        response = self.client.get(reverse('vista_facturacion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Facturación')
        self.assertContains(response, 'Facturas recientes')

    def test_detalle_factura_carga(self):
        factura = Factura.objects.create(
            usuario=self.admin,
            cliente='Cliente prueba',
            total=Decimal('325.50'),
            metodo_pago='efectivo',
            estado='pagada',
        )

        response = self.client.get(reverse('detalle_factura', args=[factura.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Factura')
        self.assertContains(response, '325.50')

    def test_vista_facturacion_tiene_navegacion_hacia_inventario(self):
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session.save()

        response = self.client.get(reverse('vista_facturacion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('vista_admin'))
        self.assertContains(response, reverse('inicio'))

    def test_vista_cajero_carga(self):
        self.session['rol'] = 'cajero'
        self.session.save()

        response = self.client.get(reverse('vista_cajero'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cajero')

    def test_pagar_factura_libera_la_mesa_en_comandas(self):
        self.session['rol'] = Usuario.Rol.CAJERO
        self.session.save()
        comanda = Comanda.objects.create(
            usuario=self.admin,
            mesa=8,
            estado=Comanda.Estado.ENVIADA,
            total=Decimal('100.00'),
        )
        factura = Factura.objects.create(
            usuario=self.admin,
            cliente='Mesa 8',
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
            estado=Factura.Estado.PENDIENTE,
            observacion=f'Comanda #{comanda.id}',
        )

        response = self.client.post(
            reverse('vista_cajero'),
            {'accion': 'pagar', 'factura_id': factura.id},
        )

        comanda.refresh_from_db()
        factura.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(factura.estado, Factura.Estado.PAGADA)
        self.assertEqual(comanda.estado, Comanda.Estado.PAGADA)
        self.assertFalse(
            Comanda.objects.filter(
                mesa=8,
                estado__in=[Comanda.Estado.PENDIENTE, Comanda.Estado.ENVIADA],
            ).exists()
        )

    def test_admin_puede_acceder_a_vista_mesero(self):
        self.session['rol'] = Usuario.Rol.ADMIN
        self.session.save()

        response = self.client.get(reverse('vista_mesero'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista de mesero')
