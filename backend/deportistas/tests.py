from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.db import IntegrityError,transaction
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Disciplina,Nivel,Periodo,Grupo,Horario,Asignacion
from deportistas.models import Deportista,Acudiente,VinculoAcudiente,TipoAutorizacion,Autorizacion
from auditoria.models import CambioAdministrativo
from inscripciones.servicios import inscribir

class DatosFase3:
    def preparar(self):
        self.hoy=timezone.localdate()
        self.admin=Usuario.objects.create_user(username="ficticio_admin_f3",rol="administrador")
        self.coord=Usuario.objects.create_user(username="ficticio_coord_f3",rol="coordinador")
        self.prof=Usuario.objects.create_user(username="ficticio_prof_f3",rol="profesor")
        self.otro=Usuario.objects.create_user(username="ficticio_otro_f3",rol="profesor")
        self.d,_=Disciplina.objects.get_or_create(codigo="escalada",defaults={"nombre":"Escalada"})
        self.n,_=Nivel.objects.get_or_create(disciplina=self.d,codigo="nivel-1",defaults={"nombre":"Nivel 1","orden":2})
        self.n2,_=Nivel.objects.get_or_create(disciplina=self.d,codigo="nivel-2",defaults={"nombre":"Nivel 2","orden":3})
        for codigo,nombre,orden in [('ludico','Lúdico',1),('especializacion','Escuela de especialización semicompetitiva',4),('alto-rendimiento','Alto rendimiento',5)]:
            Nivel.objects.get_or_create(disciplina=self.d,codigo=codigo,defaults={'nombre':nombre,'orden':orden})
        self.periodo=Periodo.objects.create(codigo="ficticio-f3",nombre="Periodo ficticio",fecha_inicio=self.hoy-timedelta(days=30),fecha_fin=self.hoy+timedelta(days=30))
        self.a=self.grupo("a","10:00","11:00")
        self.b=self.grupo("b","11:00","12:00")
        self.x=self.grupo("x","10:30","11:30")
        self.l=self.grupo("l","12:00","13:00",self.n2)
        for g in (self.a,self.b,self.x,self.l):
            Asignacion.objects.create(usuario=self.prof,grupo=g,tipo="profesor",fecha_inicio=self.periodo.fecha_inicio)
        self.persona=self.persona_nueva("Ana")
        self.c=APIClient()
        self.c.force_authenticate(self.coord)
    def grupo(self,codigo,inicio,fin,nivel=None):
        g=Grupo.objects.create(codigo="ficticio-"+codigo,nombre="Grupo ficticio "+codigo,disciplina=self.d,nivel=nivel or self.n,periodo=self.periodo,cupo_maximo=2)
        Horario.objects.create(grupo=g,dia=self.hoy.weekday(),hora_inicio=inicio,hora_fin=fin)
        return g
    def persona_nueva(self,nombre):
        return Deportista.objects.create(nombres=nombre,apellidos="Ficticio",fecha_nacimiento=self.hoy-timedelta(days=4000),creado_por=self.admin,actualizado_por=self.admin)
    def inscribir(self,persona=None,grupo=None,inicio=None):
        return inscribir(persona or self.persona,grupo or self.a,inicio or self.hoy-timedelta(days=2),self.coord,"Alta ficticia")
    def post(self,ruta,datos):
        return self.c.post("/api/"+ruta,datos,format="json")
    def comprobacion(self,tipo,version=1,**cambios):
        from uuid import uuid4
        return {"version":version,"metodo":"documental","referencia_evidencia":str(uuid4()),
            "tipo_autorizacion":tipo.pk,"resultado":"verificada","identidad_contrastada":True,
            "facultad_contrastada":True,"comprobada_en":(timezone.now()-timedelta(minutes=10)).isoformat(),
            "vigente_desde":str(self.hoy),**cambios}

