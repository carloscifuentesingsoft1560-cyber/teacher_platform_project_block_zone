"""Pruebas de barreras del ejecutor sin abrir PostgreSQL ni cargar .env."""
import contextlib
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pruebas_postgresql_aisladas as runner


class BarrerasAislamiento(unittest.TestCase):
    def test_argumentos_permitidos(self):
        opciones = runner.argumentos(['--failfast', '--verbosity', '2'])
        self.assertTrue(opciones.failfast)
        self.assertEqual(opciones.verbosity, 2)

    def test_no_admite_settings_base_o_keepdb(self):
        for args in [['--settings=configuracion.settings'], ['--keepdb'], ['--database=default']]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.argumentos(args)

    def test_rechaza_generacion_antes_de_crear_cluster(self):
        with patch.dict(os.environ, {'ZDB_GENERAR_ASCENSOS': '1'}), patch.object(runner.tempfile, 'mkdtemp') as crear:
            with self.assertRaisesRegex(RuntimeError, 'no genera migraciones'):
                runner.ejecutar([])
            crear.assert_not_called()

    def test_entorno_descarta_libpq_y_reemplaza_base(self):
        entorno = runner.entorno_aislado({'PGSERVICE': 'operativo', 'PGOPTIONS': 'peligroso',
            'PGHOST': 'remoto', 'PGPASSFILE': 'privado', 'DJANGO_SETTINGS_MODULE': 'configuracion.settings',
            'POSTGRES_DB': 'zona_bloque', 'POSTGRES_PORT': '5432',
            'PYTHONPATH': 'operativo', 'PYTHONHOME': 'operativo', 'DJANGO_DEBUG': 'True',
            'ZDB_PAQUETES_PYTHON': 'no_verificado', 'PATH': 'operativo', 'TOKEN': 'secreto'},
            Path('cluster'), 55001, Path(tempfile.gettempdir()), Path('paquetes'), Path('binarios'))
        self.assertEqual({k: v for k, v in entorno.items() if k.startswith('PG')},
                         runner.variables_libpq(Path('cluster').resolve().parent))
        self.assertEqual(entorno['DJANGO_SETTINGS_MODULE'], 'configuracion.settings_pruebas_postgresql')
        for nombre in ('PYTHONPATH', 'PYTHONHOME', 'TOKEN', 'DJANGO_DEBUG'):
            self.assertNotIn(nombre, entorno)
        self.assertEqual(entorno['POSTGRES_DB'], 'postgres')
        self.assertEqual(entorno['POSTGRES_PORT'], '55001')
        self.assertEqual(entorno['POSTGRES_HOST'], '127.0.0.1')

    def test_settings_rechaza_ejecucion_directa_sin_cargar_entorno(self):
        raiz = Path(__file__).resolve().parent.parent
        codigo = '''
import importlib.util, pathlib, site, os, sys
site.addsitedir(os.getenv('ZDB_PAQUETES_PYTHON',str(pathlib.Path('.venv-local/Lib/site-packages').resolve())))
sys.path.insert(0, str(pathlib.Path('backend').resolve()))
from django.core.exceptions import ImproperlyConfigured
spec=importlib.util.spec_from_file_location('configuracion.settings_pruebas_postgresql', 'backend/configuracion/settings_pruebas_postgresql.py')
modulo=importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(modulo)
except ImproperlyConfigured as error:
    assert 'no aislada' in str(error)
else:
    raise AssertionError('Se aceptó una ejecución sin clúster')
'''
        entorno = os.environ.copy()
        entorno.pop('ZDB_PG_TEST_CLUSTER', None)
        entorno['PYTHONDONTWRITEBYTECODE'] = '1'
        resultado = subprocess.run([sys.executable, '-c', codigo], cwd=raiz, env=entorno,
                                  capture_output=True, text=True, timeout=20)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_etiquetas_no_permiten_argumentos_o_rutas(self):
        for etiqueta in ('../operativo', '--settings=x', 'os.system', 'cuentas;otra'):
            with self.subTest(etiqueta=etiqueta), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.argumentos(['--etiqueta', etiqueta])

    def test_clasificacion_concurrencia_no_acepta_fallos_infraestructura(self):
        # Ejecutar solo la función pura extraída por AST: no importar modelos ni Django.
        archivo = runner.RAIZ / 'backend/cuentas/tests/test_competencias_b1.py'
        arbol = ast.parse(archivo.read_text(encoding='utf-8'))
        funcion = next(n for n in arbol.body if isinstance(n, ast.FunctionDef) and n.name == 'rechazo_version_esperado')
        espacio = {}
        exec(compile(ast.Module(body=[funcion], type_ignores=[]), str(archivo), 'exec'), espacio)
        clasificar = espacio['rechazo_version_esperado']
        for codigo in ('55P03', '40P01', '08006', '57014', None):
            causa = RuntimeError('fallo ficticio')
            causa.sqlstate = codigo
            error = RuntimeError('envoltura'); error.__cause__ = causa
            self.assertFalse(clasificar(error))
        causa = RuntimeError('Version B1 obsoleta, rama o propuesta retirada\nCONTEXT: fixture')
        causa.sqlstate = '23514'
        error = RuntimeError('envoltura'); error.__cause__ = causa
        self.assertTrue(clasificar(error))
        causa = RuntimeError('única')
        causa.sqlstate = '23505'
        causa.diag = SimpleNamespace(constraint_name='competencia_evento_numero')
        error.__cause__ = causa
        self.assertTrue(clasificar(error))
        causa.diag.constraint_name = 'otra_restriccion'
        self.assertFalse(clasificar(error))


