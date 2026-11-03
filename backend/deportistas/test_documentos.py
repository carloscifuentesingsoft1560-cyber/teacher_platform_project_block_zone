import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import IntegrityError,transaction,connections,close_old_connections
from django.test import TestCase,TransactionTestCase,skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient
from auditoria.models import CambioAdministrativo
from cuentas.models import Usuario
from .tests import DatosFase3
from .models import Deportista,TipoDocumento,CambioDocumentoDeportista,Acudiente,VinculoAcudiente
from .documentos_reglas import enmascarar,PAISES_ISO
from .documentos_servicios import cambiar_documento

class IdentificacionDocumental(DatosFase3,TestCase):
    def setUp(self):
        self.preparar()
    def alta(self,numero="001234567",tipo="TI",pais=None):
        datos={"nombres":"Persona documental ficticia","apellidos":"Prueba","fecha_nacimiento":str(self.persona.fecha_nacimiento),
               "tipo_documento":tipo,"numero_documento":numero}
        if pais is not None:
            datos["pais_emisor"]=pais
        return self.post("deportistas/",datos)
    def cambio(self,numero,tipo="TI",pais=None,version=1,motivo="completar_pendiente"):
        return self.post(f"deportistas/{self.persona.identificador_publico}/cambiar-documento/",
            {"version":version,"tipo_documento":tipo,"numero_documento":numero,"pais_emisor":pais,"motivo":motivo})
    def test_catalogo_inicial_y_solo_admin_lo_modifica(self):
        self.assertEqual(set(TipoDocumento.objects.values_list("codigo",flat=True)),{"RC","TI","CC","CE","PA","PPT","DNI"})
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get("/api/tipos-documento/").status_code,200)
        self.assertEqual(self.post("tipos-documento/",{}).status_code,403)
        self.c.force_authenticate(self.coord)
        self.assertEqual(self.post("tipos-documento/",{}).status_code,403)
        self.c.force_authenticate(self.admin)
        r=self.post("tipos-documento/",{"codigo":"OTRO_APROBADO","nombre":"Documento ficticio aprobado","referencia_aprobacion":"Referencia institucional ficticia"})
        self.assertEqual(r.status_code,201)
        self.assertTrue(CambioAdministrativo.objects.filter(accion="crear_tipo_documento").exists())
    def test_normalizacion_ceros_y_tipo_minusculo(self):
        r=self.alta(" ００.１２-３ ","cc")
        self.assertEqual(r.status_code,201)
        self.assertEqual((r.data["tipo_documento"],r.data["numero_documento"],r.data["pais_emisor"]),("CC","00123","CO"))
    def test_letras_extranjeras_y_separadores_significativos(self):
        r=self.alta(" ab-00/7 ","PA"," ve ")
        self.assertEqual(r.status_code,201)
        self.assertEqual(r.data["numero_documento"],"AB-00/7")
        self.assertEqual(r.data["pais_emisor"],"VE")
    def test_registro_civil_alfanumerico(self):
        self.assertEqual(self.alta(" a.０１-2 ","RC").data["numero_documento"],"A012")
    def test_duplicado_normalizado_y_sin_exponer_numero(self):
        self.assertEqual(self.alta().status_code,201)
        r=self.alta("00.123.456-7")
        self.assertEqual(r.status_code,409)
        self.assertNotIn("001234567",json.dumps(r.data))
        self.assertEqual(Deportista.objects.count(),2)
    def test_unicidad_incluye_inactivos_y_archivados(self):
        r=self.alta()
        Deportista.objects.filter(pk=r.data["id"]).update(estado="archivado")
        self.assertEqual(self.alta().status_code,409)
    def test_pasaportes_mismo_numero_paises_distintos(self):
        self.assertEqual(self.alta("AB-001","PA","CO").status_code,201)
        self.assertEqual(self.alta("AB-001","PA","VE").status_code,201)
        self.assertEqual(self.alta("ab-001","PA","co").status_code,409)
    def test_multiples_documentos_pendientes_sin_fabricar_numero(self):
        r=self.post("deportistas/",{"nombres":"Pendiente","apellidos":"Ficticio","fecha_nacimiento":str(self.persona.fecha_nacimiento)})
        self.assertEqual(r.status_code,201)
        self.assertIsNone(r.data["tipo_documento"])
        self.assertIsNone(r.data["numero_documento"])
        self.assertIsNone(r.data["pais_emisor"])
        self.assertEqual(r.data["documento_presentacion"],"Documento pendiente")
        self.assertEqual(CambioDocumentoDeportista.objects.count(),0)
    def test_combinacion_incompleta_y_pais_invalido(self):
        for datos in [(None,"00123",None),("TI","",None),("PA","AB1",None),("PA","AB1","ZZ"),("TI","00123","VE")]:
            self.assertEqual(self.alta(datos[1],datos[0],datos[2]).status_code,400)
    def test_caracteres_no_admitidos_no_se_echoan(self):
        numero="ABC<>123456789"
        r=self.alta(numero,"PA","CO")
        self.assertEqual(r.status_code,400)
        self.assertNotIn(numero,json.dumps(r.data))
    def test_numero_es_texto_y_no_colapsa_ceros_iniciales(self):
        self.assertEqual(self.alta("00123").status_code,201)
        self.assertEqual(self.alta("123").status_code,201)
    def test_restricciones_sql_directo(self):
        tipo=TipoDocumento.objects.get(codigo="TI")
        self.alta()
        datos={"nombres":"Ficticio","apellidos":"Prueba","fecha_nacimiento":self.persona.fecha_nacimiento,"creado_por":self.admin,"actualizado_por":self.admin}
        for cambios in [
            {"tipo_documento":tipo,"numero_documento":"001234567","pais_emisor":"CO"},
            {"tipo_documento":tipo,"numero_documento":"00.123","pais_emisor":"CO"},
            {"tipo_documento":tipo,"numero_documento":"ab123","pais_emisor":"CO"},
            {"tipo_documento":tipo,"numero_documento":"123","pais_emisor":None},
            {"tipo_documento":tipo,"numero_documento":"123","pais_emisor":"ZZ"},
            {"tipo_documento":tipo,"numero_documento":"123","pais_emisor":"VE"},
        ]:
            with self.assertRaises(IntegrityError),transaction.atomic():
                Deportista.objects.create(**datos,**cambios)
    def test_cambio_preserva_id_uuid_codigo_y_relaciones(self):
        inscripcion=self.inscribir()
        acudiente=Acudiente.objects.create(nombres="Contacto",apellidos="Ficticio",telefono="3000000000",creado_por=self.admin,actualizado_por=self.admin)
        vinculo=VinculoAcudiente.objects.create(deportista=self.persona,acudiente=acudiente,fecha_inicio=self.hoy,creado_por=self.admin,actualizado_por=self.admin)
        identidad=(self.persona.pk,self.persona.identificador_publico,self.persona.codigo_interno)
        r=self.cambio("001234567")
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.cambio("001234567","CC",version=2,motivo="nuevo_documento").status_code,200)
        self.persona.refresh_from_db(); inscripcion.refresh_from_db(); vinculo.refresh_from_db()
        self.assertEqual((self.persona.pk,self.persona.identificador_publico,self.persona.codigo_interno),identidad)
        self.assertEqual(inscripcion.deportista_id,self.persona.pk)
        self.assertEqual(vinculo.deportista_id,self.persona.pk)
        self.assertEqual(Deportista.objects.count(),1)
        self.assertEqual(self.persona.version,3)
    def test_version_obsoleta_no_cambia_documento(self):
        self.cambio("001234567")
        self.assertEqual(self.cambio("999999999",version=1).status_code,409)
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.numero_documento,"001234567")
        self.assertEqual(CambioDocumentoDeportista.objects.count(),1)
    def test_conflicto_documental_revierte_campos_e_historia(self):
        self.alta()
        self.assertEqual(self.cambio("001234567").status_code,409)
        self.persona.refresh_from_db()
        self.assertIsNone(self.persona.numero_documento)
        self.assertEqual(self.persona.version,1)
        self.assertEqual(CambioDocumentoDeportista.objects.count(),1)
    def test_historial_y_auditoria_nunca_guardan_numeros_completos(self):
        primero,segundo="001234567890","009876543210"
        self.assertEqual(self.cambio(primero).status_code,200)
        self.assertEqual(self.cambio(segundo,version=2,motivo="correccion").status_code,200)
        historia=str(list(CambioDocumentoDeportista.objects.values()))
        auditoria=str(list(CambioAdministrativo.objects.values()))
        for numero in (primero,segundo):
            self.assertNotIn(numero,historia)
            self.assertNotIn(numero,auditoria)
        r=self.c.get(f"/api/deportistas/{self.persona.identificador_publico}/historial-documental/")
        self.assertEqual(r.status_code,200)
        self.assertNotIn(primero,json.dumps(r.data))
        self.assertNotIn(segundo,json.dumps(r.data))
        self.assertEqual(r.data["count"],2)
    def test_numero_corto_no_se_revela_en_mascara(self):
        for numero in ("1","1234"):
            self.assertEqual(enmascarar(numero),"****")
        self.assertEqual(self.cambio("1234").status_code,200)
        self.assertNotIn("1234",str(list(CambioDocumentoDeportista.objects.values())))
    def test_no_se_permite_numero_completo_en_historial_por_sql(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            CambioDocumentoDeportista.objects.create(deportista=self.persona,actor=self.admin,motivo="correccion",version_resultante=2,documento_nuevo_enmascarado="12345678")
    def test_motivo_codificado_sin_texto_personal(self):
        numero="001234567890"
        r=self.cambio(numero,motivo="correccion de "+numero)
        self.assertEqual(r.status_code,400)
        self.assertNotIn(numero,json.dumps(r.data))
    def test_no_admite_cambio_documental_por_patch_generico(self):
        self.assertEqual(self.c.patch(f"/api/deportistas/{self.persona.identificador_publico}/",{"version":1,"tipo_documento":"TI","numero_documento":"12345"},format="json").status_code,400)
    def test_sin_cambios_no_duplica_historial(self):
        self.cambio("001234567")
        r=self.cambio("00.123.456-7",version=2,motivo="correccion")
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data["version"],2)
        self.assertEqual(CambioDocumentoDeportista.objects.count(),1)
    def test_anulacion_por_error_preserva_traza_no_numero_completo(self):
        self.cambio("001234567890")
        self.assertEqual(self.cambio(None,tipo=None,version=2,motivo="nuevo_documento").status_code,400)
        self.assertEqual(self.cambio(None,tipo=None,version=2,motivo="anulacion_por_error").status_code,200)
        self.persona.refresh_from_db()
        self.assertIsNone(self.persona.numero_documento)
        self.assertEqual(CambioDocumentoDeportista.objects.count(),2)
    def test_profesor_recibe_solo_numero_enmascarado(self):
        numero="001234567890"
        self.cambio(numero); self.inscribir()
        self.c.force_authenticate(self.prof)
        for ruta in ("/api/deportistas/",f"/api/deportistas/{self.persona.identificador_publico}/"):
            r=self.c.get(ruta)
            self.assertEqual(r.status_code,200)
            self.assertNotIn(numero,json.dumps(r.data))
            ficha=r.data["results"][0] if "results" in r.data else r.data
            self.assertNotIn("numero_documento",ficha)
            self.assertNotIn("pais_emisor",ficha)
            self.assertEqual(ficha["numero_documento_enmascarado"],"****7890")
    def test_profesor_no_cambia_no_busca_ni_ve_historia(self):
        self.inscribir()
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.cambio("00123").status_code,403)
        self.assertEqual(self.post("deportistas/buscar-documento/",{}).status_code,403)
        self.assertEqual(self.c.get(f"/api/deportistas/{self.persona.identificador_publico}/historial-documental/").status_code,403)
    def test_busqueda_exacta_es_post_sin_auditar_numero(self):
        r=self.alta()
        numero=r.data["numero_documento"]
        r=self.post("deportistas/buscar-documento/",{"tipo_documento":"TI","numero_documento":"00.123.456-7"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.data["count"],1)
        self.assertNotIn(numero,str(list(CambioAdministrativo.objects.values())))
        self.assertEqual(self.c.get("/api/deportistas/buscar-documento/").status_code,405)
    def test_permisos_revalidados_al_desactivar(self):
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.cambio("00123").status_code,403)
    def test_csrf_en_cambio_documental(self):
        c=APIClient(enforce_csrf_checks=True)
        c.force_login(self.admin)
        self.assertEqual(c.post(f"/api/deportistas/{self.persona.identificador_publico}/cambiar-documento/",{},format="json").status_code,403)
    def test_pendiente_schema_controlado(self):
        with patch("deportistas.permisos.documentos_disponibles",return_value=False):
            self.assertEqual(self.c.get("/api/deportistas/").status_code,503)
            self.assertEqual(self.c.get("/api/paneles/coordinador/resumen/").status_code,200)
            self.inscribir()
            self.assertEqual(self.c.patch(f"/api/organizacion/grupos/{self.a.pk}/",{"cupo_maximo":3},format="json").status_code,503)
    def test_paises_sin_duplicados(self):
        self.assertEqual(len(PAISES_ISO),249)
        self.assertEqual(len(set(PAISES_ISO)),249)

