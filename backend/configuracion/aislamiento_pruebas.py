"""Validaciones de archivos/entorno; no importa Django, dotenv ni abre conexiones."""
import json
from pathlib import Path


CLAVE_FICTICIA = 'clave-ficticia-exclusiva-de-pruebas-aisladas-no-operativa-123456789'


def validar_raiz(carpeta, base_temporal, repositorio):
    if Path(carpeta).is_symlink() or Path(base_temporal).is_symlink():
        raise ValueError('Raíz temporal redirigida')
    carpeta, base_temporal, repositorio = map(lambda p: Path(p).resolve(),
                                             (carpeta, base_temporal, repositorio))
    if (carpeta.parent != base_temporal or not carpeta.name.startswith('zdb_pg_')
            or carpeta.is_relative_to(repositorio) or base_temporal.is_relative_to(repositorio)
            or not carpeta.is_dir() or Path(carpeta).is_symlink()):
        raise ValueError('Directorio temporal exclusivo no válido')
    return carpeta


def variables_libpq(carpeta):
    carpeta = Path(carpeta).resolve()
    return {'PGPASSFILE': str(carpeta / 'pgpass-vacio'),
            'PGSERVICEFILE': str(carpeta / 'pgservice-vacio'),
            'PGSYSCONFDIR': str(carpeta / 'pgconf'),
            'PGSSLMODE': 'disable', 'PGCONNECT_TIMEOUT': '5'}


def verificar_identidad(datos, pid, puerto, directorio_servidor, host_servidor, puerto_servidor):
    datos = Path(datos).resolve()
    lineas = (datos / 'postmaster.pid').read_text(encoding='utf-8').splitlines()
    if (int(pid) <= 0 or int(lineas[0]) != int(pid) or Path(lineas[1]).resolve() != datos
            or int(lineas[3]) != int(puerto) or lineas[5] != '127.0.0.1'
            or Path(directorio_servidor).resolve() != datos or host_servidor != '127.0.0.1'
            or int(puerto_servidor) != int(puerto)):
        raise ValueError('Identidad de clúster temporal incompatible')


def validar_entorno(entorno, repositorio):
    """Revalida el manifiesto escrito solo después de comprobar el servidor hijo."""
    carpeta = validar_raiz(entorno['ZDB_PG_TEST_RUN'], entorno['ZDB_PG_TEST_BASE'], repositorio)
    datos = carpeta / 'cluster'
    if Path(entorno['ZDB_PG_TEST_CLUSTER']).resolve() != datos or datos.is_symlink():
        raise ValueError('Ruta del clúster incompatible')
    manifiesto = json.loads((carpeta / 'identidad.json').read_text(encoding='utf-8'))
    puerto = int(manifiesto['puerto'])
    if not 1 <= puerto <= 65535 or manifiesto['host'] != '127.0.0.1':
        raise ValueError('Host o puerto no válido')
    verificar_identidad(datos, manifiesto['pid'], puerto, manifiesto['cluster'],
                       manifiesto['host'], puerto)
    esperadas = {'POSTGRES_HOST': '127.0.0.1', 'POSTGRES_PORT': str(puerto),
                 'POSTGRES_DB': 'postgres', 'POSTGRES_USER': 'postgres', 'POSTGRES_PASSWORD': ''}
    if {k: v for k, v in entorno.items() if k.upper().startswith('POSTGRES_')} != esperadas:
        raise ValueError('Configuración PostgreSQL no aislada')
    if {k: v for k, v in entorno.items() if k.upper().startswith('PG')} != variables_libpq(carpeta):
        raise ValueError('Variables libpq no aisladas')
    for nombre in ('pgpass-vacio', 'pgservice-vacio'):
        archivo = carpeta / nombre
        if archivo.is_symlink() or archivo.read_bytes() != b'':
            raise ValueError('Archivo libpq no vacío o redirigido')
    for nombre in ('tmp', 'archivos_privados', 'pgconf', 'home'):
        directorio = carpeta / nombre
        if directorio.is_symlink() or not directorio.is_dir():
            raise ValueError('Directorio de trabajo no aislado')
    for nombre in ('TEMP', 'TMP', 'TMPDIR'):
        if entorno.get(nombre) != str(carpeta / 'tmp'):
            raise ValueError('Temporales no aislados')
    for variable, clave in (('ZDB_PAQUETES_PYTHON', 'paquetes'), ('ZDB_LIBPQ_DIR', 'binarios')):
        if str(Path(entorno[variable]).resolve()) != manifiesto[clave]:
            raise ValueError('Dependencias distintas de las verificadas')
    if entorno.get('DJANGO_SECRET_KEY') != CLAVE_FICTICIA:
        raise ValueError('Clave Django ajena al ejecutor')
    if {k: v for k, v in entorno.items() if k.upper().startswith('DJANGO_')} != {
            'DJANGO_SECRET_KEY': CLAVE_FICTICIA,
            'DJANGO_SETTINGS_MODULE': 'configuracion.settings_pruebas_postgresql'}:
        raise ValueError('Configuración Django no aislada')
    if any(k.upper() in ('PYTHONPATH', 'PYTHONHOME') for k in entorno):
        raise ValueError('Overrides Python no admitidos')
    return carpeta, puerto
