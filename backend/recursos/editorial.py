"""Comandos compartidos: autoridad actual, bloqueo, versión e idempotencia."""
import hashlib
import json
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from cuentas.models import Usuario
from cuentas.autorizacion import puede
from deportistas.servicios import Conflicto
from auditoria.servicios import registrar
from .permisos import exigir_editor, custodio


def bloquear(actor):
    list(Usuario.objects.select_for_update().order_by('pk'))
    exigir_editor(actor)


def editable(actor, version):
    exigir_editor(actor)
    if version._meta.model_name == 'mallaversion' and not (custodio(actor) or actor.tiene_rol('profesor')):
        raise PermissionDenied('Se requiere facultad curricular vigente.')
    if version.autor_id != actor.pk and not puede(actor, 'contenido.revisar'):
        raise PermissionDenied('No puedes editar este borrador.')
    if version.estado != 'borrador' or version.naturaleza == 'original_institucional':
        raise ValidationError('Crea una edición derivada; el contenido está congelado.')


def evento_modelo(version):
    return version.eventos.model


def huella(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def entrada_comando(actor, version, accion, datos, clave):
    h = huella({'version': str(version.uuid), 'accion': accion, 'datos': datos})
    previo = evento_modelo(version).objects.filter(actor=actor, clave=clave).first()
    if previo:
        if previo.version_id != version.pk or previo.accion != accion or previo.huella != h:
            raise Conflicto('La clave ya se utilizó con otro contenido.')
        return h, previo
    if datos.get('revision') != version.revision:
        raise Conflicto()
    return h, None


def registrar_evento(actor, version, accion, clave, h, motivo=''):
    evento_modelo(version).objects.create(actor=actor, version=version, accion=accion, clave=clave,
        huella=h, motivo=motivo, revision_resultante=version.revision)
    registrar(actor, version, 'contenido_' + accion, ['estado', 'revision'])


@transaction.atomic
def transicion(actor, version, accion, revision, clave, motivo=''):
    bloquear(actor)
    # Orden único: identidad y después edición; también usado al crear/derivar.
    type(version.identidad).objects.select_for_update().get(pk=version.identidad_id)
    v = type(version).objects.select_for_update().get(pk=version.pk)
    if accion in ('aprobar', 'devolver') and not puede(actor, 'contenido.revisar'):
        raise PermissionDenied('Solo el coordinador vigente revisa y publica.')
    if accion == 'retirar' and not custodio(actor) and v.autor_id != actor.pk:
        raise PermissionDenied('Retiro no autorizado.')
    if accion == 'proponer' and v.autor_id != actor.pk and not puede(actor, 'contenido.revisar'):
        raise PermissionDenied('Propuesta ajena.')
    h, previo = entrada_comando(actor, v, accion, {'revision': revision, 'motivo': motivo}, clave)
    if previo:
        return v
    if accion == 'proponer':
        if v.estado != 'borrador':
            raise ValidationError('Solo se propone un borrador.')
        validar_publicacion(v)
        v.estado = 'en_revision'
    elif accion == 'aprobar':
        if v.estado != 'en_revision':
            raise ValidationError('La edición debe estar en revisión.')
        validar_publicacion(v)
        type(v).objects.filter(identidad_id=v.identidad_id, vigente=True).exclude(pk=v.pk).update(vigente=False)
        v.estado = 'aprobado'
        v.vigente = True
        v.revisor = actor
        v.revisada_en = timezone.now()
    elif accion == 'devolver':
        if not puede(actor, 'contenido.revisar') or v.estado != 'en_revision' or not motivo.strip():
            raise PermissionDenied('Devolución requiere revisión vigente y observación.')
        v.estado = 'borrador'
        v.observaciones_revision = motivo
    elif accion == 'retirar':
        if not motivo.strip() or v.estado == 'retirado':
            raise ValidationError('Indica motivo para retirar una edición no retirada.')
        if not custodio(actor) and v.estado != 'borrador':
            raise PermissionDenied('Retiro institucional restringido.')
        v.estado = 'retirado'
        v.vigente = False
    else:
        raise ValidationError('Transición desconocida.')
    v.revision += 1
    v.save()
    registrar_evento(actor, v, accion, clave, h, motivo)
    return v


def validar_publicacion(v):
    from curriculo.models import MallaVersion
    from biblioteca.models import EjercicioVersion, MaterialDocenteVersion
    if not v.derechos.strip():
        raise ValidationError('Documenta procedencia y derechos de uso antes de proponer.')
    if v.naturaleza == 'original_institucional':
        raise ValidationError('Deriva una propuesta; el archivo original no se publica automáticamente.')
    if isinstance(v, MallaVersion):
        if not v.identidad.programa.formalizado:
            raise ValidationError('El programa está pendiente de formalización.')
        if not v.fases.exists() or not v.elementos.exists():
            raise ValidationError('Malla sin estructura o contenidos.')
        if v.semanas_esperadas and v.semanas.count() != v.semanas_esperadas:
            raise ValidationError('Cantidad de semanas incoherente.')
        from curriculo.models import ClasePrevista
        if v.clases_esperadas and ClasePrevista.objects.filter(semana__version=v).count() != v.clases_esperadas:
            raise ValidationError('Cantidad de clases incoherente.')
        if v.semanas_esperadas and list(v.semanas.values_list('ordinal',flat=True)) != list(range(1,v.semanas_esperadas+1)):
            raise ValidationError('Semanas no consecutivas.')
        if v.clases_esperadas and list(ClasePrevista.objects.filter(semana__version=v).order_by('ordinal').values_list('ordinal',flat=True)) != list(range(1,v.clases_esperadas+1)):
            raise ValidationError('Clases no consecutivas.')
        if v.semanas_esperadas == 40 and v.clases_esperadas == 80:
            esperado = [10,10,20] if v.identidad.programa.nivel.codigo == 'ludico' else [14,14,12]
            if [f.semanas.count() for f in v.fases.order_by('orden')] != esperado or any(s.clases.count()!=2 for s in v.semanas.all()):
                raise ValidationError('Distribución institucional de fases/clases incoherente.')
        if v.elementos.filter(texto__icontains='Escribir un objetivo').exists():
            raise ValidationError('Hay instrucciones pendientes en lugar de objetivos.')
    if isinstance(v, EjercicioVersion):
        if v.programas.exclude(nivel__disciplina_id=v.disciplina_id).exists():
            raise ValidationError('La disciplina no coincide con los programas.')
        if v.materiales.exclude(material__estado='aprobado', material__vigente=True).exists():
            raise ValidationError('Hay materiales pendientes de publicación o retirados.')
        for campo in ('objetivo', 'poblacion', 'metodologia', 'descripcion', 'riesgos', 'controles'):
            if not getattr(v, campo).strip():
                raise ValidationError({campo: 'Campo necesario para revisión.'})
        if not v.pasos.exists():
            raise ValidationError('Documenta los pasos de ejecución.')
        if not v.programas.exists() and not v.acceso_tecnico:
            raise ValidationError('Indica programas o acceso técnico.')
    if isinstance(v, MaterialDocenteVersion) and not (v.programas.exists() or v.acceso_tecnico):
        raise ValidationError('Indica destinatarios del material.')


@transaction.atomic
def derivar(actor, version, clave=None):
    bloquear(actor)
    from .permisos import versiones_visibles
    tipo = 'malla' if version._meta.model_name == 'mallaversion' else 'biblioteca'
    if not versiones_visibles(actor,type(version).objects.filter(pk=version.pk),tipo).exists():
        raise PermissionDenied('La fuente ya no está en tu ámbito.')
    type(version.identidad).objects.select_for_update().get(pk=version.identidad_id)
    original = type(version).objects.get(pk=version.pk)
    if clave is not None:
        existente = type(version).objects.filter(clave_derivacion=clave).first()
        if existente:
            if existente.derivada_de_id != original.pk or existente.autor_id != actor.pk:
                raise Conflicto('Clave de derivación ya utilizada.')
            return existente
    numero = type(version).objects.filter(identidad_id=original.identidad_id).aggregate(n=Max('numero'))['n'] + 1
    copia = type(version).objects.get(pk=original.pk)
    copia.pk = None
    import uuid
    copia.uuid = uuid.uuid4()
    copia.numero, copia.revision = numero, 1
    copia.estado, copia.vigente = 'borrador', False
    copia.naturaleza, copia.autor = 'propuesta_revisada', actor
    copia.revisor, copia.revisada_en = None, None
    copia.derivada_de = original
    copia.clave_derivacion = clave
    if hasattr(copia, 'original_cerrado'):
        copia.original_cerrado = False
    copia.save()
    if hasattr(copia, 'programas'):
        copia.programas.set(original.programas.all())
    if hasattr(copia, 'etiquetas'):
        copia.etiquetas.set(original.etiquetas.all())
    if original._meta.model_name == 'mallaversion':
        from curriculo.servicios import copiar_arbol
        copiar_arbol(original, copia)
    elif original._meta.model_name == 'ejercicioversion':
        for relacion in ('pasos', 'adaptaciones', 'exigencias', 'procedencias', 'materiales'):
            for hijo in getattr(original, relacion).all():
                hijo.pk = None
                hijo.version = copia
                hijo.save()
    registrar(actor, copia, 'contenido_derivar', ['derivada_de'])
    return copia
