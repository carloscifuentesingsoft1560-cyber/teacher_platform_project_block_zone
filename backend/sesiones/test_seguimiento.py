from uuid import uuid4
from unittest.mock import patch
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario, PertenenciaRol
from . import tests as dominio
from .models import SeguimientoPedagogico, EventoSesion


class SeguimientoInformes(TestCase):
    @classmethod
    def setUpTestData(cls):
        dominio.DominioSesiones.setUpTestData.__func__(cls)
        cls.coordinador = Usuario.objects.create_user(username='coordinacion-e', rol='coordinador')

    crear = dominio.DominioSesiones.crear
    plan = dominio.DominioSesiones.plan
    comando = dominio.DominioSesiones.comando

    def setUp(self):
        self.sesion = self.plan(self.crear())
        self.cliente = APIClient()
        self.cliente.default_format = 'json'
        self.cliente.force_authenticate(self.coordinador)
        self.ruta = f'/api/sesiones/{self.sesion.pk}/seguimiento/'

    def entrada(self):
        self.sesion.refresh_from_db()
        return dict(version=self.sesion.version, clave=str(uuid4()), comentario='Observación docente', recomendaciones='Revisar secuencia')

    def test_historial_idempotencia_conflictos_e_inmutabilidad(self):
        entrada = self.entrada()
        self.assertEqual(self.cliente.post(self.ruta, entrada).status_code, 200)
        self.assertEqual(self.cliente.post(self.ruta, entrada).status_code, 200)
        self.assertEqual(SeguimientoPedagogico.objects.count(), 1)
        self.assertEqual(self.cliente.post(self.ruta, dict(entrada, comentario='Distinto')).status_code, 409)
        self.assertEqual(self.cliente.post(self.ruta, dict(entrada, clave=str(uuid4()))).status_code, 409)
        self.assertEqual(self.cliente.post(self.ruta, self.entrada()).status_code, 200)
        primero, segundo = SeguimientoPedagogico.objects.all()
        self.assertEqual(segundo.anterior_id, primero.pk)
        self.assertEqual(self.cliente.get(self.ruta).data['count'], 2)
        for accion in [lambda: SeguimientoPedagogico.objects.update(comentario='Cambio'), lambda: SeguimientoPedagogico.objects.all().delete()]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                accion()
        self.assertEqual(self.cliente.patch(self.ruta, {}).status_code, 405)

    def test_roles_revocacion_y_entrada_estricta(self):
        for actor in [self.actor, self.admin]:
            self.cliente.force_authenticate(actor)
            self.assertEqual(self.cliente.post(self.ruta, self.entrada()).status_code, 403)
        self.cliente.force_authenticate(self.otro)
        self.assertEqual(self.cliente.get(self.ruta).status_code, 404)
        self.cliente.force_authenticate(self.coordinador)
        self.assertEqual(self.cliente.post(self.ruta, dict(self.entrada(), actor=self.admin.pk)).status_code, 400)
        PertenenciaRol.objects.filter(usuario=self.coordinador).update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.cliente.post(self.ruta, self.entrada()).status_code, 403)

    def test_fallo_auditoria_revierte_version(self):
        entrada = self.entrada()
        with patch('sesiones.seguimiento._evento', side_effect=RuntimeError('ficticio')), self.assertRaises(RuntimeError):
            self.cliente.post(self.ruta, entrada, format='json')
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.version, entrada['version'])
        self.assertFalse(SeguimientoPedagogico.objects.exists())

    def test_informes_filtros_ambito_y_faltantes(self):
        ruta = '/api/sesiones/informes/'
        for dimension in ['profesor', 'grupo', 'nivel', 'periodo']:
            respuesta = self.cliente.get(ruta, dict(agrupar=dimension, situacion='pendientes'))
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            datos = respuesta.data['results'][0]['indicadores']
            self.assertEqual(datos['sesiones'], 1)
            self.assertEqual(datos['informes_cerrados'], 0)
            self.assertIsNone(datos['porcentaje_presencia'])
            self.assertIsNone(datos['porcentaje_cumplimiento_curricular_declarado'])
        self.assertEqual(self.cliente.get(ruta, dict(situacion='ejecutadas')).data['count'], 0)
        for filtros in [dict(desde='incorrecto'), dict(desde='2026-11-03', hasta='2026-11-01'), dict(nivel='0'), dict(agrupar='actor'), dict(situacion='inventada')]:
            self.assertEqual(self.cliente.get(ruta, filtros).status_code, 400)
        self.cliente.force_authenticate(self.otro)
        self.assertEqual(self.cliente.get(ruta).data['count'], 0)
        self.cliente.force_authenticate(self.actor)
        self.assertEqual(self.cliente.get(ruta).data['count'], 1)
        from organizacion.models import Asignacion
        Asignacion.objects.filter(usuario=self.actor).delete()
        self.assertEqual(self.cliente.get(ruta).data['count'], 0)

    def test_informe_cerrado_no_es_realizada_y_no_duplica_revisiones(self):
        from .test_ejecucion import RegistroEjecucion
        from .ejecucion import operar
        # Reutilizar entradas ficticias de D, sin ejecutar su suite por herencia.
        self.plan_elegido = self.sesion.planes.get()
        datos = RegistroEjecucion.datos_ejecucion(self)
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='guardar_ejecucion', datos=datos)
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='guardar_asistencia', datos=dict(registros={str(self.inscripcion.pk): 'tarde'}))
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='finalizar_ejecucion', datos={})
        self.assertEqual(self.cliente.post(self.ruta, self.entrada()).status_code, 200)
        respuesta = self.cliente.get('/api/sesiones/informes/', dict(situacion='ejecutadas'))
        datos = respuesta.data['results'][0]['indicadores']
        self.assertEqual(datos['informes_cerrados'], 1)
        self.assertEqual(datos['realizadas_institucionales'], 0)
        self.assertEqual(datos['duracion_real_minutos'], 45)
        self.assertEqual(datos['minutos_efectivos'], 30)
        self.assertEqual(datos['minutos_planificados'], 60)
        self.assertEqual(datos['tiempo_no_distribuido_minutos'], 15)
        self.assertEqual(datos['porcentaje_presencia'], 100)
        self.assertEqual(datos['actividades'], dict(realizada=1, modificada=1, omitida=1))
        self.assertEqual(self.cliente.get('/api/sesiones/', dict(situacion='ejecutadas')).data['count'], 1)
        self.assertEqual(self.cliente.get('/api/sesiones/', dict(situacion='programadas')).data['count'], 0)
        self.assertEqual(self.cliente.get('/api/sesiones/', dict(situacion='realizadas')).data['count'], 0)

    def test_paginacion_historial_y_filtro_sin_resultados(self):
        for _ in range(26):
            self.assertEqual(self.cliente.post(self.ruta, self.entrada()).status_code, 200)
        primera = self.cliente.get(self.ruta).data
        segunda = self.cliente.get(self.ruta, dict(page=2)).data
        self.assertEqual(primera['count'], 26)
        self.assertEqual(len(primera['results']), 25)
        self.assertEqual(len(segunda['results']), 1)
        self.assertLess(primera['results'][-1]['id'], segunda['results'][0]['id'])
        self.assertEqual(self.cliente.get('/api/sesiones/informes/', dict(profesor=self.otro.pk)).data['count'], 0)

    def test_insercion_sql_sin_evento_coherente_rechazada(self):
        evento = EventoSesion.objects.filter(sesion=self.sesion).first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SeguimientoPedagogico.objects.create(sesion=self.sesion, actor=self.coordinador, comentario='Falso', evento=evento)


from django.test import TransactionTestCase
from . import test_ejecucion as ejecucion


class ConcurrenciaSeguimiento(TransactionTestCase):
    crear = dominio.DominioSesiones.crear
    paralelas = ejecucion.ConcurrenciaCierre.paralelas

    def setUp(self):
        dominio.ConcurrenciaSesiones.setUp(self)
        self.sesion = self.crear()
        self.coordinador = Usuario.objects.create_user(username='coord-concurrente-e', rol='coordinador')

    def test_misma_clave_y_claves_distintas(self):
        entrada = dict(version=self.sesion.version, clave=str(uuid4()), comentario='Seguimiento concurrente', recomendaciones='')
        self.assertEqual(self.paralelas('seguimiento', [entrada, entrada], actor=self.coordinador), [200, 200])
        self.assertEqual(SeguimientoPedagogico.objects.count(), 1)
        self.sesion.refresh_from_db()
        entradas = [dict(entrada, version=self.sesion.version, clave=str(uuid4())) for _ in range(2)]
        self.assertEqual(sorted(self.paralelas('seguimiento', entradas, actor=self.coordinador)), [200, 409])
        self.assertEqual(SeguimientoPedagogico.objects.count(), 2)