class BaseDeportistas(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
    def test_alta_codigo_estable_y_edicion_versionada(self):
        r=self.post("deportistas/",{"nombres":"Nombre","apellidos":"Ficticio","fecha_nacimiento":str(self.hoy-timedelta(days=2000))})
        self.assertEqual(r.status_code,201)
        uuid=r.data["identificador_publico"]
        codigo=r.data["codigo_interno"]
        r=self.c.patch(f"/api/deportistas/{uuid}/",{"nombres":"Corregido","version":1},format="json")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data["codigo_interno"],codigo)
        self.assertEqual(r.data["version"],2)
    def test_version_obsoleta(self):
        r=self.c.patch(f"/api/deportistas/{self.persona.identificador_publico}/",{"nombres":"Cambio","version":99},format="json")
        self.assertEqual(r.status_code,409)
    def test_nacimiento_futuro(self):
        self.assertEqual(self.post("deportistas/",{"nombres":"A","apellidos":"Ficticio","fecha_nacimiento":str(self.hoy+timedelta(days=1))}).status_code,400)
    def test_codigo_unico_en_base(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            Deportista.objects.create(codigo_interno=self.persona.codigo_interno,nombres="Otro",apellidos="Ficticio",fecha_nacimiento=self.hoy,creado_por=self.admin,actualizado_por=self.admin)
    def test_no_campos_sensibles_o_actor_falsificado(self):
        datos={"nombres":"A","apellidos":"Ficticio","fecha_nacimiento":str(self.hoy),"creado_por":self.admin.pk,"diagnostico":"No almacenar"}
        self.assertEqual(self.post("deportistas/",datos).status_code,400)
    def test_profesor_solo_ficha_minima_propia(self):
        self.inscribir()
        ajena=self.persona_nueva("Ajena")
        self.c.force_authenticate(self.prof)
        r=self.c.get("/api/deportistas/")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data["count"],1)
        self.assertNotIn("fecha_nacimiento",r.data["results"][0])
        self.assertEqual(self.c.get(f"/api/deportistas/{ajena.identificador_publico}/").status_code,404)
        self.assertEqual(self.post("deportistas/",{}).status_code,403)
    def test_docente_pierde_acceso_al_finalizar_asignacion(self):
        self.inscribir()
        Asignacion.objects.filter(usuario=self.prof).update(fecha_fin=self.hoy-timedelta(days=1))
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get("/api/deportistas/").data["count"],0)
    def test_coordinador_relevado_no_usa_actor_en_cache(self):
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.post("deportistas/",{"nombres":"N","apellidos":"F","fecha_nacimiento":str(self.hoy)}).status_code,403)
    def test_no_desactivar_con_inscripciones(self):
        self.inscribir()
        self.assertEqual(self.c.patch(f"/api/deportistas/{self.persona.identificador_publico}/",{"estado":"inactivo","version":1},format="json").status_code,400)
    def test_contacto_no_es_representante_ni_tiene_acceso(self):
        r=self.post("acudientes/",{"nombres":"Contacto","apellidos":"Ficticio","telefono":"3000000000"})
        self.assertEqual(r.status_code,201)
        r=self.post("vinculos-acudientes/",{"deportista":self.persona.pk,"acudiente":r.data["id"],"fecha_inicio":str(self.hoy),"es_contacto_principal":True})
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.data["facultad_para_autorizar"],"pendiente")
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get("/api/acudientes/").status_code,403)
        self.assertEqual(self.c.get("/api/autorizaciones/").status_code,403)
    def test_autorizacion_requiere_facultad_y_revocacion_conserva(self):
        a=Acudiente.objects.create(nombres="Adulto",apellidos="Ficticio",telefono="3000000000",creado_por=self.admin,actualizado_por=self.admin)
        v=VinculoAcudiente.objects.create(deportista=self.persona,acudiente=a,fecha_inicio=self.hoy,creado_por=self.admin,actualizado_por=self.admin)
        t=TipoAutorizacion.objects.create(codigo="contacto",finalidad="Finalidad ficticia de prueba",referencia_texto_aprobado="Referencia ficticia",creado_por=self.admin,actualizado_por=self.admin)
        datos={"deportista":self.persona.pk,"tipo":t.pk,"otorgante":"acudiente","vinculo_acudiente":v.pk,"decision":"otorgada","declarada_en":timezone.now().isoformat(),"vigente_desde":str(self.hoy),"referencia_evidencia":"archivo-privado-ficticio"}
        self.assertEqual(self.post("autorizaciones/",datos).status_code,400)
        self.assertEqual(self.post(f"vinculos-acudientes/{v.pk}/verificar/",{"version":1}).status_code,400)
        self.assertEqual(self.post(f"vinculos-acudientes/{v.pk}/verificar/",self.comprobacion(t)).status_code,200)
        r=self.post("autorizaciones/",datos)
        self.assertEqual(r.status_code,201)
        self.assertEqual(self.post(f"autorizaciones/{r.data['id']}/revocar/",{"version":1,"motivo":"Solicitud ficticia"}).status_code,200)
        self.assertEqual(Autorizacion.objects.count(),1)
        self.assertIsNotNone(Autorizacion.objects.get().revocada_en)
        self.assertFalse(Usuario.objects.filter(username="Adulto").exists())
    def test_contacto_principal_solapado_rechazado(self):
        a=Acudiente.objects.create(nombres="Adulto",apellidos="Ficticio",telefono="3000000000",creado_por=self.admin,actualizado_por=self.admin)
        datos={"deportista":self.persona.pk,"acudiente":a.pk,"fecha_inicio":str(self.hoy),"es_contacto_principal":True}
        self.assertEqual(self.post("vinculos-acudientes/",datos).status_code,201)
        self.assertEqual(self.post("vinculos-acudientes/",{**datos,"fecha_inicio":str(self.hoy+timedelta(days=1))}).status_code,400)
    def test_politicas_sin_plazos_predeterminados_y_solo_admin(self):
        datos={"codigo":"ficticia","finalidad":"Prueba","criterio_conservacion":"Según política aprobada ficticia","procedimiento_supresion":"Revisión autorizada","referencia_aprobacion":"Prueba"}
        self.assertEqual(self.post("politicas-datos/",datos).status_code,403)
        self.c.force_authenticate(self.admin)
        r=self.post("politicas-datos/",datos)
        self.assertEqual(r.status_code,201)
        self.assertIsNone(r.data["edad_autonomia"])
    def test_auditoria_sin_valores_personales(self):
        self.post("deportistas/",{"nombres":"Nombre privado","apellidos":"Ficticio","fecha_nacimiento":str(self.hoy)})
        self.assertNotIn("Nombre privado",str(list(CambioAdministrativo.objects.values("campos"))))
    def test_anonimo_y_csrf(self):
        c=APIClient(enforce_csrf_checks=True)
        self.assertEqual(c.get("/api/deportistas/").status_code,403)
        c.force_login(self.admin)
        self.assertEqual(c.post("/api/deportistas/",{},format="json").status_code,403)
    def test_sin_esquema_responde_503(self):
        with patch("deportistas.permisos.esquema_disponible",return_value=False):
            self.assertEqual(self.c.get("/api/deportistas/").status_code,503)

class RechazoPrevioDeGestion(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
    def test_profesor_no_valida_relaciones_privadas_antes_de_denegar(self):
        self.c.force_authenticate(self.prof)
        for ruta in ("acudientes/","vinculos-acudientes/","autorizaciones/","tipos-autorizacion/","politicas-datos/"):
            for datos in ({},{"deportista":self.persona.pk,"acudiente":999999999}):
                self.assertEqual(self.post(ruta,datos).status_code,403)
    def test_coordinador_no_valida_configuracion_antes_de_denegar(self):
        for ruta in ("tipos-autorizacion/","politicas-datos/"):
            self.assertEqual(self.post(ruta,{}).status_code,403)
