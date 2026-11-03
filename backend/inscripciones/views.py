from django.utils import timezone
from rest_framework import mixins,viewsets,serializers,filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError
from deportistas.permisos import AccesoFase3,es_gestor,inscripciones_visibles,deportistas_visibles,usuario_actual
from deportistas.views import datos_accion
from organizacion.alcance import grupos_permitidos
from organizacion.models import Grupo
from django.db.models import Q
from rest_framework.exceptions import APIException
from .models import Propuesta
from .serializers import InscripcionSerializer,PropuestaSerializer,EventoSerializer,ReservaSerializer
from .servicios import inscribir,cambiar_estado,trasladar,proponer,resolver,liberar_vencidas,ocupacion_maxima,intervalo

class InscripcionVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    permission_classes=[AccesoFase3]
    serializer_class=InscripcionSerializer
    filter_backends=[filters.SearchFilter]
    search_fields=["deportista__nombres","deportista__apellidos","deportista__codigo_interno","grupo__nombre"]
    def get_queryset(self):
        datos=inscripciones_visibles(self.request.user)
        campos={"grupo":"grupo_id","deportista":"deportista_id","periodo":"grupo__periodo_id","nivel":"grupo__nivel_id","disciplina":"grupo__disciplina_id"}
        for campo,ruta in campos.items():
            valor=self.request.query_params.get(campo)
            if valor:
                if not valor.isdigit():
                    raise ValidationError({campo:"Identificador inválido."})
                datos=datos.filter(**{ruta:valor})
        estado=self.request.query_params.get("estado")
        if estado:
            if estado not in ("activa","suspendida","finalizada"):
                raise ValidationError({"estado":"Inválido."})
            datos=datos.filter(estado=estado)
        return datos
    def create(self,request,*args,**kwargs):
        if not es_gestor(request.user):
            raise PermissionDenied("El profesor propone; no ejecuta inscripciones.")
        return super().create(request,*args,**kwargs)
    def perform_create(self,serializer):
        d=serializer.validated_data
        serializer.instance=inscribir(d["deportista"],d["grupo"],d["fecha_ingreso"],self.request.user,d["motivo"])
    def accion_estado(self,request):
        if not es_gestor(request.user):
            raise PermissionDenied()
        objeto=cambiar_estado(self.get_object(),request.user,datos_accion(request),self.action)
        return Response(self.get_serializer(objeto).data)
    @action(detail=True,methods=["post"])
    def suspender(self,request,pk=None):
        return self.accion_estado(request)
    @action(detail=True,methods=["post"])
    def reanudar(self,request,pk=None):
        return self.accion_estado(request)
    @action(detail=True,methods=["post"])
    def retirar(self,request,pk=None):
        return self.accion_estado(request)
    @action(detail=True,methods=["post"])
    def trasladar(self,request,pk=None):
        if not es_gestor(request.user):
            raise PermissionDenied()
        d=datos_accion(request)
        if "grupo_destino" not in d or not d.get("motivo"):
            raise ValidationError("Indica destino y motivo.")
        objeto=trasladar(self.get_object(),d.pop("grupo_destino"),request.user,d)
        return Response(self.get_serializer(objeto).data)
    @action(detail=True,methods=["get"])
    def historial(self,request,pk=None):
        objeto=self.get_object()
        eventos=EventoSerializer(objeto.eventos.all(),many=True).data
        reservas=ReservaSerializer(objeto.reservas.all(),many=True).data
        if not es_gestor(request.user):
            eventos=[{k:v for k,v in e.items() if k not in ("motivo","actor")} for e in eventos]
            reservas=[{k:v for k,v in r.items() if k not in ("motivo","autorizada_por","liberada_por")} for r in reservas]
        return Response({"eventos":eventos,"reservas":reservas})
    @action(detail=False,methods=["post"],url_path="liberar-reservas")
    def liberar_reservas(self,request):
        if request.data:
            raise ValidationError("Esta acción no admite campos.")
        return Response({"liberadas":liberar_vencidas(request.user)})
    @action(detail=False,methods=["get"])
    def cupos(self,request):
        grupo=self.request.query_params.get("grupo","")
        if not grupo.isdigit():
            raise ValidationError({"grupo":"Identificador obligatorio."})
        from django.shortcuts import get_object_or_404
        g=get_object_or_404(grupos_permitidos(usuario_actual(request.user)),pk=grupo)
        inicio=serializers.DateField().run_validation(request.query_params.get("desde",str(timezone.localdate())))
        fin=serializers.DateField().run_validation(request.query_params.get("hasta",str(g.periodo.fecha_fin)))
        if fin<inicio or inicio<g.periodo.fecha_inicio or fin>g.periodo.fecha_fin:
            raise ValidationError("Intervalo fuera del periodo.")
        from datetime import timedelta
        datos=list(g.inscripciones.select_related('grupo__periodo').prefetch_related('reservas'))
        ocupacion=ocupacion_maxima(g,inicio,fin+timedelta(days=1),inscripciones=datos)
        hoy=timezone.localdate()
        activas=reservadas=0
        for inscripcion in datos:
            a,b=intervalo(inscripcion,inscripcion.reservas.all())
            if a<=hoy<b:
                if inscripcion.estado=='suspendida':
                    reservadas+=1
                else:
                    activas+=1
        actual=activas+reservadas
        return Response({"grupo":g.pk,"cupo_maximo":g.cupo_maximo,"ocupacion_maxima":ocupacion,"disponibles":max(0,g.cupo_maximo-ocupacion),
            "fecha_corte":hoy,"desde":inicio,"hasta":fin,"inscripciones_activas":activas,"reservas_vigentes":reservadas,
            "ocupacion_actual":actual,"disponibles_actuales":max(0,g.cupo_maximo-actual)})