class ArchivosAislados(unittest.TestCase):
    """Solo archivos ficticios en un temporal nuevo; nunca arranca procesos PG."""
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory(prefix='zdb_pg_')
        self.addCleanup(self.temporal.cleanup)
        self.carpeta = Path(self.temporal.name).resolve()
        self.datos = self.carpeta / 'cluster'
        self.datos.mkdir()
        for nombre in ('tmp', 'archivos_privados', 'pgconf', 'home'):
            (self.carpeta / nombre).mkdir()
        for nombre in ('pgpass-vacio', 'pgservice-vacio'):
            (self.carpeta / nombre).write_bytes(b'')
        # Simulación de identidad de archivos: no es un servidor ni un PID comprobado.
        (self.datos / 'postmaster.pid').write_text(f'12345\n{self.datos}\n0\n55001\n\n127.0.0.1\n', encoding='utf-8')
        self.paquetes = Path(os.environ.get('ZDB_PAQUETES_PYTHON', runner.RAIZ / '.venv-local/Lib/site-packages')).resolve()
        self.binarios = Path('C:/Program Files/PostgreSQL/17/bin').resolve()
        self.entorno = runner.entorno_aislado(os.environ, self.datos, 55001,
            self.carpeta.parent, self.paquetes, self.binarios)
        (self.carpeta / 'identidad.json').write_text(json.dumps(dict(pid=12345, puerto=55001,
            host='127.0.0.1', cluster=str(self.datos), paquetes=str(self.paquetes), binarios=str(self.binarios))), encoding='utf-8')

    def validar(self):
        from configuracion.aislamiento_pruebas import validar_entorno
        return validar_entorno(self.entorno, runner.RAIZ)

    def test_contexto_ficticio_coherente(self):
        self.assertEqual(self.validar(), (self.carpeta, 55001))

    def test_rechaza_credenciales_y_overrides_agregados(self):
        for clave, valor in [('PGSERVICE', 'operativo'), ('PGOPTIONS', '-c x=y'),
                             ('POSTGRES_DB', 'zona_bloque'), ('POSTGRES_HOST', 'remoto'),
                             ('POSTGRES_PORT', '5432'), ('PYTHONPATH', 'otro'),
                             ('DJANGO_DEBUG', 'True'), ('TEMP', str(runner.RAIZ)),
                             ('ZDB_PAQUETES_PYTHON', str(runner.RAIZ))]:
            with self.subTest(clave=clave), patch.dict(self.entorno, {clave: valor}), self.assertRaises(ValueError):
                self.validar()

    def test_rechaza_archivos_libpq_con_contenido(self):
        (self.carpeta / 'pgpass-vacio').write_text('ficticio', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.validar()

    def test_identidad_rechaza_pid_directorio_host_y_puerto(self):
        from configuracion.aislamiento_pruebas import verificar_identidad
        casos = [(999, 55001, str(self.datos), '127.0.0.1', 55001),
                 (12345, 5432, str(self.datos), '127.0.0.1', 5432),
                 (12345, 55001, str(runner.RAIZ), '127.0.0.1', 55001),
                 (12345, 55001, str(self.datos), '0.0.0.0', 55001),
                 (12345, 55001, str(self.datos), '127.0.0.1', 5432)]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                verificar_identidad(self.datos, *caso)

    def test_rechaza_destinos_dentro_del_repositorio(self):
        from configuracion.aislamiento_pruebas import validar_raiz
        with self.assertRaises(ValueError):
            validar_raiz(runner.RAIZ / 'respaldos/zdb_pg_ficticio', runner.RAIZ / 'respaldos', runner.RAIZ)

    def test_settings_validos_no_leen_dotenv_ni_abren_conexion(self):
        codigo = r'''
import builtins, pathlib, os, sys, site
site.addsitedir(os.environ['ZDB_PAQUETES_PYTHON'])
sys.path.insert(0, sys.argv[1])
original_import = builtins.__import__
def importar(nombre, *args, **kwargs):
    if nombre == 'dotenv' or nombre.startswith('dotenv.'):
        raise AssertionError('dotenv prohibido')
    return original_import(nombre, *args, **kwargs)
builtins.__import__ = importar
from unittest.mock import patch
from django.db.backends.base.base import BaseDatabaseWrapper
with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=AssertionError('Conexion prohibida')):
    import configuracion.settings_pruebas_postgresql as s
    assert s.DATABASES['default']['NAME'] == 'postgres'
    assert s.DATABASES['default']['HOST'] == '127.0.0.1'
    assert s.DATABASES['default']['PORT'] == '55001'
    assert s.ZDB_ARCHIVOS_PRIVADOS == pathlib.Path(os.environ['ZDB_PG_TEST_RUN']) / 'archivos_privados'
    assert 'dotenv' not in sys.modules
'''
        resultado = subprocess.run([sys.executable, '-I', '-B', '-c', codigo, str(runner.RAIZ / 'backend')],
            cwd=self.carpeta, env=self.entorno, capture_output=True, text=True, timeout=20)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_fallo_initdb_simulado_solo_genera_evidencia_nueva(self):
        # No ejecuta initdb: subprocess.run está sustituido y Popen está prohibido.
        with patch.object(runner.tempfile, 'gettempdir', return_value=str(self.carpeta)), \
             patch.dict(os.environ, {'ZDB_PAQUETES_PYTHON': str(self.paquetes),
                                     'ZDB_LIBPQ_DIR': str(self.binarios), 'ZDB_GENERAR_ASCENSOS': ''}), \
             patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'fallo ficticio', b'')) as ejecutar, \
             patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('Proceso prohibido')) as iniciar, \
             patch.object(runner.Path, 'is_file', return_value=True), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'inicializar'):
                runner.ejecutar(['--etiqueta', 'cuentas.tests.test_competencias_b1'])
            self.assertEqual(ejecutar.call_count, 1)
            iniciar.assert_not_called()
        nuevas = list(self.carpeta.glob('zdb_pg_*'))
        self.assertEqual(len(nuevas), 1)
        self.assertTrue((nuevas[0] / 'resultado.json').is_file())
        self.assertTrue((nuevas[0] / 'initdb.log').is_file())