class ConcurrenciaDocumental(DatosFase3,TransactionTestCase):
    def preparar(self):
        super().preparar()
        from .documentos_reglas import CATALOGO_INICIAL
        for codigo,nombre in CATALOGO_INICIAL:
            TipoDocumento.objects.get_or_create(codigo=codigo,defaults={"nombre":nombre,"referencia_aprobacion":"Catálogo ficticio de prueba"})
    def carrera(self,acciones):
        barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10); accion(); return "confirmada"
            except (APIException,IntegrityError):
                return "rechazada"
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar,acciones))
    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_personas_mismo_documento_solo_una(self):
        self.preparar(); otra=self.persona_nueva("Segunda")
        tipo=TipoDocumento.objects.get(codigo="TI")
        def cambio(p):
            return cambiar_documento(p,self.coord,{"version":1,"tipo_documento":tipo,"numero_documento":"00123456789","pais_emisor":"CO","motivo":"completar_pendiente"})
        self.assertCountEqual(self.carrera([lambda:cambio(self.persona),lambda:cambio(otra)]),["confirmada","rechazada"])
        self.assertEqual(Deportista.objects.filter(numero_documento="00123456789").count(),1)
    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_cambios_misma_version_solo_uno(self):
        self.preparar(); tipo=TipoDocumento.objects.get(codigo="TI")
        def cambio(numero):
            return cambiar_documento(self.persona,self.coord,{"version":1,"tipo_documento":tipo,"numero_documento":numero,"pais_emisor":"CO","motivo":"completar_pendiente"})
        self.assertCountEqual(self.carrera([lambda:cambio("00123456789"),lambda:cambio("00987654321")]),["confirmada","rechazada"])
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.version,2)
        self.assertEqual(CambioDocumentoDeportista.objects.count(),1)
