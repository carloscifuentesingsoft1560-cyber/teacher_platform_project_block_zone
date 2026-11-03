from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.db import connections, close_old_connections, transaction
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import APIException
from deportistas.tests import DatosFase3
from organizacion.models import Asignacion, Horario
from auditoria.models import CambioAdministrativo
from .models import Propuesta, Inscripcion, ReservaCupo


class DatosPropuestas(DatosFase3):
    def historica_nivel(self):
        return Propuesta.objects.create(tipo='nivel', deportista=self.persona,
            inscripcion_origen=self.origen, grupo_destino=self.l, fecha_efectiva=self.hoy,
            justificacion='Historia ficticia', version_origen=self.origen.version,
            creado_por=self.prof, actualizado_por=self.prof)
    def preparar_propuestas(self):
        self.preparar()
        self.origen=self.inscribir()
        Asignacion.objects.filter(grupo=self.b,usuario=self.prof).delete()
        Asignacion.objects.create(grupo=self.b,usuario=self.otro,tipo='profesor',fecha_inicio=self.periodo.fecha_inicio)
        self.c.force_authenticate(self.prof)
    def datos(self,tipo='traslado',destino=None,origen=None,persona=None):
        return {'tipo':tipo,'deportista':(persona or self.persona).pk,'grupo_destino':(destino or self.b).pk,
            **({'inscripcion_origen':(origen or self.origen).pk} if tipo!='inscripcion' else {}),
            'fecha_efectiva':str(self.hoy),'justificacion':'Reubicación ficticia compatible'}
    def proponer(self,**opciones):
        return self.post('propuestas/',self.datos(**opciones))
    def destinos(self,tipo='traslado',**parametros):
        d=self.datos(tipo=tipo);d.pop('grupo_destino');d.pop('justificacion')
        return self.c.get('/api/propuestas/destinos/',{**d,**parametros})
    def aprobar(self,p,actor=None):
        self.c.force_authenticate(actor or self.coord)
        return self.post(f'propuestas/{p}/aprobar/',{'version':1,'resolucion':'Revisada por coordinación'})


