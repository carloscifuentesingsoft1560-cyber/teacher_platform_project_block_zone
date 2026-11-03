"""B2.2-A: fixtures exclusivamente en el clúster PostgreSQL aislado de pruebas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.db import connections, close_old_connections, transaction, IntegrityError, DatabaseError
from rest_framework.test import APIClient
from deportistas.tests import DatosFase3
from cuentas.models import Usuario
from organizacion.models import Grupo, Asignacion, Horario
from .models import Inscripcion, ReservaCupo, EventoInscripcion, Propuesta
from .modelos_ascensos import ProgresionInstitucional, EventoProgresion
from .servicios_ascensos import proponer_progresion, disponer_inscripcion


class DatosRevision(DatosFase3):
    def iniciar(self):
        self.preparar()
        self.origen = self.inscribir()
        self.p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Fundamento pedagógico ficticio')

    def preparar_plan(self):
        # Servicio interno B1, no nuevo endpoint ni disposición automática.
        for a in self.p.afectaciones.order_by('pk'):
            self.p = disponer_inscripcion(self.coord, self.p.pk, self.p.version,
                a.pk, 'pendiente', 'Reubicación pendiente revisada')

    def decidir(self, accion='aprobar', **datos):
        return self.post(f'ascensos/{self.p.pk}/{accion}/', {
            'version': self.p.version, 'decision': accion, 'resolucion': 'Resolución pedagógica ficticia', **datos})

    def detalle(self):
        return self.c.get(f'/api/ascensos/{self.p.pk}/')

    def inventario_deportivo(self):
        return [list(modelo.objects.order_by('pk').values()) for modelo in
            (Inscripcion, ReservaCupo, EventoInscripcion, Grupo, Horario, Asignacion, Propuesta)]


class RevisionAscensosApi(DatosRevision, TestCase):
    def setUp(self):
        self.iniciar()

    def test_listado_coordinador_paginado_y_filtros_estrictos(self):
        r = self.c.get('/api/ascensos/', {'estado_decision': 'pendiente',
            'disciplina': self.d.pk, 'deportista': self.persona.pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['version'], 1)
        self.assertEqual(r.data['results'][0]['profesor_proponente']['id'], self.prof.pk)
        for query in ({'estado_decision': 'inventado'}, {'foo': 1}, {'deportista': 'no'}, {'page': 0}):
            self.assertEqual(self.c.get('/api/ascensos/', query).status_code, 400)

    def test_detalle_multiples_inscripciones_reserva_y_futura(self):
        # Rehacer solo las fixtures aisladas: las afectaciones se identifican al proponer.
        otra = self.inscribir(grupo=self.b)
        self.assertEqual(self.post(f'inscripciones/{otra.pk}/suspender/', {'version': 1,
            'motivo': 'Pausa ficticia', 'fecha_vencimiento': str(self.hoy + timedelta(days=5))}).status_code, 200)
        futura = self.inscribir(grupo=self.grupo('futura', '14:00', '15:00'), inicio=self.hoy + timedelta(days=3))
        # La propuesta original detecta las dos incorporaciones y muestra la unión para revisar.
        r = self.detalle()
        self.assertEqual(r.status_code, 200)
        filas = {i['inscripcion']: i for i in r.data['inscripciones']}
        self.assertEqual(filas[otra.pk]['situacion_actual'], 'reserva')
        self.assertEqual(len(filas[otra.pk]['reservas_vigentes']), 1)
        self.assertEqual(filas[futura.pk]['situacion_actual'], 'futura')
        self.assertTrue(filas[futura.pk]['incorporada_despues'])
        self.assertFalse(r.data['revision']['puede_aprobar'])
        self.assertIn('grupo', filas[self.origen.pk])
        self.assertIn('periodo', filas[self.origen.pk])
        self.assertEqual(len(r.data['eventos']), 1)
        self.assertNotIn('datos', r.data['eventos'][0])

    def test_aprobar_sin_traslados_ni_cupos_y_auditoria(self):
        self.preparar_plan()
        antes = self.inventario_deportivo()
        r = self.decidir()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado_decision'], 'aprobada')
        self.assertEqual(r.data['estado_plan'], 'parcial')
        self.assertEqual(r.data['decision']['responsable']['id'], self.coord.pk)
        self.assertIsNotNone(r.data['decision']['fecha'])
        self.assertEqual(r.data['version'], self.p.version + 1)
        self.assertEqual(r.data['eventos'][-1]['tipo'], 'aprobar_ascenso')
        self.assertEqual(self.inventario_deportivo(), antes)
        self.assertFalse(r.data['revision']['ejecucion_habilitada'])

    def test_rechazo_auditado_sin_preparacion_ni_movimientos(self):
        antes = self.inventario_deportivo()
        r = self.decidir('rechazar')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado_decision'], 'rechazada')
        self.assertEqual(r.data['eventos'][-1]['tipo'], 'rechazar_ascenso')
        self.assertEqual(self.inventario_deportivo(), antes)

    def test_disposicion_no_se_inventa_para_aprobar(self):
        r = self.decidir()
        self.assertEqual(r.status_code, 400)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado_decision, 'pendiente')
        self.assertEqual(self.p.afectaciones.get().disposicion, 'revisar')

    def test_profesor_y_administrador_no_deciden_ni_ven_revision_privada(self):
        for actor in (self.prof, self.admin):
            self.c.force_authenticate(actor)
            for accion in ('aprobar', 'rechazar'):
                self.assertEqual(self.decidir(accion).status_code, 403)
            self.assertEqual(self.c.get(f'/api/ascensos/{self.p.pk}/advertencias/').status_code, 403)
            r = self.detalle()
            self.assertEqual(r.status_code, 200)
            for privado in ('inscripciones', 'eventos', 'excepciones', 'revision', 'version'):
                self.assertNotIn(privado, r.data)

    def test_coordinador_desactivado_no_decide(self):
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.decidir('rechazar').status_code, 403)
        self.assertEqual(self.detalle().status_code, 403)

    def test_coordinador_relevado_no_usa_actor_cacheado(self):
        Usuario.objects.filter(pk=self.coord.pk).update(rol='profesor')
        Usuario.objects.create_user(username='ficticio_nuevo_coord', rol='coordinador')
        self.assertEqual(self.decidir('rechazar').status_code, 403)

    def test_ajeno_sin_expediente_y_anonimo(self):
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.detalle().status_code, 404)
        self.assertEqual(self.c.get('/api/ascensos/').data['count'], 0)
        self.c.force_authenticate(None)
        self.assertIn(self.detalle().status_code, (401, 403))

    def test_version_obsoleta_y_doble_decision(self):
        self.assertEqual(self.decidir('rechazar', version=999).status_code, 409)
        self.assertEqual(self.decidir('rechazar').status_code, 200)
        self.assertEqual(self.decidir('rechazar').status_code, 409)
        self.assertEqual(self.p.eventos.count(), 2)

    def test_contrato_estricto_y_decision_explicita(self):
        for extra in ({'actor': self.prof.pk}, {'estado_decision': 'aprobada'},
            {'estado_plan': 'ejecutado'}, {'decidida_en': '2026-01-01'}, {'decision': 'aprobar'},
            {'resolucion': '  '}):
            self.assertEqual(self.decidir('rechazar', **extra).status_code, 400)
        self.assertEqual(self.post(f'ascensos/{self.p.pk}/rechazar/', {}).status_code, 400)
        self.assertEqual(self.c.patch(f'/api/ascensos/{self.p.pk}/',
            {'estado_plan': 'ejecutado'}, format='json').status_code, 405)

    def test_nueva_inscripcion_bloquea_ambas_decisiones(self):
        self.inscribir(grupo=self.b)
        for accion in ('aprobar', 'rechazar'):
            self.assertEqual(self.decidir(accion).status_code, 409)
        self.assertEqual(self.p.eventos.count(), 1)

    def test_version_inscripcion_modificada(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(version=2)
        self.assertEqual(self.decidir('rechazar').status_code, 409)

    def test_cambios_materiales_grupo_horario_periodo(self):
        for modelo, pk, cambio in ((Grupo, self.a.pk, {'cupo_maximo': 3}),
            (Horario, self.a.horarios.get().pk, {'activo': False}),
            (type(self.periodo), self.periodo.pk, {'activo': False})):
            with self.subTest(modelo=modelo.__name__), transaction.atomic():
                modelo.objects.filter(pk=pk).update(**cambio)
                self.assertEqual(self.decidir('rechazar').status_code, 409)
                transaction.set_rollback(True)

    def test_reserva_editada_sin_version_inscripcion_detectada(self):
        self.assertEqual(self.decidir('rechazar').status_code, 200)
        b = self.inscribir(grupo=self.b)
        self.post(f'inscripciones/{b.pk}/suspender/', {'version': 1, 'motivo': 'Reserva',
            'fecha_vencimiento': str(self.hoy + timedelta(days=5))})
        self.p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Revisión con reserva')
        from .revision_ascensos import evidencia_contexto, huella
        antes = evidencia_contexto(self.p)
        version = Inscripcion.objects.get(pk=b.pk).version
        ReservaCupo.objects.filter(inscripcion=b).update(fecha_vencimiento=self.hoy + timedelta(days=4))
        self.assertNotEqual(huella(antes), huella(evidencia_contexto(self.p)))
        self.assertEqual(Inscripcion.objects.get(pk=b.pk).version, version)
        self.assertEqual(self.decidir('rechazar').status_code, 409)

    def test_aprobar_con_reserva_y_futura_no_altera_su_historial(self):
        self.assertEqual(self.decidir('rechazar').status_code, 200)
        b = self.inscribir(grupo=self.b)
        self.assertEqual(self.post(f'inscripciones/{b.pk}/suspender/', {'version': 1,
            'motivo': 'Reserva', 'fecha_vencimiento': str(self.hoy + timedelta(days=5))}).status_code, 200)
        futura = self.inscribir(grupo=self.grupo('futura', '14:00', '15:00'), inicio=self.hoy + timedelta(days=3))
        self.p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Todas las inscripciones')
        self.preparar_plan()
        antes = self.inventario_deportivo()
        r = self.decidir()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual({i['situacion_observada'] for i in r.data['inscripciones']}, {'activa', 'reserva', 'futura'})
        self.assertEqual({i['inscripcion'] for i in r.data['inscripciones']}, {self.origen.pk, b.pk, futura.pk})
        self.assertEqual(self.inventario_deportivo(), antes)

    def test_destino_modificado_despues_de_disponer(self):
        a = self.p.afectaciones.get()
        self.p = disponer_inscripcion(self.coord, self.p.pk, self.p.version,
            a.pk, 'reubicar', 'Destino revisado', self.l.pk)
        Grupo.objects.filter(pk=self.l.pk).update(cupo_maximo=3)
        self.assertEqual(self.decidir().status_code, 409)

    def test_perdida_asignacion_impide_aprobar_permite_rechazo(self):
        self.preparar_plan()
        Asignacion.objects.filter(usuario=self.prof).update(fecha_fin=self.hoy - timedelta(days=1))
        self.assertEqual(self.decidir().status_code, 403)
        self.assertEqual(self.decidir('rechazar').status_code, 200)

    def test_fallo_evento_revierte_decision_completa(self):
        with patch('inscripciones.servicios_ascensos.registrar_evento', side_effect=RuntimeError('Fallo aislado')):
            with self.assertRaises(RuntimeError):
                self.decidir('rechazar')
        self.p.refresh_from_db()
        self.assertEqual((self.p.estado_decision, self.p.version), ('pendiente', 1))
        self.assertEqual(self.p.eventos.count(), 1)

    def test_historial_y_estado_ejecutado_protegidos_en_postgresql(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            EventoProgresion.objects.filter(progresion=self.p).update(motivo='Reescritura')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgresionInstitucional.objects.filter(pk=self.p.pk).update(estado_plan='ejecutado')
        self.assertEqual(self.p.eventos.get().motivo, 'Fundamento pedagógico ficticio')

    def test_propuesta_sin_evidencia_anterior_no_se_reconstruye(self):
        self.assertEqual(self.decidir('rechazar').status_code, 200)
        with patch('inscripciones.revision_ascensos.evidencia_contexto', return_value=None):
            self.p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Expediente anterior sin evidencia')
        eventos = list(self.p.eventos.values())
        r = self.c.get(f'/api/ascensos/{self.p.pk}/advertencias/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('sin_evidencia_material', [a['codigo'] for a in r.data['advertencias']])
        self.assertEqual(self.decidir('rechazar').status_code, 409)
        self.assertEqual(list(self.p.eventos.values()), eventos)

    def test_csrf_decision_con_sesion(self):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(self.coord)
        self.assertEqual(c.post(f'/api/ascensos/{self.p.pk}/rechazar/', {
            'version': 1, 'decision': 'rechazar', 'resolucion': 'Sin CSRF'}, format='json').status_code, 403)


class ConcurrenciaRevisionAscensos(DatosRevision, TransactionTestCase):
    def test_desactivacion_entre_permiso_http_y_servicio(self):
        self.iniciar()
        ingreso, continuar = Event(), Event()
        from .servicios_ascensos import decidir_progresion
        def servicio(*args, **kwargs):
            ingreso.set()
            if not continuar.wait(timeout=10):
                raise RuntimeError('Sin señal de la prueba')
            return decidir_progresion(*args, **kwargs)
        def solicitud():
            close_old_connections()
            try:
                c = APIClient()
                c.force_authenticate(self.coord)
                return c.post(f'/api/ascensos/{self.p.pk}/rechazar/', {
                    'version': 1, 'decision': 'rechazar', 'resolucion': 'Relevo concurrente'}, format='json').status_code
            finally:
                connections['default'].close()
        with patch('inscripciones.views_ascensos.decidir_progresion', side_effect=servicio):
            with ThreadPoolExecutor(max_workers=1) as pool:
                trabajo = pool.submit(solicitud)
                try:
                    self.assertTrue(ingreso.wait(timeout=10))
                    Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
                finally:
                    continuar.set()
                self.assertEqual(trabajo.result(timeout=15), 403)
        self.p.refresh_from_db()
        self.assertEqual((self.p.estado_decision, self.p.eventos.count()), ('pendiente', 1))

    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_aprobaciones_solo_una_decision(self):
        self.iniciar()
        self.preparar_plan()
        antes = self.inventario_deportivo()
        barrera = Barrier(2)
        def aprobar(_):
            close_old_connections()
            try:
                c = APIClient()
                c.force_authenticate(self.coord)
                barrera.wait(timeout=10)
                return c.post(f'/api/ascensos/{self.p.pk}/aprobar/', {'version': self.p.version,
                    'decision': 'aprobar', 'resolucion': 'Concurrente'}, format='json').status_code
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(aprobar, range(2))), [200, 409])
        self.assertEqual(self.p.eventos.filter(tipo='aprobar_ascenso').count(), 1)
        self.assertEqual(self.inventario_deportivo(), antes)
