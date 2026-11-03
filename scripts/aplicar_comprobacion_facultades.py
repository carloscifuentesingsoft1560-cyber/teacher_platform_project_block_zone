"""Aplicación exclusiva de 0003 autorizada; respaldo restaurado antes de DDL.

Ejecutar con django_local.py shell/runpy. Rechaza repetición y planes distintos.
No imprime filas, referencias privadas ni credenciales.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

RAIZ=Path(__file__).resolve().parent.parent
OBJETIVO=('deportistas','0003_comprobacion_facultades')
SHA_APROBADO='eb74789677295641b97013087e14c391bb164ee18a5667bdfd939bc59d7dce54'
TABLA='deportistas_comprobacionfacultad'
RESTRICCIONES={'facultad_version_unica','facultad_metodo_valido','facultad_resultado_valido','facultad_revision_suficiente','facultad_vigencia_valida'}

# Reutilizar únicamente las utilidades de respaldo/restauración ya comprobadas.
# Importar este módulo no ejecuta su migración 0002.
spec=importlib.util.spec_from_file_location('respaldo_documental_util',RAIZ/'scripts/aplicar_identificacion_documental.py')
comun=importlib.util.module_from_spec(spec)
spec.loader.exec_module(comun)
exigir=comun.exigir
guardar=comun.guardar


def filtro(tabla):
    if tabla=='django_migrations':
        return " WHERE NOT (app='deportistas' AND name='0003_comprobacion_facultades')"
    if tabla=='django_content_type':
        return " WHERE NOT (app_label='deportistas' AND model='comprobacionfacultad')"
    if tabla=='auth_permission':
        return " WHERE content_type_id NOT IN (SELECT id FROM django_content_type WHERE app_label='deportistas' AND model='comprobacionfacultad')"
    return ''


def huellas(con,columnas):
    resultado={}
    q=connection.ops.quote_name
    with con.cursor() as c:
        for tabla,campos in sorted(columnas.items()):
            c.execute('SELECT row_to_json(t)::text FROM (SELECT '+','.join(q(f) for f in campos)+' FROM '+q(tabla)+filtro(tabla)+') t')
            filas=sorted(r[0] for r in c.fetchall())
            resultado[tabla]={'filas':len(filas),'sha256':hashlib.sha256(json.dumps(filas,ensure_ascii=False).encode()).hexdigest()}
    return resultado


# La restauración compara todas las columnas anteriores y excluye solo metadatos 0003.
comun.huellas=huellas


def plan_exclusivo():
    comun.destino()
    exigir(hashlib.sha256((RAIZ/'backend/deportistas/migrations/0003_comprobacion_facultades.py').read_bytes()).hexdigest()==SHA_APROBADO,'El archivo difiere del aprobado.')
    e=MigrationExecutor(connection)
    e.loader.check_consistent_history(connection)
    plan=e.migration_plan(e.loader.graph.leaf_nodes())
    exigir([(m.app_label,m.name,b) for m,b in plan]==[(*OBJETIVO,False)],'Plan distinto de la única migración autorizada.')
    m=plan[0][0]
    cantidades=dict(Counter(type(o).__name__ for o in m.operations))
    exigir(cantidades=={'CreateModel':1,'AddField':1,'AddConstraint':5,'RunPython':1} and len(m.operations)==8,'Inventario de ocho operaciones diferente.')
    exigir({o.constraint.name for o in m.operations if type(o).__name__=='AddConstraint'}==RESTRICCIONES,'Restricciones diferentes.')
    estado=e._create_project_state(with_applied_migrations=True)
    with connection.schema_editor(collect_sql=True,atomic=False) as editor:
        m.apply(estado,editor,collect_sql=True)
        # collect_sql omite RunPython; recoger también su SQL sin ejecutarlo.
        m.operations[-1].code(None,editor)
    sql='\n'.join(editor.collected_sql)
    exigir(not re.search(r'(?im)^\s*(DROP|DELETE|UPDATE|TRUNCATE)\s',sql),'SQL destructivo inesperado.')
    with connection.cursor() as c:
        c.execute("SELECT relname FROM pg_class WHERE relnamespace='public'::regnamespace")
        nombres={TABLA,TABLA+'_id_seq'}|set(re.findall(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+"([^"]+)"',sql,re.I))
        exigir(not {r[0] for r in c.fetchall()}&nombres,'Colisión de tabla, secuencia o índice.')
        c.execute("SELECT conname FROM pg_constraint WHERE connamespace='public'::regnamespace")
        exigir(not {r[0] for r in c.fetchall()}&(RESTRICCIONES|set(re.findall(r'CONSTRAINT\s+"([^"]+)"',sql))),'Colisión de restricción.')
        exigir('comprobacion_facultad_id' not in {f.name for f in connection.introspection.get_table_description(c,'deportistas_autorizacion')},'La columna nueva ya existe.')
        c.execute("SELECT COUNT(*) FROM pg_proc WHERE proname='zdb_facultad_historial_inmutable'")
        exigir(c.fetchone()[0]==0,'Colisión de función.')
        c.execute("SELECT COUNT(*) FROM pg_trigger WHERE tgname='zdb_facultad_no_modificar'")
        exigir(c.fetchone()[0]==0,'Colisión de trigger.')
        c.execute("SELECT COUNT(*) FROM django_content_type WHERE app_label='deportistas' AND model='comprobacionfacultad'")
        exigir(c.fetchone()[0]==0,'Metadatos nuevos ya presentes.')
        c.execute('SELECT facultad_para_autorizar FROM deportistas_vinculoacudiente WHERE id=3')
        exigir(c.fetchone()==('pendiente',),'El vínculo 3 no está pendiente; detener para revisión.')
    return e,plan,cantidades,sql


def verificar_esquema():
    with connection.cursor() as c:
        campos={f.name:f for f in connection.introspection.get_table_description(c,'deportistas_autorizacion')}
        exigir('comprobacion_facultad_id' in campos and campos['comprobacion_facultad_id'].null_ok,'Falta FK opcional.')
        claves=connection.introspection.get_constraints(c,'deportistas_autorizacion')
        exigir(any(r.get('foreign_key')==(TABLA,'id') and r['columns']==['comprobacion_facultad_id'] for r in claves.values()),'La FK no apunta al historial aprobado.')
        restricciones=connection.introspection.get_constraints(c,TABLA)
        for nombre in RESTRICCIONES:
            exigir(nombre in restricciones and (restricciones[nombre].get('check') or restricciones[nombre].get('unique')),'Falta restricción '+nombre)
        c.execute("SELECT COUNT(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='zdb_facultad_historial_inmutable' AND p.pronargs=0")
        exigir(c.fetchone()[0]==1,'Falta función de protección.')
        c.execute("SELECT t.tgenabled, t.tgtype, p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid=%s::regclass AND t.tgname='zdb_facultad_no_modificar'",[TABLA])
        exigir(c.fetchone()==('O',27,'zdb_facultad_historial_inmutable'),'Trigger distinto: debe ser ROW BEFORE UPDATE/DELETE habilitado.')
        c.execute('SELECT COUNT(*) FROM '+TABLA)
        exigir(c.fetchone()[0]==0,'Se crearon comprobaciones no autorizadas.')
        c.execute('SELECT COUNT(*) FROM deportistas_autorizacion WHERE comprobacion_facultad_id IS NOT NULL')
        exigir(c.fetchone()[0]==0,'Se acreditaron autorizaciones históricas automáticamente.')
        c.execute('SELECT facultad_para_autorizar FROM deportistas_vinculoacudiente WHERE id=3')
        exigir(c.fetchone()==('pendiente',),'El vínculo 3 cambió.')
        for tabla in (TABLA,'deportistas_autorizacion'):
            c.execute('SELECT COUNT(*) FROM pg_constraint WHERE conrelid=%s::regclass AND NOT convalidated',[tabla])
            exigir(c.fetchone()[0]==0,'Restricciones sin validar.')
            c.execute('SELECT COUNT(*) FROM pg_index WHERE indrelid=%s::regclass AND (NOT indisvalid OR NOT indisready)',[tabla])
            exigir(c.fetchone()[0]==0,'Índices inválidos.')
        c.execute("SELECT COUNT(*) FROM django_content_type WHERE app_label='deportistas' AND model='comprobacionfacultad'")
        exigir(c.fetchone()[0]==1,'Metadatos de contenido inesperados.')
        c.execute("SELECT codename FROM auth_permission WHERE content_type_id IN (SELECT id FROM django_content_type WHERE app_label='deportistas' AND model='comprobacionfacultad')")
        exigir(c.fetchall()==[('view_comprobacionfacultad',)],'Permisos de modelo inesperados.')


def ejecutar():
    e,plan,cantidades,sql=plan_exclusivo()
    instante=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    carpeta=RAIZ/'respaldos'/('facultades_aplicacion_'+instante)
    carpeta.mkdir(parents=True,exist_ok=False)
    ruta=carpeta/'manifiesto.json'
    archivo=carpeta/'zona_bloque_antes_facultades.dump'
    datos={'base':'zona_bloque','esquema':'public','fecha_utc':instante,'migracion':'.'.join(OBJETIVO),'sha256_migracion':SHA_APROBADO,
           'operaciones':cantidades,'restricciones':sorted(RESTRICCIONES),'estado':'preflight_correcto'}
    (carpeta/'plan.sql').write_text(sql,encoding='utf-8')
    confirmada=False
    print('Preflight correcto: zona_bloque/public; exclusivamente 0003; ocho operaciones; sin colisiones.',flush=True)
    try:
        with transaction.atomic():
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout='10s'")
                c.execute("SET LOCAL statement_timeout='120s'")
                tablas=connection.introspection.table_names()
                c.execute('LOCK TABLE '+','.join(connection.ops.quote_name(t) for t in sorted(tablas))+' IN SHARE MODE')
                columnas={t:[f.name for f in connection.introspection.get_table_description(c,t)] for t in tablas}
            e,plan,_,_=plan_exclusivo()
            aplicadas=set(MigrationRecorder(connection).applied_migrations())
            antes=huellas(connection,columnas)
            # Comparar también con la referencia de solo lectura de la implementación.
            previo=json.loads(sorted((RAIZ/'respaldos').glob('facultades_antes_*.json'))[-1].read_text(encoding='utf-8'))
            exigir(antes==previo['tablas'],'Los registros difieren de la referencia previa; detener sin aplicar.')
            datos.update(columnas_originales=columnas,huellas_antes=antes)
            guardar(ruta,datos)
            cfg=connection.settings_dict;env=os.environ.copy();env['PGPASSWORD']=cfg.get('PASSWORD') or ''
            try:
                comun.comando([comun.BIN/'pg_dump.exe','-h',cfg.get('HOST') or '127.0.0.1','-p',cfg.get('PORT') or 5432,
                    '-U',cfg['USER'],'-d','zona_bloque','--no-password','-Fc','-f',archivo],carpeta,'respaldo',env=env,timeout=180)
            finally:
                env.pop('PGPASSWORD',None)
            exigir(archivo.is_file() and archivo.stat().st_size>0,'Respaldo vacío.')
            toc=comun.comando([comun.BIN/'pg_restore.exe','--list',archivo],carpeta,'catalogo')
            (carpeta/'catalogo_respaldo.txt').write_bytes(toc.stdout)
            comun.comando([comun.BIN/'pg_restore.exe','--file',os.devnull,archivo],carpeta,'lectura_completa',timeout=180)
            datos.update(respaldo=archivo.relative_to(RAIZ).as_posix(),bytes=archivo.stat().st_size,
                sha256_respaldo=hashlib.sha256(archivo.read_bytes()).hexdigest(),lectura_completa=True)
            print('Respaldo nuevo leído completamente; iniciando restauración aislada antes de modificar el esquema.',flush=True)
            datos['recuperacion']=comun.restaurar_aislado(archivo,carpeta,columnas,antes)
            datos['estado']='respaldo_leido_y_restaurado';guardar(ruta,datos)
            exigir(hashlib.sha256(archivo.read_bytes()).hexdigest()==datos['sha256_respaldo'],'La integridad del respaldo cambió.')
            exigir(huellas(connection,columnas)==antes,'Cambios anteriores a la aplicación; detener.')
            plan_exclusivo()
            print('Restauración funcional confirmada: '+str(len(antes))+' tablas con conteos/huellas idénticos; clúster detenido.',flush=True)
            print('Respaldo:',datos['respaldo'],'SHA-256:',datos['sha256_respaldo'],flush=True)
            e.migrate([OBJETIVO],plan=plan)
            create_permissions(apps.get_app_config('deportistas'),verbosity=0,interactive=False,using=connection.alias,apps=apps)
            actuales=set(MigrationRecorder(connection).applied_migrations())
            exigir(actuales-aplicadas=={OBJETIVO} and aplicadas.issubset(actuales),'Registro de migraciones inesperado.')
            exigir(set(connection.introspection.table_names())==set(tablas)|{TABLA},'Inventario de tablas inesperado.')
            verificar_esquema()
            despues=huellas(connection,columnas)
            exigir(despues==antes,'Datos anteriores cambiaron; revertir migración.')
            final=MigrationExecutor(connection)
            exigir(not final.migration_plan(final.loader.graph.leaf_nodes()),'Hay migraciones pendientes.')
            datos.update(estado='verificada_dentro_transaccion',huellas_despues=despues,comprobaciones=0,
                autorizaciones_acreditadas_retroactivamente=0,vinculo_3='pendiente',metadatos_nuevos={'content_types':1,'permissions':1},pendientes=[])
        confirmada=True
        datos['estado']='aplicada_y_confirmada';guardar(ruta,datos)
    except Exception as error:
        datos.update(estado='incidencia_posterior_commit' if confirmada else 'detenida_transaccion_revertida',tipo_error=type(error).__name__)
        guardar(ruta,datos)
        if isinstance(error,RuntimeError):
            raise SystemExit(str(error))
        raise SystemExit('Proceso detenido; revisar manifiesto privado. Tipo: '+type(error).__name__)
    print('Aplicada exclusivamente deportistas.0003_comprobacion_facultades; ocho operaciones; cero pendientes.',flush=True)
    print('Tabla, FK opcional, cinco restricciones, función y trigger verificados; vínculo 3 y las 31 tablas anteriores intactos.',flush=True)
    print('Sin comprobaciones ficticias ni autorizaciones acreditadas retroactivamente. Manifiesto:',ruta.relative_to(RAIZ).as_posix(),flush=True)


if __name__=='__main__':
    ejecutar()
