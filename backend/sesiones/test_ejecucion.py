from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.db import transaction, IntegrityError, connection, close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario, PertenenciaRol
from organizacion.models import Asignacion, Grupo
from deportistas.models import Deportista
from inscripciones.models import Inscripcion
from . import tests as dominio
from .models import Sesion, Asistencia, PlanSesion, EjecucionSesion, ActividadEjecutada, CorreccionAsistencia, EventoSesion


class RegistroEjecucion(TestCase):
    @classmethod
    def setUpTestData(cls):
        dominio.DominioSesiones.setUpTestData.__func__(cls)

    crear = dominio.DominioSesiones.crear
    plan = dominio.DominioSesiones.plan
    comando = dominio.DominioSesiones.comando

    def setUp(self):
        self.sesion = self.plan(self.crear())
        self.version = self.sesion.version
        self.plan_elegido = self.sesion.planes.get()
        self.ruta = f'/api/sesiones/{self.sesion.pk}/'
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.actor)

    def post(self, ruta, datos=None, **cambios):
        entrada = dict(clave=str(uuid4()), version=self.version, **(datos or {}))
        entrada.update(cambios)
        r = self.cliente.post(self.ruta+ruta+'/', entrada, format='json')
        if r.status_code == 200:
            self.version = r.data['sesion']['version']
        return r

    def datos_ejecucion(self):
        tareas = list(self.plan_elegido.tareas.all())
        return dict(plan=self.plan_elegido.pk, inicio=f'{self.fecha}T10:00:00-05:00', fin=f'{self.fecha}T10:45:00-05:00', observaciones='Observación pedagógica ficticia', incidencias_pedagogicas='Incidencia pedagógica ficticia', actividades=[dict(tarea=tareas[0].pk, resultado='realizada', minutos=10, descripcion='Actividad prevista realizada'), dict(tarea=tareas[1].pk, resultado='modificada', minutos=20, descripcion='Actividad modificada', adaptacion_metodologica='Cambio metodológico ficticio'), dict(tarea=tareas[2].pk, resultado='omitida', minutos=0, motivo_omision='Falta de tiempo ficticia')])

    def guardar_asistencia(self, estado='asistio'):
        registros = {str(a.inscripcion_id): estado for a in self.sesion.asistencias.all()}
        r = self.post('asistencia', dict(registros=registros))
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def finalizar(self):
        self.assertEqual(self.post('ejecucion', self.datos_ejecucion()).status_code, 200)
        self.guardar_asistencia()
        r = self.post('ejecucion/finalizar')
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def nuevo_participante(self, **cambios):
        persona = Deportista.objects.create(nombres='Ficticio', apellidos=str(uuid4()), fecha_nacimiento=self.fecha.replace(year=2010), creado_por=self.admin, actualizado_por=self.admin)
        datos = dict(grupo=self.grupo, deportista=persona, fecha_ingreso=self.fecha, creado_por=self.admin, actualizado_por=self.admin)
        datos.update(cambios)
        return Inscripcion.objects.create(**datos)

    def test_registro_y_consulta_distinguen_resultados_y_duracion(self):
        r = self.post('ejecucion', self.datos_ejecucion())
        self.assertEqual(r.status_code, 200, r.data)
        datos = self.cliente.get(self.ruta+'ejecucion/').data['ejecucion']
        self.assertEqual(datos['duracion_real_minutos'], 45)
        self.assertEqual(datos['tiempo_no_distribuido_minutos'], 15)
        self.assertEqual({a['resultado'] for a in datos['actividades']}, {'realizada', 'modificada', 'omitida'})
        self.assertEqual(datos['plan']['id'], self.plan_elegido.pk)
        self.assertIsNone(datos['finalizada_en'])
        self.assertEqual(self.plan_elegido.tareas.get(orden=1).minutos, 20)

    def test_cierre_registro_y_asistencia_sin_autorizar_practica(self):
        r = self.finalizar()
        self.assertTrue(r.data['sesion']['asistencia_confirmada'])
        self.assertEqual(r.data['sesion']['estado_ejecucion'], 'registrada_pendiente_validacion')
        self.assertEqual(r.data['sesion']['estado'], 'planificada')
        r = self.post('realizar')
        self.assertEqual(r.status_code, 403, r.data)
        self.assertIn('autorización funcional', str(r.data))
        self.sesion.refresh_from_db()
        self.assertIsNone(self.sesion.plan_ejecutado_id)
        self.assertEqual(self.sesion.estado, 'planificada')
        ejecucion = EjecucionSesion.objects.get()
        self.assertEqual(ejecucion.finalizada_por_id, self.actor.pk)
        self.assertIsNotNone(ejecucion.finalizada_en)

    def test_cierre_incompleto_y_error_evento_revierten_todo(self):
        self.assertEqual(self.post('ejecucion', self.datos_ejecucion()).status_code, 200)
        self.assertEqual(self.post('ejecucion/finalizar').status_code, 400)
        self.assertFalse(Sesion.objects.get().asistencia_confirmada)
        self.assertIsNone(EjecucionSesion.objects.get().finalizada_en)
        self.guardar_asistencia()
        version = self.version
        with patch('sesiones.ejecucion._evento', side_effect=RuntimeError('Fallo ficticio')), self.assertRaises(RuntimeError):
            self.post('ejecucion/finalizar')
        self.assertEqual(Sesion.objects.get().version, version)
        self.assertFalse(Sesion.objects.get().asistencia_confirmada)
        self.assertIsNone(EjecucionSesion.objects.get().finalizada_en)

    def test_cierre_idempotente_y_claves_reutilizadas(self):
        datos = self.datos_ejecucion()
        clave = str(uuid4())
        version = self.version
        self.assertEqual(self.post('ejecucion', datos, clave=clave).status_code, 200)
        self.assertEqual(self.post('ejecucion', datos, clave=clave, version=version).status_code, 200)
        self.assertEqual(EjecucionSesion.objects.count(), 1)
        self.assertEqual(EventoSesion.objects.filter(operacion='guardar_ejecucion').count(), 1)
        self.assertEqual(self.post('ejecucion', dict(datos, observaciones='Otra'), clave=clave, version=version).status_code, 409)
        self.guardar_asistencia()
        clave, version = str(uuid4()), self.version
        self.assertEqual(self.post('ejecucion/finalizar', clave=clave).status_code, 200)
        self.assertEqual(self.post('ejecucion/finalizar', clave=clave, version=version).status_code, 200)
        self.assertEqual(self.post('ejecucion/finalizar').status_code, 400)
        self.assertEqual(EventoSesion.objects.filter(operacion='finalizar_ejecucion').count(), 1)

    def test_inmutabilidad_sql_y_api_despues_del_cierre(self):
        self.finalizar()
        acciones = [lambda: EjecucionSesion.objects.update(observaciones='Alterado'), lambda: EjecucionSesion.objects.all().delete(), lambda: ActividadEjecutada.objects.update(minutos=2), lambda: ActividadEjecutada.objects.all().delete(), lambda: Asistencia.objects.update(estado='tarde'), lambda: Asistencia.objects.all().delete(), lambda: Sesion.objects.update(fecha=self.fecha+timedelta(days=1)), lambda: Sesion.objects.update(asistencia_confirmada=False), lambda: EventoSesion.objects.update(detalle={}), lambda: EventoSesion.objects.all().delete()]
        for accion in acciones:
            with self.assertRaises(IntegrityError), transaction.atomic():
                accion()
        self.assertEqual(self.post('ejecucion', self.datos_ejecucion()).status_code, 400)
        self.assertEqual(self.post('asistencia', dict(registros={str(self.inscripcion.pk): 'tarde'})).status_code, 400)
        self.assertEqual(self.post('asistencia/preparar', dict(motivo='Cambio')).status_code, 400)
        r = self.cliente.patch(self.ruta, dict(version=self.version, clave=str(uuid4()), objetivo='Cambio', tareas=[dict(fase=f, minutos=20, instrucciones='Cambio') for f in ('inicial', 'central', 'final')]), format='json')
        self.assertEqual(r.status_code, 400)

    def test_duracion_fechas_obligatorios_y_tareas_ajenas(self):
        variantes = []
        for cambio in [dict(fin=f'{self.fecha}T09:00:00-05:00'), dict(inicio=f'{self.fecha}T10:00:00'), dict(plan=999999), dict(actividades=[]), dict(inicio=f'{self.fecha+timedelta(days=1)}T10:00:00-05:00')]:
            variantes.append(dict(self.datos_ejecucion(), **cambio))
        for tipo in ('minutos', 'tarea', 'adaptacion'):
            datos = self.datos_ejecucion()
            if tipo == 'minutos': datos['actividades'][0]['minutos'] = 100
            if tipo == 'tarea': datos['actividades'][0]['tarea'] = datos['actividades'][1]['tarea']
            if tipo == 'adaptacion': datos['actividades'][1].pop('adaptacion_metodologica')
            variantes.append(datos)
        for datos in variantes:
            r = self.post('ejecucion', datos)
            self.assertIn(r.status_code, (400, 404), r.data)
        self.assertFalse(EjecucionSesion.objects.exists())

    def test_todos_los_estados_y_resumen_cerrado(self):
        for _ in range(4): self.nuevo_participante()
        self.assertEqual(self.post('asistencia/preparar', dict(motivo='Matrículas ficticias nuevas')).status_code, 200)
        estados = ('asistio', 'no_asistio', 'tarde', 'excusa', 'retiro')
        ids = list(self.sesion.asistencias.order_by('pk').values_list('inscripcion_id', flat=True))
        self.assertEqual(self.post('asistencia', dict(registros={str(i):e for i,e in zip(ids, estados)})).status_code, 200)
        self.assertEqual(self.post('asistencia/cerrar').status_code, 200)
        resumen = self.cliente.get(self.ruta+'asistencia/resumen/').data
        self.assertTrue(resumen['cerrada'])
        self.assertEqual(resumen['total'], 5)
        self.assertEqual(resumen['sin_registrar'], 0)
        self.assertEqual(resumen['estados'], {e:1 for e in estados})

    def test_elegibilidad_fecha_grupo_y_preparacion_explicita(self):
        incluida = self.nuevo_participante()
        self.nuevo_participante(fecha_ingreso=self.fecha+timedelta(days=1))
        self.nuevo_participante(fecha_ingreso=self.fecha-timedelta(days=1), fecha_salida=self.fecha, estado='finalizada', causa_salida='retiro')
        ajeno = Grupo.objects.create(codigo='ejecucion-ajeno', nombre='Ajeno ficticio', disciplina=self.grupo.disciplina, nivel=self.grupo.nivel, periodo=self.grupo.periodo, cupo_maximo=10)
        self.nuevo_participante(grupo=ajeno)
        participantes = self.cliente.get(self.ruta+'participantes/').data
        self.assertEqual(len(participantes['participantes']), 2)
        self.assertTrue(participantes['requiere_preparacion'])
        self.assertEqual(self.post('asistencia', dict(registros={str(self.inscripcion.pk): 'asistio'})).status_code, 400)
        self.assertEqual(self.post('asistencia/preparar', dict(motivo='Actualizar padrón ficticio')).status_code, 200)
        self.assertEqual(set(self.sesion.asistencias.values_list('inscripcion_id', flat=True)), {self.inscripcion.pk, incluida.pk})
        self.guardar_asistencia()
        self.assertEqual(self.post('asistencia/cerrar').status_code, 200)
        incluida.fecha_ingreso = self.fecha+timedelta(days=1)
        incluida.save()
        self.assertEqual(len(self.cliente.get(self.ruta+'asistencia/').data['participantes']), 2)

    def test_un_registro_por_persona_y_inscripciones_superpuestas(self):
        Inscripcion.objects.create(grupo=self.grupo, deportista=self.inscripcion.deportista, fecha_ingreso=self.fecha-timedelta(days=2), fecha_salida=self.fecha+timedelta(days=1), estado='finalizada', causa_salida='retiro', creado_por=self.admin, actualizado_por=self.admin)
        self.assertEqual(self.post('asistencia/preparar', dict(motivo='Prueba')).status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asistencia.objects.create(sesion=self.sesion, inscripcion=self.inscripcion, deportista=self.inscripcion.deportista)

    def test_objetos_ajenos_y_roles_no_docentes_no_reciben_personas(self):
        self.cliente.force_authenticate(self.otro)
        for ruta in ('participantes', 'asistencia', 'asistencia/resumen', 'ejecucion'):
            self.assertEqual(self.cliente.get(self.ruta+ruta+'/').status_code, 404)
        for rol in ('acudiente', 'deportista'):
            actor = Usuario.objects.create_user(username='sin-acceso-'+rol, rol=rol)
            self.cliente.force_authenticate(actor)
            self.assertEqual(self.cliente.get(self.ruta+'participantes/').status_code, 403)
        self.cliente.force_authenticate(self.admin)
        self.assertEqual(self.post('ejecucion', self.datos_ejecucion()).status_code, 403)

    def test_revocacion_rol_y_asignacion_bloquean_incluso_reintento(self):
        datos, clave, version = self.datos_ejecucion(), str(uuid4()), self.version
        self.assertEqual(self.post('ejecucion', datos, clave=clave).status_code, 200)
        Asignacion.objects.filter(usuario=self.actor).update(fecha_fin=self.fecha-timedelta(days=1))
        self.assertEqual(self.post('ejecucion', datos, clave=clave, version=version).status_code, 404)
        Asignacion.objects.filter(usuario=self.actor).update(fecha_fin=None)
        PertenenciaRol.objects.create(usuario=self.actor, rol='acudiente')
        PertenenciaRol.objects.filter(usuario=self.actor, rol='profesor').update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.post('ejecucion', datos, clave=clave, version=version).status_code, 403)

    def test_correccion_administrativa_auditada_y_coordinador_denegado(self):
        self.guardar_asistencia('tarde')
        self.assertEqual(self.post('asistencia/cerrar').status_code, 200)
        datos = dict(deportista=self.inscripcion.deportista_id, anterior='tarde', nuevo='asistio', motivo='Rectificación ficticia contrastada')
        self.assertEqual(self.post('asistencia/corregir', datos).status_code, 403)
        coordinador = Usuario.objects.create_user(username='ejecucion-coord', rol='coordinador')
        self.cliente.force_authenticate(coordinador)
        self.assertEqual(self.post('asistencia/corregir', datos).status_code, 403)
        self.cliente.force_authenticate(self.admin)
        clave, version = str(uuid4()), self.version
        r = self.post('asistencia/corregir', datos, clave=clave)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.post('asistencia/corregir', datos, clave=clave, version=version).status_code, 200)
        self.assertEqual(self.post('asistencia/corregir', datos).status_code, 409)
        correccion = CorreccionAsistencia.objects.get()
        self.assertEqual(correccion.anterior, 'tarde')
        self.assertEqual(correccion.nuevo, 'asistio')
        self.assertEqual(correccion.actor, self.admin)
        self.assertIsNotNone(correccion.registrada_en)
        self.assertEqual(self.sesion.asistencias.get().estado, 'asistio')
        self.assertIsNotNone(correccion.evento.detalle['evento_anterior'])
        self.assertEqual(len(self.cliente.get(self.ruta+'asistencia/').data['correcciones']), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CorreccionAsistencia.objects.update(motivo='Alterar')
        with self.assertRaises(IntegrityError), transaction.atomic():
            CorreccionAsistencia.objects.all().delete()

    def test_correccion_exige_cierre_motivo_valor_anterior_y_facultad_actual(self):
        self.cliente.force_authenticate(self.admin)
        datos = dict(deportista=self.inscripcion.deportista_id, anterior='asistio', nuevo='excusa', motivo='Prueba')
        self.assertEqual(self.post('asistencia/corregir', datos).status_code, 400)
        self.cliente.force_authenticate(self.actor)
        self.guardar_asistencia()
        self.assertEqual(self.post('asistencia/cerrar').status_code, 200)
        self.cliente.force_authenticate(self.admin)
        for cambio, estado in [(dict(motivo=''), 400), (dict(anterior='retiro'), 409), (dict(nuevo='asistio'), 400), (dict(deportista=999999), 404)]:
            self.assertEqual(self.post('asistencia/corregir', dict(datos, **cambio)).status_code, estado)
        PertenenciaRol.objects.create(usuario=self.admin, rol='coordinador')
        PertenenciaRol.objects.filter(usuario=self.admin, rol='administrador').update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.post('asistencia/corregir', datos).status_code, 403)
        self.assertFalse(CorreccionAsistencia.objects.exists())

    def test_json_estricto_csrf_y_transicion_sql_bloqueada(self):
        for datos in ([], 'texto', {'actor': self.admin.pk}):
            self.assertEqual(self.cliente.post(self.ruta+'ejecucion/', datos, format='json').status_code, 400)
        for campo in ('actor', 'finalizada_por', 'finalizada_en', 'estado'):
            self.assertEqual(self.post('ejecucion', dict(self.datos_ejecucion(), **{campo: 'alteración'})).status_code, 400)
        cliente = APIClient(enforce_csrf_checks=True)
        cliente.force_login(self.actor)
        datos = dict(clave=str(uuid4()), version=self.version, **self.datos_ejecucion())
        self.assertEqual(cliente.post(self.ruta+'ejecucion/', datos, format='json').status_code, 403)
        token = cliente.get('/api/autenticacion/csrf/').data['csrfToken']
        self.assertEqual(cliente.post(self.ruta+'ejecucion/', datos, format='json', HTTP_X_CSRFTOKEN=token).status_code, 200)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sesion.objects.filter(pk=self.sesion.pk).update(estado='realizada', plan_ejecutado=self.plan_elegido, inicio_real=timezone.now()-timedelta(hours=1), fin_real=timezone.now())

    def test_fallo_auditoria_revierte_correccion_y_evento(self):
        self.guardar_asistencia()
        self.assertEqual(self.post('asistencia/cerrar').status_code, 200)
        self.cliente.force_authenticate(self.admin)
        version = self.version
        with patch('sesiones.ejecucion.registrar', side_effect=RuntimeError('Fallo ficticio')), self.assertRaises(RuntimeError):
            self.post('asistencia/corregir', dict(deportista=self.inscripcion.deportista_id, anterior='asistio', nuevo='excusa', motivo='Rectificación ficticia'))
        self.assertEqual(self.sesion.asistencias.get().estado, 'asistio')
        self.assertEqual(Sesion.objects.get().version, version)
        self.assertFalse(CorreccionAsistencia.objects.exists())
        self.assertFalse(EventoSesion.objects.filter(operacion='corregir_asistencia').exists())

    def test_revision_nueva_no_sustituye_plan_del_registro_real(self):
        self.assertEqual(self.post('ejecucion', self.datos_ejecucion()).status_code, 200)
        self.sesion.refresh_from_db()
        sesion = self.plan(self.sesion)
        self.version = sesion.version
        self.assertEqual(sesion.planes.count(), 2)
        self.guardar_asistencia()
        self.assertEqual(self.post('ejecucion/finalizar').status_code, 200)
        registro = self.cliente.get(self.ruta+'ejecucion/').data['ejecucion']
        self.assertEqual(registro['plan']['id'], self.plan_elegido.pk)
        self.assertEqual(registro['plan']['numero'], 1)

    def test_asistencia_futura_no_se_cierra(self):
        futura = self.crear(fecha=timezone.localdate()+timedelta(days=1))
        self.ruta = f'/api/sesiones/{futura.pk}/'
        self.version = futura.version
        self.assertEqual(self.post('asistencia', dict(registros={str(self.inscripcion.pk): 'asistio'})).status_code, 200)
        self.assertEqual(self.post('asistencia/cerrar').status_code, 400)
        self.assertFalse(Sesion.objects.get(pk=futura.pk).asistencia_confirmada)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless


