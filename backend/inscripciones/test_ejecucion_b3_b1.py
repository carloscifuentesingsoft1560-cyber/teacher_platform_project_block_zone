"""Estructura B3-B1; no prueba ni ejecuta traslados institucionales."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.db import connection, transaction, DatabaseError, close_old_connections, connections
from django.db.migrations.executor import MigrationExecutor
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from deportistas.servicios import Conflicto
from organizacion.models import Grupo
from .test_revision_ascensos import DatosRevision
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from .modelos_ascensos import ProgresionInstitucional
from .models import Inscripcion
from .servicios_ascensos import decidir_progresion, autorizar_excepcion
from .servicios_ejecucion import revisar_plan, registrar_resultado, consultar_ejecucion


class DatosEjecucion(DatosRevision):
    def aprobada(self):
        self.iniciar()
        self.preparar_plan()
        self.p = decidir_progresion(self.coord, self.p.pk, self.p.version, True, 'Aprobación ficticia')

    def filas(self, disposicion='pendiente'):
        return [{'afectacion': a.pk, 'disposicion': disposicion, 'motivo': 'Revisión expresa',
            **({'destino': self.l.pk} if disposicion == 'reubicar' else {})} for a in self.p.afectaciones.all()]

    def revisar(self, actor=None, filas=None):
        self.p.refresh_from_db()
        return revisar_plan(actor or self.admin, self.p.pk, self.p.version,
            filas if filas is not None else self.filas(), 'Nueva revisión administrativa')

    def resultado(self, r, actor=None, **cambios):
        self.p.refresh_from_db()
        return registrar_resultado(actor or self.admin, r.pk, self.p.version,
            self.p.afectaciones.first().pk, cambios.pop('clave', uuid4()), 'Registro administrativo', **cambios)


class EstructuraEjecucionB3(DatosEjecucion, TestCase):
    def setUp(self):
        self.aprobada()

    def test_resultado_pendiente_vinculado_sin_movimientos(self):
        antes = self.inventario_deportivo()
        r = self.revisar()
        e = self.resultado(r)
        self.assertEqual((e.origen_id, e.afectacion_id, e.revision_id, e.estado),
            (self.origen.pk, self.p.afectaciones.get().pk, r.pk, 'pendiente'))
        self.assertEqual(self.inventario_deportivo(), antes)

    def test_revision_coordinador_y_admin_conserva_aprobacion(self):
        decision = (self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion)
        a = self.revisar()
        b = self.revisar(self.admin, self.filas('reubicar'))
        self.p.refresh_from_db()
        self.assertEqual((b.numero, b.anterior_id), (2, a.pk))
        self.assertEqual(RevisionAdministrativa.objects.get(pk=a.pk).disposiciones, a.disposiciones)
        self.assertEqual((self.p.decidida_por_id, self.p.decidida_en, self.p.resolucion), decision)
        with self.assertRaises(PermissionDenied):
            decidir_progresion(self.admin, self.p.pk, self.p.version, True, 'No autoriza')

    def test_profesor_sin_revision_ni_consulta_global(self):
        with self.assertRaises(PermissionDenied):
            self.revisar(self.prof)
        with self.assertRaises(PermissionDenied):
            consultar_ejecucion(self.prof, self.p.pk)

    def test_revision_resuelta_no_omite_afectaciones(self):
        with self.assertRaises(ValidationError):
            self.revisar(filas=[])

    def test_revision_duplicada_o_version_obsoleta(self):
        version = self.p.version
        self.revisar()
        with self.assertRaises(Conflicto):
            revisar_plan(self.admin, self.p.pk, version, self.filas(), 'Obsoleta')

    def test_resultado_idempotente_y_no_duplicado(self):
        r = self.revisar(); clave = uuid4()
        a = self.resultado(r, clave=clave)
        self.assertEqual(self.resultado(r, clave=clave).pk, a.pk)
        with self.assertRaises(Conflicto):
            self.resultado(r)
        self.assertEqual(ResultadoAdministrativo.objects.count(), 1)

    def test_clave_con_otro_contenido_rechazada(self):
        r = self.revisar(); clave = uuid4(); self.resultado(r, clave=clave)
        with self.assertRaises(Conflicto):
            self.resultado(r, clave=clave, estado='resuelta')

    def test_historial_inmutable_por_orm_y_sql(self):
        r = self.revisar(); e = self.resultado(r)
        for modelo in (RevisionAdministrativa, ResultadoAdministrativo):
            for accion in ('update', 'delete'):
                with self.subTest(modelo=modelo, accion=accion), self.assertRaises(DatabaseError), transaction.atomic():
                    if accion == 'update':
                        modelo.objects.all().update(motivo='Alterado')
                    else:
                        with connection.cursor() as c:
                            c.execute('DELETE FROM public.' + modelo._meta.db_table)

    def test_estado_ejecutado_sigue_bloqueado(self):
        r = self.revisar()
        with self.assertRaises(ValidationError):
            self.resultado(r, estado='ejecutada')
        with self.assertRaises(DatabaseError), transaction.atomic():
            ProgresionInstitucional.objects.filter(pk=self.p.pk).update(estado_plan='ejecutado')
        e = self.resultado(r)
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute("UPDATE public.inscripciones_resultadoadministrativo SET estado='ejecutada' WHERE id=%s", [e.pk])

    def test_no_cierra_con_pendiente_y_plan_parcial(self):
        r = self.revisar(); self.resultado(r)
        resumen = consultar_ejecucion(self.admin, self.p.pk)
        self.assertTrue(resumen['plan_completo'])
        self.assertFalse(resumen['puede_cerrar'])
        self.assertEqual(resumen['estado_ejecucion'], 'pendiente')
        self.assertFalse(resumen['ejecucion_habilitada'])
        self.revisar(filas=self.filas('revisar'))
        self.assertFalse(consultar_ejecucion(self.coord, self.p.pk)['plan_completo'])

    def test_excepciones_vigentes_y_vencidas_son_abiertas(self):
        a = self.p.afectaciones.get()
        autorizar_excepcion(self.coord, self.p.pk, self.p.version, a.pk, 'Temporal', self.hoy, self.hoy)
        self.revisar()
        for dia in (self.hoy, self.hoy + timedelta(days=1)):
            with patch('django.utils.timezone.localdate', return_value=dia):
                resumen = consultar_ejecucion(self.coord, self.p.pk)
                self.assertTrue(resumen['excepciones_abiertas'])
                self.assertFalse(resumen['puede_cerrar'])

    def test_resuelta_exige_origen_previamente_finalizado(self):
        r = self.revisar()
        with self.assertRaises(ValidationError):
            self.resultado(r, estado='resuelta')

    def test_situacion_final_solo_referencia_no_cierra_inscripcion(self):
        # Simular un cierre administrativo previo en la fixture, no mediante B3.
        Inscripcion.objects.filter(pk=self.origen.pk).update(estado='finalizada', fecha_salida=self.hoy,
            causa_salida='retiro', version=2)
        r = self.revisar(filas=self.filas('reubicar'))
        antes = self.inventario_deportivo()
        self.resultado(r, estado='resuelta')
        self.assertEqual(self.inventario_deportivo(), antes)
        self.assertTrue(consultar_ejecucion(self.coord, self.p.pk)['puede_cerrar'])
        self.assertFalse(consultar_ejecucion(self.coord, self.p.pk)['cerrado'])

    def test_reserva_futura_y_varias_inscripciones(self):
        # La primera aprobación permanece intacta: incorporar inscripciones en fixtures aisladas.
        b = self.inscribir(grupo=self.b)
        self.post(f'inscripciones/{b.pk}/suspender/', {'version': 1, 'motivo': 'Pausa',
            'fecha_vencimiento': str(self.hoy + timedelta(days=3))})
        f = self.inscribir(grupo=self.grupo('futura', '14:00', '15:00'), inicio=self.hoy + timedelta(days=2))
        from .modelos_ascensos import AfectacionInscripcion
        for i, situacion in ((b, 'reserva'), (f, 'futura')):
            i.refresh_from_db()
            AfectacionInscripcion.objects.create(progresion=self.p, inscripcion=i, version_observada=i.version, situacion_observada=situacion)
        filas = self.filas()
        disposiciones = {self.p.afectaciones.get(inscripcion=b).pk: 'reserva',
                         self.p.afectaciones.get(inscripcion=f).pk: 'futura'}
        for fila in filas:
            fila['disposicion'] = disposiciones.get(fila['afectacion'], fila['disposicion'])
        r = self.revisar(filas=filas)
        self.assertEqual({f['situacion'] for f in r.disposiciones}, {'activa', 'reserva', 'futura'})
        self.assertFalse(consultar_ejecucion(self.coord, self.p.pk)['puede_cerrar'])

    def test_cambio_grupo_requiere_revision_explicita(self):
        r = self.revisar()
        Grupo.objects.filter(pk=self.a.pk).update(cupo_maximo=3)
        with self.assertRaises(Conflicto):
            self.resultado(r)
        self.revisar()
        self.assertFalse(consultar_ejecucion(self.coord, self.p.pk)['discrepancias'])

    def test_auditoria_deferida_no_se_omite(self):
        r = self.revisar()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
            c.execute('INSERT INTO public.inscripciones_resultadoadministrativo (revision_id,afectacion_id,origen_id,estado,clave,motivo,actor_id,version_progresion,registrada_en) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())',
                [r.pk, self.p.afectaciones.get().pk, self.origen.pk, 'pendiente', uuid4(), 'Sin evento', self.admin.pk, r.version_progresion+1])
            c.execute('SET CONSTRAINTS ALL IMMEDIATE')

    def test_sql_rechaza_origen_ajeno_y_ejecucion_insertada(self):
        r = self.revisar()
        otro = self.inscribir(persona=self.persona_nueva('Ajena'), grupo=self.b)
        for origen, estado in ((otro.pk, 'pendiente'), (self.origen.pk, 'ejecutada')):
            with self.subTest(estado=estado), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as c:
                c.execute('INSERT INTO public.inscripciones_resultadoadministrativo (revision_id,afectacion_id,origen_id,estado,clave,motivo,actor_id,version_progresion,registrada_en) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now())',
                    [r.pk, self.p.afectaciones.get().pk, origen, estado, uuid4(), 'Intento invalido', self.admin.pk, r.version_progresion+1])

    def test_situacion_resuelta_no_convierte_pendiente_en_cierre(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(estado='finalizada', fecha_salida=self.hoy,
            causa_salida='retiro', version=2)
        r = self.revisar()
        self.resultado(r, estado='resuelta')
        self.assertFalse(consultar_ejecucion(self.coord, self.p.pk)['puede_cerrar'])

    def test_resultado_en_revision_anterior_conservado(self):
        r = self.revisar(); e = self.resultado(r)
        nueva = self.revisar()
        self.assertTrue(ResultadoAdministrativo.objects.filter(pk=e.pk, revision=r).exists())
        with self.assertRaises(Conflicto):
            self.resultado(r)
        self.assertEqual(consultar_ejecucion(self.coord, self.p.pk)['revision'], nueva.pk)

    def test_fallo_evento_revierte_revision(self):
        antes = self.inventario_deportivo()
        with patch('inscripciones.servicios_ejecucion.registrar_evento', side_effect=RuntimeError('Aislado')):
            with self.assertRaises(RuntimeError):
                self.revisar()
        self.assertEqual(RevisionAdministrativa.objects.count(), 0)
        self.assertEqual(self.inventario_deportivo(), antes)

    def test_paso_del_tiempo_detecta_situacion_futura(self):
        # Reserva y futura pertenecen a una revisión completa de fixtures aisladas.
        self.test_reserva_futura_y_varias_inscripciones()
        with patch('django.utils.timezone.localdate', return_value=self.hoy + timedelta(days=2)):
            self.assertTrue(consultar_ejecucion(self.coord, self.p.pk)['discrepancias'])


class ConcurrenciaEjecucionB3(DatosEjecucion, TransactionTestCase):
    def test_resultados_concurrentes_idempotentes(self):
        self.aprobada(); r = self.revisar(); self.p.refresh_from_db()
        version, clave = self.p.version, uuid4(); afectacion = self.p.afectaciones.get().pk
        barrera = Barrier(2)
        def competir(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return registrar_resultado(self.admin, r.pk, version, afectacion, clave, 'Idempotente').pk
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(competir, range(2)))
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(ResultadoAdministrativo.objects.count(), 1)

    def test_revisiones_concurrentes_una_version(self):
        self.aprobada(); barrera = Barrier(2); filas = self.filas(); version = self.p.version
        def competir(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                revisar_plan(self.admin, self.p.pk, version, filas, 'Concurrente')
                return 'ok'
            except APIException:
                return 'conflicto'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(competir, range(2))), ['ok', 'conflicto'])


class MigracionEjecucionB3(DatosEjecucion, TransactionTestCase):
    def test_revertir_reaplicar_preserva_datos_previos(self):
        with connection.cursor() as c:
            c.execute('SELECT current_database()')
            self.assertTrue(c.fetchone()[0].startswith('test_zdb_fase3_'))
        self.aprobada(); self.revisar()
        from .test_seguridad_migracion_b1 import SeguridadMigracionB1
        auditor = SeguridadMigracionB1()
        tablas = [t for t in connection.introspection.table_names() if t not in (
            'django_migrations', 'inscripciones_revisionadministrativa', 'inscripciones_resultadoadministrativo')]
        antes = auditor.huellas(tablas)
        try:
            MigrationExecutor(connection).migrate([('inscripciones', '0002_progresioninstitucional_eventoprogresion_and_more')])
            self.assertEqual(auditor.huellas(tablas), antes)
        finally:
            MigrationExecutor(connection).migrate([('inscripciones', '0005_facultades_multirrol')])
        self.assertEqual(auditor.huellas(tablas), antes)
        self.assertEqual(RevisionAdministrativa.objects.count(), 0)