class PropuestaVista(mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    permission_classes=[AccesoFase3]
    serializer_class=PropuestaSerializer
    filter_backends=[filters.SearchFilter]
    search_fields=["deportista__codigo_interno","grupo_destino__nombre","justificacion"]
    def get_queryset(self):
        datos=Propuesta.objects.select_related("grupo_destino__nivel","grupo_destino__periodo","inscripcion_origen__grupo__nivel")
        if not es_gestor(self.request.user):
            datos=datos.filter(creado_por=self.request.user,deportista__in=deportistas_visibles(self.request.user))
        estado=self.request.query_params.get("estado")
        if estado:
            if estado not in ("pendiente","aplicada","rechazada","cancelada"):
                raise ValidationError({"estado":"Inválido."})
            datos=datos.filter(estado=estado)
        return datos
    def get_serializer(self,*args,**kwargs):
        s=super().get_serializer(*args,**kwargs)
        if self.action=="create" and not es_gestor(self.request.user):
            s.fields["deportista"].queryset=deportistas_visibles(self.request.user)
            # Solo cambia el permiso de proponer: no se abre GrupoVista ni sus alumnos.
            s.fields["grupo_destino"].queryset=Grupo.objects.select_related('periodo','nivel','disciplina').all()
            s.fields["inscripcion_origen"].queryset=inscripciones_visibles(self.request.user)
        return s
    def perform_create(self,serializer):
        serializer.instance=proponer(serializer,self.request.user)

    @action(detail=False,methods=['get'],url_path='destinos')
    def destinos(self,request):
        from .compatibilidad_propuestas import contexto_docente, validar_destino, metadatos_destino
        actor=usuario_actual(request.user)
        if (not actor.tiene_rol('profesor')):
            raise PermissionDenied('La consulta de destinos corresponde al profesor que propone.')
        class Consulta(serializers.Serializer):
            tipo=serializers.ChoiceField(choices=['inscripcion','traslado','nivel'])
            deportista=serializers.PrimaryKeyRelatedField(queryset=deportistas_visibles(actor))
            inscripcion_origen=serializers.PrimaryKeyRelatedField(queryset=inscripciones_visibles(actor),required=False)
            fecha_efectiva=serializers.DateField(default=timezone.localdate)
            search=serializers.CharField(required=False,allow_blank=True,max_length=240)
            page=serializers.IntegerField(required=False,min_value=1)
        consulta=Consulta(data=request.query_params)
        consulta.is_valid(raise_exception=True)
        d=consulta.validated_data
        persona,origen=contexto_docente(actor,d['deportista'],d['tipo'],d['fecha_efectiva'],d.get('inscripcion_origen'))
        grupos=Grupo.objects.filter(activo=True,periodo__activo=True,nivel__activo=True,disciplina__activo=True,
            periodo__fecha_inicio__lte=d['fecha_efectiva'],periodo__fecha_fin__gte=d['fecha_efectiva']).select_related('periodo','nivel','disciplina').prefetch_related('horarios')
        if origen:
            grupos=grupos.exclude(pk=origen.grupo_id).filter(disciplina_id=origen.grupo.disciplina_id)
            grupos=grupos.exclude(nivel_id=origen.grupo.nivel_id) if d['tipo']=='nivel' else grupos.filter(nivel_id=origen.grupo.nivel_id)
        if d.get('search'):
            texto=d['search']
            grupos=grupos.filter(Q(codigo__icontains=texto)|Q(nombre__icontains=texto)|Q(periodo__nombre__icontains=texto)|Q(nivel__nombre__icontains=texto))
        compatibles=[]
        for grupo in grupos:
            try:
                validar_destino(persona,d['tipo'],d['fecha_efectiva'],origen,grupo)
            except (ValidationError,APIException):
                continue
            compatibles.append(grupo)
        pagina=self.paginate_queryset(compatibles)
        return self.get_paginated_response([metadatos_destino(g,d['fecha_efectiva']) for g in pagina])
    @action(detail=True,methods=["post"])
    def aprobar(self,request,pk=None):
        objeto=resolver(self.get_object(),request.user,datos_accion(request),True)
        return Response(self.get_serializer(objeto).data)
    @action(detail=True,methods=["post"])
    def rechazar(self,request,pk=None):
        objeto=resolver(self.get_object(),request.user,datos_accion(request),False)
        return Response(self.get_serializer(objeto).data)

    @action(detail=True,methods=["post"])
    def cancelar(self,request,pk=None):
        from .cancelacion import cancelar
        objeto=cancelar(self.get_object(),request.user,datos_accion(request))
        return Response(self.get_serializer(objeto).data)
