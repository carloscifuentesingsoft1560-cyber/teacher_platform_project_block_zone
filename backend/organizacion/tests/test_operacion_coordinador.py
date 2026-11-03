from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from auditoria.models import CambioAdministrativo
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Horario, Asignacion
from organizacion.servicios import crear_asignacion
from organizacion.serializers import AsignacionSerializer
from rest_framework.exceptions import PermissionDenied

class PruebasOperacionCoordinador(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hoy = timezone.localdate()
        cls.admin = Usuario.objects.create_user(username="demo_admin_op", rol="administrador")
        cls.coord = Usuario.objects.create_user(username="demo_coord_op", rol="coordinador")
        cls.prof = Usuario.objects.create_user(username="demo_prof_op", rol="profesor")
        cls.otro = Usuario.objects.create_user(username="demo_sin_grupo", rol="profesor")
        cls.d = Disciplina.objects.get(codigo="escalada")
        cls.n = Nivel.objects.get(codigo="nivel-1")
        cls.p = Periodo.objects.create(codigo="demo-op", nombre="Ciclo ficticio", fecha_inicio=cls.hoy-timedelta(days=30), fecha_fin=cls.hoy+timedelta(days=30))
        cls.g = Grupo.objects.create(codigo="demo-op-a", nombre="Grupo A ficticio", disciplina=cls.d, nivel=cls.n, periodo=cls.p, cupo_maximo=8)
        cls.g2 = Grupo.objects.create(codigo="demo-op-b", nombre="Grupo B ficticio", disciplina=cls.d, nivel=cls.n, periodo=cls.p, cupo_maximo=8)
        Horario.objects.create(grupo=cls.g, dia=cls.hoy.weekday(), hora_inicio="10:00", hora_fin="11:00")
        Horario.objects.create(grupo=cls.g2, dia=cls.hoy.weekday(), hora_inicio="11:00", hora_fin="12:00")

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.coord)

    def asignar(self, grupo=None, usuario=None, tipo="profesor", inicio=None):
        return self.cliente.post("/api/organizacion/asignaciones/", {"grupo": (grupo or self.g).pk, "usuario": (usuario or self.prof).pk, "tipo": tipo, "fecha_inicio": str(inicio or self.hoy)}, format="json")

    def test_equipo_incluye_profesores_sin_grupo_e_inactivos_sin_datos_sensibles(self):
        Usuario.objects.filter(pk=self.otro.pk).update(is_active=False)
        r = self.cliente.get("/api/organizacion/profesores/")
        self.assertEqual({u["id"] for u in r.data["results"]}, {self.prof.pk, self.otro.pk})
        self.assertNotIn("email", r.data["results"][0])
        self.assertNotIn("password", r.data["results"][0])

    def test_coordinador_gestiona_grupo_sin_asignacion_personal(self):
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"nombre": "Nombre ficticio nuevo"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(CambioAdministrativo.objects.filter(actor=self.coord, identificador=self.g.pk).exists())

    def test_crea_grupo_reutilizando_catalogos(self):
        datos = {"codigo": "demo-nuevo-op", "nombre": "Grupo nuevo", "disciplina": self.d.pk, "nivel": self.n.pk, "periodo": self.p.pk, "cupo_maximo": 10,
            "horarios": [{"dia": 1, "hora_inicio": "16:00", "hora_fin": "18:00"}]}
        self.assertEqual(self.cliente.post("/api/organizacion/grupos/", datos, format="json").status_code, 201)

    def test_crea_y_finaliza_asignacion_docente_con_historial(self):
        r = self.asignar(inicio=self.hoy-timedelta(days=2))
        self.assertEqual(r.status_code, 201)
        pk = r.data["id"]
        self.assertEqual(self.cliente.post(f"/api/organizacion/asignaciones/{pk}/finalizar/", {"fecha_fin": str(self.hoy-timedelta(days=1))}, format="json").status_code, 200)
        historial = self.cliente.get("/api/organizacion/asignaciones/").data
        self.assertEqual(historial["count"], 1)
        self.assertEqual(historial["results"][0]["id"], pk)

    def test_no_administra_cuentas_privilegios_recuperacion_ni_catalogos(self):
        for ruta, metodo in [("/api/usuarios/", "post"), (f"/api/usuarios/{self.coord.pk}/", "patch"),
            (f"/api/usuarios/{self.admin.pk}/restablecer-acceso/", "post"), ("/api/organizacion/disciplinas/", "post"),
            (f"/api/organizacion/niveles/{self.n.pk}/", "patch"), (f"/api/organizacion/periodos/{self.p.pk}/", "patch")]:
            self.assertEqual(getattr(self.cliente, metodo)(ruta, {"rol": "administrador", "is_superuser": True}, format="json").status_code, 403)

    def test_no_crea_responsabilidades_de_coordinador(self):
        self.assertEqual(self.asignar(usuario=self.coord, tipo="coordinador").status_code, 403)

    def test_rechaza_campos_administrativos_ocultos(self):
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"nombre": "Ficticio", "is_superuser": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_valida_cambios_de_horario_compartido_y_revierte_conflicto(self):
        self.assertEqual(self.asignar().status_code, 201)
        self.assertEqual(self.asignar(usuario=self.otro).status_code, 201)
        self.assertEqual(self.asignar(grupo=self.g2).status_code, 201)
        r = self.cliente.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"horarios": [{"dia": self.hoy.weekday(), "hora_inicio": "10:30", "hora_fin": "11:30"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(str(self.g.horarios.get(activo=True).hora_inicio), "10:00:00")
        correcto = self.cliente.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"horarios": [{"dia": self.hoy.weekday(), "hora_inicio": "09:00", "hora_fin": "10:00"}]}, format="json")
        self.assertEqual(correcto.status_code, 200)
        self.assertEqual(self.g.horarios.filter(activo=False).count(), 1)

    def test_calendario_institucional_sin_asignacion_personal(self):
        r = self.cliente.get("/api/organizacion/calendario/", {"desde": str(self.hoy), "hasta": str(self.hoy)})
        self.assertEqual({e["grupo"] for e in r.data["eventos"]}, {self.g.pk, self.g2.pk})

    def test_profesor_no_gestiona_ni_ve_grupos_ajenos(self):
        self.cliente.force_authenticate(self.prof)
        self.assertEqual(self.cliente.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"nombre": "No"}, format="json").status_code, 403)
        self.assertEqual(self.asignar().status_code, 403)
        self.assertEqual(self.cliente.get(f"/api/organizacion/grupos/{self.g2.pk}/").status_code, 404)

    def test_servicio_revalida_cuenta_tras_revocacion(self):
        serializer = AsignacionSerializer(data={"grupo": self.g.pk, "usuario": self.prof.pk, "tipo": "profesor", "fecha_inicio": str(self.hoy)})
        serializer.is_valid(raise_exception=True)
        Usuario.objects.filter(pk=self.coord.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            crear_asignacion(serializer, self.coord)

    def test_asignaciones_coordinador_legacy_no_dan_nuevos_permisos(self):
        legacy = Asignacion.objects.create(usuario=self.coord, grupo=self.g, tipo="coordinador", fecha_inicio=self.hoy)
        r = self.cliente.post(f"/api/organizacion/asignaciones/{legacy.pk}/finalizar/", {"fecha_fin": str(self.hoy)}, format="json")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Asignacion.objects.filter(pk=legacy.pk).exists())

    def test_escrituras_coordinadoras_exigen_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        c.force_login(self.coord)
        self.assertEqual(c.patch(f"/api/organizacion/grupos/{self.g.pk}/", {"nombre": "Ficticio"}, format="json").status_code, 403)
