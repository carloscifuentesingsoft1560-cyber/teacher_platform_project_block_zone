"""Preparación expresa B2.2-B1; solo fixtures en PostgreSQL aislado."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.db import connections, close_old_connections
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Grupo, Periodo
from .models import Inscripcion, ReservaCupo
from .servicios_ascensos import proponer_progresion, autorizar_excepcion, revocar_excepcion
from .test_revision_ascensos import DatosRevision


class DatosPlan(DatosRevision):
    def disponer_api(self, **cambios):
        datos = {'version': self.p.version, 'afectacion': self.p.afectaciones.order_by('pk').first().pk,
            'disposicion': 'pendiente', 'motivo': 'Disposición explícita ficticia', **cambios}
        return self.post(f'ascensos/{self.p.pk}/disponer/', datos)

    def consultar_plan(self):
        return self.c.get(f'/api/ascensos/{self.p.pk}/afectaciones/')

    def nueva_propuesta_multiple(self):
        self.assertEqual(self.decidir('rechazar').status_code, 200)
        b = self.inscribir(grupo=self.b)
        self.assertEqual(self.post(f'inscripciones/{b.pk}/suspender/', {'version': 1,
            'motivo': 'Pausa', 'fecha_vencimiento': str(self.hoy + timedelta(days=5))}).status_code, 200)
        futura = self.inscribir(grupo=self.grupo('futura', '14:00', '15:00'), inicio=self.hoy + timedelta(days=3))
        self.p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Propuesta con reserva y futura')
        return b, futura


class PlanAscensosApi(DatosPlan, TestCase):
    def setUp(self):
        self.iniciar()

    def test_consulta_y_disposicion_explicita_sin_aprobar(self):
        antes = self.inventario_deportivo()
        consulta = self.consultar_plan()
        self.assertEqual(consulta.status_code, 200)
        self.assertTrue(consulta.data['revision']['puede_preparar'])
        self.assertTrue(consulta.data['inscripciones'][0]['requiere_revision'])
        r = self.disponer_api()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['estado_decision'], r.data['estado_plan'], r.data['version']), ('pendiente', 'parcial', 2))
        self.assertTrue(r.data['inscripciones'][0]['reubicacion_pendiente'])
        self.assertEqual(r.data['inscripciones'][0]['motivo'], 'Disposición explícita ficticia')
        self.assertEqual(self.inventario_deportivo(), antes)
        self.assertEqual(self.p.eventos.count(), 2)

    def test_varias_reserva_y_futura_cada_una_explicita(self):
        b, futura = self.nueva_propuesta_multiple()
        antes = self.inventario_deportivo()
        for a in self.p.afectaciones.order_by('pk'):
            disposicion = 'reserva' if a.inscripcion_id == b.pk else 'futura' if a.inscripcion_id == futura.pk else 'pendiente'
            r = self.disponer_api(afectacion=a.pk, disposicion=disposicion)
            self.assertEqual(r.status_code, 200, r.data)
            self.p.refresh_from_db()
        self.assertEqual(set(self.p.afectaciones.values_list('disposicion', flat=True)), {'reserva', 'futura', 'pendiente'})
        self.assertTrue(r.data['revision']['puede_aprobar'])
        self.assertEqual(self.inventario_deportivo(), antes)

    def test_reubicar_preparado_no_ejecutado_y_destino_lleno_no_reserva(self):
        self.inscribir(persona=self.persona_nueva('Otra A'), grupo=self.l)
        self.inscribir(persona=self.persona_nueva('Otra B'), grupo=self.l)
        antes = self.inventario_deportivo()
        r = self.disponer_api(disposicion='reubicar', destino=self.l.pk)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado_plan'], 'preparado')
        self.assertEqual(r.data['estado_decision'], 'pendiente')
        self.assertEqual(self.inventario_deportivo(), antes)
        self.assertFalse(r.data['revision']['ejecucion_habilitada'])

    def test_destinos_inexistente_origen_y_nivel_incorrecto(self):
        for destino, estado in ((999999, 404), (self.a.pk, 400), (self.b.pk, 400)):
            self.assertEqual(self.disponer_api(disposicion='reubicar', destino=destino).status_code, estado)
        self.assertEqual(self.p.eventos.count(), 1)

    def test_destino_inactivo_sin_horarios_o_periodo_incompatible(self):
        Grupo.objects.filter(pk=self.l.pk).update(activo=False)
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 400)
        Grupo.objects.filter(pk=self.l.pk).update(activo=True)
        self.l.horarios.update(activo=False)
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 400)
        self.l.horarios.update(activo=True)
        futuro = Periodo.objects.create(codigo='ficticio-otro-periodo', nombre='Futuro',
            fecha_inicio=self.hoy + timedelta(days=60), fecha_fin=self.hoy + timedelta(days=90))
        Grupo.objects.filter(pk=self.l.pk).update(periodo=futuro)
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 400)

    def test_destino_disciplina_ajena(self):
        from organizacion.models import Disciplina, Nivel
        d = Disciplina.objects.create(codigo='otra-ficticia', nombre='Otra')
        n = Nivel.objects.create(disciplina=d, codigo='ficticio', nombre='Otro nivel')
        Grupo.objects.filter(pk=self.l.pk).update(disciplina=d, nivel=n)
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 400)

    def test_contrato_estricto_y_destino_solo_reubicar(self):
        for cambio in ({'disposicion': 'ejecutado'}, {'disposicion': 'reubicar'},
            {'destino': self.l.pk}, {'motivo': '  '}, {'actor': self.coord.pk},
            {'estado_decision': 'aprobada'}, {'version_observada': 1}, {'excepcion': 'autorizada'}):
            self.assertEqual(self.disponer_api(**cambio).status_code, 400)
        self.assertEqual(self.post(f'ascensos/{self.p.pk}/disponer/', {}).status_code, 400)

    def test_profesor_administrador_e_inactivo_sin_permiso(self):
        for actor in (self.prof, self.admin, self.otro):
            self.c.force_authenticate(actor)
            self.assertEqual(self.disponer_api().status_code, 403)
            self.assertEqual(self.consultar_plan().status_code, 403)
        self.c.force_authenticate(self.coord)
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.disponer_api().status_code, 403)

    def test_version_obsoleta_no_repite_evento(self):
        self.assertEqual(self.disponer_api().status_code, 200)
        self.assertEqual(self.disponer_api().status_code, 409)
        self.assertEqual(self.p.eventos.count(), 2)

    def test_afectacion_de_otra_progresion_no_es_editable(self):
        persona = self.persona_nueva('Ajena')
        i = self.inscribir(persona=persona, grupo=self.b)
        p = proponer_progresion(self.prof, i.pk, self.n2, 'Otra propuesta')
        self.assertEqual(self.disponer_api(afectacion=p.afectaciones.get().pk).status_code, 404)
        self.assertEqual(p.afectaciones.get().disposicion, 'revisar')

    def test_cambios_materiales_bloquean_y_no_reconstruyen_plan(self):
        Grupo.objects.filter(pk=self.a.pk).update(cupo_maximo=3)
        self.assertEqual(self.disponer_api().status_code, 409)
        self.assertFalse(self.consultar_plan().data['revision']['puede_preparar'])
        self.assertEqual(self.p.afectaciones.get().disposicion, 'revisar')
        self.assertEqual(self.p.eventos.count(), 1)

    def test_inscripcion_nueva_no_se_incorpora_automaticamente(self):
        self.inscribir(grupo=self.b)
        self.assertEqual(self.disponer_api().status_code, 409)
        self.assertEqual(self.p.afectaciones.count(), 1)

    def test_reserva_modificada_bloquea_preparacion(self):
        b, _ = self.nueva_propuesta_multiple()
        ReservaCupo.objects.filter(inscripcion=b).update(fecha_vencimiento=self.hoy + timedelta(days=4))
        self.assertEqual(self.disponer_api().status_code, 409)

    def test_destino_ya_preparado_cambiado_no_se_rebasa_evidencia(self):
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 200)
        self.p.refresh_from_db()
        Grupo.objects.filter(pk=self.l.pk).update(cupo_maximo=3)
        self.assertEqual(self.disponer_api(disposicion='reubicar', destino=self.l.pk).status_code, 409)
        self.assertEqual(self.p.eventos.count(), 2)

    def test_continuidad_no_autoriza_excepcion_por_texto(self):
        self.assertEqual(self.disponer_api(disposicion='continuidad', motivo='Autorizada').status_code, 400)
        self.assertEqual(self.p.afectaciones.get().excepciones.count(), 0)

    def test_continuidad_con_excepcion_explicita_y_revocacion(self):
        a = self.p.afectaciones.get()
        e = autorizar_excepcion(self.coord, self.p.pk, self.p.version, a.pk, 'Motivo autorizado',
            self.hoy, self.hoy + timedelta(days=2))
        self.p.refresh_from_db()
        self.assertEqual(self.disponer_api(disposicion='continuidad').status_code, 200)
        self.p.refresh_from_db()
        revocar_excepcion(self.coord, self.p.pk, self.p.version, e.pk, 'Revocación institucional')
        self.p.refresh_from_db()
        self.assertEqual(self.disponer_api(disposicion='continuidad').status_code, 400)
        self.assertEqual(self.p.afectaciones.get().disposicion, 'pendiente')

    def test_continuidad_con_excepcion_vencida_rechazada(self):
        a = self.p.afectaciones.get()
        autorizar_excepcion(self.coord, self.p.pk, self.p.version, a.pk, 'Temporal', self.hoy, self.hoy)
        self.p.refresh_from_db()
        with patch('django.utils.timezone.localdate', return_value=self.hoy + timedelta(days=1)):
            self.assertEqual(self.disponer_api(disposicion='continuidad').status_code, 400)

    def test_reserva_y_futura_no_fingen_situacion(self):
        for disposicion in ('reserva', 'futura'):
            self.assertEqual(self.disponer_api(disposicion=disposicion).status_code, 400)

    def test_historial_motivos_y_reapertura_explicita(self):
        self.assertEqual(self.disponer_api().status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.disponer_api(disposicion='revisar', motivo='Reabrir revisión').status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.estado_plan, 'pendiente')
        evento = self.p.eventos.last()
        self.assertEqual(evento.datos['referencia']['anterior']['motivo'], 'Disposición explícita ficticia')
        self.assertEqual(evento.datos['afectaciones'][0]['motivo'], 'Reabrir revisión')

    def test_fallo_evento_revierte_disposicion_y_version(self):
        with patch('inscripciones.servicios_ascensos.registrar_evento', side_effect=RuntimeError('Prueba aislada')):
            with self.assertRaises(RuntimeError):
                self.disponer_api()
        self.p.refresh_from_db()
        self.assertEqual(self.p.version, 1)
        self.assertEqual(self.p.afectaciones.get().disposicion, 'revisar')

    def test_preparacion_y_aprobacion_son_dos_solicitudes(self):
        self.assertEqual(self.disponer_api().status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.decidir().status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.disponer_api().status_code, 409)
        # B3-C publica una acción estricta: aprobar no aporta por sí solo el contrato administrativo.
        self.assertEqual(self.post(f'ascensos/{self.p.pk}/ejecutar/', {}).status_code, 403)

    def test_csrf_no_se_omite_y_parametros_no_permitidos(self):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(self.coord)
        self.assertEqual(c.post(f'/api/ascensos/{self.p.pk}/disponer/', {}, format='json').status_code, 403)
        self.assertEqual(self.c.get(f'/api/ascensos/{self.p.pk}/afectaciones/?foo=1').status_code, 400)


class ConcurrenciaPlanAscensos(DatosPlan, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_preparaciones_misma_version_una_sola_escritura(self):
        self.iniciar()
        antes = self.inventario_deportivo()
        a = self.p.afectaciones.get()
        barrera = Barrier(2)
        def preparar(_):
            close_old_connections()
            try:
                c = APIClient()
                c.force_authenticate(self.coord)
                barrera.wait(timeout=10)
                return c.post(f'/api/ascensos/{self.p.pk}/disponer/', {'version': 1,
                    'afectacion': a.pk, 'disposicion': 'pendiente', 'motivo': 'Concurrente'}, format='json').status_code
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(preparar, range(2))), [200, 409])
        self.assertEqual(self.p.eventos.count(), 2)
        self.assertEqual(self.inventario_deportivo(), antes)
