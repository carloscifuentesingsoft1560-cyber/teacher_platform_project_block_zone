from datetime import timedelta
from urllib.parse import urlsplit, parse_qs
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from auditoria.models import CambioAdministrativo
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Asignacion
from cuentas.models import Usuario, SolicitudRestablecimiento

CLAVE = "Clave-ficticia-con-suficiente-longitud-527!"
NUEVA = "Otra-clave-ficticia-completamente-distinta-932!"

class PruebasGestionUsuarios(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(username="demo_gestor", password=CLAVE, rol="administrador")
        cls.profe = Usuario.objects.create_user(username="demo_docente", password=CLAVE, rol="profesor")

    def setUp(self):
        cache.clear()
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.admin)

    def solicitar(self):
        return self.cliente.post(f"/api/usuarios/{self.profe.pk}/restablecer-acceso/", {"contrasena_actual": CLAVE}, format="json")

    def token(self):
        r = self.solicitar()
        self.assertEqual(r.status_code, 200, r.data)
        return parse_qs(urlsplit(r.data["ruta"]).fragment)["token"][0]

    def test_crea_cada_rol_y_audita_sin_contrasena(self):
        for rol in Usuario.Rol.values:
            r = self.cliente.post("/api/usuarios/", {"username": "demo_nuevo_"+rol, "rol": rol, "contrasena": NUEVA}, format="json")
            self.assertEqual(r.status_code, 201, r.data)
            self.assertNotIn("contrasena", r.data)
            self.assertTrue(Usuario.objects.get(pk=r.data["id"]).check_password(NUEVA))
        self.assertEqual(CambioAdministrativo.objects.filter(accion="crear").count(), len(Usuario.Rol.values))
        self.assertFalse(any("contrasena" in c.campos for c in CambioAdministrativo.objects.all()))

    def test_crear_sin_clave_deja_acceso_inutilizable(self):
        r = self.cliente.post("/api/usuarios/", {"username": "demo_sin_acceso", "rol": "profesor"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Usuario.objects.get(pk=r.data["id"]).has_usable_password())

    def test_clave_debil_rechazada(self):
        r = self.cliente.post("/api/usuarios/", {"username": "demo_debil", "contrasena": "123456789012"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_busqueda_usuarios(self):
        r = self.cliente.get("/api/usuarios/?search=demo_docente")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["id"], self.profe.pk)

    def test_modifica_datos_rol_y_audita_actor(self):
        r = self.cliente.patch(f"/api/usuarios/{self.profe.pk}/", {"first_name": "Persona ficticia", "rol": "coordinador"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.profe.refresh_from_db()
        self.assertEqual(self.profe.rol, "coordinador")
        self.assertEqual(CambioAdministrativo.objects.get(accion="modificar").actor_id, self.admin.pk)

    def test_no_permite_cambiar_clave_desde_edicion_normal(self):
        r = self.cliente.patch(f"/api/usuarios/{self.profe.pk}/", {"contrasena": NUEVA}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_profesor_y_coordinador_no_administran_usuarios(self):
        for rol in ["profesor", "coordinador"]:
            self.profe.rol = rol
            self.profe.save()
            self.cliente.force_authenticate(self.profe)
            for metodo, ruta in [("get", "/api/usuarios/"), ("post", "/api/usuarios/"), ("patch", f"/api/usuarios/{self.profe.pk}/")]:
                r = getattr(self.cliente, metodo)(ruta, {} if metodo != "get" else None, format="json")
                self.assertEqual(r.status_code, 403)

    def test_anonimo_no_administra(self):
        self.cliente.force_authenticate(None)
        self.assertEqual(self.cliente.get("/api/usuarios/").status_code, 403)

    def test_no_auto_desactivacion_ni_cambio_de_rol(self):
        for datos in [{"is_active": False}, {"rol": "profesor"}]:
            self.assertEqual(self.cliente.patch(f"/api/usuarios/{self.admin.pk}/", datos, format="json").status_code, 400)

    def test_desactiva_reactiva_y_no_elimina(self):
        ruta = f"/api/usuarios/{self.profe.pk}/"
        self.assertEqual(self.cliente.patch(ruta, {"is_active": False}, format="json").status_code, 200)
        self.assertEqual(self.cliente.patch(ruta, {"is_active": True}, format="json").status_code, 200)
        self.assertEqual(self.cliente.delete(ruta).status_code, 405)
        self.assertTrue(Usuario.objects.filter(pk=self.profe.pk).exists())

    def test_no_eleva_flags_tecnicos_desde_api(self):
        r = self.cliente.patch(f"/api/usuarios/{self.profe.pk}/", {"is_superuser": True, "is_staff": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.profe.refresh_from_db()
        self.assertFalse(self.profe.is_superuser)
        self.assertFalse(self.profe.is_staff)

    def test_rol_invalido_y_usuario_duplicado(self):
        self.assertEqual(self.cliente.post("/api/usuarios/", {"username": "demo_docente", "rol": "profesor"}, format="json").status_code, 400)
        self.assertEqual(self.cliente.post("/api/usuarios/", {"username": "demo_invalido", "rol": "estudiante"}, format="json").status_code, 400)

    def test_cambio_rol_con_asignaciones_rechazado(self):
        hoy = timezone.localdate()
        d = Disciplina.objects.get(codigo="escalada")
        p = Periodo.objects.create(codigo="demo-us", nombre="Demo", fecha_inicio=hoy, fecha_fin=hoy+timedelta(days=7))
        g = Grupo.objects.create(codigo="demo-us", nombre="Demo", disciplina=d, nivel=Nivel.objects.get(codigo="nivel-1"), periodo=p, cupo_maximo=5)
        a = Asignacion.objects.create(grupo=g, usuario=self.profe, tipo="profesor", fecha_inicio=hoy)
        r = self.cliente.patch(f"/api/usuarios/{self.profe.pk}/", {"rol": "coordinador"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Asignacion.objects.filter(pk=a.pk).exists())

    def test_restablecer_exige_reautenticacion(self):
        r = self.cliente.post(f"/api/usuarios/{self.profe.pk}/restablecer-acceso/", {"contrasena_actual": "incorrecta"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(SolicitudRestablecimiento.objects.count(), 0)

    def test_token_solo_se_conserva_como_hash_y_no_se_audita(self):
        token = self.token()
        solicitud = SolicitudRestablecimiento.objects.get()
        self.assertNotEqual(token, solicitud.token_hash)
        self.assertEqual(len(solicitud.token_hash), 64)
        self.assertNotIn(token, str(list(CambioAdministrativo.objects.values())))

    def test_recuperacion_csrf_y_un_solo_uso_revoca_sesion(self):
        sesion_previa = APIClient()
        sesion_previa.force_login(self.profe)
        token = self.token()
        publico = APIClient(enforce_csrf_checks=True)
        datos = {"token": token, "contrasena": NUEVA}
        self.assertEqual(publico.post("/api/recuperacion/confirmar/", datos, format="json").status_code, 403)
        csrf = publico.get("/api/autenticacion/csrf/").data["csrfToken"]
        self.assertEqual(publico.post("/api/recuperacion/confirmar/", datos, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 200)
        self.profe.refresh_from_db()
        self.assertTrue(self.profe.check_password(NUEVA))
        self.assertEqual(sesion_previa.get("/api/autenticacion/sesion/").status_code, 403)
        self.assertEqual(publico.post("/api/recuperacion/confirmar/", datos, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 400)

    def test_token_caducado_rechazado(self):
        token = self.token()
        SolicitudRestablecimiento.objects.update(fecha_expira=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.cliente.post("/api/recuperacion/confirmar/", {"token": token, "contrasena": NUEVA}, format="json").status_code, 400)

    def test_nueva_solicitud_revoca_enlace_anterior(self):
        antiguo = self.token()
        nuevo = self.token()
        self.assertNotEqual(antiguo, nuevo)
        self.assertEqual(self.cliente.post("/api/recuperacion/confirmar/", {"token": antiguo, "contrasena": NUEVA}, format="json").status_code, 400)

    def test_escrituras_de_usuario_exigen_csrf_real(self):
        cliente = APIClient(enforce_csrf_checks=True)
        cliente.force_login(self.admin)
        self.assertEqual(cliente.post("/api/usuarios/", {"username": "demo_csrf"}, format="json").status_code, 403)

    def test_cuenta_desactivada_no_puede_consumir_enlace(self):
        token = self.token()
        Usuario.objects.filter(pk=self.profe.pk).update(is_active=False)
        r = self.cliente.post("/api/recuperacion/confirmar/", {"token": token, "contrasena": NUEVA}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIsNone(SolicitudRestablecimiento.objects.get().fecha_uso)