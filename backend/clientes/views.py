from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from usuarios.permissions import EsJefeOSoloLectura
from .models import Cliente
from .serializers import ClienteSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    """
    CRUD de clientes. Soporta ?search=<texto> sobre razón social o
    teléfono, usado por HU-02 (sugerir clientes existentes) y
    HU-10/CU-06 (buscar historial de un cliente).

    HU-06: alta/edición/baja de clientes es solo del Jefe de Taller; el
    Técnico puede consultar (GET) pero no modificar.
    """
    queryset = Cliente.objects.filter(activo=True)
    serializer_class = ClienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['razon_social', 'telefono']
    # IsAuthenticated de más (defensa en profundidad): EsJefeOSoloLectura ya
    # exige sesión activa, pero así ninguna viewset de acá depende
    # únicamente de esa clase para RNF-10.
    permission_classes = [IsAuthenticated, EsJefeOSoloLectura]

    def perform_destroy(self, instance):
        # Baja lógica: nunca eliminar físicamente (preserva historial de órdenes)
        instance.activo = False
        instance.save()
