from django.conf import settings
from django.urls import path
from rest_framework.routers import DefaultRouter
from .motor import OrdenesActivasMotor, PrioridadesMotor, RespaldoMotor
from .views import (
    EquipoViewSet, RepuestoViewSet, OrdenTrabajoViewSet,
    ProveedorViewSet, PrecioProveedorViewSet,
)

router = DefaultRouter()
router.register('equipos', EquipoViewSet, basename='equipo')
router.register('ordenes', OrdenTrabajoViewSet, basename='orden')

# Stock y proveedores se pueden apagar con FEATURE_STOCK_PROVEEDORES=False
# (config/settings.py). Por defecto están activos.
if settings.FEATURE_STOCK_PROVEEDORES:
    router.register('repuestos', RepuestoViewSet, basename='repuesto')
    router.register('proveedores', ProveedorViewSet, basename='proveedor')
    router.register('precios-proveedor', PrecioProveedorViewSet, basename='precio-proveedor')

# Endpoints del motor de priorización (n8n), ver taller/motor.py.
urlpatterns = router.urls + [
    path('motor/ordenes-activas/', OrdenesActivasMotor.as_view(), name='motor-ordenes-activas'),
    path('motor/prioridades/', PrioridadesMotor.as_view(), name='motor-prioridades'),
    path('motor/respaldo/', RespaldoMotor.as_view(), name='motor-respaldo'),
]
