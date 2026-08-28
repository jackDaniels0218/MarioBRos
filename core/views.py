from django.contrib.auth.hashers import check_password
from django.shortcuts import redirect, render

from .models import RegistroSesion, Usuario


def iniciar_sesion(request):
	error = None

	if request.method == 'POST':
		nombre = request.POST.get('usuario', '').strip()
		password = request.POST.get('password', '')
		rol = request.POST.get('rol', '')
		usuario = Usuario.objects.filter(nombre=nombre, estado=True).first()

		if usuario and usuario.rol == rol and check_password(password, usuario.password_hash):
			request.session['usuario_id'] = usuario.id
			request.session['rol'] = usuario.rol
			RegistroSesion.objects.create(
				usuario=usuario,
				tipo_evento=RegistroSesion.TipoEvento.LOGIN,
				ip_address=request.META.get('REMOTE_ADDR') or '0.0.0.0',
			)
			return redirect('vista_admin' if rol == Usuario.Rol.ADMIN else 'vista_mesero')

		error = 'Usuario, contraseña o rol incorrecto.'

	return render(request, 'IniciarSesion.html', {'error': error})


def vista_admin(request):
	if request.session.get('rol') != Usuario.Rol.ADMIN:
		return redirect('iniciar_sesion')
	return render(request, 'Inventario.html')


def vista_mesero(request):
	if request.session.get('rol') != Usuario.Rol.EMPLEADO:
		return redirect('iniciar_sesion')
	return render(request, 'Comandas.html')

