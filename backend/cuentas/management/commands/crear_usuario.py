from getpass import getpass
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from cuentas.models import Usuario


class Command(BaseCommand):
    help = "Crea una cuenta local con rol y contraseña interactiva; no permite contraseñas en argumentos."

    def add_arguments(self, parser):
        parser.add_argument("usuario")
        parser.add_argument("--rol", required=True, choices=Usuario.Rol.values)

    def handle(self, *args, **opciones):
        if opciones["rol"] == "coordinador":
            raise CommandError("La coordinación se designa desde el panel administrativo para conservar su historial.")
        if Usuario.objects.filter(username=opciones["usuario"]).exists():
            raise CommandError("Ese usuario ya existe. No se modificó.")
        cuenta = Usuario(username=opciones["usuario"], rol=opciones["rol"])
        contrasena = getpass("Contraseña (mínimo 12 caracteres): ")
        if contrasena != getpass("Repite la contraseña: "):
            raise CommandError("Las contraseñas no coinciden.")
        try:
            validate_password(contrasena, cuenta)
            cuenta.full_clean()
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error
        cuenta.set_password(contrasena)
        cuenta.save()
        self.stdout.write(self.style.SUCCESS("Cuenta creada. Para administrar Django utiliza createsuperuser."))
