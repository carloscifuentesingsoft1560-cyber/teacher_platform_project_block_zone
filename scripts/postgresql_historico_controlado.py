"""R2-B1: protocolo documental exclusivamente simulado, en memoria y sin E/S.

Las identidades son declaraciones ficticias del padre, no pruebas de un servidor.
No importa Django, drivers, ejecutores, red ni lanzadores de procesos.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
from pathlib import PureWindowsPath
import re
import secrets
from threading import RLock
from types import MappingProxyType


MAX_TRAMA = 65536
MAX_PLAZO_MS = 30000
PROTOCOLO = 'zdb_documental_r2b1'
ETAPAS = ('identidad_declarada', 'grafo_declarado', 'reserva_simulada',
          'configuracion_declarada', 'plan_declarado', 'resultado_simulado', 'cierre_simulado')
ESCENARIOS = MappingProxyType({'documental': ETAPAS})


class BarreraProtocolo(ValueError):
    """Rechazo del protocolo; un cierre completado nunca se modifica."""


class TramaIncompleta(BarreraProtocolo):
    pass


def canonico(valor):
    return json.dumps(valor, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def huella(valor):
    return hashlib.sha256(canonico(valor)).hexdigest()


def esquema(valor, campos):
    if (type(valor) is not dict or set(valor) != set(campos)
            or any(type(valor[k]) is not t for k, t in campos.items())):
        raise BarreraProtocolo('Campos o tipos no autorizados.')


def hexadecimal(valor, longitud):
    if type(valor) is not str or re.fullmatch('[0-9a-f]{%d}' % longitud, valor) is None:
        raise BarreraProtocolo('Huella o identificador incompatible.')


def leer_trama(trama):
    if type(trama) is not bytes or len(trama) > MAX_TRAMA:
        raise BarreraProtocolo('Tipo o tamaño de trama incompatible.')
    if not trama:
        raise EOFError('Canal simulado finalizado antes de completar el protocolo.')
    if not trama.endswith(b'\n'):
        raise TramaIncompleta('Falta el delimitador de la trama.')
    if b'\n' in trama[:-1]:
        raise BarreraProtocolo('Se requiere exactamente una trama.')

    def pares(filas):
        resultado = {}
        for k, v in filas:
            if k in resultado:
                raise BarreraProtocolo('Clave duplicada.')
            resultado[k] = v
        return resultado

    def constante(_):
        raise BarreraProtocolo('Constante JSON no finita.')

    def decimal_finito(texto):
        valor = float(texto)
        if not math.isfinite(valor):
            raise BarreraProtocolo('Número JSON fuera del intervalo finito.')
        return valor

    try:
        return json.loads(trama[:-1].decode('utf-8'), object_pairs_hook=pares,
                          parse_constant=constante, parse_float=decimal_finito)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise BarreraProtocolo('JSON incompatible.') from error


@dataclass(frozen=True)
class IdentidadSimulada:
    pid: int
    host: str
    puerto: int
    raiz: str
    directorio: str
    sello: str

    def __post_init__(self):
        esquema(self.datos(), dict(pid=int, host=str, puerto=int, raiz=str,
                                   directorio=str, sello=str))
        hexadecimal(self.sello, 64)
        raiz, directorio = PureWindowsPath(self.raiz), PureWindowsPath(self.directorio)
        if (self.pid <= 0 or self.host != '127.0.0.1' or not 1024 <= self.puerto <= 65535
                or not raiz.is_absolute() or '..' in raiz.parts or '..' in directorio.parts
                or not raiz.name.startswith('zdb_pg_') or directorio != raiz / 'cluster'
                or self.raiz != raiz.as_posix() or self.directorio != directorio.as_posix()):
            raise BarreraProtocolo('Identidad ficticia no admisible.')

    def datos(self):
        return dict(pid=self.pid, host=self.host, puerto=self.puerto,
                    raiz=self.raiz, directorio=self.directorio, sello=self.sello)


def validar_plan(plan):
    """Solo conjuntos y pasos declarados; no acredita dependencias Django reales."""
    esquema(plan, dict(historial=list, pasos=list, destino=list))
    if any(len(plan[k]) > 256 for k in plan):
        raise BarreraProtocolo('Plan declarado excesivo.')

    def nodo(n):
        if (type(n) is not list or len(n) != 2
                or any(type(x) is not str or re.fullmatch('[a-zA-Z0-9_]+', x) is None for x in n)):
            raise BarreraProtocolo('Nodo no autorizado.')
        return tuple(n)

    anteriores = [nodo(n) for n in plan['historial']]
    destino = [nodo(n) for n in plan['destino']]
    if len(set(anteriores)) != len(anteriores) or len(set(destino)) != len(destino):
        raise BarreraProtocolo('Historial o destino duplicado.')
    actual = set(anteriores)
    if not actual <= set(destino):
        raise BarreraProtocolo('Retroceso indirecto prohibido.')
    for paso in plan['pasos']:
        esquema(paso, dict(nodo=list, atras=bool))
        if paso['atras'] is not False:
            raise BarreraProtocolo('Plan inverso prohibido.')
        n = nodo(paso['nodo'])
        if n in actual or n not in destino:
            raise BarreraProtocolo('Paso ajeno o repetido.')
        actual.add(n)
    if actual != set(destino):
        raise BarreraProtocolo('Plan incompleto.')
    return huella(plan)


def configuracion_propuesta(contexto):
    """Descriptor inerte; nunca configura settings ni importa Django."""
    return dict(alias='default', base=contexto['base'], usuario=contexto['usuario'],
                host=contexto['identidad']['host'], puerto=contexto['identidad']['puerto'],
                otros_aliases=[], cargar_dotenv=False, conexiones_iniciadas=False,
                django_iniciado=False, grafo_real_validado=False)


def validar_configuracion(propuesta, contexto):
    esquema(propuesta, dict(alias=str, base=str, usuario=str, host=str, puerto=int,
        otros_aliases=list, cargar_dotenv=bool, conexiones_iniciadas=bool,
        django_iniciado=bool, grafo_real_validado=bool))
    if canonico(propuesta) != canonico(configuracion_propuesta(contexto)):
        raise BarreraProtocolo('Configuración alternativa o inicialización prematura.')


class ContextoHijoSimulado:
    """Capacidad en memoria del canal; no serializable como autorización operativa."""
    def __init__(self, padre, marca):
        self._padre, self._marca = padre, marca
        self._vistos = set()
        self._cerrado = False


class RegistroDocumentalSimulado:
    def __init__(self, identidad, codigo_sha256, plan, inventario, *, escenario='documental',
                 inicio_ms=0, plazo_ms=MAX_PLAZO_MS):
        if type(identidad) is not IdentidadSimulada or type(escenario) is not str or escenario not in ESCENARIOS:
            raise BarreraProtocolo('Escenario o identidad fuera del contrato.')
        hexadecimal(codigo_sha256, 64)
        contrato = validar_plan(plan)
        if (type(inventario) is not list or any(type(x) is not str for x in inventario)
                or len(set(inventario)) != len(inventario)):
            raise BarreraProtocolo('Inventario ficticio no válido.')
        if (type(inicio_ms) is not int or inicio_ms < 0 or type(plazo_ms) is not int
                or not 1 <= plazo_ms <= MAX_PLAZO_MS):
            raise BarreraProtocolo('Plazo simulado incompatible.')
        self._id, canal = secrets.token_hex(16), secrets.token_hex(16)
        base = 'test_zdb_hist_' + self._id
        usuario = 'zdb_hist_' + secrets.token_hex(12)
        if base in inventario or base in ('postgres', 'template0', 'template1'):
            raise BarreraProtocolo('Reserva preexistente; no reutilizar.')
        contexto = dict(escenario=escenario, identidad=identidad.datos(), base=base,
                        usuario=usuario, codigo_sha256=codigo_sha256, contrato_sha256=contrato)
        self._contexto = canonico(contexto)
        self._plan = canonico(plan)
        self._canal = canal
        self._secreto = secrets.token_bytes(32)
        self._marca = object()
        self._hijo = ContextoHijoSimulado(self, self._marca)
        self._limite = inicio_ms + plazo_ms
        self._ultimo = inicio_ms
        self._indice = 0
        self._pendiente = None
        self._usados = set()
        self._eventos = []
        self._fallo_evidencia = False
        self._estado = 'registrada'
        self._error_original = None
        self._cerrojo = RLock()

    @property
    def contexto(self):
        return json.loads(self._contexto)

    @property
    def evidencias(self):
        return json.loads(canonico(self._eventos))

    @property
    def estado(self):
        return self._estado

    @property
    def error_original(self):
        return self._error_original

    def contexto_hijo(self):
        return self._hijo

    def simular_fallo_evidencia(self):
        self._fallo_evidencia = True

    def _evidencia(self, etapa, error=None):
        if self._fallo_evidencia:
            raise OSError('Fallo ficticio de evidencia en memoria.')
        self._eventos.append(dict(version=1, simulacion=True, ejecucion=self._id,
            etapa=etapa, secuencia=self._indice + 1, estado=self._estado,
            error_tipo=None if error is None else type(error).__name__))

    def _capacidad(self, contexto):
        if (type(contexto) is not ContextoHijoSimulado or contexto is not self._hijo
                or contexto._padre is not self or contexto._marca is not self._marca
                or contexto._cerrado):
            raise BarreraProtocolo('Falta el canal privado del padre emisor.')

    def _rechazar_cierre_completado(self):
        if self._estado == 'cerrada_simulada':
            raise BarreraProtocolo('Solicitud posterior al cierre; resultado inmutable.')

    def _comprobar(self, observacion, ahora_ms):
        self._rechazar_cierre_completado()
        if self._estado == 'fallida':
            raise BarreraProtocolo('Ejecución terminal; no reutilizar.')
        if type(ahora_ms) is not int or ahora_ms < self._ultimo:
            raise BarreraProtocolo('Reloj simulado no monotónico.')
        if ahora_ms >= self._limite:
            raise TimeoutError('Plazo ficticio agotado.')
        self._ultimo = ahora_ms
        if type(observacion) is not dict or canonico(observacion) != self._contexto:
            raise BarreraProtocolo('Identidad, código, contrato o destino cambiados.')
        if validar_plan(json.loads(self._plan)) != self.contexto['contrato_sha256']:
            raise BarreraProtocolo('El plan declarado cambió dentro del contexto.')

    def _firmar(self, payload):
        firma = hmac.new(self._secreto, canonico(payload), hashlib.sha256).hexdigest()
        trama = canonico(dict(payload=payload, firma=firma)) + b'\n'
        if len(trama) > MAX_TRAMA:
            raise BarreraProtocolo('Trama emitida excesiva.')
        return trama

    def _verificar(self, trama, emisor):
        mensaje = leer_trama(trama)
        esquema(mensaje, dict(payload=dict, firma=str))
        hexadecimal(mensaje['firma'], 64)
        p = mensaje['payload']
        campos = dict(version=int, protocolo=str, modo=str, escenario=str, ejecucion=str,
            canal=str, emisor=str, secuencia=int, nonce=str, etapa=str, contexto=dict)
        if emisor == 'hijo':
            campos.update(solicitud_sha256=str, resultado=str)
        esquema(p, campos)
        # Igualdad canónica además de esquema: distingue también tipos anidados.
        if (p['version'] != 1 or p['protocolo'] != PROTOCOLO or p['modo'] != 'simulacion'
                or p['escenario'] != 'documental' or p['ejecucion'] != self._id
                or p['canal'] != self._canal or p['emisor'] != emisor
                or p['secuencia'] != self._indice + 1
                or canonico(p['contexto']) != self._contexto):
            raise BarreraProtocolo('Emisor, secuencia o contexto incompatible.')
        hexadecimal(p['nonce'], 32)
        firma = hmac.new(self._secreto, canonico(p), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, mensaje['firma']):
            raise BarreraProtocolo('Integridad criptográfica no acreditada.')
        return p

    def fallar(self, error):
        """Invalida antes de registrar y conserva el primer error, incluso al fallar evidencia."""
        if not isinstance(error, Exception):
            raise BarreraProtocolo('Excepción original requerida.')
        with self._cerrojo:
            self._rechazar_cierre_completado()
            if self._error_original is not None:
                raise self._error_original
            self._error_original = error
            self._estado = 'fallida'
            if self._pendiente is not None:
                self._usados.add(self._pendiente['nonce'])
            self._pendiente = None
            self._hijo._cerrado = True
            try:
                self._evidencia('fallo_simulado', error)
            except Exception:
                error.add_note('Falló también la evidencia simulada; se conserva el error original.')
            raise error

    def emitir(self, etapa, observacion, ahora_ms):
        with self._cerrojo:
            self._rechazar_cierre_completado()
            try:
                self._comprobar(observacion, ahora_ms)
                if self._pendiente is not None or type(etapa) is not str or etapa != ETAPAS[self._indice]:
                    raise BarreraProtocolo('Etapa duplicada o fuera de secuencia.')
                nonce = secrets.token_hex(16)
                if nonce in self._usados:
                    raise BarreraProtocolo('Nonce ya utilizado.')
                p = dict(version=1, protocolo=PROTOCOLO, modo='simulacion', escenario='documental',
                    ejecucion=self._id, canal=self._canal, emisor='padre', secuencia=self._indice + 1,
                    nonce=nonce, etapa=etapa, contexto=self.contexto)
                self._pendiente = p
                self._evidencia('envio_simulado')
                return self._firmar(p)
            except Exception as error:
                self.fallar(error)

    def recibir_en_hijo(self, contexto, trama, observacion, ahora_ms):
        with self._cerrojo:
            try:
                self._capacidad(contexto)
                self._comprobar(observacion, ahora_ms)
                p = self._verificar(trama, 'padre')
                if (self._pendiente is None or canonico(p) != canonico(self._pendiente)
                        or p['nonce'] in contexto._vistos or p['nonce'] in self._usados):
                    raise BarreraProtocolo('Solicitud ajena o repetida.')
                if p['etapa'] == 'configuracion_declarada':
                    validar_configuracion(configuracion_propuesta(self.contexto), self.contexto)
                contexto._vistos.add(p['nonce'])
                respuesta = dict(p, emisor='hijo', solicitud_sha256=huella(p),
                                 resultado='validacion_simulada')
                return self._firmar(respuesta)
            except Exception as error:
                self.fallar(error)

    def confirmar(self, trama, observacion, ahora_ms):
        with self._cerrojo:
            self._rechazar_cierre_completado()
            try:
                self._comprobar(observacion, ahora_ms)
                p = self._verificar(trama, 'hijo')
                original = self._pendiente
                if (original is None or p['nonce'] in self._usados
                        or p['nonce'] not in self._hijo._vistos
                        or p != dict(original, emisor='hijo', solicitud_sha256=huella(original),
                                     resultado='validacion_simulada')):
                    raise BarreraProtocolo('Respuesta ajena, alterada o repetida.')
                self._usados.add(p['nonce'])
                self._pendiente = None
                self._estado = ETAPAS[self._indice]
                self._evidencia('confirmacion_simulada')
                self._indice += 1
                if self._indice == len(ETAPAS):
                    self._estado = 'cerrada_simulada'
                    self._hijo._cerrado = True
                return self._estado
            except Exception as error:
                self.fallar(error)


def main(argv=None):
    raise BarreraProtocolo('R2-B1 no dispone de entrada operativa independiente.')


if __name__ == '__main__':
    main()
