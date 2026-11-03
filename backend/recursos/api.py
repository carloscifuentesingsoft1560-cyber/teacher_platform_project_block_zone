import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.autorizacion import puede
from .models import ArchivoPrivado, FuenteDocumento, FuenteVersion, FragmentoFuente
from .permisos import AccesoContenido, custodio, exigir_editor, versiones_visibles
from .almacenamiento import subir, ruta
from .editorial import bloquear, editable, transicion, derivar


class Estricto(serializers.ModelSerializer):
    def to_internal_value(self, data):
        malos = set(data) - set(self.fields)
        malos |= {k for k in data if k in self.fields and self.fields[k].read_only}
        if malos:
            raise serializers.ValidationError({k: 'Campo no permitido.' for k in malos})
        return super().to_internal_value(data)


class ArchivoSerializer(Estricto):
    class Meta:
        model = ArchivoPrivado
        fields = ['id', 'uuid', 'nombre', 'sha256', 'bytes', 'tipo', 'finalidad']
        read_only_fields = fields


class FuenteSerializer(Estricto):
    class Meta:
        model = FuenteDocumento
        fields = ['id', 'uuid', 'titulo', 'referencia']
        read_only_fields = ['id', 'uuid']


class FuenteVersionSerializer(Estricto):
    class Meta:
        model = FuenteVersion
        fields = ['id', 'uuid', 'fuente', 'numero', 'archivo', 'referencia_externa', 'licencia', 'sha256']
        read_only_fields = ['id', 'uuid', 'sha256']

    def validate(self, data):
        a = data.get('archivo')
        if a and not (a.autor_id == self.context['request'].user.pk or custodio(self.context['request'].user)):
            raise serializers.ValidationError('Archivo no disponible.')
        if bool(a) == bool(data.get('referencia_externa')):
            raise serializers.ValidationError('Indica archivo o referencia, no ambos.')
        return data


class FragmentoSerializer(Estricto):
    class Meta:
        model = FragmentoFuente
        fields = ['id', 'fuente', 'localizador', 'hoja', 'celda', 'rango', 'texto_original', 'formula_original', 'contexto']
        read_only_fields = ['id']


class CustodiaVista(viewsets.GenericViewSet):
    permission_classes = [AccesoContenido]
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not custodio(request.user):
            raise PermissionDenied('Se requiere custodia institucional vigente.')

    def list(self, request):
        pagina = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def create(self, request):
        bloquear(request.user)
        if not custodio(request.user):
            raise PermissionDenied()
        s = self.get_serializer(data=request.data); s.is_valid(raise_exception=True)
        self.perform_create(s)
        return Response(s.data, status=201)

    def perform_create(self, s):
        s.save()


class FuentesVista(CustodiaVista):
    queryset = FuenteDocumento.objects.order_by('pk')
    serializer_class = FuenteSerializer
    def perform_create(self, s):
        s.save(autor=self.request.user)


class FuentesVersionVista(CustodiaVista):
    queryset = FuenteVersion.objects.order_by('pk')
    serializer_class = FuenteVersionSerializer
    def perform_create(self, s):
        a = s.validated_data.get('archivo')
        s.save(sha256=a.sha256 if a else '')

    @action(detail=True, methods=['get'])
    def descarga(self, request, pk=None):
        fuente = self.get_object()
        if not fuente.archivo_id: raise ValidationError('Fuente externa, sin copia descargable.')
        return descargar(fuente.archivo, request.user)


class FragmentosVista(CustodiaVista):
    queryset = FragmentoFuente.objects.order_by('pk')
    serializer_class = FragmentoSerializer


class ArchivosVista(viewsets.GenericViewSet):
    permission_classes = [AccesoContenido]
    serializer_class = ArchivoSerializer
    lookup_field = 'uuid'
    def get_queryset(self):
        qs = ArchivoPrivado.objects.filter(autor=self.request.user).order_by('pk')
        return qs if custodio(self.request.user) else qs.filter(finalidad='material_docente')

    def create(self, request):
        if set(request.data) - {'archivo', 'finalidad', 'declaracion'}:
            raise ValidationError('Campos no permitidos.')
        f = request.FILES.get('archivo')
        if not f:
            raise ValidationError('Adjunta un archivo.')
        a = subir(request.user, f, request.data.get('finalidad', 'material_docente'), request.data.get('declaracion') in (True, 'true'))
        return Response(ArchivoSerializer(a).data, status=201)

    @action(detail=True, methods=['get'])
    def descarga(self, request, uuid=None):
        a = self.get_object()
        return descargar(a, request.user)


