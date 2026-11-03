from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

Usuario = get_user_model()
CLAVE = "Una-clave-ficticia-para-pruebas-451!"
ROLES = ("profesor", "coordinador", "administrador")


class PruebasAcceso(TestCase):
    @classmethod
    def setUpTestData(cls):
        for rol in ROLES:
            Usuario.objects.create_user(username="demo_" + rol, password=CLAVE, rol=rol)

    def setUp(self):
        cache.clear()
        self.cliente = APIClient(enforce_csrf_checks=True)

    def token(self, cliente=None):
        respuesta = (cliente or self.cliente).get("/api/autenticacion/csrf/")
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()["csrfToken"]

    def ingresar(self, rol="profesor", **extras):
        token = self.token()
        return self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "demo_" + rol, "contrasena": CLAVE}, format="json",
            HTTP_X_CSRFTOKEN=token, **extras)

    def test_anonimo_no_consulta_sesion_ni_paneles(self):
        for ruta in ["/api/autenticacion/sesion/"] + ["/api/paneles/" + rol + "/" for rol in ROLES]:
            with self.subTest(ruta=ruta):
                self.assertEqual(self.cliente.get(ruta).status_code, 403)

    def test_login_anonimo_exige_csrf(self):
        respuesta = self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "demo_profesor", "contrasena": CLAVE}, format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("detalle", respuesta.json())

    def test_csrf_incorrecto_rechazado(self):
        self.token()
        respuesta = self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "demo_profesor", "contrasena": CLAVE}, format="json",
            HTTP_X_CSRFTOKEN="x" * 64)
        self.assertEqual(respuesta.status_code, 403)

    def test_login_y_cookies_httponly(self):
        respuesta = self.ingresar()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"]["rol"], "profesor")
        self.assertNotIn("password", respuesta.json()["usuario"])
        self.assertTrue(respuesta.cookies["sessionid"]["httponly"])
        self.assertTrue(respuesta.cookies["csrftoken"]["httponly"])
        self.assertEqual(respuesta.cookies["sessionid"]["samesite"], "Lax")
        self.assertEqual(respuesta["Cache-Control"], "no-store, private")
        self.assertEqual(self.cliente.get("/api/autenticacion/sesion/").status_code, 200)

    def test_clave_incorrecta_e_inactivo_mismo_mensaje(self):
        token = self.token()
        respuesta = self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "demo_profesor", "contrasena": "incorrecta"}, format="json", HTTP_X_CSRFTOKEN=token)
        cuenta = Usuario.objects.get(username="demo_profesor")
        cuenta.is_active = False
        cuenta.save()
        inactivo = self.ingresar()
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(inactivo.status_code, 400)
        self.assertEqual(respuesta.json(), inactivo.json())

    def test_matriz_completa_de_roles_por_panel(self):
        for rol in ROLES:
            with self.subTest(rol=rol):
                self.cliente = APIClient(enforce_csrf_checks=True)
                self.assertEqual(self.ingresar(rol).status_code, 200)
                for panel in ROLES:
                    with self.subTest(panel=panel):
                        respuesta = self.cliente.get("/api/paneles/" + panel + "/")
                        self.assertEqual(respuesta.status_code, 200 if rol == panel else 403)

    def test_rol_solicitado_por_cliente_no_eleva_privilegios(self):
        self.ingresar()
        respuesta = self.cliente.get("/api/paneles/administrador/?rol=administrador",
                                    HTTP_X_ROL="administrador")
        self.assertEqual(respuesta.status_code, 403)

    def test_desactivar_cuenta_revoca_sesion_existente(self):
        self.ingresar()
        Usuario.objects.filter(username="demo_profesor").update(is_active=False)
        self.assertEqual(self.cliente.get("/api/paneles/profesor/").status_code, 403)

    def test_cambio_rol_se_aplica_a_sesion_existente(self):
        self.ingresar()
        Usuario.objects.filter(username="demo_coordinador").update(is_active=False)
        Usuario.objects.filter(username="demo_profesor").update(rol="coordinador")
        self.assertEqual(self.cliente.get("/api/paneles/profesor/").status_code, 403)
        self.assertEqual(self.cliente.get("/api/paneles/coordinador/").status_code, 200)

    def test_logout_exige_post_y_csrf_e_invalida_sesion(self):
        self.ingresar()
        self.assertEqual(self.cliente.get("/api/autenticacion/salir/").status_code, 405)
        self.assertEqual(self.cliente.post("/api/autenticacion/salir/").status_code, 403)
        respuesta = self.cliente.post("/api/autenticacion/salir/", HTTP_X_CSRFTOKEN=self.token())
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.cliente.get("/api/autenticacion/sesion/").status_code, 403)

    def test_login_rota_csrf_y_clave_de_sesion(self):
        self.cliente.force_login(Usuario.objects.get(username="demo_profesor"))
        sesion_anterior = self.cliente.cookies["sessionid"].value
        token_anterior = self.token()
        respuesta = self.ingresar()
        self.assertNotEqual(sesion_anterior, respuesta.cookies["sessionid"].value)
        self.assertNotEqual(token_anterior, respuesta.json()["csrfToken"])
        sesion_vieja = APIClient()
        sesion_vieja.cookies["sessionid"] = sesion_anterior
        self.assertEqual(sesion_vieja.get("/api/autenticacion/sesion/").status_code, 403)

    def test_origen_externo_rechazado(self):
        self.assertEqual(self.ingresar(HTTP_ORIGIN="https://sitio-ajeno.example").status_code, 403)

    def test_origen_local_autorizado(self):
        self.assertEqual(self.ingresar(HTTP_ORIGIN="http://127.0.0.1:5173").status_code, 200)

    def test_ingreso_solo_json_y_campos_requeridos(self):
        respuesta = self.cliente.post("/api/autenticacion/ingresar/", {}, format="json", HTTP_X_CSRFTOKEN=self.token())
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("errores", respuesta.json())

    def test_limite_de_intentos(self):
        token = self.token()
        for _ in range(10):
            respuesta = self.cliente.post("/api/autenticacion/ingresar/",
                {"usuario": "no_existe", "contrasena": "incorrecta"}, format="json", HTTP_X_CSRFTOKEN=token)
            self.assertEqual(respuesta.status_code, 400)
        respuesta = self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "no_existe", "contrasena": "incorrecta"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(respuesta.status_code, 429)

    def test_base_rechaza_rol_invalido(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.filter(username="demo_profesor").update(rol="otro")

    def test_superusuario_tiene_rol_administrador(self):
        usuario = Usuario.objects.create_superuser(username="demo_super", password=CLAVE)
        self.assertEqual(usuario.rol, "administrador")

    def test_staff_profesor_no_accede_admin(self):
        usuario = Usuario.objects.get(username="demo_profesor")
        usuario.is_staff = True
        usuario.save()
        self.cliente.force_login(usuario)
        respuesta = self.cliente.get("/admin/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/admin/login/", respuesta.url)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_cookies_secure_en_configuracion_https(self):
        respuesta = self.ingresar()
        self.assertTrue(respuesta.cookies["sessionid"]["secure"])
        self.assertTrue(respuesta.cookies["csrftoken"]["secure"])
