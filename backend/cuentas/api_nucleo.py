from rest_framework import serializers, viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission
class EsAdministrador(BasePermission):
    def has_permission(self,request,view):
        return request.user.is_authenticated and request.user.tiene_rol("administrador")
from .models import Persona, EnlaceIdentidad, PertenenciaRol
from .servicios_roles import otorgar, revocar
from .servicios_identidad import acreditar, revocar_enlace
from auditoria.servicios import registrar


class Entrada(serializers.Serializer):
    def to_internal_value(self, data):
        if set(data)-set(self.fields):
            raise serializers.ValidationError({'non_field_errors':['Campos no permitidos.']})
        return super().to_internal_value(data)


class OtorgarRol(Entrada):
    rol=serializers.ChoiceField(choices=['administrador','coordinador','profesor','routesetter','deportista','acudiente'])
    motivo=serializers.CharField(max_length=240)


class RevocarRol(Entrada):
    pertenencia=serializers.IntegerField(min_value=1)
    version=serializers.IntegerField(min_value=1)
    motivo=serializers.CharField(max_length=240)


class RolLectura(serializers.ModelSerializer):
    class Meta:
        model=PertenenciaRol
        fields=('id','rol','vigente','fecha_inicio','fecha_fin','version')
        read_only_fields=fields


class RolesUsuarioMixin:
    @action(detail=True, methods=['get','post'])
    def roles(self,request,pk=None):
        u=self.get_object()
        if request.method=='GET':
            registrar(request.user,u,'consultar_roles')
            return Response(RolLectura(u.pertenencias.order_by('id'),many=True).data)
        entrada=OtorgarRol(data=request.data);entrada.is_valid(raise_exception=True)
        return Response(RolLectura(otorgar(request.user,u.pk,**entrada.validated_data)).data,status=201)

    @action(detail=True,methods=['post'],url_path='revocar-rol')
    def revocar_rol(self,request,pk=None):
        u=self.get_object();entrada=RevocarRol(data=request.data);entrada.is_valid(raise_exception=True)
        d=entrada.validated_data;get_object_or_404(u.pertenencias,pk=d['pertenencia'])
        return Response(RolLectura(revocar(request.user,d['pertenencia'],d['version'],d['motivo'])).data)


class AcreditarIdentidad(Entrada):
    identidad_contrastada=serializers.BooleanField()
    def validate_identidad_contrastada(self,v):
        if not v: raise serializers.ValidationError("Debes contrastar la identidad antes de acreditarla.")
        return v
    persona=serializers.PrimaryKeyRelatedField(queryset=Persona.objects.all(),allow_null=True,required=False)
    tipo=serializers.ChoiceField(choices=['usuario','deportista','acudiente'])
    perfil=serializers.IntegerField(min_value=1)
    evidencia=serializers.UUIDField()
    version_persona=serializers.IntegerField(min_value=1,required=False)


class RevocarIdentidad(Entrada):
    version=serializers.IntegerField(min_value=1)


class EnlaceLectura(serializers.ModelSerializer):
    version_persona=serializers.IntegerField(source='persona.version',read_only=True)
    class Meta:
        model=EnlaceIdentidad
        fields=('id','persona','version_persona','usuario','deportista','acudiente','vigente','version','acreditado_en','revocado_en')
        read_only_fields=fields


class PersonaLectura(serializers.ModelSerializer):
    nombre=serializers.SerializerMethodField()
    class Meta:
        model=Persona
        fields=('id','nombre','identificador','version')
        read_only_fields=fields

    def get_nombre(self,obj):
        for e in obj.enlaces.all():
            if not e.vigente: continue
            if e.usuario_id: return e.usuario.get_full_name() or e.usuario.username
            p=e.deportista if e.deportista_id else e.acudiente
            return p.nombres+' '+p.apellidos
        return 'Identidad institucional pendiente de enlace'


class PersonaVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    permission_classes=[IsAuthenticated,EsAdministrador]
    serializer_class=PersonaLectura
    queryset=Persona.objects.prefetch_related('enlaces__usuario','enlaces__deportista','enlaces__acudiente').order_by('id')
    http_method_names=['get','head','options']

    def list(self,request,*args,**kwargs):
        registrar(request.user,request.user,'consultar_personas')
        return super().list(request,*args,**kwargs)


class IdentidadVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    permission_classes=[IsAuthenticated,EsAdministrador]
    serializer_class=EnlaceLectura
    queryset=EnlaceIdentidad.objects.select_related('persona').order_by('id')
    http_method_names=['get','post','head','options']

    def list(self,request,*args,**kwargs):
        registrar(request.user,request.user,'consultar_identidades')
        return super().list(request,*args,**kwargs)

    def retrieve(self,request,*args,**kwargs):
        e=self.get_object();registrar(request.user,e,'consultar_identidad')
        return Response(self.get_serializer(e).data)

    def create(self,request):
        entrada=AcreditarIdentidad(data=request.data);entrada.is_valid(raise_exception=True);d=entrada.validated_data
        modelo=EnlaceIdentidad._meta.get_field(d['tipo']).remote_field.model
        get_object_or_404(modelo,pk=d['perfil'])
        e=acreditar(request.user,getattr(d.get('persona'),'pk',None),d['tipo'],d['perfil'],d['evidencia'],d.get('version_persona'))
        return Response(self.get_serializer(e).data,status=201)

    @action(detail=True,methods=['post'])
    def revocar(self,request,pk=None):
        e=self.get_object();entrada=RevocarIdentidad(data=request.data);entrada.is_valid(raise_exception=True)
        return Response(self.get_serializer(revocar_enlace(request.user,e.pk,entrada.validated_data['version'])).data)
