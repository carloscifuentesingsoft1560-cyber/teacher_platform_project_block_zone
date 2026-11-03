from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.db import connections, close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from deportistas.tests import DatosFase3
from organizacion.models import Asignacion, Nivel, Disciplina, Grupo
from .models import Inscripcion, Propuesta, ReservaCupo, EventoInscripcion
from .modelos_ascensos import ProgresionInstitucional, AfectacionInscripcion


class ApiAscensos(DatosFase3, TestCase):
    def setUp(self):
        self.preparar()
        self.origen = self.inscribir()
        self.c.force_authenticate(self.prof)

    def datos(self, **cambios):
        return {'deportista':self.persona.pk, 'disciplina':self.d.pk,
            'inscripcion_referencia':self.origen.pk, 'nivel_destino':self.n2.pk,
            'justificacion':'Intención pedagógica ficticia', **cambios}

    def crear(self, **cambios):
        return self.post('ascensos/', self.datos(**cambios))

    def contexto(self, **cambios):
        return self.c.get('/api/ascensos/contexto/', {'deportista':self.persona.pk, **cambios})

    def niveles(self, **cambios):
        return self.c.get('/api/ascensos/niveles/', {'deportista':self.persona.pk,
            'disciplina':self.d.pk, 'inscripcion_referencia':self.origen.pk, **cambios})

    def antigua(self):
        return Propuesta.objects.create(tipo='nivel', deportista=self.persona,
            inscripcion_origen=self.origen, grupo_destino=self.l, fecha_efectiva=self.hoy,
            justificacion='Histórica ficticia', creado_por=self.prof, actualizado_por=self.prof)

    def test_contexto_y_disciplina_propios_paginados(self):
        r = self.contexto()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['id'], self.origen.pk)
        self.assertEqual(r.data['results'][0]['nivel_origen']['id'], self.n.pk)
        self.assertEqual(r.data['results'][0]['nivel_siguiente']['id'], self.n2.pk)
        r = self.contexto(vista='disciplinas')
        self.assertEqual(r.data['results'], [{'id':self.d.pk,'nombre':self.d.nombre,'codigo':self.d.codigo}])

    def test_varias_referencias_activas_sin_elegir_automaticamente(self):
        b = self.inscribir(grupo=self.b)
        r = self.contexto(disciplina=self.d.pk)
        self.assertEqual({x['id'] for x in r.data['results']}, {self.origen.pk,b.pk})
        d = self.datos();d.pop('inscripcion_referencia')
        self.assertEqual(self.post('ascensos/',d).status_code,400)

    def test_sin_asignacion_no_consulta_ni_propone(self):
        Asignacion.objects.filter(usuario=self.prof).update(fecha_fin=self.hoy-timedelta(days=1))
        self.assertEqual(self.contexto().status_code,404)
        self.assertEqual(self.crear().status_code,404)

    def test_deportista_ajeno_no_revela_existencia(self):
        ajena = self.persona_nueva('Ajena')
        self.assertEqual(self.contexto(deportista=ajena.pk).status_code,404)
        self.assertEqual(self.crear(deportista=ajena.pk).status_code,404)

    def test_nivel_no_impartido_solo_expone_metadatos(self):
        Asignacion.objects.filter(usuario=self.prof,grupo=self.l).delete()
        r = self.niveles()
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data['results'], [{'id':self.n2.pk,'codigo':self.n2.codigo,
            'nombre':self.n2.nombre,'disciplina':self.d.pk,'orden':3}])
        self.assertEqual(self.c.get(f'/api/organizacion/grupos/{self.l.pk}/').status_code,404)

    def test_secuencia_no_se_infiere_de_ids(self):
        Nivel.objects.get(disciplina=self.d,codigo='ludico').delete()
        ludico = Nivel.objects.create(disciplina=self.d,codigo='ludico',nombre='Lúdico',orden=1)
        self.assertGreater(ludico.pk,self.n.pk)
        g = self.grupo('ludico-api','14:00','15:00',ludico)
        Asignacion.objects.create(usuario=self.prof,grupo=g,tipo='profesor',fecha_inicio=self.periodo.fecha_inicio)
        i = Inscripcion.objects.create(deportista=self.persona,grupo=g,fecha_ingreso=self.hoy,
            creado_por=self.coord,actualizado_por=self.coord)
        r = self.niveles(inscripcion_referencia=i.pk)
        self.assertEqual(r.data['results'][0]['id'],self.n.pk)

    def test_mismo_nivel_saltos_y_retrocesos_bloqueados(self):
        for n in Nivel.objects.filter(disciplina=self.d).exclude(pk=self.n2.pk):
            with self.subTest(codigo=n.codigo):
                self.assertEqual(self.crear(nivel_destino=n.pk).status_code,400)
        self.assertFalse(ProgresionInstitucional.objects.exists())

    def test_otra_disciplina_se_rechaza(self):
        d = Disciplina.objects.create(codigo='otra-api',nombre='Otra')
        n = Nivel.objects.create(disciplina=d,codigo='nivel-2',nombre='Otro nivel',orden=3)
        self.assertEqual(self.crear(nivel_destino=n.pk).status_code,400)
        self.assertEqual(self.crear(disciplina=d.pk).status_code,404)

    def test_siguiente_inactivo_no_se_omite(self):
        Nivel.objects.filter(pk=self.n2.pk).update(activo=False)
        self.assertEqual(self.niveles().data['results'],[])
        self.assertEqual(self.crear().status_code,400)

    def test_catalogo_incompleto_o_orden_ambiguo_falla_cerrado(self):
        for orden in (2,0):
            Nivel.objects.filter(pk=self.n2.pk).update(orden=orden)
            self.assertEqual(self.niveles().status_code,409)
            self.assertEqual(self.crear().status_code,409)

    def test_ultimo_nivel_no_tiene_superior(self):
        n = Nivel.objects.get(disciplina=self.d,codigo='alto-rendimiento')
        g = self.grupo('alto-api','15:00','16:00',n)
        Asignacion.objects.create(usuario=self.prof,grupo=g,tipo='profesor',fecha_inicio=self.periodo.fecha_inicio)
        i = Inscripcion.objects.create(deportista=self.persona,grupo=g,fecha_ingreso=self.hoy,
            creado_por=self.coord,actualizado_por=self.coord)
        self.assertEqual(self.niveles(inscripcion_referencia=i.pk).data['results'],[])
        self.assertEqual(self.crear(inscripcion_referencia=i.pk).status_code,400)

    def test_referencia_suspendida_no_habilita_propuesta(self):
        self.c.force_authenticate(self.coord)
        self.post(f'inscripciones/{self.origen.pk}/suspender/',{'version':1,'motivo':'Pausa',
            'fecha_vencimiento':str(self.hoy+timedelta(days=1))})
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.contexto().data['results'],[])
        self.assertEqual(self.crear().status_code,404)

    def test_propuesta_incluye_reservas_y_futuras_sin_revelar_grupos_ajenos(self):
        b = self.inscribir(grupo=self.b)
        self.c.force_authenticate(self.coord)
        self.post(f'inscripciones/{b.pk}/suspender/',{'version':1,'motivo':'Motivo privado',
            'fecha_vencimiento':str(self.hoy+timedelta(days=3))})
        Asignacion.objects.filter(usuario=self.prof,grupo=self.b).delete()
        g = self.grupo('futuro-api','13:00','14:00')
        futura = self.inscribir(grupo=g,inicio=self.hoy+timedelta(days=4))
        self.c.force_authenticate(self.prof)
        r = self.crear()
        self.assertEqual(r.status_code,201)
        p = ProgresionInstitucional.objects.get(pk=r.data['id'])
        self.assertEqual(dict(p.afectaciones.values_list('inscripcion_id','situacion_observada')),
            {self.origen.pk:'activa',b.pk:'reserva',futura.pk:'futura'})
        for respuesta in (r,self.contexto(),self.c.get('/api/ascensos/')):
            self.assertNotIn(self.b.nombre,str(respuesta.data))
            self.assertNotIn(g.nombre,str(respuesta.data))
            self.assertNotIn('Motivo privado',str(respuesta.data))
            self.assertNotIn('afectaciones',str(respuesta.data))

    def test_creacion_pendiente_sin_efectos_operativos(self):
        modelos = (Inscripcion,ReservaCupo,EventoInscripcion,Grupo,Propuesta)
        antes = {m:list(m.objects.values()) for m in modelos}
        r = self.crear()
        self.assertEqual(r.status_code,201)
        self.assertEqual((r.data['estado_decision'],r.data['estado_plan']),('pendiente','pendiente'))
        self.assertEqual(ProgresionInstitucional.objects.get().creado_por_id,self.prof.pk)
        for m in modelos:self.assertEqual(list(m.objects.values()),antes[m])
        for campo in ('numero_documento','fecha_nacimiento','afectaciones','excepciones','resolucion'):
            self.assertNotIn(campo,r.data)

    def test_intencion_mismo_dia_no_cierra_origen(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
        self.assertEqual(self.crear().status_code,201)
        self.origen.refresh_from_db();self.assertIsNone(self.origen.fecha_salida)

    def test_inyeccion_campos_y_justificacion_vacia(self):
        for campo in ('creado_por','autor','responsable','estado_decision','estado_plan','version',
                'afectaciones','resolucion','grupo_destino','periodo','nivel_origen','fecha_efectiva'):
            with self.subTest(campo=campo):self.assertEqual(self.crear(**{campo:1}).status_code,400)
        self.assertEqual(self.crear(justificacion='   ').status_code,400)
        self.assertEqual(self.crear(justificacion='a'*501).status_code,400)
        self.assertFalse(ProgresionInstitucional.objects.exists())

    def test_parametros_estrictos_y_paginacion(self):
        for parametros in ({'page':0},{'disciplina':'abc'},{'desconocido':1},{'vista':'global'}):
            self.assertEqual(self.contexto(**parametros).status_code,400)
        self.assertEqual(self.contexto(page=2).status_code,404)
        self.assertEqual(self.c.get('/api/ascensos/contexto/?deportista=1&deportista=2').status_code,400)
        self.assertEqual(self.c.get('/api/ascensos/?estado_decision=ejecutado').status_code,400)
        self.assertEqual(self.c.get('/api/ascensos/?profesor=1').status_code,400)
        self.assertEqual(self.c.post('/api/ascensos/?autor=1',self.datos(),format='json').status_code,400)

    def test_busquedas_contextuales(self):
        self.assertEqual(self.contexto(search=self.a.codigo).data['count'],1)
        self.assertEqual(self.contexto(search='sin-coincidencia').data['count'],0)
        self.assertEqual(self.niveles(search='sin-coincidencia').data['count'],0)

    def test_duplicada_responde_conflicto_sin_detalles_ajenos(self):
        self.assertEqual(self.crear().status_code,201)
        r = self.crear();self.assertEqual(r.status_code,409)
        self.assertEqual(ProgresionInstitucional.objects.count(),1)
        self.assertNotIn('creado_por',r.data)

    def test_lectura_propia_y_roles_sin_nuevas_facultades(self):
        p = self.crear().data['id']
        for actor in (self.admin,self.coord,self.prof):
            self.c.force_authenticate(actor)
            self.assertEqual(self.c.get('/api/ascensos/').status_code,200)
            self.assertEqual(self.c.get(f'/api/ascensos/{p}/').status_code,200)
            if actor.rol!='profesor':
                self.assertEqual(self.crear().status_code,403)
                self.assertEqual(self.contexto().status_code,403)
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.c.get('/api/ascensos/').data['count'],0)
        self.assertEqual(self.c.get(f'/api/ascensos/{p}/').status_code,404)
        self.assertEqual(self.crear().status_code,404)
        self.c.force_authenticate(None)
        self.assertEqual(self.c.get('/api/ascensos/').status_code,403)

    def test_perdida_de_asignacion_tras_consulta(self):
        self.assertEqual(self.contexto().status_code,200)
        Asignacion.objects.filter(usuario=self.prof).delete()
        self.assertEqual(self.crear().status_code,404)

    def test_perdida_ambito_tras_propuesta_cierra_lectura(self):
        p = self.crear().data['id'];Asignacion.objects.filter(usuario=self.prof).delete()
        self.assertEqual(self.c.get(f'/api/ascensos/{p}/').status_code,404)

    def test_inactivo_y_coordinador_desactivado(self):
        for actor in (self.prof,self.coord):
            actor.is_active=False;actor.save();self.c.force_authenticate(actor)
            self.assertEqual(self.c.get('/api/ascensos/').status_code,403)

    def test_no_existe_edicion_arbitraria_y_ejecucion_exige_contrato_b3(self):
        p = self.crear().data['id'];self.c.force_authenticate(self.coord)
        for accion in ('revocar','planes','excepciones'):
            self.assertEqual(self.post(f'ascensos/{p}/{accion}/',{}).status_code,404)
        # B3-C añade la acción específica, sin permitir mutación libre del agregado.
        self.assertEqual(self.post(f'ascensos/{p}/ejecutar/',{}).status_code,403)
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.post(f'ascensos/{p}/ejecutar/',{}).status_code,403)
        self.assertEqual(self.c.patch(f'/api/ascensos/{p}/',{'estado_plan':'ejecutado'},format='json').status_code,405)

    def test_csrf_con_sesion_no_se_omite(self):
        c = APIClient(enforce_csrf_checks=True);c.force_login(self.prof)
        self.assertEqual(c.post('/api/ascensos/',self.datos(),format='json').status_code,403)

    def test_historia_antigua_visible_y_aprobacion_bloqueada(self):
        p = self.antigua();antes=list(Propuesta.objects.values())
        r = self.c.get(f'/api/propuestas/{p.pk}/')
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.data['mecanismo_deshabilitado'])
        self.assertIn('deshabilitado',r.data['aviso_procedimiento'])
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f'propuestas/{p.pk}/aprobar/',{'version':1,'resolucion':'No ejecutar'}).status_code,409)
        self.assertEqual(list(Propuesta.objects.values()),antes)
        self.assertEqual(Inscripcion.objects.count(),1)

    def test_antigua_pendiente_bloquea_nuevo_sin_conversion(self):
        p = self.antigua()
        self.assertEqual(self.crear().status_code,409)
        p.refresh_from_db();self.assertEqual(p.estado,'pendiente')
        self.assertFalse(ProgresionInstitucional.objects.exists())

    def test_alta_nivel_antigua_y_traslado_directo_no_eluden_cierre(self):
        d = {'tipo':'nivel','deportista':self.persona.pk,'inscripcion_origen':self.origen.pk,
            'grupo_destino':self.l.pk,'fecha_efectiva':str(self.hoy),'justificacion':'Antigua'}
        self.assertEqual(self.post('propuestas/',d).status_code,409)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f'inscripciones/{self.origen.pk}/trasladar/',
            {'version':1,'grupo_destino':self.l.pk,'motivo':'No eludir'}).status_code,400)
        self.assertFalse(Propuesta.objects.exists())


class ConcurrenciaApiAscensos(DatosFase3, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_docentes_distintos_solo_crean_una_progresion(self):
        self.preparar();a=self.inscribir();b=self.inscribir(grupo=self.b)
        Asignacion.objects.create(usuario=self.otro,grupo=self.b,tipo='profesor',fecha_inicio=self.periodo.fecha_inicio)
        barrera=Barrier(2)
        def competir(par):
            close_old_connections()
            try:
                actor,i=par;c=APIClient();c.force_authenticate(actor);barrera.wait(timeout=10)
                return c.post('/api/ascensos/',{'deportista':self.persona.pk,'disciplina':self.d.pk,
                    'inscripcion_referencia':i.pk,'nivel_destino':self.n2.pk,'justificacion':'Concurrente'},format='json').status_code
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(competir,[(self.prof,a),(self.otro,b)])),[201,409])
        self.assertEqual(ProgresionInstitucional.objects.count(),1)
        self.assertEqual(AfectacionInscripcion.objects.count(),2)
        self.assertEqual(Inscripcion.objects.count(),2)
