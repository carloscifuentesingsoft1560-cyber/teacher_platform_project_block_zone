"""Pruebas nuevas simuladas: no importan Django ni ejecutan MigrationLoader."""
import builtins
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))


@contextmanager
def arranque_seguro():
    """Barrera externa stdlib anterior incluso a la importación del módulo de barreras."""
    importar, abrir, abrir_io = builtins.__import__, builtins.open, io.open

    def importar_seguro(nombre, *args, **kwargs):
        if nombre.split('.')[0] in ('django', 'dotenv', 'psycopg', 'psycopg2', 'asyncpg', 'pg8000', 'sqlite3'):
            raise AssertionError('Django o controlador real prohibido')
        return importar(nombre, *args, **kwargs)

    def apertura(original, ruta, *args, **kwargs):
        if isinstance(ruta, (str, os.PathLike)) and Path(ruta).name.casefold() == '.env':
            raise AssertionError('Lectura .env prohibida en bootstrap')
        return original(ruta, *args, **kwargs)

    with ExitStack() as stack:
        for objeto, nombres in ((socket.socket, ('connect', 'connect_ex', 'bind', 'listen', 'send', 'sendall', 'sendto')),
                (socket, ('create_connection', 'create_server', 'getaddrinfo')),
                (subprocess, ('Popen', 'run', 'call', 'check_call', 'check_output')),
                (os, ('system', 'popen', 'startfile', 'fork', 'forkpty', 'posix_spawn', 'posix_spawnp')
                 + tuple(n for n in dir(os) if n.startswith(('exec', 'spawn'))))):
            for nombre in nombres:
                if hasattr(objeto, nombre):
                    stack.enter_context(patch.object(objeto, nombre, side_effect=AssertionError('Red/procesos reales prohibidos')))
        stack.enter_context(patch.object(builtins, '__import__', side_effect=importar_seguro))
        stack.enter_context(patch.object(builtins, 'open', side_effect=lambda r, *a, **k: apertura(abrir, r, *a, **k)))
        stack.enter_context(patch.object(io, 'open', side_effect=lambda r, *a, **k: apertura(abrir_io, r, *a, **k)))
        yield


with arranque_seguro():
    if any(n == 'django' or n.startswith('django.') for n in sys.modules):
        raise AssertionError('Entorno contaminado')
    if any(n in sys.modules for n in ('preflight_grafo_documental', 'barreras_preflight_grafo')):
        raise AssertionError('Se requieren primeras importaciones protegidas')
    import barreras_preflight_grafo as b
    RUTA_COMPARADOR = SCRIPTS / 'preflight_grafo_documental.py'
    APROBADAS = {'preflight_grafo_documental': dict(ruta=str(RUTA_COMPARADOR),
        sha256=hashlib.sha256(RUTA_COMPARADOR.read_bytes()).hexdigest())}
    with b.BarrerasPreflight(APROBADAS, entorno={}):
        import preflight_grafo_documental as p
    CONTRATO = json.loads((SCRIPTS / 'contrato_grafo_documental.json').read_text(encoding='utf-8'))


