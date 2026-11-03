from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Persona, EnlaceIdentidad
from .servicios_roles import bloquear_admin
from auditoria.servicios import registrar


@transaction.atomic
def acreditar(actor, persona_id, tipo, perfil_id, evidencia, version=None):
    bloquear_admin(actor)
    import uuid
    if tipo not in ('usuario','deportista','acudiente') or not isinstance(evidencia,uuid.UUID) or evidencia.version!=4:
        raise ValidationError('Perfil o referencia de acreditación no admitidos.')
    if persona_id is None:
        persona=Persona.objects.create(creada_por=actor)
    else:
        persona=Persona.objects.select_for_update().get(pk=persona_id)
        from deportistas.servicios import Conflicto
        if persona.version!=version:raise Conflicto()
    modelo=EnlaceIdentidad._meta.get_field(tipo).remote_field.model
    perfil=modelo.objects.select_for_update().get(pk=perfil_id)
    if EnlaceIdentidad.objects.filter(vigente=True,**{tipo:perfil}).exists() or EnlaceIdentidad.objects.filter(persona=persona,vigente=True,**{tipo+'__isnull':False}).exists():
        raise ValidationError('Ya hay un enlace acreditado; no se fusionan identidades automáticamente.')
    enlace=EnlaceIdentidad.objects.create(persona=persona,acreditado_por=actor,evidencia=evidencia,**{tipo:perfil})
    persona.version+=1;persona.save(update_fields=['version'])
    registrar(actor,enlace,'acreditar_identidad',[tipo,'persona'])
    return enlace


@transaction.atomic
def revocar_enlace(actor, enlace_id, version):
    bloquear_admin(actor)
    e=EnlaceIdentidad.objects.select_for_update().get(pk=enlace_id)
    from deportistas.servicios import Conflicto
    if e.version!=version or not e.vigente:raise Conflicto()
    e.vigente=False;e.revocado_por=actor;e.revocado_en=timezone.now();e.version+=1;e.save()
    Persona.objects.filter(pk=e.persona_id).update(version=F('version')+1)
    registrar(actor,e,'revocar_identidad',['vigente'])
    return e
