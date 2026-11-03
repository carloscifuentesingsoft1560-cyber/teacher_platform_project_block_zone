from uuid import uuid4
from django.test import TestCase
from django.db import IntegrityError, transaction, connection
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario, PertenenciaRol
from organizacion.models import Asignacion, Nivel
from curriculo.models import ProgramaFormativo, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular
from biblioteca.models import Ejercicio, EjercicioVersion, PasoEjercicio
from recursos.editorial import transicion, derivar
from . import tests as dominio
from .models import PlanSesion, TareaSesion, CompetenciaPlan, Asistencia


class IntegracionCurricular(TestCase):
    @classmethod
    def setUpTestData(cls):
        dominio.DominioSesiones.setUpTestData.__func__(cls)
        cls.coord = Usuario.objects.create_user(username='curricular-coord', rol='coordinador')
        cls.programa = ProgramaFormativo.objects.create(nivel=cls.grupo.nivel, formalizado=True)
        cls.malla = Malla.objects.create(codigo='sesiones-malla', nombre='Malla ficticia', programa=cls.programa, autor=cls.actor)
        cls.v = MallaVersion.objects.create(identidad=cls.malla, autor=cls.actor, derechos='Redacción ficticia')
        cls.fase = FaseCurricular.objects.create(version=cls.v, codigo='fase', nombre='Fase ficticia', orden=1)
        cls.semana = SemanaCurricular.objects.create(version=cls.v, fase=cls.fase, ordinal=1)
        cls.clase = ClasePrevista.objects.create(semana=cls.semana, ordinal=1)
        cls.competencia = ElementoCurricular.objects.create(version=cls.v, tipo='competencia', texto='Competencia ficticia de prueba')
        cls.objetivo = ElementoCurricular.objects.create(version=cls.v, tipo='objetivo', texto='Objetivo ficticio')
        cls.publicar(cls.v)
        identidad = Ejercicio.objects.create(codigo='sesiones-ejercicio', nombre='Ficticio', autor=cls.actor)
        cls.e = EjercicioVersion.objects.create(identidad=identidad, autor=cls.actor, disciplina=cls.grupo.disciplina, nombre='Ejercicio ficticio', objetivo='Precisión ficticia', poblacion='Ficticia', metodologia='Juego ficticio', descripcion='Pasos ficticios', riesgos='Riesgo ficticio', controles='Control ficticio', derechos='Propios ficticios', duracion_min=5, duracion_max=30)
        cls.e.programas.add(cls.programa)
        PasoEjercicio.objects.create(version=cls.e, orden=1, instrucciones='Paso ficticio')
        cls.publicar(cls.e)

    @classmethod
    def publicar(cls, version):
        version.refresh_from_db()
        transicion(cls.actor, version, 'proponer', version.revision, uuid4())
        version.refresh_from_db()
        transicion(cls.coord, version, 'aprobar', version.revision, uuid4())
        version.refresh_from_db()

    crear = dominio.DominioSesiones.crear
    comando = dominio.DominioSesiones.comando

    def setUp(self):
        self.sesion = self.crear()
        self.ruta = f'/api/sesiones/{self.sesion.pk}/'
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.actor)

    def datos(self, **cambios):
        datos = dict(clave=str(uuid4()), version=1, objetivo='Objetivo de sesión ficticio', programa_id=self.programa.pk, malla_version_id=self.v.pk, clase_id=self.clase.pk, competencias_ids=[self.competencia.pk], tareas=[dict(fase=f, minutos=20, objetivo='Objetivo de actividad ficticio', instrucciones='Instrucciones propias', ejercicio_version_id=self.e.pk) for f in ('inicial', 'central', 'final')])
        datos.update(cambios)
        return datos

    def guardar(self, **cambios):
        return self.cliente.patch(self.ruta, self.datos(**cambios), format='json')

    def opciones(self, tipo, **filtros):
        return self.cliente.get(self.ruta+'opciones-plan/', dict(tipo=tipo, **filtros))

    def test_selectores_y_plan_completo_ancestros_derivados(self):
        for tipo in ('programas', 'versiones', 'ejercicios', 'fases', 'semanas', 'clases', 'competencias'):
            r = self.opciones(tipo, malla_version=self.v.pk)
            self.assertEqual(r.status_code, 200, r.data)
            self.assertEqual(r.data['count'], 1)
        r = self.guardar()
        self.assertEqual(r.status_code, 200, r.data)
        plan = r.data['planes'][0]
        self.assertEqual(plan['programa'], self.programa.pk)
        self.assertEqual(plan['fase_curricular'], self.fase.pk)
        self.assertEqual(plan['semana'], self.semana.pk)
        self.assertEqual(plan['competencias'][0]['texto'], self.competencia.texto)
        self.assertEqual(plan['tareas'][0]['ejercicio_detalle']['uuid'], str(self.e.uuid))
        self.assertEqual(plan['tareas'][0]['objetivo'], 'Objetivo de actividad ficticio')
        self.assertEqual(self.cliente.get(self.ruta).data['planes'], r.data['planes'])
        self.assertIsNone(r.data['inicio_real'])
        self.assertEqual(r.data['estado'], 'planificada')

    def test_programa_grupo_incompatible(self):
        nivel = Nivel.objects.exclude(pk=self.grupo.nivel_id).first()
        programa = ProgramaFormativo.objects.create(nivel=nivel, formalizado=True)
        self.assertEqual(self.guardar(programa_id=programa.pk).status_code, 400)
        self.assertFalse(PlanSesion.objects.exists())

    def test_estructura_y_competencias_de_otra_version(self):
        copia = derivar(self.actor, self.v)
        for cambios in [dict(malla_version_id=copia.pk), dict(clase_id=copia.semanas.first().clases.first().pk), dict(fase_curricular_id=copia.fases.first().pk), dict(semana_id=copia.semanas.first().pk), dict(competencias_ids=[copia.elementos.filter(tipo='competencia').get().pk]), dict(competencias_ids=[self.objetivo.pk]), dict(competencias_ids=[self.competencia.pk]*2), dict(malla_version_id=None)]:
            r = self.guardar(**cambios)
            self.assertEqual(r.status_code, 400, r.data)
            self.assertIn('detalle', r.data)
        self.assertFalse(PlanSesion.objects.exists())

    def test_fase_y_semana_sin_clase(self):
        r = self.guardar(clase_id=None, semana_id=self.semana.pk, fase_curricular_id=self.fase.pk)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['planes'][0]['clase'])

    def test_ejercicio_retirable_no_seleccionable_y_candidato_no_aprobado(self):
        copia = derivar(self.actor, self.e)
        datos = self.datos()
        datos['tareas'][0]['ejercicio_version_id'] = copia.pk
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 400)
        transicion(self.coord, self.e, 'retirar', self.e.revision, uuid4(), 'Retiro ficticio')
        self.assertEqual(self.opciones('ejercicios').data['count'], 0)
        self.assertEqual(self.guardar().status_code, 400)
        copia.refresh_from_db()
        self.assertEqual(copia.estado, 'borrador')

    def test_ejercicio_otro_programa_y_acceso_tecnico_no_bastan(self):
        copia = derivar(self.actor, self.e)
        copia.programas.clear()
        copia.acceso_tecnico = True
        copia.save()
        self.publicar(copia)
        datos = self.datos()
        datos['tareas'][0]['ejercicio_version_id'] = copia.pk
        self.cliente.force_authenticate(self.admin)
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 400)

    def test_ejercicio_aprobado_de_otro_programa_no_es_compatible(self):
        otro = ProgramaFormativo.objects.create(nivel=Nivel.objects.exclude(pk=self.grupo.nivel_id).first(), formalizado=True)
        copia = derivar(self.actor, self.e)
        copia.programas.set([otro])
        self.publicar(copia)
        datos = self.datos()
        for tarea in datos['tareas']:
            tarea['ejercicio_version_id'] = copia.pk
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 400)
        self.assertEqual(self.opciones('ejercicios').data['count'], 0)

    def test_malla_retirada_no_se_selecciona_pero_historia_permanece(self):
        self.assertEqual(self.guardar().status_code, 200)
        transicion(self.coord, self.v, 'retirar', self.v.revision, uuid4(), 'Retiro curricular ficticio')
        self.assertEqual(self.opciones('versiones').data['count'], 0)
        self.assertEqual(self.guardar(version=2).status_code, 400)
        self.assertEqual(self.cliente.get(self.ruta).data['planes'][0]['contexto_curricular']['estado_actual'], 'retirado')

    def test_historia_publicacion_y_reintento_tras_retiro(self):
        datos = self.datos()
        r = self.cliente.patch(self.ruta, datos, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        plan_id = r.data['planes'][0]['id']
        nueva = derivar(self.actor, self.v)
        self.publicar(nueva)
        transicion(self.coord, self.e, 'retirar', self.e.revision, uuid4(), 'Retiro ficticio')
        self.assertEqual(self.opciones('versiones').data['results'][0]['id'], nueva.pk)
        detalle = self.cliente.get(self.ruta).data['planes'][0]
        self.assertEqual(detalle['malla_version'], self.v.pk)
        self.assertEqual(detalle['tareas'][0]['ejercicio_version'], self.e.pk)
        self.assertFalse(detalle['contexto_curricular']['vigente_actual'])
        self.assertEqual(detalle['tareas'][0]['ejercicio_detalle']['estado_actual'], 'retirado')
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 200)
        self.assertEqual(self.guardar(version=2).status_code, 400)
        self.assertEqual(PlanSesion.objects.get().pk, plan_id)

    def test_original_y_revisiones_congelados_en_sql(self):
        self.assertEqual(self.guardar().status_code, 200)
        original = PlanSesion.objects.get()
        self.assertEqual(self.guardar(version=2, objetivo='Revisión propia').status_code, 200)
        revision = PlanSesion.objects.order_by('-numero').first()
        self.assertEqual(revision.revision_anterior_id, original.pk)
        self.assertEqual(original.objetivo, 'Objetivo de sesión ficticio')
        acciones = [lambda: PlanSesion.objects.filter(pk=original.pk).update(objetivo='Alterado'), lambda: connection.cursor().execute('DELETE FROM sesiones_plansesion WHERE id=%s', [original.pk]), lambda: original.tareas.update(minutos=10), lambda: original.tareas.all().delete(), lambda: CompetenciaPlan.objects.filter(plan=original).delete(), lambda: TareaSesion.objects.create(plan=original, orden=4, fase='final', minutos=1, instrucciones='Ajena'), lambda: CompetenciaPlan.objects.create(plan=original, competencia=self.objetivo)]
        for accion in acciones:
            with self.assertRaises(IntegrityError), transaction.atomic():
                accion()

    def test_duraciones_y_objetivos_propios_sin_curriculo(self):
        datos = self.datos()
        datos['tareas'][0]['minutos'] = 19
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 400)
        datos['tareas'][0]['minutos'] = 1
        datos['tareas'][1]['minutos'] = 39
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 400)
        self.assertFalse(PlanSesion.objects.exists())
        datos = self.datos(malla_version_id=None, clase_id=None, competencias_ids=[], programa_id=None)
        for tarea in datos['tareas']:
            tarea.pop('ejercicio_version_id')
        self.assertEqual(self.cliente.patch(self.ruta, datos, format='json').status_code, 200)

    def test_permisos_roles_revocacion_y_ejecucion_bloqueada(self):
        self.assertEqual(self.guardar().status_code, 200)
        self.cliente.force_authenticate(self.otro)
        self.assertEqual(self.opciones('versiones').status_code, 404)
        self.assertEqual(self.cliente.get(self.ruta).status_code, 404)
        self.cliente.force_authenticate(self.actor)
        PertenenciaRol.objects.create(usuario=self.actor, rol='acudiente')
        self.assertEqual(self.opciones('versiones').status_code, 200)
        PertenenciaRol.objects.filter(usuario=self.actor, rol='profesor').update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.opciones('versiones').status_code, 403)
        self.cliente.force_authenticate(self.admin)
        self.assertEqual(self.opciones('versiones').status_code, 200)
        self.assertEqual(self.cliente.post(self.ruta+'realizar/', {}, format='json').status_code, 400)

    def test_errores_selector_y_version_conflicto(self):
        for tipo, filtros in [('desconocido', {}), ('clases', {}), ('semanas', {'malla_version': 'x'}), ('competencias', {'malla_version': 99999})]:
            self.assertEqual(self.opciones(tipo, **filtros).status_code, 400)
        self.assertEqual(self.guardar().status_code, 200)
        self.assertEqual(self.guardar().status_code, 409)


