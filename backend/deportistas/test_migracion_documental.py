"""Preservación del esquema anterior, exclusivamente en bases de pruebas Django."""
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

class MigracionDocumentalPreservaDatos(TransactionTestCase):
    def test_transicion_nullable_preserva_identidad_y_relaciones(self):
        self.assertNotEqual(connection.settings_dict["NAME"],"zona_bloque")
        anterior=[("deportistas","0001_initial"),("inscripciones","0001_initial")]
        nuevo=[("deportistas","0002_identificacion_documental"),("inscripciones","0001_initial")]
        try:
            ejecutor=MigrationExecutor(connection)
            ejecutor.migrate(anterior)
            apps=ejecutor.loader.project_state(anterior).apps
            Usuario=apps.get_model("cuentas","Usuario")
            Persona=apps.get_model("deportistas","Deportista")
            actor=Usuario.objects.create(username="ficticio_migracion_documental",rol="administrador",password="!")
            persona=Persona.objects.create(nombres="Identidad ficticia anterior",apellidos="Prueba",fecha_nacimiento=timezone.localdate()-timedelta(days=4000),creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            Disciplina=apps.get_model("organizacion","Disciplina")
            Nivel=apps.get_model("organizacion","Nivel")
            Periodo=apps.get_model("organizacion","Periodo")
            Grupo=apps.get_model("organizacion","Grupo")
            Inscripcion=apps.get_model("inscripciones","Inscripcion")
            d=Disciplina.objects.create(codigo="ficticia-migracion",nombre="Ficticia")
            n=Nivel.objects.create(disciplina=d,codigo="ficticio",nombre="Ficticio")
            p=Periodo.objects.create(codigo="ficticio-migracion",nombre="Ficticio",fecha_inicio=timezone.localdate()-timedelta(days=10),fecha_fin=timezone.localdate()+timedelta(days=10))
            g=Grupo.objects.create(codigo="ficticio-migracion",nombre="Ficticio",disciplina=d,nivel=n,periodo=p,cupo_maximo=10)
            inscripcion=Inscripcion.objects.create(deportista_id=persona.pk,grupo=g,fecha_ingreso=timezone.localdate(),creado_por_id=actor.pk,actualizado_por_id=actor.pk)
            campos=[f.attname for f in Persona._meta.fields]
            antes=Persona.objects.values(*campos).get(pk=persona.pk)
            referencia=Inscripcion.objects.values().get(pk=inscripcion.pk)
            ejecutor=MigrationExecutor(connection)
            ejecutor.migrate(nuevo)
            actuales=ejecutor.loader.project_state(nuevo).apps
            Persona=actuales.get_model("deportistas","Deportista")
            fila=Persona.objects.get(pk=persona.pk)
            self.assertEqual(Persona.objects.values(*campos).get(pk=fila.pk),antes)
            self.assertIsNone(fila.tipo_documento_id)
            self.assertIsNone(fila.numero_documento)
            self.assertIsNone(fila.pais_emisor)
            self.assertEqual(actuales.get_model("inscripciones","Inscripcion").objects.values().get(pk=inscripcion.pk),referencia)
            self.assertEqual(actuales.get_model("deportistas","TipoDocumento").objects.count(),7)
            self.assertEqual(actuales.get_model("deportistas","CambioDocumentoDeportista").objects.count(),0)
        finally:
            ejecutor=MigrationExecutor(connection)
            ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())
