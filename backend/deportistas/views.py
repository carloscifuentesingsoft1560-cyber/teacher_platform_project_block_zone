from django.db.models import Q
from rest_framework import mixins, viewsets, filters, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from organizacion.models import Grupo
from .models import Deportista, Acudiente, VinculoAcudiente, TipoAutorizacion, Autorizacion, PoliticaDatos
from .serializers import DeportistaSerializer, DeportistaProfesorSerializer, AcudienteSerializer, VinculoSerializer, TipoSerializer, AutorizacionSerializer, PoliticaSerializer
from .permisos import SoloGestion, AccesoFase3, es_gestor, deportistas_visibles, inscripciones_visibles
from .servicios import guardar, verificar_vinculo, revocar

class Accion(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(max_length=240,required=False)
    resolucion = serializers.CharField(max_length=240,required=False)
    fecha_vencimiento = serializers.DateField(required=False)
    grupo_destino = serializers.PrimaryKeyRelatedField(queryset=Grupo.objects.all(),required=False)
    def to_internal_value(self,data):
        if set(data)-set(self.fields):
            raise serializers.ValidationError("Campos no permitidos.")
        return super().to_internal_value(data)

def datos_accion(request):
    accion=request.parser_context["view"].action
    permitidos={"revocar":{"version","motivo"},
        "suspender":{"version","motivo","fecha_vencimiento"},"reanudar":{"version","motivo"},
        "retirar":{"version","motivo"},"trasladar":{"version","motivo","grupo_destino"},
        "aprobar":{"version","resolucion"},"rechazar":{"version","resolucion"},
        "cancelar":{"version","resolucion"}}
    if set(request.data)-permitidos.get(accion,set()):
        raise serializers.ValidationError("Campos fuera de la acción autorizada.")
    s=Accion(data=request.data)
    s.is_valid(raise_exception=True)
    return s.validated_data

class RegistroVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,mixins.UpdateModelMixin,viewsets.GenericViewSet):
    permission_classes=[AccesoFase3,SoloGestion]
    http_method_names=["get","post","patch","head","options"]
    filter_backends=[filters.SearchFilter]
    search_fields=["nombres","apellidos"]
    def get_queryset(self):
        if not es_gestor(self.request.user):
            raise PermissionDenied("Información reservada a gestión operativa.")
        return self.serializer_class.Meta.model.objects.all().order_by("pk")
    def perform_create(self,serializer):
        serializer.instance=guardar(serializer,self.request.user)
    def perform_update(self,serializer):
        serializer.instance=guardar(serializer,self.request.user)

