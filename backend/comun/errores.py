from django.http import JsonResponse
from django.db import IntegrityError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def error_csrf(request, reason=""):
    return JsonResponse({"detalle": "La verificación de seguridad falló. Recarga e intenta de nuevo."}, status=403)


def manejar_excepcion(excepcion, contexto):
    if isinstance(excepcion, IntegrityError):
        return Response({"detalle": "La operación viola una restricción de integridad o duplica un registro."}, status=400)
    respuesta = exception_handler(excepcion, contexto)
    if respuesta is not None:
        datos = respuesta.data
        respuesta.data = {"detalle": datos.get("detail", "Revisa los datos de la solicitud.") if isinstance(datos, dict) else " ".join(str(valor) for valor in datos) if isinstance(datos, list) else "Solicitud inválida."}
        if isinstance(datos, dict) and "detail" not in datos:
            respuesta.data["errores"] = datos
    return respuesta
