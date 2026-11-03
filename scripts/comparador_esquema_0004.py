"""Comparación sin escrituras; equivalencias SQL cerradas y probadas en aislamiento."""
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_CERTIFICADO = RAIZ/'scripts/evidencias_0004/equivalencias.json'
SHA_CERTIFICADO = '234059d583bb438f53c58a0da3884abf27993b0ecd0afb2e7a9094ca9c21e109'


def huella(valor):
    return hashlib.sha256(json.dumps(valor, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def cargar_certificado(ruta=RUTA_CERTIFICADO, sha_esperado=SHA_CERTIFICADO):
    contenido = Path(ruta).read_bytes()
    if hashlib.sha256(contenido).hexdigest() != sha_esperado:
        raise RuntimeError('Certificado de equivalencias ausente o alterado.')
    return json.loads(contenido)


def firma_columnas(con):
    """Solo catálogo: nombres, tipos, collation, nulabilidad, identidad y generación."""
    with con.cursor() as c:
        c.execute("""SELECT t.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),
          a.attnotnull,a.attidentity,a.attgenerated,nc.nspname,co.collname,
          pg_catalog.pg_get_expr(d.adbin,d.adrelid)
          FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class t ON t.oid=a.attrelid
          JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
          LEFT JOIN pg_catalog.pg_collation co ON co.oid=a.attcollation
          LEFT JOIN pg_catalog.pg_namespace nc ON nc.oid=co.collnamespace
          LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
          WHERE n.nspname='public' AND t.relkind IN ('r','p') AND a.attnum>0
          AND NOT a.attisdropped ORDER BY t.relname,a.attnum""")
        return [list(r) for r in c.fetchall()]


def estructura(inventario):
    return {k: inventario[k] for k in ('restricciones','indices','funciones','triggers')}


def comparar_esquema(observado, esperado, origen, columnas, certificado):
    """No reinterpreta SQL en producción ni admite variantes no certificadas."""
    def exigir(condicion, mensaje):
        if not condicion: raise RuntimeError('Comparador 0004: '+mensaje)
    exigir(certificado['referencia_origen_sha256']==huella(estructura(origen)), 'referencia de origen distinta')
    exigir(certificado['referencia_0004_sha256']==huella(estructura(esperado)), 'referencia 0004 distinta')
    exigir(certificado['columnas_0004_sha256']==huella(columnas), 'tablas/columnas/tipos diferentes')
    exigir(set(observado['tablas'])==set(esperado['tablas']), 'inventario de tablas diferente')
    aceptadas = []
    for tipo in ('restricciones','indices','funciones','triggers'):
        exigir(set(observado[tipo])==set(esperado[tipo]), 'objetos ausentes o adicionales en '+tipo)
        for clave, valor in esperado[tipo].items():
            actual = observado[tipo][clave]
            if actual == valor: continue
            exigir(tipo in ('restricciones','indices'), 'objeto modificado: '+clave)
            exigir(set(actual)==set(valor), 'metadatos distintos: '+clave)
            exigir(all(actual[k]==valor[k] for k in valor if k!='definicion'), 'atributos distintos: '+clave)
            prueba = certificado['equivalencias'].get(tipo+':'+clave)
            exigir(prueba is not None, 'definición no certificada: '+clave)
            exigir(prueba['origen']==actual['definicion'] and prueba['restaurado']==valor['definicion']
                and prueba['canonico_origen']==prueba['canonico_restaurado'], 'condición SQL distinta: '+clave)
            exigir(origen[tipo][clave]['definicion']==prueba['origen'], 'par distinto del origen: '+clave)
            aceptadas.append(tipo+':'+clave)
    exigir(all(v['validada'] for v in observado['restricciones'].values()), 'restricción sin validar')
    exigir(all(v['valido'] and v['listo'] for v in observado['indices'].values()), 'índice inválido')
    exigir(all(v['habilitado']=='O' for v in observado['triggers'].values()), 'trigger deshabilitado')
    return {'correcto': True, 'equivalencias_aplicadas': aceptadas}
