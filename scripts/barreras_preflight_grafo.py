"""Barreras R2-B2-A. Django real permanece prohibido en este incremento.

El cargador ejecuta solo fuentes Python aprobadas por ruta y SHA-256, sin .pyc.
La instrumentación Django usa exclusivamente superficies ficticias en memoria.
No es un sandbox del sistema operativo ni una frontera ante código hostil nativo.
"""
import builtins
from contextlib import ExitStack
import hashlib
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch


class IntentoProhibido(RuntimeError):
    pass


PERFIL = dict(backend='django.db.backends.dummy', aliases=['default'], settings_module=None,
              django_configurado=False, apps_cargadas=False)
RAICES_PROHIBIDAS = frozenset(('django', 'dotenv', 'psycopg', 'psycopg2', 'asyncpg',
    'pg8000', 'sqlite3', '_sqlite3', 'ctypes', '_ctypes'))
NATIVAS_NO_IMPORTABLES = frozenset(('_socket', 'ssl', '_ssl', '_winapi', '_overlapped'))
SUPERFICIES = frozenset(('conexion', 'cursor', 'orm', 'sql', 'migrar', 'revertir', 'recorder'))
_ACTIVA = False


def _canonico(valor):
    return json.dumps(valor, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


class _Cargador(importlib.abc.Loader):
    def __init__(self, fuente, ruta):
        self.fuente, self.ruta = fuente, ruta

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Ejecuta exactamente los bytes cuya huella se comprobó, sin caché de bytecode.
        exec(compile(self.fuente, self.ruta, 'exec', dont_inherit=True), module.__dict__)


class _Buscador(importlib.abc.MetaPathFinder):
    def __init__(self, guardia):
        self.guardia = guardia

    def find_spec(self, fullname, path=None, target=None):
        g = self.guardia
        g._nombre(fullname)
        if fullname in g._fuentes:
            ruta, _ = g._fuentes[fullname]
            datos = g._fuente(fullname)
            return importlib.util.spec_from_file_location(fullname, ruta,
                loader=_Cargador(datos, str(ruta)))
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None:
            g._origen(fullname, spec.origin)
        return spec


class BarrerasPreflight:
    def __init__(self, fuentes_aprobadas, *, entorno, perfil=None, fuentes_simuladas=None):
        """Las rutas/huellas aprobadas son entrada confiable del revisor, no del módulo importado."""
        if type(fuentes_aprobadas) is not dict or type(entorno) is not dict:
            raise IntentoProhibido('Política de barreras incompatible.')
        self._fuentes = {}
        for nombre, fila in fuentes_aprobadas.items():
            if (type(nombre) is not str or type(fila) is not dict or set(fila) != {'ruta', 'sha256'}
                    or type(fila['ruta']) is not str or type(fila['sha256']) is not str
                    or re.fullmatch('[0-9a-f]{64}', fila['sha256']) is None):
                raise IntentoProhibido('Fuente aprobada incompatible.')
            ruta = Path(fila['ruta'])
            if not ruta.is_absolute() or ruta.suffix != '.py':
                raise IntentoProhibido('Solo se admiten fuentes Python absolutas.')
            self._fuentes[nombre] = (ruta, fila['sha256'])
        self._entorno = dict(entorno)
        self._perfil = json.loads(_canonico(PERFIL if perfil is None else perfil))
        self._simuladas = dict(fuentes_simuladas or {})
        if any(type(k) is not str or not k.startswith('_zdb_simulado_')
               or type(v) is not str or re.fullmatch('[0-9a-f]{64}', v) is None
               for k, v in self._simuladas.items()):
            raise IntentoProhibido('Fuente simulada incompatible.')
        self._eventos = []
        self._intentos = 0
        self._stack = None
        self._usada = False
        self.error_original = None

    @property
    def evidencias(self):
        return json.loads(_canonico(self._eventos))

    @property
    def intentos(self):
        return self._intentos

    def _evento(self, categoria):
        self._eventos.append(dict(version=1, simulacion=True,
            ordinal=len(self._eventos) + 1, categoria=categoria))

    def _rechazar(self, categoria):
        self._intentos += 1
        self._evento(categoria)
        raise IntentoProhibido('Intento prohibido durante el preflight simulado: ' + categoria)

    def _nombre(self, nombre):
        raiz = nombre.split('.')[0]
        if (raiz in RAICES_PROHIBIDAS or raiz in NATIVAS_NO_IMPORTABLES or nombre.startswith('configuracion.settings')
                or raiz in ('configuracion', 'pruebas_postgresql_aisladas', 'django_local')
                or (raiz not in sys.stdlib_module_names and nombre not in self._fuentes)):
            self._rechazar('importacion_no_aprobada')

    def _origen(self, nombre, origen):
        if origen in ('built-in', 'frozen'):
            return
        if nombre in self._fuentes:
            if origen is None or Path(origen) != self._fuentes[nombre][0]:
                self._rechazar('origen_sustituido')
            return
        if origen is None:
            self._rechazar('origen_ausente')
        ruta = Path(origen).resolve()
        if (not ruta.is_relative_to(Path(sys.base_prefix).resolve())
                or 'site-packages' in ruta.parts or 'dist-packages' in ruta.parts):
            self._rechazar('ruta_dependencia_no_aprobada')

    def _fuente(self, nombre):
        ruta, esperada = self._fuentes[nombre]
        for parte in (ruta, *ruta.parents):
            if parte.is_symlink() or getattr(parte, 'is_junction', lambda: False)():
                self._rechazar('fuente_redirigida')
        if ruta.resolve() != ruta:
            self._rechazar('ruta_fuente_incompatible')
        datos = ruta.read_bytes()
        if hashlib.sha256(datos).hexdigest() != esperada:
            self._rechazar('huella_fuente_alterada')
        return datos

    def _validar_fuentes(self):
        for nombre in self._fuentes:
            self._fuente(nombre)
            modulo = sys.modules.get(nombre)
            if modulo is not None:
                self._origen(nombre, getattr(getattr(modulo, '__spec__', None), 'origin', None))

    def __enter__(self):
        global _ACTIVA
        if self._usada or _ACTIVA:
            self._rechazar('guardia_reutilizada_o_anidada')
        self._usada = True
        self._stack = ExitStack()
        try:
            if _canonico(self._perfil) != _canonico(PERFIL):
                self._rechazar('perfil_contaminado')
            if any(type(k) is not str or k.upper().startswith(('DJANGO_', 'POSTGRES_', 'PG'))
                   or k.upper() in ('PYTHONPATH', 'PYTHONHOME') for k in self._entorno):
                self._rechazar('entorno_contaminado')
            if any(n.split('.')[0] in RAICES_PROHIBIDAS or n.startswith('configuracion.settings')
                   for n in sys.modules):
                self._rechazar('modulos_contaminados')
            importar, importar_modulo = builtins.__import__, importlib.import_module
            abrir, abrir_io = builtins.open, io.open

            def importacion(nombre, globals=None, locals=None, fromlist=(), level=0):
                completo = importlib.util.resolve_name('.'*level + nombre, globals['__package__']) if level else nombre
                self._nombre(completo)
                resultado = importar(nombre, globals, locals, fromlist, level)
                if getattr(resultado, '__spec__', None) is not None:
                    self._origen(resultado.__name__, resultado.__spec__.origin)
                return resultado

            def importar_por_nombre(nombre, package=None):
                completo = importlib.util.resolve_name(nombre, package) if nombre.startswith('.') else nombre
                self._nombre(completo)
                resultado = importar_modulo(nombre, package)
                self._origen(completo, resultado.__spec__.origin)
                return resultado

            def apertura(original, ruta, *args, **kwargs):
                if isinstance(ruta, (str, os.PathLike)) and Path(ruta).name.casefold() == '.env':
                    self._rechazar('lectura_env')
                return original(ruta, *args, **kwargs)

            for objeto, nombres in (
                (socket.socket, ('connect', 'connect_ex', 'bind', 'listen', 'send', 'sendall', 'sendto')),
                (socket, ('create_connection', 'create_server', 'getaddrinfo')),
                (subprocess, ('Popen', 'run', 'call', 'check_call', 'check_output')),
                (os, ('system', 'popen', 'startfile', 'fork', 'forkpty', 'posix_spawn', 'posix_spawnp')
                 + tuple(n for n in dir(os) if n.startswith(('exec', 'spawn'))))):
                for nombre in nombres:
                    if hasattr(objeto, nombre):
                        self._stack.enter_context(patch.object(objeto, nombre,
                            side_effect=lambda *a, **k: self._rechazar('red_o_proceso')))
            self._stack.enter_context(patch.object(builtins, '__import__', side_effect=importacion))
            self._stack.enter_context(patch.object(importlib, 'import_module', side_effect=importar_por_nombre))
            self._stack.enter_context(patch.object(builtins, 'open', side_effect=lambda r, *a, **k: apertura(abrir, r, *a, **k)))
            self._stack.enter_context(patch.object(io, 'open', side_effect=lambda r, *a, **k: apertura(abrir_io, r, *a, **k)))
            buscador = _Buscador(self)
            sys.meta_path.insert(0, buscador)
            self._stack.callback(sys.meta_path.remove, buscador)
            self._validar_fuentes()
            _ACTIVA = True
            self._evento('entrada')
            return self
        except BaseException as error:
            self.error_original = error
            self._stack.close()
            raise

    def instrumentar_superficies_simuladas(self, superficies):
        if not _ACTIVA or type(superficies) is not dict or set(superficies) != SUPERFICIES:
            self._rechazar('superficies_incompatibles')
        for categoria, par in superficies.items():
            if (type(par) is not tuple or len(par) != 2 or type(par[1]) is not str
                    or not getattr(par[0], '__module__', '').startswith('_zdb_simulado_')):
                self._rechazar('superficie_no_ficticia')
            self._stack.enter_context(patch.object(par[0], par[1],
                side_effect=lambda *a, _categoria=categoria, **k: self._rechazar(_categoria)))

    def importar_simulado(self, nombre, fuente):
        if (not _ACTIVA or type(nombre) is not str or type(fuente) is not str
                or nombre not in self._simuladas
                or hashlib.sha256(fuente.encode('utf-8')).hexdigest() != self._simuladas[nombre]):
            self._rechazar('fuente_simulada_no_aprobada')
        modulo = importlib.util.module_from_spec(importlib.util.spec_from_loader(
            nombre, _Cargador(fuente.encode('utf-8'), '<fuente-ficticia-aprobada>')))
        modulo.__spec__.loader.exec_module(modulo)
        return modulo

    def __exit__(self, tipo, error, traceback):
        global _ACTIVA
        incidente = None
        try:
            self._validar_fuentes()
        except BaseException as fallo:
            incidente = fallo
        finally:
            self._stack.close()
            _ACTIVA = False
        if error is not None:
            self.error_original = error
            self._evento('error_' + type(error).__name__)
            if self._intentos or incidente is not None:
                error.add_note('El preflight registró incidencias; se conserva el error original.')
            return False
        if incidente is not None:
            self.error_original = incidente
            raise incidente
        if self._intentos:
            error = IntentoProhibido('Hubo intentos prohibidos capturados internamente.')
            self.error_original = error
            raise error
        self._evento('salida_sin_intentos')
        return False


def main(argv=None):
    raise IntentoProhibido('R2-B2-A no habilita Django real ni un ejecutor operativo.')


if __name__ == '__main__':
    main()
