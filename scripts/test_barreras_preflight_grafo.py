"""Pruebas de barreras con módulos/superficies ficticios. Nunca carga Django."""
from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
import socket
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from scripts.test_preflight_grafo_documental import APROBADAS, RUTA_COMPARADOR, arranque_seguro, b


class BarrerasSimuladas(unittest.TestCase):
    def setUp(self):
        self.bootstrap = arranque_seguro()
        self.bootstrap.__enter__()
        self.addCleanup(self.bootstrap.__exit__, None, None, None)

    def guardia(self, fuente=None, **cambios):
        datos = dict(fuentes_aprobadas=APROBADAS, entorno={})
        if fuente is not None:
            datos['fuentes_simuladas'] = {'_zdb_simulado_importacion': hashlib.sha256(fuente.encode('utf-8')).hexdigest()}
        datos.update(cambios)
        return b.BarrerasPreflight(**datos)

    def test_01_entrada_salida_y_restauracion(self):
        original = socket.create_connection
        g = self.guardia()
        with g:
            self.assertEqual(g.intentos, 0)
        self.assertIs(socket.create_connection, original)
        self.assertEqual([e['categoria'] for e in g.evidencias], ['entrada', 'salida_sin_intentos'])

    def test_02_django_y_drivers_rechazados(self):
        for nombre in ('django', 'django.db.migrations.loader', 'psycopg', 'psycopg2', 'dotenv', 'sqlite3'):
            g = self.guardia()
            with self.subTest(nombre=nombre), self.assertRaises(b.IntentoProhibido):
                with g: importlib.import_module(nombre)
            self.assertGreater(g.intentos, 0)
            self.assertNotIn(nombre, sys.modules)

        # Estos módulos nativos pueden estar precargados por stdlib; se rechaza su solicitud directa.
        for nombre in ('_socket', '_ssl', '_winapi'):
            with self.assertRaises(b.IntentoProhibido):
                with self.guardia(): importlib.import_module(nombre)

    def test_03_settings_operativos_rechazados(self):
        with self.assertRaises(b.IntentoProhibido):
            with self.guardia(): __import__('configuracion.settings')

    def test_04_lectura_env_rechazada_antes_de_abrir(self):
        with self.assertRaises(b.IntentoProhibido):
            with self.guardia(): Path('.ENV').read_text()

    def test_05_intento_de_red(self):
        with self.assertRaises(b.IntentoProhibido):
            with self.guardia(): socket.create_connection(('127.0.0.1', 5432))

    def test_06_intento_de_proceso(self):
        with self.assertRaises(b.IntentoProhibido):
            with self.guardia(): b.subprocess.Popen(['ficticio'])

    def test_07_intento_capturado_internamente_invalida_salida(self):
        g = self.guardia()
        with self.assertRaisesRegex(b.IntentoProhibido, 'capturados internamente'):
            with g:
                try: socket.create_connection(('127.0.0.1', 5432))
                except b.IntentoProhibido: pass
        self.assertEqual(g.intentos, 1)
        self.assertTrue(g.evidencias)

    def test_08_error_original_no_se_sustituye(self):
        original = RuntimeError('detalle-ficticio-privado')
        g = self.guardia()
        with self.assertRaises(RuntimeError) as capturado:
            with g:
                try: __import__('django')
                except b.IntentoProhibido: pass
                raise original
        self.assertIs(capturado.exception, original)
        self.assertIs(g.error_original, original)
        self.assertTrue(original.__notes__)
        self.assertNotIn('detalle-ficticio-privado', str(g.evidencias))

    def test_09_fallo_de_importacion_conservado(self):
        fuente = "raise ImportError('fallo ficticio de importación')"
        g = self.guardia(fuente)
        with self.assertRaises(ImportError) as capturado:
            with g: g.importar_simulado('_zdb_simulado_importacion', fuente)
        self.assertIs(g.error_original, capturado.exception)

    def test_10_importacion_con_intento_de_red(self):
        fuente = "import socket; socket.create_connection(('127.0.0.1', 5432))"
        g = self.guardia(fuente)
        with self.assertRaises(b.IntentoProhibido):
            with g: g.importar_simulado('_zdb_simulado_importacion', fuente)
        self.assertEqual(g.intentos, 1)

    def test_11_importacion_con_intento_de_proceso(self):
        fuente = "import subprocess; subprocess.run(['ficticio'])"
        g = self.guardia(fuente)
        with self.assertRaises(b.IntentoProhibido):
            with g: g.importar_simulado('_zdb_simulado_importacion', fuente)

    def test_12_importacion_que_oculta_intento(self):
        fuente = "import socket\ntry: socket.create_connection(('127.0.0.1',5432))\nexcept RuntimeError: pass"
        g = self.guardia(fuente)
        with self.assertRaisesRegex(b.IntentoProhibido, 'capturados internamente'):
            with g: g.importar_simulado('_zdb_simulado_importacion', fuente)

    def test_13_huella_de_fuente_incorrecta(self):
        fuentes = deepcopy(APROBADAS)
        fuentes['preflight_grafo_documental']['sha256'] = '0'*64
        g = self.guardia(fuentes_aprobadas=fuentes)
        original = socket.create_connection
        with self.assertRaises(b.IntentoProhibido):
            with g: pass
        self.assertIs(socket.create_connection, original)

    def test_14_entorno_precargado_contaminado(self):
        # Es un objeto vacío ficticio, no una importación de Django.
        with patch.dict(sys.modules, {'django.ficticio': ModuleType('django.ficticio')}):
            with self.assertRaises(b.IntentoProhibido):
                with self.guardia(): pass

    def test_15_settings_y_aliases_contaminados(self):
        for cambio in (dict(django_configurado=True), dict(aliases=['default', 'otra']),
                       dict(settings_module='configuracion.settings')):
            with self.assertRaises(b.IntentoProhibido):
                with self.guardia(perfil=dict(b.PERFIL, **cambio)): pass

    def test_16_variables_operativas_rechazadas(self):
        for nombre in ('DJANGO_SETTINGS_MODULE', 'POSTGRES_DB', 'PGSERVICE', 'PYTHONPATH'):
            with self.assertRaises(b.IntentoProhibido):
                with self.guardia(entorno={nombre: 'valor-ficticio'}): pass

    def test_17_importacion_no_aprobada(self):
        with self.assertRaises(b.IntentoProhibido):
            with self.guardia(): __import__('_zdb_ajeno_no_aprobado')

    def test_18_ruta_dependencia_no_aprobada(self):
        g = self.guardia()
        with self.assertRaises(b.IntentoProhibido):
            with g: g._origen('json', str(Path.cwd() / 'json.py'))

    def test_19_superficies_orm_sql_migraciones_y_recorder(self):
        llamadas = []
        clase = type('FalsoDjango', (), {'__module__': '_zdb_simulado_django',
            'accion': lambda self: llamadas.append('no debe ejecutarse')})
        objetos = {categoria: clase() for categoria in b.SUPERFICIES}
        g = self.guardia()
        with self.assertRaisesRegex(b.IntentoProhibido, 'capturados internamente'):
            with g:
                g.instrumentar_superficies_simuladas({k: (v, 'accion') for k, v in objetos.items()})
                for objeto in objetos.values():
                    try: objeto.accion()
                    except b.IntentoProhibido: pass
        self.assertEqual(llamadas, [])
        self.assertEqual(g.intentos, 7)

    def test_20_superficie_no_ficticia_rechazada(self):
        g = self.guardia()
        with self.assertRaises(b.IntentoProhibido):
            with g: g.instrumentar_superficies_simuladas({k: (object(), 'accion') for k in b.SUPERFICIES})

    def test_21_guardia_no_se_reutiliza(self):
        g = self.guardia()
        with g: pass
        with self.assertRaises(b.IntentoProhibido):
            with g: pass

    def test_22_huella_alterada_al_salir(self):
        original = RUTA_COMPARADOR.read_bytes()
        g = self.guardia()
        with self.assertRaises(b.IntentoProhibido):
            with patch.object(Path, 'read_bytes', side_effect=[original, b'alteracion ficticia']):
                with g: pass
        self.assertTrue(any(e['categoria'] == 'huella_fuente_alterada' for e in g.evidencias))

    def test_23_cargador_usa_fuente_verificada_sin_pyc(self):
        nombre = '_zdb_copia_comparador'
        fuentes = {nombre: APROBADAS['preflight_grafo_documental']}
        with patch.dict(sys.modules):
            with self.guardia(fuentes_aprobadas=fuentes):
                modulo = importlib.import_module(nombre)
                self.assertIsInstance(modulo.__spec__.loader, b._Cargador)
                self.assertEqual(modulo.HEAD_BASE, 'dc3ba22b88985ff454d7c2af1d6a2cd0551f70d5')

    def test_24_fuente_simulada_alterada(self):
        g = self.guardia('x=1')
        with self.assertRaises(b.IntentoProhibido):
            with g: g.importar_simulado('_zdb_simulado_importacion', 'x=2')

    def test_25_evidencias_son_copias(self):
        g = self.guardia()
        with g: pass
        eventos = g.evidencias
        eventos.clear()
        self.assertEqual(len(g.evidencias), 2)
        self.assertTrue(all(x['simulacion'] is True for x in g.evidencias))

    def test_26_cli_no_habilitada(self):
        with self.assertRaises(b.IntentoProhibido): b.main([])


if __name__ == '__main__':
    unittest.main(failfast=True, verbosity=2)
