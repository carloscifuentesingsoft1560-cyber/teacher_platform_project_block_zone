from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.exceptions import ValidationError as ErrorModelo
from django.db import connection, transaction, IntegrityError, connections, close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient
from .tests import DatosFase3
from .models import Acudiente, VinculoAcudiente, TipoAutorizacion, ComprobacionFacultad, Autorizacion
from .facultades import comprobar_facultad
from auditoria.models import CambioAdministrativo


class DatosFacultades(DatosFase3):
    def preparar_facultades(self):
        self.preparar()
        self.contacto = Acudiente.objects.create(nombres='Adulto',apellidos='Ficticio',telefono='3000000000',creado_por=self.admin,actualizado_por=self.admin)
        self.v = VinculoAcudiente.objects.create(deportista=self.persona,acudiente=self.contacto,parentesco='Madre',es_contacto_principal=True,
            fecha_inicio=self.hoy-timedelta(days=1),creado_por=self.admin,actualizado_por=self.admin)
        self.tipo = TipoAutorizacion.objects.create(codigo='ficticia-facultad',numero_version=1,finalidad='Finalidad ficticia',referencia_texto_aprobado='Referencia ficticia',creado_por=self.admin,actualizado_por=self.admin)
    def decidir(self,**cambios):
        return self.post(f'vinculos-acudientes/{self.v.pk}/verificar/',self.comprobacion(self.tipo,**cambios))
    def autorizar(self,**cambios):
        return self.post('autorizaciones/',{'deportista':self.persona.pk,'tipo':self.tipo.pk,'otorgante':'acudiente','vinculo_acudiente':self.v.pk,
            'decision':'otorgada','declarada_en':timezone.now().isoformat(),'vigente_desde':str(self.hoy),'referencia_evidencia':'Referencia privada ficticia',**cambios})


