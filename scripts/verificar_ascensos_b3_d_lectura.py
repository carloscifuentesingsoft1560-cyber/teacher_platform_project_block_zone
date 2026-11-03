"""Verificación real B3-D: solo GET y transacciones READ ONLY; sin login ni fixtures."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Grupo
from organizacion.permisos import es_coordinador_activo
from inscripciones.models import Inscripcion
from inscripciones.modelos_ascensos import ProgresionInstitucional
from inscripciones.modelos_ejecucion import RevisionAdministrativa, ResultadoAdministrativo
from inscripciones.views_ascensos import AccesoAscensos
from inscripciones.api_ejecucion import instalacion_verificada

RAIZ=Path(__file__).resolve().parent.parent


def exigir(condicion, mensaje):
    if not condicion: raise RuntimeError(mensaje)


def ejecutar():
    instante=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    carpeta=RAIZ/'respaldos'/('verificacion_b3_d_'+instante)
    carpeta.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('inventario_solo_lectura',
        RAIZ/'respaldos/preparacion_0004_20261031T005057Z/verificacion.py')
    u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
    base=json.loads((RAIZ/'respaldos/aplicacion_0004_segundo_20261031T012845Z/inventario_despues.json').read_text(encoding='utf-8'))
    resultado={'fecha_utc':instante,'metodo':'APIClient con force_authenticate; solo GET y evaluación de permisos; sin login ni escritura de sesión',
        'respuestas':[],'operaciones_deportivas':0}
    with transaction.atomic():
        with connection.cursor() as c:c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        u.sesion_lectura()
        identidad=u.identidad()
        exigir((identidad['base'],identidad['esquema'],identidad['servidor'],identidad['puerto'])==
            ('zona_bloque','public','127.0.0.1',5432),'Conexión real no autorizada para lectura.')
        resultado['conexion']={k:v for k,v in identidad.items() if k!='directorio'}
        e=MigrationExecutor(connection)
        exigir(not e.migration_plan(e.loader.graph.leaf_nodes()),'Hay migraciones pendientes.')
        exigir(instalacion_verificada(),'0004 no está instalada/verificada.')
        antes=u.inventario()
        resultado['pendientes']=[]
        relevantes=['inscripciones_progresioninstitucional','inscripciones_eventoprogresion','inscripciones_afectacioninscripcion',
            'inscripciones_inscripcion','inscripciones_eventoinscripcion','inscripciones_reservacupo',
            'inscripciones_revisionadministrativa','inscripciones_resultadoadministrativo',
            'organizacion_grupo','organizacion_horario','organizacion_asignacion']
        exigir(all(antes['tablas'][t]==base['tablas'][t] for t in relevantes),'El historial relevante difiere de la instalación; revisar sin cambiar datos.')
        p=ProgresionInstitucional.objects.get(estado_decision='rechazada')
        exigir(p.decidida_por_id is not None and p.decidida_en is not None and bool(p.resolucion)
            and p.eventos.filter(tipo='rechazar_ascenso').exists(),'La propuesta rechazada perdió decisión o auditoría.')
        resultado['progresion']={'id':p.pk,'decision':'rechazada','eventos':p.eventos.count(),
            'decision_y_auditoria_identicas_a_instalacion':True}
        i=Inscripcion.objects.get(pk=18)
        exigir(i.estado=='activa' and i.fecha_salida is None and i.inscripcion_anterior_id is None
            and not Inscripcion.objects.filter(inscripcion_anterior=i).exists(),'La inscripción 18 no conserva su estado original sin traslado.')
        g=Grupo.objects.get(codigo='ESC-N1-001')
        exigir(i.grupo_id==g.pk,'La inscripción 18 cambió de grupo.')
        exigir(RevisionAdministrativa.objects.count()==0 and ResultadoAdministrativo.objects.count()==0,
            'Ya hay revisiones/resultados B3; no afirmar estado vacío.')
        resultado['inscripcion_18']={'activa':True,'sin_cierre':True,'sin_traslado':True,'grupo_codigo':g.codigo}
        resultado['consultas_vacias']={'revisiones':0,'resultados':0}
        actores={rol:Usuario.objects.get(rol=rol,is_active=True) for rol in ('administrador','coordinador','profesor')}
        exigir(es_coordinador_activo(actores['coordinador']),'Coordinador no vigente.')
        for rol,actor in actores.items():
            cliente=APIClient(enforce_csrf_checks=True)
            cliente.force_authenticate(actor)  # No crea sesión ni actualiza last_login.
            def get(ruta, esperado=200):
                respuesta=cliente.get('/api'+ruta,HTTP_HOST='127.0.0.1')
                resultado['respuestas'].append({'rol':rol,'ruta':ruta,'estado':respuesta.status_code})
                exigir(respuesta.status_code==esperado,'Respuesta inesperada '+rol+' '+ruta+': '+str(respuesta.status_code))
                return respuesta.data
            get('/ascensos/')
            if rol in ('administrador','coordinador'):
                get(f'/ascensos/{p.pk}/')
                datos=get(f'/ascensos/{p.pk}/ejecucion/')
                exigir(datos['ejecucion_habilitada'] and datos['estado_decision']=='rechazada'
                    and datos['revision'] is None and not any(f['puede_ejecutar'] for f in datos['afectaciones']),
                    'El estado administrativo vacío/rechazado se presenta incoherentemente.')
                for accion in ('revisiones','resultados'):
                    exigir(get(f'/ascensos/{p.pk}/{accion}/')['count']==0,'La consulta vacía no devuelve count=0.')
                cupos=get('/inscripciones/cupos/?grupo='+str(g.pk))
                exigir(cupos['cupo_maximo']==g.cupo_maximo,'La API de cupos difiere del modelo.')
                resultado['grupo_ESC_N1_001']={k:cupos[k] for k in ('cupo_maximo','ocupacion_actual','reservas_vigentes',
                    'disponibles_actuales','ocupacion_maxima','disponibles','fecha_corte')}
                get('/inscripciones/18/historial/')
            else:
                for accion in ('ejecucion','revisiones','resultados'):
                    get(f'/ascensos/{p.pk}/{accion}/',403)
            # Sin POST reales: la acción se evalúa con el mismo permiso efectivo de la vista.
            permiso=AccesoAscensos()
            ejecutar=permiso.has_permission(SimpleNamespace(user=actor),SimpleNamespace(action='ejecutar'))
            aprobar=permiso.has_permission(SimpleNamespace(user=actor),SimpleNamespace(action='aprobar'))
            exigir(ejecutar==(rol!='profesor') and aprobar==(rol=='coordinador'),'Autoridad por rol incorrecta.')
            resultado.setdefault('permisos_acciones',{})[rol]={'ejecutar':ejecutar,'aprobar':aprobar}
        exigir(u.inventario()==antes,'Las consultas alteraron registros/esquema.')
    # Instantánea fresca para detectar cambios también después de terminar las consultas.
    with transaction.atomic():
        with connection.cursor() as c:c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        u.sesion_lectura();despues=u.inventario()
        exigir(despues==antes,'El origen cambió durante la verificación; revisar evidencia.')
    resultado.update(correcto=True,huellas_antes_despues_identicas=True,historial_relevante_identico_a_instalacion=True,
        tablas=len(despues['tablas']),registros=sum(t['filas'] for t in despues['tablas'].values()))
    for nombre,datos in [('resultado.json',resultado),('inventario_antes.json',antes),('inventario_despues.json',despues)]:
        (carpeta/nombre).write_text(json.dumps(datos,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print('Lectura B3-D correcta: API, permisos, rechazo/auditoría, inscripción 18 y cupos intactos. Evidencia: '+carpeta.relative_to(RAIZ).as_posix(),flush=True)


if __name__=='__main__':ejecutar()