@skipUnless(connection.vendor == 'postgresql', 'Bloqueos reales PostgreSQL')
class ConcurrenciaCierre(TransactionTestCase):
    crear = dominio.DominioSesiones.crear
    plan = dominio.DominioSesiones.plan
    comando = dominio.DominioSesiones.comando
    datos_ejecucion = RegistroEjecucion.datos_ejecucion

    def setUp(self):
        dominio.ConcurrenciaSesiones.setUp(self)
        self.sesion = self.plan(self.crear())
        self.plan_elegido = self.sesion.planes.get()
        from .ejecucion import operar
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='guardar_asistencia', datos={'registros': {str(self.inscripcion.pk): 'tarde'}})

    def paralelas(self, ruta, entradas, actor=None):
        barrera = Barrier(2)
        def ejecutar(datos):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=(actor or self.actor).pk))
                barrera.wait(timeout=10)
                return cliente.post(f'/api/sesiones/{self.sesion.pk}/{ruta}/', datos, format='json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, entradas))

    def test_cierres_compiten_por_version(self):
        estados = self.paralelas('asistencia/cerrar', [dict(version=self.sesion.version, clave=str(uuid4())) for _ in range(2)])
        self.assertEqual(sorted(estados), [200, 409])
        self.assertEqual(EventoSesion.objects.filter(operacion='cerrar_asistencia').count(), 1)

    def test_reintento_simultaneo_un_solo_cierre(self):
        datos = dict(version=self.sesion.version, clave=str(uuid4()))
        self.assertEqual(self.paralelas('asistencia/cerrar', [datos, datos]), [200, 200])
        self.assertEqual(EventoSesion.objects.filter(operacion='cerrar_asistencia').count(), 1)

    def test_correcciones_compiten_sin_perder_historia(self):
        from .ejecucion import operar
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='cerrar_asistencia', datos={})
        base = dict(version=self.sesion.version, deportista=self.inscripcion.deportista_id, anterior='tarde', motivo='Corrección concurrente ficticia')
        estados = self.paralelas('asistencia/corregir', [dict(base, clave=str(uuid4()), nuevo=nuevo) for nuevo in ('asistio', 'excusa')], actor=self.admin)
        self.assertEqual(sorted(estados), [200, 409])
        self.assertEqual(CorreccionAsistencia.objects.count(), 1)
        self.assertEqual(EventoSesion.objects.filter(operacion='corregir_asistencia').count(), 1)

    def test_finalizacion_simultanea_no_duplica_evidencia(self):
        from .ejecucion import operar
        self.sesion = operar(actor=self.actor, sesion_id=self.sesion.pk, version=self.sesion.version, clave=uuid4(), operacion='guardar_ejecucion', datos=self.datos_ejecucion())
        datos = dict(version=self.sesion.version, clave=str(uuid4()))
        self.assertEqual(self.paralelas('ejecucion/finalizar', [datos, datos]), [200, 200])
        self.assertEqual(EventoSesion.objects.filter(operacion='finalizar_ejecucion').count(), 1)
        self.assertIsNotNone(EjecucionSesion.objects.get().finalizada_en)


