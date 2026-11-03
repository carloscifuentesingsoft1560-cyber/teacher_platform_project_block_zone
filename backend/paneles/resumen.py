from cuentas.autorizacion import usuarios_con_rol
"""Estadísticas organizativas reales; no hay métricas de módulos futuros."""
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from cuentas.models import Usuario
from organizacion.models import Grupo, Asignacion, Periodo, Disciplina, Nivel
from organizacion.alcance import en_fecha


class FiltrosResumen(serializers.Serializer):
    fecha = serializers.DateField(required=False)
    periodo = serializers.PrimaryKeyRelatedField(queryset=Periodo.objects.all(), required=False)
    disciplina = serializers.PrimaryKeyRelatedField(queryset=Disciplina.objects.all(), required=False)
    nivel = serializers.PrimaryKeyRelatedField(queryset=Nivel.objects.all(), required=False)


def resumen_institucional(parametros):
    filtros = FiltrosResumen(data=parametros)
    filtros.is_valid(raise_exception=True)
    datos = filtros.validated_data
    fecha = datos.get("fecha", timezone.localdate())
    grupos = Grupo.objects.all()
    for campo in ("periodo", "disciplina", "nivel"):
        if campo in datos:
            grupos = grupos.filter(**{campo: datos[campo]})
    profesores = usuarios_con_rol("profesor")
    vigentes = Asignacion.objects.filter(en_fecha(fecha), tipo="profesor", grupo__in=grupos)
    operativas = vigentes.filter(usuario__is_active=True, grupo__activo=True, grupo__periodo__activo=True)
    sin_grupo = profesores.filter(is_active=True).exclude(pk__in=operativas.values("usuario_id")).count()
    periodos = Periodo.objects.all()
    if "periodo" in datos:
        periodos = periodos.filter(pk=datos["periodo"].pk)
    coordinadores = usuarios_con_rol("coordinador").filter(is_active=True).order_by("pk")
    cantidad = coordinadores.count()
    coordinador = coordinadores.first() if cantidad == 1 else None
    def por_campo(campo):
        modelo = Disciplina if campo == "disciplina" else Nivel
        catalogo = modelo.objects.all()
        if campo in datos:
            catalogo = catalogo.filter(pk=datos[campo].pk)
        if campo == "nivel" and "disciplina" in datos:
            catalogo = catalogo.filter(disciplina=datos["disciplina"])
        if campo == "disciplina" and "nivel" in datos:
            catalogo = catalogo.filter(pk=datos["nivel"].disciplina_id)
        conteos = {fila[campo + "_id"]: fila for fila in grupos.values(campo + "_id").annotate(
            total=Count("pk"), activos=Count("pk", filter=Q(activo=True)))}
        return [{
            "id": elemento.pk, "nombre": elemento.nombre,
            "total": conteos.get(elemento.pk, {}).get("total", 0),
            "activos": conteos.get(elemento.pk, {}).get("activos", 0),
        } for elemento in catalogo.order_by("nombre")]

    return {
        "fecha_corte": fecha.isoformat(),
        "estado_cuentas": "actual",
        "filtros": {campo: datos[campo].pk if campo in datos else None for campo in ("periodo", "disciplina", "nivel")},
        "profesores": {"activos": profesores.filter(is_active=True).count(), "inactivos": profesores.filter(is_active=False).count(), "sin_grupo": sin_grupo},
        "coordinacion": {"estado": "activo" if cantidad == 1 else "vacante" if cantidad == 0 else "inconsistente", "cantidad_activos": cantidad,
            "actual": {"id": coordinador.pk, "nombre": coordinador.get_full_name() or coordinador.username} if coordinador else None},
        "grupos": {"activos": grupos.filter(activo=True).count(), "inactivos": grupos.filter(activo=False).count()},
        "periodos": {"total": periodos.count(), "activos": periodos.filter(activo=True).count(), "en_curso": periodos.filter(fecha_inicio__lte=fecha, fecha_fin__gte=fecha).count()},
        "asignaciones": {"vigentes": vigentes.count(), "operativas": operativas.count()},
        "disciplinas": por_campo("disciplina"),
        "niveles": por_campo("nivel"),
    }
