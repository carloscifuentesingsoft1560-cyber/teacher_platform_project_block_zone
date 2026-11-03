from datetime import timedelta
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from auditoria.models import CambioAdministrativo
from organizacion.models import Asignacion, Disciplina, Nivel, Periodo, Grupo

class PruebasCoordinacionUnica(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(username="demo_dueno", rol="administrador")
        self.coordinador = Usuario.objects.create_user(username="demo_titular", rol="coordinador")
        self.entrante = Usuario.objects.create_user(username="demo_entrante", rol="profesor")
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.admin)

    def relevar(self, **cambios):
        datos = {"usuario": self.entrante.pk, "coordinador_actual": self.coordinador.pk}
        datos.update(cambios)
        return self.cliente.post("/api/organizacion/coordinacion/relevar/", datos, format="json")

    def test_base_rechaza_dos_coordinadores_activos(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user(username="demo_duplicado", rol="coordinador")
        self.assertEqual(Usuario.objects.filter(rol="coordinador", is_active=True).count(), 1)

    def test_permite_historicos_inactivos(self):
        for n in range(2):
            Usuario.objects.create_user(username="demo_anterior_"+str(n), rol="coordinador", is_active=False)
        self.assertEqual(Usuario.objects.filter(rol="coordinador", is_active=False).count(), 2)

    def test_api_rechaza_creacion_de_segundo_coordinador(self):
        r = self.cliente.post("/api/usuarios/", {"username": "demo_segundo", "rol": "coordinador"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Usuario.objects.filter(username="demo_segundo").exists())

    def test_api_permite_cuenta_coordinadora_inactiva_pero_no_activarla(self):
        r = self.cliente.post("/api/usuarios/", {"username": "demo_pendiente", "rol": "coordinador", "is_active": False}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        activacion = self.cliente.patch(f"/api/usuarios/{r.data['id']}/", {"is_active": True}, format="json")
        self.assertEqual(activacion.status_code, 400)

    def test_relevo_preserva_cuentas_y_registra_actor_fechas(self):
        r = self.relevar()
        self.assertEqual(r.status_code, 200, r.data)
        self.coordinador.refresh_from_db()
        self.entrante.refresh_from_db()
        self.assertFalse(self.coordinador.is_active)
        self.assertTrue(self.entrante.is_active)
        self.assertEqual(self.entrante.rol, "profesor")
        self.assertTrue(self.entrante.tiene_rol("coordinador"))
        eventos = CambioAdministrativo.objects.filter(accion__startswith="coordinacion_").order_by("fecha")
        self.assertEqual(list(eventos.values_list("accion", flat=True)), ["coordinacion_fin", "coordinacion_inicio"])
        self.assertEqual(list(eventos.values_list("identificador", flat=True)), [self.coordinador.pk, self.entrante.pk])
        self.assertTrue(all(e.actor_id == self.admin.pk and e.fecha for e in eventos))
        self.assertEqual(Usuario.objects.count(), 3)

    def test_relevo_rechaza_version_obsoleta(self):
        r = self.relevar(coordinador_actual=None)
        self.assertEqual(r.status_code, 409)
        self.coordinador.refresh_from_db()
        self.assertTrue(self.coordinador.is_active)
        self.assertFalse(CambioAdministrativo.objects.exists())

    def test_no_repite_nombramiento_del_mismo_titular(self):
        self.assertEqual(self.relevar(usuario=self.coordinador.pk).status_code, 400)

    def test_no_demueve_al_propio_administrador(self):
        self.assertEqual(self.relevar(usuario=self.admin.pk).status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, "administrador")

    def test_relevo_invalido_revierte_cese_y_auditoria(self):
        hoy = timezone.localdate()
        d = Disciplina.objects.get(codigo="escalada")
        p = Periodo.objects.create(codigo="demo-relevo", nombre="Ficticio", fecha_inicio=hoy, fecha_fin=hoy+timedelta(days=10))
        g = Grupo.objects.create(codigo="demo-relevo", nombre="Ficticio", disciplina=d, nivel=Nivel.objects.get(codigo="nivel-1"), periodo=p, cupo_maximo=5)
        Asignacion.objects.create(grupo=g, usuario=self.entrante, tipo="profesor", fecha_inicio=hoy)
        self.entrante.is_active=False
        self.entrante.save(update_fields=["is_active"])
        self.assertEqual(self.relevar().status_code, 400)
        self.coordinador.refresh_from_db()
        self.assertTrue(self.coordinador.is_active)
        self.assertEqual(CambioAdministrativo.objects.count(), 0)

    def test_coordinador_y_profesor_no_relevan_cargo(self):
        for cuenta in [self.coordinador, self.entrante]:
            self.cliente.force_authenticate(cuenta)
            self.assertEqual(self.relevar().status_code, 403)
            self.assertEqual(self.cliente.get("/api/organizacion/coordinacion/").status_code, 403)

    def test_historial_conserva_persona_tras_cambiar_de_rol(self):
        self.assertEqual(self.relevar().status_code, 200)
        self.cliente.patch(f"/api/usuarios/{self.coordinador.pk}/", {"rol": "profesor"}, format="json")
        r = self.cliente.get("/api/organizacion/coordinacion/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["actual"]["id"], self.entrante.pk)
        self.assertIn(self.coordinador.pk, [e["usuario"] for e in r.data["results"]])

    def test_cese_revoca_sesion_previa(self):
        sesion = APIClient(enforce_csrf_checks=True)
        sesion.force_login(self.coordinador)
        self.assertEqual(self.relevar().status_code, 200)
        self.assertEqual(sesion.get("/api/organizacion/grupos/").status_code, 403)

    def test_vacante_y_primera_designacion(self):
        self.coordinador.is_active = False
        self.coordinador.save()
        self.assertIsNone(self.cliente.get("/api/organizacion/coordinacion/").data["actual"])
        self.assertEqual(self.relevar(coordinador_actual=None).status_code, 200)

    def test_cambio_generico_registra_fin_sin_borrar_cuenta(self):
        r = self.cliente.patch(f"/api/usuarios/{self.coordinador.pk}/", {"is_active": False}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(CambioAdministrativo.objects.filter(accion="coordinacion_fin", identificador=self.coordinador.pk, actor=self.admin).exists())

    def test_relevo_exige_csrf(self):
        cliente = APIClient(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        r = cliente.post("/api/organizacion/coordinacion/relevar/", {"usuario": self.entrante.pk, "coordinador_actual": self.coordinador.pk}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_comando_local_no_omite_historial_del_cargo(self):
        from django.core.management import call_command, CommandError
        with self.assertRaises(CommandError):
            call_command("crear_usuario", "demo_cli", rol="coordinador")
        self.assertFalse(Usuario.objects.filter(username="demo_cli").exists())
    def test_actor_saliente_en_cache_no_hereda_alcance_del_entrante(self):
        self.assertEqual(self.relevar().status_code, 200)
        # Simula una referencia a la cuenta anterior cargada antes del relevo.
        self.cliente.force_authenticate(self.coordinador)
        self.assertEqual(self.cliente.get("/api/organizacion/grupos/").status_code, 403)