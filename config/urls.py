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
    path('logout/', views.logout_view, name='logout'),
    path('login/<str:rol>/', views.iniciar_sesion, name='iniciar_sesion_rol'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin/inicio/', views.vista_admin, name='vista_admin'),
    path('admin/panel/', views.vista_admin, name='panel_admin'),
    path('admin/usuarios/', views.usuarios, name='usuarios'),
    path('admin/lotes/', views.lotes, name='lotes'),
    path('admin/platos/', views.platos, name='platos'),
    path('admin/recetas/', views.recetas, name='recetas'),
    path('admin/reportes/<str:formato>/', views.reporte_admin_exportar, name='reporte_admin_exportar'),
    path('menu/', views.vista_menu, name='vista_menu'),
    path('mesero/inicio/', views.vista_mesero, name='vista_mesero'),
    path('cajero/inicio/', views.vista_cajero, name='vista_cajero'),
    path('facturacion/', views.vista_facturacion, name='vista_facturacion'),
    path('factura/<int:factura_id>/', views.detalle_factura, name='detalle_factura'),
    path('reportes/', views.reportes, name='reportes'),
    path('reportes/excel/', views.reporte_excel, name='reporte_excel'),
    path('reportes/pdf/', views.reporte_pdf, name='reporte_pdf'),
    path('api/resumen/', views.api_resumen, name='api_resumen'),
    path('admin/', admin.site.urls),
]
