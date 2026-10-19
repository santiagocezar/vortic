"""
Endpoints que usa el motor de priorización (flujo de n8n). No los usa el
frontend. Se autentican con un token de servicio (cabecera X-Motor-Token)
en vez del login JWT, porque n8n es un sistema, no una persona.

GET  /api/motor/ordenes-activas/  -> reglas del taller + órdenes activas anonimizadas
POST /api/motor/prioridades/      -> guarda lo que decidió la IA
POST /api/motor/respaldo/         -> aplica la regla fija (si la IA falló)
"""
import hmac

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .priorizacion import ResultadoInvalido, aplicar_respaldo, datos_para_motor, guardar_resultados


class EsMotorPriorizacion(BasePermission):
    message = 'Token del motor de priorización inválido o no configurado.'

    def has_permission(self, request, view):
        esperado = getattr(settings, 'MOTOR_TOKEN', '')
        recibido = request.headers.get('X-Motor-Token', '')
        # Sin token configurado en el servidor, nadie entra.
        return bool(esperado) and hmac.compare_digest(esperado, recibido)


class _MotorView(APIView):
    authentication_classes = []  # no usa JWT: se valida el token de servicio
    permission_classes = [EsMotorPriorizacion]


class OrdenesActivasMotor(_MotorView):
    def get(self, request):
        return Response(datos_para_motor())


class PrioridadesMotor(_MotorView):
    def post(self, request):
        try:
            resumen = guardar_resultados(request.data.get('resultados'))
        except ResultadoInvalido as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resumen)


class RespaldoMotor(_MotorView):
    def post(self, request):
        return Response({'completadas_con_respaldo': aplicar_respaldo()})
