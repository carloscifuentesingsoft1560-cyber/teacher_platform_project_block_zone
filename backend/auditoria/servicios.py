from .models import CambioAdministrativo

def registrar(actor, objeto, accion, campos=()):
    # Solo nombres de campos: no valores, contraseñas, tokens ni datos de contacto.
    CambioAdministrativo.objects.create(actor=actor, entidad=objeto._meta.label_lower,
        identificador=objeto.pk, accion=accion, campos=sorted(set(campos)))
