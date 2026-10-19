"""
Pruebas automatizadas del backend. Cada clase indica el caso de prueba del
informe (sección 14) que cubre. Se ejecutan con:

    python manage.py test

Las señales de repriorización corren en transaction.on_commit; dentro de un
TestCase la transacción nunca se confirma, por eso las pruebas que dependen
del recálculo usan captureOnCommitCallbacks(execute=True).
"""
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from clientes.models import Cliente, numero_whatsapp
from usuarios.models import Usuario
from . import priorizacion
from .models import Equipo, OrdenRepuesto, OrdenTrabajo, Repuesto
from .serializers import OrdenTrabajoDetailSerializer

TOKEN = 'token-de-prueba'


class Base(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(razon_social='Agro Test', telefono='3564 123456')
        self.jefe = Usuario.objects.create_user('jefe', password='Clave.Segura1', rol=Usuario.ROL_JEFE)
        self.tecnico = Usuario.objects.create_user('tec', password='Clave.Segura1', rol=Usuario.ROL_TECNICO)
        self.api = APIClient()

    def orden(self, tipo='cilindro', criticidad=2, tiempo=3, costo=10000, estado='pendiente', dias=0):
        equipo = Equipo.objects.create(cliente=self.cliente, tipo_equipo=tipo)
        with self.captureOnCommitCallbacks(execute=True):
            o = OrdenTrabajo.objects.create(
                cliente=self.cliente, equipo=equipo, descripcion_falla='falla', criticidad=criticidad,
                tiempo_estimado=tiempo, costo_estimado=costo, estado=estado,
            )
        if dias:
            OrdenTrabajo.objects.filter(pk=o.pk).update(fecha_ingreso=timezone.now() - timedelta(days=dias))
            o.refresh_from_db()
        return o


# --- CP-01 a CP-04: regla de respaldo --------------------------------------

class ReglaRespaldoTests(Base):
    def test_cp01_criticidad_pesa_mas_que_todo(self):
        urgente = self.orden(criticidad=5, tiempo=10)
        rapida = self.orden(criticidad=2, tiempo=1, dias=5)
        self.assertGreater(priorizacion.puntaje_respaldo(urgente)[0], priorizacion.puntaje_respaldo(rapida)[0])

    def test_cp02_rapida_gana_con_igual_criticidad(self):
        lenta = self.orden(criticidad=3, tiempo=10)
        rapida = self.orden(criticidad=3, tiempo=1)
        self.assertGreater(priorizacion.puntaje_respaldo(rapida)[0], priorizacion.puntaje_respaldo(lenta)[0])

    def test_cp03_faltante_de_repuesto_baja_la_prioridad(self):
        con = self.orden(criticidad=3)
        sin = self.orden(criticidad=3)
        rep = Repuesto.objects.create(codigo='S1', descripcion='Sello', cantidad_actual=-1)
        OrdenRepuesto.objects.create(orden=sin, repuesto=rep, cantidad=2)
        self.assertGreater(priorizacion.puntaje_respaldo(con)[0], priorizacion.puntaje_respaldo(sin)[0])

    def test_cp04_puntaje_entre_0_y_100_y_justificado(self):
        o = self.orden(criticidad=5, tiempo=1, dias=30)
        puntaje, texto = priorizacion.puntaje_respaldo(o)
        self.assertLessEqual(puntaje, 100)
        self.assertIn('criticidad 5', texto)

    def test_alta_de_orden_queda_priorizada_sin_n8n(self):
        o = self.orden()
        o.refresh_from_db()
        self.assertIsNotNone(o.indice_prioridad)
        self.assertEqual(o.prioridad_origen, 'respaldo')

    def test_bloqueada_sale_del_orden_con_su_motivo(self):
        o = self.orden()
        self.api.force_authenticate(self.jefe)
        with self.captureOnCommitCallbacks(execute=True):
            self.api.post(f'/api/ordenes/{o.id}/cambiar_estado/', {'estado': 'bloqueado', 'motivo_bloqueo': 'falta sello'}, format='json')
        o.refresh_from_db()
        self.assertIsNone(o.indice_prioridad)
        self.assertEqual(o.justificacion_prioridad, 'Bloqueada: falta sello')


# --- CP-08: completar estimaciones después del alta ------------------------

class EstimacionPosteriorTests(Base):
    def test_cp08_orden_sin_estimacion_se_completa_despues(self):
        s = OrdenTrabajoDetailSerializer(data={'cliente': self.cliente.id, 'descripcion_falla': 'pierde aceite', 'criticidad': 5})
        self.assertTrue(s.is_valid(), s.errors)
        with self.captureOnCommitCallbacks(execute=True):
            orden = s.save()
        s2 = OrdenTrabajoDetailSerializer(orden, data={'costo_estimado': 45000, 'tiempo_estimado': 3}, partial=True)
        self.assertTrue(s2.is_valid(), s2.errors)
        with self.captureOnCommitCallbacks(execute=True):
            s2.save()
        orden.refresh_from_db()
        self.assertIsNotNone(orden.indice_prioridad)


# --- CP-07 y CP-09: validación de la orden ---------------------------------

class OrdenTrabajoValidacionTests(Base):
    def _datos(self, **extra):
        return {'cliente': self.cliente.id, 'descripcion_falla': 'x', 'criticidad': 3, **extra}

    def test_cp09_tiempo_estimado_cero_es_rechazado(self):
        s = OrdenTrabajoDetailSerializer(data=self._datos(tiempo_estimado=0, costo_estimado=500))
        self.assertFalse(s.is_valid())
        self.assertIn('tiempo_estimado', s.errors)

    def test_cp07_costo_estimado_negativo_es_rechazado(self):
        s = OrdenTrabajoDetailSerializer(data=self._datos(tiempo_estimado=2, costo_estimado=-500))
        self.assertFalse(s.is_valid())
        self.assertIn('costo_estimado', s.errors)


# --- CP-05, CP-06 y CP-15: teléfono y WhatsApp -----------------------------

class TelefonoWhatsappTests(Base):
    def test_cp06_telefono_sin_codigo_de_area_es_rechazado(self):
        from clientes.serializers import ClienteSerializer
        for malo in ('sin telefono', '123456'):
            s = ClienteSerializer(data={'razon_social': 'X', 'telefono': malo})
            self.assertFalse(s.is_valid(), malo)

    def test_cp05_telefono_duplicado_normalizado_es_rechazado(self):
        from clientes.serializers import ClienteSerializer
        Cliente.objects.create(razon_social='Original', telefono='351-412-3456')
        s = ClienteSerializer(data={'razon_social': 'Otra ficha', 'telefono': '3514123456'})
        self.assertFalse(s.is_valid())

    def test_formatos_argentinos_a_internacional(self):
        for entrada in ('3564 123456', '(03564) 15-123456', '+54 9 3564 123456', '54 3564 123456', '03564-123456'):
            self.assertEqual(numero_whatsapp(entrada), '5493564123456', entrada)
        self.assertEqual(numero_whatsapp('11 15 2345 6789'), '5491123456789')

    def test_cp15_aviso_arma_enlace_internacional_y_codificado(self):
        o = self.orden(tipo='motor', estado='terminado')
        self.api.force_authenticate(self.jefe)
        r = self.api.post(f'/api/ordenes/{o.id}/avisar_cliente/', {}, format='json')
        self.assertEqual(r.status_code, 200)
        url = r.json()['whatsapp_url']
        self.assertTrue(url.startswith('https://wa.me/5493564123456?text='))
        self.assertNotIn(' ', url)


# --- CP-10: reabrir una orden terminada ------------------------------------

class ReabrirOrdenTerminadaTests(Base):
    def test_cp10_reabrir_limpia_fecha_aviso_cliente(self):
        o = self.orden(estado='terminado')
        OrdenTrabajo.objects.filter(pk=o.pk).update(fecha_aviso_cliente=timezone.now())
        self.api.force_authenticate(self.jefe)
        r = self.api.post(f'/api/ordenes/{o.id}/cambiar_estado/', {'estado': 'en_curso'}, format='json')
        self.assertEqual(r.status_code, 200)
        o.refresh_from_db()
        self.assertIsNone(o.fecha_aviso_cliente)


# --- CP-12 a CP-14: roles, bloqueo y sesión --------------------------------

class PermisosTests(Base):
    def test_cp12_tecnico_no_crea_ni_avisa(self):
        o = self.orden(estado='terminado')
        self.api.force_authenticate(self.tecnico)
        self.assertEqual(self.api.post('/api/ordenes/', {'cliente': self.cliente.id, 'descripcion_falla': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.api.post(f'/api/ordenes/{o.id}/avisar_cliente/', {}, format='json').status_code, 403)
        self.assertEqual(self.api.get('/api/usuarios/').status_code, 403)

    def test_cp13_bloqueo_exige_motivo(self):
        o = self.orden()
        self.api.force_authenticate(self.tecnico)
        self.assertEqual(self.api.post(f'/api/ordenes/{o.id}/cambiar_estado/', {'estado': 'bloqueado'}, format='json').status_code, 400)

    def test_cp14_sin_token_no_hay_datos(self):
        self.assertEqual(self.api.get('/api/ordenes/').status_code, 401)


# --- CP-16 y CP-17: motor de priorización (endpoints que usa n8n) ----------

@override_settings(MOTOR_TOKEN=TOKEN)
class MotorTests(Base):
    def motor(self, metodo, ruta, datos=None, token=TOKEN):
        return getattr(self.api, metodo)(f'/api/motor/{ruta}/', datos, format='json', HTTP_X_MOTOR_TOKEN=token)

    def test_token_obligatorio(self):
        self.assertEqual(self.motor('get', 'ordenes-activas', token='otro').status_code, 403)
        with override_settings(MOTOR_TOKEN=''):
            self.assertEqual(self.motor('get', 'ordenes-activas', token='').status_code, 403)

    def test_datos_anonimizados_y_solo_activas(self):
        a = self.orden()
        self.orden(estado='terminado')
        datos = self.motor('get', 'ordenes-activas').json()
        self.assertEqual([o['orden_id'] for o in datos['ordenes']], [a.id])
        texto = str(datos)
        self.assertNotIn('Agro Test', texto)
        self.assertNotIn('123456', texto)
        self.assertTrue(datos['reglas'])

    def test_cp16_guarda_lo_que_decide_la_ia(self):
        a, b = self.orden(), self.orden()
        r = self.motor('post', 'prioridades', {'resultados': [
            {'orden_id': a.id, 'puntaje': 90, 'justificacion': 'Urgente y rápida.'},
            {'orden_id': b.id, 'puntaje': 40, 'justificacion': 'Puede esperar.'},
        ]})
        self.assertEqual(r.json(), {'guardadas_ia': 2, 'completadas_con_respaldo': 0, 'ignoradas': 0})
        a.refresh_from_db()
        self.assertEqual((a.indice_prioridad, a.prioridad_origen, a.justificacion_prioridad), (90, 'ia', 'Urgente y rápida.'))

    def test_cp17_respuesta_incompleta_o_invalida_se_completa_con_respaldo(self):
        a, b, c = self.orden(), self.orden(), self.orden()
        r = self.motor('post', 'prioridades', {'resultados': [
            {'orden_id': a.id, 'puntaje': 80, 'justificacion': 'ok'},
            {'orden_id': b.id, 'puntaje': 150, 'justificacion': 'fuera de rango'},
            {'orden_id': 9999, 'puntaje': 50, 'justificacion': 'no existe'},
        ]}).json()
        self.assertEqual(r, {'guardadas_ia': 1, 'completadas_con_respaldo': 2, 'ignoradas': 2})
        for o in (b, c):
            o.refresh_from_db()
            self.assertEqual(o.prioridad_origen, 'respaldo')

    def test_resultados_que_no_son_lista(self):
        self.assertEqual(self.motor('post', 'prioridades', {'resultados': 'hola'}).status_code, 400)

    def test_respaldo_a_pedido(self):
        self.orden()
        self.assertEqual(self.motor('post', 'respaldo').json(), {'completadas_con_respaldo': 1})

    @override_settings(N8N_WEBHOOK_URL='http://n8n.local/webhook/vortic', N8N_WEBHOOK_SECRETO='s3')
    def test_alta_de_orden_avisa_a_n8n(self):
        with mock.patch('taller.priorizacion.threading.Thread') as hilo:
            self.orden()
        args = hilo.call_args.kwargs['args']
        self.assertEqual(args[0], 'http://n8n.local/webhook/vortic')
        self.assertEqual(args[1], 's3')
