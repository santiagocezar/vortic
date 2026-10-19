from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Usuario


class EsJefeOSoloLectura(BasePermission):
    """
    HU-06: el rol Técnico tiene una vista de solo lectura de todo lo que
    no sea su propio trabajo operativo del día (ver taller/permissions.py
    para las excepciones puntuales de OrdenTrabajo). Cualquier usuario
    autenticado puede leer (GET); crear/editar/eliminar requiere rol Jefe
    de Taller.
    """

    def has_permission(self, request, view):
        # RNF-10: sin sesión activa no se puede ver ningún dato — el chequeo
        # de autenticación va PRIMERO y aplica también a los métodos
        # seguros (GET). Antes de este fix, el `if SAFE_METHODS: return True`
        # dejaba pasar lecturas sin loguearse en cuanto esta clase se usaba
        # como único permission_classes del viewset (reemplaza el
        # IsAuthenticated global de settings.py en vez de sumarse a él).
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.rol == Usuario.ROL_JEFE


class EsJefe(BasePermission):
    """
    Gestión de usuarios (alta de técnicos, cambio de contraseña, baja
    lógica): a diferencia de EsJefeOSoloLectura, acá ni siquiera el
    Técnico puede leer — es información administrativa del taller, no
    parte de su trabajo operativo del día (HU-06).
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.rol == Usuario.ROL_JEFE)