from django.test import TransactionTestCase
from django.db import close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from organizacion.models import Disciplina


@skipUnless(connection.vendor == 'postgresql', 'Requiere PostgreSQL real')
class ConcurrenciaCurricular(TransactionTestCase):
    publicar = classmethod(IntegracionCurricular.publicar.__func__)
    crear = dominio.DominioSesiones.crear
    datos = IntegracionCurricular.datos

    def setUp(self):
        disciplina, _ = Disciplina.objects.get_or_create(codigo='escalada', defaults={'nombre': 'Ficticia'})
        Nivel.objects.get_or_create(disciplina=disciplina, codigo='nivel-1', defaults={'nombre': 'Ficticio'})
        IntegracionCurricular.setUpTestData.__func__(type(self))
        self.sesion = self.crear()

    def test_retiro_concurrente_con_plan_no_admite_referencia_obsoleta(self):
        barrera = Barrier(2)

        def planificar():
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.actor.pk))
                barrera.wait(timeout=10)
                return cliente.patch(f'/api/sesiones/{self.sesion.pk}/', self.datos(), format='json').status_code
            finally:
                close_old_connections()

        def retirar():
            close_old_connections()
            try:
                actor = Usuario.objects.get(pk=self.coord.pk)
                version = EjercicioVersion.objects.get(pk=self.e.pk)
                barrera.wait(timeout=10)
                transicion(actor, version, 'retirar', version.revision, uuid4(), 'Retiro concurrente ficticio')
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            plan = pool.submit(planificar)
            retiro = pool.submit(retirar)
            estado = plan.result(timeout=30)
            retiro.result(timeout=30)
        self.assertIn(estado, [200, 400])
        self.assertEqual(PlanSesion.objects.count(), int(estado == 200))
        self.e.refresh_from_db()
        self.assertEqual(self.e.estado, 'retirado')
        if estado == 200:
            self.assertEqual(PlanSesion.objects.get().tareas.first().ejercicio_version_id, self.e.pk)


