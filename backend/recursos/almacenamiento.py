"""Blobs docentes privados: no interpreta rutas del cliente ni ejecuta archivos."""
import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET
import os
import re
import subprocess
import base64
from pathlib import Path
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import ArchivoPrivado
from .permisos import exigir_editor, custodio

MAX_BYTES = 25 * 1024 * 1024


def raiz():
    return Path(settings.ZDB_ARCHIVOS_PRIVADOS).resolve()


def ruta(archivo):
    return raiz() / str(archivo.clave)


def asegurar_custodia():
    if Path(settings.ZDB_ARCHIVOS_PRIVADOS).is_symlink():
        raise ValidationError('El almacenamiento privado no admite enlaces.')
    root = raiz()
    root.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        oculto = {'creationflags': subprocess.CREATE_NO_WINDOW}
        identidad = subprocess.run(['whoami.exe','/user','/fo','csv','/nh'], capture_output=True, timeout=10, **oculto)
        sid = re.search(rb'S-1-5-[0-9-]+', identidad.stdout)
        if not sid: raise ValidationError('No se pudo acreditar la custodia local.')
        permitidos = {sid.group().decode(), 'S-1-5-18', 'S-1-5-32-544'}
        def ejecutar_acl(args):
            r = subprocess.run(['icacls.exe', str(root), *args], capture_output=True, timeout=10, **oculto)
            if r.returncode: raise ValidationError('No se pudo restringir la custodia local.')
        ejecutar_acl(['/inheritance:r', '/grant:r', *['*'+s+':(OI)(CI)F' for s in sorted(permitidos)]])
        # Consultar solo DACL; Set-Acl puede exigir privilegios SACL innecesarios.
        ps = "$a=Get-Acl -LiteralPath '"+str(root).replace("'","''")+"'; @{protegida=$a.AreAccessRulesProtected; permitidos=@($a.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) | Where-Object {$_.AccessControlType -eq 'Allow'} | ForEach-Object {$_.IdentityReference.Value})} | ConvertTo-Json -Compress"
        def consultar_acl():
            import json
            r = subprocess.run(['powershell.exe','-NoProfile','-EncodedCommand',base64.b64encode(ps.encode('utf-16-le')).decode()], capture_output=True, timeout=10, **oculto)
            if r.returncode: raise ValidationError('No se pudo verificar la custodia local.')
            return json.loads(r.stdout)
        inicial = consultar_acl()
        for extra in set(inicial['permitidos']) - permitidos:
            ejecutar_acl(['/remove:g', '*'+extra])
        final = consultar_acl()
        if not final['protegida'] or set(final['permitidos']) != permitidos:
            raise ValidationError('Hay accesos locales adicionales; no se almacena el archivo.')
    else:
        root.chmod(0o700)


def verificar_zip(datos):
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            infos = z.infolist()
            if len(infos) > 5000 or sum(x.file_size for x in infos) > 50 * 1024 * 1024:
                raise ValidationError('Archivo comprimido excesivo.')
            nombres = z.namelist()
            for i in infos:
                if i.flag_bits & 1 or '..' in Path(i.filename).parts or i.filename.startswith(('/', '\\')) or '\\' in i.filename or ':' in i.filename:
                    raise ValidationError('Ruta o cifrado no admitidos.')
                if 'vba' in i.filename.lower() or 'externalLink' in i.filename or '/embeddings/' in i.filename:
                    raise ValidationError('Contenido activo no admitido.')
                if i.filename.endswith('.rels'):
                    if any(x.attrib.get('TargetMode') == 'External' for x in ET.fromstring(z.read(i))):
                        raise ValidationError('Relaciones externas no admitidas.')
            if 'xl/workbook.xml' in nombres:
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            if 'word/document.xml' in nombres:
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError):
        raise ValidationError('Contenedor no válido.')
    raise ValidationError('Solo se admiten documentos Office sin contenido activo.')


def tipo_verificado(datos, nombre):
    ext = Path(nombre).suffix.lower()
    if datos.startswith(b'PK') and ext in ('.xlsx', '.docx'):
        tipo = verificar_zip(datos)
        if (ext == '.xlsx') != ('spreadsheet' in tipo):
            raise ValidationError('Firma y extensión no coinciden.')
        return tipo
    firmas = {'.pdf': (b'%PDF-', 'application/pdf'), '.png': (b'\x89PNG\r\n\x1a\n', 'image/png'), '.jpg': (b'\xff\xd8\xff', 'image/jpeg'), '.jpeg': (b'\xff\xd8\xff', 'image/jpeg')}
    if ext in firmas and datos.startswith(firmas[ext][0]):
        return firmas[ext][1]
    if ext in ('.mp4', '.mov') and len(datos) > 12 and datos[4:8] == b'ftyp':
        return 'video/mp4' if ext == '.mp4' else 'video/quicktime'
    if ext == '.txt' and b'\0' not in datos:
        try:
            datos.decode('utf-8')
            return 'text/plain'
        except UnicodeDecodeError:
            pass
    raise ValidationError('Tipo o firma no admitidos.')


@transaction.atomic
def subir(actor, archivo, finalidad, declaracion):
    from .editorial import bloquear
    bloquear(actor)
    if finalidad not in ('fuente_curricular', 'material_docente') or declaracion is not True:
        raise ValidationError('Confirma derechos y ausencia de datos personales o grabaciones privadas.')
    if finalidad == 'fuente_curricular' and not custodio(actor):
        raise PermissionDenied('La custodia de fuentes es institucional.')
    datos = archivo.read(MAX_BYTES + 1)
    if not datos or len(datos) > MAX_BYTES:
        raise ValidationError('Tamaño admitido: 1 byte a 25 MiB.')
    nombre = Path(archivo.name.replace('\\', '/')).name[:200]
    tipo = tipo_verificado(datos, nombre)
    a = ArchivoPrivado(autor=actor, nombre=nombre, sha256=hashlib.sha256(datos).hexdigest(), bytes=len(datos), tipo=tipo, finalidad=finalidad)
    asegurar_custodia()
    destino = ruta(a)
    try:
        with destino.open('xb') as f:
            f.write(datos)
        with transaction.atomic():
            a.save()
    except BaseException:
        if destino.is_file() and destino.parent == raiz():
            destino.unlink()
        raise
    return a
