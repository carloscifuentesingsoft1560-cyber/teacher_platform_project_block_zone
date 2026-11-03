from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,TransactionTestCase,skipUnlessDBFeature
from django.db import connections,connection,close_old_connections
from django.utils import timezone
from rest_framework.exceptions import APIException
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from deportistas.tests import DatosFase3
from deportistas.models import Deportista
from .models import Inscripcion,ReservaCupo,EventoInscripcion,Propuesta
from .servicios import inscribir,liberar_vencidas
from cuentas.models import Usuario
from organizacion.models import Asignacion

class InscripcionesPruebas(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
    def test_grupos_contiguos_compatibles_misma_identidad(self):
        a=self.inscribir()
        b=self.inscribir(grupo=self.b)
        self.assertEqual(a.deportista_id,b.deportista_id)
        self.assertEqual(Deportista.objects.count(),1)
    def test_cruce_rechazado(self):
        self.inscribir()
        with self.assertRaises(APIException):
            self.inscribir(grupo=self.x)
    def test_duplicado_rechazado(self):
        self.inscribir()
        with self.assertRaises(APIException):
            self.inscribir()
    def test_periodo_fuera_de_fechas(self):
        with self.assertRaises(APIException):
            self.inscribir(inicio=self.hoy-timedelta(days=40))
    def test_cupo_completo(self):
        self.inscribir()
        self.inscribir(persona=self.persona_nueva("Dos"))
        with self.assertRaises(APIException):
            self.inscribir(persona=self.persona_nueva("Tres"))
    def test_suspension_reserva_y_vencimiento_inclusivo(self):
        i=self.inscribir()
        r=self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa ficticia","fecha_vencimiento":str(self.hoy)})
        self.assertEqual(r.status_code,200)
        self.inscribir(persona=self.persona_nueva("Dos"))
        with self.assertRaises(APIException):
            self.inscribir(persona=self.persona_nueva("Tres"))
        self.assertEqual(liberar_vencidas(self.coord),0)
        self.assertEqual(ReservaCupo.objects.get().autorizada_por,self.coord)
    def test_suspension_sin_fecha_no_valida(self):
        i=self.inscribir()
        self.assertEqual(self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa"}).status_code,400)
    def test_reserva_vencida_se_libera_una_vez_con_historial(self):
        i=self.inscribir()
        self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa","fecha_vencimiento":str(self.hoy)})
        manana=self.hoy+timedelta(days=1)
        with patch("django.utils.timezone.localdate",return_value=manana):
            self.assertEqual(liberar_vencidas(self.coord),1)
            self.assertEqual(liberar_vencidas(self.coord),0)
        i.refresh_from_db()
        self.assertEqual(i.estado,"finalizada")
        self.assertEqual(i.fecha_salida,manana)
        self.assertEqual(i.eventos.filter(tipo="liberar_reserva").count(),1)
        self.assertEqual(Inscripcion.objects.count(),1)
    def test_get_no_libera_ni_escribe(self):
        i=self.inscribir()
        self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa","fecha_vencimiento":str(self.hoy)})
        with patch("django.utils.timezone.localdate",return_value=self.hoy+timedelta(days=1)):
            antes=EventoInscripcion.objects.count()
            self.assertEqual(self.c.get(f"/api/inscripciones/cupos/?grupo={self.a.pk}").data["ocupacion_maxima"],0)
            self.assertEqual(EventoInscripcion.objects.count(),antes)
            self.assertIsNone(ReservaCupo.objects.get().liberada_en)
    def test_reanudar_revalida_horarios_futuros(self):
        i=self.inscribir()
        self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa","fecha_vencimiento":str(self.hoy)})
        # Alta futura tras la reserva es válida, pero bloquea una reincorporación incompatible.
        self.inscribir(grupo=self.x,inicio=self.hoy+timedelta(days=1))
        self.assertEqual(self.post(f"inscripciones/{i.pk}/reanudar/",{"version":2,"motivo":"Retorno"}).status_code,400)
        i.refresh_from_db()
        self.assertEqual(i.estado,"suspendida")
    def test_cambio_horario_con_inscripcion_compartida(self):
        self.inscribir()
        self.inscribir(grupo=self.b)
        r=self.c.patch(f"/api/organizacion/grupos/{self.a.pk}/",{"horarios":[{"dia":self.hoy.weekday(),"hora_inicio":"10:30","hora_fin":"11:30"}]},format="json")
        self.assertEqual(r.status_code,400)
        self.assertEqual(str(self.a.horarios.get(activo=True).hora_inicio),"10:00:00")
    def test_no_reducir_cupo_ni_archivar_con_inscritos(self):
        self.inscribir()
        self.inscribir(persona=self.persona_nueva("Dos"))
        for datos in [{"cupo_maximo":1},{"activo":False}]:
            self.assertEqual(self.c.patch(f"/api/organizacion/grupos/{self.a.pk}/",datos,format="json").status_code,400)
    def test_no_reescribir_periodo_con_historial(self):
        self.inscribir()
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.c.patch(f"/api/organizacion/periodos/{self.periodo.pk}/",{"fecha_fin":str(self.hoy+timedelta(days=50))},format="json").status_code,400)
    def test_traslado_preserva_origen_y_eventos(self):
        i=self.inscribir()
        r=self.post(f"inscripciones/{i.pk}/trasladar/",{"version":1,"grupo_destino":self.b.pk,"motivo":"Cambio ficticio"})
        self.assertEqual(r.status_code,200)
        i.refresh_from_db()
        self.assertEqual(i.estado,"finalizada")
        self.assertEqual(Inscripcion.objects.count(),2)
        self.assertEqual(Inscripcion.objects.get(pk=r.data["id"]).inscripcion_anterior_id,i.pk)
    def test_traslado_sin_cupo_revierte_origen(self):
        i=self.inscribir()
        self.inscribir(persona=self.persona_nueva("Dos"),grupo=self.b)
        self.inscribir(persona=self.persona_nueva("Tres"),grupo=self.b)
        self.assertEqual(self.post(f"inscripciones/{i.pk}/trasladar/",{"version":1,"grupo_destino":self.b.pk,"motivo":"Cambio"}).status_code,409)
        i.refresh_from_db()
        self.assertEqual(i.estado,"activa")
        self.assertIsNone(i.fecha_salida)
    def test_profesor_no_ejecuta_inscripciones_o_estados(self):
        i=self.inscribir()
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.post("inscripciones/",{}).status_code,403)
        self.assertEqual(self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"No"}).status_code,403)
    def test_profesor_no_accede_historial_ajeno(self):
        i=self.inscribir()
        self.c.force_authenticate(self.otro)
        self.assertEqual(self.c.get(f"/api/inscripciones/{i.pk}/historial/").status_code,404)
    def test_retiro_y_reingreso_conserva_identidad(self):
        i=self.inscribir()
        self.assertEqual(self.post(f"inscripciones/{i.pk}/retirar/",{"version":1,"motivo":"Retiro"}).status_code,200)
        nuevo=self.inscribir(inicio=self.hoy)
        self.assertEqual(nuevo.deportista_id,i.deportista_id)
        self.assertEqual(Inscripcion.objects.count(),2)
    def test_administrador_no_elude_cambio_nivel(self):
        i=self.inscribir()
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.post(f"inscripciones/{i.pk}/trasladar/",{"version":1,"grupo_destino":self.l.pk,"motivo":"Cambio"}).status_code,400)

