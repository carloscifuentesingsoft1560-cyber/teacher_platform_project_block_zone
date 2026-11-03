"""Ciclo reversible y aislamiento de nombres: solo en la base Django de pruebas."""
import hashlib
from django.db import connection, transaction, IntegrityError, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from deportistas.tests import DatosFase3
from .modelos_ascensos import ProgresionInstitucional
from .servicios_ascensos import proponer_progresion, disponer_inscripcion, decidir_progresion


B1 = ('inscripciones', '0002_progresioninstitucional_eventoprogresion_and_more')
ANTES = ('inscripciones', '0001_initial')
TABLAS = ('inscripciones_progresioninstitucional', 'inscripciones_eventoprogresion',
    'inscripciones_afectacioninscripcion', 'inscripciones_excepcionpedagogica')
FUNCIONES = ('zdb_validar_ascenso_b1', 'zdb_historial_ascenso_inmutable',
    'zdb_nivel_ascenso_estable', 'zdb_revocacion_ascenso_auditada')


class SeguridadMigracionB1(DatosFase3, TransactionTestCase):
    def tearDown(self):
        # La auditoría histórica revierte descendientes; reponer el esquema vigente.
        self.migrar(('inscripciones', '0005_facultades_multirrol'))
        super().tearDown()

    def migrar(self, destino):
        # Defensa adicional: estas pruebas nunca deben usar la base institucional.
        with connection.cursor() as c:
            c.execute('SELECT current_database()')
            self.assertTrue(c.fetchone()[0].startswith('test_zdb_fase3_'))
        MigrationExecutor(connection).migrate([destino])

    def huellas(self, tablas):
        resultado = {}
        with connection.cursor() as c:
            for t in tablas:
                c.execute('SELECT row_to_json(t)::text FROM public.' + connection.ops.quote_name(t) + ' t')
                filas = sorted(r[0] for r in c.fetchall())
                c.execute('SELECT attname FROM pg_catalog.pg_attribute WHERE attrelid=pg_catalog.to_regclass(%s) AND attnum>0 AND NOT attisdropped ORDER BY attnum', ['public.' + t])
                columnas = tuple(x[0] for x in c.fetchall())
                resultado[t] = (columnas, len(filas), hashlib.sha256('\n'.join(filas).encode()).hexdigest())
        return resultado

    def test_aplicar_revertir_reaplicar_con_homonimos_y_datos(self):
        self.migrar(ANTES)
        try:
            self.preparar()
            origen = self.inscribir()
            segunda = self.inscribir(grupo=self.b)
            self.assertEqual(self.post(f'inscripciones/{segunda.pk}/suspender/',
                {'version':1, 'motivo':'Reserva ficticia', 'fecha_vencimiento':str(self.hoy)}).status_code, 200)
            tablas = [t for t in connection.introspection.table_names() if t != 'django_migrations']
            antes = self.huellas(tablas)
            with connection.cursor() as c:
                c.execute('CREATE SCHEMA b1_ajeno')
                for t in (*TABLAS, 'organizacion_nivel'):
                    c.execute('CREATE TABLE b1_ajeno.' + t + ' (marca text)')
                    c.execute('INSERT INTO b1_ajeno.' + t + " VALUES ('no tocar')")
                for f in FUNCIONES:
                    c.execute('CREATE FUNCTION b1_ajeno.' + f + '() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$')
                c.execute('CREATE TRIGGER zdb_nivel_ascenso_estable BEFORE UPDATE ON b1_ajeno.organizacion_nivel FOR EACH ROW EXECUTE FUNCTION b1_ajeno.zdb_nivel_ascenso_estable()')
                c.execute('CREATE TEMP TABLE organizacion_nivel (marca text)')
                c.execute("INSERT INTO pg_temp.organizacion_nivel VALUES ('temporal intacta')")
                c.execute('SET search_path TO b1_ajeno, public')
            self.migrar(B1)
            with connection.cursor() as c:
                c.execute('SHOW search_path')
                self.assertEqual(c.fetchone()[0], 'b1_ajeno, public')
                c.execute('SET search_path TO public, pg_catalog, pg_temp')
            self.assertEqual(self.huellas(tablas), antes)
            p = proponer_progresion(self.prof, origen.pk, self.n2, 'Auditoría ficticia')
            for a in p.afectaciones.all():
                p = disponer_inscripcion(self.coord, p.pk, p.version, a.pk, 'pendiente', 'Sin destino')
            inscripciones = self.huellas(['inscripciones_inscripcion', 'inscripciones_reservacupo', 'organizacion_grupo'])
            p = decidir_progresion(self.coord, p.pk, p.version, True, 'Aprobada sin ejecutar')
            self.assertEqual(self.huellas(list(inscripciones)), inscripciones)
            for ruta in ('b1_ajeno, public', 'pg_temp, b1_ajeno, public', 'pg_catalog, public'):
                with connection.cursor() as c:
                    c.execute('SET search_path TO ' + ruta)
                    # Validación de referencias debe leer public, no el homónimo ajeno/temporal.
                    c.execute('UPDATE public.inscripciones_progresioninstitucional SET version=version WHERE id=%s', [p.pk])
                with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as c:
                    c.execute("UPDATE public.inscripciones_progresioninstitucional SET estado_plan='ejecutado' WHERE id=%s", [p.pk])
                with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as c:
                    c.execute('UPDATE public.inscripciones_eventoprogresion SET motivo=%s WHERE progresion_id=%s', ['No permitido', p.pk])
            with connection.cursor() as c:
                c.execute('SET search_path TO public, pg_catalog, pg_temp')
            antes_reversa = self.huellas(tablas)
            with connection.cursor() as c:
                c.execute('SET search_path TO pg_temp, b1_ajeno, public')
            self.migrar(ANTES)
            with connection.cursor() as c:
                c.execute('SET search_path TO public, pg_catalog, pg_temp')
            self.assertEqual(self.huellas(tablas), antes_reversa)
            with connection.cursor() as c:
                for t in TABLAS:
                    c.execute('SELECT pg_catalog.to_regclass(%s)', ['public.' + t])
                    self.assertIsNone(c.fetchone()[0])
                for t in (*TABLAS, 'organizacion_nivel'):
                    c.execute('SELECT marca FROM b1_ajeno.' + t)
                    self.assertEqual(c.fetchall(), [('no tocar',)])
                c.execute('SELECT marca FROM pg_temp.organizacion_nivel')
                self.assertEqual(c.fetchall(), [('temporal intacta',)])
                c.execute("SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='b1_ajeno'")
                self.assertEqual(c.fetchone()[0], 4)
                c.execute("SELECT count(*) FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class r ON r.oid=t.tgrelid JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='b1_ajeno' AND NOT t.tgisinternal")
                self.assertEqual(c.fetchone()[0], 1)
                c.execute('SET search_path TO b1_ajeno, public')
            self.migrar(B1)
            with connection.cursor() as c:
                c.execute('SET search_path TO public, pg_catalog, pg_temp')
                c.execute("SELECT proconfig, prosecdef FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND proname=ANY(%s)", [list(FUNCIONES)])
                funciones = c.fetchall()
                self.assertEqual(len(funciones), 4)
                self.assertTrue(all(config == ['search_path=pg_catalog'] and not definer for config, definer in funciones))
            self.assertEqual(self.huellas(tablas), antes_reversa)
            self.assertEqual(ProgresionInstitucional.objects.count(), 0)
        finally:
            with connection.cursor() as c:
                c.execute('SET search_path TO public, pg_catalog, pg_temp')
                c.execute('DROP SCHEMA IF EXISTS b1_ajeno CASCADE')
                c.execute('DROP TABLE IF EXISTS pg_temp.organizacion_nivel')
            self.migrar(B1)

    def test_colisiones_publicas_no_sobrescriben_objetos(self):
        for clase in ('funcion', 'trigger'):
            with self.subTest(clase=clase):
                self.migrar(ANTES)
                with connection.cursor() as c:
                    if clase == 'funcion':
                        c.execute('CREATE FUNCTION public.zdb_validar_ascenso_b1() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$')
                    else:
                        c.execute('CREATE FUNCTION public.b1_colision_prueba() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$')
                        c.execute('CREATE TRIGGER zdb_nivel_ascenso_estable BEFORE UPDATE ON public.organizacion_nivel FOR EACH ROW EXECUTE FUNCTION public.b1_colision_prueba()')
                try:
                    with self.assertRaises(DatabaseError):
                        self.migrar(B1)
                    with connection.cursor() as c:
                        c.execute("SELECT pg_catalog.to_regclass('public.inscripciones_progresioninstitucional')")
                        self.assertIsNone(c.fetchone()[0])
                        if clase == 'funcion':
                            c.execute("SELECT pg_catalog.pg_get_functiondef('public.zdb_validar_ascenso_b1()'::regprocedure)")
                            self.assertIn('RETURN NEW', c.fetchone()[0])
                        else:
                            c.execute("SELECT p.proname FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.organizacion_nivel'::regclass AND t.tgname='zdb_nivel_ascenso_estable'")
                            self.assertEqual(c.fetchone()[0], 'b1_colision_prueba')
                finally:
                    with connection.cursor() as c:
                        if clase == 'funcion':
                            c.execute('DROP FUNCTION public.zdb_validar_ascenso_b1()')
                        else:
                            c.execute('DROP TRIGGER zdb_nivel_ascenso_estable ON public.organizacion_nivel')
                            c.execute('DROP FUNCTION public.b1_colision_prueba()')
                    self.migrar(B1)
