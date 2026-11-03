from django.core.exceptions import ValidationError as ErrorModelo, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PlanSesion, TareaSesion
from .permisos import AccesoSesiones, sesiones_visibles, grupos_disponibles
from .serializers import CrearSesion, SesionLectura, EditarPlan, CancelarSesion
from .servicios import crear_sesion, comandar, _usuarios
from .curricular import programas_grupo, mallas_elegibles, ejercicios_elegibles
from curriculo.models import FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular
from rest_framework import serializers


class SesionVista(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, AccesoSesiones]
    serializer_class = SesionLectura
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        planes = PlanSesion.objects.select_related('malla_version', 'fase_curricular', 'semana', 'clase').order_by('numero').prefetch_related('competencias', Prefetch('tareas', queryset=TareaSesion.objects.select_related('ejercicio_version').order_by('orden')))
        datos = sesiones_visibles(self.request.user).prefetch_related(Prefetch('planes', queryset=planes)).order_by('-fecha', 'hora_inicio', 'pk')
        grupo = self.request.query_params.get('grupo')
        if grupo is not None:
            if not grupo.isdecimal() or int(grupo) < 1:
                raise ValidationError({'grupo': 'Identificador inválido.'})
            datos = datos.filter(grupo_id=int(grupo))
        return datos

    def ejecutar(self, funcion, **argumentos):
        try:
            return funcion(**argumentos)
        except ErrorModelo as error:
            raise ValidationError(getattr(error, 'message_dict', None) or error.messages)
        except ObjectDoesNotExist:
            # Referencias de contenido inexistentes tampoco revelan metadatos.
            raise ValidationError('Referencia no disponible.')

    @transaction.atomic
    def create(self, request):
        entrada = CrearSesion(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data.copy()
        profesor_id = datos.pop('profesor', request.user.pk)
        actor, _ = _usuarios(request.user, profesor_id)
        grupo = get_object_or_404(grupos_disponibles(actor, fecha=datos['fecha']).select_for_update(), pk=datos.pop('grupo'))
        sesion = self.ejecutar(crear_sesion, actor=actor, profesor_id=profesor_id, grupo_id=grupo.pk, **datos)
        return Response(SesionLectura(sesion).data, status=201)

    @transaction.atomic
    def cambiar(self, request, tipo, serializador):
        # Recuperación inicial por ámbito antes de leer IDs para bloquear.
        referencia = self.get_object()
        actor, _ = _usuarios(request.user, referencia.profesor_id)
        # Revalidación dentro de la transacción y tras bloquear facultades.
        referencia = get_object_or_404(sesiones_visibles(actor), pk=referencia.pk)
        entrada = serializador(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data.copy()
        version, clave = datos.pop('version'), datos.pop('clave')
        sesion = self.ejecutar(comandar, actor=actor, sesion_id=referencia.pk, version=version, clave=clave, operacion=tipo, datos=datos)
        return Response(SesionLectura(sesion).data)

    def partial_update(self, request, pk=None):
        """Editar crea una revisión completa; no reprograma ni cambia el padrón."""
        return self.cambiar(request, 'planificar', EditarPlan)

    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        return self.cambiar(request, 'cancelar', CancelarSesion)

    @action(detail=True, methods=['post'])
    def realizar(self, request, pk=None):
        self.get_object()
        raise PermissionDenied('Ejecución pendiente del contrato de autorización funcional de actividades.')

    @action(detail=True, methods=['get'], url_path='opciones-plan')
    def opciones_plan(self, request, pk=None):
        sesion = self.get_object()
        grupo = sesion.grupo
        tipo = request.query_params.get('tipo', 'programas')

        def identificador(nombre, requerido=False):
            valor = request.query_params.get(nombre)
            if valor is None and not requerido:
                return None
            return serializers.IntegerField(min_value=1).run_validation(valor)

        if tipo == 'programas':
            datos = programas_grupo(grupo).order_by('pk').values('id', 'uuid', 'nivel_id', 'modalidad')
        elif tipo == 'versiones':
            datos = mallas_elegibles(request.user, grupo).order_by('pk').values('id', 'uuid', 'numero', 'identidad_id', 'identidad__nombre', 'identidad__programa_id')
        elif tipo == 'ejercicios':
            datos = ejercicios_elegibles(request.user, grupo).order_by('pk').values('id', 'uuid', 'numero', 'nombre', 'objetivo', 'duracion_min', 'duracion_max')
        elif tipo in ('fases', 'semanas', 'clases', 'competencias'):
            version = identificador('malla_version', requerido=True)
            if not mallas_elegibles(request.user, grupo).filter(pk=version).exists():
                raise ValidationError('Versión curricular no disponible.')
            if tipo == 'fases':
                datos = FaseCurricular.objects.filter(version_id=version).order_by('orden').values('id', 'uuid', 'codigo', 'nombre', 'orden')
            elif tipo == 'semanas':
                consulta = SemanaCurricular.objects.filter(version_id=version)
                fase = identificador('fase')
                if fase:
                    consulta = consulta.filter(fase_id=fase)
                datos = consulta.order_by('ordinal').values('id', 'uuid', 'ordinal', 'fase_id')
            elif tipo == 'clases':
                consulta = ClasePrevista.objects.filter(semana__version_id=version)
                semana = identificador('semana')
                if semana:
                    consulta = consulta.filter(semana_id=semana)
                datos = consulta.order_by('ordinal').values('id', 'uuid', 'ordinal', 'semana_id')
            else:
                datos = ElementoCurricular.objects.filter(version_id=version, tipo='competencia').order_by('pk').values('id', 'uuid', 'clave_logica', 'texto', 'fase_id', 'semana_id', 'clase_id')
        else:
            raise ValidationError({'tipo': 'Selector no disponible.'})
        return self.get_paginated_response(list(self.paginate_queryset(datos)))

    @action(detail=False, methods=['get'])
    def grupos(self, request):
        datos = grupos_disponibles(request.user).order_by('nombre', 'pk').values('id', 'codigo', 'nombre', 'nivel_id', 'periodo_id')
        pagina = self.paginate_queryset(datos)
        return self.get_paginated_response(list(pagina))
