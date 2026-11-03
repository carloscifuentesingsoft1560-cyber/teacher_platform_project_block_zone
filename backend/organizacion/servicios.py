from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from cuentas.models import Usuario
from auditoria.servicios import registrar
from .models import Asignacion, Horario


def bloquear_usuarios(actor=None, permitir_coordinador=False):
    # Orden global compartido por cambios de usuarios, grupos y asignaciones.
    # En PostgreSQL serializa la comprobación de cruces antes de escribir.
    usuarios = list(Usuario.objects.select_for_update().order_by("pk"))
    if actor is not None:
        actual = next((usuario for usuario in usuarios if usuario.pk == actor.pk), None)
        coordinador_valido = bool(
            permitir_coordinador and actual is not None and (actual.tiene_rol("coordinador"))
            and sum(u.is_active and (u.tiene_rol("coordinador")) for u in usuarios) == 1
        )
        if actual is None or not actual.is_active or not ((actual.tiene_rol("administrador")) or coordinador_valido):
            raise PermissionDenied("Tu cuenta ya no tiene permiso para esta operación.")
    return usuarios


def validar_horarios(horarios):
    if not horarios:
        raise ValidationError({"horarios": "Define al menos un horario."})
    for i, horario in enumerate(horarios):
        if horario["hora_fin"] <= horario["hora_inicio"]:
            raise ValidationError({"horarios": "La hora final debe ser posterior a la inicial; no se admiten franjas nocturnas partidas."})
        if horario["hora_inicio"].second or horario["hora_fin"].second or horario["hora_inicio"].microsecond or horario["hora_fin"].microsecond:
            raise ValidationError({"horarios": "Usa precisión de minutos."})
        for anterior in horarios[:i]:
            if horario["dia"] == anterior["dia"] and horario["hora_inicio"] < anterior["hora_fin"] and anterior["hora_inicio"] < horario["hora_fin"]:
                raise ValidationError({"horarios": "Hay horarios duplicados o solapados dentro del grupo."})


def validar_asignacion(asignacion):
    grupo = asignacion.grupo
    if not asignacion.usuario.is_active or (not asignacion.usuario.tiene_rol(asignacion.tipo)):
        raise ValidationError({"usuario": "La cuenta debe estar activa y su rol debe coincidir con el tipo de asignación."})
    if not grupo.activo:
        raise ValidationError({"grupo": "El grupo debe estar activo."})
    if asignacion.fecha_inicio < grupo.periodo.fecha_inicio or asignacion.fecha_inicio > grupo.periodo.fecha_fin:
        raise ValidationError({"fecha_inicio": "La fecha debe pertenecer al periodo del grupo."})
    if asignacion.fecha_fin and (asignacion.fecha_fin < asignacion.fecha_inicio or asignacion.fecha_fin > grupo.periodo.fecha_fin):
        raise ValidationError({"fecha_fin": "La fecha final debe estar dentro del periodo y no preceder al inicio."})
    fin = asignacion.fecha_fin or grupo.periodo.fecha_fin
    otras = Asignacion.objects.filter(usuario=asignacion.usuario).exclude(pk=asignacion.pk).select_related("grupo__periodo")
    for otra in otras:
        inicio_comun = max(asignacion.fecha_inicio, otra.fecha_inicio)
        fin_comun = min(fin, otra.fecha_fin or otra.grupo.periodo.fecha_fin)
        if inicio_comun > fin_comun:
            continue
        if otra.grupo_id == grupo.pk and otra.tipo == asignacion.tipo:
            raise ValidationError({"usuario": "Ya existe una asignación de esta persona al grupo con fechas solapadas."})
        if asignacion.tipo != "profesor" or otra.tipo != "profesor" or not otra.grupo.activo:
            continue
        for horario in grupo.horarios.filter(activo=True):
            for previo in otra.grupo.horarios.filter(activo=True, dia=horario.dia):
                primer_dia = inicio_comun + timedelta(days=(horario.dia - inicio_comun.weekday()) % 7)
                if primer_dia <= fin_comun and horario.hora_inicio < previo.hora_fin and previo.hora_inicio < horario.hora_fin:
                    raise ValidationError({"usuario": "El profesor tiene un cruce de horarios con otro grupo durante esta vigencia."})


