from uuid import uuid4
from django.test import TestCase, override_settings
from django.db import transaction, IntegrityError, DatabaseError, connection
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import Usuario, Persona, EnlaceIdentidad, PertenenciaRol, EventoRol
from cuentas.autorizacion import tiene_rol, puede, roles_vigentes
from cuentas.servicios_roles import otorgar, revocar
from cuentas.servicios_identidad import acreditar, revocar_enlace
from cuentas.coordinacion import relevar_coordinador
from auditoria.models import CambioAdministrativo


class NucleoInstitucional(TestCase):
    def setUp(self):
        self.admin=Usuario.objects.create_user(username='ficticio_admin',rol='administrador')
        self.prof=Usuario.objects.create_user(username='ficticio_prof',rol='profesor')
        self.ajeno=Usuario.objects.create_user(username='ficticio_otro',rol='profesor')
        self.coord=Usuario.objects.create_user(username='ficticio_coord',rol='coordinador')
        self.c=APIClient();self.c.force_authenticate(self.admin)

    def test_2a_accion_desconocida_y_anonimo_denegados(self):
        self.assertFalse(puede(self.admin,'inventada'))
        self.assertFalse(tiene_rol(AnonymousUser(),'administrador'))

    def test_2a_sesion_no_es_fuente_de_autoridad(self):
        copia=Usuario.objects.get(pk=self.prof.pk)
        copia.rol='administrador'
        self.assertFalse(puede(copia,'cuentas.gestionar'))

    def test_2a_roles_combinados_no_dan_autoridad_clinica(self):
        otorgar(self.admin,self.prof.pk,'routesetter','Función adicional')
        self.assertEqual(set(roles_vigentes(self.prof)),{'profesor','routesetter'})
        self.assertFalse(puede(self.prof,'cuentas.gestionar'))
        self.assertFalse(puede(self.prof,'medicina.alta'))

    def test_2b_no_acredita_identidades_al_crear_roles(self):
        self.assertEqual(Persona.objects.count(),0)
        self.assertEqual(EnlaceIdentidad.objects.count(),0)

    def test_2b_acreditacion_explicita_y_revocacion_conservan_perfiles(self):
        a=acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        persona=a.persona; ids=list(Usuario.objects.values_list('pk',flat=True))
        revocar_enlace(self.admin,a.pk,a.version)
        a.refresh_from_db();self.assertFalse(a.vigente)
        self.assertEqual(list(Usuario.objects.values_list('pk',flat=True)),ids)
        self.assertTrue(Persona.objects.filter(pk=persona.pk).exists())

    def test_2b_no_fusiona_ni_reenlaza_perfil_vigente(self):
        acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        with self.assertRaises(ValidationError):
            acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        self.assertEqual(Persona.objects.count(),1)

    def test_2b_version_persona_obsoleta(self):
        a=acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        from deportistas.servicios import Conflicto
        with self.assertRaises(Conflicto):
            acreditar(self.admin,a.persona_id,'usuario',self.ajeno.pk,uuid4(),1)

    def test_2b_profesor_no_lee_identidades_ajenas(self):
        a=acreditar(self.admin,None,'usuario',self.ajeno.pk,uuid4())
        self.c.force_authenticate(self.prof)
        for ruta in ['/api/identidad/',f'/api/identidad/{a.pk}/']:
            self.assertEqual(self.c.get(ruta).status_code,403)
        self.assertEqual(self.c.post('/api/identidad/',{},format='json').status_code,403)

    def test_2b_rol_nuevo_no_abre_fichas(self):
        u=Usuario.objects.create_user(username='ficticio_portal',rol='acudiente')
        self.c.force_authenticate(u)
        self.assertEqual(self.c.get('/api/deportistas/').data['count'],0)
        self.assertEqual(self.c.get('/api/deportistas/00000000-0000-0000-0000-000000000001/').status_code,404)

    def test_2c_revocacion_inmediata_con_actor_en_cache(self):
        r=otorgar(self.admin,self.prof.pk,'administrador','Responsabilidad institucional')
        copia=Usuario.objects.get(pk=self.prof.pk)
        self.assertTrue(puede(copia,'cuentas.gestionar'))
        revocar(self.admin,r.pk,r.version,'Fin de responsabilidad')
        self.assertFalse(puede(copia,'cuentas.gestionar'))
        self.c.force_authenticate(copia)
        self.assertEqual(self.c.get('/api/usuarios/').status_code,403)

    def test_2c_no_autoampliacion_ni_api_actor_inyectado(self):
        self.assertEqual(self.c.post(f'/api/usuarios/{self.admin.pk}/roles/',{'rol':'profesor','motivo':'Cambio'},format='json').status_code,400)
        self.assertEqual(self.c.post(f'/api/usuarios/{self.prof.pk}/roles/',{'rol':'routesetter','motivo':'Cambio','actor':self.admin.pk},format='json').status_code,400)

    def test_2c_revocar_pertenencia_de_otro_objeto(self):
        r=otorgar(self.admin,self.ajeno.pk,'routesetter','Cambio')
        self.assertEqual(self.c.post(f'/api/usuarios/{self.prof.pk}/revocar-rol/',{'pertenencia':r.pk,'version':r.version,'motivo':'Cambio'},format='json').status_code,404)
        r.refresh_from_db();self.assertTrue(r.vigente)

    def test_2c_relevo_preserva_otras_facultades_y_cuentas(self):
        otorgar(self.admin,self.coord.pk,'profesor','Docencia vigente')
        relevar_coordinador(self.admin,self.prof,self.coord.pk)
        self.coord.refresh_from_db()
        self.assertTrue(self.coord.is_active)
        self.assertTrue(self.coord.tiene_rol('profesor'))
        self.assertFalse(self.coord.tiene_rol('coordinador'))
        self.assertTrue(self.prof.tiene_rol('coordinador'))
        self.assertTrue(self.prof.tiene_rol('profesor'))

    def test_2c_coordinador_unico_tambien_en_sql(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            PertenenciaRol.objects.create(usuario=self.prof,rol='coordinador')

    def test_2c_evento_inmutable_en_sql(self):
        e=EventoRol.objects.first()
        with self.assertRaises(DatabaseError),transaction.atomic():
            EventoRol.objects.filter(pk=e.pk).update(motivo='Sobrescribir')

    def test_2c_desactivar_cuenta_revoca_facultades_efectivas(self):
        otorgar(self.admin,self.prof.pk,'routesetter','Cambio')
        Usuario.objects.filter(pk=self.prof.pk).update(is_active=False)
        self.assertEqual(roles_vigentes(self.prof),[])

    def test_2d_matriz_acciones_y_combinacion_explicita(self):
        self.assertTrue(puede(self.prof,'ascensos.proponer'))
        self.assertTrue(puede(self.coord,'ascensos.revisar'))
        self.assertFalse(puede(self.coord,'ascensos.formalizar'))
        self.assertFalse(puede(self.admin,'ascensos.revisar'))
        otorgar(self.admin,self.coord.pk,'administrador','Doble función autorizada')
        self.assertTrue(puede(self.coord,'ascensos.formalizar'))

    def test_2e_sesion_roles_y_facultades_sin_datos_privados(self):
        otorgar(self.admin,self.prof.pk,'routesetter','Cambio')
        self.c.force_authenticate(self.prof)
        u=self.c.get('/api/autenticacion/sesion/').data['usuario']
        self.assertEqual(set(u['roles']),{'profesor','routesetter'})
        self.assertIn('ascensos.proponer',u['facultades'])
        self.assertNotIn('password',u)

    def test_2e_lectura_identidad_audita_sin_copiar_evidencia(self):
        a=acreditar(self.admin,None,'usuario',self.prof.pk,uuid4())
        self.assertEqual(self.c.get(f'/api/identidad/{a.pk}/').status_code,200)
        log=CambioAdministrativo.objects.filter(accion='consultar_identidad').get()
        self.assertEqual(log.identificador,a.pk)
        self.assertNotIn(str(a.evidencia),str(log.campos))

    def test_api_otorga_y_revoca_rol_con_version(self):
        ruta=f'/api/usuarios/{self.prof.pk}/'
        r=self.c.post(ruta+'roles/',{'rol':'routesetter','motivo':'Nueva función'},format='json')
        self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(set(roles_vigentes(self.prof)),{'profesor','routesetter'})
        d={'pertenencia':r.data['id'],'version':r.data['version'],'motivo':'Fin de función'}
        self.assertEqual(self.c.post(ruta+'revocar-rol/',d,format='json').status_code,200)
        self.assertEqual(self.c.post(ruta+'revocar-rol/',d,format='json').status_code,409)

    def test_api_identidad_exige_contraste_y_devuelve_version(self):
        d={'tipo':'usuario','perfil':self.prof.pk,'evidencia':str(uuid4()),'identidad_contrastada':False}
        self.assertEqual(self.c.post('/api/identidad/',d,format='json').status_code,400)
        self.assertEqual(Persona.objects.count(),0)
        d['identidad_contrastada']=True
        r=self.c.post('/api/identidad/',d,format='json')
        self.assertEqual(r.status_code,201,r.data)
        personas=self.c.get('/api/personas-institucionales/').data['results']
        self.assertEqual(personas[0]['version'],r.data['version_persona'])
        self.assertEqual(personas[0]['nombre'],self.prof.username)

    def test_desactivar_coordinador_secundario_registra_cese_del_cargo(self):
        relevar_coordinador(self.admin,self.prof,self.coord.pk)
        r=self.c.patch(f'/api/usuarios/{self.prof.pk}/',{'is_active':False},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.assertTrue(CambioAdministrativo.objects.filter(accion='coordinacion_fin',identificador=self.prof.pk).exists())
        self.assertFalse(self.prof.tiene_rol('coordinador'))

    def test_ultimo_rol_revocado_no_reaparece_por_desactivar_o_reactivar(self):
        r=PertenenciaRol.objects.get(usuario=self.prof,rol='profesor',vigente=True)
        revocar(self.admin,r.pk,r.version,'Fin de todas las facultades')
        self.prof.refresh_from_db()
        self.assertFalse(self.prof.is_active)
        self.assertFalse(self.prof.pertenencias.filter(vigente=True).exists())
        self.assertEqual(self.c.patch(f'/api/usuarios/{self.prof.pk}/',{'is_active':True},format='json').status_code,400)
        otorgar(self.admin,self.prof.pk,'routesetter','Nueva función explícita sin docencia')
        self.assertEqual(self.c.patch(f'/api/usuarios/{self.prof.pk}/',{'is_active':True},format='json').status_code,200)
        self.assertEqual(roles_vigentes(self.prof),['routesetter'])

    def test_inactivar_no_borra_flags_admin_asignados_pero_si_revoca_acceso(self):
        otorgar(self.admin,self.prof.pk,'administrador','Administración adicional')
        self.prof.is_staff=True;self.prof.save(update_fields=['is_staff'])
        self.assertEqual(self.c.patch(f'/api/usuarios/{self.prof.pk}/',{'is_active':False},format='json').status_code,200)
        self.prof.refresh_from_db()
        self.assertTrue(self.prof.is_staff)
        self.assertFalse(puede(self.prof,'cuentas.gestionar'))
