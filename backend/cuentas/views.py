from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .serializers import IngresoSerializer, UsuarioSerializer


class LimiteIngreso(SimpleRateThrottle):
    scope = "ingreso"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class CsrfVista(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class IngresarVista(APIView):
    """Protección CSRF explícita también para solicitudes anónimas de login."""
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LimiteIngreso]

    def post(self, request):
        datos = IngresoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario = authenticate(request=request._request, username=datos.validated_data["usuario"], password=datos.validated_data["contrasena"])
        if usuario is None:
            return Response({"detalle": "Usuario o contraseña incorrectos."}, status=400)
        login(request._request, usuario)
        request.session.cycle_key()
        return Response({"usuario": UsuarioSerializer(usuario).data, "csrfToken": get_token(request._request)})


class SesionVista(APIView):
    def get(self, request):
        return Response({"usuario": UsuarioSerializer(request.user).data})


class SalirVista(APIView):
    def post(self, request):
        logout(request._request)
        return Response({"detalle": "Sesión cerrada."})