class PropuestasTrasladosSeguros(DatosPropuestas,TestCase):
    def setUp(self):
        self.preparar_propuestas()
    def comprobar_mensaje_temporal(self, tipo, respuesta):
        if tipo == 'nivel':
            self.assertEqual(respuesta.status_code, 409)
            self.assertIn('deshabilitado', str(respuesta.data))
            return
        operacion = 'El cambio de nivel' if tipo == 'nivel' else 'El traslado al mismo nivel'
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(str(respuesta.data['detalle']),
            f'{operacion} no puede ejecutarse el mismo día del ingreso por integridad del historial. '
            'La fecha efectiva debe ser posterior a la fecha de ingreso y la inscripción debe estar activa.')

    def test_mensajes_temporales_consulta_y_creacion_ambas_operaciones(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
        for tipo, destino in (('traslado', self.b), ('nivel', self.l)):
            with self.subTest(tipo=tipo):
                self.comprobar_mensaje_temporal(tipo, self.destinos(tipo=tipo))
                self.comprobar_mensaje_temporal(tipo, self.proponer(tipo=tipo, destino=destino))
        self.assertFalse(Propuesta.objects.exists())

    def test_mensajes_temporales_aprobacion_ambas_operaciones(self):
        for tipo, destino in (('traslado', self.b), ('nivel', self.l)):
            with self.subTest(tipo=tipo):
                Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy-timedelta(days=2))
                self.c.force_authenticate(self.prof)
                p = self.historica_nivel().pk if tipo == 'nivel' else self.proponer(tipo=tipo, destino=destino).data['id']
                # Simular un origen del mismo día únicamente en la base aislada.
                Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
                self.comprobar_mensaje_temporal(tipo, self.aprobar(p))
                self.assertEqual(Propuesta.objects.get(pk=p).estado, 'pendiente')
                Propuesta.objects.filter(pk=p).delete()
        self.assertEqual(Inscripcion.objects.count(), 1)

    def test_reanudacion_mismo_dia_no_elude_mensajes_ambas_operaciones(self):
        Inscripcion.objects.filter(pk=self.origen.pk).update(fecha_ingreso=self.hoy)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f'inscripciones/{self.origen.pk}/suspender/',
            {'version':1, 'motivo':'Suspensión ficticia', 'fecha_vencimiento':str(self.hoy)}).status_code, 200)
        self.assertEqual(self.post(f'inscripciones/{self.origen.pk}/reanudar/',
            {'version':2, 'motivo':'Reanudación ficticia'}).status_code, 200)
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.fecha_ingreso, self.hoy)
        self.assertEqual(self.origen.estado, 'activa')
        self.c.force_authenticate(self.prof)
        for tipo, destino in (('traslado', self.b), ('nivel', self.l)):
            with self.subTest(tipo=tipo):
                self.comprobar_mensaje_temporal(tipo, self.destinos(tipo=tipo))
                self.comprobar_mensaje_temporal(tipo, self.proponer(tipo=tipo, destino=destino))
        self.assertFalse(Propuesta.objects.exists())

    def test_servicio_ejecutable_mantiene_mensajes_y_no_cierra_origen(self):
        from .servicios import trasladar_bajo_bloqueo, mensaje_integridad_historial
        from rest_framework.exceptions import ValidationError
        self.origen.fecha_ingreso = self.hoy
        for permite_nivel, destino in ((False, self.b), (True, self.l)):
            with self.subTest(permite_nivel=permite_nivel):
                with self.assertRaises(APIException) as error:
                    trasladar_bajo_bloqueo(self.origen, destino, self.hoy, self.coord, 'Prueba', permite_nivel)
                if permite_nivel:
                    self.assertEqual(error.exception.status_code, 409)
                    self.assertIn('deshabilitado', str(error.exception.detail))
                else:
                    self.assertEqual(str(error.exception.detail[0]), mensaje_integridad_historial(False))
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.estado, 'activa')
        self.assertIsNone(self.origen.fecha_salida)

    def test_traslado_entre_profesores_no_otorga_asignacion(self):
        r=self.proponer();self.assertEqual(r.status_code,201)
        self.assertEqual(Inscripcion.objects.count(),1)
        self.assertFalse(Asignacion.objects.filter(usuario=self.prof,grupo=self.b).exists())
        self.assertEqual(self.aprobar(r.data['id']).status_code,200)
        self.assertEqual(Inscripcion.objects.get(inscripcion_anterior=self.origen).grupo_id,self.b.pk)
    def test_traslado_entre_jornadas_domingo(self):
        Horario.objects.filter(grupo=self.a).update(dia=0)
        Horario.objects.filter(grupo=self.b).update(dia=6)
        r=self.destinos();self.assertEqual(r.status_code,200)
        b=next(x for x in r.data['results'] if x['id']==self.b.pk)
        self.assertEqual(b['jornada'],'Domingo')
        self.assertEqual(self.aprobar(self.proponer().data['id']).status_code,200)
    def test_mismo_grupo_se_rechaza_antes_de_pendiente(self):
        self.assertEqual(self.proponer(destino=self.a).status_code,400)
        self.assertEqual(Propuesta.objects.count(),0)
        self.assertNotIn(self.a.pk,[g['id'] for g in self.destinos().data['results']])
    def test_cambio_nivel_no_ofrece_ni_admite_mismo_nivel(self):
        for g in (self.a,self.b):
            self.assertEqual(self.proponer(tipo='nivel',destino=g).status_code,409)
        candidatos=self.destinos(tipo='nivel')
        self.assertEqual(candidatos.status_code,409)
        self.assertIn('deshabilitado', str(candidatos.data))
    def test_inscripcion_adicional_duplicada_rechazada_antes_de_guardar(self):
        self.assertEqual(self.proponer(tipo='inscripcion',destino=self.a).status_code,409)
        self.assertEqual(Propuesta.objects.count(),0)
        self.assertNotIn(self.a.pk,[g['id'] for g in self.destinos(tipo='inscripcion').data['results']])
    def test_privacidad_metadatos_y_rutas_ordinarias_siguen_cerradas(self):
        ajena=self.persona_nueva('Ficha ajena ficticia')
        self.c.force_authenticate(self.coord);inscripcion=self.inscribir(persona=ajena,grupo=self.b)
        self.c.force_authenticate(self.prof)
        r=self.destinos();self.assertEqual(r.status_code,200)
        b=next(x for x in r.data['results'] if x['id']==self.b.pk)
        self.assertEqual(set(b),{'id','codigo','nombre','nivel','nivel_nombre','jornada','periodo','periodo_nombre',
            'fecha_inicio_periodo','fecha_fin_periodo','horarios','disponibilidad'})
        self.assertEqual(set(b['disponibilidad']),{'desde','hasta','cupo_maximo','disponibles'})
        self.assertNotIn(ajena.nombres,str(r.data))
        self.assertEqual(self.c.get(f'/api/organizacion/grupos/{self.b.pk}/').status_code,404)
        self.assertEqual(self.c.get('/api/inscripciones/',{'grupo':self.b.pk}).data['count'],0)
        self.assertEqual(self.c.get('/api/deportistas/',{'grupo':self.b.pk}).data['count'],0)
        self.assertEqual(self.c.get(f'/api/inscripciones/{inscripcion.pk}/historial/').status_code,404)
        self.assertEqual(self.c.get(f'/api/deportistas/{ajena.identificador_publico}/').status_code,404)
        self.assertEqual(self.c.get('/api/inscripciones/cupos/',{'grupo':self.b.pk}).status_code,404)
    def test_origen_y_persona_ajenos_no_se_exponen(self):
        ajena=self.persona_nueva('Ajena')
        self.assertEqual(self.destinos(deportista=ajena.pk).status_code,400)
        self.assertEqual(self.proponer(persona=ajena).status_code,400)
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.destinos().status_code,400)
    def test_profesor_no_ejecuta_ni_aprueba(self):
        p=self.proponer().data['id']
        self.assertEqual(self.post(f'propuestas/{p}/aprobar/',{'version':1,'resolucion':'No permitido'}).status_code,403)
        self.assertEqual(self.post('inscripciones/',{'deportista':self.persona.pk,'grupo':self.b.pk,'fecha_ingreso':str(self.hoy),'motivo':'No permitido'}).status_code,403)
        self.assertEqual(self.post(f'inscripciones/{self.origen.pk}/trasladar/',{'version':1,'grupo_destino':self.b.pk,'motivo':'No permitido'}).status_code,403)
    def test_cambio_nivel_solo_coordinador(self):
        p=self.historica_nivel()
        self.assertEqual(self.aprobar(p.pk,self.admin).status_code,403)
        self.assertEqual(self.aprobar(p.pk).status_code,409)
        p.refresh_from_db();self.assertEqual(p.estado,'pendiente')
    def test_multi_inscripcion_bloquea_nivel_al_proponer(self):
        self.c.force_authenticate(self.coord);self.inscribir(grupo=self.b)
        self.c.force_authenticate(self.prof)
        r=self.proponer(tipo='nivel',destino=self.l)
        self.assertEqual(r.status_code,409);self.assertIn('deshabilitado',str(r.data))
        self.assertEqual(Propuesta.objects.count(),0)
    def test_segunda_inscripcion_posterior_impide_ascenso_parcial(self):
        p=self.historica_nivel().pk
        self.c.force_authenticate(self.coord);self.inscribir(grupo=self.b)
        antes=list(Inscripcion.objects.values())
        r=self.aprobar(p);self.assertEqual(r.status_code,409)
        self.assertIn('deshabilitado',str(r.data));self.assertEqual(list(Inscripcion.objects.values()),antes)
        self.assertEqual(Propuesta.objects.get(pk=p).estado,'pendiente')
    def test_reserva_o_inscripcion_futura_tambien_bloquean_ascenso_parcial(self):
        self.c.force_authenticate(self.coord);futura=self.inscribir(grupo=self.b,inicio=self.hoy+timedelta(days=1))
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.proponer(tipo='nivel',destino=self.l).status_code,409)
    def test_reserva_vigente_bloquea_nivel_y_vencida_no_crea_un_cambio_parcial(self):
        from unittest.mock import patch
        self.c.force_authenticate(self.coord);segunda=self.inscribir(grupo=self.b)
        self.assertEqual(self.post(f'inscripciones/{segunda.pk}/suspender/',{'version':1,'motivo':'Reserva ficticia','fecha_vencimiento':str(self.hoy)}).status_code,200)
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.proponer(tipo='nivel',destino=self.l).status_code,409)
        antes=list(Inscripcion.objects.values())
        manana=self.hoy+timedelta(days=1)
        with patch('django.utils.timezone.localdate',return_value=manana):
            datos=self.datos(tipo='nivel',destino=self.l);datos['fecha_efectiva']=str(manana)
            self.assertEqual(self.post('propuestas/',datos).status_code,409)
        self.assertEqual(list(Inscripcion.objects.values()),antes)
    def test_cupo_completo_rechazado_al_proponer_y_revalidado_al_aprobar(self):
        p=self.proponer().data['id']
        self.b.cupo_maximo=1;self.b.save()
        self.c.force_authenticate(self.coord);self.inscribir(persona=self.persona_nueva('Otra'),grupo=self.b)
        antes=list(Inscripcion.objects.values())
        self.assertEqual(self.aprobar(p).status_code,409)
        self.assertEqual(list(Inscripcion.objects.values()),antes)
        self.post(f'propuestas/{p}/cancelar/',{'version':1,'resolucion':'Revisar cupo'})
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.proponer().status_code,409)
        self.assertNotIn(self.b.pk,[x['id'] for x in self.destinos().data['results']])
    def test_conflicto_horario_con_tercera_inscripcion_rechazado(self):
        Horario.objects.filter(grupo=self.b).update(hora_inicio='11:00',hora_fin='13:00')
        Horario.objects.filter(grupo=self.x).update(hora_inicio='12:00',hora_fin='14:00')
        self.c.force_authenticate(self.coord);self.inscribir(grupo=self.x)
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.proponer().status_code,400)
        self.assertNotIn(self.b.pk,[x['id'] for x in self.destinos().data['results']])
    def test_origen_excluido_virtualmente_sin_cerrarlo(self):
        Horario.objects.filter(grupo=self.b).update(hora_inicio='10:00',hora_fin='11:00')
        antes=list(Inscripcion.objects.values())
        self.assertIn(self.b.pk,[x['id'] for x in self.destinos().data['results']])
        self.assertEqual(self.proponer().status_code,201)
        self.assertEqual(list(Inscripcion.objects.values()),antes)
    def test_horario_cambiado_entre_propuesta_y_decision_se_revalida(self):
        p=self.proponer().data['id']
        Horario.objects.filter(grupo=self.x).update(hora_inicio='12:00',hora_fin='13:00')
        self.c.force_authenticate(self.coord);self.inscribir(grupo=self.x)
        Horario.objects.filter(grupo=self.b).update(hora_inicio='12:00',hora_fin='13:00')
        antes=list(Inscripcion.objects.values())
        self.assertEqual(self.aprobar(p).status_code,400)
        self.assertEqual(list(Inscripcion.objects.values()),antes)
    def test_destino_inactivo_fuera_periodo_o_sin_horarios_no_se_ofrece(self):
        self.b.activo=False;self.b.save()
        self.assertNotIn(self.b.pk,[x['id'] for x in self.destinos().data['results']])
        self.assertEqual(self.proponer().status_code,400)
        self.b.activo=True;self.b.save();Horario.objects.filter(grupo=self.b).update(activo=False)
        self.assertEqual(self.proponer().status_code,400)
    def test_destino_fuera_periodo_no_se_ofrece_ni_admite(self):
        from organizacion.models import Periodo
        futuro=Periodo.objects.create(codigo='futuro-propuesta',nombre='Periodo futuro ficticio',fecha_inicio=self.hoy+timedelta(days=1),fecha_fin=self.hoy+timedelta(days=30))
        self.b.periodo=futuro;self.b.save()
        self.assertEqual(self.proponer().status_code,400)
        self.assertNotIn(self.b.pk,[x['id'] for x in self.destinos().data['results']])
    def test_origen_ajeno_del_mismo_profesor_no_se_confunde_con_deportista(self):
        otra=self.persona_nueva('Otra ficha')
        self.c.force_authenticate(self.coord);origen_otra=self.inscribir(persona=otra)
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.proponer(origen=origen_otra).status_code,403)
        self.assertEqual(Propuesta.objects.count(),0)
    def test_perdida_asignacion_del_autor_despues_de_proponer(self):
        p=self.proponer().data['id']
        Asignacion.objects.filter(grupo=self.a,usuario=self.prof).update(fecha_fin=self.hoy-timedelta(days=1))
        self.assertEqual(self.aprobar(p).status_code,403)
        self.assertEqual(Propuesta.objects.get(pk=p).estado,'pendiente')
    def test_perder_origen_no_se_elude_por_otro_grupo_del_mismo_alumno(self):
        p=self.proponer().data['id']
        Horario.objects.filter(grupo=self.x).update(hora_inicio='13:00',hora_fin='14:00')
        self.c.force_authenticate(self.coord);self.inscribir(grupo=self.x)
        Asignacion.objects.filter(grupo=self.a,usuario=self.prof).update(fecha_fin=self.hoy-timedelta(days=1))
        self.assertEqual(self.aprobar(p).status_code,403)
    def test_coordinador_relevado_no_puede_aprobar(self):
        p=self.proponer().data['id']
        from cuentas.models import Usuario
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.aprobar(p).status_code,403)
    def test_aprobacion_duplicada_y_conservacion_historial(self):
        p=self.proponer().data['id']
        self.assertEqual(self.aprobar(p).status_code,200)
        self.assertEqual(self.aprobar(p).status_code,409)
        self.origen.refresh_from_db();self.assertEqual(self.origen.estado,'finalizada')
        self.assertEqual(self.origen.grupo_id,self.a.pk)
        destino=Inscripcion.objects.get(inscripcion_anterior=self.origen)
        self.assertEqual(destino.deportista_id,self.persona.pk)
        self.assertEqual(Propuesta.objects.get(pk=p).inscripcion_resultante_id,destino.pk)
        self.assertEqual(CambioAdministrativo.objects.filter(accion='aprobar_aplicar').count(),1)
    def test_duplicados_pendientes_no_generan_500(self):
        self.assertEqual(self.proponer().status_code,201)
        self.assertEqual(self.proponer().status_code,409)
        self.assertEqual(Propuesta.objects.count(),1)
    def test_consulta_no_libera_reservas_vencidas_ni_crea_eventos(self):
        self.c.force_authenticate(self.coord)
        self.post(f'inscripciones/{self.origen.pk}/suspender/',{'version':1,'motivo':'Pausa','fecha_vencimiento':str(self.hoy)})
        from .models import EventoInscripcion
        antes=(list(ReservaCupo.objects.values()),EventoInscripcion.objects.count())
        self.c.force_authenticate(self.prof)
        self.destinos(tipo='inscripcion')
        self.assertEqual((list(ReservaCupo.objects.values()),EventoInscripcion.objects.count()),antes)
    def test_busqueda_paginada_minima_y_fecha_invalida(self):
        r=self.destinos(search=self.b.codigo)
        self.assertEqual([x['id'] for x in r.data['results']],[self.b.pk])
        self.assertEqual(self.destinos(fecha_efectiva=str(self.hoy+timedelta(days=1))).status_code,400)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.destinos().status_code,403)


