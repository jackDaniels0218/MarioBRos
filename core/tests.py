from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from django.urls import reverse

from core.models import Comanda, DetalleComanda, Factura, LoteInsumo, Plato, RecetaPlato, Usuario


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
