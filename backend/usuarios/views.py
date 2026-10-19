from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Usuario
from .permissions import EsJefe
from .serializers import TokenObtainPairConRolSerializer, UsuarioSerializer


class TokenObtainPairConRolView(TokenObtainPairView):
    serializer_class = TokenObtainPairConRolSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    """Alta/edición de usuarios (Jefe de Taller) — ver UsuarioSerializer."""
    queryset = Usuario.objects.all().order_by('username')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, EsJefe]
    # Sin PUT (evita pisar campos no mandados por accidente). DELETE queda
    # habilitado pero perform_destroy lo redirige a baja lógica: `usuario`
    # es PROTECT en HistorialEstado/SesionHoras, así que un borrado físico
    # de alguien que ya tocó una orden fallaría igual — mejor desactivar
    # directamente (is_active=False, mismo criterio que Cliente.activo).
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])
