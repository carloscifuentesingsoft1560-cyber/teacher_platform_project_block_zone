from django.conf import settings
from django.db import models
from django.db.models import Q, F
from deportistas.models import Registro, Deportista

class Inscripcion(Registro):
    deportista = models.ForeignKey(Deportista, on_delete=models.PROTECT, related_name="inscripciones")
    grupo = models.ForeignKey("organizacion.Grupo", on_delete=models.PROTECT, related_name="inscripciones")
    fecha_ingreso = models.DateField()
    fecha_salida = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=[(x,x) for x in ("activa","suspendida","finalizada")], default="activa")
    causa_salida = models.CharField(max_length=20, blank=True)
    inscripcion_anterior = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="continuacion")
    class Meta:
        ordering = ["-fecha_ingreso","-id"]
        indexes = [models.Index(fields=["grupo","fecha_ingreso"],name="inscripcion_grupo_fecha"), models.Index(fields=["deportista","fecha_ingreso"],name="inscripcion_persona_fecha")]
        constraints = [
            models.CheckConstraint(condition=Q(fecha_salida__isnull=True)|Q(fecha_salida__gt=F("fecha_ingreso")),name="inscripcion_fechas_validas"),
            models.CheckConstraint(condition=Q(estado__in=["activa","suspendida","finalizada"]),name="inscripcion_estado_valido"),
            models.CheckConstraint(condition=(Q(estado="finalizada",fecha_salida__isnull=False)&~Q(causa_salida=""))|(Q(estado__in=["activa","suspendida"],fecha_salida__isnull=True)&Q(causa_salida="")),name="inscripcion_cierre_coherente"),
            models.UniqueConstraint(fields=["deportista","grupo","fecha_ingreso"],name="inscripcion_inicio_unico"),
            models.UniqueConstraint(fields=["deportista","grupo"],condition=Q(fecha_salida__isnull=True),name="inscripcion_abierta_unica"),
        ]

class EventoInscripcion(models.Model):
    inscripcion = models.ForeignKey(Inscripcion,on_delete=models.PROTECT,related_name="eventos")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    tipo = models.CharField(max_length=32)
    estado_anterior = models.CharField(max_length=12,blank=True)
    estado_resultante = models.CharField(max_length=12)
    fecha_efectiva = models.DateField()
    registrado_en = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=240)
    class Meta:
        ordering = ["registrado_en","id"]

class ReservaCupo(models.Model):
    inscripcion = models.ForeignKey(Inscripcion,on_delete=models.PROTECT,related_name="reservas")
    autorizada_por = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="+")
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField(help_text="Último día con cupo reservado.")
    motivo = models.CharField(max_length=240)
    creada_en = models.DateTimeField(auto_now_add=True)
    liberada_en = models.DateTimeField(null=True,blank=True)
    liberada_por = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name="+")
    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(fecha_vencimiento__gte=F("fecha_inicio")),name="reserva_fechas_validas"),
            models.UniqueConstraint(fields=["inscripcion"],condition=Q(liberada_en__isnull=True),name="reserva_pendiente_unica"),
        ]

class Propuesta(Registro):
    tipo = models.CharField(max_length=12,choices=[(x,x) for x in ("inscripcion","traslado","nivel")])
    deportista = models.ForeignKey(Deportista,on_delete=models.PROTECT,related_name="propuestas")
    inscripcion_origen = models.ForeignKey(Inscripcion,null=True,blank=True,on_delete=models.PROTECT,related_name="propuestas")
    grupo_destino = models.ForeignKey("organizacion.Grupo",on_delete=models.PROTECT,related_name="+")
    fecha_efectiva = models.DateField()
    justificacion = models.CharField(max_length=240)
    estado = models.CharField(max_length=12,choices=[(x,x) for x in ("pendiente","aplicada","rechazada","cancelada")],default="pendiente")
    resuelta_por = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.PROTECT,related_name="+")
    resuelta_en = models.DateTimeField(null=True,blank=True)
    resolucion = models.CharField(max_length=240,blank=True)
    version_origen = models.PositiveIntegerField(null=True,blank=True)
    inscripcion_resultante = models.OneToOneField(Inscripcion,null=True,blank=True,on_delete=models.PROTECT,related_name="propuesta_aplicada")
    class Meta:
        ordering = ["-creado_en","-id"]
        constraints = [
            models.CheckConstraint(condition=Q(tipo__in=["inscripcion","traslado","nivel"]),name="propuesta_tipo_valido"),
            models.CheckConstraint(condition=Q(estado__in=["pendiente","aplicada","rechazada","cancelada"]),name="propuesta_estado_valido"),
            models.CheckConstraint(condition=Q(estado="pendiente",resuelta_por__isnull=True,resuelta_en__isnull=True)|(~Q(estado="pendiente")&Q(resuelta_por__isnull=False,resuelta_en__isnull=False)),name="propuesta_resolucion_coherente"),
            models.CheckConstraint(condition=Q(tipo="inscripcion",inscripcion_origen__isnull=True)|Q(tipo__in=["traslado","nivel"],inscripcion_origen__isnull=False),name="propuesta_origen_coherente"),
            models.UniqueConstraint(fields=["inscripcion_origen"],condition=Q(estado="pendiente",inscripcion_origen__isnull=False),name="propuesta_origen_pendiente_unica"),
            models.UniqueConstraint(fields=["deportista","grupo_destino"],condition=Q(estado="pendiente"),name="propuesta_destino_pendiente_unico"),
        ]


from .modelos_ascensos import (  # noqa: E402,F401
    ProgresionInstitucional, AfectacionInscripcion, ExcepcionPedagogica, EventoProgresion,
)
from .modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo  # noqa: E402,F401
