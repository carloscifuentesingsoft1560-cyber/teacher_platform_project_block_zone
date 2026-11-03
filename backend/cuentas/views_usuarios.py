from cuentas.autorizacion import usuarios_con_rol
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import mixins, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Usuario
from .api_nucleo import RolesUsuarioMixin
from .serializers_usuarios import AdministracionUsuarioSerializer, SolicitarRestablecimientoSerializer, ConfirmarRestablecimientoSerializer
from .servicios_usuarios import guardar_usuario
from .recuperacion import solicitar_restablecimiento, confirmar_restablecimiento
from .views import LimiteIngreso

class EsAdministrador(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and (request.user.tiene_rol("administrador")))

class LimiteRecuperacion(LimiteIngreso):
    scope = "recuperacion"

class UsuariosVista(RolesUsuarioMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = Usuario.objects.order_by("username")
    serializer_class = AdministracionUsuarioSerializer
    permission_classes = [IsAuthenticated, EsAdministrador]
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "first_name", "last_name", "email"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        datos = super().get_queryset()
        rol = self.request.query_params.get("rol")
        activo = self.request.query_params.get("activo")
        if rol:
            if rol not in Usuario.Rol.values:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"rol": "Rol inválido."})
            datos = datos.filter(pk__in=usuarios_con_rol(rol).values("pk"))
        if activo is not None:
            if activo not in ("true", "false"):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"activo": "Usa true o false."})
            datos = datos.filter(is_active=activo == "true")
        return datos

    def perform_create(self, serializer):
        guardar_usuario(serializer, self.request.user)

    def perform_update(self, serializer):
        guardar_usuario(serializer, self.request.user)

    @action(detail=True, methods=["post"], url_path="restablecer-acceso", throttle_classes=[LimiteRecuperacion])
    def restablecer_acceso(self, request, pk=None):
        usuario = self.get_object()
        datos = SolicitarRestablecimientoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        token, expira = solicitar_restablecimiento(usuario.pk, request.user, datos.validated_data["contrasena_actual"])
        # Ruta relativa para evitar inyección del encabezado Host.
        return Response({"ruta": "/restablecer-acceso#token=" + token, "fecha_expira": expira})

@method_decorator(csrf_protect, name="dispatch")
class ConfirmarRecuperacionVista(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LimiteRecuperacion]

    def post(self, request):
        datos = ConfirmarRestablecimientoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        confirmar_restablecimiento(**datos.validated_data)
        return Response({"detalle": "Acceso restablecido. Inicia sesión con tu nueva contraseña."})
