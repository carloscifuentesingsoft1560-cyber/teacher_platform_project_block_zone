import io
import json
import uuid
import zipfile
from xml.sax.saxutils import escape
from django.test import TestCase
from django.db import IntegrityError, transaction
from organizacion.models import Disciplina, Nivel
from recursos.tests import BaseContenido
from recursos.editorial import transicion, derivar
from .models import ProgramaFormativo, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular, ProcedenciaCurricular
from .servicios import crear_hijo
from .importacion import leer_xlsx, PERFIL


def xlsx_ficticio():
    b = io.BytesIO(); ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="'+ns+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{nombre}" sheetId="{i}" r:id="r{i}"/>' for i,nombre in enumerate(PERFIL,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships>'+''.join(f'<Relationship Id="r{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1,5))+'</Relationships>')
        for i,(nombre,(_,inicios,cantidades)) in enumerate(PERFIL.items(),1):
            cells={}; merges=[]; semana=clase=0
            for indice,(inicio,nsemanas) in enumerate(zip(inicios,cantidades)):
                cells[f'A{inicio}']='ETAPA '+str(indice);cells[f'G{inicio+1}']='Objetivo ficticio';cells[f'H{inicio+2}']='Motriz';cells[f'C{inicio+6}']='Motivación de fase'
                merges.append(f'C{inicio+6}:C{inicio+5+4*nsemanas}')
                for j in range(nsemanas):
                    semana+=1;fila=inicio+6+4*j;cells[f'A{fila}']=str(semana);merges.append(f'A{fila}:A{fila+3}')
                    for offset in (0,2):
                        clase+=1;r=fila+offset;cells[f'B{r}']=str(clase);cells[f'G{r}']='Tema';cells[f'H{r}']='Observo';cells[f'H{r+1}']='Practico';merges += [f'B{r}:B{r+1}',f'G{r}:G{r+1}']
            rows={}
            for a,t in cells.items(): rows.setdefault(int(''.join(filter(str.isdigit,a))),[]).append(f'<c r="{a}" t="inlineStr"><is><t>{escape(t)}</t></is></c>')
            z.writestr(f'xl/worksheets/sheet{i}.xml','<worksheet xmlns="'+ns+'"><sheetData>'+''.join(f'<row r="{r}">{"".join(c)}</row>' for r,c in sorted(rows.items()))+'</sheetData><mergeCells>'+''.join(f'<mergeCell ref="{m}"/>' for m in merges)+'</mergeCells></worksheet>')
    return b.getvalue()


class CurriculoTests(BaseContenido, TestCase):
    def setUp(self):
        self.preparar(); self.disc = Disciplina.objects.get(codigo='escalada');self.nivel=Nivel.objects.get(codigo='nivel-1')
        self.programa=ProgramaFormativo.objects.create(nivel=self.nivel,formalizado=True)
        self.m=Malla.objects.create(codigo='malla-ficticia',nombre='Ficticia',programa=self.programa,autor=self.coord)
        self.v=MallaVersion.objects.create(identidad=self.m,autor=self.coord,derechos='Redacción propia ficticia')
        self.f=FaseCurricular.objects.create(version=self.v,codigo='exploracion',nombre='Exploración',orden=1)
        self.e=ElementoCurricular.objects.create(version=self.v,tipo='objetivo',texto='Observar movimiento',fase=self.f)
    def cmd(self, accion, v=None, actor=None, clave=None, revision=None):
        v=v or self.v;v.refresh_from_db()
        return transicion(actor or self.coord,v,accion,revision or v.revision,clave or uuid.uuid4(),'Ensayo')
    def publicar(self): self.cmd('proponer');self.cmd('aprobar');self.v.refresh_from_db()
    def test_tres_estados_original_propuesta_publicacion(self):
        self.assertEqual(self.v.naturaleza,'propuesta_revisada');self.publicar();self.assertTrue(self.v.vigente)
    def test_admin_no_aprueba_por_su_rol(self):
        self.cmd('proponer')
        from rest_framework.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied): self.cmd('aprobar',actor=self.admin)
    def test_publicado_no_editable_api_y_sql(self):
        self.publicar();r=self.c.patch(f'/api/curriculo/versiones/{self.v.uuid}/',{'revision':self.v.revision,'derechos':'otro'},format='json');self.assertEqual(r.status_code,400)
        with self.assertRaises(IntegrityError),transaction.atomic(): ElementoCurricular.objects.filter(pk=self.e.pk).update(texto='Alterado')
        with self.assertRaises(IntegrityError),transaction.atomic(): MallaVersion.objects.filter(pk=self.v.pk).update(derechos='Alterado')
    def test_derivacion_copia_arbol_y_claves_logicas(self):
        self.publicar();n=derivar(self.coord,self.v)
        self.assertEqual(n.numero,2);self.assertEqual(n.estado,'borrador');self.assertEqual(n.elementos.get().clave_logica,self.e.clave_logica);self.assertNotEqual(n.elementos.get().pk,self.e.pk)
    def test_semana_de_otra_version_falla_sql(self):
        n=derivar(self.coord,self.v)
        with self.assertRaises(IntegrityError),transaction.atomic(): SemanaCurricular.objects.create(version=n,fase=self.f,ordinal=1)
    def test_ciclo_curricular_rechazado(self):
        with self.assertRaises(IntegrityError),transaction.atomic(): ElementoCurricular.objects.filter(pk=self.e.pk).update(padre=self.e)
    def test_clase_no_equivale_a_sesion(self):
        s=SemanaCurricular.objects.create(version=self.v,fase=self.f,ordinal=1);ClasePrevista.objects.create(semana=s,ordinal=1)
        from django.apps import apps
        self.assertNotIn('sesion',[m._meta.model_name for m in apps.get_app_config('curriculo').get_models()])
    def test_idempotencia_de_comando_y_conflicto(self):
        clave=uuid.uuid4();v=self.cmd('proponer',clave=clave,revision=1)
        transicion(self.coord,v,'proponer',1,clave,'Ensayo');self.assertEqual(v.eventos.count(),1)
        from deportistas.servicios import Conflicto
        with self.assertRaises(Conflicto): transicion(self.coord,v,'proponer',1,clave,'Otro')
    def test_objeto_ajeno_y_revocacion_rol(self):
        self.c.force_authenticate(self.otro);self.assertEqual(self.c.get(f'/api/curriculo/versiones/{self.v.uuid}/').status_code,404)
    def test_original_cerrado_exige_derivar(self):
        MallaVersion.objects.filter(pk=self.v.pk).update(naturaleza='original_institucional',original_cerrado=True)
        with self.assertRaises(IntegrityError),transaction.atomic(): self.e.texto='Otro';self.e.save()
        with self.assertRaisesMessage(Exception,'Deriva'): self.cmd('proponer')
    def test_excel_cuatro_hojas_40_80(self):
        x=leer_xlsx(xlsx_ficticio());self.assertEqual(len(x['hojas']),4)
        self.assertTrue(all(h['semanas']==40 and h['clases']==80 for h in x['hojas']))
        self.assertEqual(x['hojas'][0]['fases'],[10,10,20])
    def test_confirmacion_y_procedencia_sin_competencias_inventadas(self):
        import tempfile,hashlib
        from pathlib import Path
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from recursos.almacenamiento import subir
        from recursos.models import FuenteDocumento,FuenteVersion
        from .importacion import extraer_lote,confirmar_lote
        with tempfile.TemporaryDirectory() as tmp,override_settings(ZDB_ARCHIVOS_PRIVADOS=Path(tmp)):
            a=subir(self.coord,SimpleUploadedFile('mallas.xlsx',xlsx_ficticio()),'fuente_curricular',True)
            f=FuenteDocumento.objects.create(titulo='Ficticio',autor=self.coord);fv=FuenteVersion.objects.create(fuente=f,archivo=a,sha256=a.sha256,licencia='Ficticio')
            lote=extraer_lote(self.coord,fv.pk,uuid.uuid4());mapa={}
            for nombre,(codigo,_,_) in PERFIL.items():mapa[nombre]=ProgramaFormativo.objects.get_or_create(nivel=Nivel.objects.get(codigo=codigo),defaults={'formalizado':True})[0].pk
            confirmar_lote(self.coord,lote,mapa);lote.refresh_from_db();self.assertEqual(len(lote.resultado),4)
            originales=MallaVersion.objects.filter(uuid__in=lote.resultado)
            self.assertTrue(all(x.semanas.count()==40 for x in originales));self.assertEqual(ClasePrevista.objects.filter(semana__version__in=originales).count(),320)
            self.assertFalse(ElementoCurricular.objects.filter(version__in=originales,tipo='competencia').exists())
            pro=ProcedenciaCurricular.objects.filter(elemento__version__in=originales,fragmento__celda='G10').first();self.assertEqual(pro.fragmento.rango,'G10:G11')
            self.assertFalse(originales.filter(vigente=True).exists());confirmar_lote(self.coord,lote,mapa);self.assertEqual(MallaVersion.objects.filter(uuid__in=lote.resultado).count(),4)
    def test_ordinal_global_clase_no_se_duplica(self):
        a=SemanaCurricular.objects.create(version=self.v,fase=self.f,ordinal=1);b=SemanaCurricular.objects.create(version=self.v,fase=self.f,ordinal=2)
        ClasePrevista.objects.create(semana=a,ordinal=1)
        with self.assertRaises(IntegrityError),transaction.atomic(): ClasePrevista.objects.create(semana=b,ordinal=1)
    def test_ubicaciones_multiples_sin_duplicar_competencia(self):
        from .models import UbicacionCurricular
        s=SemanaCurricular.objects.create(version=self.v,fase=self.f,ordinal=1)
        UbicacionCurricular.objects.create(elemento=self.e,fase=self.f)
        UbicacionCurricular.objects.create(elemento=self.e,semana=s)
        self.assertEqual(self.v.elementos.count(),1)
        otra=derivar(self.coord,self.v)
        with self.assertRaises(IntegrityError),transaction.atomic():UbicacionCurricular.objects.create(elemento=self.e,fase=otra.fases.get())
        self.assertEqual(otra.elementos.get().ubicaciones.count(),2)
    def test_derivacion_reintentada_conserva_identidad(self):
        clave=uuid.uuid4();a=derivar(self.coord,self.v,clave);b=derivar(self.coord,self.v,clave)
        self.assertEqual(a.pk,b.pk);self.assertEqual(self.m.versiones.count(),2)
    def test_filtro_invalido_400(self):
        self.assertEqual(self.c.get('/api/curriculo/versiones/?programa=no-numero').status_code,400)
    def test_identidad_de_malla_no_altera_ediciones_sql(self):
        with self.assertRaises(IntegrityError),transaction.atomic():Malla.objects.filter(pk=self.m.pk).update(programa_id=None)
    def test_reintento_de_revision_revalida_facultad(self):
        from cuentas.servicios_roles import otorgar,revocar
        from rest_framework.exceptions import PermissionDenied
        otorgar(self.admin,self.coord.pk,'profesor','Ensayo de facultades combinadas')
        self.cmd('proponer');self.v.refresh_from_db();revision=self.v.revision;clave=uuid.uuid4()
        transicion(self.coord,self.v,'devolver',revision,clave,'Ensayo')
        rol=self.coord.pertenencias.get(rol='coordinador',vigente=True);revocar(self.admin,rol.pk,rol.version,'Ensayo')
        with self.assertRaises(PermissionDenied):transicion(self.coord,self.v,'devolver',revision,clave,'Ensayo')
    def test_tipo_estructura_no_textual_400(self):
        r=self.post(f'curriculo/versiones/{self.v.uuid}/agregar/',{'tipo':{},'datos':{},'revision':1});self.assertEqual(r.status_code,400)
    def test_fuente_id_malformado_400(self):
        r=self.post('curriculo/importaciones/',{'fuente':'no-numero','clave':str(uuid.uuid4())});self.assertEqual(r.status_code,400)
