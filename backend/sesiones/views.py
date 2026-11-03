from django.core.exceptions import ValidationError as ErrorModelo, ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from biblioteca.models import EjercicioVersion
from curriculo.models import MallaVersion
from recursos.permisos import versiones_visibles
from .models import Sesion
from .permisos import AccesoSesiones, sesiones_visibles, grupos_disponibles
from .serializers import CrearSesion, SesionLectura, EditarPlan, CancelarSesion
from .servicios import crear_sesion, comandar, _usuarios


class SesionVista(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, AccesoSesiones]
    serializer_class = SesionLectura
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        datos = sesiones_visibles(self.request.user).prefetch_related('planes__tareas').order_by('-fecha', 'hora_inicio', 'pk')
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

    def validar_contenido(self, actor, datos):
        malla = datos.get('malla_version_id')
        if malla and not versiones_visibles(actor, MallaVersion.objects.all(), 'malla').filter(pk=malla).exists():
            raise ValidationError('Referencia curricular no disponible.')
        for tarea in datos['tareas']:
            ejercicio = tarea.get('ejercicio_version_id')
            if ejercicio and not versiones_visibles(actor, EjercicioVersion.objects.all(), 'ejercicio').filter(pk=ejercicio).exists():
                raise ValidationError('Referencia de biblioteca no disponible.')

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
        if tipo == 'planificar':
            self.validar_contenido(actor, datos)
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

    @action(detail=False, methods=['get'])
    def grupos(self, request):
        datos = grupos_disponibles(request.user).order_by('nombre', 'pk').values('id', 'codigo', 'nombre', 'nivel_id', 'periodo_id')
        pagina = self.paginate_queryset(datos)
        return self.get_paginated_response(list(pagina))
