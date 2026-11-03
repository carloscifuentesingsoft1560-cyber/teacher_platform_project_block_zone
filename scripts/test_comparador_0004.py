"""Pruebas del comparador; invocadas únicamente por el ejecutor PostgreSQL aislado."""
from copy import deepcopy
import io
import unittest
from django.db import transaction


def ejecutar_pruebas(comp, observado, esperado, origen, columnas, certificado, archivo, sha, con, inventariar):
    class Comparacion(unittest.TestCase):
        def comprobar(self, datos=None, firma=None, ref=None):
            return comp.comparar_esquema(datos or observado, ref or esperado, origen,
                firma or columnas, certificado)

        def alterado(self, tipo, clave, valor):
            d = deepcopy(observado); d[tipo][clave] = valor
            return d

        def test_catalogo_postgresql_real(self):
            self.assertTrue(self.comprobar()['correcto'])

        def test_21_checks_y_un_indice_en_formato_original(self):
            d = deepcopy(observado)
            for clave, par in certificado['equivalencias'].items():
                tipo,nombre = clave.split(':',1)
                d[tipo][nombre]['definicion'] = par['origen']
            self.assertEqual(len(self.comprobar(d)['equivalencias_aplicadas']),22)

        def test_check_ausente(self):
            d=deepcopy(observado); d['restricciones'].pop(next(iter(d['restricciones'])))
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_check_adicional(self):
            d=deepcopy(observado); d['restricciones']['organizacion_grupo.extra']=next(iter(d['restricciones'].values()))
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_check_cambiado_de_tabla(self):
            d=deepcopy(observado); clave=next(iter(d['restricciones']))
            d['restricciones']['otra_tabla.'+clave.split('.',1)[1]]=d['restricciones'].pop(clave)
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_no_se_ignoran_condiciones_certificadas(self):
            k=next(k for k in certificado['equivalencias'] if k.startswith('restricciones:'))
            tipo,nombre=k.split(':',1); d=deepcopy(observado)
            d[tipo][nombre]['definicion']='CHECK (true)'
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_variante_no_certificada_tambien_se_rechaza(self):
            d=deepcopy(observado); k=next(iter(d['restricciones']))
            d['restricciones'][k]['definicion']+=' '
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_check_no_validado(self):
            d=deepcopy(observado); k=next(iter(d['restricciones'])); d['restricciones'][k]['validada']=False
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_indice_ausente(self):
            d=deepcopy(observado); d['indices'].pop(next(iter(d['indices'])))
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_predicado_indice_modificado(self):
            k=next(k for k in certificado['equivalencias'] if k.startswith('indices:'))
            tipo,nombre=k.split(':',1); d=deepcopy(observado)
            d[tipo][nombre]['definicion']=d[tipo][nombre]['definicion'].split(' WHERE ',1)[0]+' WHERE true'
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_indice_no_valido(self):
            d=deepcopy(observado); k=next(iter(d['indices'])); d['indices'][k]['valido']=False
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_funcion_modificada(self):
            d=deepcopy(observado); k=next(iter(d['funciones'])); d['funciones'][k]+=' -- cambio'
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_trigger_modificado(self):
            d=deepcopy(observado); k=next(iter(d['triggers'])); d['triggers'][k]['habilitado']='D'
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_tabla_ausente(self):
            d=deepcopy(observado); d['tablas'].pop(next(iter(d['tablas'])))
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_tabla_adicional(self):
            d=deepcopy(observado); d['tablas']['tabla_no_aprobada']={}
            with self.assertRaises(RuntimeError): self.comprobar(d)

        def test_columna_tipo_o_nullable_modificados(self):
            for posicion, nuevo in ((1,'otra_columna'),(2,'bigint_no_aprobado'),(3,False),(8,'42')):
                f=deepcopy(columnas); f[0][posicion]=nuevo if nuevo!=f[0][posicion] else 'diferente'
                with self.subTest(posicion=posicion),self.assertRaises(RuntimeError): self.comprobar(firma=f)

        def test_referencia_manipulada(self):
            ref=deepcopy(esperado); ref['funciones']['extra()']='no aprobada'
            with self.assertRaises(RuntimeError): self.comprobar(ref=ref)

        def test_certificado_valido_y_sha_incorrecto(self):
            self.assertEqual(comp.cargar_certificado(archivo,sha),certificado)
            with self.assertRaises(RuntimeError): comp.cargar_certificado(archivo,'0'*64)

        def comprobar_ddl_rechazado(self,sql):
            with transaction.atomic(),con.cursor() as c:
                try:
                    c.execute(sql)
                    d=inventariar()
                    with self.assertRaises(RuntimeError): self.comprobar(d,firma=comp.firma_columnas(con))
                finally:
                    transaction.set_rollback(True)

        def test_sql_real_sin_check(self):
            self.comprobar_ddl_rechazado('ALTER TABLE public.cuentas_usuario DROP CONSTRAINT usuario_rol_valido')

        def test_sql_real_condicion_distinta(self):
            self.comprobar_ddl_rechazado('ALTER TABLE public.cuentas_usuario DROP CONSTRAINT usuario_rol_valido, ADD CONSTRAINT usuario_rol_valido CHECK (true)')

        def test_sql_real_trigger_deshabilitado(self):
            self.comprobar_ddl_rechazado('ALTER TABLE public.inscripciones_resultadoadministrativo DISABLE TRIGGER zdb_movimiento_ascenso_verificado')

        def test_sql_real_columna_adicional(self):
            self.comprobar_ddl_rechazado('ALTER TABLE public.organizacion_grupo ADD COLUMN zdb_no_autorizada integer')

        def test_sql_real_default_no_autorizado(self):
            self.comprobar_ddl_rechazado('ALTER TABLE public.organizacion_grupo ALTER COLUMN cupo_maximo SET DEFAULT 999')

        def test_comparacion_no_escribe_en_transaccion_solo_lectura(self):
            with transaction.atomic(),con.cursor() as c:
                c.execute('SET TRANSACTION READ ONLY')
                self.assertTrue(self.comprobar(inventariar(),firma=comp.firma_columnas(con))['correcto'])

    salida=io.StringIO()
    resultado=unittest.TextTestRunner(stream=salida,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Comparacion))
    return resultado,salida.getvalue()