@transaction.atomic
def guardar_grupo(serializer, actor):
    usuarios = bloquear_usuarios(actor, permitir_coordinador=True)
    actor_actual = next(u for u in usuarios if u.pk == actor.pk)
    anterior = serializer.instance
    if anterior:
        anterior = type(anterior).objects.select_for_update().get(pk=anterior.pk)
        serializer.instance = anterior
        from deportistas.permisos import esquema_disponible
        tiene_inscritos = esquema_disponible() and anterior.inscripciones.exists()
        if tiene_inscritos:
            from deportistas.permisos import documentos_disponibles, IdentificacionPendiente
            if not documentos_disponibles():
                raise IdentificacionPendiente()
        if anterior.asignaciones.exists() or tiene_inscritos:
            for campo in ("disciplina", "nivel", "periodo"):
                if campo in serializer.validated_data and getattr(anterior, campo + "_id") != serializer.validated_data[campo].pk:
                    raise ValidationError({campo: "El grupo tiene historial: crea otro grupo para cambiar su estructura."})
    for campo in ("disciplina", "nivel", "periodo"):
        referencia = serializer.validated_data.get(campo)
        if referencia is not None:
            referencia.refresh_from_db()
    serializer.validate(serializer.validated_data)
    horarios = serializer.validated_data.pop("horarios", None)
    campos = list(serializer.validated_data) + (["horarios"] if horarios is not None else [])
    grupo = serializer.save()
    if horarios is not None:
        grupo.horarios.filter(activo=True).update(activo=False)
        Horario.objects.bulk_create([Horario(grupo=grupo, **horario) for horario in horarios])
    if grupo.activo:
        for asignacion in grupo.asignaciones.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=timezone.localdate())).select_related("usuario", "grupo__periodo"):
            if asignacion.usuario.is_active:
                validar_asignacion(asignacion)
    from inscripciones.servicios import validar_grupo_con_inscritos
    validar_grupo_con_inscritos(grupo)
    registrar(actor, grupo, "modificar" if anterior else "crear", campos)
    return grupo


@transaction.atomic
def crear_asignacion(serializer, actor):
    usuarios = bloquear_usuarios(actor, permitir_coordinador=True)
    actor_actual = next(u for u in usuarios if u.pk == actor.pk)
    asignacion = Asignacion(**serializer.validated_data)
    # Releer estado después de adquirir bloqueos, no confiar en la validación previa.
    asignacion.usuario = Usuario.objects.get(pk=asignacion.usuario_id)
    asignacion.grupo = type(asignacion.grupo).objects.select_for_update().select_related("periodo").get(pk=asignacion.grupo_id)
    if (actor_actual.tiene_rol("coordinador") and not actor_actual.tiene_rol("administrador")) and asignacion.tipo != "profesor":
        raise PermissionDenied("Coordinación solo puede gestionar asignaciones de profesores.")
    validar_asignacion(asignacion)
    asignacion.save()
    registrar(actor, asignacion, "asignar", serializer.validated_data.keys())
    return asignacion


@transaction.atomic
def finalizar_asignacion(asignacion_id, fecha, actor):
    usuarios = bloquear_usuarios(actor, permitir_coordinador=True)
    actor_actual = next(u for u in usuarios if u.pk == actor.pk)
    asignacion = Asignacion.objects.select_for_update().get(pk=asignacion_id)
    if (actor_actual.tiene_rol("coordinador") and not actor_actual.tiene_rol("administrador")) and asignacion.tipo != "profesor":
        raise PermissionDenied("Coordinación solo puede finalizar asignaciones de profesores.")
    if fecha < asignacion.fecha_inicio or fecha > asignacion.grupo.periodo.fecha_fin:
        raise ValidationError({"fecha_fin": "La fecha debe estar dentro de la vigencia del grupo y no preceder al inicio."})
    if asignacion.fecha_fin and fecha >= asignacion.fecha_fin:
        raise ValidationError({"fecha_fin": "La asignación ya tiene esa fecha o una fecha final anterior; no se reabre ni se amplía."})
    asignacion.fecha_fin = fecha
    asignacion.save(update_fields=["fecha_fin"])
    registrar(actor, asignacion, "finalizar", ["fecha_fin"])
    return asignacion
