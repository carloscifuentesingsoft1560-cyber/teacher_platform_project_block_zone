"""R2-B2-A: comparador puro. No importa Django ni carga fuentes, settings o bases."""
from collections import deque
import hashlib
import json
from pathlib import PurePosixPath
import re


HUELLA_CONTRATO_DOCUMENTAL = 'c207ab34193144abeabacd64aa1f570659625b8ef35bba0cfbd37e4d69b10659'
HEAD_BASE = 'dc3ba22b88985ff454d7c2af1d6a2cd0551f70d5'


class RechazoGrafo(ValueError):
    pass


def canonico(valor):
    return json.dumps(valor, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def huella(valor):
    return hashlib.sha256(canonico(valor)).hexdigest()


def esquema(valor, campos):
    if (type(valor) is not dict or set(valor) != set(campos)
            or any(type(valor[k]) is not t for k, t in campos.items())):
        raise RechazoGrafo('Campos o tipos incompatibles.')


def sha256(valor):
    if type(valor) is not str or re.fullmatch('[0-9a-f]{64}', valor) is None:
        raise RechazoGrafo('Huella SHA-256 incompatible.')


def nodo(valor):
    if (type(valor) is not list or len(valor) != 2
            or any(type(x) is not str or re.fullmatch('[a-zA-Z0-9_]+', x) is None for x in valor)):
        raise RechazoGrafo('Nodo incompatible.')
    return tuple(valor)


def nodos(valores):
    if type(valores) is not list or len(valores) > 256:
        raise RechazoGrafo('Inventario de nodos incompatible.')
    filas = [nodo(x) for x in valores]
    if len(set(filas)) != len(filas):
        raise RechazoGrafo('Nodo duplicado.')
    return set(filas)


def pares(valores):
    if type(valores) is not list or len(valores) > 2048:
        raise RechazoGrafo('Inventario de relaciones incompatible.')
    filas = []
    for fila in valores:
        if type(fila) is not list or len(fila) != 2:
            raise RechazoGrafo('Relación incompatible.')
        filas.append((nodo(fila[0]), nodo(fila[1])))
    if len(set(filas)) != len(filas):
        raise RechazoGrafo('Relación duplicada.')
    return set(filas)


def analizar_grafo(grafo):
    esquema(grafo, dict(nodos=list, aristas=list, hojas=list, intercambiables=list,
                        reemplazos=list, run_before=list))
    ns, aristas = nodos(grafo['nodos']), pares(grafo['aristas'])
    if not ns:
        raise RechazoGrafo('Grafo vacío.')
    padres, hijos = {n: set() for n in ns}, {n: set() for n in ns}
    for hijo, padre in aristas:
        if hijo not in ns or padre not in ns:
            raise RechazoGrafo('Dependencia desconocida.')
        padres[hijo].add(padre)
        hijos[padre].add(hijo)
    grados = {n: len(padres[n]) for n in ns}
    pendientes = deque(sorted(n for n in ns if grados[n] == 0))
    orden = []
    while pendientes:
        n = pendientes.popleft()
        orden.append(n)
        for hijo in sorted(hijos[n]):
            grados[hijo] -= 1
            if grados[hijo] == 0:
                pendientes.append(hijo)
    if len(orden) != len(ns):
        raise RechazoGrafo('Ciclo en el grafo.')
    hojas = {n for n in ns if not any(h[0] == n[0] for h in hijos[n])}
    por_app = {}
    for app, nombre in hojas:
        por_app.setdefault(app, set()).add(nombre)
    if any(len(filas) != 1 for filas in por_app.values()):
        raise RechazoGrafo('Conflicto: varias hojas en una aplicación.')
    if nodos(grafo['hojas']) != hojas:
        raise RechazoGrafo('Hojas declaradas incompatibles con las aristas.')
    if not pares(grafo['intercambiables']) <= aristas:
        raise RechazoGrafo('Dependencia intercambiable incompatible.')
    # No hay estas relaciones en la referencia inspeccionada. No resolverlas silenciosamente.
    if grafo['reemplazos'] or grafo['run_before']:
        raise RechazoGrafo('Reemplazo o run_before inesperado; requiere otra revisión.')
    return ns, aristas, hojas, padres, orden


def cierre(semillas, padres):
    resultado, pendientes = set(), list(nodos(semillas))
    while pendientes:
        n = pendientes.pop()
        if n not in padres:
            raise RechazoGrafo('Destino desconocido.')
        if n not in resultado:
            resultado.add(n)
            pendientes.extend(padres[n])
    return resultado


def fuentes(valores):
    if type(valores) is not list or not 1 <= len(valores) <= 10000:
        raise RechazoGrafo('Inventario de fuentes incompatible.')
    resultado = {}
    for fila in valores:
        esquema(fila, dict(raiz=str, ruta=str, sha256=str))
        p = PurePosixPath(fila['ruta'])
        if (fila['raiz'] not in ('repo', 'dependencias') or not fila['ruta']
                or len(fila['ruta']) > 512 or p.is_absolute() or '..' in p.parts
                or ':' in fila['ruta'] or '\\' in fila['ruta']
                or p.as_posix() != fila['ruta']):
            raise RechazoGrafo('Ruta de fuente no aprobada.')
        sha256(fila['sha256'])
        clave = fila['raiz'], fila['ruta'].casefold()
        if clave in resultado:
            raise RechazoGrafo('Fuente duplicada.')
        resultado[clave] = fila['sha256']
    return resultado


def validar_contrato(contrato, huella_aprobada):
    """La huella aprobada debe proceder del revisor, nunca del mensaje observado."""
    sha256(huella_aprobada)
    esquema(contrato, dict(version=int, escenario=str, repositorio=dict, perfil=dict,
        grafo=dict, destinos=dict, declaraciones=list, paquetes=list, interprete=dict,
        fuentes=list, pendientes_relaciones=list))
    if huella(contrato) != huella_aprobada:
        raise RechazoGrafo('Contrato distinto de la referencia aprobada.')
    if contrato['version'] != 1 or contrato['escenario'] != 'documental' or contrato['pendientes_relaciones']:
        raise RechazoGrafo('Contrato no cerrado estáticamente.')
    esquema(contrato['repositorio'], dict(nombre=str, head_base=str))
    if contrato['repositorio'] != dict(nombre='zona-de-bloque-github', head_base=HEAD_BASE):
        raise RechazoGrafo('Base de repositorio incompatible.')
    perfil = contrato['perfil']
    esquema(perfil, dict(apps=list, auth_user_model=str, backend=str, aliases=list,
                         routers=list, migration_modules=dict))
    if (any(type(x) is not str for x in perfil['apps']) or len(set(perfil['apps'])) != len(perfil['apps'])
            or perfil['auth_user_model'] != 'cuentas.Usuario'
            or perfil['backend'] != 'django.db.backends.dummy' or perfil['aliases'] != ['default']
            or perfil['routers'] or perfil['migration_modules']):
        raise RechazoGrafo('Perfil alternativo no autorizado.')
    ns, aristas, hojas, padres, _ = analizar_grafo(contrato['grafo'])
    esquema(contrato['destinos'], dict(anterior=dict, posterior=dict, completo=dict))
    estados = {}
    for nombre, destino in contrato['destinos'].items():
        esquema(destino, dict(semillas=list, cierre=list))
        estados[nombre] = nodos(destino['cierre'])
        if estados[nombre] != cierre(destino['semillas'], padres):
            raise RechazoGrafo('Cierre esperado incompleto o incompatible.')
    if not estados['anterior'] <= estados['posterior'] <= estados['completo']:
        raise RechazoGrafo('Destinos históricos incompatibles.')
    if estados['posterior'] - estados['anterior'] != {('deportistas', '0002_identificacion_documental')}:
        raise RechazoGrafo('Diferencia documental incompatible.')
    if estados['completo'] != ns or nodos(contrato['destinos']['completo']['semillas']) != hojas:
        raise RechazoGrafo('Destino completo distinto de las hojas publicadas.')
    declaradas = set()
    for fila in contrato['declaraciones']:
        esquema(fila, dict(nodo=list, tipo=str, referencia=list, resuelta=list))
        if (fila['tipo'] not in ('explicita', 'intercambiable') or len(fila['referencia']) != 2
                or any(type(x) is not str for x in fila['referencia'])):
            raise RechazoGrafo('Declaración de dependencia incompatible.')
        par = nodo(fila['nodo']), nodo(fila['resuelta'])
        if par in declaradas:
            raise RechazoGrafo('Declaración duplicada.')
        declaradas.add(par)
        if fila['tipo'] == 'intercambiable':
            if (fila['referencia'] != ['AUTH_USER_MODEL', 'cuentas.Usuario']
                    or par[1] != ('cuentas', '0001_initial')
                    or par not in pares(contrato['grafo']['intercambiables'])):
                raise RechazoGrafo('Resolución intercambiable incompatible.')
        elif (fila['referencia'] != fila['resuelta']
              and not (fila['referencia'] == ['contenttypes', '__first__']
                       and fila['resuelta'] == ['contenttypes', '0001_initial'])):
            raise RechazoGrafo('Resolución explícita incompatible.')
    if declaradas != aristas:
        raise RechazoGrafo('Aristas y declaraciones no coinciden.')
    for paquete in contrato['paquetes']:
        esquema(paquete, dict(nombre=str, version=str, modulo=str))
    esquema(contrato['interprete'], dict(version=str, cache_tag=str, ejecutable_sha256=str))
    sha256(contrato['interprete']['ejecutable_sha256'])
    fuentes(contrato['fuentes'])
    return estados


def comparar_grafo(contrato, observado, huellas_observadas, huella_aprobada):
    """Observado es una estructura ficticia; no se invoca ningún loader."""
    estados = validar_contrato(contrato, huella_aprobada)
    ns, aristas, hojas, padres, _ = analizar_grafo(observado)
    esperado = contrato['grafo']
    if ns != nodos(esperado['nodos']):
        raise RechazoGrafo('Nodos faltantes o adicionales.')
    if aristas != pares(esperado['aristas']):
        raise RechazoGrafo('Aristas faltantes o adicionales.')
    if hojas != nodos(esperado['hojas']) or pares(observado['intercambiables']) != pares(esperado['intercambiables']):
        raise RechazoGrafo('Hojas o relaciones especiales distintas.')
    for nombre, destino in contrato['destinos'].items():
        if cierre(destino['semillas'], padres) != estados[nombre]:
            raise RechazoGrafo('Cierre observado distinto.')
    if fuentes(huellas_observadas) != fuentes(contrato['fuentes']):
        raise RechazoGrafo('Fuentes faltantes, adicionales o alteradas.')
    return dict(version=1, escenario='documental', simulacion=True, django_ejecutado=False,
        autoriza_ddl=False, historial_bd_verificado=False, contrato_sha256=huella_aprobada,
        nodos=len(ns), aristas=len(aristas), hojas=len(hojas),
        cierres={k: len(v) for k, v in estados.items()})


def comparar_documental(contrato, observado, huellas_observadas):
    return comparar_grafo(contrato, observado, huellas_observadas, HUELLA_CONTRATO_DOCUMENTAL)


def main(argv=None):
    raise RechazoGrafo('R2-B2-A no ejecuta Django ni MigrationLoader; solo comparación de datos.')


if __name__ == '__main__':
    main()
