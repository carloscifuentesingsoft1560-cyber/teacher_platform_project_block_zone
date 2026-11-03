import uuid
from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError, transaction, connections, close_old_connections
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from rest_framework.exceptions import APIException
from cuentas.models import Usuario
from cuentas.servicios_roles import otorgar, revocar
from organizacion.models import Disciplina, Nivel
from curriculo.models import ProgramaFormativo
from recursos.tests import BaseContenido
from recursos.editorial import transicion, derivar
from .models import Ejercicio, EjercicioVersion, PasoEjercicio, TerminoActividad, MaterialDocente, MaterialDocenteVersion, CandidatoBiblioteca


class BibliotecaTests(BaseContenido, TestCase):
    def setUp(self):
        self.preparar();self.programa=ProgramaFormativo.objects.create(nivel=Nivel.objects.get(codigo='nivel-1'),formalizado=True)
        self.e=Ejercicio.objects.create(codigo='ejercicio-ficticio',nombre='Pies',autor=self.prof)
        self.v=EjercicioVersion.objects.create(identidad=self.e,autor=self.prof,disciplina=Disciplina.objects.get(codigo='escalada'),nombre='Pies',objetivo='Precisión',poblacion='Grupo ficticio',metodologia='Demostración',descripcion='Pasos seguros',riesgos='Caída',controles='Supervisión',derechos='Redacción propia',duracion_min=5,duracion_max=10)
        self.v.programas.add(self.programa);PasoEjercicio.objects.create(version=self.v,orden=1,instrucciones='Ejecutar en suelo')
        self.c.force_authenticate(self.prof)
    def publicar(self):
        transicion(self.prof,self.v,'proponer',self.v.revision,uuid.uuid4())
        self.v.refresh_from_db();transicion(self.coord,self.v,'aprobar',self.v.revision,uuid.uuid4());self.v.refresh_from_db()
    def test_crear_por_api_sin_elevacion(self):
        self.c.force_authenticate(self.coord)
        r=self.post('biblioteca/versiones/',{'codigo':'otro-ejercicio','contenido':{'disciplina':self.v.disciplina_id,'nombre':'Equilibrio','objetivo':'Observar','poblacion':'Ficticia','metodologia':'Juego','descripcion':'En suelo','riesgos':'Ninguno evaluado','controles':'Revisión','derechos':'Propios'}})
        self.assertEqual(r.status_code,201,r.data);self.assertEqual(r.data['estado'],'borrador')
    def test_cuerpo_json_no_objeto_400(self):
        r=self.post('biblioteca/versiones/',[{'codigo':'invalido'}]);self.assertEqual(r.status_code,400)
    def test_no_se_puede_inyectar_estado_aprobado(self):
        self.c.force_authenticate(self.coord)
        r=self.post('biblioteca/versiones/',{'codigo':'falso','contenido':{'estado':'aprobado'}});self.assertEqual(r.status_code,400)
    def test_objeto_de_otro_profesor(self):
        self.c.force_authenticate(self.otro);self.assertEqual(self.c.get(f'/api/biblioteca/versiones/{self.v.uuid}/').status_code,404)
    def test_publicacion_conserva_version(self):
        self.publicar();n=derivar(self.prof,self.v);self.assertEqual(n.pasos.count(),1);self.assertEqual(n.programas.count(),1);self.assertFalse(n.vigente)
    def test_pasos_y_m2m_congelados_sql(self):
        self.publicar()
        with self.assertRaises(IntegrityError),transaction.atomic(): self.v.programas.clear()
        with self.assertRaises(IntegrityError),transaction.atomic(): self.v.pasos.update(instrucciones='Alterado')
    def test_publicacion_sin_seguridad_rechazada(self):
        self.v.riesgos='';self.v.save()
        with self.assertRaisesMessage(Exception,'Campo necesario'):transicion(self.prof,self.v,'proponer',1,uuid.uuid4())
    def test_busqueda_y_filtros_sin_imputar_duracion(self):
        self.publicar();self.c.force_authenticate(self.coord)
        r=self.c.get('/api/biblioteca/versiones/?buscar=Pies&duracion_max=10');self.assertEqual(r.data['count'],1)
        r=self.c.get('/api/biblioteca/versiones/?duracion_max=4');self.assertEqual(r.data['count'],0)
    def test_duracion_incoherente_no_llega_a_sql(self):
        r=self.c.patch(f'/api/biblioteca/versiones/{self.v.uuid}/',{'revision':1,'duracion_min':12,'duracion_max':3},format='json');self.assertEqual(r.status_code,400)
    def test_agregar_adaptacion_sin_datos_personales(self):
        r=self.post(f'biblioteca/versiones/{self.v.uuid}/agregar/',{'tipo':'adaptacion','revision':1,'datos':{'condicion':'Principiante','alternativa':'En suelo','limites':'Sin altura'}})
        self.assertEqual(r.status_code,201,r.data);self.assertEqual(self.v.adaptaciones.count(),1)
    def test_version_obsoleta_409(self):
        r=self.c.patch(f'/api/biblioteca/versiones/{self.v.uuid}/',{'revision':0,'objetivo':'Otro'},format='json');self.assertEqual(r.status_code,409)
    def test_roles_combinados_no_aprueban(self):
        otorgar(self.admin,self.prof.pk,'routesetter','Ensayo');transicion(self.prof,self.v,'proponer',1,uuid.uuid4());self.v.refresh_from_db()
        r=self.post(f'biblioteca/versiones/{self.v.uuid}/aprobar/',{'revision':self.v.revision,'clave':str(uuid.uuid4())});self.assertEqual(r.status_code,403)
    def test_retiro_no_modifica_pasado(self):
        self.publicar();v=transicion(self.coord,self.v,'retirar',self.v.revision,uuid.uuid4(),'Seguridad');self.assertFalse(v.vigente);self.assertTrue(v.pasos.exists())
        from curriculo.servicios import resolver_referencia
        with self.assertRaises(Exception):resolver_referencia(self.prof,v)
    def test_no_carga_224_candidatos(self):
        self.assertEqual(CandidatoBiblioteca.objects.count(),0);self.assertEqual(EjercicioVersion.objects.count(),1)
    def test_material_es_versionado_y_descarga_revalida(self):
        m=MaterialDocente.objects.create(codigo='guia',nombre='Guía',autor=self.prof)
        v=MaterialDocenteVersion.objects.create(identidad=m,autor=self.prof,titulo='Guía',resumen='Ficticia',referencia_externa='https://example.com/guia',derechos='Enlace')
        self.c.force_authenticate(self.otro);self.assertEqual(self.c.get(f'/api/biblioteca/materiales/{v.uuid}/descarga/').status_code,404)
    def test_portales_sin_contenido_interno(self):
        for rol in ['deportista','acudiente']:
            u=Usuario.objects.create_user(username='ficticio_'+rol,rol=rol);self.c.force_authenticate(u);self.assertEqual(self.c.get('/api/biblioteca/versiones/').status_code,403)
    def test_estilos_no_son_capacidades(self):
        self.c.force_authenticate(self.coord)
        r=self.post('biblioteca/terminos/',{'namespace':'estilo','codigo':'resistencia','nombre':'Resistencia'});self.assertEqual(r.status_code,400)
    def test_revision_revocada_no_publica(self):
        transicion(self.prof,self.v,'proponer',1,uuid.uuid4());self.v.refresh_from_db()
        p=self.coord.pertenencias.get(vigente=True);revocar(self.admin,p.pk,p.version,'Ensayo')
        with self.assertRaises(APIException):transicion(self.coord,self.v,'aprobar',self.v.revision,uuid.uuid4())


class ConcurrenciaEditorial(TransactionTestCase):
    def test_dos_publicaciones_una_version_y_evento(self):
        coord=Usuario.objects.create_user(username='ficticio_coord',rol='coordinador')
        d=Disciplina.objects.create(codigo='ficticia',nombre='Ficticia')
        e=Ejercicio.objects.create(codigo='ficticio',nombre='Ficticio',autor=coord)
        v=EjercicioVersion.objects.create(identidad=e,autor=coord,disciplina=d,nombre='Ficticio',objetivo='O',poblacion='P',metodologia='M',descripcion='D',riesgos='R',controles='C',derechos='Propios',acceso_tecnico=True)
        PasoEjercicio.objects.create(version=v,orden=1,instrucciones='En suelo');transicion(coord,v,'proponer',1,uuid.uuid4());v.refresh_from_db()
        b=Barrier(2)
        def publicar(_):
            close_old_connections()
            try:
                b.wait(timeout=10);transicion(coord,v,'aprobar',v.revision,uuid.uuid4());return 'ok'
            except APIException:return 'conflicto'
            finally:connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(publicar,[1,2])),['ok','conflicto'])
        self.assertEqual(v.eventos.filter(accion='aprobar').count(),1)