from . import test_curricular as curricular
from recursos.editorial import transicion, derivar


class IntegridadCurricularReal(TestCase):
    publicar = classmethod(curricular.IntegracionCurricular.publicar.__func__)
    crear = dominio.DominioSesiones.crear
    comando = dominio.DominioSesiones.comando
    datos = curricular.IntegracionCurricular.datos

    @classmethod
    def setUpTestData(cls):
        curricular.IntegracionCurricular.setUpTestData.__func__(cls)

    def setUp(self):
        curricular.IntegracionCurricular.setUp(self)

    def test_registro_conserva_version_curricular_y_ejercicio_historicos(self):
        r = curricular.IntegracionCurricular.guardar(self)
        self.assertEqual(r.status_code, 200, r.data)
        plan = PlanSesion.objects.get()
        nueva = derivar(self.actor, self.v)
        self.publicar(nueva)
        transicion(self.coord, self.e, 'retirar', self.e.revision, uuid4(), 'Retiro ficticio posterior')
        datos = dict(version=r.data['version'], clave=str(uuid4()), plan=plan.pk, inicio=f'{self.fecha}T10:00:00-05:00', fin=f'{self.fecha}T11:00:00-05:00', actividades=[dict(tarea=t.pk, resultado='realizada', minutos=10, descripcion='Declaración retrospectiva ficticia') for t in plan.tareas.all()])
        self.assertEqual(self.cliente.post(self.ruta+'ejecucion/', datos, format='json').status_code, 200)
        ejecucion = self.cliente.get(self.ruta+'ejecucion/').data['ejecucion']
        self.assertEqual(ejecucion['plan']['malla_version'], self.v.pk)
        self.assertEqual(ejecucion['plan']['competencias'][0]['id'], self.competencia.pk)
        self.assertEqual(ejecucion['plan']['tareas'][0]['ejercicio_version'], self.e.pk)
        self.assertEqual(ejecucion['validacion_funcional'], 'pendiente')