class PropuestasPruebas(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
        self.origen=self.inscribir()
    def proponer(self,tipo="traslado",destino=None):
        self.c.force_authenticate(self.prof)
        return self.post("propuestas/",{"tipo":tipo,"deportista":self.persona.pk,"inscripcion_origen":self.origen.pk,"grupo_destino":(destino or self.b).pk,"fecha_efectiva":str(self.hoy),"justificacion":"Propuesta ficticia"})
    def aprobar(self,r):
        self.c.force_authenticate(self.coord)
        return self.post(f"propuestas/{r.data['id']}/aprobar/",{"version":1,"resolucion":"Decisión ficticia"})
    def test_proponer_no_ejecuta(self):
        r=self.proponer()
        self.assertEqual(r.status_code,201)
        self.assertEqual(Inscripcion.objects.count(),1)
        self.assertEqual(r.data["estado"],"pendiente")
    def test_aprobacion_unica_preserva_autoria(self):
        r=self.proponer()
        aprobado=self.aprobar(r)
        self.assertEqual(aprobado.status_code,200)
        self.assertEqual(aprobado.data["creado_por"],self.prof.pk)
        self.assertEqual(aprobado.data["resuelta_por"],self.coord.pk)
        self.assertEqual(self.aprobar(r).status_code,409)
        self.assertEqual(Inscripcion.objects.count(),2)
    def test_fuera_ambito(self):
        self.c.force_authenticate(self.otro)
        r=self.post("propuestas/",{"tipo":"inscripcion","deportista":self.persona.pk,"grupo_destino":self.b.pk,"fecha_efectiva":str(self.hoy),"justificacion":"No"})
        self.assertEqual(r.status_code,400)
    def test_destino_sin_asignacion_admite_propuesta_sin_acceso_general(self):
        Asignacion.objects.filter(grupo=self.b).delete()
        self.assertEqual(self.proponer().status_code,201)
        self.assertEqual(self.c.get(f'/api/organizacion/grupos/{self.b.pk}/').status_code,404)
    def test_profesor_no_aprueba(self):
        r=self.proponer()
        self.assertEqual(self.post(f"propuestas/{r.data['id']}/aprobar/",{"version":1,"resolucion":"No"}).status_code,403)
    def test_cambio_nivel_solo_coordinador_decide(self):
        p=Propuesta.objects.create(tipo='nivel',deportista=self.persona,inscripcion_origen=self.origen,
            grupo_destino=self.l,fecha_efectiva=self.hoy,justificacion='Historia ficticia',
            creado_por=self.prof,actualizado_por=self.prof)
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.post(f"propuestas/{p.pk}/aprobar/",{"version":1,"resolucion":"No"}).status_code,403)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f"propuestas/{p.pk}/aprobar/",{"version":1,"resolucion":"No"}).status_code,409)
        p.refresh_from_db();self.assertEqual(p.estado,'pendiente')
        self.origen.refresh_from_db()
        self.assertEqual(self.origen.grupo.nivel_id,self.n.pk)
    def test_coordinador_desactivado_no_resuelve(self):
        r=self.proponer()
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.aprobar(r).status_code,403)
        self.assertEqual(Propuesta.objects.get().estado,"pendiente")
    def test_relevo_no_reutiliza_actor_anterior(self):
        r=self.proponer()
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        Usuario.objects.create_user(username="ficticio_relevo",rol="coordinador")
        self.assertEqual(self.aprobar(r).status_code,403)
    def test_docente_desasignado_impide_aprobar(self):
        r=self.proponer()
        Asignacion.objects.filter(usuario=self.prof).update(fecha_fin=self.hoy-timedelta(days=1))
        self.assertEqual(self.aprobar(r).status_code,403)
    def test_version_origen_modificada(self):
        r=self.proponer()
        Inscripcion.objects.filter(pk=self.origen.pk).update(version=2)
        self.assertEqual(self.aprobar(r).status_code,409)
    def test_rechazo_conserva_propuesta_no_inscribe(self):
        r=self.proponer()
        self.c.force_authenticate(self.coord)
        resultado=self.post(f"propuestas/{r.data['id']}/rechazar/",{"version":1,"resolucion":"No procede"})
        self.assertEqual(resultado.status_code,200)
        self.assertEqual(resultado.data["estado"],"rechazada")
        self.assertEqual(Inscripcion.objects.count(),1)
    def test_propuesta_sin_autor_falsificable(self):
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.post("propuestas/",{"creado_por":self.admin.pk}).status_code,400)

