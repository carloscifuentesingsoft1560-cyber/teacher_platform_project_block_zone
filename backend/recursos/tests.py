import io
import tempfile
import uuid
import zipfile
from pathlib import Path
from django.conf import settings
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction, IntegrityError
from rest_framework.test import APIClient
from cuentas.models import Usuario
from cuentas.servicios_roles import otorgar, revocar
from recursos.models import FuenteDocumento, FuenteVersion, ArchivoPrivado
from recursos.almacenamiento import subir, ruta


class BaseContenido:
    def preparar(self):
        self.admin = Usuario.objects.create_user(username='ficticio_admin', rol='administrador')
        self.coord = Usuario.objects.create_user(username='ficticio_coord', rol='coordinador')
        self.prof = Usuario.objects.create_user(username='ficticio_prof', rol='profesor')
        self.otro = Usuario.objects.create_user(username='ficticio_otro', rol='profesor')
        self.c = APIClient(); self.c.force_authenticate(self.coord)
    def post(self, ruta_api, datos):
        return self.c.post('/api/'+ruta_api, datos, format='json')


class RecursosTests(BaseContenido, TestCase):
    def setUp(self):
        self.preparar()
        self.tmp = tempfile.TemporaryDirectory(prefix='archivos_docentes_test_')
        self.ov = override_settings(ZDB_ARCHIVOS_PRIVADOS=Path(self.tmp.name)); self.ov.enable()
    def tearDown(self):
        self.ov.disable(); self.tmp.cleanup()
    def archivo(self, actor=None):
        return subir(actor or self.prof, SimpleUploadedFile('guia.txt', b'Contenido ficticio docente'), 'material_docente', True)
    def test_upload_ruta_opaca_y_checksum(self):
        a = self.archivo()
        self.assertTrue(ruta(a).is_file()); self.assertNotEqual(ruta(a).name, a.nombre)
        self.assertEqual(a.bytes, len(b'Contenido ficticio docente'))
    def test_no_se_admite_tipo_disfrazado(self):
        with self.assertRaisesMessage(Exception, 'Tipo o firma'):
            subir(self.prof, SimpleUploadedFile('guia.pdf', b'html'), 'material_docente', True)
    def test_declaracion_obligatoria(self):
        with self.assertRaises(Exception): subir(self.prof, SimpleUploadedFile('guia.txt', b'x'), 'material_docente', False)
        self.assertFalse(ArchivoPrivado.objects.exists())
    def test_zip_con_enlace_externo_rechazado(self):
        z = io.BytesIO()
        with zipfile.ZipFile(z, 'w') as f:
            f.writestr('xl/workbook.xml','<x/>'); f.writestr('_rels/.rels','<Relationships><Relationship TargetMode="External"/></Relationships>')
        with self.assertRaisesMessage(Exception, 'externas'):
            subir(self.coord, SimpleUploadedFile('fuente.xlsx', z.getvalue()), 'fuente_curricular', True)
    def test_descarga_ajena_no_revela(self):
        a = self.archivo(); self.c.force_authenticate(self.otro)
        self.assertEqual(self.c.get(f'/api/recursos/archivos/{a.uuid}/descarga/').status_code, 404)
    def test_descarga_propietaria_es_privada(self):
        a = self.archivo(); self.c.force_authenticate(self.prof)
        r = self.c.get(f'/api/recursos/archivos/{a.uuid}/descarga/')
        try:
            self.assertEqual(r.status_code, 200)
            self.assertEqual({x.strip() for x in r['Cache-Control'].split(',')}, {'private','no-store'})
            self.assertEqual(b''.join(r.streaming_content), b'Contenido ficticio docente')
        finally:
            if r.file_to_stream: r.file_to_stream.close()
    def test_revocacion_cuenta_cargada(self):
        a = self.archivo(); self.c.force_authenticate(self.prof)
        p = self.prof.pertenencias.get(vigente=True)
        revocar(self.admin,p.pk,p.version,'Ensayo ficticio')
        self.assertEqual(self.c.get(f'/api/recursos/archivos/{a.uuid}/descarga/').status_code,403)
    def test_fuente_bytes_inmutables_sql(self):
        a = self.archivo()
        with self.assertRaises(IntegrityError), transaction.atomic(): ArchivoPrivado.objects.filter(pk=a.pk).update(nombre='alterado.txt')
    def test_profesor_no_custodia_fuente(self):
        self.c.force_authenticate(self.prof)
        self.assertEqual(self.c.get('/api/recursos/fuentes/').status_code,403)
    def test_deportista_y_acudiente_sin_acceso(self):
        for rol in ('deportista','acudiente'):
            u = Usuario.objects.create_user(username='ficticio_'+rol,rol=rol); self.c.force_authenticate(u)
            self.assertEqual(self.c.get('/api/recursos/fuentes/').status_code,403)
    def test_campos_controlados_por_servidor(self):
        r = self.post('recursos/fuentes/', {'titulo':'Ficticio', 'autor': self.prof.pk})
        self.assertEqual(r.status_code,400)
    def test_material_publicado_revalida_asignacion_y_rol(self):
        from datetime import timedelta
        from django.utils import timezone
        from organizacion.models import Disciplina,Nivel,Periodo,Grupo,Asignacion
        from curriculo.models import ProgramaFormativo
        from biblioteca.models import MaterialDocente,MaterialDocenteVersion
        from recursos.editorial import transicion
        hoy=timezone.localdate();nivel=Nivel.objects.get(codigo='nivel-1')
        programa=ProgramaFormativo.objects.create(nivel=nivel,formalizado=True)
        periodo=Periodo.objects.create(codigo='ficticio',nombre='Ficticio',fecha_inicio=hoy-timedelta(days=1),fecha_fin=hoy+timedelta(days=10))
        grupo=Grupo.objects.create(codigo='ficticio',nombre='Ficticio',nivel=nivel,disciplina=nivel.disciplina,periodo=periodo,cupo_maximo=5)
        Asignacion.objects.create(grupo=grupo,usuario=self.prof,tipo='profesor',fecha_inicio=hoy)
        a=self.archivo(self.coord);m=MaterialDocente.objects.create(codigo='guia-publicada',nombre='Guía',autor=self.coord)
        v=MaterialDocenteVersion.objects.create(identidad=m,autor=self.coord,titulo='Guía',resumen='Ficticia',archivo=a,derechos='Propios');v.programas.add(programa)
        transicion(self.coord,v,'proponer',1,uuid.uuid4());v.refresh_from_db();transicion(self.coord,v,'aprobar',v.revision,uuid.uuid4())
        self.c.force_authenticate(self.prof);r=self.c.get(f'/api/biblioteca/materiales/{v.uuid}/descarga/')
        self.assertEqual(r.status_code,200);self.assertEqual(b''.join(r.streaming_content),b'Contenido ficticio docente')
        otorgar(self.admin,self.prof.pk,'routesetter','Ensayo combinado');p=self.prof.pertenencias.get(vigente=True,rol='profesor');revocar(self.admin,p.pk,p.version,'Ensayo de revocación')
        self.assertEqual(self.c.get(f'/api/biblioteca/materiales/{v.uuid}/descarga/').status_code,404)
    def test_revocacion_custodia_cierra_original_aun_siendo_autor(self):
        a=subir(self.coord,SimpleUploadedFile('original.txt',b'Fuente ficticia'),'fuente_curricular',True)
        otorgar(self.admin,self.coord.pk,'profesor','Ensayo');self.c.force_authenticate(self.coord)
        rol=self.coord.pertenencias.get(rol='coordinador',vigente=True);revocar(self.admin,rol.pk,rol.version,'Ensayo')
        self.assertEqual(self.c.get(f'/api/recursos/archivos/{a.uuid}/descarga/').status_code,404)
    def test_fuente_privada_no_se_degrada_a_material_publicable(self):
        a=subir(self.coord,SimpleUploadedFile('original.txt',b'Fuente ficticia'),'fuente_curricular',True)
        r=self.post('biblioteca/materiales/',{'codigo':'material-invalido','contenido':{'titulo':'Ficticio','resumen':'Prueba','derechos':'Custodia','archivo':a.pk}})
        self.assertEqual(r.status_code,400)
