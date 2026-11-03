"""Flujo funcional B3-D mediante API; escrituras solo en PostgreSQL temporal aislado."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.test import TestCase
from django.db import connection
from deportistas.tests import DatosFase3
from organizacion.models import Horario
from .models import Inscripcion, EventoInscripcion, ReservaCupo
from .modelos_ascensos import ProgresionInstitucional, EventoProgresion
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from .servicios_ascensos import autorizar_excepcion


class IntegracionAscensosB3D(DatosFase3, TestCase):
    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_zdb_fase3_'))
        self.assertNotEqual(int(connection.settings_dict['PORT']),5432)
        self.preparar()

    def get(self, accion):
        r=self.c.get(f'/api/ascensos/{self.p.pk}/{accion}/')
        self.assertEqual(r.status_code,200,r.data)
        return r.data

    def crear_flujo(self, dos=False):
        self.origen=self.inscribir()
        self.segunda=self.inscribir(grupo=self.b) if dos else None
        self.c.force_authenticate(self.prof)
        propuesta=self.post('ascensos/',{'deportista':self.persona.pk,'disciplina':self.d.pk,
            'inscripcion_referencia':self.origen.pk,'nivel_destino':self.n2.pk,'justificacion':'Progresión pedagógica ficticia B3-D'})
        self.assertEqual(propuesta.status_code,201,propuesta.data)
        self.p=ProgresionInstitucional.objects.get(pk=propuesta.data['id'])
        self.assertEqual(self.p.estado_decision,'pendiente')
        self.c.force_authenticate(self.coord)
        destinos=self.c.get('/api/organizacion/grupos/',{'disciplina':self.d.pk,'nivel':self.n2.pk,'activo':'true'})
        self.assertEqual(destinos.status_code,200)
        self.assertIn(self.l.pk,[g['id'] for g in destinos.data['results']])
        cupos=self.c.get('/api/inscripciones/cupos/',{'grupo':self.l.pk})
        self.assertEqual(cupos.status_code,200)
        self.assertEqual(cupos.data['disponibles'],2)
        for a in self.p.afectaciones.order_by('pk'):
            self.p.refresh_from_db()
            r=self.post(f'ascensos/{self.p.pk}/disponer/',{'version':self.p.version,'afectacion':a.pk,
                'disposicion':'pendiente','destino':None,'motivo':'Revisada expresamente antes de decisión'})
            self.assertEqual(r.status_code,200,r.data)
        self.p.refresh_from_db()
        aprobada=self.post(f'ascensos/{self.p.pk}/aprobar/',{'version':self.p.version,'decision':'aprobar',
            'resolucion':'Aprobación pedagógica ficticia del coordinador'})
        self.assertEqual(aprobada.status_code,200,aprobada.data)
        self.p.refresh_from_db()
        self.decision=(self.p.decidida_por_id,self.p.decidida_en,self.p.resolucion)
        if dos:
            segunda=self.p.afectaciones.get(inscripcion=self.segunda)
            autorizar_excepcion(self.coord,self.p.pk,self.p.version,segunda.pk,'Permanencia temporal expresa',
                self.hoy,self.hoy+timedelta(days=3))
        self.filas=[{'afectacion':a.pk,'disposicion':'pendiente','destino':None,'motivo':'Revisión administrativa inicial'}
            for a in self.p.afectaciones.order_by('pk')]
        self.crear_revision(self.filas)
        self.aid=self.p.afectaciones.get(inscripcion=self.origen).pk
        next(f for f in self.filas if f['afectacion']==self.aid).update(disposicion='reubicar',destino=self.l.pk)
        self.crear_revision(self.filas)
        self.assertEqual(RevisionAdministrativa.objects.filter(progresion=self.p).count(),2)
        contexto=self.get('ejecucion')
        self.assertTrue(contexto['plan_completo'])
        self.assertTrue(next(f for f in contexto['afectaciones'] if f['afectacion']==self.aid)['puede_ejecutar'])
        self.payload={'revision':contexto['revision'],'version':contexto['version'],'afectacion':self.aid,
            'clave':str(uuid4()),'motivo':'Ejecución individual ficticia B3-D'}

    def crear_revision(self, filas):
        self.c.force_authenticate(self.admin)
        self.p.refresh_from_db()
        r=self.post(f'ascensos/{self.p.pk}/revisiones/',{'version':self.p.version,'motivo':'Revisión completa versionada B3-D',
            'disposiciones':filas})
        self.assertEqual(r.status_code,201,r.data)

    def ejecutar(self):
        return self.post(f'ascensos/{self.p.pk}/ejecutar/',self.payload)

    def foto(self):
        return [list(m.objects.order_by('pk').values()) for m in (Inscripcion,EventoInscripcion,ReservaCupo,
            ProgresionInstitucional,EventoProgresion,RevisionAdministrativa,ResultadoAdministrativo)]

    def test_flujo_api_administrador_historia_idempotencia_y_cupos(self):
        self.crear_flujo()
        self.c.force_authenticate(self.admin)
        r=self.ejecutar();self.assertEqual(r.status_code,200,r.data)
        antes_reintento=self.foto()
        repetida=self.ejecutar();self.assertEqual(repetida.status_code,200,repetida.data)
        self.assertEqual(r.data['resultado'],repetida.data['resultado'])
        self.assertEqual(self.foto(),antes_reintento)
        self.origen.refresh_from_db();self.p.refresh_from_db()
        self.assertEqual(self.origen.estado,'finalizada')
        destino=Inscripcion.objects.get(pk=r.data['destino'])
        self.assertEqual((destino.inscripcion_anterior_id,destino.grupo_id,destino.estado),
            (self.origen.pk,self.l.pk,'activa'))
        self.assertEqual((self.p.decidida_por_id,self.p.decidida_en,self.p.resolucion),self.decision)
        self.assertEqual(EventoInscripcion.objects.filter(tipo='traslado_origen').count(),1)
        self.assertEqual(EventoProgresion.objects.filter(tipo='ejecutar_reubicacion').count(),1)
        self.assertEqual(self.get('resultados')['count'],1)
        self.assertEqual(self.get('revisiones')['count'],2)
        self.assertEqual(self.get('ejecucion')['estado_ejecucion'],'ejecutado')
        for grupo,ocupacion in ((self.a,0),(self.l,1)):
            datos=self.c.get('/api/inscripciones/cupos/',{'grupo':grupo.pk}).data
            self.assertEqual(datos['ocupacion_actual'],ocupacion)
        self.assertEqual(ReservaCupo.objects.count(),0)

    def test_flujo_api_progresivo_con_otra_inscripcion_pendiente(self):
        self.crear_flujo(dos=True)
        segunda=Inscripcion.objects.filter(pk=self.segunda.pk).values().get()
        r=self.ejecutar();self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(Inscripcion.objects.filter(pk=self.segunda.pk).values().get(),segunda)
        resumen=self.get('ejecucion')
        self.assertEqual(resumen['estado_ejecucion'],'parcialmente_ejecutado')
        self.assertFalse(resumen['puede_cerrar'])
        self.assertEqual(ResultadoAdministrativo.objects.count(),1)

    def test_fallo_auditoria_revierte_movimiento_y_eventos(self):
        self.crear_flujo();antes=self.foto()
        with patch('inscripciones.servicios_movimientos.registrar_evento',side_effect=RuntimeError('Fallo ficticio B3-D')):
            with self.assertRaises(RuntimeError):self.ejecutar()
        self.assertEqual(self.foto(),antes)
        self.assertEqual(ResultadoAdministrativo.objects.count(),0)

    def test_cupo_agotado_despues_de_revision(self):
        self.crear_flujo()
        for nombre in ('Cupo ficticio A','Cupo ficticio B'):
            self.inscribir(persona=self.persona_nueva(nombre),grupo=self.l)
        antes=self.foto();r=self.ejecutar()
        self.assertEqual(r.status_code,409,r.data)
        self.assertEqual(self.foto(),antes)

    def test_horario_modificado_despues_de_revision(self):
        self.crear_flujo()
        Horario.objects.filter(grupo=self.l).update(hora_inicio='10:15',hora_fin='10:45')
        antes=self.foto();r=self.ejecutar()
        self.assertEqual(r.status_code,409,r.data)
        self.assertEqual(self.foto(),antes)

    def test_profesor_no_ejecuta_admin_no_decide(self):
        self.crear_flujo();antes=self.foto()
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.ejecutar().status_code,403)
        self.c.force_authenticate(self.admin)
        r=self.post(f'ascensos/{self.p.pk}/aprobar/',{'version':self.payload['version'],
            'decision':'aprobar','resolucion':'No debe admitirse'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.foto(),antes)
