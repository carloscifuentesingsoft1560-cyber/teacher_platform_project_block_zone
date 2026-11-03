from datetime import timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.test import TestCase, TransactionTestCase
from django.db import connection, close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario, PertenenciaRol
from organizacion.models import Asignacion, Grupo
from . import tests as dominio
from .models import Sesion, PlanSesion, EventoSesion


class ApiSesiones(TestCase):
    @classmethod
    def setUpTestData(cls):
        dominio.DominioSesiones.setUpTestData.__func__(cls)

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.actor)

    crear = dominio.DominioSesiones.crear
    plan = dominio.DominioSesiones.plan
    comando = dominio.DominioSesiones.comando

    def datos(self, **cambios):
        datos = dict(clave=str(uuid4()), grupo=self.grupo.pk, fecha=str(self.fecha), hora_inicio='10:00', hora_fin='11:00')
        datos.update(cambios)
        return datos

    def plan_datos(self, version=1, **cambios):
        datos = dict(clave=str(uuid4()), version=version, objetivo='Prueba API', tareas=[dict(fase=f, minutos=20, instrucciones='Ficticia') for f in ('inicial', 'central', 'final')])
        datos.update(cambios)
        return datos

    def ruta(self, sesion):
        return f'/api/sesiones/{sesion.pk}/'

    def test_crear_listar_consultar_y_grupos(self):
        r = self.cliente.post('/api/sesiones/', self.datos(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['profesor'], self.actor.pk)
        listado = self.cliente.get('/api/sesiones/').data
        self.assertEqual(listado['count'], 1)
        detalle = self.cliente.get(f"/api/sesiones/{r.data['id']}/")
        self.assertEqual(detalle.status_code, 200)
        self.assertNotIn('asistencias', detalle.data)
        self.assertNotIn('eventos', detalle.data)
        self.assertEqual(self.cliente.get('/api/sesiones/grupos/').data['results'][0]['id'], self.grupo.pk)

    def test_sesion_ajena_incluso_en_mismo_grupo(self):
        s = self.crear()
        Asignacion.objects.create(grupo=self.grupo, usuario=self.otro, tipo='profesor', fecha_inicio=self.fecha)
        self.cliente.force_authenticate(self.otro)
        self.assertEqual(self.cliente.get('/api/sesiones/').data['count'], 0)
        for metodo, ruta, datos in [('get', self.ruta(s), None), ('patch', self.ruta(s), self.plan_datos()), ('post', self.ruta(s)+'cancelar/', dict(clave=str(uuid4()), version=1, motivo='Prueba')), ('post', self.ruta(s)+'realizar/', {})]:
            r = getattr(self.cliente, metodo)(ruta, datos, format='json')
            self.assertEqual(r.status_code, 404, r.data)
        self.assertEqual(s.eventos.count(), 1)

    def test_grupo_ajeno_en_creacion(self):
        otro = Grupo.objects.create(codigo='api-ajeno', nombre='Ajeno', disciplina=self.grupo.disciplina, nivel=self.grupo.nivel, periodo=self.grupo.periodo, cupo_maximo=4)
        r = self.cliente.post('/api/sesiones/', self.datos(grupo=otro.pk), format='json')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Sesion.objects.exists())

    def test_no_suplantar_profesor_ni_actor(self):
        for cambios, estado in [({'profesor': self.otro.pk}, 403), ({'actor': self.admin.pk}, 400), ({'creado_por': self.admin.pk}, 400), ({'estado': 'realizada'}, 400)]:
            r = self.cliente.post('/api/sesiones/', self.datos(**cambios), format='json')
            self.assertEqual(r.status_code, estado, r.data)
        self.assertFalse(Sesion.objects.exists())

    def test_editar_plan_version_idempotencia_y_campos_inmutables(self):
        s = self.crear()
        datos = self.plan_datos()
        r = self.cliente.patch(self.ruta(s), datos, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['version'], 2)
        self.assertEqual(self.cliente.patch(self.ruta(s), datos, format='json').status_code, 200)
        self.assertEqual(PlanSesion.objects.count(), 1)
        self.assertEqual(self.cliente.patch(self.ruta(s), self.plan_datos(), format='json').status_code, 409)
        self.assertEqual(self.cliente.patch(self.ruta(s), dict(datos, objetivo='Distinto'), format='json').status_code, 409)
        for campo in ('fecha', 'profesor', 'grupo', 'estado', 'asistencia_confirmada'):
            self.assertEqual(self.cliente.patch(self.ruta(s), dict(self.plan_datos(2), **{campo: 'ajeno'}), format='json').status_code, 400)

    def test_cancelar_y_transiciones_bloqueadas(self):
        s = self.crear()
        self.assertEqual(self.cliente.post(self.ruta(s)+'realizar/', {}, format='json').status_code, 403)
        datos = dict(clave=str(uuid4()), version=1, motivo='Prueba')
        r = self.cliente.post(self.ruta(s)+'cancelar/', datos, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado'], 'cancelada')
        self.assertEqual(self.cliente.patch(self.ruta(s), self.plan_datos(2), format='json').status_code, 400)
        self.assertEqual(self.cliente.delete(self.ruta(s)).status_code, 405)

    def test_revocacion_asignacion_oculta_y_bloquea_reintento(self):
        datos = self.datos()
        r = self.cliente.post('/api/sesiones/', datos, format='json')
        Asignacion.objects.filter(usuario=self.actor).update(fecha_fin=self.fecha-timedelta(days=1))
        self.assertEqual(self.cliente.get('/api/sesiones/').data['count'], 0)
        self.assertEqual(self.cliente.get(f"/api/sesiones/{r.data['id']}/").status_code, 404)
        self.assertEqual(self.cliente.post('/api/sesiones/', datos, format='json').status_code, 404)
        self.assertEqual(self.cliente.get('/api/sesiones/grupos/').data['count'], 0)

    def test_roles_multiples_y_revocacion_sin_cache(self):
        PertenenciaRol.objects.create(usuario=self.actor, rol='acudiente')
        s = self.crear()
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 200)
        PertenenciaRol.objects.filter(usuario=self.actor, rol='profesor').update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 403)
        self.assertEqual(self.cliente.patch(self.ruta(s), self.plan_datos(), format='json').status_code, 403)

    def test_cuenta_inactiva_anonimo_y_rol_no_docente(self):
        for actor in (None, self.otro):
            if actor:
                PertenenciaRol.objects.filter(usuario=actor).update(vigente=False, fecha_fin=timezone.now())
                PertenenciaRol.objects.create(usuario=actor, rol='routesetter')
            self.cliente.force_authenticate(actor)
            self.assertEqual(self.cliente.get('/api/sesiones/').status_code, 403)
        self.cliente.force_authenticate(self.actor)
        Usuario.objects.filter(pk=self.actor.pk).update(is_active=False)
        self.assertEqual(self.cliente.get('/api/sesiones/').status_code, 403)

    def test_gestor_sin_asignacion_y_roles_combinados(self):
        s = self.crear()
        PertenenciaRol.objects.create(usuario=self.admin, rol='profesor')
        self.cliente.force_authenticate(self.admin)
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 200)
        self.assertEqual(self.cliente.patch(self.ruta(s), self.plan_datos(), format='json').status_code, 200)
        self.assertEqual(self.cliente.post('/api/sesiones/', self.datos(profesor=self.actor.pk, hora_inicio='12:00', hora_fin='13:00'), format='json').status_code, 201)

    def test_coordinador_vigente_y_revocacion_gestor_con_rol_profesor(self):
        s = self.crear()
        coordinador = Usuario.objects.create_user(username='api-coordinador', rol='coordinador')
        self.cliente.force_authenticate(coordinador)
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 200)
        PertenenciaRol.objects.create(usuario=self.admin, rol='profesor')
        self.cliente.force_authenticate(self.admin)
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 200)
        PertenenciaRol.objects.filter(usuario=self.admin, rol='administrador').update(vigente=False, fecha_fin=timezone.now())
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 404)
        self.assertEqual(self.cliente.get('/api/sesiones/').data['count'], 0)

    def test_revocacion_entre_entrada_y_comando(self):
        from unittest.mock import patch
        from .servicios import _usuarios
        s = self.crear()

        def revocar(actor, profesor_id):
            usuarios = _usuarios(actor, profesor_id)
            Asignacion.objects.filter(usuario=actor).update(fecha_fin=self.fecha-timedelta(days=1))
            return usuarios

        with patch('sesiones.views._usuarios', side_effect=revocar):
            self.assertEqual(self.cliente.patch(self.ruta(s), self.plan_datos(), format='json').status_code, 404)
        self.assertFalse(PlanSesion.objects.exists())

    def test_asignacion_nueva_no_abre_historia_ajena(self):
        s = self.crear()
        Asignacion.objects.create(grupo=self.grupo, usuario=self.otro, tipo='profesor', fecha_inicio=self.fecha)
        self.cliente.force_authenticate(self.otro)
        self.assertEqual(self.cliente.get(self.ruta(s)).status_code, 404)

    def test_entradas_invalidas_y_referencias_no_disponibles(self):
        s = self.crear()
        for datos in ([], 'texto', {'version': 1}, self.plan_datos(malla_version_id=999999), self.plan_datos(clase_id=999999), self.plan_datos(tareas=[{'fase': 'inicial', 'minutos': 0, 'instrucciones': 'Ficticia'}])):
            self.assertEqual(self.cliente.patch(self.ruta(s), datos, format='json').status_code, 400)
        self.assertEqual(self.cliente.get('/api/sesiones/?grupo=abc').status_code, 400)
        self.assertEqual(PlanSesion.objects.count(), 0)

    def test_creacion_reintentable_y_asignacion_sin_acceso_retroactivo(self):
        datos = self.datos()
        primero = self.cliente.post('/api/sesiones/', datos, format='json')
        segundo = self.cliente.post('/api/sesiones/', datos, format='json')
        self.assertEqual(primero.status_code, 201)
        self.assertEqual(segundo.data['id'], primero.data['id'])
        self.assertEqual(self.cliente.post('/api/sesiones/', dict(datos, hora_inicio='12:00', hora_fin='13:00'), format='json').status_code, 409)
        Asignacion.objects.filter(usuario=self.actor).update(fecha_inicio=self.fecha+timedelta(days=1))
        self.assertEqual(self.cliente.get('/api/sesiones/').data['count'], 0)
        self.assertEqual(self.cliente.post('/api/sesiones/', self.datos(), format='json').status_code, 404)

    def test_csrf_sesion_real(self):
        cliente = APIClient(enforce_csrf_checks=True)
        cliente.force_login(self.actor)
        self.assertEqual(cliente.post('/api/sesiones/', self.datos(), format='json').status_code, 403)
        token = cliente.get('/api/autenticacion/csrf/').data['csrfToken']
        self.assertEqual(cliente.post('/api/sesiones/', self.datos(), format='json', HTTP_X_CSRFTOKEN=token).status_code, 201)


@skipUnless(connection.vendor == 'postgresql', 'Requiere PostgreSQL')
class ConcurrenciaApi(TransactionTestCase):
    def setUp(self):
        dominio.ConcurrenciaSesiones.setUp(self)

    crear = dominio.DominioSesiones.crear

    def test_ediciones_concurrentes_una_sola_version(self):
        sesion = self.crear()
        barrera = Barrier(2)

        def editar(_):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.actor.pk))
                datos = dict(clave=str(uuid4()), version=1, objetivo='Concurrente', tareas=[dict(fase=f, minutos=20, instrucciones='Ficticia') for f in ('inicial', 'central', 'final')])
                barrera.wait(timeout=10)
                return cliente.patch(f'/api/sesiones/{sesion.pk}/', datos, format='json').status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            estados = list(pool.map(editar, range(2)))
        self.assertEqual(sorted(estados), [200, 409])
        self.assertEqual(PlanSesion.objects.count(), 1)
        self.assertEqual(EventoSesion.objects.filter(operacion='planificar').count(), 1)
