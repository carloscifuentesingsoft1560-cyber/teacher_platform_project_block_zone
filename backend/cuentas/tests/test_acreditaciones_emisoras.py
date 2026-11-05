"""B2.1 con identidades ficticias, exclusivamente en PostgreSQL temporal aislado."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, time
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError as ErrorModelo
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from auditoria.models import CambioAdministrativo
from cuentas.autorizacion import puede
from cuentas.models import (Usuario, Persona, EnlaceIdentidad, CompetenciaEmisora, EventoCompetenciaEmisora,
                            MandatoInstitucional, EventoMandatoInstitucional, AcreditacionEmisora, EventoAcreditacionEmisora)
from cuentas.servicios_competencias_emisoras import proponer_mandato, proponer_acreditacion, registrar_evento
from deportistas.servicios import Conflicto
from organizacion.models import Disciplina


class DatosB21:
    def identidad(self, nombre, rol='profesor', persona=None):
        usuario = Usuario.objects.create_user(username='b21_ficticio_' + nombre, rol=rol)
        persona = persona or Persona.objects.create(creada_por=self.registrador if hasattr(self, 'registrador') else usuario)
        enlace = EnlaceIdentidad.objects.create(persona=persona, usuario=usuario,
            evidencia=uuid4(), acreditado_por=usuario)
        return usuario, enlace

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.registrador, self.enlace_reg = self.identidad('registrador', 'administrador')
        self.titular, self.enlace_tit = self.identidad('titular')
        self.candidato, self.enlace_cand = self.identidad('candidato')
        self.otro, self.enlace_otro = self.identidad('otro', 'administrador')
        self.disciplina = Disciplina.objects.create(codigo='b21-ficticia', nombre='Fixture B2.1')
        self.desde = timezone.now() - timedelta(days=2)
        self.hasta = self.desde + timedelta(days=30)
        with transaction.atomic():
            self.b1 = CompetenciaEmisora.objects.create(persona=self.enlace_cand.persona,
                usuario=self.candidato, enlace_identidad=self.enlace_cand, version_enlace=1,
                evidencia_identidad=self.enlace_cand.evidencia, disciplina=self.disciplina,
                alcance_propuesto='Candidatura ficticia sin facultad', registrada_por=self.registrador)
            self.evento_b1 = EventoCompetenciaEmisora.objects.create(competencia=self.b1, numero=1,
                accion='propuesta', actor=self.registrador, clave=uuid4(), motivo='Fixture B1',
                referencia_evidencia=uuid4(), vigente_desde_propuesta=self.desde, vigente_hasta_propuesta=self.hasta)
        self.evento_m = self.mandato()
        self.m = self.evento_m.mandato
        self.evento_a = self.acreditacion()
        self.a = self.evento_a.acreditacion

    def datos(self):
        return dict(motivo='Fixture pendiente, sin aprobación', referencia_evidencia=uuid4(),
                    vigente_desde_propuesta=self.desde, vigente_hasta_propuesta=self.hasta)

    def mandato(self, **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), enlace_identidad_id=self.enlace_tit.pk,
                     disciplina_id=self.disciplina.pk, alcance_propuesto='Mandato ficticio pendiente', **self.datos())
        datos.update(cambios)
        return proponer_mandato(**datos)

    def acreditacion(self, **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), competencia_id=self.b1.pk,
                     evento_competencia_id=self.evento_b1.pk, mandato_id=self.m.pk,
                     evento_mandato_id=self.evento_m.pk, **self.datos())
        datos.update(cambios)
        return proponer_acreditacion(**datos)

    def evento(self, tipo='mandato', **cambios):
        datos = dict(actor=self.registrador, clave=uuid4(), tipo=tipo,
                     expediente_id=self.m.pk if tipo == 'mandato' else self.a.pk,
                     numero_esperado=1, accion='revision', **self.datos())
        datos.update(cambios)
        return registrar_evento(**datos)

    def raw_evento(self, tipo='mandato', **cambios):
        padre, modelo = ((self.m, EventoMandatoInstitucional) if tipo == 'mandato'
                          else (self.a, EventoAcreditacionEmisora))
        valores = dict(self.datos())
        valores['referencia_evidencia'] = str(valores['referencia_evidencia'])
        valores['vigente_desde_propuesta'] = self.desde.isoformat()
        valores['vigente_hasta_propuesta'] = self.hasta.isoformat()
        datos = {tipo: padre, 'numero': 2, 'anterior': padre.eventos.get(numero=1), 'accion': 'revision',
                 'actor': self.registrador, 'persona_actor': self.enlace_reg.persona,
                 'enlace_actor': self.enlace_reg, 'version_enlace_actor': 1,
                 'evidencia_actor': self.enlace_reg.evidencia, 'clave': uuid4(),
                 'solicitud': dict(tipo=tipo, operacion='revision', expediente=padre.pk, numero_esperado=1, datos=valores),
                 **{k: v for k, v in valores.items() if k not in ('vigente_desde_propuesta', 'vigente_hasta_propuesta')},
                 'vigente_desde_propuesta': self.desde, 'vigente_hasta_propuesta': self.hasta}
        datos.update(cambios)
        return modelo.objects.create(**datos)

    def cabecera_sin_evento(self):
        datos = {f.attname: getattr(self.m, f.attname) for f in self.m._meta.fields
                 if f.name not in ('id', 'identificador', 'registrada_en')}
        return MandatoInstitucional.objects.create(**datos)


class IntegridadB21(DatosB21, TestCase):
    def test_expedientes_y_acciones_no_conceden_permisos(self):
        for modelo in (MandatoInstitucional, AcreditacionEmisora, EventoMandatoInstitucional, EventoAcreditacionEmisora):
            self.assertEqual(modelo._meta.default_permissions, ('view',))
            self.assertFalse({'vigente', 'activo', 'aprobado'}.intersection(f.name for f in modelo._meta.fields))
        for actor in (self.registrador, self.titular, self.candidato):
            self.assertFalse(puede(actor, 'autorizaciones_funcionales.emitir'))
        with self.assertRaises(ValidationError):
            self.evento(accion='aprobar')

    def test_auto_mandato_y_candidato_registrador_rechazados(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.mandato(enlace_identidad_id=self.enlace_reg.pk)
        self.candidato.rol = 'administrador'
        self.candidato.save(update_fields=['rol'])
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion(actor=self.candidato)

    def test_candidato_y_titular_no_pueden_ser_misma_persona(self):
        evento = self.mandato(enlace_identidad_id=self.enlace_cand.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion(mandato_id=evento.mandato_id, evento_mandato_id=evento.pk)

    def test_autoacreditacion_entre_cuentas_con_identidad_historica(self):
        EnlaceIdentidad.objects.filter(pk=self.enlace_cand.pk).update(vigente=False,
            revocado_por=self.registrador, revocado_en=timezone.now(), version=2)
        cuenta, _ = self.identidad('otra_cuenta_candidato', 'administrador', self.enlace_cand.persona)
        with self.assertRaises(DatabaseError) as error, transaction.atomic():
            self.acreditacion(actor=cuenta)
        self.assertIn('autoacreditacion', str(error.exception))

    def test_registro_exige_admin_e_identidad(self):
        with self.assertRaises(PermissionDenied):
            self.mandato(actor=self.titular)
        sin_identidad = Usuario.objects.create_user(username='b21_ficticio_sin_identidad', rol='administrador')
        with self.assertRaises(PermissionDenied):
            self.mandato(actor=sin_identidad)

    def test_revocacion_de_registrador_impide_incluso_reintento(self):
        clave = uuid4(); evidencia = uuid4()
        self.mandato(clave=clave, referencia_evidencia=evidencia)
        Usuario.objects.filter(pk=self.registrador.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.mandato(clave=clave, referencia_evidencia=evidencia)

    def test_identidad_retirada_preserva_snapshot_y_bloquea_nuevos_eventos(self):
        evidencia = self.m.evidencia_identidad
        EnlaceIdentidad.objects.filter(pk=self.enlace_tit.pk).update(vigente=False,
            revocado_por=self.registrador, revocado_en=timezone.now(), version=2)
        self.m.refresh_from_db()
        self.assertEqual(self.m.evidencia_identidad, evidencia)
        self.assertEqual(self.m.version_enlace, 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.evento()

    def test_referencias_inexistentes_ajenas_y_disciplina_incompatible(self):
        otra = Disciplina.objects.create(codigo='b21-otra', nombre='Otra fixture')
        evento_otro = self.mandato(disciplina_id=otra.pk)
        casos = [dict(competencia_id=999999), dict(evento_competencia_id=999999),
                 dict(mandato_id=999999), dict(evento_mandato_id=evento_otro.pk),
                 dict(mandato_id=evento_otro.mandato_id, evento_mandato_id=evento_otro.pk)]
        for datos in casos:
            with self.subTest(datos=datos), self.assertRaises(DatabaseError), transaction.atomic():
                self.acreditacion(**datos)

    def test_fundamento_mandato_revisado_o_retirado_no_se_reutiliza(self):
        segundo = self.evento()
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion()
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.evento(tipo='acreditacion')
        nuevo = self.acreditacion(evento_mandato_id=segundo.pk)
        self.assertEqual(nuevo.numero, 1)
        self.evento(numero_esperado=2, accion='retiro')
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion(evento_mandato_id=segundo.pk)

    def test_fundamento_b1_retirado_no_se_reutiliza(self):
        EventoCompetenciaEmisora.objects.create(competencia=self.b1, numero=2, anterior=self.evento_b1,
            accion='retiro', actor=self.registrador, clave=uuid4(), **self.datos())
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion()
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.evento(tipo='acreditacion')

    def test_revision_b1_exige_nuevo_antecedente_exacto(self):
        nuevo = EventoCompetenciaEmisora.objects.create(competencia=self.b1, numero=2, anterior=self.evento_b1,
            accion='revision', actor=self.registrador, clave=uuid4(), **self.datos())
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion()
        self.assertEqual(self.acreditacion(evento_competencia_id=nuevo.pk).accion, 'propuesta')

    def test_eventos_consecutivos_y_retiro_terminal_en_ambos_expedientes(self):
        # Acreditación primero: revisar el mandato invalida sus referencias para nuevas actuaciones.
        for tipo in ('acreditacion', 'mandato'):
            segundo = self.evento(tipo=tipo)
            tercero = self.evento(tipo=tipo, numero_esperado=2, accion='retiro')
            self.assertEqual(tercero.anterior_id, segundo.pk)
            with self.assertRaises(Conflicto):
                self.evento(tipo=tipo)
            with self.assertRaises(ValidationError):
                self.evento(tipo=tipo, numero_esperado=3)

    def test_intervalos_pasados_y_futuros_son_solo_propuestos(self):
        for desde, hasta in ((self.desde-timedelta(days=60), self.desde-timedelta(days=30)),
                             (self.hasta+timedelta(days=1), self.hasta+timedelta(days=2))):
            self.assertEqual(self.mandato(vigente_desde_propuesta=desde, vigente_hasta_propuesta=hasta).accion, 'propuesta')
        for hasta in (self.desde, self.desde-timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                self.evento(vigente_hasta_propuesta=hasta)
        with self.assertRaises(ValidationError):
            self.evento(vigente_desde_propuesta=self.desde.replace(tzinfo=None))
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion(vigente_hasta_propuesta=None)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.acreditacion(vigente_desde_propuesta=self.desde-timedelta(seconds=1))

    def test_idempotencia_y_claves_cruzadas(self):
        clave, evidencia = uuid4(), uuid4()
        primero = self.mandato(clave=clave, referencia_evidencia=evidencia)
        antes = CambioAdministrativo.objects.count()
        self.assertEqual(self.mandato(clave=clave, referencia_evidencia=evidencia).pk, primero.pk)
        self.assertEqual(CambioAdministrativo.objects.count(), antes)
        with self.assertRaises(Conflicto):
            self.mandato(clave=clave)
        with self.assertRaises(Conflicto):
            self.acreditacion(clave=clave, referencia_evidencia=evidencia)

    def test_idempotencia_revision_y_acreditacion_no_duplica_historia(self):
        for tipo in ('acreditacion', 'mandato'):
            clave, evidencia = uuid4(), uuid4()
            primero = self.evento(tipo=tipo, clave=clave, referencia_evidencia=evidencia)
            segundo = self.evento(tipo=tipo, clave=clave, referencia_evidencia=evidencia)
            self.assertEqual(primero.pk, segundo.pk)
        clave, evidencia = uuid4(), uuid4()
        actual_m = self.m.eventos.order_by('-numero').first()
        primero = self.acreditacion(clave=clave, referencia_evidencia=evidencia, evento_mandato_id=actual_m.pk)
        self.assertEqual(self.acreditacion(clave=clave, referencia_evidencia=evidencia, evento_mandato_id=actual_m.pk).pk, primero.pk)

    def test_historia_no_se_reescribe_orm_ni_sql(self):
        for objeto in (self.m, self.a, self.evento_m, self.evento_a):
            for operacion in (objeto.save, objeto.delete,
                              lambda: type(objeto).objects.filter(pk=objeto.pk).update(id=objeto.pk),
                              lambda: type(objeto).objects.filter(pk=objeto.pk).delete(),
                              lambda: type(objeto).objects.bulk_update([objeto], ['registrada_en'])):
                with self.assertRaises(ErrorModelo):
                    operacion()
            for sql in (f'UPDATE {objeto._meta.db_table} SET id=id WHERE id=%s',
                        f'DELETE FROM {objeto._meta.db_table} WHERE id=%s'):
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, [objeto.pk])

    def test_sql_rechaza_accion_solicitud_numero_y_actor_invalidos(self):
        for tipo in ('mandato', 'acreditacion'):
            for cambios in (dict(accion='aprobada'), dict(numero=7), dict(solicitud={}),
                            dict(version_enlace_actor=9), dict(actor=self.titular), dict(motivo='  ')):
                with self.subTest(tipo=tipo, cambios=cambios), self.assertRaises(DatabaseError), transaction.atomic():
                    self.raw_evento(tipo=tipo, **cambios)

    def test_sql_rechaza_antecedentes_de_otro_expediente(self):
        otros = {'mandato': self.mandato(), 'acreditacion': self.acreditacion()}
        for tipo, anterior in otros.items():
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.raw_evento(tipo=tipo, anterior=anterior)

    def test_auditoria_eventos_y_relaciones_protegidas(self):
        for evento in (self.evento_m, self.evento_a):
            self.assertTrue(CambioAdministrativo.objects.filter(entidad=evento._meta.label_lower,
                identificador=evento.pk, actor=self.registrador, accion='propuesta').exists())
        for objeto in (self.m, self.b1, self.evento_b1, self.evento_m, self.enlace_reg, self.enlace_tit, self.disciplina):
            with self.assertRaises((ProtectedError, ErrorModelo)):
                objeto.delete()

    def test_fallo_auditoria_revierte_la_operacion(self):
        antes = (MandatoInstitucional.objects.count(), EventoMandatoInstitucional.objects.count())
        with patch('cuentas.servicios_competencias_emisoras.registrar', side_effect=RuntimeError('Auditoría ficticia fallida')):
            with self.assertRaisesRegex(RuntimeError, 'Auditoría ficticia'):
                self.mandato()
        self.assertEqual((MandatoInstitucional.objects.count(), EventoMandatoInstitucional.objects.count()), antes)

    def test_migraciones_anteriores_y_guardias_b1_permanecen(self):
        from django.db.migrations.recorder import MigrationRecorder
        aplicadas = MigrationRecorder(connection).applied_migrations()
        for numero in ('0008_competencia_emisora_b1', '0009_competencia_emisora_guardias_b1',
                       '0010_mandatos_acreditaciones_b2_1', '0011_guardias_mandatos_acreditaciones_b2_1'):
            self.assertIn(('cuentas', numero), aplicadas)
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE cuentas_eventocompetenciaemisora SET motivo=%s WHERE id=%s', ['No permitido', self.evento_b1.pk])

    def test_realizada_sigue_bloqueada_python_y_sql(self):
        from sesiones.ejecucion import verificar_autorizacion_funcional
        from sesiones.models import Sesion
        from organizacion.models import Grupo, Nivel, Periodo
        with self.assertRaises(PermissionDenied):
            verificar_autorizacion_funcional(None, None)
        hoy = timezone.localdate()
        nivel = Nivel.objects.create(disciplina=self.disciplina, codigo='b21', nombre='Fixture')
        periodo = Periodo.objects.create(codigo='b21', nombre='Fixture', fecha_inicio=hoy, fecha_fin=hoy)
        grupo = Grupo.objects.create(codigo='b21', nombre='Fixture', disciplina=self.disciplina,
            nivel=nivel, periodo=periodo, cupo_maximo=5)
        datos = dict(grupo=grupo, profesor=self.candidato, fecha=hoy, hora_inicio=time(10), hora_fin=time(11),
                     creado_por=self.registrador, actualizado_por=self.registrador)
        with self.assertRaises(DatabaseError) as error, transaction.atomic():
            Sesion.objects.create(**datos, estado='realizada', inicio_real=self.desde, fin_real=self.desde+timedelta(hours=1))
        self.assertIn('Validación funcional institucional pendiente', str(error.exception))
        sesion = Sesion.objects.create(**datos)
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE sesiones_sesion SET estado=%s, inicio_real=%s, fin_real=%s WHERE id=%s',
                           ['realizada', self.desde, self.desde+timedelta(hours=1), sesion.pk])


class TransaccionesB21(DatosB21, TransactionTestCase):
    def test_rollback_completo_de_ambos_expedientes_y_auditoria(self):
        modelos = (MandatoInstitucional, EventoMandatoInstitucional, AcreditacionEmisora,
                   EventoAcreditacionEmisora, CambioAdministrativo)
        antes = [m.objects.count() for m in modelos]
        with self.assertRaisesRegex(RuntimeError, 'Fallo posterior ficticio'):
            with transaction.atomic():
                mandato = self.mandato()
                self.acreditacion(mandato_id=mandato.mandato_id, evento_mandato_id=mandato.pk)
                raise RuntimeError('Fallo posterior ficticio')
        self.assertEqual([m.objects.count() for m in modelos], antes)

    def test_primer_evento_obligatorio_en_commit(self):
        self.assertFalse(connection.in_atomic_block)
        antes = MandatoInstitucional.objects.count()
        with self.assertRaises(DatabaseError) as error:
            with transaction.atomic():
                self.cabecera_sin_evento()
                self.assertEqual(MandatoInstitucional.objects.count(), antes+1)
        self.assertEqual(error.exception.__cause__.sqlstate, '23514')
        self.assertIn('incompleto', str(error.exception))
        self.assertEqual(MandatoInstitucional.objects.count(), antes)

    def test_evento_sin_auditoria_falla_en_commit(self):
        antes = EventoMandatoInstitucional.objects.count()
        with self.assertRaises(DatabaseError) as error:
            with transaction.atomic():
                self.raw_evento()
        self.assertEqual(error.exception.__cause__.sqlstate, '23514')
        self.assertEqual(EventoMandatoInstitucional.objects.count(), antes)

    def carrera(self, tipo):
        barrera = Barrier(2)

        def intentar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout='5s'")
                    self.evento(tipo=tipo)
                return 'creada'
            except Conflicto:
                return 'conflicto'
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(intentar, range(2)))
        self.assertCountEqual(resultados, ['creada', 'conflicto'])
        padre = self.m if tipo == 'mandato' else self.a
        self.assertEqual(padre.eventos.count(), 2)

    def test_concurrencia_mandatos_sin_bifurcacion(self):
        self.carrera('mandato')

    def test_concurrencia_acreditaciones_sin_bifurcacion(self):
        self.carrera('acreditacion')

    def test_idempotencia_concurrente_crea_un_solo_expediente(self):
        clave, evidencia, barrera = uuid4(), uuid4(), Barrier(2)
        antes = MandatoInstitucional.objects.count()

        def intentar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout='5s'")
                    return self.mandato(clave=clave, referencia_evidencia=evidencia).pk
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            ids = list(ejecutor.map(intentar, range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(MandatoInstitucional.objects.count(), antes+1)