class ComparadorDocumental(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(arranque_seguro())
        self.stack.enter_context(b.BarrerasPreflight(APROBADAS, entorno={}))
        self.c = deepcopy(CONTRATO)
        self.g = deepcopy(CONTRATO['grafo'])
        self.f = deepcopy(CONTRATO['fuentes'])

    def comparar(self):
        return p.comparar_documental(self.c, self.g, self.f)

    def contrato_invalido(self):
        # La raíz de confianza ficticia se cambia solo para alcanzar validaciones estructurales.
        # La entrada documental pública mantiene su pin fijo y no acepta esta sustitución.
        return p.validar_contrato(self.c, p.huella(self.c))

    def test_01_referencia_estatica_completa(self):
        resultado = self.comparar()
        self.assertEqual((resultado['nodos'], resultado['aristas'], resultado['hojas']), (60, 110, 13))
        self.assertEqual(resultado['cierres'], dict(anterior=19, posterior=20, completo=60))
        self.assertIs(resultado['django_ejecutado'], False)
        self.assertIs(resultado['autoriza_ddl'], False)
        self.assertNotIn('django', sys.modules)

    def test_02_misma_cantidad_arista_alterada(self):
        arista = [['inscripciones', '0001_initial'], ['organizacion', '0002_catalogos_iniciales']]
        i = self.g['aristas'].index(arista)
        self.g['aristas'][i] = [['inscripciones', '0001_initial'], ['organizacion', '0001_initial']]
        self.assertEqual(len(self.g['aristas']), len(self.c['grafo']['aristas']))
        with self.assertRaisesRegex(p.RechazoGrafo, 'Aristas'):
            self.comparar()

    def test_03_nodo_faltante(self):
        self.g['nodos'].remove(['auditoria', '0001_initial'])
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_04_nodo_adicional(self):
        self.g['nodos'].append(['extra', '0001'])
        self.g['hojas'].append(['extra', '0001'])
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_05_mismo_numero_nodo_sustituido(self):
        i = self.g['nodos'].index(['sessions', '0001_initial'])
        self.g['nodos'][i] = ['sessions_ajena', '0001_initial']
        self.g['hojas'][self.g['hojas'].index(['sessions', '0001_initial'])] = self.g['nodos'][i]
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_06_dependencia_desconocida(self):
        self.g['aristas'].append([['cuentas', '0001_initial'], ['ajena', '0001']])
        with self.assertRaisesRegex(p.RechazoGrafo, 'desconocida'): self.comparar()

    def test_07_ciclo(self):
        self.g['aristas'].append([['cuentas', '0001_initial'], ['deportistas', '0001_initial']])
        with self.assertRaisesRegex(p.RechazoGrafo, 'Ciclo'): self.comparar()

    def test_08_conflicto_de_hojas(self):
        self.g['nodos'].append(['inscripciones', 'rama_ajena'])
        self.g['aristas'].append([['inscripciones', 'rama_ajena'], ['inscripciones', '0001_initial']])
        self.g['hojas'].append(['inscripciones', 'rama_ajena'])
        with self.assertRaisesRegex(p.RechazoGrafo, 'Conflicto'): self.comparar()

    def test_09_hoja_modificada(self):
        self.g['hojas'].pop()
        with self.assertRaisesRegex(p.RechazoGrafo, 'Hojas'): self.comparar()

    def test_10_cierre_incompleto(self):
        self.c['destinos']['anterior']['cierre'].pop()
        with self.assertRaisesRegex(p.RechazoGrafo, 'Cierre'): self.contrato_invalido()

    def test_11_contrato_alterado_no_se_autorregenera(self):
        self.c['interprete']['version'] = 'sustituido'
        with self.assertRaisesRegex(p.RechazoGrafo, 'referencia'): self.comparar()

    def test_12_tipos_estrictos(self):
        for valor in (True, 1.0, '1', None):
            self.c = deepcopy(CONTRATO)
            self.c['version'] = valor
            with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_13_nodos_duplicados(self):
        self.g['nodos'].append(self.g['nodos'][0])
        with self.assertRaisesRegex(p.RechazoGrafo, 'duplicado'): self.comparar()

    def test_14_aristas_duplicadas(self):
        self.g['aristas'].append(self.g['aristas'][0])
        with self.assertRaisesRegex(p.RechazoGrafo, 'duplicada'): self.comparar()

    def test_15_huella_incorrecta(self):
        self.f[0]['sha256'] = '0'*64
        with self.assertRaisesRegex(p.RechazoGrafo, 'Fuentes'): self.comparar()

    def test_16_fuente_faltante(self):
        self.f.pop()
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_17_fuente_sustituida_misma_cantidad(self):
        self.f[0]['ruta'] = 'ajena.py'
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_18_reemplazo_inesperado(self):
        self.g['reemplazos'] = [[['cuentas', '0001_initial'], ['cuentas', 'otra']]]
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_19_run_before_inesperado(self):
        self.g['run_before'] = [[['cuentas', '0001_initial'], ['deportistas', '0001_initial']]]
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_20_intercambiable_ausente(self):
        self.g['intercambiables'].pop()
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_21_destino_desconocido(self):
        self.c['destinos']['anterior']['semillas'].append(['ajena', '0001'])
        with self.assertRaisesRegex(p.RechazoGrafo, 'desconocido'): self.contrato_invalido()

    def test_22_destinos_historicos_incompatibles(self):
        self.c['destinos']['anterior'] = deepcopy(self.c['destinos']['completo'])
        with self.assertRaises(p.RechazoGrafo): self.contrato_invalido()

    def test_23_diferencia_documental_incompatible(self):
        self.c['destinos']['posterior'] = deepcopy(self.c['destinos']['anterior'])
        with self.assertRaisesRegex(p.RechazoGrafo, 'Diferencia'): self.contrato_invalido()

    def test_24_cierre_completo_incompatible(self):
        self.c['destinos']['completo'] = deepcopy(self.c['destinos']['posterior'])
        with self.assertRaises(p.RechazoGrafo): self.contrato_invalido()

    def test_25_ruta_de_fuente_con_retroceso(self):
        self.f[0]['ruta'] = '../ajena.py'
        with self.assertRaisesRegex(p.RechazoGrafo, 'Ruta'): self.comparar()

    def test_26_fuente_duplicada_sin_distinguir_mayusculas(self):
        self.f.append(dict(self.f[0], ruta=self.f[0]['ruta'].upper()))
        with self.assertRaisesRegex(p.RechazoGrafo, 'duplicada'): self.comparar()

    def test_27_campos_extra(self):
        self.g['sql'] = 'no ejecutar'
        with self.assertRaises(p.RechazoGrafo): self.comparar()

    def test_28_perfil_operativo_rechazado(self):
        self.c['perfil']['backend'] = 'django.db.backends.postgresql'
        with self.assertRaisesRegex(p.RechazoGrafo, 'Perfil'): self.contrato_invalido()

    def test_29_cli_no_habilitada(self):
        with self.assertRaises(p.RechazoGrafo): p.main(['--database', 'postgres'])

    def test_30_entradas_no_se_modifican(self):
        antes = p.huella([self.c, self.g, self.f])
        resultado = self.comparar()
        resultado['cierres'].clear()
        self.assertEqual(p.huella([self.c, self.g, self.f]), antes)
        self.assertTrue(self.comparar()['cierres'])

    def test_31_fuentes_referencia_y_paquetes_inspeccionados(self):
        self.assertEqual({x['nombre'] for x in self.c['paquetes']},
                         {'Django', 'djangorestframework', 'asgiref', 'sqlparse', 'tzdata'})
        self.assertEqual(self.c['pendientes_relaciones'], [])
        self.assertEqual(len(self.c['grafo']['intercambiables']), 19)
        self.assertEqual(p.huella(CONTRATO), p.HUELLA_CONTRATO_DOCUMENTAL)


if __name__ == '__main__':
    unittest.main(failfast=True, verbosity=2)