class DeportistaVista(RegistroVista):
    def retrieve(self,request,*args,**kwargs):
        from auditoria.servicios import registrar
        objeto=self.get_object()
        registrar(request.user,objeto,'consultar_ficha')
        return Response(self.get_serializer(objeto).data)
    permission_classes=[AccesoFase3]
    serializer_class=DeportistaSerializer
    lookup_field="identificador_publico"
    search_fields=["nombres","apellidos","codigo_interno"]
    def get_queryset(self):
        datos=deportistas_visibles(self.request.user)
        for campo in ("grupo","periodo","disciplina","nivel"):
            valor=self.request.query_params.get(campo)
            if valor:
                if not valor.isdigit():
                    raise serializers.ValidationError({campo:"Identificador inválido."})
                ruta={"grupo":"grupo_id","periodo":"grupo__periodo_id","disciplina":"grupo__disciplina_id","nivel":"grupo__nivel_id"}[campo]
                ids=inscripciones_visibles(self.request.user).filter(**{ruta:valor}).values("deportista_id")
                datos=datos.filter(pk__in=ids)
        estado=self.request.query_params.get("estado")
        if estado:
            if estado not in ("activo","inactivo","archivado"):
                raise serializers.ValidationError({"estado":"Estado inválido."})
            datos=datos.filter(estado=estado)
        return datos.distinct()
    def get_serializer_class(self):
        return DeportistaSerializer if es_gestor(self.request.user) else DeportistaProfesorSerializer
    def create(self,request,*args,**kwargs):
        if not es_gestor(request.user):
            raise PermissionDenied()
        return super().create(request,*args,**kwargs)
    def update(self,request,*args,**kwargs):
        if not es_gestor(request.user):
            raise PermissionDenied()
        return super().update(request,*args,**kwargs)
    @action(detail=True,methods=["get"])
    def trayectoria(self,request,identificador_publico=None):
        from inscripciones.serializers import InscripcionSerializer
        persona=self.get_object()
        datos=inscripciones_visibles(request.user).filter(deportista=persona)
        pagina=self.paginate_queryset(datos)
        return self.get_paginated_response(InscripcionSerializer(pagina,many=True).data)

    @action(detail=True,methods=["post"],url_path="cambiar-documento")
    def cambiar_documento(self,request,identificador_publico=None):
        if not es_gestor(request.user):
            raise PermissionDenied()
        from .documentos_serializers import SolicitudDocumentoSerializer
        from .documentos_servicios import cambiar_documento
        datos=SolicitudDocumentoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        objeto=cambiar_documento(self.get_object(),request.user,datos.validated_data)
        return Response(self.get_serializer(objeto).data)

    @action(detail=True,methods=["get"],url_path="historial-documental")
    def historial_documental(self,request,identificador_publico=None):
        if not es_gestor(request.user):
            raise PermissionDenied()
        from .documentos_serializers import HistorialDocumentoSerializer
        pagina=self.paginate_queryset(self.get_object().cambios_documentales.all())
        return self.get_paginated_response(HistorialDocumentoSerializer(pagina,many=True).data)

    @action(detail=False,methods=["post"],url_path="buscar-documento")
    def buscar_documento(self,request):
        if not es_gestor(request.user):
            raise PermissionDenied()
        from .documentos_serializers import ConsultaDocumentoSerializer
        from .documentos_reglas import normalizar_identificacion
        s=ConsultaDocumentoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d=s.validated_data
        try:
            tipo,numero,pais=normalizar_identificacion(d["tipo_documento"].codigo,d["numero_documento"],d.get("pais_emisor"))
        except ValueError as error:
            raise serializers.ValidationError({"documento":str(error)})
        pagina=self.paginate_queryset(self.get_queryset().filter(tipo_documento_id=tipo,numero_documento=numero,pais_emisor=pais))
        return self.get_paginated_response(self.get_serializer(pagina,many=True).data)

class AcudienteVista(RegistroVista):
    serializer_class=AcudienteSerializer

class VinculoVista(RegistroVista):
    serializer_class=VinculoSerializer
    search_fields=[]
    def get_queryset(self):
        datos=super().get_queryset()
        persona=self.request.query_params.get("deportista")
        return datos.filter(deportista_id=persona) if persona and persona.isdigit() else datos
    @action(detail=True,methods=["post"])
    def verificar(self,request,pk=None):
        from .facultades import DecisionFacultad, comprobar_facultad, ComprobacionSerializer, exigir_esquema
        exigir_esquema()
        datos=DecisionFacultad(data=request.data)
        datos.is_valid(raise_exception=True)
        evento=comprobar_facultad(self.get_object(),request.user,datos.validated_data)
        return Response(ComprobacionSerializer(evento).data)

    @action(detail=True,methods=['get'],url_path='historial-facultades')
    def historial_facultades(self,request,pk=None):
        from .facultades import exigir_esquema, ComprobacionSerializer
        exigir_esquema()
        eventos=self.get_object().comprobaciones.select_related('tipo_autorizacion')
        return Response(ComprobacionSerializer(eventos,many=True).data)

class TipoVista(RegistroVista):
    serializer_class=TipoSerializer
    search_fields=["codigo","finalidad"]

class AutorizacionVista(RegistroVista):
    serializer_class=AutorizacionSerializer
    search_fields=[]
    def get_serializer_class(self):
        from .facultades import exigir_esquema
        exigir_esquema()
        return super().get_serializer_class()
    def get_queryset(self):
        from .facultades import exigir_esquema
        exigir_esquema()
        datos=super().get_queryset()
        persona=self.request.query_params.get("deportista")
        return datos.filter(deportista_id=persona) if persona and persona.isdigit() else datos
    @action(detail=True,methods=["post"])
    def revocar(self,request,pk=None):
        objeto=revocar(self.get_object(),request.user,datos_accion(request))
        return Response(self.get_serializer(objeto).data)

class PoliticaVista(RegistroVista):
    serializer_class=PoliticaSerializer
    search_fields=["codigo","finalidad"]
