from rest_framework import mixins,viewsets,filters
from rest_framework.permissions import BasePermission,SAFE_METHODS
from .models import TipoDocumento
from .permisos import AccesoFase3,usuario_actual
from .documentos_serializers import TipoDocumentoSerializer
from .documentos_servicios import guardar_tipo

class GestionCatalogoDocumental(BasePermission):
    def has_permission(self,request,view):
        return request.method in SAFE_METHODS or (usuario_actual(request.user).tiene_rol("administrador"))

class TipoDocumentoVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,mixins.UpdateModelMixin,viewsets.GenericViewSet):
    permission_classes=[AccesoFase3,GestionCatalogoDocumental]
    serializer_class=TipoDocumentoSerializer
    lookup_field="codigo"
    http_method_names=["get","post","patch","head","options"]
    queryset=TipoDocumento.objects.all()
    filter_backends=[filters.SearchFilter]
    search_fields=["codigo","nombre"]
    def perform_create(self,serializer):
        serializer.instance=guardar_tipo(serializer,self.request.user)
    def perform_update(self,serializer):
        serializer.instance=guardar_tipo(serializer,self.request.user)