class PropuestasConcurrentes(DatosPropuestas,TransactionTestCase):
    def competir(self,acciones):
        barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                c=APIClient();c.force_authenticate(self.coord);barrera.wait(timeout=10)
                return accion(c)
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar,acciones))
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_aprobaciones_misma_propuesta_solo_una(self):
        self.preparar_propuestas();p=self.proponer().data['id']
        def aprobar(c): return c.post(f'/api/propuestas/{p}/aprobar/',{'version':1,'resolucion':'Revisión concurrente'},format='json').status_code
        self.assertCountEqual(self.competir([aprobar,aprobar]),[200,409])
        self.assertEqual(Inscripcion.objects.count(),2)
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_propuestas_compiten_ultimo_cupo_sin_cierre_parcial(self):
        self.preparar_propuestas();self.b.cupo_maximo=1;self.b.save()
        otro=self.persona_nueva('Segunda');self.c.force_authenticate(self.coord);origen2=self.inscribir(persona=otro)
        self.c.force_authenticate(self.prof)
        p1=self.proponer().data['id'];p2=self.proponer(persona=otro,origen=origen2).data['id']
        def aprobar(pk):
            return lambda c: c.post(f'/api/propuestas/{pk}/aprobar/',{'version':1,'resolucion':'Cupo concurrente'},format='json').status_code
        self.assertCountEqual(self.competir([aprobar(p1),aprobar(p2)]),[200,409])
        self.assertEqual(Inscripcion.objects.filter(grupo=self.b).count(),1)
        self.assertEqual(Inscripcion.objects.filter(grupo=self.a,estado='activa').count(),1)
        self.assertEqual(Propuesta.objects.filter(estado='pendiente').count(),1)
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_propuestas_mismo_origen_solo_una_pendiente(self):
        self.preparar_propuestas()
        def crear(destino):
            def enviar(c):
                c.force_authenticate(self.prof)
                return c.post('/api/propuestas/',self.datos(destino=destino),format='json').status_code
            return enviar
        self.assertCountEqual(self.competir([crear(self.b),crear(self.x)]),[201,409])
        self.assertEqual(Propuesta.objects.count(),1)
        self.assertEqual(Inscripcion.objects.count(),1)
