"""Pruebas B1: solo fixtures de la base aislada creada por el ejecutor."""
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.core.exceptions import ValidationError as ErrorModelo
from django.db import transaction, IntegrityError, close_old_connections, connections
from rest_framework.exceptions import PermissionDenied, ValidationError
from deportistas.tests import DatosFase3
from deportistas.servicios import Conflicto
from organizacion.models import Disciplina, Nivel, Asignacion
from .models import Inscripcion, ReservaCupo, EventoInscripcion, Propuesta
from .modelos_ascensos import ProgresionInstitucional, AfectacionInscripcion, ExcepcionPedagogica, EventoProgresion
from .servicios_ascensos import (proponer_progresion, disponer_inscripcion, decidir_progresion,
    autorizar_excepcion, revocar_excepcion, leer_progresion, progresiones_visibles)


class AscensosB1(DatosFase3, TestCase):
    def setUp(self):
        self.preparar()
        self.origen = self.inscribir()

    def propuesta(self):
        return proponer_progresion(self.prof, self.origen.pk, self.n2, 'Justificación pedagógica ficticia')

    def disponer(self, p, disposicion='pendiente', destino=None, inscripcion=None):
        a = p.afectaciones.get(inscripcion=inscripcion or self.origen)
        return disponer_inscripcion(self.coord, p.pk, p.version, a.pk, disposicion, 'Revisión ficticia', destino)

    def test_creacion_estructural_valida(self):
        p = self.propuesta()
        self.assertEqual((p.deportista_id, p.disciplina_id, p.nivel_origen_id, p.nivel_destino_id, p.periodo_id),
            (self.persona.pk, self.d.pk, self.n.pk, self.n2.pk, self.periodo.pk))
        self.assertEqual((p.estado_decision, p.estado_plan), ('pendiente', 'pendiente'))
        self.assertEqual(p.afectaciones.count(), 1)
        self.assertEqual(p.eventos.get().tipo, 'proponer_ascenso')

    def test_mismo_nivel_y_disciplina_ajena_rechazados(self):
        d = Disciplina.objects.create(codigo='ficticia-otra', nombre='Disciplina ficticia')
        n = Nivel.objects.create(disciplina=d, codigo='ficticio', nombre='Nivel ficticio')
        for nivel in (self.n, n):
            with self.subTest(nivel=nivel.pk), self.assertRaises(ValidationError):
                proponer_progresion(self.prof, self.origen.pk, nivel, 'Motivo')
        self.assertFalse(ProgresionInstitucional.objects.exists())

    def test_identidad_referencia_coherente_en_modelo(self):
        p = self.propuesta()
        p.deportista = self.persona_nueva('Persona ajena')
        with self.assertRaises(ErrorModelo):
            p.save()

    def test_incluye_activa_suspendida_reserva_y_futura(self):
        b = self.inscribir(grupo=self.b)
        self.post(f'inscripciones/{b.pk}/suspender/', {'version':1, 'motivo':'Pausa',
            'fecha_vencimiento':str(self.hoy+timedelta(days=3))})
        g = self.grupo('futuro', '13:00', '14:00')
        futura = self.inscribir(grupo=g, inicio=self.hoy+timedelta(days=5))
        p = self.propuesta()
        self.assertEqual(dict(p.afectaciones.values_list('inscripcion_id', 'situacion_observada')),
            {self.origen.pk:'activa', b.pk:'reserva', futura.pk:'futura'})

    def test_incluye_suspendida_sin_reserva_no_la_ignora(self):
        b = self.inscribir(grupo=self.b)
        Inscripcion.objects.filter(pk=b.pk).update(estado='suspendida')
        self.assertEqual(self.propuesta().afectaciones.get(inscripcion=b).situacion_observada, 'suspendida')

    def test_historicas_finalizadas_no_son_afectaciones(self):
        b = self.inscribir(grupo=self.b)
        self.post(f'inscripciones/{b.pk}/retirar/', {'version':1, 'motivo':'Retiro ficticio'})
        self.assertEqual(self.propuesta().afectaciones.count(), 1)

    def test_aprobacion_sin_destino_no_ejecuta(self):
        p = self.disponer(self.propuesta())
        antes = list(Inscripcion.objects.values())
        p = decidir_progresion(self.coord, p.pk, p.version, True, 'Aprobación pedagógica sin plaza')
        self.assertEqual((p.estado_decision, p.estado_plan), ('aprobada', 'parcial'))
        self.assertEqual(list(Inscripcion.objects.values()), antes)
        self.assertEqual(p.eventos.count(), 3)

    def test_plan_preparado_no_equivale_a_ejecutado(self):
        p = self.disponer(self.propuesta(), 'reubicar', self.l.pk)
        self.assertEqual(p.estado_plan, 'preparado')
        p = decidir_progresion(self.coord, p.pk, p.version, True, 'Revisado')
        self.assertEqual(p.estado_plan, 'preparado')
        self.assertEqual(Inscripcion.objects.count(), 1)

    def test_disposicion_explicita_obligatoria_antes_de_aprobar(self):
        p = self.propuesta()
        with self.assertRaises(ValidationError):
            decidir_progresion(self.coord, p.pk, p.version, True, 'Incompleto')

    def test_rechazo_independiente_no_mueve_inscripciones(self):
        p = self.propuesta()
        decidir_progresion(self.coord, p.pk, p.version, False, 'No procede')
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.estado, 'activa')
        with self.assertRaises(Conflicto):
            decidir_progresion(self.coord, p.pk, 2, True, 'No repetir')

    def test_duplicacion_agregado_y_detalle(self):
        p = self.propuesta()
        with self.assertRaises(Conflicto):
            self.propuesta()
        with self.assertRaises(ErrorModelo):
            AfectacionInscripcion.objects.create(progresion=p, inscripcion=self.origen,
                version_observada=1, situacion_observada='activa')

    def test_sql_rechaza_estado_incompatible(self):
        p = self.propuesta()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgresionInstitucional.objects.filter(pk=p.pk).update(estado_plan='ejecutado')

    def test_destino_y_persona_ajenos_en_detalle(self):
        p = self.propuesta()
        a = p.afectaciones.get()
        a.destino, a.disposicion = self.b, 'reubicar'
        with self.assertRaises(ErrorModelo):
            a.save()
        ajena = self.inscribir(persona=self.persona_nueva('Ajena'), grupo=self.b)
        with self.assertRaises(ErrorModelo):
            AfectacionInscripcion.objects.create(progresion=p, inscripcion=ajena,
                version_observada=1, situacion_observada='activa')

    def test_excepcion_exige_limite_y_fechas_validas(self):
        p = self.propuesta()
        for inicio, limite in ((self.hoy, None), (self.hoy, self.hoy-timedelta(days=1)),
                (self.hoy, self.periodo.fecha_fin+timedelta(days=1))):
            with self.subTest(limite=limite), self.assertRaises(ValidationError):
                autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Temporal', inicio, limite)
        self.assertFalse(ExcepcionPedagogica.objects.exists())

    def test_excepcion_temporal_y_vencimiento_sin_escritura(self):
        p = self.propuesta()
        e = autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Permanencia', self.hoy, self.hoy)
        self.assertEqual(e.situacion, 'vigente')
        with patch('django.utils.timezone.localdate', return_value=self.hoy+timedelta(days=1)):
            self.assertEqual(e.situacion, 'vencida')
        self.assertEqual(Inscripcion.objects.count(), 1)
        self.assertFalse(ReservaCupo.objects.exists())

    def test_continuidad_no_se_concede_sin_excepcion(self):
        with self.assertRaises(ValidationError):
            self.disponer(self.propuesta(), 'continuidad')

    def test_revocacion_conserva_historial_y_reabre_disposicion(self):
        p = self.propuesta()
        e = autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Permanencia', self.hoy, self.hoy)
        p.refresh_from_db()
        p = self.disponer(p, 'continuidad')
        revocar_excepcion(self.coord, p.pk, p.version, e.pk, 'Fin autorizado')
        e.refresh_from_db()
        self.assertEqual(e.situacion, 'revocada')
        self.assertEqual(p.afectaciones.get().disposicion, 'pendiente')
        self.assertEqual(p.eventos.count(), 4)

    def test_administrador_y_coordinador_no_suplantan_docente(self):
        for actor in (self.admin, self.coord):
            with self.subTest(actor=actor.rol), self.assertRaises(PermissionDenied):
                proponer_progresion(actor, self.origen.pk, self.n2, 'No docente')

    def test_solo_coordinador_revisa_decide_y_autoriza(self):
        p = self.propuesta()
        for actor in (self.prof, self.admin):
            for operacion in (
                lambda: decidir_progresion(actor, p.pk, p.version, False, 'No autorizado'),
                lambda: disponer_inscripcion(actor, p.pk, p.version, p.afectaciones.get().pk, 'pendiente', 'Motivo'),
                lambda: autorizar_excepcion(actor, p.pk, p.version, p.afectaciones.get().pk, 'Motivo', self.hoy, self.hoy)):
                with self.subTest(actor=actor.rol), self.assertRaises(PermissionDenied):
                    operacion()

    def test_privacidad_lectura_docente_y_admin(self):
        b = self.inscribir(grupo=self.b)
        Asignacion.objects.filter(grupo=self.b, usuario=self.prof).delete()
        p = self.propuesta()
        datos = leer_progresion(self.prof, p.pk)
        self.assertNotIn('afectaciones', datos)
        self.assertNotIn('excepciones', datos)
        self.assertEqual(len(leer_progresion(self.coord, p.pk)['afectaciones']), 2)
        self.assertEqual(len(leer_progresion(self.admin, p.pk)['afectaciones']), 2)
        with self.assertRaises(PermissionDenied):
            leer_progresion(self.otro, p.pk)

    def test_profesor_desasignado_no_consulta_ni_se_aprueba(self):
        p = self.disponer(self.propuesta())
        Asignacion.objects.filter(usuario=self.prof).delete()
        self.assertFalse(progresiones_visibles(self.prof).exists())
        with self.assertRaises(PermissionDenied):
            decidir_progresion(self.coord, p.pk, p.version, True, 'No vigente')

    def test_coordinador_desactivado_no_decide(self):
        p = self.propuesta()
        self.coord.is_active = False
        self.coord.save()
        with self.assertRaises(PermissionDenied):
            decidir_progresion(self.coord, p.pk, p.version, False, 'No vigente')

    def test_version_y_conjunto_desactualizados(self):
        p = self.propuesta()
        with self.assertRaises(Conflicto):
            disponer_inscripcion(self.coord, p.pk, 99, p.afectaciones.get().pk, 'pendiente', 'Motivo')
        self.inscribir(grupo=self.b)
        with self.assertRaises(Conflicto):
            decidir_progresion(self.coord, p.pk, p.version, True, 'Conjunto anterior')

    def test_version_inscripcion_modificada_rechaza_revision(self):
        p = self.propuesta()
        Inscripcion.objects.filter(pk=self.origen.pk).update(version=2)
        with self.assertRaises(Conflicto):
            self.disponer(p)

    def test_auditoria_y_eventos_no_editables(self):
        p = self.propuesta()
        e = p.eventos.get()
        with self.assertRaises(ErrorModelo):
            e.save()
        with self.assertRaises(ErrorModelo):
            e.delete()
        self.assertNotIn('numero_documento', str(e.datos))

    def test_flujo_completo_b1_no_altera_historial_cupos_reservas(self):
        antes = {m: list(m.objects.values()) for m in (Inscripcion, ReservaCupo, EventoInscripcion, Propuesta)}
        grupos = list(type(self.a).objects.values())
        p = self.propuesta()
        e = autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Temporal', self.hoy, self.hoy)
        p.refresh_from_db()
        p = self.disponer(p, 'continuidad')
        p = decidir_progresion(self.coord, p.pk, p.version, True, 'Aprobado sin ejecutar')
        revocar_excepcion(self.coord, p.pk, p.version, e.pk, 'Revocada')
        for m, filas in antes.items():
            self.assertEqual(list(m.objects.values()), filas)
        self.assertEqual(list(type(self.a).objects.values()), grupos)

    def test_propuesta_antigua_pendiente_bloquea_nueva_sin_modificarla(self):
        antigua = Propuesta.objects.create(tipo='nivel', deportista=self.persona, inscripcion_origen=self.origen,
            grupo_destino=self.l, fecha_efectiva=self.hoy, justificacion='Anterior', creado_por=self.prof, actualizado_por=self.prof)
        with self.assertRaises(Conflicto):
            self.propuesta()
        antigua.refresh_from_db()
        self.assertEqual(antigua.estado, 'pendiente')

    def test_situacion_futura_y_reserva_requieren_estado_observado(self):
        p = self.propuesta()
        for disposicion in ('reserva', 'futura'):
            with self.subTest(disposicion=disposicion), self.assertRaises(ValidationError):
                self.disponer(p, disposicion)

    def test_progresion_abierta_bloquea_propuesta_individual_nueva(self):
        self.propuesta()
        self.c.force_authenticate(self.prof)
        respuesta = self.post('propuestas/', {'tipo':'nivel', 'deportista':self.persona.pk,
            'inscripcion_origen':self.origen.pk, 'grupo_destino':self.l.pk,
            'fecha_efectiva':str(self.hoy), 'justificacion':'No duplicar progresión'})
        self.assertEqual(respuesta.status_code, 409)
        self.assertFalse(Propuesta.objects.exists())

    def test_sql_no_permite_reescribir_decision_o_historial(self):
        p = self.disponer(self.propuesta())
        p = decidir_progresion(self.coord, p.pk, p.version, True, 'Aprobación original')
        for operacion in (
            lambda: ProgresionInstitucional.objects.filter(pk=p.pk).update(resolucion='Reescritura'),
            lambda: EventoProgresion.objects.filter(progresion=p).update(motivo='Reescritura'),
            lambda: EventoProgresion.objects.filter(progresion=p).delete()):
            with self.subTest(operacion=operacion), self.assertRaises(IntegrityError), transaction.atomic():
                operacion()

    def test_sql_no_admite_destino_de_nivel_o_disciplina_incompatibles(self):
        p = self.propuesta()
        with self.assertRaises(IntegrityError), transaction.atomic():
            p.afectaciones.update(disposicion='reubicar', destino=self.b)

    def test_rechazo_revoca_excepcion_sin_tocar_inscripcion(self):
        p = self.propuesta()
        e = autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Temporal', self.hoy, self.hoy)
        p.refresh_from_db()
        decidir_progresion(self.coord, p.pk, p.version, False, 'No procede')
        e.refresh_from_db()
        self.assertEqual(e.estado, 'revocada')
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.estado, 'activa')

    def test_continuidad_vencida_impide_aprobar(self):
        p = self.propuesta()
        autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'Temporal', self.hoy, self.hoy)
        p.refresh_from_db()
        p = self.disponer(p, 'continuidad')
        with patch('django.utils.timezone.localdate', return_value=self.hoy+timedelta(days=1)):
            with self.assertRaises(Conflicto):
                decidir_progresion(self.coord, p.pk, p.version, True, 'Vencida')

    def test_fecha_propuesta_no_es_fecha_ejecucion(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
        p = self.disponer(self.propuesta())
        with patch('django.utils.timezone.localdate', return_value=self.hoy+timedelta(days=1)):
            p = decidir_progresion(self.coord, p.pk, p.version, True, 'Revisión posterior')
        self.assertEqual(p.estado_decision, 'aprobada')
        self.origen.refresh_from_db()
        self.assertIsNone(self.origen.fecha_salida)

    def test_aprobada_tampoco_admite_ejecutado_por_orm_o_sql(self):
        p = self.disponer(self.propuesta())
        p = decidir_progresion(self.coord, p.pk, p.version, True, 'Aprobada sin ejecutar')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProgresionInstitucional.objects.filter(pk=p.pk).update(estado_plan='ejecutado')
        from django.db import connection
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("UPDATE public.inscripciones_progresioninstitucional SET estado_plan='ejecutado' WHERE id=%s", [p.pk])
        p.refresh_from_db()
        self.assertNotEqual(p.estado_plan, 'ejecutado')

    def excepcion_para_prueba(self):
        p = self.propuesta()
        e = autorizar_excepcion(self.coord, p.pk, p.version, p.afectaciones.get().pk,
            'Motivo original', self.hoy, self.hoy+timedelta(days=1))
        p.refresh_from_db()
        return p, e

    def test_excepcion_original_inmutable_por_orm_y_sql(self):
        p, e = self.excepcion_para_prueba()
        from django.db import connection
        for campos in ({'motivo':'Reescritura'}, {'fecha_limite':self.hoy}, {'creado_por':self.admin},
                {'estado':'revocada'}, {'actualizado_por':self.admin}):
            with self.subTest(campos=campos), self.assertRaises(IntegrityError), transaction.atomic():
                ExcepcionPedagogica.objects.filter(pk=e.pk).update(**campos)
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE public.inscripciones_excepcionpedagogica SET motivo=%s WHERE id=%s', ['Reescritura', e.pk])
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExcepcionPedagogica.objects.filter(pk=e.pk).delete()
        self.assertEqual(p.eventos.count(), 2)

    def test_revocacion_sin_evento_coincidente_rechazada(self):
        p, e = self.excepcion_para_prueba()
        from django.db import connection
        from django.utils import timezone
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExcepcionPedagogica.objects.filter(pk=e.pk).update(estado='revocada', revocada_por=self.coord,
                revocada_en=timezone.now(), motivo_revocacion='Sin evento', actualizado_por=self.coord, version=e.version+1)
            # TestCase no hace commit; forzar aquí la restricción diferida.
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS zdb_revocacion_ascenso_auditada IMMEDIATE')
        e.refresh_from_db()
        self.assertEqual(e.estado, 'autorizada')

    def test_revocacion_auditada_conserva_original_y_no_admite_reescritura(self):
        p, e = self.excepcion_para_prueba()
        from django.db import connection
        with transaction.atomic():
            revocar_excepcion(self.coord, p.pk, p.version, e.pk, 'Motivo de revocación')
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS zdb_revocacion_ascenso_auditada IMMEDIATE')
                cursor.execute('SET CONSTRAINTS zdb_revocacion_ascenso_auditada DEFERRED')
        e.refresh_from_db()
        self.assertEqual(e.motivo, 'Motivo original')
        self.assertEqual(e.revocada_por_id, self.coord.pk)
        self.assertIsNotNone(e.revocada_en)
        self.assertEqual(e.motivo_revocacion, 'Motivo de revocación')
        evento = p.eventos.get(tipo='revocar_excepcion')
        self.assertEqual(evento.actor_id, self.coord.pk)
        self.assertEqual(evento.datos['excepciones'][0]['motivo_revocacion'], e.motivo_revocacion)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExcepcionPedagogica.objects.filter(pk=e.pk).update(motivo_revocacion='Reescritura')

    def test_rechazo_con_excepcion_produce_revocacion_auditada(self):
        p, e = self.excepcion_para_prueba()
        from django.db import connection
        decidir_progresion(self.coord, p.pk, p.version, False, 'No procede')
        with connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS zdb_revocacion_ascenso_auditada IMMEDIATE')
            cursor.execute('SET CONSTRAINTS zdb_revocacion_ascenso_auditada DEFERRED')
        e.refresh_from_db()
        self.assertEqual(e.motivo, 'Motivo original')
        self.assertEqual(e.motivo_revocacion, 'No procede')

    def test_sql_nivel_referenciado_no_cambia_disciplina(self):
        self.propuesta()
        d = Disciplina.objects.create(codigo='otra-b1', nombre='Otra ficticia')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Nivel.objects.filter(pk=self.n2.pk).update(disciplina=d)


class ConcurrenciaAscensosB1(DatosFase3, TransactionTestCase):
    def setUp(self):
        self.preparar()
        self.origen = self.inscribir()

    def competir(self, operacion):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from rest_framework.exceptions import APIException
        barrera = Barrier(2)
        def ejecutar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                operacion()
                return 'aceptada'
            except APIException:
                return 'rechazada'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(ejecutar, range(2))), ['aceptada', 'rechazada'])

    @skipUnlessDBFeature('has_select_for_update')
    def test_propuestas_concurrentes_una_progresion(self):
        self.competir(lambda: proponer_progresion(self.prof, self.origen.pk, self.n2, 'Concurrente'))
        self.assertEqual(ProgresionInstitucional.objects.count(), 1)
        self.assertEqual(EventoProgresion.objects.count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_decisiones_concurrentes_no_se_duplican(self):
        p = proponer_progresion(self.prof, self.origen.pk, self.n2, 'Concurrente')
        p = disponer_inscripcion(self.coord, p.pk, p.version, p.afectaciones.get().pk, 'pendiente', 'Sin destino')
        self.competir(lambda: decidir_progresion(self.coord, p.pk, p.version, True, 'Decisión'))
        self.assertEqual(EventoProgresion.objects.filter(tipo='aprobar_ascenso').count(), 1)
        self.assertEqual(Inscripcion.objects.count(), 1)
