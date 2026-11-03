"""API B3-C: datos ficticios únicamente en PostgreSQL aislado."""
from uuid import uuid4
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from .test_movimientos_b3_b2 import DatosMovimiento
from .modelos_ejecucion import ResultadoAdministrativo, RevisionAdministrativa
from .api_ejecucion import instalacion_verificada


class ApiEjecucion(DatosMovimiento, TestCase):
    def setUp(self):
        self.iniciar_movimiento()

    def ruta(self, accion): return f'/api/ascensos/{self.p.pk}/{accion}/'

    def payload(self, **cambios):
        self.p.refresh_from_db()
        return {'revision': self.r.pk, 'version': self.p.version, 'afectacion': self.aid,
            'clave': str(uuid4()), 'motivo': 'Reubicación autorizada ficticia', **cambios}

    def enviar(self, **cambios):
        return self.c.post(self.ruta('ejecutar'), self.payload(**cambios), format='json')

    def test_consulta_y_privacidad(self):
        self.assertTrue(instalacion_verificada())
        r = self.c.get(self.ruta('ejecucion'))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['ejecucion_habilitada'])
        self.assertTrue(r.data['afectaciones'][0]['puede_ejecutar'])
        self.assertEqual(r.data['afectaciones'][0]['destino']['disponibles'], 2)
        texto = str(r.data)
        for campo in ('numero_documento', 'fecha_nacimiento', 'huella_contexto', 'evidencia_ejecucion'):
            self.assertNotIn(campo, texto)

    def test_ejecucion_por_administrador_sin_cambio_pedagogico(self):
        decision = (self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion)
        r = self.enviar()
        self.assertEqual(r.status_code, 200, r.data)
        self.p.refresh_from_db()
        self.assertEqual((self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion), decision)
        self.assertEqual(self.c.get(self.ruta('ejecucion')).data['estado_ejecucion'], 'ejecutado')

    def test_administrador_ejecuta_pero_no_aprueba(self):
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.c.get(self.ruta('ejecucion')).status_code, 200)
        self.assertEqual(self.c.post(self.ruta('aprobar'), {}, format='json').status_code, 403)
        self.assertEqual(self.enviar().status_code, 200)

    def test_profesor_denegado_en_todas_las_rutas(self):
        self.c.force_authenticate(self.prof)
        antes = self.inventario_deportivo()
        for accion in ('ejecucion', 'revisiones', 'resultados'):
            self.assertEqual(self.c.get(self.ruta(accion)).status_code, 403)
        self.assertEqual(self.enviar().status_code, 403)
        self.assertEqual(self.c.post(self.ruta('revisiones'), {}, format='json').status_code, 403)
        self.assertEqual(antes, self.inventario_deportivo())

    def test_coordinador_desactivado(self):
        self.c.force_authenticate(self.coord)
        type(self.coord).objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.enviar().status_code, 403)

    def test_guardia_sql_anterior_no_habilita_formalizacion(self):
        from importlib import import_module
        anterior=import_module('inscripciones.migrations.0004_ejecucion_administrativa')
        with connection.cursor() as c:c.execute(anterior.GUARDIA)
        self.assertFalse(instalacion_verificada())
        self.assertEqual(self.enviar().status_code,503)

    def test_esquema_pendiente_bloquea_sin_llamar_servicio(self):
        antes = self.inventario_deportivo()
        with patch('inscripciones.api_ejecucion.instalacion_verificada', return_value=False), patch(
                'inscripciones.servicios_movimientos.ejecutar_reubicacion') as servicio:
            self.assertEqual(self.enviar().status_code, 503)
            servicio.assert_not_called()
            r = self.c.get(self.ruta('ejecucion'))
            self.assertFalse(r.data['ejecucion_habilitada'])
            self.assertFalse(r.data['afectaciones'][0]['puede_ejecutar'])
        self.assertEqual(antes, self.inventario_deportivo())

    def test_idempotencia_y_doble_ejecucion(self):
        d = self.payload()
        a = self.c.post(self.ruta('ejecutar'), d, format='json')
        b = self.c.post(self.ruta('ejecutar'), d, format='json')
        self.assertEqual((a.status_code, b.status_code), (200, 200))
        self.assertEqual(a.data['resultado'], b.data['resultado'])
        self.assertEqual(self.enviar().status_code, 409)
        self.assertEqual(ResultadoAdministrativo.objects.count(), 1)

    def test_payload_estricto(self):
        for campo in ('actor', 'estado', 'destino', 'fecha', 'estado_decision', 'aprobada'):
            self.assertEqual(self.enviar(**{campo: 1}).status_code, 400)
        self.assertEqual(self.enviar(clave='no-es-uuid').status_code, 400)

    def test_version_obsoleta(self):
        antes = self.inventario_deportivo()
        self.assertEqual(self.enviar(version=999).status_code, 409)
        self.assertEqual(antes, self.inventario_deportivo())

    def test_revision_no_pertenece_a_url(self):
        self.assertEqual(self.enviar(revision=99999).status_code, 404)

    def test_cupo_y_estado_inactivo_bloquean(self):
        self.inscribir(persona=self.persona_nueva('Cupo A'), grupo=self.l)
        self.inscribir(persona=self.persona_nueva('Cupo B'), grupo=self.l)
        r = self.c.get(self.ruta('ejecucion'))
        self.assertFalse(r.data['afectaciones'][0]['puede_ejecutar'])
        self.assertEqual(self.enviar().status_code, 409)
        type(self.l).objects.filter(pk=self.l.pk).update(activo=False)
        fila = self.c.get(self.ruta('ejecucion')).data['afectaciones'][0]
        self.assertFalse(fila['puede_ejecutar'])
        self.assertNotIn('ErrorDetail', str(fila['bloqueos']))

    def test_suspendida_y_futura_no_ejecutables(self):
        from .models import Inscripcion
        for cambios in ({'estado': 'suspendida'}, {'fecha_ingreso': self.hoy + timedelta(days=1)}):
            with self.subTest(cambios=cambios):
                Inscripcion.objects.filter(pk=self.origen.pk).update(**cambios)
                r = self.c.get(self.ruta('ejecucion'))
                self.assertFalse(r.data['afectaciones'][0]['puede_ejecutar'])
                self.assertEqual(self.enviar().status_code, 409)

    def test_historial_paginado_sin_evidencia_privada(self):
        self.enviar()
        for accion in ('resultados', 'revisiones'):
            r = self.c.get(self.ruta(accion))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.data['count'], 1)
            self.assertNotIn('huella_contexto', str(r.data))
            self.assertNotIn('evidencia_ejecucion', str(r.data))
            self.assertEqual(self.c.get(self.ruta(accion), {'page': 0}).status_code, 400)
            self.assertEqual(self.c.get(self.ruta(accion), {'intruso': 1}).status_code, 400)

    def test_revision_completa_versionada_por_administrador(self):
        self.c.force_authenticate(self.admin)
        antes = self.inventario_deportivo()
        r = self.c.post(self.ruta('revisiones'), {'version': self.p.version, 'motivo': 'Revisión expresa',
            'disposiciones': self.filas('reubicar')}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(RevisionAdministrativa.objects.count(), 2)
        self.assertEqual(antes, self.inventario_deportivo())

    def test_plan_incompleto_bloquea(self):
        self.r = self.revisar(filas=self.filas('revisar'))
        self.assertFalse(self.c.get(self.ruta('ejecucion')).data['afectaciones'][0]['puede_ejecutar'])
        self.assertEqual(self.enviar().status_code, 409)

    def test_destino_desaparecido_en_consulta(self):
        self.l.horarios.all().delete()
        from organizacion.models import Asignacion
        Asignacion.objects.filter(grupo=self.l).delete()
        self.l.delete()
        r = self.c.get(self.ruta('ejecucion'))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['afectaciones'][0]['destino'])
        self.assertFalse(r.data['afectaciones'][0]['puede_ejecutar'])
        self.assertEqual(r.data['advertencias_destinos'][0]['codigo'], 'destino_inexistente')
        self.assertEqual(self.enviar().status_code, 409)

    def test_csrf_en_sesion_de_administrador(self):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(self.admin)
        self.assertEqual(c.post(self.ruta('ejecutar'), self.payload(), format='json').status_code, 403)

    def test_trigger_deshabilitado_no_habilita_ejecucion(self):
        with connection.cursor() as c:
            c.execute('ALTER TABLE public.inscripciones_resultadoadministrativo DISABLE TRIGGER zdb_movimiento_ascenso_verificado')
        self.assertFalse(instalacion_verificada())
        self.assertEqual(self.enviar().status_code, 503)


