"""Ensayo de actualización Etapa 2→3 sobre datos ficticios y clúster del runner."""
from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from cuentas.models import Usuario


class MigracionEtapa3(TransactionTestCase):
    def test_actualizacion_preserva_cuenta_y_facultades(self):
        ejecutor = MigrationExecutor(connection)
        finales = ejecutor.loader.graph.leaf_nodes()
        previos = [('recursos',None),('curriculo',None),('biblioteca',None)]
        try:
            ejecutor.migrate(previos)
            cuenta = Usuario.objects.create_user(username='ficticio_migracion_e3',rol='profesor')
            with connection.cursor() as c:
                c.execute('SELECT id,username,rol,is_active FROM cuentas_usuario ORDER BY id'); antes = c.fetchall()
                c.execute('SELECT usuario_id,rol,vigente FROM cuentas_pertenenciarol ORDER BY id'); roles = c.fetchall()
            MigrationExecutor(connection).migrate(finales)
            with connection.cursor() as c:
                c.execute('SELECT id,username,rol,is_active FROM cuentas_usuario ORDER BY id'); self.assertEqual(c.fetchall(),antes)
                c.execute('SELECT usuario_id,rol,vigente FROM cuentas_pertenenciarol ORDER BY id'); self.assertEqual(c.fetchall(),roles)
                c.execute("SELECT count(*) FROM pg_trigger WHERE tgname='zdb_e3_version'");self.assertEqual(c.fetchone()[0],3)
            from biblioteca.models import CandidatoBiblioteca
            from curriculo.models import MallaVersion
            self.assertFalse(CandidatoBiblioteca.objects.exists());self.assertFalse(MallaVersion.objects.exists())
            self.assertEqual(MigrationExecutor(connection).migration_plan(finales),[])
        finally:
            MigrationExecutor(connection).migrate(finales)
