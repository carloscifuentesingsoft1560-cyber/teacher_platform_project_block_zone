from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from cuentas.permisos import TieneRolDelPanel
from organizacion.permisos import es_coordinador_activo
from rest_framework.exceptions import PermissionDenied
from .resumen import resumen_institucional


class ResumenVista(APIView):
    rol_requerido = None
    permission_classes = [IsAuthenticated, TieneRolDelPanel]

    def get(self, request):
        if self.rol_requerido == "coordinador" and not es_coordinador_activo(request.user):
            raise PermissionDenied("La coordinación activa no es válida.")
        return Response(resumen_institucional(request.query_params))