class ApiEsquemaAnterior(DatosMovimiento, TransactionTestCase):
    def test_lectura_y_bloqueo_con_0003_sin_columna_nueva(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_zdb_fase3_'))
        self.iniciar_movimiento()
        anterior = [('inscripciones', '0003_revisionadministrativa_resultadoadministrativo_and_more')]
        actual = [('inscripciones', '0005_facultades_multirrol')]
        try:
            MigrationExecutor(connection).migrate(anterior)
            self.assertFalse(instalacion_verificada())
            base = f'/api/ascensos/{self.p.pk}/'
            r = self.c.get(base + 'ejecucion/')
            self.assertEqual(r.status_code, 200, r.data)
            self.assertFalse(r.data['ejecucion_habilitada'])
            self.assertEqual(self.c.get(base + 'resultados/').status_code, 200)
            self.assertEqual(self.c.get(base + 'revisiones/').status_code, 200)
            self.assertEqual(self.c.post(base + 'ejecutar/', {}, format='json').status_code, 503)
        finally:
            MigrationExecutor(connection).migrate(actual)


class ApiEjecucionConcurrente(DatosMovimiento, TransactionTestCase):
    def test_dos_peticiones_misma_clave_solo_un_movimiento(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_zdb_fase3_'))
        self.iniciar_movimiento()
        datos = {'revision': self.r.pk, 'version': self.p.version, 'afectacion': self.aid,
            'clave': str(uuid4()), 'motivo': 'Movimiento concurrente ficticio'}
        barrera = Barrier(2)
        def peticion(_):
            close_old_connections()
            try:
                c = APIClient(); c.force_authenticate(self.admin)
                barrera.wait(timeout=10)
                r = c.post(f'/api/ascensos/{self.p.pk}/ejecutar/', datos, format='json')
                return r.status_code, r.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(peticion, range(2)))
        self.assertEqual([r[0] for r in resultados], [200, 200], resultados)
        self.assertEqual(resultados[0][1]['resultado'], resultados[1][1]['resultado'])
        self.assertEqual(ResultadoAdministrativo.objects.filter(estado='ejecutada').count(), 1)
