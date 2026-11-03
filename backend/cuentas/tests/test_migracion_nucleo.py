"""Ensayo de conservación con identidades ficticias en PostgreSQL temporal."""
from django.test import TransactionTestCase
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor


class MigracionNucleo(TransactionTestCase):
    def test_backfill_preserva_usuario_y_no_acredita_persona(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_zdb_fase3_'))
        ejecutor=MigrationExecutor(connection)
        finales=ejecutor.loader.graph.leaf_nodes()
        try:
            ejecutor.migrate([('cuentas','0004_usuario_un_coordinador_activo')])
            estado=ejecutor.loader.project_state([('cuentas','0004_usuario_un_coordinador_activo')]).apps
            Usuario=estado.get_model('cuentas','Usuario')
            u=Usuario.objects.create(username='ficticio_previo',rol='administrador',password='hash-ficticio-no-operativo')
            antes=list(Usuario.objects.order_by('pk').values())
            MigrationExecutor(connection).migrate(finales)
            from cuentas.models import Usuario as Actual, PertenenciaRol,Persona,EnlaceIdentidad
            self.assertEqual(list(Actual.objects.order_by('pk').values()),antes)
            r=PertenenciaRol.objects.get(usuario_id=u.pk,vigente=True)
            self.assertEqual(r.rol,'administrador')
            self.assertEqual(r.eventos.get().accion,'migracion')
            self.assertEqual(Persona.objects.count(),0)
            self.assertEqual(EnlaceIdentidad.objects.count(),0)
        finally:
            MigrationExecutor(connection).migrate(finales)
