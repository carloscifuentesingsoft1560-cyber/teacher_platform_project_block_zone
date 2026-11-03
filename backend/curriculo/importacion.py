"""Perfil explícito de las cuatro hojas. No ejecuta Excel ni aprueba contenido."""
import uuid
import io
import hashlib
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from recursos.almacenamiento import verificar_zip, ruta
from recursos.editorial import bloquear
from recursos.permisos import custodio
from recursos.models import FuenteVersion, FragmentoFuente
from .models import ProgramaFormativo, LoteImportacion, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular, ProcedenciaCurricular

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
PERFIL = {'LUDICO': ('ludico', [4, 50, 96], [10, 10, 20]), 'NIVEL 1': ('nivel-1', [4, 66, 128], [14, 14, 12]), 'NIVEL 2': ('nivel-2', [4, 66, 128], [14, 14, 12]), 'ESPECIALIZACION SEMICOMPETITIVA': ('especializacion', [4, 66, 128], [14, 14, 12])}


def leer_xlsx(datos):
    verificar_zip(datos)
    hojas = []
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(t.text or '' for t in x.iter('{'+NS['s']+'}t')) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {x.attrib['Id']: x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sh in ET.fromstring(z.read('xl/workbook.xml')).find('s:sheets', NS):
            nombre = sh.attrib['name']
            if nombre not in PERFIL: raise ValidationError('El perfil exige exactamente las cuatro hojas curriculares.')
            target = rels[sh.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not path.startswith('xl/worksheets/') or '..' in path: raise ValidationError('Relación de hoja inválida.')
            root = ET.fromstring(z.read(path))
            cells, formulas = {}, {}
            for c in root.findall('.//s:sheetData/s:row/s:c', NS):
                a = c.attrib['r']
                if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]{0,4}', a): raise ValidationError('Coordenada inválida.')
                v = c.find('s:v', NS); val = v.text if v is not None else ''
                if c.attrib.get('t') == 's': val = strings[int(val)] if val else ''
                elif c.attrib.get('t') == 'inlineStr': val = ''.join(t.text or '' for t in c.iter('{'+NS['s']+'}t'))
                f = c.find('s:f', NS)
                if f is not None: formulas[a] = f.text or ''
                if val or f is not None: cells[a] = val or ''
            if len(cells) > 10000: raise ValidationError('Demasiadas celdas.')
            merges = [x.attrib['ref'] for x in root.findall('s:mergeCells/s:mergeCell', NS)]
            nsem = sum(1 for a, v in cells.items() if re.fullmatch('A[0-9]+', a) and re.fullmatch(r'[0-9]+(?:\.0+)?', v))
            ncla = sum(1 for a, v in cells.items() if re.fullmatch('B[0-9]+', a) and re.fullmatch(r'[0-9]+(?:\.0+)?', v))
            if nsem != 40 or ncla != 80: raise ValidationError('El perfil exige 40 semanas y 80 clases por hoja.')
            if formulas: raise ValidationError('Fórmulas inesperadas: conservar fuente y revisar otro perfil sin evaluarlas.')
            hojas.append({'nombre': nombre, 'celdas': cells, 'combinadas': merges, 'parte': path,
                'fases': PERFIL[nombre][2], 'semanas': nsem, 'clases': ncla,
                'incidencias': ['Revisar objetivos, instalaciones y notas editoriales. No constituye aprobación.']})
    if {x['nombre'] for x in hojas} != set(PERFIL): raise ValidationError('Faltan hojas curriculares.')
    return {'hojas': hojas, 'perfil': 'mallas-zdb-v1', 'publicacion_automatica': False}


@transaction.atomic
def extraer_lote(actor, fuente_id, clave):
    bloquear(actor)
    if not custodio(actor): raise PermissionDenied()
    try: clave = uuid.UUID(str(clave))
    except (TypeError, ValueError): raise ValidationError('Clave UUID requerida.')
    try: fuente_id = int(fuente_id)
    except (ValueError, TypeError): raise ValidationError('Identificador de fuente inválido.')
    fuente = get_object_or_404(FuenteVersion, pk=fuente_id)
    previo = LoteImportacion.objects.filter(autor=actor, clave=clave).first()
    if previo:
        if previo.fuente_id != fuente.pk: raise ValidationError('Clave utilizada para otra fuente.')
        return previo
    if not fuente.archivo_id: raise ValidationError('La importación necesita el archivo original privado.')
    existente = LoteImportacion.objects.filter(fuente=fuente, perfil='mallas-zdb-v1').first()
    if existente: return existente
    datos = ruta(fuente.archivo).read_bytes()
    if hashlib.sha256(datos).hexdigest() != fuente.sha256: raise ValidationError('La huella del archivo no coincide.')
    try: vista = leer_xlsx(datos)
    except (KeyError, IndexError, ET.ParseError, ValueError, zipfile.BadZipFile): raise ValidationError('Estructura XLSX inválida.')
    return LoteImportacion.objects.create(fuente=fuente, autor=actor, clave=clave, vista_previa=vista)


@transaction.atomic
def confirmar_lote(actor, lote, programas):
    bloquear(actor)
    if not custodio(actor): raise PermissionDenied()
    lote = LoteImportacion.objects.select_for_update().get(pk=lote.pk)
    if not isinstance(programas, dict) or set(programas) != set(PERFIL): raise ValidationError('Mapa de cuatro hojas requerido.')
    mapa = {}
    for nombre, pk in programas.items():
        try: pk = int(pk)
        except (ValueError, TypeError): raise ValidationError('Identificador de programa inválido.')
        programa = get_object_or_404(ProgramaFormativo.objects.select_related('nivel__disciplina'), pk=pk)
        if programa.nivel.codigo != PERFIL[nombre][0] or programa.nivel.disciplina.codigo != 'escalada':
            raise ValidationError('El programa no corresponde a la hoja.')
        mapa[nombre] = programa
    if lote.estado == 'confirmado':
        if any(MallaVersion.objects.get(uuid=u).identidad.programa_id != mapa[h['nombre']].pk for u, h in zip(lote.resultado, lote.vista_previa['hojas'])):
            raise ValidationError('El mapa no coincide con la confirmación previa.')
        return lote
    resultado = []
    for h in lote.vista_previa['hojas']:
        nombre, cells = h['nombre'], h['celdas']; programa = mapa[nombre]
        malla, creada = Malla.objects.get_or_create(codigo='original-'+programa.nivel.codigo+'-'+lote.fuente.sha256[:12], defaults={'nombre': nombre, 'programa': programa, 'autor': actor})
        if not creada:
            v = malla.versiones.get(numero=1); resultado.append(str(v.uuid)); continue
        v = MallaVersion.objects.create(identidad=malla, autor=actor, naturaleza='original_institucional', semanas_esperadas=40, clases_esperadas=80, derechos=lote.fuente.licencia)
        merges = {x.split(':')[0]: x for x in h['combinadas']}
        fragments = {}
        for a, texto in cells.items():
            fragmento, _ = FragmentoFuente.objects.get_or_create(fuente=lote.fuente, localizador=nombre+'!'+a, defaults={
                'hoja': nombre, 'celda': a, 'rango': merges.get(a, a), 'texto_original': texto,
                'contexto': {'parte': h['parte'], 'editorial': bool(re.match(r'[I-Z]', a)), 'ancla': a}})
            fragments[a] = fragmento
        def elemento(a, tipo, **kwargs):
            if not cells.get(a, '').strip(): return
            e = ElementoCurricular.objects.create(version=v, tipo=tipo, texto=cells[a], **kwargs)
            ProcedenciaCurricular.objects.create(elemento=e, fragmento=fragments[a])
        for i, inicio in enumerate(PERFIL[nombre][1]):
            fin = PERFIL[nombre][1][i+1]-1 if i < 2 else 181
            fase = FaseCurricular.objects.create(version=v, codigo=['exploracion', 'apropiacion', 'dominio'][i], nombre=cells.get(f'A{inicio}', ''), orden=i+1, fuente=fragments.get(f'A{inicio}'))
            for a, dim in [(f'G{inicio+1}', ''), (f'H{inicio+2}', 'motriz'), (f'H{inicio+3}', 'ludica'), (f'H{inicio+4}', 'cognitiva')]:
                elemento(a, 'objetivo', fase=fase, dimension=dim)
            for col, sub in [('C','motivacion'),('D','desarrollo_personal'),('E','ciudadania'),('F','convivencia')]:
                elemento(f'{col}{inicio+6}', 'objetivo', fase=fase, dimension='psicosocial', subdimension=sub)
            semana = clase = None
            for fila in range(inicio+6, fin+1):
                a, b = cells.get(f'A{fila}', ''), cells.get(f'B{fila}', '')
                if re.fullmatch(r'[0-9]+(?:\.0+)?', a):
                    semana = SemanaCurricular.objects.create(version=v, fase=fase, ordinal=int(float(a)), fuente=fragments[f'A{fila}'])
                if re.fullmatch(r'[0-9]+(?:\.0+)?', b):
                    if semana is None: raise ValidationError('Clase sin semana.')
                    clase = ClasePrevista.objects.create(semana=semana, ordinal=int(float(b)), fuente=fragments[f'B{fila}'])
                if clase is not None:
                    elemento(f'G{fila}', 'contenido', clase=clase)
                    elemento(f'H{fila}', 'desempeno', clase=clase)
            if fase.semanas.count() != PERFIL[nombre][2][i]: raise ValidationError('Distribución de fases inesperada.')
        resultado.append(str(v.uuid))
        v.original_cerrado = True
        v.save(update_fields=['original_cerrado'])
        from auditoria.servicios import registrar
        registrar(actor, v, 'curriculo_original', ['fuente', 'procedencia'])
    lote.estado, lote.resultado = 'confirmado', resultado
    lote.save(update_fields=['estado', 'resultado'])
    return lote
