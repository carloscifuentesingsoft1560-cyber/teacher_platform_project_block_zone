"""Pruebas nuevas del receptor simulado; no inicia el bootstrap Django futuro."""
from copy import deepcopy
import importlib.abc
import importlib.util
import sys
import unittest

from scripts.test_postgresql_historico_controlado import BaseSimulada, barreras

with barreras():
    import postgresql_historico_controlado as p
    import hijo_migracion_documental as h


class ReceptorDocumental(BaseSimulada):
    def hijo(self):
        return h.HijoDocumentalSimulado(self.registro.contexto_hijo())

    def test_01_sin_contexto_privado(self):
        for contexto in (None, {}, object()):
            with self.assertRaises(p.BarreraProtocolo):
                h.HijoDocumentalSimulado(contexto)
        falso = p.ContextoHijoSimulado(self.registro, object())
        with self.assertRaises(p.BarreraProtocolo):
            h.HijoDocumentalSimulado(falso)

    def test_02_cli_no_se_habilita(self):
        for args in ([], ['--host', '127.0.0.1'], ['--fake']):
            with self.assertRaises(p.BarreraProtocolo):
                h.main(args)

    def test_03_solicitud_consumida_una_vez(self):
        trama = self.solicitud()
        hijo = self.hijo()
        hijo.recibir(trama, self.registro.contexto, 1)
        with self.assertRaises(p.BarreraProtocolo):
            hijo.recibir(trama, self.registro.contexto, 1)

    def test_04_respuesta_consumida_una_vez(self):
        respuesta = self.hijo().recibir(self.solicitud(), self.registro.contexto, 1)
        self.registro.confirmar(respuesta, self.registro.contexto, 1)
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.confirmar(respuesta, self.registro.contexto, 1)

    def test_05_hmac_invalido(self):
        m = p.leer_trama(self.solicitud())
        m['firma'] = '0'*64
        with self.assertRaises(p.BarreraProtocolo):
            self.hijo().recibir(p.canonico(m)+b'\n', self.registro.contexto, 1)

    def test_06_contenido_modificado_con_firma_anterior(self):
        for campo, valor in (('etapa', p.ETAPAS[1]), ('emisor', 'hijo'),
                             ('nonce', '3'*32), ('protocolo', 'r2a'), ('modo', 'operativo')):
            r = self.nuevo()
            m = p.leer_trama(r.emitir(p.ETAPAS[0], r.contexto, 1))
            m['payload'][campo] = valor
            with self.subTest(campo=campo), self.assertRaises(p.BarreraProtocolo):
                h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(p.canonico(m)+b'\n', r.contexto, 1)

    def test_07_tipos_estrictos_en_campos_enteros(self):
        for campo in ('version', 'secuencia'):
            for valor in (True, 1.0, '1', None):
                r = self.nuevo()
                m = p.leer_trama(r.emitir(p.ETAPAS[0], r.contexto, 1))
                m['payload'][campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises(p.BarreraProtocolo):
                    h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(p.canonico(m)+b'\n', r.contexto, 1)

    def test_08_tipos_anidados_aun_con_firma_valida(self):
        for campo, valor in (('puerto', 55001.0), ('pid', 12345.0)):
            r = self.nuevo()
            m = p.leer_trama(r.emitir(p.ETAPAS[0], r.contexto, 1))
            m['payload']['contexto']['identidad'][campo] = valor
            trama = r._firmar(m['payload'])
            with self.assertRaises(p.BarreraProtocolo):
                h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(trama, r.contexto, 1)

    def test_09_esquema_extra_y_ausente(self):
        for modo in ('extra', 'ausente', 'exterior'):
            r = self.nuevo()
            m = p.leer_trama(r.emitir(p.ETAPAS[0], r.contexto, 1))
            if modo == 'extra': m['payload']['host'] = 'otro'
            if modo == 'ausente': del m['payload']['nonce']
            if modo == 'exterior': m['extra'] = True
            with self.subTest(modo=modo), self.assertRaises(p.BarreraProtocolo):
                h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(p.canonico(m)+b'\n', r.contexto, 1)

    def test_10_firma_valida_no_acredita_propiedad_ajena(self):
        trama = self.solicitud()
        otro = self.nuevo()
        with self.assertRaises(p.BarreraProtocolo):
            h.HijoDocumentalSimulado(otro.contexto_hijo()).recibir(trama, otro.contexto, 1)

    def test_11_eof_y_truncamiento(self):
        for trama, error in ((b'', EOFError), (b'{', p.TramaIncompleta), (b'{}', p.TramaIncompleta)):
            r = self.nuevo()
            with self.assertRaises(error) as capturado:
                h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(trama, r.contexto, 1)
            self.assertIs(r.error_original, capturado.exception)
            self.assertTrue(r.contexto_hijo()._cerrado)

    def test_12_tamano_json_duplicados_y_no_finitos(self):
        for trama in (b'x'*65537, b'{"x":1,"x":2}\n', b'{"x":NaN}\n',
                      b'{}\n{}\n', b'\xff\n', b'{\n'):
            r = self.nuevo()
            with self.assertRaises(p.BarreraProtocolo):
                h.HijoDocumentalSimulado(r.contexto_hijo()).recibir(trama, r.contexto, 1)

    def test_13_timeout_del_hijo(self):
        trama = self.solicitud()
        with self.assertRaises(TimeoutError):
            self.hijo().recibir(trama, self.registro.contexto, 30000)

    def test_14_timeout_esperando_respuesta(self):
        respuesta = self.hijo().recibir(self.solicitud(), self.registro.contexto, 1)
        with self.assertRaises(TimeoutError):
            self.registro.confirmar(respuesta, self.registro.contexto, 30000)

    def test_15_error_original_del_hijo(self):
        original = RuntimeError('Fallo ficticio del hijo')
        self.registro.simular_fallo_evidencia()
        with self.assertRaises(RuntimeError) as capturado:
            self.hijo().comunicar_error(original)
        self.assertIs(capturado.exception, original)
        self.assertTrue(original.__notes__)

    def test_16_configuracion_inerte_unico_default(self):
        propuesta = self.hijo().describir_configuracion()
        self.assertEqual(propuesta['alias'], 'default')
        self.assertEqual(propuesta['base'], self.registro.contexto['base'])
        self.assertEqual(propuesta['otros_aliases'], [])
        self.assertFalse(propuesta['cargar_dotenv'])
        self.assertFalse(propuesta['grafo_real_validado'])
        self.assertNotIn('django', sys.modules)

    def test_17_configuracion_rechaza_overrides_y_aliases(self):
        original = self.hijo().describir_configuracion()
        for campo, valor in (('alias', 'otra'), ('base', 'postgres'), ('usuario', 'postgres'),
                             ('host', '192.0.2.1'), ('puerto', 5432), ('otros_aliases', ['otra']),
                             ('cargar_dotenv', True), ('conexiones_iniciadas', True),
                             ('django_iniciado', True), ('grafo_real_validado', True)):
            propuesta = dict(original, **{campo: valor})
            with self.subTest(campo=campo), self.assertRaises(p.BarreraProtocolo):
                self.hijo().describir_configuracion(propuesta)
        with self.assertRaises(p.BarreraProtocolo):
            self.hijo().describir_configuracion(dict(original, PASSWORD='ficticia'))

    def test_18_configuracion_tipos_exactos(self):
        original = self.hijo().describir_configuracion()
        for campo, valor in (('puerto', 55001.0), ('cargar_dotenv', 0), ('otros_aliases', ())):
            with self.assertRaises(p.BarreraProtocolo):
                self.hijo().describir_configuracion(dict(original, **{campo: valor}))

    def test_19_cierre_y_fallo_no_afectan_otro_registro(self):
        otro = self.nuevo()
        for _ in p.ETAPAS:
            self.intercambio()
        with self.assertRaises(p.BarreraProtocolo):
            self.hijo()
        self.assertFalse(otro.contexto_hijo()._cerrado)
        self.intercambio(otro)

    def test_20_fallo_evidencia_confirmacion_no_admite_replay(self):
        respuesta = self.hijo().recibir(self.solicitud(), self.registro.contexto, 1)
        self.registro.simular_fallo_evidencia()
        with self.assertRaises(OSError) as capturado:
            self.registro.confirmar(respuesta, self.registro.contexto, 1)
        self.assertIn(p.leer_trama(respuesta)['payload']['nonce'], self.registro._usados)
        with self.assertRaises(OSError) as repetido:
            self.registro.confirmar(respuesta, self.registro.contexto, 1)
        self.assertIs(repetido.exception, capturado.exception)

    def test_21_respuesta_firmada_modificada(self):
        respuesta = self.hijo().recibir(self.solicitud(), self.registro.contexto, 1)
        payload = p.leer_trama(respuesta)['payload']
        payload['resultado'] = 'ejecucion_real'
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.confirmar(self.registro._firmar(payload), self.registro.contexto, 1)

    def test_22_efectos_secundarios_durante_importacion(self):
        class Cargador(importlib.abc.MetaPathFinder, importlib.abc.Loader):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == '_r2b1_hostil':
                    return importlib.util.spec_from_loader(fullname, self)

            def create_module(self, spec):
                return None

            def exec_module(self, module):
                exec(self.fuente, module.__dict__)

        cargador = Cargador()
        sys.meta_path.append(cargador)
        try:
            for fuente in ("import socket; socket.create_connection(('127.0.0.1', 55001))",
                           "import subprocess; subprocess.Popen(['ficticio'])",
                           "import django", "import dotenv", "import psycopg"):
                cargador.fuente = fuente
                with self.subTest(fuente=fuente), self.assertRaises(AssertionError):
                    __import__('_r2b1_hostil')
                self.assertNotIn('_r2b1_hostil', sys.modules)
        finally:
            sys.meta_path.remove(cargador)

    def test_23_respuesta_no_se_fabrica_sin_recepcion(self):
        solicitud = p.leer_trama(self.solicitud())['payload']
        respuesta = dict(solicitud, emisor='hijo', solicitud_sha256=p.huella(solicitud),
                         resultado='validacion_simulada')
        with self.assertRaises(p.BarreraProtocolo):
            self.registro.confirmar(self.registro._firmar(respuesta), self.registro.contexto, 1)

    def test_24_fallo_cierre_simulado_no_es_exito(self):
        for _ in p.ETAPAS[:-1]:
            self.intercambio()
        trama = self.registro.emitir(p.ETAPAS[-1], self.registro.contexto, 1)
        respuesta = self.hijo().recibir(trama, self.registro.contexto, 1)
        self.registro.simular_fallo_evidencia()
        with self.assertRaises(OSError):
            self.registro.confirmar(respuesta, self.registro.contexto, 1)
        self.assertEqual(self.registro.estado, 'fallida')
        self.assertTrue(self.registro.contexto_hijo()._cerrado)

    def test_25_constantes_no_finitas_en_lector(self):
        for numero in ('NaN', 'Infinity', '-Infinity'):
            for plantilla in ('%s', '{"numero":%s}', '{"anidado":[{"numero":%s}]}'):
                trama = (plantilla % numero).encode('ascii') + b'\n'
                with self.subTest(numero=numero, plantilla=plantilla), self.assertRaises(p.BarreraProtocolo):
                    p.leer_trama(trama)

    def test_26_desbordamientos_decimales_en_lector(self):
        for numero in ('1e400', '-1e400', '9.9e9999', '-9.9e9999', '1.7976931348623159e308'):
            for plantilla in ('%s', '{"numero":%s}', '{"anidado":[{"numero":%s}]}'):
                trama = (plantilla % numero).encode('ascii') + b'\n'
                with self.subTest(numero=numero, plantilla=plantilla), self.assertRaises(p.BarreraProtocolo):
                    p.leer_trama(trama)

    def test_27_numeros_finitos_conservan_valor_y_tipo(self):
        for numero, esperado in (('1', 1), ('0', 0), ('1.0', 1.0), ('-0.0', -0.0),
                                 ('1.25', 1.25), ('1e3', 1000.0), ('1e-300', 1e-300),
                                 ('1.7976931348623157e308', 1.7976931348623157e308)):
            with self.subTest(numero=numero):
                obtenido = p.leer_trama(('{"n":' + numero + '}\n').encode('ascii'))['n']
                self.assertEqual(obtenido, esperado)
                self.assertIs(type(obtenido), type(esperado))
                self.assertEqual(p.canonico(obtenido), p.canonico(esperado))

    def test_28_desbordamiento_en_solicitud_conserva_error_terminal(self):
        self.solicitud()
        with self.assertRaises(p.BarreraProtocolo) as capturado:
            self.hijo().recibir(b'{"payload":{"contexto":{"puerto":1e400}}}\n',
                               self.registro.contexto, 1)
        self.assertIs(self.registro.error_original, capturado.exception)
        self.assertEqual(self.registro.estado, 'fallida')
        self.assertTrue(self.registro.contexto_hijo()._cerrado)

    def test_29_recepcion_posterior_no_modifica_cierre(self):
        hijo = self.hijo()
        ultima = None
        for etapa in p.ETAPAS:
            ultima = self.registro.emitir(etapa, self.registro.contexto, 1)
            respuesta = hijo.recibir(ultima, self.registro.contexto, 1)
            self.registro.confirmar(respuesta, self.registro.contexto, 1)
        anterior = (self.registro.evidencias, frozenset(self.registro._usados),
                    frozenset(self.registro.contexto_hijo()._vistos), self.registro._indice,
                    self.registro._ultimo, self.registro._limite, self.registro.contexto)
        for trama in (ultima, b'', b'{'):
            with self.assertRaises(p.BarreraProtocolo):
                hijo.recibir(trama, {}, 30000)
            self.assertEqual(self.registro.estado, 'cerrada_simulada')
            self.assertIsNone(self.registro.error_original)
            self.assertTrue(self.registro.contexto_hijo()._cerrado)
            self.assertEqual((self.registro.evidencias, frozenset(self.registro._usados),
                frozenset(self.registro.contexto_hijo()._vistos), self.registro._indice,
                self.registro._ultimo, self.registro._limite, self.registro.contexto), anterior)


if __name__ == '__main__':
    unittest.main(failfast=True, verbosity=2)