class ConcurrenciaPostgresql(DatosFase3,TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_operaciones_sobre_ultimo_cupo(self):
        self.preparar()
        self.a.cupo_maximo=1
        self.a.save()
        segunda=self.persona_nueva("Segunda")
        barrera=Barrier(2)
        def competir(pk):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                inscribir(Deportista.objects.get(pk=pk),self.a,self.hoy,self.coord,"Alta concurrente ficticia")
                return "creada"
            except APIException:
                return "rechazada"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(competir,[self.persona.pk,segunda.pk]))
        self.assertCountEqual(resultados,["creada","rechazada"])
        self.assertEqual(Inscripcion.objects.count(),1)

class CasosAdicionales(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
    def test_docente_propone_inscripcion_adicional_y_coordinador_ejecuta(self):
        self.inscribir()
        self.c.force_authenticate(self.prof)
        r=self.post("propuestas/",{"tipo":"inscripcion","deportista":self.persona.pk,"grupo_destino":self.b.pk,"fecha_efectiva":str(self.hoy),"justificacion":"Grupo adicional compatible"})
        self.assertEqual(r.status_code,201)
        self.assertEqual(Inscripcion.objects.count(),1)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post(f"propuestas/{r.data['id']}/aprobar/",{"version":1,"resolucion":"Autorizada"}).status_code,200)
        self.assertEqual(Inscripcion.objects.count(),2)
    def test_cancelar_propuesta_no_modifica_inscripciones(self):
        self.inscribir()
        self.c.force_authenticate(self.prof)
        r=self.post("propuestas/",{"tipo":"inscripcion","deportista":self.persona.pk,"grupo_destino":self.b.pk,"fecha_efectiva":str(self.hoy),"justificacion":"Propuesta cancelable"})
        self.assertEqual(self.post(f"propuestas/{r.data['id']}/cancelar/",{"version":1,"resolucion":"Retirada por autor"}).status_code,200)
        self.assertEqual(Propuesta.objects.get().estado,"cancelada")
        self.assertEqual(Inscripcion.objects.count(),1)
    def test_historial_docente_no_revela_motivo_administrativo(self):
        i=self.inscribir()
        self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Motivo administrativo privado","fecha_vencimiento":str(self.hoy)})
        self.c.force_authenticate(self.prof)
        r=self.c.get(f"/api/inscripciones/{i.pk}/historial/")
        self.assertEqual(r.status_code,200)
        self.assertNotIn("Motivo administrativo privado",str(r.data))
        self.assertNotIn("motivo",r.data["reservas"][0])
    def test_estructura_de_grupo_con_historial_sin_docentes_no_se_reescribe(self):
        self.inscribir()
        Asignacion.objects.filter(grupo=self.a).delete()
        self.assertEqual(self.c.patch(f"/api/organizacion/grupos/{self.a.pk}/",{"nivel":self.n2.pk},format="json").status_code,400)
    def test_expiracion_es_visible_sin_escritura_y_liberacion_permite_reingreso(self):
        i=self.inscribir()
        self.post(f"inscripciones/{i.pk}/suspender/",{"version":1,"motivo":"Pausa","fecha_vencimiento":str(self.hoy)})
        with patch("django.utils.timezone.localdate",return_value=self.hoy+timedelta(days=1)):
            r=self.c.get(f"/api/inscripciones/{i.pk}/")
            self.assertEqual(r.data["situacion_temporal"],"reserva_vencida")
            nueva=self.inscribir(inicio=self.hoy+timedelta(days=1))
        self.assertNotEqual(nueva.pk,i.pk)
        i.refresh_from_db()
        self.assertEqual(i.causa_salida,"reserva_vencida")
        self.assertEqual(i.eventos.filter(tipo="liberar_reserva").count(),1)
