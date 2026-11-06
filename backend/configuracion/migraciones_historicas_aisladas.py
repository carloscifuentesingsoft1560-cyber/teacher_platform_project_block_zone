"""R2-A: contratos y simulaciones. Sin Django, SQL, conexiones ni procesos nuevos."""
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from threading import RLock
from types import MappingProxyType
from uuid import uuid4

from .aislamiento_pruebas import validar_entorno


class BarreraHistorica(ValueError):
    """Entrada/contexto rechazado; nunca un resultado de migración."""


@dataclass(frozen=True)
class Escenario:
    archivo: str
    clase: str
    inicio: str
    destino: str
    reversion_pendiente: bool = False


ESCENARIOS = MappingProxyType({
    'nucleo': Escenario('backend/cuentas/tests/test_migracion_nucleo.py', 'MigracionNucleo', 'cuentas/0004', 'hojas_publicadas'),
    'documental': Escenario('backend/deportistas/test_migracion_documental.py', 'MigracionDocumentalPreservaDatos', 'deportistas/0001+inscripciones/0001', 'deportistas/0002+inscripciones/0001'),
    'facultades': Escenario('backend/deportistas/test_migracion_facultades.py', 'MigracionFacultadesPreservaDatos', 'deportistas/0002+inscripciones/0001', 'deportistas/0003+inscripciones/0001'),
    'etapa3': Escenario('backend/recursos/test_migracion.py', 'MigracionEtapa3', 'sin_recursos_curriculo_biblioteca', 'hojas_publicadas'),
    'seguridad_ascensos': Escenario('backend/inscripciones/test_seguridad_migracion_b1.py', 'SeguridadMigracionB1', 'inscripciones/0001', 'inscripciones/0002', True),
    'api_anterior': Escenario('backend/inscripciones/test_api_ejecucion.py', 'ApiEsquemaAnterior', 'inscripciones/0003', 'inscripciones/0005'),
    'movimientos': Escenario('backend/inscripciones/test_movimientos_b3_b2.py', 'MigracionMovimientosB3B2', 'inscripciones/0003', 'inscripciones/0005', True),
    'planes': Escenario('backend/sesiones/test_curricular.py', 'MigracionPlanesExistentes', 'sesiones/0001', 'sesiones/0007'),
})


def escenario(nombre):
    if type(nombre) is not str or nombre not in ESCENARIOS:
        raise BarreraHistorica('Escenario fuera del registro cerrado.')
    return ESCENARIOS[nombre]


