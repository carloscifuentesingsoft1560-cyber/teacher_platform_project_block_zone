from django.core.management.base import BaseCommand, CommandError
from cuentas.models import Usuario
from deportistas.permisos import esquema_disponible
from inscripciones.servicios import liberar_vencidas

class Command(BaseCommand):
    help="Libera reservas vencidas con actor autorizado; no borra inscripciones."
    def add_arguments(self,parser):
        parser.add_argument("--responsable",type=int,required=True)
    def handle(self,*args,**options):
        if not esquema_disponible():
            raise CommandError("Faltan migraciones autorizadas de Fase 3.")
        usuario=Usuario.objects.filter(pk=options["responsable"],is_active=True).first()
        if usuario is None:
            raise CommandError("Responsable no válido.")
        self.stdout.write(str(liberar_vencidas(usuario))+" reservas liberadas.")
