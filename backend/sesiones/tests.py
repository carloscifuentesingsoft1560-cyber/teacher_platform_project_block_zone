from datetime import date, timedelta
from uuid import uuid4
from django.test import TestCase
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from cuentas.models import Usuario
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Asignacion
from deportistas.models import Deportista
from inscripciones.models import Inscripcion
from .models import Sesion, PlanSesion, Asistencia, EventoSesion
from .servicios import crear_sesion, comandar, Conflicto


class DominioSesiones(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fecha = date(2026, 11, 2)
        cls.actor = Usuario.objects.create_user(username='sesiones-profe', rol='profesor')
        cls.admin = Usuario.objects.create_user(username='sesiones-admin', rol='administrador')
        cls.otro = Usuario.objects.create_user(username='sesiones-otro', rol='profesor')
        disciplina = Disciplina.objects.get(codigo='escalada')
        nivel = Nivel.objects.get(codigo='nivel-1')
        periodo = Periodo.objects.create(codigo='sesiones', nombre='Pruebas', fecha_inicio=cls.fecha-timedelta(days=30), fecha_fin=cls.fecha+timedelta(days=30))
        cls.grupo = Grupo.objects.create(codigo='sesiones', nombre='Pruebas', disciplina=disciplina, nivel=nivel, periodo=periodo, cupo_maximo=10)
        Asignacion.objects.create(grupo=cls.grupo, usuario=cls.actor, tipo='profesor', fecha_inicio=periodo.fecha_inicio)
        deportista = Deportista.objects.create(nombres='Ficticio', apellidos='Prueba', fecha_nacimiento=date(2010, 1, 1), creado_por=cls.admin, actualizado_por=cls.admin)
        cls.inscripcion = Inscripcion.objects.create(grupo=cls.grupo, deportista=deportista, fecha_ingreso=cls.fecha, creado_por=cls.admin, actualizado_por=cls.admin)

    def crear(self, **cambios):
        datos = dict(actor=self.actor, clave=uuid4(), grupo_id=self.grupo.pk, profesor_id=self.actor.pk, fecha=self.fecha, hora_inicio='10:00', hora_fin='11:00')
        datos.update(cambios)
        return crear_sesion(**datos)

    def comando(self, sesion, operacion, datos, **cambios):
        argumentos = dict(actor=self.actor, sesion_id=sesion.pk, version=sesion.version, clave=uuid4(), operacion=operacion, datos=datos)
        argumentos.update(cambios)
        return comandar(**argumentos)

    def plan(self, sesion, minutos=20):
        return self.comando(sesion, 'planificar', {'objetivo': 'Objetivo ficticio', 'tareas': [dict(fase=f, minutos=minutos, instrucciones='Actividad propia ficticia') for f in ['inicial', 'central', 'final']]})

    def realizada(self):
        s = self.plan(self.crear())
        return self.comando(s, 'realizar', {'inicio': '2026-11-02T10:00:00-05:00', 'fin': '2026-11-02T11:00:00-05:00'})

    def test_creacion_padron_e_idempotencia(self):
        clave = uuid4()
        s = self.crear(clave=clave)
        self.assertEqual(self.crear(clave=clave).pk, s.pk)
        self.assertEqual(Sesion.objects.count(), 1)
        self.assertEqual(s.asistencias.get().inscripcion, self.inscripcion)
        self.assertEqual(s.asistencias.get().estado, '')
        with self.assertRaises(Conflicto):
            self.crear(clave=clave, hora_inicio='12:00', hora_fin='13:00')

    def test_maximo_dos_cancelacion_y_solapamiento(self):
        s = self.crear()
        with self.assertRaises(ValidationError):
            self.crear(hora_inicio='10:30', hora_fin='11:30')
        self.crear(hora_inicio='12:00', hora_fin='13:00')
        with self.assertRaises(ValidationError):
            self.crear(hora_inicio='14:00', hora_fin='15:00')
        self.comando(s, 'cancelar', {'motivo': 'Prueba'})
        self.crear(hora_inicio='14:00', hora_fin='15:00')

    def test_ajeno_y_revocacion_incluso_reintento(self):
        clave = uuid4()
        self.crear(clave=clave)
        with self.assertRaises(PermissionDenied):
            self.crear(actor=self.otro)
        Asignacion.objects.filter(usuario=self.actor).update(fecha_fin=self.fecha-timedelta(days=1))
        with self.assertRaises(PermissionDenied):
            self.crear(clave=clave)

    def test_version_y_plan_atomico(self):
        s = self.crear()
        with self.assertRaises(ValidationError):
            self.plan(s, minutos=10)
        self.assertFalse(PlanSesion.objects.exists())
        s = self.plan(s)
        with self.assertRaises(Conflicto):
            self.comando(s, 'cancelar', {'motivo': 'Prueba'}, version=1)
        self.assertEqual(s.planes.get().tareas.count(), 3)

    def test_ejecucion_y_asistencia_separadas_correccion_con_historia(self):
        s = self.realizada()
        self.assertFalse(s.asistencia_confirmada)
        self.assertIsNotNone(s.plan_ejecutado_id)
        with self.assertRaises(ValidationError):
            self.comando(s, 'confirmar_asistencia', {'registros': {}})
        self.assertEqual(s.asistencias.get().estado, '')
        datos = {'registros': {str(self.inscripcion.pk): 'tarde'}}
        clave = uuid4()
        version = s.version
        s = self.comando(s, 'confirmar_asistencia', datos, clave=clave)
        self.comando(s, 'confirmar_asistencia', datos, clave=clave, version=version)
        self.assertEqual(s.eventos.filter(operacion='confirmar_asistencia').count(), 1)
        with self.assertRaises(ValidationError):
            self.comando(s, 'confirmar_asistencia', datos)
        correccion = {'registros': {str(self.inscripcion.pk): 'asistio'}, 'motivo': 'Rectificación ficticia'}
        with self.assertRaises(PermissionDenied):
            self.comando(s, 'corregir_asistencia', correccion)
        s = self.comando(s, 'corregir_asistencia', correccion, actor=self.admin)
        evento = s.eventos.get(operacion='corregir_asistencia')
        self.assertEqual(evento.detalle['anterior'][str(self.inscripcion.pk)], 'tarde')
        self.assertTrue(evento.detalle['evento_anterior'])

    def test_padron_no_se_recalcula_y_referencia_protegida(self):
        s = self.crear()
        self.inscripcion.fecha_salida = self.fecha+timedelta(days=1)
        self.inscripcion.estado = 'finalizada'
        self.inscripcion.causa_salida = 'retiro'
        self.inscripcion.save()
        self.assertEqual(s.asistencias.get().inscripcion_id, self.inscripcion.pk)
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.inscripcion.delete()

    def test_restricciones_base_de_datos(self):
        s = self.crear()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asistencia.objects.create(sesion=s, inscripcion=self.inscripcion)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sesion.objects.filter(pk=s.pk).update(asistencia_confirmada=True)

    def test_fecha_fuera_periodo_y_cuenta_inactiva(self):
        with self.assertRaises(ValidationError):
            self.crear(fecha=self.fecha+timedelta(days=60))
        Usuario.objects.filter(pk=self.actor.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.crear()

    def test_asistencia_planificada_y_cancelada_bloqueadas(self):
        s = self.crear()
        datos = {'registros': {str(self.inscripcion.pk): 'asistio'}}
        with self.assertRaises(ValidationError):
            self.comando(s, 'confirmar_asistencia', datos)
        s = self.comando(s, 'cancelar', {'motivo': 'Prueba'})
        with self.assertRaises(ValidationError):
            self.plan(s)

    def test_plan_revisado_conserva_original_y_no_edita_ejecucion(self):
        s = self.plan(self.crear())
        original = s.planes.get()
        s = self.plan(s)
        self.assertEqual(s.planes.count(), 2)
        self.assertEqual(original.tareas.count(), 3)
        s = self.comando(s, 'realizar', {'inicio': '2026-11-02T10:00:00-05:00', 'fin': '2026-11-02T11:00:00-05:00'})
        self.assertEqual(s.plan_ejecutado.numero, 2)
        with self.assertRaises(ValidationError):
            self.plan(s)

    def test_malla_borrador_y_clase_ajena_rechazadas(self):
        from curriculo.models import ProgramaFormativo, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista
        programa = ProgramaFormativo.objects.create(nivel=self.grupo.nivel)
        malla = Malla.objects.create(programa=programa, codigo='prueba-sesiones', nombre='Ficticia', autor=self.actor)
        v = MallaVersion.objects.create(identidad=malla, autor=self.actor)
        fase = FaseCurricular.objects.create(version=v, codigo='f', nombre='Ficticia', orden=1)
        semana = SemanaCurricular.objects.create(version=v, fase=fase, ordinal=1)
        clase = ClasePrevista.objects.create(semana=semana, ordinal=1)
        s = self.crear()
        datos = {'objetivo': 'Ficticio', 'malla_version_id': v.pk, 'tareas': [dict(fase=f, minutos=20, instrucciones='Ficticia') for f in ['inicial', 'central', 'final']]}
        with self.assertRaises(ValidationError):
            self.comando(s, 'planificar', datos)
        datos.pop('malla_version_id')
        datos['clase_id'] = clase.pk
        with self.assertRaises(ValidationError):
            self.comando(s, 'planificar', datos)
        self.assertFalse(s.planes.exists())

    def test_gestor_puede_corregir_tras_baja_del_profesor(self):
        s = self.realizada()
        datos = {'registros': {str(self.inscripcion.pk): 'no_asistio'}}
        s = self.comando(s, 'confirmar_asistencia', datos)
        Usuario.objects.filter(pk=self.actor.pk).update(is_active=False)
        s = self.comando(s, 'corregir_asistencia', dict(datos, motivo='Revisión ficticia'), actor=self.admin)
        self.assertTrue(s.asistencia_confirmada)


from django.test import TransactionTestCase
from django.db import connection, close_old_connections
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier


@skipUnless(connection.vendor == 'postgresql', 'Requiere bloqueos reales PostgreSQL')
class ConcurrenciaSesiones(TransactionTestCase):
    def setUp(self):
        disciplina, _ = Disciplina.objects.get_or_create(codigo='escalada', defaults={'nombre': 'Escalada ficticia'})
        Nivel.objects.get_or_create(codigo='nivel-1', disciplina=disciplina, defaults={'nombre': 'Nivel ficticio'})
        DominioSesiones.setUpTestData.__func__(type(self))

    crear = DominioSesiones.crear

    def paralelas(self, entradas):
        barrera = Barrier(2)

        def ejecutar(entrada):
            close_old_connections()
            try:
                actor = Usuario.objects.get(pk=self.actor.pk)
                barrera.wait(timeout=10)
                return crear_sesion(actor=actor, grupo_id=self.grupo.pk, profesor_id=actor.pk, fecha=self.fecha, **entrada).pk
            except ValidationError:
                return 'rechazada'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, entradas))

    def test_limite_diario_serializado(self):
        self.crear()
        resultado = self.paralelas([dict(clave=uuid4(), hora_inicio='12:00', hora_fin='13:00'), dict(clave=uuid4(), hora_inicio='14:00', hora_fin='15:00')])
        self.assertEqual(resultado.count('rechazada'), 1)
        self.assertEqual(Sesion.objects.count(), 2)

    def test_reintento_concurrente_un_solo_evento(self):
        entrada = dict(clave=uuid4(), hora_inicio='10:00', hora_fin='11:00')
        resultado = self.paralelas([entrada, entrada])
        self.assertEqual(resultado[0], resultado[1])
        self.assertEqual(EventoSesion.objects.count(), 1)