class FacultadesSeguras(DatosFacultades,TestCase):
    def setUp(self):
        self.preparar_facultades()
    def test_version_sola_y_numero_version_no_acreditan(self):
        for datos in ({'version':1},{'numero_version':1}):
            self.assertEqual(self.post(f'vinculos-acudientes/{self.v.pk}/verificar/',datos).status_code,400)
        self.assertEqual(ComprobacionFacultad.objects.count(),0)
        self.v.refresh_from_db(); self.assertEqual(self.v.version,1)
    def test_parentesco_contacto_y_estado_legacy_no_conceden_facultad(self):
        self.assertEqual(self.autorizar().status_code,400)
        VinculoAcudiente.objects.filter(pk=self.v.pk).update(facultad_para_autorizar='verificada',verificada_por=self.admin,verificada_en=timezone.now())
        self.assertEqual(self.autorizar().status_code,400)
        r=self.c.get(f'/api/vinculos-acudientes/{self.v.pk}/')
        self.assertEqual(r.data['facultad_para_autorizar'],'pendiente')
    def test_evidencia_obligatoria_opaca_sin_copias(self):
        for referencia in ('','   ','3000000000','12345678901234567890123456789012','https://ejemplo.test/documento','00000000-0000-0000-0000-000000000000'):
            self.assertEqual(self.decidir(referencia_evidencia=referencia).status_code,400)
        self.assertEqual(ComprobacionFacultad.objects.count(),0)
    def test_metodo_no_prueba_suficiencia(self):
        for metodo in ('presencial','documental'):
            self.assertEqual(self.decidir(metodo=metodo,facultad_contrastada=False).status_code,400)
            self.assertEqual(self.decidir(metodo=metodo,identidad_contrastada=False).status_code,400)
        self.assertEqual(self.autorizar().status_code,400)
    def test_decision_completa_y_responsable_servidor(self):
        r=self.decidir();self.assertEqual(r.status_code,200)
        e=ComprobacionFacultad.objects.get()
        self.assertEqual(e.responsable,self.coord);self.assertIsNotNone(e.registrada_en)
        self.assertEqual(self.autorizar().status_code,201)
        self.assertEqual(Autorizacion.objects.get().comprobacion_facultad_id,e.pk)
        self.v.refresh_from_db();self.assertEqual(self.v.facultad_para_autorizar,'pendiente')
    def test_admin_y_metodo_presencial(self):
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.decidir(metodo='presencial').status_code,200)
    def test_pendiente_y_rechazada_no_autorizan(self):
        for version,resultado in ((1,'pendiente'),(2,'rechazada')):
            self.assertEqual(self.decidir(version=version,resultado=resultado,facultad_contrastada=False).status_code,200)
            self.assertEqual(self.autorizar().status_code,400)
        self.assertEqual(list(ComprobacionFacultad.objects.values_list('resultado',flat=True)),['rechazada','pendiente'])
    def test_revocacion_historial_y_sin_borrar_autorizacion(self):
        self.decidir();self.assertEqual(self.autorizar().status_code,201)
        self.assertEqual(self.decidir(version=2,resultado='revocada').status_code,200)
        self.assertEqual(self.autorizar(tipo=self.tipo.pk).status_code,400)
        self.assertEqual(ComprobacionFacultad.objects.count(),2)
        self.assertEqual(Autorizacion.objects.count(),1)
        self.assertFalse(self.c.get('/api/autorizaciones/').data['results'][0]['facultad_vigente'])
    def test_no_revocar_sin_acreditacion(self):
        self.assertEqual(self.decidir(resultado='revocada').status_code,400)
    def test_vencimiento_y_cobertura_de_vigencias(self):
        self.assertEqual(self.decidir(vigente_hasta=str(self.hoy)).status_code,200)
        self.assertEqual(self.autorizar().status_code,400)
        self.assertEqual(self.autorizar(vigente_hasta=str(self.hoy)).status_code,201)
        with patch('deportistas.facultades.timezone.localdate',return_value=self.hoy+timedelta(days=1)):
            self.assertEqual(self.autorizar(vigente_hasta=str(self.hoy)).status_code,400)
    def test_otra_finalidad_o_version_no_hereda_facultad(self):
        self.decidir()
        otra=TipoAutorizacion.objects.create(codigo=self.tipo.codigo,numero_version=2,finalidad='Otra versión',referencia_texto_aprobado='Referencia ficticia',creado_por=self.admin,actualizado_por=self.admin)
        self.assertEqual(self.autorizar(tipo=otra.pk).status_code,400)
    def test_no_cambiar_estado_con_patch_ni_falsificar_actor_fecha(self):
        self.assertEqual(self.c.patch(f'/api/vinculos-acudientes/{self.v.pk}/',{'facultad_para_autorizar':'verificada','version':1},format='json').status_code,400)
        for campo in ('responsable','registrada_en','numero_documento'):
            self.assertEqual(self.decidir(**{campo:'dato-no-admitido'}).status_code,400)
    def test_sin_permiso_no_consulta_historia_ni_decide(self):
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.decidir().status_code,403)
        self.assertEqual(self.c.get(f'/api/vinculos-acudientes/{self.v.pk}/historial-facultades/').status_code,403)
        self.c.force_authenticate(None)
        self.assertEqual(self.decidir().status_code,403)
    def test_coordinador_relevado_o_desactivado_no_decide(self):
        from cuentas.models import Usuario
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        self.assertEqual(self.decidir().status_code,403)
    def test_csrf_no_se_elimina(self):
        c=APIClient(enforce_csrf_checks=True);c.force_login(self.admin)
        self.assertEqual(c.post(f'/api/vinculos-acudientes/{self.v.pk}/verificar/',self.comprobacion(self.tipo),format='json').status_code,403)
    def test_doble_envio_conflicto_sin_duplicacion(self):
        self.assertEqual(self.decidir().status_code,200)
        self.assertEqual(self.decidir().status_code,409)
        self.assertEqual(ComprobacionFacultad.objects.count(),1)
    def test_historia_protegida_y_referencia_fuera_auditoria_y_listado(self):
        self.decidir();e=ComprobacionFacultad.objects.get()
        self.assertNotIn(str(e.referencia_evidencia),str(list(CambioAdministrativo.objects.values())))
        self.assertNotIn(str(e.referencia_evidencia),str(self.c.get('/api/vinculos-acudientes/').data))
        self.assertEqual(self.c.get(f'/api/vinculos-acudientes/{self.v.pk}/historial-facultades/').data[0]['referencia_evidencia'],str(e.referencia_evidencia))
        with self.assertRaises(ErrorModelo):
            e.save()
        with self.assertRaises(ErrorModelo):
            ComprobacionFacultad.objects.filter(pk=e.pk).update(resultado='revocada')
        with self.assertRaises(ErrorModelo):
            e.delete()
    def test_sql_postgresql_no_altera_ni_borra_historia(self):
        if connection.vendor!='postgresql': self.skipTest('Trigger exclusivo PostgreSQL')
        self.decidir()
        for sql in ("UPDATE deportistas_comprobacionfacultad SET resultado='revocada'",'DELETE FROM deportistas_comprobacionfacultad'):
            with self.assertRaises(IntegrityError),transaction.atomic():
                with connection.cursor() as c: c.execute(sql)
    def test_rollback_auditoria_y_evento_atomicos(self):
        with patch('deportistas.facultades.registrar',side_effect=RuntimeError('fallo ficticio')):
            with self.assertRaises(RuntimeError):self.decidir()
        self.assertEqual(ComprobacionFacultad.objects.count(),0)
        self.v.refresh_from_db();self.assertEqual(self.v.version,1)
    def test_fecha_futura_vinculo_finalizado_y_tipo_inactivo(self):
        self.assertEqual(self.decidir(comprobada_en=(timezone.now()+timedelta(days=1)).isoformat()).status_code,400)
        TipoAutorizacion.objects.filter(pk=self.tipo.pk).update(activo=False)
        self.assertEqual(self.decidir().status_code,400)
        TipoAutorizacion.objects.filter(pk=self.tipo.pk).update(activo=True)
        VinculoAcudiente.objects.filter(pk=self.v.pk).update(fecha_fin=self.hoy)
        self.assertEqual(self.decidir().status_code,400)
    def test_texto_usado_en_comprobacion_no_se_reescribe(self):
        self.decidir(); self.c.force_authenticate(self.admin)
        self.assertEqual(self.c.patch(f'/api/tipos-autorizacion/{self.tipo.pk}/',{'version':1,'finalidad':'Finalidad alterada'},format='json').status_code,400)
    def test_otro_deportista_no_usa_la_comprobacion_y_referencia_no_se_falsifica(self):
        self.decidir(); otra=self.persona_nueva('Otra ficha ficticia')
        self.assertEqual(self.autorizar(deportista=otra.pk).status_code,400)
        self.assertEqual(self.autorizar(comprobacion_facultad=ComprobacionFacultad.objects.get().pk).status_code,400)
    def test_migracion_pendiente_no_deja_usar_via_antigua(self):
        with patch('deportistas.facultades.esquema_facultades',return_value=False):
            self.assertEqual(self.decidir().status_code,503)
            self.assertEqual(self.c.get('/api/autorizaciones/').status_code,503)
            self.assertEqual(self.c.get('/api/acudientes/').status_code,200)
            self.assertEqual(self.c.get('/api/paneles/coordinador/resumen/').status_code,200)


