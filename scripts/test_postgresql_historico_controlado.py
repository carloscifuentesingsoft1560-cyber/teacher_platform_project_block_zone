"""Pruebas R2-B1 nuevas: barreras antes de importar los módulos revisados."""
import ast
import builtins
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import replace
import importlib
import importlib.abc
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
PROHIBIDOS = frozenset(('django', 'dotenv', 'psycopg', 'psycopg2', 'asyncpg', 'pg8000'))


class RechazarImportacion(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in PROHIBIDOS:
            raise AssertionError('Importación operativa prohibida')


@contextmanager
def barreras():
    importar, abrir, abrir_io = builtins.__import__, builtins.open, io.open

    def importacion(nombre, *args, **kwargs):
        if nombre.split('.')[0] in PROHIBIDOS:
            raise AssertionError('Importación operativa prohibida')
        return importar(nombre, *args, **kwargs)

    def apertura(original, ruta, *args, **kwargs):
        if isinstance(ruta, (str, os.PathLike)) and Path(ruta).name == '.env':
            raise AssertionError('Lectura .env prohibida')
        return original(ruta, *args, **kwargs)

    with ExitStack() as stack:
        for objeto, nombres in (
                (socket.socket, ('connect', 'connect_ex', 'bind', 'listen', 'send', 'sendall', 'sendto')),
                (socket, ('create_connection', 'create_server', 'getaddrinfo')),
                (subprocess, ('Popen', 'run', 'call', 'check_call', 'check_output')),
                (os, ('system', 'popen', 'startfile', 'fork', 'forkpty', 'posix_spawn', 'posix_spawnp')
                 + tuple(n for n in dir(os) if n.startswith(('spawn', 'exec'))))):
            for nombre in nombres:
                if hasattr(objeto, nombre):
                    stack.enter_context(patch.object(objeto, nombre,
                        side_effect=AssertionError('Red/procesos prohibidos')))
        stack.enter_context(patch.object(builtins, '__import__', side_effect=importacion))
        stack.enter_context(patch.object(builtins, 'open', side_effect=lambda r, *a, **k: apertura(abrir, r, *a, **k)))
        stack.enter_context(patch.object(io, 'open', side_effect=lambda r, *a, **k: apertura(abrir_io, r, *a, **k)))
        filtro = RechazarImportacion()
        sys.meta_path.insert(0, filtro)
        stack.callback(sys.meta_path.remove, filtro)
        yield


with barreras():
    if any(n.split('.')[0] in PROHIBIDOS for n in sys.modules):
        raise AssertionError('Proceso contaminado por módulos operativos')
    if any(n in sys.modules for n in ('postgresql_historico_controlado', 'hijo_migracion_documental')):
        raise AssertionError('Se requiere la primera importación bajo barreras')
    import postgresql_historico_controlado as p
    import hijo_migracion_documental as h


class BaseSimulada(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(barreras())
        self.identidad = p.IdentidadSimulada(12345, '127.0.0.1', 55001,
            'C:/Temp/zdb_pg_ficticio', 'C:/Temp/zdb_pg_ficticio/cluster', 'b'*64)
        a, b, c = ['deportistas', '0001_initial'], ['deportistas', '0002_identificacion_documental'], ['inscripciones', '0001_initial']
        self.plan = dict(historial=[a, c], pasos=[dict(nodo=b, atras=False)], destino=[a, b, c])
        self.registro = self.nuevo()

    def nuevo(self, **cambios):
        datos = dict(identidad=self.identidad, codigo_sha256='a'*64,
                     plan=deepcopy(self.plan), inventario=['postgres', 'template0', 'template1'])
        datos.update(cambios)
        return p.RegistroDocumentalSimulado(**datos)

    def intercambio(self, registro=None, ahora=1):
        r = self.registro if registro is None else registro
        etapa = p.ETAPAS[r._indice]
        trama = r.emitir(etapa, r.contexto, ahora)
        respuesta = h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(trama, r.contexto, ahora)
        return r.confirmar(respuesta, r.contexto, ahora)

    def solicitud(self):
        return self.registro.emitir(p.ETAPAS[0], self.registro.contexto, 1)


class ContratosDocumentales(BaseSimulada):
    def test_01_recorrido_completo_solo_simulado(self):
        for etapa in p.ETAPAS:
            estado = self.intercambio()
            self.assertEqual(estado, 'cerrada_simulada' if etapa == p.ETAPAS[-1] else etapa)
        self.assertEqual(len(self.registro.evidencias), 14)
        self.assertTrue(self.registro.contexto_hijo()._cerrado)

    def test_02_registro_cerrado(self):
        self.assertEqual(set(p.ESCENARIOS), {'documental'})
        with self.assertRaises(TypeError):
            p.ESCENARIOS['otro'] = ()
        with self.assertRaises(p.BarreraProtocolo):
            self.nuevo(escenario='otro')

    def test_03_identidad_estricta(self):
        for cambios in (dict(pid=True), dict(puerto=55001.0), dict(pid=0),
                        dict(host='192.0.2.1'), dict(puerto=543), dict(sello='x')):
            with self.subTest(cambios=cambios), self.assertRaises(p.BarreraProtocolo):
                replace(self.identidad, **cambios)

    def test_04_directorio_inconsistente(self):
        for directorio in ('C:/Temp/otro/cluster', 'cluster', 'C:/Temp/zdb_pg_ficticio/../cluster'):
            with self.subTest(directorio=directorio), self.assertRaises(p.BarreraProtocolo):
                replace(self.identidad, directorio=directorio)

    def test_05_identidad_fijada_por_el_emisor(self):
        for campo, valor in (('pid', 99999), ('puerto', 55002), ('host', '192.0.2.1'),
                             ('directorio', 'C:/Temp/ajeno/cluster'), ('sello', 'c'*64)):
            r = self.nuevo()
            contexto = r.contexto
            contexto['identidad'][campo] = valor
            with self.subTest(campo=campo), self.assertRaises(p.BarreraProtocolo):
                r.emitir(p.ETAPAS[0], contexto, 1)
            self.assertEqual(r.estado, 'fallida')

    def test_06_base_y_usuario_no_son_seleccionables(self):
        for campo, valor in (('base', 'postgres'), ('base', 'template0'), ('base', 'ajena'),
                             ('usuario', 'postgres'), ('usuario', 'otro')):
            r = self.nuevo()
            contexto = r.contexto
            contexto[campo] = valor
            with self.subTest(campo=campo, valor=valor), self.assertRaises(p.BarreraProtocolo):
                r.emitir(p.ETAPAS[0], contexto, 1)

    def test_07_no_reutiliza_base_existente(self):
        with patch.object(p.secrets, 'token_hex', return_value='1'*32):
            with self.assertRaises(p.BarreraProtocolo):
                self.nuevo(inventario=['test_zdb_hist_' + '1'*32])

    def test_08_inventario_estricto(self):
        for inventario in (None, {}, ['postgres', 'postgres'], [True]):
            with self.subTest(inventario=inventario), self.assertRaises(p.BarreraProtocolo):
                self.nuevo(inventario=inventario)

    def test_09_contexto_de_otro_emisor(self):
        otro = self.nuevo()
        with self.assertRaises(p.BarreraProtocolo):
            otro.recibir_en_hijo(self.registro.contexto_hijo(), b'{}\n', otro.contexto, 1)
        self.assertFalse(self.registro.contexto_hijo()._cerrado)

    def test_10_contexto_no_expone_referencias_mutables(self):
        copia = self.registro.contexto
        copia['identidad']['puerto'] = 1
        self.assertEqual(self.registro.contexto['identidad']['puerto'], 55001)
        self.plan['pasos'].clear()
        self.intercambio()

    def test_11_plan_inverso(self):
        plan = deepcopy(self.plan)
        plan['pasos'][0]['atras'] = True
        with self.assertRaises(p.BarreraProtocolo):
            self.nuevo(plan=plan)

    def test_12_retroceso_indirecto(self):
        plan = deepcopy(self.plan)
        plan['destino'].remove(plan['historial'][0])
        with self.assertRaises(p.BarreraProtocolo):
            self.nuevo(plan=plan)

    def test_13_plan_incompleto_duplicado_o_ajeno(self):
        planes = []
        for modo in ('incompleto', 'duplicado', 'ajeno', 'opcion', 'historial'):
            plan = deepcopy(self.plan)
            if modo == 'incompleto': plan['pasos'] = []
            if modo == 'duplicado': plan['pasos'] *= 2
            if modo == 'ajeno': plan['pasos'][0]['nodo'] = ['otra', '0001']
            if modo == 'opcion': plan['pasos'][0]['fake'] = True
            if modo == 'historial': plan['historial'] *= 2
            planes.append(plan)
        for plan in planes:
            with self.subTest(plan=plan), self.assertRaises(p.BarreraProtocolo):
                self.nuevo(plan=plan)

    def test_14_plan_tipos_y_limites(self):
        for valor in (0, None, 'False'):
            plan = deepcopy(self.plan)
            plan['pasos'][0]['atras'] = valor
            with self.assertRaises(p.BarreraProtocolo):
                self.nuevo(plan=plan)
        plan = deepcopy(self.plan)
        plan['historial'] *= 257
        with self.assertRaises(p.BarreraProtocolo):
            self.nuevo(plan=plan)

    def test_15_codigo_o_contrato_cambiado(self):
        for campo in ('codigo_sha256', 'contrato_sha256'):
            r = self.nuevo()
            contexto = r.contexto
            contexto[campo] = 'c'*64
            with self.subTest(campo=campo), self.assertRaises(p.BarreraProtocolo):
                r.emitir(p.ETAPAS[0], contexto, 1)

    def test_16_etapa_fuera_de_orden(self):
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.emitir(p.ETAPAS[1], self.registro.contexto, 1)

    def test_17_solicitud_pendiente_no_se_duplica(self):
        self.solicitud()
        with self.assertRaises(p.BarreraProtocolo):
            self.solicitud()

    def test_18_plazo_y_reloj_estrictos(self):
        for cambios in (dict(inicio_ms=True), dict(plazo_ms=True), dict(plazo_ms=0), dict(plazo_ms=30001)):
            with self.assertRaises(p.BarreraProtocolo):
                self.nuevo(**cambios)
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.emitir(p.ETAPAS[0], self.registro.contexto, True)

    def test_19_timeout_simulado(self):
        with self.assertRaises(TimeoutError) as capturado:
            self.registro.emitir(p.ETAPAS[0], self.registro.contexto, p.MAX_PLAZO_MS)
        self.assertIs(self.registro.error_original, capturado.exception)
        self.assertTrue(self.registro.contexto_hijo()._cerrado)

    def test_20_reloj_no_puede_retroceder(self):
        self.intercambio(ahora=10)
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.emitir(p.ETAPAS[1], self.registro.contexto, 9)

    def test_21_nonce_repetido_por_el_generador(self):
        with patch.object(p.secrets, 'token_hex', return_value='2'*32):
            self.intercambio()
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.emitir(p.ETAPAS[1], self.registro.contexto, 1)

    def test_22_fallo_de_evidencia_invalida_contexto(self):
        self.registro.simular_fallo_evidencia()
        with self.assertRaises(OSError) as capturado:
            self.solicitud()
        self.assertIs(self.registro.error_original, capturado.exception)
        self.assertTrue(capturado.exception.__notes__)
        self.assertEqual(self.registro.estado, 'fallida')
        self.assertIsNone(self.registro._pendiente)

    def test_23_fallo_original_no_se_sustituye(self):
        original = RuntimeError('Detalle ficticio que no debe registrarse')
        self.registro.simular_fallo_evidencia()
        with self.assertRaises(RuntimeError) as capturado:
            self.registro.fallar(original)
        self.assertIs(capturado.exception, original)
        with self.assertRaises(RuntimeError) as repetido:
            self.registro.fallar(OSError('Otro fallo ficticio'))
        self.assertIs(repetido.exception, original)

    def test_24_evidencias_sin_secretos_ni_detalle_del_error(self):
        self.intercambio()
        original = RuntimeError('detalle-ficticio-privado')
        with self.assertRaises(RuntimeError):
            self.registro.fallar(original)
        texto = p.canonico(self.registro.evidencias)
        self.assertNotIn(self.registro._secreto.hex().encode('ascii'), texto)
        self.assertNotIn(b'detalle-ficticio-privado', texto)
        for evento in self.registro.evidencias:
            self.assertIs(evento['simulacion'], True)
        copia = self.registro.evidencias
        copia.clear()
        self.assertTrue(self.registro.evidencias)

    def test_25_cli_independiente_rechazada(self):
        for argumentos in ([], ['--database', 'postgres'], ['--escenario', 'documental']):
            with self.assertRaises(p.BarreraProtocolo):
                p.main(argumentos)

    def test_26_ast_sin_capacidades_operativas(self):
        permitidos = {'dataclasses', 'hashlib', 'hmac', 'json', 'math', 'pathlib', 're',
                      'secrets', 'threading', 'types', 'postgresql_historico_controlado'}
        prohibidas = {'open', 'exec', 'eval', 'compile', '__import__', 'connect', 'Popen',
                      'run', 'migrate', 'execute', 'read_text', 'read_bytes', 'write_text', 'write_bytes'}
        for nombre in ('postgresql_historico_controlado.py', 'hijo_migracion_documental.py'):
            arbol = ast.parse((SCRIPTS / nombre).read_text(encoding='utf-8'))
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    self.assertTrue(all(n.name.split('.')[0] in permitidos for n in nodo.names))
                if isinstance(nodo, ast.ImportFrom):
                    self.assertIn(nodo.module.split('.')[0], permitidos)
                if isinstance(nodo, ast.Call):
                    funcion = nodo.func
                    nombre_llamada = funcion.id if isinstance(funcion, ast.Name) else getattr(funcion, 'attr', '')
                    self.assertNotIn(nombre_llamada, prohibidas)

    def test_27_barreras_importacion_y_env(self):
        for nombre in PROHIBIDOS:
            with self.assertRaises(AssertionError):
                __import__(nombre)
            with self.assertRaises(AssertionError):
                importlib.import_module(nombre)
            self.assertNotIn(nombre, sys.modules)
        with self.assertRaises(AssertionError):
            Path('.env').read_text()

    def test_28_barreras_red_y_procesos(self):
        for llamada in (lambda: socket.create_connection(('127.0.0.1', 55001)),
                        lambda: subprocess.Popen(['ficticio']), lambda: subprocess.run(['ficticio']),
                        lambda: os.system('ficticio')):
            with self.assertRaisesRegex(AssertionError, 'Red/procesos'):
                llamada()

    def test_29_plan_interno_alterado(self):
        plan = deepcopy(self.plan)
        plan['pasos'].clear()
        self.registro._plan = p.canonico(plan)
        with self.assertRaises(p.BarreraProtocolo):
            self.solicitud()

    def test_30_identidad_inmutable_y_plazo_no_renovable(self):
        with self.assertRaises(AttributeError):
            self.identidad.pid = 99999
        r = self.nuevo(plazo_ms=10)
        self.intercambio(r, ahora=9)
        with self.assertRaises(TimeoutError):
            r.emitir(p.ETAPAS[1], r.contexto, 10)

    def cerrar_y_capturar(self):
        respuesta = None
        for etapa in p.ETAPAS:
            trama = self.registro.emitir(etapa, self.registro.contexto, 1)
            respuesta = h.HijoDocumentalSimulado(self.registro.contexto_hijo()).recibir(
                trama, self.registro.contexto, 1)
            self.registro.confirmar(respuesta, self.registro.contexto, 1)
        return respuesta, self.instantanea_cierre()

    def instantanea_cierre(self):
        r = self.registro
        return dict(estado=r.estado, evidencias=r.evidencias, usados=frozenset(r._usados),
            vistos=frozenset(r.contexto_hijo()._vistos), pendiente=deepcopy(r._pendiente),
            indice=r._indice, ultimo=r._ultimo, limite=r._limite,
            cerrado=r.contexto_hijo()._cerrado, error=r.error_original, contexto=r.contexto)

    def test_31_emision_posterior_no_modifica_cierre(self):
        _, anterior = self.cerrar_y_capturar()
        for etapa, observacion, reloj in ((p.ETAPAS[0], self.registro.contexto, 2),
                                         ('ajena', {}, 30000), (None, None, True)):
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.emitir(etapa, observacion, reloj)
            self.assertEqual(self.instantanea_cierre(), anterior)

    def test_32_confirmacion_posterior_no_modifica_cierre(self):
        respuesta, anterior = self.cerrar_y_capturar()
        for trama in (respuesta, b'', b'{', b'{}\n'):
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.confirmar(trama, self.registro.contexto, 30000)
            self.assertEqual(self.instantanea_cierre(), anterior)

    def test_33_fallar_despues_del_cierre_no_registra_error(self):
        _, anterior = self.cerrar_y_capturar()
        for error in (RuntimeError('Fallo ficticio tardío'), OSError('Otro fallo ficticio')):
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.fallar(error)
            self.assertEqual(self.instantanea_cierre(), anterior)
        self.assertIsNone(self.registro.error_original)

    def test_34_rechazo_posterior_no_intenta_escribir_evidencia(self):
        respuesta, anterior = self.cerrar_y_capturar()
        with patch.object(self.registro, '_evidencia', side_effect=AssertionError('No escribir')) as escritura:
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.emitir(p.ETAPAS[0], {}, 1)
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.confirmar(respuesta, {}, 1)
            with self.assertRaises(p.BarreraProtocolo):
                self.registro.fallar(RuntimeError('Tardío'))
            escritura.assert_not_called()
        self.assertEqual(self.instantanea_cierre(), anterior)

    def test_35_comprobar_cierre_no_altera_reloj_ni_contexto(self):
        _, anterior = self.cerrar_y_capturar()
        with self.assertRaises(p.BarreraProtocolo):
            self.registro._comprobar({}, 30000)
        self.assertEqual(self.instantanea_cierre(), anterior)


if __name__ == '__main__':
    unittest.main(failfast=True, verbosity=2)