class DetencionSimulada(unittest.TestCase):
    setUp = ArchivosAislados.setUp

    def proceso(self):
        propio = Mock(pid=12345)
        propio.poll.return_value = None
        propio.wait.return_value = 0
        propio.terminate.side_effect = lambda: setattr(propio.poll, 'return_value', 0)
        return propio

    def detener(self, propio, **cambios):
        contexto = dict(servidor=propio, datos=self.datos, puerto=55001,
                        carpeta=self.carpeta, binarios=self.binarios, entorno=self.entorno, oculto={})
        contexto.update(cambios)
        return runner.detener_cluster_propio(**contexto)

    def test_identidad_correcta_permite_cierre_controlado(self):
        propio = self.proceso()

        def cierre(*args, **kwargs):
            propio.poll.return_value = 0
            return subprocess.CompletedProcess(args[0], 0, b'', b'')

        with patch.object(runner.subprocess, 'run', side_effect=cierre) as solicitar:
            estado = self.detener(propio)
        solicitar.assert_called_once()
        self.assertEqual(solicitar.call_args.args[0], [str(self.binarios / 'pg_ctl.exe'),
            '-D', str(self.datos), '-m', 'fast', '-w', 'stop'])
        self.assertTrue(estado['identidad_revalidada'])
        self.assertTrue(estado['detenido'])
        self.assertEqual(estado['incidentes'], [])
        propio.terminate.assert_not_called()

    def test_pid_distinto_del_hijo_prohibe_pg_ctl_aunque_manifiesto_coincida(self):
        propio = self.proceso()
        propio.pid = 99999  # Disco y manifiesto coinciden entre sí, pero no con el hijo.
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar:
            estado = self.detener(propio)
        solicitar.assert_not_called()
        propio.terminate.assert_called_once_with()
        self.assertFalse(estado['pg_ctl_solicitado'])
        self.assertTrue(estado['detenido'])
        self.assertTrue(estado['incidentes'])

    def test_directorio_distinto_prohibe_pg_ctl(self):
        propio = self.proceso()
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar:
            estado = self.detener(propio, datos=self.carpeta / 'otro-directorio')
        solicitar.assert_not_called()
        self.assertFalse(estado['pg_ctl_solicitado'])
        propio.terminate.assert_called_once_with()

    def test_directorio_distinto_en_pid_prohibe_pg_ctl(self):
        propio = self.proceso()
        (self.datos / 'postmaster.pid').write_text(f'12345\n{self.carpeta}\n0\n55001\n\n127.0.0.1\n', encoding='utf-8')
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar:
            estado = self.detener(propio)
        solicitar.assert_not_called()
        self.assertFalse(estado['identidad_revalidada'])
        propio.terminate.assert_called_once_with()

    def test_identidad_no_verificable_prohibe_pg_ctl(self):
        propio = self.proceso()
        (self.datos / 'postmaster.pid').unlink()  # Solo archivo ficticio de este test.
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar:
            estado = self.detener(propio)
        solicitar.assert_not_called()
        self.assertTrue(estado['incidentes'])
        propio.terminate.assert_called_once_with()

    def test_fallo_verificacion_no_envia_senales_a_pid_ajeno(self):
        propio = self.proceso()
        with patch.object(runner, 'verificar_identidad', side_effect=ValueError('Identidad ambigua')), \
             patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar, \
             patch.object(runner.os, 'kill', side_effect=AssertionError('PID arbitrario prohibido')) as matar:
            estado = self.detener(propio)
        solicitar.assert_not_called()
        matar.assert_not_called()
        propio.terminate.assert_called_once_with()
        self.assertIn('Identidad ambigua', estado['incidentes'][0])

    def test_fallo_pg_ctl_solo_termina_objeto_propio_y_registra_incidente(self):
        propio = self.proceso()
        with patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired('pg_ctl simulado', 45)):
            estado = self.detener(propio)
        self.assertTrue(estado['pg_ctl_solicitado'])
        propio.terminate.assert_called_once_with()
        self.assertTrue(estado['detenido'])
        self.assertIn('TimeoutExpired', estado['incidentes'][0])

    def test_hijo_ya_terminado_no_solicita_cierre(self):
        propio = self.proceso()
        propio.poll.return_value = 0
        with patch.object(runner.subprocess, 'run', side_effect=AssertionError('pg_ctl prohibido')) as solicitar:
            estado = self.detener(propio)
        solicitar.assert_not_called()
        propio.terminate.assert_not_called()
        self.assertTrue(estado['detenido'])

    def test_error_original_se_conserva_con_fallo_de_limpieza_y_evidencia(self):
        propio = self.proceso()
        propio.terminate.side_effect = PermissionError('Terminación propia ficticia fallida')
        original = RuntimeError('Fallo original de identificación simulado')

        def simular(comando, **kwargs):
            nombre = Path(comando[0]).name
            if nombre == 'initdb.exe' or nombre == 'pg_isready.exe':
                return subprocess.CompletedProcess(comando, 0, b'', b'')
            if nombre == 'psql.exe':
                raise original
            raise AssertionError('Nunca ejecutar pg_ctl ni otros procesos')

        errores = io.StringIO()
        with patch.object(runner.tempfile, 'gettempdir', return_value=str(self.carpeta)), \
             patch.dict(os.environ, {'ZDB_PAQUETES_PYTHON': str(self.paquetes),
                                     'ZDB_LIBPQ_DIR': str(self.binarios), 'ZDB_GENERAR_ASCENSOS': ''}), \
             patch.object(runner.Path, 'is_file', return_value=True), \
             patch.object(runner.subprocess, 'Popen', return_value=propio), \
             patch.object(runner.subprocess, 'run', side_effect=simular) as procesos, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errores):
            with self.assertRaises(RuntimeError) as capturado:
                runner.ejecutar(['--etiqueta', 'cuentas.tests.test_competencias_b1'])
        self.assertIs(capturado.exception, original)
        self.assertFalse(any(Path(c.args[0][0]).name == 'pg_ctl.exe' for c in procesos.call_args_list))
        evidencia = next(self.carpeta.glob('zdb_pg_*/resultado.json'))
        resultado = json.loads(evidencia.read_text(encoding='utf-8'))
        self.assertIn(str(original), resultado['error'])
        self.assertFalse(resultado['detenido'])
        self.assertFalse(resultado['limpieza']['pg_ctl_solicitado'])
        self.assertIn('PermissionError', str(resultado['limpieza']['incidentes']))
        self.assertIn('Incidente de limpieza', errores.getvalue())

    def test_fallo_guardando_evidencia_no_oculta_error_original(self):
        original = RuntimeError('Fallo original ficticio de initdb')
        escribir = Path.write_text

        def guardar(ruta, *args, **kwargs):
            if ruta.name == 'resultado.json':
                raise OSError('Disco ficticio no disponible')
            return escribir(ruta, *args, **kwargs)

        errores = io.StringIO()
        with patch.object(runner.tempfile, 'gettempdir', return_value=str(self.carpeta)), \
             patch.dict(os.environ, {'ZDB_PAQUETES_PYTHON': str(self.paquetes),
                                     'ZDB_LIBPQ_DIR': str(self.binarios), 'ZDB_GENERAR_ASCENSOS': ''}), \
             patch.object(runner.Path, 'is_file', return_value=True), \
             patch.object(runner.Path, 'write_text', new=guardar), \
             patch.object(runner.subprocess, 'run', side_effect=original), \
             patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('Proceso prohibido')) as iniciar, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errores):
            with self.assertRaises(RuntimeError) as capturado:
                runner.ejecutar(['--etiqueta', 'cuentas.tests.test_competencias_b1'])
        self.assertIs(capturado.exception, original)
        iniciar.assert_not_called()
        self.assertIn('No se pudo guardar resultado.json', errores.getvalue())
        self.assertIn('Disco ficticio no disponible', errores.getvalue())


if __name__ == '__main__':
    unittest.main()
