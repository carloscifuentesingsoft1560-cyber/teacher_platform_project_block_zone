from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


def fecha_corte(parametros):
    return serializers.DateField().run_validation(parametros["fecha"]) if "fecha" in parametros else timezone.localdate()


def filtrar_grupos(grupos, parametros):
    for campo in ("disciplina", "nivel", "periodo"):
        valor = parametros.get(campo)
        if valor:
            if not str(valor).isdigit():
                raise ValidationError({campo: "Identificador inválido."})
            grupos = grupos.filter(**{campo + "_id": valor})
    if "activo" in parametros:
        if parametros["activo"] not in ("true", "false"):
            raise ValidationError({"activo": "Usa true o false."})
        grupos = grupos.filter(activo=parametros["activo"] == "true")
    return grupos
