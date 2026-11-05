"""Fixtures ficticias; ejecutar solo mediante el clúster PostgreSQL aislado."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase

from cuentas.autorizacion import puede
from cuentas.models import CompetenciaEmisora, EnlaceIdentidad, EventoCompetenciaEmisora, Persona, Usuario
from django.utils import timezone
from organizacion.models import Disciplina


def rechazo_version_esperado(error):
    """No aceptar como conflicto lógico un timeout, deadlock u otro fallo SQL."""
    causa = error.__cause__
    codigo = getattr(causa, 'sqlstate', None)
    if codigo == '23514':
        return str(causa).splitlines()[0] == 'Version B1 obsoleta, rama o propuesta retirada'
    if codigo == '23505':
        return getattr(getattr(causa, 'diag', None), 'constraint_name', None) in {
            'competencia_evento_numero', 'cuentas_eventocompetenciaemisora_anterior_id_key'}
    return False


class CompetenciasB1(TestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql', 'B1 requiere PostgreSQL aislado.')
        self.actor = Usuario.objects.create_user(username='b1_ficticio_registrador', rol='profesor')
        self.usuario = Usuario.objects.create_user(username='b1_ficticio_candidato', rol='profesor')
        self.persona = Persona.objects.create(creada_por=self.actor)
        self.enlace = EnlaceIdentidad.objects.create(persona=self.persona, usuario=self.usuario,
            evidencia=uuid4(), acreditado_por=self.actor)
        self.disciplina = Disciplina.objects.create(codigo='b1-ficticia', nombre='Fixture B1')
        self.competencia, self.evento = self.crear()

    def crear(self, **cambios):
        datos = dict(persona=self.persona, usuario=self.usuario, enlace_identidad=self.enlace,
            version_enlace=self.enlace.version, evidencia_identidad=self.enlace.evidencia,
            disciplina=self.disciplina, alcance_propuesto='Propuesta ficticia sin aprobación', registrada_por=self.actor)
        datos.update(cambios)
        with transaction.atomic():
            competencia = CompetenciaEmisora.objects.create(**datos)
            evento = self.agregar(competencia, None, 'propuesta')
        return competencia, evento

    def agregar(self, competencia, precedente, accion, **cambios):
        datos = dict(competencia=competencia, anterior=precedente, numero=precedente.numero+1 if precedente else 1,
            accion=accion, actor=self.actor, clave=uuid4(), motivo='Fixture sin efecto institucional',
            referencia_evidencia=uuid4(), vigente_desde_propuesta=timezone.now())
        datos.update(cambios)
        return EventoCompetenciaEmisora.objects.create(**datos)

    def test_propuesta_no_concede_facultad_y_no_hay_aprobacion(self):
        self.assertFalse(puede(self.usuario, 'autorizaciones_funcionales.emitir'))
        self.assertEqual(self.evento.numero, 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.agregar(self.competencia, self.evento, 'aprobada')

    def test_historia_secuencial_y_retiro_terminal(self):
        revision = self.agregar(self.competencia, self.evento, 'revision')
        retiro = self.agregar(self.competencia, revision, 'retiro')
        for anterior in (self.evento, retiro):
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.agregar(self.competencia, anterior, 'revision')
        self.assertEqual(self.competencia.eventos.count(), 3)

    def test_identidad_incompatible_y_snapshot_conservado(self):
        for cambio in ({'version_enlace': 99}, {'persona': Persona.objects.create(creada_por=self.actor)},
                       {'evidencia_identidad': uuid4()}, {'usuario': self.actor}):
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.crear(**cambio)
        evidencia = self.competencia.evidencia_identidad
        EnlaceIdentidad.objects.filter(pk=self.enlace.pk).update(vigente=False, revocado_por=self.actor,
            revocado_en=timezone.now(), version=2)
        self.competencia.refresh_from_db()
        self.assertEqual(self.competencia.evidencia_identidad, evidencia)
        self.assertEqual(self.competencia.version_enlace, 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.crear()

    def test_restricciones_intervalo_motivo_clave_y_antecedente(self):
        otro, evento_otro = self.crear()
        casos = [dict(motivo='  '), dict(vigente_hasta_propuesta=self.evento.vigente_desde_propuesta),
                 dict(clave=self.evento.clave), dict(numero=9), dict(anterior=evento_otro)]
        for datos in casos:
            with self.subTest(datos=datos), self.assertRaises(DatabaseError), transaction.atomic():
                self.agregar(self.competencia, self.evento, 'revision', **datos)
        self.assertEqual(otro.eventos.count(), 1)

    def test_orm_y_sql_no_reescriben_ni_eliminan(self):
        for obj in (self.competencia, self.evento):
            with self.assertRaises(ValidationError):
                obj.save()
            with self.assertRaises(ValidationError):
                obj.delete()
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).update(id=obj.pk)
            with self.assertRaises(ValidationError):
                type(obj).objects.filter(pk=obj.pk).delete()
            for sql in (f'UPDATE {obj._meta.db_table} SET id=id WHERE id=%s',
                        f'DELETE FROM {obj._meta.db_table} WHERE id=%s'):
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, [obj.pk])
        with self.assertRaises(ProtectedError):
            self.disciplina.delete()

    def test_cabecera_sin_historia_rechazada_al_comprobar_constraint(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            CompetenciaEmisora.objects.bulk_create([CompetenciaEmisora(persona=self.persona,
                usuario=self.usuario, enlace_identidad=self.enlace, version_enlace=1,
                evidencia_identidad=self.enlace.evidencia, disciplina=self.disciplina,
                alcance_propuesto='Fixture huérfana', registrada_por=self.actor)])
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS zdb_competencia_b1_completa IMMEDIATE')

    def test_identidades_protegidas(self):
        for obj in (self.enlace, self.persona, self.usuario):
            with self.assertRaises(ProtectedError):
                obj.delete()

    def test_alcance_version_y_primer_actor_restringidos(self):
        for datos in ({'alcance_propuesto': ' \t '}, {'version_enlace': 0}):
            with self.subTest(datos=datos), self.assertRaises(DatabaseError), transaction.atomic():
                self.crear(**datos)
        # Un autor inicial diferente del registrado en cabecera no crea historia válida.
        with self.assertRaises(DatabaseError), transaction.atomic():
            competencia = CompetenciaEmisora.objects.create(persona=self.persona, usuario=self.usuario,
                enlace_identidad=self.enlace, version_enlace=1, evidencia_identidad=self.enlace.evidencia,
                disciplina=self.disciplina, alcance_propuesto='Fixture B1', registrada_por=self.usuario)
            self.agregar(competencia, None, 'propuesta')

    def test_revision_con_intervalo_vacio_o_invertido(self):
        inicio = timezone.now()
        for fin in (inicio, inicio - timedelta(seconds=1)):
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.agregar(self.competencia, self.evento, 'revision',
                    vigente_desde_propuesta=inicio, vigente_hasta_propuesta=fin)

    def test_migracion_0009_es_deliberadamente_irreversible(self):
        from importlib import import_module
        modulo = import_module('cuentas.migrations.0009_competencia_emisora_guardias_b1')
        operacion = modulo.Migration.operations[0]
        self.assertFalse(operacion.reversible)
        # La operación debe rechazar la reversión antes de usar un schema_editor.
        with self.assertRaises(NotImplementedError):
            operacion.database_backwards('cuentas', None, None, None)


class ConcurrenciaCompetenciasB1(TransactionTestCase):
    # TransactionTestCase permite que los hilos vean fixtures confirmadas.
    crear = CompetenciasB1.crear
    agregar = CompetenciasB1.agregar
    setUp = CompetenciasB1.setUp

    def test_dos_revisiones_del_mismo_antecedente_no_bifurcan(self):
        barrera = Barrier(2)
        competencia_id, anterior_id = self.competencia.pk, self.evento.pk
        actor_id = self.actor.pk

        def intentar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                with transaction.atomic():
                    # Evitar que un fallo de bloqueo deje la prueba esperando indefinidamente.
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                    EventoCompetenciaEmisora.objects.create(competencia_id=competencia_id,
                        anterior_id=anterior_id, numero=2, accion='revision', actor_id=actor_id,
                        clave=uuid4(), motivo='Carrera ficticia B1', referencia_evidencia=uuid4(),
                        vigente_desde_propuesta=timezone.now())
                return 'creada'
            except DatabaseError as error:
                if rechazo_version_esperado(error):
                    return 'rechazada'
                raise
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(lambda _: intentar(), range(2)))
        self.assertCountEqual(resultados, ['creada', 'rechazada'])
        self.assertEqual(self.competencia.eventos.count(), 2)

    def test_rollback_completo_de_cabecera_y_eventos(self):
        antes = (CompetenciaEmisora.objects.count(), EventoCompetenciaEmisora.objects.count())
        with self.assertRaisesRegex(RuntimeError, 'fallo posterior ficticio'):
            with transaction.atomic():
                competencia, evento = self.crear()
                self.agregar(competencia, evento, 'revision')
                raise RuntimeError('fallo posterior ficticio')
        self.assertEqual((CompetenciaEmisora.objects.count(), EventoCompetenciaEmisora.objects.count()), antes)

    def test_constraint_diferida_falla_al_confirmar_y_revierte_cabecera(self):
        self.assertFalse(connection.in_atomic_block)
        antes = CompetenciaEmisora.objects.count()
        with self.assertRaises(DatabaseError) as fallo:
            with transaction.atomic():
                CompetenciaEmisora.objects.create(persona=self.persona, usuario=self.usuario,
                    enlace_identidad=self.enlace, version_enlace=1, evidencia_identidad=self.enlace.evidencia,
                    disciplina=self.disciplina, alcance_propuesto='Fixture sin primer evento', registrada_por=self.actor)
                self.assertEqual(CompetenciaEmisora.objects.count(), antes + 1)
                # Sin SET CONSTRAINTS: el error debe producirse en COMMIT.
        self.assertEqual(getattr(fallo.exception.__cause__, 'sqlstate', None), '23514')
        self.assertIn('primer evento', str(fallo.exception))
        self.assertEqual(CompetenciaEmisora.objects.count(), antes)
