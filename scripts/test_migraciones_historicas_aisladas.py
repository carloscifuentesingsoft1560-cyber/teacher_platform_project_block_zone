"""Barreras R2-A: solo stdlib, archivos nuevos y un proceso ficticio."""
import ast
from contextlib import ExitStack, contextmanager
import builtins
import importlib
import importlib.abc
import importlib.util
import os
from copy import deepcopy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'backend'))

PROHIBIDOS = frozenset(('django', 'dotenv', 'psycopg', 'psycopg2'))


class RechazarImportacion(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in PROHIBIDOS:
            raise AssertionError('Importación operativa prohibida: ' + fullname)


@contextmanager
def barreras():
    importar = builtins.__import__

    def importacion(nombre, *args, **kwargs):
        if nombre.split('.')[0] in PROHIBIDOS:
            raise AssertionError('Settings/conexiones/.env prohibidos')
        return importar(nombre, *args, **kwargs)

    with ExitStack() as stack:
        for propietario, metodos in (
                (socket.socket, ('connect', 'connect_ex', 'bind', 'listen', 'sendto', 'send', 'sendall')),
                (socket, ('create_connection', 'create_server', 'getaddrinfo')),
                (subprocess, ('Popen', 'run', 'call', 'check_call', 'check_output')),
                (os, ('system', 'popen', 'startfile', 'fork', 'forkpty', 'posix_spawn', 'posix_spawnp')
                 + tuple(n for n in dir(os) if n.startswith(('spawn', 'exec'))))):
            for metodo in metodos:
                if hasattr(propietario, metodo):
                    stack.enter_context(patch.object(propietario, metodo,
                        side_effect=AssertionError('Red/procesos prohibidos')))
        stack.enter_context(patch.object(builtins, '__import__', side_effect=importacion))
        filtro = RechazarImportacion()
        sys.meta_path.insert(0, filtro)
        stack.callback(sys.meta_path.remove, filtro)
        yield


# La stdlib anterior prepara las barreras; ningún módulo del proyecto la precede.
with barreras():
    if any(n.split('.')[0] in PROHIBIDOS for n in sys.modules):
        raise AssertionError('Proceso de pruebas contaminado antes de importar el proyecto')
    if any(n in sys.modules for n in ('configuracion',
            'configuracion.aislamiento_pruebas', 'configuracion.migraciones_historicas_aisladas',
            'pruebas_postgresql_aisladas', 'casos_migraciones_historicas')):
        raise AssertionError('Se requieren importaciones iniciales sin caché del proyecto')
    from configuracion import migraciones_historicas_aisladas as h
    from configuracion.aislamiento_pruebas import CLAVE_FICTICIA
    from pruebas_postgresql_aisladas import entorno_aislado
    from casos_migraciones_historicas import procesar_solicitud, main

A = ('deportistas', '0001_initial')
B = ('deportistas', '0002_identificacion_documental')
C = ('inscripciones', '0001_initial')


class BarrerasHistoricas(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(barreras())
        self.temporal = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='zdb_r2a_sim_'))).resolve()
        self.carpeta = self.temporal / 'zdb_pg_simulado'
        self.carpeta.mkdir()
        self.cluster = self.carpeta / 'cluster'
        self.cluster.mkdir()
        for nombre in ('tmp', 'archivos_privados', 'pgconf', 'home'):
            (self.carpeta / nombre).mkdir()
        for nombre in ('pgpass-vacio', 'pgservice-vacio'):
            (self.carpeta / nombre).write_bytes(b'')
        (self.cluster / 'postmaster.pid').write_text(f'12345\n{self.cluster}\n0\n55001\nx\n127.0.0.1\n', encoding='utf-8')
        self.entorno = entorno_aislado({}, self.cluster, 55001, self.temporal,
            self.temporal / 'paquetes', self.temporal / 'binarios')
        self.identidad = dict(pid=12345, cluster=str(self.cluster), host='127.0.0.1', puerto=55001,
            paquetes=self.entorno['ZDB_PAQUETES_PYTHON'], binarios=self.entorno['ZDB_LIBPQ_DIR'])
        self.archivo_identidad = self.carpeta / 'identidad.json'
        self.escribir_identidad()
        self.proceso = SimpleNamespace(pid=12345, poll=Mock(return_value=None))
        self.registro = self.nuevo_registro()
        self.contrato = h.ContratoPlan(((A, ()), (B, (A,)), (C, (A,))), (A, C), (A, B, C))

    def escribir_identidad(self):
        self.archivo_identidad.write_text(json.dumps(self.identidad), encoding='utf-8')

    def nuevo_registro(self, **cambios):
        datos = dict(entorno=self.entorno, repositorio=RAIZ, proceso=self.proceso,
                     base_principal='test_zdb_fase3_abcdef012345')
        datos.update(cambios)
        return h.RegistroEjecucion(**datos)

    def manifiesto(self, **cambios):
        datos = dict(caso='documental', contrato=self.contrato, bases_existentes=['postgres', 'template0', 'template1'])
        datos.update(cambios)
        return self.registro.reservar(**datos)

    def mensaje(self, manifiesto):
        return dict(version=1, operacion='validar_plan_simulado', manifiesto=manifiesto,
                    historial=[A, C], pasos=[dict(nodo=B, atras=False)])

    def test_01_registro_cerrado_ocho_clases(self):
        self.assertEqual(len(h.ESCENARIOS), 8)
        self.assertEqual(h.escenario('documental').clase, 'MigracionDocumentalPreservaDatos')
        with self.assertRaises(TypeError):
            h.ESCENARIOS['otro'] = h.ESCENARIOS['documental']

    def test_02_escenario_desconocido(self):
        for caso in ('otro', '../documental', None):
            with self.assertRaises(h.BarreraHistorica):
                self.manifiesto(caso=caso)

    def test_03_manifiesto_valido_solo_simulado(self):
        m = self.manifiesto()
        self.assertEqual(self.registro.validar(m), self.contrato)
        self.assertEqual(procesar_solicitud(self.registro, json.dumps(self.mensaje(m))), 'contrato_simulado_validado')

    def test_04_manifiesto_alterado_por_campo(self):
        original = self.manifiesto()
        for clave in original['payload']:
            m = deepcopy(original)
            m['payload'][clave] = 'alterado'
            with self.subTest(campo=clave), self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)

    def test_05_firma_falsa(self):
        m = self.manifiesto()
        m['firma'] = '0' * 64
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)

    def test_06_otra_ejecucion_no_es_propietaria(self):
        otro = self.nuevo_registro()
        with self.assertRaises(h.BarreraHistorica):
            otro.validar(self.manifiesto())

    def test_07_replay(self):
        m = self.manifiesto()
        self.registro.consumir(m, [A,C], [dict(nodo=B, atras=False)])
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)

    def test_08_manifiesto_ausente_o_campos_extra(self):
        for m in (None, {}, dict(self.manifiesto(), fake=True)):
            with self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)

    def test_09_base_administrativa_y_operativa(self):
        for base in ('postgres', 'template0', 'template1', 'zona_bloque', 'default', 'test_zdb_fase3_../x'):
            with self.assertRaises(h.BarreraHistorica):
                self.nuevo_registro(base_principal=base)
            m = self.manifiesto()
            m['payload']['base'] = base
            with self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)

    def test_10_nombre_preexistente_no_reutilizado(self):
        fijo = SimpleNamespace(hex='1'*32)
        base = 'test_zdb_hist_' + self.registro._id[:12] + '_' + fijo.hex[:12]
        with patch.object(h, 'uuid4', return_value=fijo), self.assertRaises(h.BarreraHistorica):
            self.manifiesto(bases_existentes=[base])

    def test_11_no_admite_base_elegida_por_cliente(self):
        mensaje = self.mensaje(self.manifiesto())
        mensaje['base'] = 'otra'
        with self.assertRaises(h.BarreraHistorica):
            procesar_solicitud(self.registro, json.dumps(mensaje))

    def test_12_plan_ascendente(self):
        self.contrato.validar([A,C], [dict(nodo=B, atras=False)])

    def test_13_operacion_inversa(self):
        with self.assertRaises(h.BarreraHistorica):
            self.contrato.validar([A,C], [dict(nodo=B, atras=True)])

    def test_14_dependencia_exige_retroceso_indirecto(self):
        with self.assertRaises(h.BarreraHistorica):
            h.ContratoPlan(((A,()), (B,(A,)), (C,(A,))), (A,C), (A,B))

    def test_15_dependencia_no_aplicada(self):
        contrato = h.ContratoPlan(((A,()), (B,(A,))), (), (A,B))
        with self.assertRaises(h.BarreraHistorica):
            contrato.validar([], [dict(nodo=B, atras=False), dict(nodo=A, atras=False)])

    def test_16_historial_inesperado(self):
        for historial in ([], [A], [A,C,C], [A,B,C]):
            with self.assertRaises(h.BarreraHistorica):
                self.contrato.validar(historial, [dict(nodo=B, atras=False)])

    def test_17_plan_incompleto_repetido_o_arbitrario(self):
        for pasos in ([], [dict(nodo=C, atras=False)], [dict(nodo=('otra','0001'), atras=False)],
                      [dict(nodo=B, atras=False), dict(nodo=B, atras=False)]):
            with self.assertRaises(h.BarreraHistorica):
                self.contrato.validar([A,C], pasos)

    def test_18_grafo_circular_o_dependencia_ausente(self):
        for grafo in (((A,(B,)),(B,(A,))), ((A,(B,)),)):
            with self.assertRaises(h.BarreraHistorica):
                h.ContratoPlan(grafo, (), ())

    def test_19_pid_del_objeto_distinto(self):
        self.proceso.pid = 99999
        with self.assertRaises(h.BarreraHistorica):
            self.manifiesto()

    def test_20_proceso_finalizado(self):
        self.proceso.poll.return_value = 1
        with self.assertRaises(h.BarreraHistorica):
            self.manifiesto()

    def test_21_pid_en_archivo_distinto(self):
        archivo = self.cluster / 'postmaster.pid'
        archivo.write_text(archivo.read_text(encoding='utf-8').replace('12345','98765'), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.manifiesto()

    def test_22_host_y_puerto_manipulados(self):
        for clave, valor in (('host','192.0.2.1'), ('puerto',55002)):
            original = dict(self.identidad)
            self.identidad[clave] = valor
            self.escribir_identidad()
            with self.assertRaises(ValueError):
                self.manifiesto()
            self.identidad = original
            self.escribir_identidad()

    def test_23_directorio_cluster_incompatible(self):
        self.entorno['ZDB_PG_TEST_CLUSTER'] = str(self.temporal / 'otro')
        with self.assertRaises(ValueError):
            self.nuevo_registro()

    def test_24_identidad_ausente(self):
        # Archivo creado exclusivamente por esta fixture.
        self.archivo_identidad.unlink()
        with self.assertRaises(FileNotFoundError):
            self.manifiesto()

    def test_25_manifiesto_cambiado_aun_si_semantica_igual(self):
        self.archivo_identidad.write_text(json.dumps(self.identidad, indent=2), encoding='utf-8')
        with self.assertRaises(h.BarreraHistorica):
            self.manifiesto()

    def test_26_credenciales_y_overrides_rechazados(self):
        for clave, valor in (('POSTGRES_PASSWORD','real'), ('PGSERVICE','operativo'),
                             ('DJANGO_SETTINGS_MODULE','configuracion.settings'), ('TOKEN','secreto-ficticio'),
                             ('PYTHONPATH','otro'), ('DJANGO_SECRET_KEY','otra')):
            with self.assertRaises(ValueError):
                self.nuevo_registro(entorno=dict(self.entorno, **{clave:valor}))

    def test_27_libpq_privado_no_vacio(self):
        (self.carpeta / 'pgpass-vacio').write_text('dato-ficticio', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.manifiesto()

    def test_28_invocacion_independiente(self):
        for args in ([], ['--escenario','documental'], ['--database','postgres'], ['--fake']):
            with self.assertRaises(h.BarreraHistorica):
                main(args)
        with self.assertRaises(h.BarreraHistorica):
            procesar_solicitud(None, '{}')

    def test_29_fake_triggers_e_historial_prohibidos(self):
        for operacion in ('migrar','--fake','disable_triggers','editar_django_migrations'):
            mensaje = self.mensaje(self.manifiesto())
            mensaje['operacion'] = operacion
            with self.assertRaises(h.BarreraHistorica):
                procesar_solicitud(self.registro,json.dumps(mensaje))
        with self.assertRaises(h.BarreraHistorica):
            self.contrato.validar([A,C], [dict(nodo=B, atras=False, fake=True)])

    def test_30_json_duplicado_o_excesivo(self):
        for texto in ('{"x":1,"x":2}', 'x'*65537, '{', '{"x":NaN}'):
            with self.assertRaises(h.BarreraHistorica):
                h.leer_json(texto)

    def test_31_fallo_creacion_simulado(self):
        original = RuntimeError('Creación ficticia fallida')
        with self.assertRaises(RuntimeError) as capturado:
            self.registro.registrar_fallo(self.manifiesto(), 'creacion_simulada', original)
        self.assertIs(capturado.exception, original)

    def test_32_fallo_ejecucion_simulado(self):
        original = RuntimeError('Ejecución ficticia fallida')
        with self.assertRaises(RuntimeError) as capturado:
            self.registro.registrar_fallo(self.manifiesto(), 'ejecucion_simulada', original)
        self.assertIs(capturado.exception, original)

    def test_33_timeout_simulado_no_es_exito(self):
        original = TimeoutError('Timeout ficticio')
        with self.assertRaises(TimeoutError) as capturado:
            self.registro.registrar_fallo(self.manifiesto(), 'timeout_simulado', original)
        self.assertIs(capturado.exception, original)

    def test_34_fallo_evidencia_no_oculta_original(self):
        manifiesto = self.manifiesto()
        original = RuntimeError('Diagnóstico original ficticio')
        with patch.object(self.registro, 'evidencia', side_effect=OSError('Disco ficticio')), self.assertRaises(RuntimeError) as capturado:
            self.registro.registrar_fallo(manifiesto, 'ejecucion_simulada', original)
        self.assertIs(capturado.exception, original)
        self.assertTrue(original.__notes__)
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(manifiesto)

    def test_35_recurso_ajeno_no_se_modifica(self):
        ajeno = self.temporal / 'evidencia_ajena.json'
        ajeno.write_bytes(b'no tocar')
        self.registro._directorio = self.temporal
        with self.assertRaises(h.BarreraHistorica):
            self.manifiesto()
        self.assertEqual(ajeno.read_bytes(), b'no tocar')

    def test_36_evidencia_estructurada_siempre_simulada(self):
        m = self.manifiesto()
        self.registro.consumir(m,[A,C],[dict(nodo=B,atras=False)])
        archivos = list(self.registro._directorio.glob('*.json'))
        self.assertEqual(len(archivos),2)
        for archivo in archivos:
            evento = json.loads(archivo.read_text(encoding='ascii'))
            self.assertIs(evento['simulacion'],True)
            self.assertNotIn('secreto',evento)

    def test_37_no_sobrescribe_evidencia(self):
        fijo = SimpleNamespace(hex='2'*32)
        with patch.object(h,'uuid4',return_value=fijo):
            self.registro.evidencia('reserva',{})
            with self.assertRaises(FileExistsError):
                self.registro.evidencia('reserva',{})

    def test_38_no_hay_capacidad_de_conexion_o_proceso(self):
        for ruta in (RAIZ/'backend/configuracion/migraciones_historicas_aisladas.py',RAIZ/'scripts/casos_migraciones_historicas.py'):
            arbol=ast.parse(ruta.read_text(encoding='utf-8'))
            for n in ast.walk(arbol):
                if isinstance(n,ast.Import):
                    self.assertFalse({'django','dotenv','psycopg','psycopg2','socket','subprocess'} & {a.name.split('.')[0] for a in n.names})
                if isinstance(n,ast.ImportFrom):
                    self.assertNotIn((n.module or '').split('.')[0],('django','dotenv','psycopg','psycopg2','socket','subprocess'))
        self.assertNotIn('dotenv',sys.modules)
        self.assertNotIn('django',sys.modules)
        self.assertNotIn('psycopg',sys.modules)

    def test_39_reversiones_no_se_declaran_cubiertas(self):
        self.assertTrue(h.ESCENARIOS['seguridad_ascensos'].reversion_pendiente)
        self.assertTrue(h.ESCENARIOS['movimientos'].reversion_pendiente)

    def test_40_entero_a_booleano(self):
        m = self.manifiesto()
        m['payload']['version'] = True
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)

    def test_41_entero_a_decimal(self):
        original = self.manifiesto()
        for campo in ('version', 'pid', 'puerto'):
            m = deepcopy(original)
            m['payload'][campo] = float(m['payload'][campo])
            with self.subTest(campo=campo), self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)

    def test_42_tipos_exactos_todos_los_campos(self):
        original = self.manifiesto()
        for campo, valor in original['payload'].items():
            for otro in (None, True, 1, 1.0, '1', [], {}):
                if type(otro) is type(valor):
                    continue
                m = deepcopy(original)
                m['payload'][campo] = otro
                with self.subTest(campo=campo, tipo=type(otro)), self.assertRaises(h.BarreraHistorica):
                    self.registro.validar(m)

    def test_43_payload_extra_o_ausente(self):
        original = self.manifiesto()
        for campo in original['payload']:
            m = deepcopy(original)
            del m['payload'][campo]
            with self.subTest(campo=campo), self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)
        m = deepcopy(original)
        m['payload']['extra'] = None
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)

    def test_44_hmac_se_recalcula_sobre_payload_recibido(self):
        m = self.manifiesto()
        m['payload']['host'] = '192.0.2.1'
        real = h.hmac.new
        with patch.object(h.hmac, 'new', wraps=real) as calculo:
            with self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)
            calculo.assert_called_once_with(self.registro._secreto,
                h.canonico(m['payload']), h.hashlib.sha256)

    def test_45_firma_no_sustituye_propiedad(self):
        m = self.manifiesto()
        m['payload']['host'] = '192.0.2.1'
        m['firma'] = h.hmac.new(self.registro._secreto,
            h.canonico(m['payload']), h.hashlib.sha256).hexdigest()
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)
        for firma in (None, True, '', 'é'*64, '0'*64):
            m = self.manifiesto()
            m['firma'] = firma
            with self.subTest(firma=firma), self.assertRaises(h.BarreraHistorica):
                self.registro.validar(m)

    def test_46_importacion_con_efectos_secundarios(self):
        # Loader en memoria: reproduce efectos durante exec_module sin escribir módulos.
        class ModuloHostil(importlib.abc.MetaPathFinder, importlib.abc.Loader):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == '_r2a_hostil':
                    return importlib.util.spec_from_loader(fullname, self)

            def create_module(self, spec):
                return None

            def exec_module(self, module):
                exec(self.fuente, module.__dict__)

        filtro = ModuloHostil()
        sys.meta_path.append(filtro)
        try:
            for fuente in ("import socket; socket.create_connection(('127.0.0.1', 55001))",
                           "import socket\nwith socket.socket() as s: s.connect(('127.0.0.1', 55001))",
                           "import subprocess; subprocess.Popen(['proceso-ficticio'])",
                           "import subprocess; subprocess.run(['proceso-ficticio'])",
                           "import os; os.system('proceso-ficticio')"):
                filtro.fuente = fuente
                with self.subTest(fuente=fuente), self.assertRaisesRegex(AssertionError, 'Red/procesos'):
                    importlib.import_module('_r2a_hostil')
                self.assertNotIn('_r2a_hostil', sys.modules)
        finally:
            sys.meta_path.remove(filtro)

    def test_47_importaciones_prohibidas(self):
        for nombre in PROHIBIDOS:
            with self.subTest(nombre=nombre):
                with self.assertRaises(AssertionError):
                    __import__(nombre)
                with self.assertRaises(AssertionError):
                    importlib.import_module(nombre)
                self.assertNotIn(nombre, sys.modules)

    def test_48_fallo_consumo_no_permite_replay(self):
        m = self.manifiesto()
        with patch.object(self.registro, 'evidencia', side_effect=OSError('Disco ficticio')):
            with self.assertRaises(OSError):
                self.registro.consumir(m, [A,C], [dict(nodo=B, atras=False)])
        with self.assertRaises(h.BarreraHistorica):
            self.registro.validar(m)


if __name__ == '__main__':
    unittest.main(failfast=True, verbosity=2)
