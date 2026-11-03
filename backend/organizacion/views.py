from cuentas.autorizacion import usuarios_con_rol
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets, filters, serializers
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from auditoria.servicios import registrar
from cuentas.models import Usuario
from cuentas.serializers import UsuarioSerializer
from .models import Disciplina, Nivel, Periodo, Grupo, Asignacion
from .permisos import LecturaOOperacion, puede_gestionar_operacion, es_coordinador_activo
from .serializers import DisciplinaSerializer, NivelSerializer, PeriodoSerializer, GrupoSerializer, AsignacionSerializer, ProfesorOperativoSerializer
from .alcance import grupos_permitidos, asignaciones_permitidas, en_fecha
from .consultas import fecha_corte, filtrar_grupos
from .servicios import guardar_grupo, crear_asignacion, finalizar_asignacion, bloquear_usuarios

class LecturaOAdministracion(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and (request.method in ("GET", "HEAD", "OPTIONS") or (request.user.tiene_rol("administrador"))))

class SinEliminacion(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, LecturaOAdministracion]
    filter_backends = [filters.SearchFilter]
    search_fields = ["codigo", "nombre"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def guardar_catalogo(self, serializer, accion):
        with transaction.atomic():
            bloquear_usuarios(self.request.user)
            if serializer.instance:
                instancia = type(serializer.instance).objects.select_for_update().get(pk=serializer.instance.pk)
                serializer.instance = instancia
                if serializer.validated_data.get("activo") is False:
                    grupos = instancia.grupos if hasattr(instancia, "grupos") else None
                    if grupos is not None and grupos.filter(activo=True).exists():
                        raise ValidationError({"activo": "Desactiva primero los grupos activos asociados."})
            for campo in ("disciplina",):
                referencia = serializer.validated_data.get(campo)
                if referencia is not None:
                    referencia.refresh_from_db()
            serializer.validate(serializer.validated_data)
            objeto = serializer.save()
            registrar(self.request.user, objeto, accion, serializer.validated_data.keys())

    def perform_create(self, serializer):
        self.guardar_catalogo(serializer, "crear")

    def perform_update(self, serializer):
        self.guardar_catalogo(serializer, "modificar")

class DisciplinaVista(SinEliminacion):
    serializer_class = DisciplinaSerializer
    def get_queryset(self):
        datos = Disciplina.objects.all()
        if not puede_gestionar_operacion(self.request.user):
            datos = datos.filter(pk__in=grupos_permitidos(self.request.user).values("disciplina_id"))
        return datos

class NivelVista(SinEliminacion):
    serializer_class = NivelSerializer
    def get_queryset(self):
        datos = Nivel.objects.select_related("disciplina").all()
        if not puede_gestionar_operacion(self.request.user):
            datos = datos.filter(pk__in=grupos_permitidos(self.request.user).values("nivel_id"))
        disciplina = self.request.query_params.get("disciplina")
        return datos.filter(disciplina_id=disciplina) if disciplina and disciplina.isdigit() else datos

class PeriodoVista(SinEliminacion):
    serializer_class = PeriodoSerializer
    def get_queryset(self):
        datos = Periodo.objects.all()
        identificador = self.request.query_params.get("id")
        if identificador:
            if not identificador.isdigit():
                raise ValidationError({"id": "Identificador inválido."})
            datos = datos.filter(pk=identificador)
        if not puede_gestionar_operacion(self.request.user):
            datos = datos.filter(pk__in=grupos_permitidos(self.request.user).values("periodo_id"))
        return datos

class GrupoVista(SinEliminacion):
    permission_classes = [IsAuthenticated, LecturaOOperacion]

    def validar_campos_operativos(self):
        if (self.request.user.tiene_rol("coordinador") and not self.request.user.tiene_rol("administrador")):
            permitidos = {"codigo", "nombre", "disciplina", "nivel", "periodo", "activo", "cupo_maximo", "horarios"}
            if set(self.request.data) - permitidos:
                raise ValidationError("La solicitud contiene campos fuera de la gestión de grupos.")

    def create(self, request, *args, **kwargs):
        self.validar_campos_operativos()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self.validar_campos_operativos()
        return super().update(request, *args, **kwargs)
    serializer_class = GrupoSerializer
    def get_queryset(self):
        datos = filtrar_grupos(grupos_permitidos(self.request.user), self.request.query_params)
        profesor = self.request.query_params.get("profesor")
        if profesor:
            if not puede_gestionar_operacion(self.request.user):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("No puedes consultar asignaciones de otros profesores.")
            if not profesor.isdigit():
                raise ValidationError({"profesor": "Identificador inválido."})
            datos = datos.filter(pk__in=Asignacion.objects.filter(en_fecha(), tipo="profesor", usuario_id=profesor).values("grupo_id"))
        return datos

    def perform_create(self, serializer):
        guardar_grupo(serializer, self.request.user)

    def perform_update(self, serializer):
        guardar_grupo(serializer, self.request.user)

class AsignacionVista(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    def create(self, request, *args, **kwargs):
        if (request.user.tiene_rol("coordinador") and not request.user.tiene_rol("administrador")) and set(request.data) - {"grupo", "usuario", "tipo", "fecha_inicio", "fecha_fin"}:
            raise ValidationError("La solicitud contiene campos fuera de la asignación docente.")
        return super().create(request, *args, **kwargs)

    permission_classes = [IsAuthenticated, LecturaOOperacion]
    serializer_class = AsignacionSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        datos = asignaciones_permitidas(self.request.user)
        grupo = self.request.query_params.get("grupo")
        if grupo:
            if not grupo.isdigit():
                raise ValidationError({"grupo": "Identificador inválido."})
            datos = datos.filter(grupo_id=grupo)
        grupos = filtrar_grupos(grupos_permitidos(self.request.user), self.request.query_params)
        datos = datos.filter(grupo__in=grupos) if puede_gestionar_operacion(self.request.user) else datos
        estado = self.request.query_params.get("estado")
        if estado:
            if estado not in ("vigentes", "operativas"):
                raise ValidationError({"estado": "Estado inválido."})
            datos = datos.filter(en_fecha(fecha_corte(self.request.query_params)), tipo="profesor")
            if estado == "operativas":
                datos = datos.filter(usuario__is_active=True, grupo__activo=True, grupo__periodo__activo=True)
        return datos

    def perform_create(self, serializer):
        serializer.instance = crear_asignacion(serializer, self.request.user)

    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        asignacion = self.get_object()
        if (request.user.tiene_rol("coordinador") and not request.user.tiene_rol("administrador")) and set(request.data) - {"fecha_fin"}:
            raise ValidationError("La solicitud contiene campos fuera de la finalización.")
        campo = serializers.DateField()
        fecha = campo.run_validation(request.data.get("fecha_fin"))
        resultado = finalizar_asignacion(asignacion.pk, fecha, request.user)
        return Response(self.get_serializer(resultado).data)

class ProfesoresVista(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfesorOperativoSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["username", "first_name", "last_name"]
    def get_queryset(self):
        if (self.request.user.tiene_rol("profesor")) and not puede_gestionar_operacion(self.request.user):
            return Usuario.objects.filter(pk=self.request.user.pk)
        if not puede_gestionar_operacion(self.request.user):
            return Usuario.objects.none()
        datos = usuarios_con_rol("profesor").order_by("username")
        activo = self.request.query_params.get("activo")
        if activo is not None:
            if activo not in ("true", "false"):
                raise ValidationError({"activo": "Usa true o false."})
            datos = datos.filter(is_active=activo == "true")
        sin_grupo = self.request.query_params.get("sin_grupo")
        if sin_grupo is not None:
            if sin_grupo not in ("true", "false"):
                raise ValidationError({"sin_grupo": "Usa true o false."})
            grupos = filtrar_grupos(Grupo.objects.all(), self.request.query_params)
            ids = Asignacion.objects.filter(en_fecha(fecha_corte(self.request.query_params)),
                tipo="profesor", usuario__is_active=True, grupo__activo=True, grupo__periodo__activo=True,
                grupo__in=grupos).values("usuario_id")
            datos = datos.exclude(pk__in=ids) if sin_grupo == "true" else datos.filter(pk__in=ids)
        return datos

class CalendarioVista(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        try:
            desde = parse_date(request.query_params.get("desde", timezone.localdate().isoformat()))
            hasta = parse_date(request.query_params.get("hasta", (timezone.localdate() + timedelta(days=30)).isoformat()))
        except ValueError:
            raise ValidationError("Fechas inválidas.")
        if not desde or not hasta or hasta < desde or (hasta - desde).days > 92:
            raise ValidationError("El rango debe estar ordenado y no superar 92 días.")
        gestiona = puede_gestionar_operacion(request.user)
        grupos = Grupo.objects.filter(activo=True, periodo__activo=True).select_related("periodo").prefetch_related("horarios", "asignaciones")
        if not gestiona:
            ids = Asignacion.objects.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=desde), fecha_inicio__lte=hasta, usuario=request.user, tipo="profesor").values("grupo_id")
            grupos = grupos.filter(pk__in=ids)
            grupos = grupos.filter(pk__in=grupos_permitidos(request.user).values("pk"))
        eventos = []
        for grupo in grupos:
            inicio = max(desde, grupo.periodo.fecha_inicio)
            fin = min(hasta, grupo.periodo.fecha_fin)
            dia = inicio
            while dia <= fin:
                permitido = gestiona or any(a.usuario_id == request.user.pk and a.tipo == "profesor" and request.user.tiene_rol("profesor") and a.fecha_inicio <= dia and (a.fecha_fin is None or a.fecha_fin >= dia) for a in grupo.asignaciones.all())
                if permitido:
                    for horario in grupo.horarios.all():
                        if horario.activo and horario.dia == dia.weekday():
                            eventos.append({"id": str(horario.pk) + ":" + dia.isoformat(), "fecha": dia.isoformat(), "grupo": grupo.pk, "grupo_nombre": grupo.nombre, "hora_inicio": horario.hora_inicio.isoformat(timespec="minutes"), "hora_fin": horario.hora_fin.isoformat(timespec="minutes"), "duracion_minutos": horario.duracion_minutos})
                dia += timedelta(days=1)
        return Response({"tipo": "horarios_recurrentes", "eventos": sorted(eventos, key=lambda e: (e["fecha"], e["hora_inicio"], e["grupo"]))})