def descargar(a, actor):
    from auditoria.servicios import registrar
    if not ruta(a).is_file():
        raise Http404
    registrar(actor, a, 'archivo_descargar', [])
    respuesta = FileResponse(ruta(a).open('rb'), content_type=a.tipo, as_attachment=True, filename=a.nombre)
    respuesta['Cache-Control'] = 'private, no-store'
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


class VersionVista(viewsets.GenericViewSet):
    permission_classes = [AccesoContenido]
    lookup_field = 'uuid'
    tipo = 'biblioteca'

    def get_queryset(self):
        return versiones_visibles(self.request.user, self.modelo.objects.select_related('identidad').order_by('identidad_id', '-numero'), self.tipo)

    def list(self, request):
        qs = self.filtrar(self.get_queryset())
        pagina = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(pagina, many=True).data)

    def filtrar(self, qs):
        estado = self.request.query_params.get('estado')
        if estado: qs = qs.filter(estado=estado)
        if self.request.query_params.get('mios') == 'true': qs = qs.filter(autor=self.request.user)
        if self.request.query_params.get('vigente') in ('true', 'false'):
            qs = qs.filter(vigente=self.request.query_params['vigente'] == 'true')
        return qs

    def retrieve(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        bloquear(request.user)
        objeto = self.get_object()
        type(objeto.identidad).objects.select_for_update().get(pk=objeto.identidad_id)
        v = self.modelo.objects.select_for_update().get(pk=objeto.pk)
        editable(request.user, v)
        from deportistas.servicios import Conflicto
        datos = dict(request.data)
        if datos.pop('revision', None) != v.revision:
            raise Conflicto()
        s = self.get_serializer(v, data=datos, partial=True); s.is_valid(raise_exception=True)
        s.save(revision=v.revision + 1)
        from auditoria.servicios import registrar
        registrar(request.user, v, 'contenido_editar', list(datos))
        return Response(s.data)

    @action(detail=True, methods=['post'])
    def derivar(self, request, uuid=None):
        if set(request.data) != {'clave'}:
            raise ValidationError('La derivación requiere una clave UUID de reintento.')
        try: clave = __import__('uuid').UUID(str(request.data['clave']))
        except (ValueError,TypeError): raise ValidationError('Clave UUID requerida.')
        v = derivar(request.user, self.get_object(), clave)
        return Response(self.get_serializer(v).data, status=201)

    def ejecutar(self, request, accion):
        if set(request.data) - {'revision', 'clave', 'motivo'}:
            raise ValidationError('Campos no permitidos.')
        try:
            clave = uuid.UUID(str(request.data['clave']))
        except (ValueError, KeyError, TypeError):
            raise ValidationError('Clave UUID requerida.')
        motivo = request.data.get('motivo', '')
        if not isinstance(motivo, str) or len(motivo) > 500:
            raise ValidationError('Motivo de hasta 500 caracteres.')
        v = transicion(request.user, self.get_object(), accion, request.data.get('revision'), clave, motivo)
        return Response(self.get_serializer(v).data)

    @action(detail=True, methods=['post'])
    def proponer(self, request, uuid=None): return self.ejecutar(request, 'proponer')
    @action(detail=True, methods=['post'])
    def aprobar(self, request, uuid=None): return self.ejecutar(request, 'aprobar')
    @action(detail=True, methods=['post'])
    def devolver(self, request, uuid=None): return self.ejecutar(request, 'devolver')
    @action(detail=True, methods=['post'])
    def retirar(self, request, uuid=None): return self.ejecutar(request, 'retirar')

    @action(detail=True, methods=['get'])
    def eventos(self, request, uuid=None):
        v = self.get_object()
        return Response(list(v.eventos.order_by('pk').values('accion', 'fecha', 'revision_resultante', 'motivo')))