@skipUnless(connection.vendor == 'postgresql', 'Migración PostgreSQL')
class MigracionPlanesExistentes(TransactionTestCase):
    crear = dominio.DominioSesiones.crear

    def test_actualizacion_preserva_planes_previos_y_sella_sus_tareas(self):
        from django.db.migrations.executor import MigrationExecutor
        dominio.ConcurrenciaSesiones.setUp(self)
        sesion = self.crear()
        destino = [('sesiones', '0005_cierre_definitivo')]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([('sesiones', '0001_initial')])
            apps = executor.loader.project_state([('sesiones', '0001_initial')]).apps
            PlanAnterior = apps.get_model('sesiones', 'PlanSesion')
            TareaAnterior = apps.get_model('sesiones', 'TareaSesion')
            planes = []
            for numero in (1, 2):
                plan = PlanAnterior.objects.create(sesion_id=sesion.pk, numero=numero, autor_id=self.actor.pk, objetivo=f'Plan histórico ficticio {numero}')
                for orden, fase in enumerate(('inicial', 'central', 'final'), 1):
                    TareaAnterior.objects.create(plan=plan, orden=orden, fase=fase, minutos=20, instrucciones='Original ficticia')
                planes.append(plan.pk)
            MigrationExecutor(connection).migrate(destino)
            original, revision = list(PlanSesion.objects.order_by('numero'))
            self.assertEqual([original.pk, revision.pk], planes)
            self.assertTrue(original.sellado and revision.sellado)
            self.assertEqual(revision.revision_anterior_id, original.pk)
            self.assertIsNone(original.programa_id)
            self.assertEqual(original.tareas.count(), 3)
            self.assertEqual(Asistencia.objects.get().deportista_id, self.inscripcion.deportista_id)
            with self.assertRaises(IntegrityError), transaction.atomic():
                original.tareas.update(instrucciones='Alteración')
        finally:
            MigrationExecutor(connection).migrate(destino)
