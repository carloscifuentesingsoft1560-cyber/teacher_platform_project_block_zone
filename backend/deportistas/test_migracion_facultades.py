"""Prueba de transición sin backfill ni cambios de vínculos históricos."""
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class MigracionFacultadesPreservaDatos(TransactionTestCase):
    def test_conserva_vinculo_tres_pendiente_y_autorizacion_legacy(self):
        self.assertNotEqual(connection.settings_dict['NAME'],'zona_bloque')
        previo=[('deportistas','0002_identificacion_documental'),('inscripciones','0001_initial')]
        nuevo=[('deportistas','0003_comprobacion_facultades'),('inscripciones','0001_initial')]
        try:
            e=MigrationExecutor(connection);e.migrate(previo)
            apps=e.loader.project_state(previo).apps
            Usuario=apps.get_model('cuentas','Usuario');Persona=apps.get_model('deportistas','Deportista')
            Contacto=apps.get_model('deportistas','Acudiente');Vinculo=apps.get_model('deportistas','VinculoAcudiente')
            Tipo=apps.get_model('deportistas','TipoAutorizacion');Aut=apps.get_model('deportistas','Autorizacion')
            actor=Usuario.objects.create(username='ficticio_migracion_facultades',rol='administrador',password='!')
            persona=Persona.objects.create(nombres='Persona ficticia',apellidos='Prueba',fecha_nacimiento=timezone.localdate()-timedelta(days=4000),creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            contacto=Contacto.objects.create(nombres='Contacto ficticio',apellidos='Prueba',telefono='3000000000',creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            v=Vinculo.objects.create(pk=3,deportista=persona,acudiente=contacto,parentesco='Madre',fecha_inicio=timezone.localdate(),creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            tipo=Tipo.objects.create(codigo='ficticio-migracion-facultad',finalidad='Prueba',referencia_texto_aprobado='Referencia ficticia',creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            Aut.objects.create(deportista=persona,tipo=tipo,otorgante='acudiente',vinculo_acudiente=v,decision='denegada',declarada_en=timezone.now(),vigente_desde=timezone.localdate(),creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            modelos=(Persona,Contacto,Vinculo,Aut)
            campos={m.__name__:[f.attname for f in m._meta.fields] for m in modelos}
            antes={m.__name__:list(m.objects.order_by('pk').values(*campos[m.__name__])) for m in modelos}
            e=MigrationExecutor(connection);e.migrate(nuevo);apps=e.loader.project_state(nuevo).apps
            for nombre,filas in antes.items():
                self.assertEqual(list(apps.get_model('deportistas',nombre).objects.order_by('pk').values(*campos[nombre])),filas)
            self.assertEqual(apps.get_model('deportistas','VinculoAcudiente').objects.get(pk=3).facultad_para_autorizar,'pendiente')
            self.assertEqual(apps.get_model('deportistas','ComprobacionFacultad').objects.count(),0)
            self.assertIsNone(apps.get_model('deportistas','Autorizacion').objects.get().comprobacion_facultad_id)
        finally:
            e=MigrationExecutor(connection);e.migrate(e.loader.graph.leaf_nodes())
