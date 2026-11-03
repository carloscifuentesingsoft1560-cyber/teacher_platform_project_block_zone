from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from cuentas.models import EventoAcceso


class PruebasAuditoria(TestCase):
    def setUp(self):
        cache.clear()
        self.usuario = get_user_model().objects.create_user(username="demo_auditoria", password="Clave-ficticia-473!")
        self.cliente = APIClient(enforce_csrf_checks=True)

    def token(self):
        return self.cliente.get("/api/autenticacion/csrf/").json()["csrfToken"]

    def test_ingreso_y_salida_guardan_actor_y_fecha(self):
        respuesta = self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": self.usuario.username, "contrasena": "Clave-ficticia-473!"},
            format="json", HTTP_X_CSRFTOKEN=self.token())
        self.assertEqual(respuesta.status_code, 200)
        self.cliente.post("/api/autenticacion/salir/", HTTP_X_CSRFTOKEN=self.token())
        eventos = EventoAcceso.objects.order_by("fecha")
        self.assertEqual(list(eventos.values_list("tipo", flat=True)), ["ingreso", "salida"])
        self.assertTrue(all(evento.usuario_id == self.usuario.pk and evento.fecha for evento in eventos))

    def test_intento_fallido_no_conserva_credenciales(self):
        self.cliente.post("/api/autenticacion/ingresar/",
            {"usuario": "nombre-no-guardado", "contrasena": "clave-no-guardada"},
            format="json", HTTP_X_CSRFTOKEN=self.token())
        evento = EventoAcceso.objects.get()
        self.assertEqual(evento.tipo, "fallo")
        self.assertIsNone(evento.usuario)
        self.assertEqual({campo.name for campo in evento._meta.fields}, {"id", "tipo", "fecha", "usuario"})
