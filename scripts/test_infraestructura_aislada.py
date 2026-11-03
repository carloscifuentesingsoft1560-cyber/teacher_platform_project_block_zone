"""Pruebas de barreras del ejecutor sin abrir PostgreSQL ni cargar .env."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

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
            'POSTGRES_DB': 'zona_bloque', 'POSTGRES_PORT': '5432'}, Path('cluster'), 55001)
        self.assertFalse(any(k.startswith('PG') for k in entorno))
        self.assertNotIn('DJANGO_SETTINGS_MODULE', entorno)
        self.assertEqual(entorno['POSTGRES_DB'], 'postgres')
        self.assertEqual(entorno['POSTGRES_PORT'], '55001')
        self.assertEqual(entorno['POSTGRES_HOST'], '127.0.0.1')

    def test_settings_rechaza_ejecucion_directa_sin_cargar_entorno(self):
        raiz = Path(__file__).resolve().parent.parent
        codigo = '''
import importlib.util, pathlib, site, os
site.addsitedir(os.getenv('ZDB_PAQUETES_PYTHON',str(pathlib.Path('.venv-local/Lib/site-packages').resolve())))
from django.core.exceptions import ImproperlyConfigured
spec=importlib.util.spec_from_file_location('prueba_settings', 'backend/configuracion/settings_pruebas_postgresql.py')
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


if __name__ == '__main__':
    unittest.main()