class ConcurrenciaFacultades(DatosFacultades,TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_decisiones_misma_version_solo_una(self):
        self.preparar_facultades();barrera=Barrier(2)
        def decidir(resultado):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                comprobar_facultad(self.v,self.coord,self.comprobacion(self.tipo,resultado=resultado))
                return 'confirmada'
            except APIException:
                return 'rechazada'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(decidir,['verificada','rechazada'])),['confirmada','rechazada'])
        self.assertEqual(ComprobacionFacultad.objects.count(),1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_revocar_y_otorgar_son_serializables(self):
        self.preparar_facultades();self.decidir();barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                c=APIClient();c.force_authenticate(self.coord);barrera.wait(timeout=10)
                if accion=='revocar':
                    return c.post(f'/api/vinculos-acudientes/{self.v.pk}/verificar/',self.comprobacion(self.tipo,version=2,resultado='revocada'),format='json').status_code
                return c.post('/api/autorizaciones/',{'deportista':self.persona.pk,'tipo':self.tipo.pk,'otorgante':'acudiente','vinculo_acudiente':self.v.pk,
                    'decision':'otorgada','declarada_en':timezone.now().isoformat(),'vigente_desde':str(self.hoy),'referencia_evidencia':'Referencia privada ficticia'},format='json').status_code
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(ejecutar,['revocar','otorgar']))
        self.assertEqual(resultados[0],200);self.assertIn(resultados[1],(201,400))
        self.assertEqual(self.autorizar().status_code,400)
        for r in self.c.get('/api/autorizaciones/').data['results']:
            self.assertFalse(r['facultad_vigente'])

    @skipUnlessDBFeature('has_select_for_update')
    def test_desactivacion_concurrente_revalida_coordinador(self):
        self.preparar_facultades();barrera=Barrier(2)
        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if accion=='desactivar':
                    from organizacion.servicios import bloquear_usuarios
                    from cuentas.models import Usuario
                    with transaction.atomic():
                        bloquear_usuarios(self.admin)
                        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
                    return 'desactivada'
                try:
                    comprobar_facultad(self.v,self.coord,self.comprobacion(self.tipo))
                    return 'verificada'
                except APIException:
                    return 'denegada'
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(ejecutar,['desactivar','verificar']))
        self.assertEqual(resultados[0],'desactivada');self.assertIn(resultados[1],('verificada','denegada'))
        self.assertEqual(self.decidir(version=2).status_code,403)
