from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from cuentas.permisos import TieneRolDelPanel


class PanelVista(APIView):
    permission_classes = [IsAuthenticated, TieneRolDelPanel]
    rol_requerido = None

    def get(self, request):
        return Response({
            "rol": self.rol_requerido,
            "nombre": request.user.get_full_name() or request.user.username,
            "mensaje": "Tu espacio de trabajo está listo. Los módulos operativos se incorporarán en las siguientes fases.",
        })