def canonico(valor):
    return json.dumps(valor, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def leer_json(texto):
    if type(texto) is not str or len(texto) > 65536:
        raise BarreraHistorica('Mensaje ausente o excesivo.')

    def pares(filas):
        resultado = {}
        for clave, valor in filas:
            if clave in resultado:
                raise BarreraHistorica('Clave JSON duplicada.')
            resultado[clave] = valor
        return resultado

    try:
        return json.loads(texto, object_pairs_hook=pares,
                          parse_constant=lambda _: (_ for _ in ()).throw(BarreraHistorica('JSON no finito.')))
    except (ValueError, TypeError, RecursionError) as error:
        raise BarreraHistorica('Mensaje JSON inválido.') from error


def nodo(valor):
    if not isinstance(valor, (tuple, list)) or len(valor) != 2 or any(type(x) is not str for x in valor):
        raise BarreraHistorica('Nodo inválido; no se admiten destinos None ni SQL.')
    import re
    if not all(re.fullmatch(r'[a-zA-Z0-9_]+', x) for x in valor):
        raise BarreraHistorica('Identificador de migración no válido.')
    return tuple(valor)


@dataclass(frozen=True)
class ContratoPlan:
    """Grafo/estados declarados por el padre. No certifica un grafo real de Django.

    R2-B debe obtenerlos del loader publicado y comprobar el historial por SQL.
    R2-A solo valida el contrato puro; jamás ejecuta el plan.
    """
    grafo: tuple
    anterior: tuple
    final: tuple

    def __post_init__(self):
        g = {nodo(n): tuple(nodo(d) for d in ds) for n, ds in self.grafo}
        if len(g) != len(self.grafo):
            raise BarreraHistorica('Grafo duplicado.')
        anteriores = tuple(nodo(n) for n in self.anterior)
        finales = tuple(nodo(n) for n in self.final)
        if len(set(anteriores)) != len(anteriores) or len(set(finales)) != len(finales):
            raise BarreraHistorica('Historial duplicado.')
        visitados, activos = set(), set()

        def visitar(n):
            if n not in g or n in activos:
                raise BarreraHistorica('Dependencia ausente o circular.')
            if n in visitados:
                return
            activos.add(n)
            for d in g[n]:
                visitar(d)
            activos.remove(n)
            visitados.add(n)

        for n in g:
            visitar(n)
        for estado in (set(anteriores), set(finales)):
            if not estado <= set(g) or any(not set(g[n]) <= estado for n in estado):
                raise BarreraHistorica('Estado no cerrado por dependencias.')
        if not set(anteriores) <= set(finales):
            raise BarreraHistorica('El destino exige retroceso indirecto.')
        object.__setattr__(self, 'grafo', tuple(sorted(g.items())))
        object.__setattr__(self, 'anterior', tuple(sorted(anteriores)))
        object.__setattr__(self, 'final', tuple(sorted(finales)))

    def huella(self):
        return hashlib.sha256(canonico([self.grafo, self.anterior, self.final])).hexdigest()

    def validar(self, historial, pasos):
        if not isinstance(historial, (list, tuple)) or not isinstance(pasos, (list, tuple)):
            raise BarreraHistorica('Historial y pasos estructurados requeridos.')
        filas = [nodo(n) for n in historial]
        if len(set(filas)) != len(filas) or set(filas) != set(self.anterior):
            raise BarreraHistorica('Historial aplicado inesperado.')
        g, actual = dict(self.grafo), set(filas)
        for paso in pasos:
            if type(paso) is not dict or set(paso) != {'nodo', 'atras'} or paso['atras'] is not False:
                raise BarreraHistorica('Operación inversa o parámetro no autorizado.')
            n = nodo(paso['nodo'])
            if n not in g or n in actual or n not in self.final or not set(g[n]) <= actual:
                raise BarreraHistorica('Paso ajeno, repetido o dependencia no aplicada.')
            actual.add(n)
        if actual != set(self.final):
            raise BarreraHistorica('Plan incompleto o destino incompatible.')


def _sin_redireccion(ruta):
    if ruta.is_symlink() or getattr(ruta, 'is_junction', lambda: False)():
        raise BarreraHistorica('Ruta redirigida.')


class RegistroEjecucion:
    """Registro local del padre, ligado al objeto de proceso que ya creó el runner.

    No contiene adaptadores de conexión, creación/borrado de bases ni migraciones.
    Los manifiestos son permisos de VALIDACIÓN SIMULADA, no de ejecución.
    """
    def __init__(self, entorno, repositorio, proceso, base_principal):
        permitidas = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE',
            'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST', 'POSTGRES_PORT',
            'ZDB_PG_TEST_CLUSTER', 'ZDB_PG_TEST_RUN', 'ZDB_PG_TEST_BASE', 'ZDB_PAQUETES_PYTHON', 'ZDB_LIBPQ_DIR',
            'PYTHONDONTWRITEBYTECODE', 'PATH', 'TEMP', 'TMP', 'TMPDIR', 'HOME', 'USERPROFILE', 'APPDATA',
            'LOCALAPPDATA', 'PSYCOPG_IMPL', 'DJANGO_SETTINGS_MODULE', 'PYTHONIOENCODING', 'DJANGO_SECRET_KEY',
            'PGPASSFILE', 'PGSERVICEFILE', 'PGSYSCONFDIR', 'PGSSLMODE', 'PGCONNECT_TIMEOUT'}
        if set(entorno) - permitidas:
            raise BarreraHistorica('Variables heredadas o credenciales ajenas al contrato.')
        self._entorno = dict(entorno)
        self._repositorio = Path(repositorio).resolve()
        if self._repositorio != Path(__file__).resolve().parents[2]:
            raise BarreraHistorica('Repositorio distinto del que contiene el contrato.')
        self._proceso = proceso
        self._carpeta, self._puerto = validar_entorno(self._entorno, self._repositorio)
        self._identidad = (self._carpeta / 'identidad.json').read_bytes()
        self._pid = json.loads(self._identidad)['pid']
        import re
        if type(base_principal) is not str or not re.fullmatch(r'test_zdb_fase3_[0-9a-f]{12}', base_principal):
            raise BarreraHistorica('Base principal no identificada como prueba.')
        self._principal = base_principal
        self._revalidar()
        self._id = uuid4().hex
        self._secreto = secrets.token_bytes(32)
        self._emitidos = {}
        self._usados = set()
        self._cerrojo = RLock()
        self._directorio = self._carpeta / ('r2a_' + self._id)
        self._directorio.mkdir(mode=0o700)
        self._ino = self._directorio.stat().st_ino

    def _revalidar(self):
        carpeta, puerto = validar_entorno(self._entorno, self._repositorio)
        _sin_redireccion(carpeta)
        _sin_redireccion(carpeta / 'identidad.json')
        _sin_redireccion(carpeta / 'cluster')
        _sin_redireccion(carpeta / 'cluster' / 'postmaster.pid')
        if (carpeta != self._carpeta or puerto != self._puerto or self._proceso.pid != self._pid
                or self._proceso.poll() is not None or (carpeta / 'identidad.json').read_bytes() != self._identidad):
            raise BarreraHistorica('Clúster/proceso/manifiesto incompatible con el padre.')

    def evidencia(self, etapa, datos):
        self._revalidar()
        _sin_redireccion(self._directorio)
        if self._directorio.resolve() != self._carpeta / ('r2a_' + self._id) or self._directorio.stat().st_ino != self._ino:
            raise BarreraHistorica('Directorio de evidencia ajeno.')
        if etapa not in ('reserva', 'consumo', 'fallo_simulado'):
            raise BarreraHistorica('Etapa ajena al contrato.')
        contenido = canonico(dict(version=1, simulacion=True, ejecucion=self._id, etapa=etapa, datos=datos))
        with (self._directorio / (uuid4().hex + '.json')).open('xb') as archivo:
            archivo.write(contenido)

    def reservar(self, caso, contrato, bases_existentes):
        escenario(caso)
        if type(contrato) is not ContratoPlan:
            raise BarreraHistorica('Contrato de plan requerido.')
        if not isinstance(bases_existentes, (list, tuple, set, frozenset)) or any(type(b) is not str for b in bases_existentes):
            raise BarreraHistorica('Inventario de bases requerido; R2-A no lo consulta.')
        self._revalidar()
        nonce = uuid4().hex
        base = 'test_zdb_hist_' + self._id[:12] + '_' + nonce[:12]
        if base == self._principal or base in bases_existentes or any(e[0]['base'] == base for e in self._emitidos.values()):
            raise BarreraHistorica('Base preexistente o ya reservada; nunca reutilizar.')
        payload = dict(version=1, escenario=caso, ejecucion=self._id, nonce=nonce, base=base,
            principal=self._principal, pid=self._pid, host='127.0.0.1', puerto=self._puerto,
            cluster=str(self._carpeta / 'cluster'), identidad_sha256=hashlib.sha256(self._identidad).hexdigest(),
            contrato_sha256=contrato.huella(), modo='validacion_simulada')
        firma = hmac.new(self._secreto, canonico(payload), hashlib.sha256).hexdigest()
        self.evidencia('reserva', dict(escenario=caso, nonce=nonce, base=base))
        self._emitidos[nonce] = (dict(payload), firma, contrato)
        return dict(payload=payload, firma=firma)

    def validar(self, manifiesto):
        self._revalidar()
        if type(manifiesto) is not dict or set(manifiesto) != {'payload', 'firma'} or type(manifiesto['payload']) is not dict:
            raise BarreraHistorica('Manifiesto ausente o campos ajenos.')
        p = manifiesto['payload']
        esquema = dict.fromkeys(('escenario', 'ejecucion', 'nonce', 'base', 'principal',
            'host', 'cluster', 'identidad_sha256', 'contrato_sha256', 'modo'), str)
        esquema.update(version=int, pid=int, puerto=int)
        if (set(p) != set(esquema)
                or any(type(p[campo]) is not tipo for campo, tipo in esquema.items())):
            raise BarreraHistorica('Esquema o tipos del payload incompatibles.')
        nonce = p.get('nonce')
        if type(nonce) is not str or nonce not in self._emitidos or nonce in self._usados:
            raise BarreraHistorica('Manifiesto ajeno, perdido o ya consumido.')
        original, firma, contrato = self._emitidos[nonce]
        recibido = canonico(p)
        recalculada = hmac.new(self._secreto, recibido, hashlib.sha256).hexdigest()
        import re
        if (type(manifiesto['firma']) is not str
                or re.fullmatch(r'[0-9a-f]{64}', manifiesto['firma']) is None
                or not hmac.compare_digest(recalculada, manifiesto['firma'])
                or not hmac.compare_digest(firma, recalculada)
                or recibido != canonico(original)):
            raise BarreraHistorica('Manifiesto alterado o propiedad no acreditada.')
        return contrato

    def consumir(self, manifiesto, historial, pasos):
        with self._cerrojo:
            contrato = self.validar(manifiesto)
            contrato.validar(historial, pasos)
            nonce = manifiesto['payload']['nonce']
            # Marcar antes de escribir: un fallo de evidencia no permite reutilización.
            self._usados.add(nonce)
            self.evidencia('consumo', dict(nonce=nonce, resultado='contrato_simulado_validado'))
            return 'contrato_simulado_validado'

    def registrar_fallo(self, manifiesto, etapa, error):
        with self._cerrojo:
            self.validar(manifiesto)
            if etapa not in ('creacion_simulada', 'ejecucion_simulada', 'timeout_simulado') or not isinstance(error, Exception):
                raise BarreraHistorica('Fallo ajeno al contrato simulado.')
            self._usados.add(manifiesto['payload']['nonce'])
            try:
                self.evidencia('fallo_simulado', dict(nonce=manifiesto['payload']['nonce'], etapa=etapa, tipo=type(error).__name__))
            except Exception:
                error.add_note('Falló también el registro de evidencia; conservar el error original.')
            raise error
