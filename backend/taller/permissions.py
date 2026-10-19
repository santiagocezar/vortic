from rest_framework.permissions import SAFE_METHODS, BasePermission

from usuarios.models import Usuario

# HU-06: el Técnico puede ver todo (GET) y, además, hacer su trabajo
# operativo del día sobre una orden ya cargada: cambiar su estado,
# registrar horas trabajadas y marcar repuestos usados. Crear/editar/
# eliminar la orden en sí, y avisar al cliente, quedan para el Jefe.
ACCIONES_TECNICO = {'cambiar_estado', 'registrar_repuesto', 'registrar_horas'}


class PuedeOperarOrden(BasePermission):
    def has_permission(self, request, view):
        # RNF-10: sin sesión activa no se puede ver ningún dato — igual que
        # en usuarios/permissions.py, el chequeo de autenticado va primero
        # y cubre también las lecturas (GET), no solo las escrituras.
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.user.rol == Usuario.ROL_JEFE:
            return True
        return getattr(view, 'action', None) in ACCIONES_TECNICO
