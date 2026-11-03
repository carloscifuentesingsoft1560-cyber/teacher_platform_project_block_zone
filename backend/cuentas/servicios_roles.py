from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from .autorizacion import tiene_rol
from .models import Usuario, PertenenciaRol, EventoRol
from auditoria.servicios import registrar


def bloquear_admin(actor):
    # Mismo orden global usado por matrículas y ascensos; serializa revocación/escritura.
    list(Usuario.objects.select_for_update().order_by('pk'))
    if not tiene_rol(actor, 'administrador'):
        raise PermissionDenied('Se requiere administración vigente.')


@transaction.atomic
def otorgar(actor, usuario_id, rol, motivo):
    bloquear_admin(actor)
    if rol not in Usuario.Rol.values or not isinstance(motivo, str) or not motivo.strip() or len(motivo)>240:
        raise ValidationError('Rol o motivo no admitidos.')
    usuario = Usuario.objects.get(pk=usuario_id)
    if not usuario.is_active and rol == 'coordinador':
        raise ValidationError('Activa una cuenta con facultades antes del relevo institucional.')
    if usuario.pk == actor.pk:
        raise ValidationError('No puedes ampliar tus propias facultades.')
    if PertenenciaRol.objects.filter(usuario=usuario,rol=rol,vigente=True).exists():
        raise ValidationError('El rol ya está vigente.')
    if rol == 'coordinador' and PertenenciaRol.objects.filter(rol=rol,vigente=True).exists():
        raise ValidationError('Usa el relevo institucional del coordinador.')
    r = PertenenciaRol.objects.create(usuario=usuario,rol=rol)
    if not PertenenciaRol.objects.filter(usuario=usuario,rol=usuario.rol,vigente=True).exists():
        usuario.rol=rol
        usuario.save(update_fields=['rol'])
    EventoRol.objects.create(pertenencia=r,actor=actor,accion='otorgar',motivo=motivo.strip(),version=r.version)
    registrar(actor,r,'otorgar_rol',['rol','vigente'])
    if rol=='coordinador': registrar(actor,usuario,'coordinacion_inicio',['rol'])
    return r


@transaction.atomic
def revocar(actor, pertenencia_id, version, motivo):
    bloquear_admin(actor)
    r = PertenenciaRol.objects.select_for_update().select_related('usuario').get(pk=pertenencia_id)
    from deportistas.servicios import Conflicto
    if r.version != version or not r.vigente:
        raise Conflicto()
    if not isinstance(motivo,str) or not motivo.strip() or len(motivo)>240:
        raise ValidationError('Indica un motivo de hasta 240 caracteres.')
    if r.usuario_id == actor.pk:
        raise ValidationError('No puedes revocar tus propias facultades.')
    if r.rol == 'administrador' and not PertenenciaRol.objects.filter(rol=r.rol,vigente=True,usuario__is_active=True).exclude(pk=r.pk).exists():
        raise ValidationError('Debe conservarse al menos un administrador activo.')
    # Se preservan asignaciones como historia; pierden efecto al revocar el rol.
    r.vigente=False; r.fecha_fin=timezone.now();r.version+=1;r.save()
    EventoRol.objects.create(pertenencia=r,actor=actor,accion='revocar',motivo=motivo.strip(),version=r.version)
    registrar(actor,r,'revocar_rol',['vigente'])
    if r.rol=='coordinador': registrar(actor,r.usuario,'coordinacion_fin',['rol'])
    u=r.usuario
    if u.rol==r.rol:
        otra=PertenenciaRol.objects.filter(usuario=u,vigente=True).order_by('id').first()
        if otra:
            u.rol=otra.rol
        else:
            u.is_active=False
        u.save(update_fields=['rol','is_active'])
    if r.rol=='administrador' and (u.is_staff or u.is_superuser):
        u.is_staff=False;u.is_superuser=False;u.save(update_fields=['is_staff','is_superuser'])
    return r
