from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Usuario
from .serializers import UsuarioSerializer
from .views_usuarios import EsAdministrador
from .coordinacion import coordinador_actual, eventos_cargo, relevar_coordinador


class RelevoSerializer(serializers.Serializer):
    usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    coordinador_actual = serializers.IntegerField(allow_null=True, min_value=1)


class CoordinacionVista(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, EsAdministrador]
    http_method_names = ["get", "post", "head", "options"]

    def list(self, request):
        actual = coordinador_actual()
        eventos = eventos_cargo()
        pagina = self.paginate_queryset(eventos)
        datos = pagina if pagina is not None else eventos
        personas = {u.pk: u for u in Usuario.objects.filter(pk__in=[e.identificador for e in datos])}
        historial = [{
            "id": e.pk, "accion": e.accion, "fecha": e.fecha,
            "usuario": e.identificador,
            "nombre": (personas[e.identificador].get_full_name() or personas[e.identificador].username) if e.identificador in personas else "Cuenta conservada en historial",
            "autorizado_por": e.actor.get_full_name() or e.actor.username,
        } for e in datos]
        respuesta = self.get_paginated_response(historial) if pagina is not None else Response({"results": historial})
        respuesta.data["actual"] = UsuarioSerializer(actual).data if actual else None
        return respuesta

    @action(detail=False, methods=["post"])
    def relevar(self, request):
        datos = RelevoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        entrante = relevar_coordinador(request.user, datos.validated_data["usuario"], datos.validated_data["coordinador_actual"])
        return Response({"actual": UsuarioSerializer(entrante).data, "detalle": "Cargo actualizado. Se conservó el historial y la cuenta saliente quedó desactivada."})
