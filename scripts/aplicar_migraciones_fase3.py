"""Aplica exclusivamente Fase 3 autorizada, con respaldo integral y preservación.

Ejecutar mediante django_local.py shell. Nunca imprime credenciales o filas.
Rechaza repetición, reversión, otras migraciones o conflictos de esquema.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import CreateModel, AddIndex, AddConstraint
from django.db.migrations.recorder import MigrationRecorder

RAIZ = Path(__file__).resolve().parent.parent
APROBADAS = [("deportistas","0001_initial"),("inscripciones","0001_initial")]
TABLAS = {
    "deportistas_deportista","deportistas_acudiente","deportistas_vinculoacudiente",
    "deportistas_tipoautorizacion","deportistas_autorizacion","deportistas_politicadatos",
    "inscripciones_inscripcion","inscripciones_eventoinscripcion","inscripciones_reservacupo","inscripciones_propuesta",
}

def exigir(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)

def destino():
    exigir(connection.vendor=="postgresql" and connection.settings_dict["NAME"]=="zona_bloque","Destino configurado no autorizado.")
    with connection.cursor() as c:
        c.execute("SELECT current_database(),current_schema()")
        exigir(c.fetchone()==("zona_bloque","public"),"Destino efectivo no autorizado.")

def huellas(tablas):
    """Huellas solo de registros anteriores; excluye metadatos de las dos apps nuevas."""
    resultado={}
    with connection.cursor() as c:
        for tabla in sorted(tablas):
            filtro=""
            if tabla=="django_migrations":
                filtro=" WHERE NOT (app IN ('deportistas','inscripciones') AND name='0001_initial')"
            elif tabla=="django_content_type":
                filtro=" WHERE app_label NOT IN ('deportistas','inscripciones')"
            elif tabla=="auth_permission":
                filtro=" WHERE content_type_id IN (SELECT id FROM django_content_type WHERE app_label NOT IN ('deportistas','inscripciones'))"
            c.execute("SELECT row_to_json(t)::text FROM "+connection.ops.quote_name(tabla)+" t"+filtro)
            filas=sorted(r[0] for r in c.fetchall())
            resultado[tabla]={"filas":len(filas),"sha256":hashlib.sha256(json.dumps(filas,ensure_ascii=False).encode()).hexdigest()}
    return resultado

def escribir(ruta, datos):
    ruta.write_text(json.dumps(datos,indent=2,ensure_ascii=False),encoding="utf-8")

def inspeccionar_plan():
    e=MigrationExecutor(connection)
    e.loader.check_consistent_history(connection)
    plan=e.migration_plan(e.loader.graph.leaf_nodes())
    exigir([(m.app_label,m.name) for m,b in plan]==APROBADAS and not any(b for m,b in plan),"El plan difiere de las dos migraciones autorizadas.")
    contadores={t.__name__:sum(isinstance(o,t) for m,b in plan for o in m.operations) for t in (CreateModel,AddIndex,AddConstraint)}
    exigir(contadores=={"CreateModel":10,"AddIndex":3,"AddConstraint":22},"Inventario distinto del aprobado.")
    exigir(all(isinstance(o,(CreateModel,AddIndex,AddConstraint)) for m,b in plan for o in m.operations),"Operación no autorizada.")
    tablas={m.app_label+"_"+o.name.lower() for m,b in plan for o in m.operations if isinstance(o,CreateModel)}
    exigir(tablas==TABLAS,"Tablas inesperadas.")
    estado=e._create_project_state(with_applied_migrations=True)
    sql=[]
    for m,b in plan:
        with connection.schema_editor(collect_sql=True,atomic=False) as editor:
            estado=m.apply(estado,editor,collect_sql=True)
        sql.extend(editor.collected_sql)
    exigir(not any(re.search(r"\b(DROP|DELETE|TRUNCATE|UPDATE|INSERT)\b",s,re.I) for s in sql),"SQL de datos o destructivo inesperado.")
    indices={}
    restricciones={}
    for m,b in plan:
        for o in m.operations:
            if isinstance(o,AddIndex):
                indices[o.index.name]=m.app_label+"_"+o.model_name
            if isinstance(o,AddConstraint):
                restricciones[o.constraint.name]=m.app_label+"_"+o.model_name
    return e,plan,sql,indices,restricciones

def conflictos(sql,indices,restricciones):
    relaciones=set(TABLAS)|{t+"_id_seq" for t in TABLAS}|set(indices)
    nombres_restricciones=set(restricciones)
    for s in sql:
        relaciones.update(re.findall(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+"([^"]+)"',s,re.I))
        nombres_restricciones.update(re.findall(r'CONSTRAINT\s+"([^"]+)"',s,re.I))
    with connection.cursor() as c:
        c.execute("SELECT relname FROM pg_class WHERE relnamespace='public'::regnamespace")
        actuales={r[0] for r in c.fetchall()}
        exigir(not relaciones & actuales,"Colisión de tabla, secuencia o índice con el esquema existente.")
        exigir(not any(n.startswith(("deportistas_","inscripciones_")) for n in actuales),"Hay objetos previos inesperados de Fase 3.")
        c.execute("SELECT conname FROM pg_constraint WHERE connamespace='public'::regnamespace")
        exigir(not nombres_restricciones & {r[0] for r in c.fetchall()},"Colisión de nombre de restricción.")
        c.execute("SELECT COUNT(*) FROM django_content_type WHERE app_label IN ('deportistas','inscripciones')")
        exigir(c.fetchone()[0]==0,"Metadatos previos inesperados de Fase 3.")

def verificar_esquema(indices,restricciones):
    exigir(TABLAS.issubset(set(connection.introspection.table_names())),"Faltan tablas.")
    with connection.cursor() as c:
        cache={}
        for nombre,tabla in {**indices,**restricciones}.items():
            if tabla not in cache:
                cache[tabla]=connection.introspection.get_constraints(c,tabla)
            exigir(nombre in cache[tabla],"Falta índice/restricción prevista: "+nombre)
            info=cache[tabla][nombre]
            if nombre in indices:
                exigir(info.get("index"),"Objeto no es índice: "+nombre)
            else:
                exigir(info.get("check") or info.get("unique"),"Restricción incorrecta: "+nombre)
        c.execute("""SELECT COUNT(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid
          WHERE t.relnamespace='public'::regnamespace AND t.relname=ANY(%s)
          AND (NOT i.indisvalid OR NOT i.indisready)""",[sorted(TABLAS)])
        exigir(c.fetchone()[0]==0,"Índice nuevo no válido/listo.")
        c.execute("""SELECT COUNT(*) FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
          WHERE t.relnamespace='public'::regnamespace AND t.relname=ANY(%s) AND NOT c.convalidated""",[sorted(TABLAS)])
        exigir(c.fetchone()[0]==0,"Restricción no validada.")
        for tabla in sorted(TABLAS):
            c.execute("SELECT COUNT(*) FROM "+connection.ops.quote_name(tabla))
            exigir(c.fetchone()[0]==0,"Tabla nueva contiene registros inesperados.")

def ejecutar():
    destino()
    e,plan,sql,indices,restricciones=inspeccionar_plan()
    conflictos(sql,indices,restricciones)
    viejas=set(connection.introspection.table_names())
    aplicadas=set(MigrationRecorder(connection).applied_migrations())
    instante=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    carpeta=RAIZ/"respaldos"
    carpeta.mkdir(exist_ok=True)
    archivo=carpeta/("zona_bloque_antes_fase3_"+instante+".dump")
    manifiesto=carpeta/("fase3_"+instante+".json")
    exigir(not archivo.exists() and not manifiesto.exists(),"No se sobrescribe respaldo existente.")
    datos={"base":"zona_bloque","esquema":"public","fecha_utc":instante,
        "migraciones":[".".join(t) for t in APROBADAS],"estado":"preflight_correcto",
        "tablas_anteriores":sorted(viejas),"tablas_nuevas":sorted(TABLAS),
        "indices_explicitos":indices,"restricciones_explicitas":restricciones,
        "sql_sha256":hashlib.sha256("\n".join(sql).encode()).hexdigest(),
        "archivos_migracion_sha256":{a+"."+n:hashlib.sha256((RAIZ/"backend"/a/"migrations"/(n+".py")).read_bytes()).hexdigest() for a,n in APROBADAS}}
    print("Preflight correcto: PostgreSQL zona_bloque/public; solo dos migraciones autorizadas.")
    print("Conflictos revisados: tablas, secuencias, índices, restricciones y metadatos; ninguno.")
    try:
        with transaction.atomic():
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout='10s'")
                c.execute("SET LOCAL statement_timeout='90s'")
                c.execute("LOCK TABLE "+", ".join(connection.ops.quote_name(t) for t in sorted(viejas))+" IN SHARE MODE")
            destino()
            inspeccionar_plan()
            conflictos(sql,indices,restricciones)
            antes=huellas(viejas)
            datos["huellas_antes"]=antes
            escribir(manifiesto,datos)
            cfg=connection.settings_dict
            entorno=os.environ.copy()
            entorno["PGPASSWORD"]=cfg.get("PASSWORD") or ""
            binarios=Path(os.getenv("ZDB_LIBPQ_DIR","C:/Program Files/PostgreSQL/17/bin"))
            args=["--host",str(cfg.get("HOST") or "127.0.0.1"),"--port",str(cfg.get("PORT") or "5432"),
                "--username",str(cfg["USER"]),"--dbname","zona_bloque","--no-password"]
            r=subprocess.run([str(binarios/"pg_dump.exe"),*args,"--format=custom","--file",str(archivo)],env=entorno,capture_output=True,timeout=180)
            entorno.pop("PGPASSWORD",None)
            exigir(r.returncode==0 and archivo.exists() and archivo.stat().st_size>0,"Respaldo no completado; no se migra.")
            r=subprocess.run([str(binarios/"pg_restore.exe"),"--list",str(archivo)],capture_output=True,timeout=60)
            exigir(r.returncode==0 and b"; Archive created at" in r.stdout,"Catálogo de respaldo inválido.")
            r=subprocess.run([str(binarios/"pg_restore.exe"),"--file",os.devnull,str(archivo)],capture_output=True,timeout=180)
            exigir(r.returncode==0,"Lectura completa del respaldo fallida.")
            datos.update(estado="respaldo_verificado",respaldo=archivo.relative_to(RAIZ).as_posix(),
                bytes=archivo.stat().st_size,sha256=hashlib.sha256(archivo.read_bytes()).hexdigest(),
                catalogo_verificado=True,lectura_completa_verificada=True)
            escribir(manifiesto,datos)
            print("Nuevo respaldo leído completamente:",datos["respaldo"])
            print("Bytes:",datos["bytes"],"SHA-256:",datos["sha256"])
            exigir(huellas(viejas)==antes,"Registros cambiaron antes de aplicar; operación detenida.")
            e.migrate(APROBADAS,plan=plan)
            # Metadatos estándar únicamente de los modelos nuevos; no se conceden privilegios.
            for etiqueta in ("deportistas","inscripciones"):
                create_permissions(apps.get_app_config(etiqueta),verbosity=0,interactive=False,using=connection.alias,apps=apps)
            despues=set(MigrationRecorder(connection).applied_migrations())
            exigir(despues-aplicadas==set(APROBADAS) and not aplicadas-despues,"Registro de migraciones inesperado.")
            verificar_esquema(indices,restricciones)
            exigir(huellas(viejas)==antes,"Cambios en registros anteriores: se revierte el conjunto.")
            with connection.cursor() as c:
                c.execute("SELECT COUNT(*) FROM django_content_type WHERE app_label IN ('deportistas','inscripciones')")
                tipos=c.fetchone()[0]
                c.execute("""SELECT COUNT(*) FROM auth_permission p JOIN django_content_type c ON c.id=p.content_type_id
                    WHERE c.app_label IN ('deportistas','inscripciones')""")
                permisos=c.fetchone()[0]
                exigir((tipos,permisos)==(10,40),"Metadatos nuevos inesperados.")
            final=MigrationExecutor(connection)
            exigir(not final.migration_plan(final.loader.graph.leaf_nodes()),"Quedan migraciones pendientes.")
            datos.update(estado="verificada_dentro_transaccion",registros_anteriores_identicos=True,
                tipos_contenido_nuevos=tipos,permisos_modelo_nuevos=permisos,
                permisos_concedidos_a_personal=0,tablas_nuevas_vacias=True)
    except Exception as error:
        datos.update(estado="detenida_sin_confirmar_migraciones",tipo_error=type(error).__name__)
        escribir(manifiesto,datos)
        if isinstance(error,RuntimeError):
            raise SystemExit(str(error))
        raise SystemExit("Operación detenida y transacción revertida; consultar estado privado. Tipo: "+type(error).__name__)
    datos.update(estado="aplicadas_y_confirmadas",pendientes=[])
    escribir(manifiesto,datos)
    print("Aplicadas exclusivamente deportistas.0001_initial e inscripciones.0001_initial.")
    print("10 tablas vacías, 3 índices y 22 restricciones explícitas verificados. Cero pendientes.")
    print("Todos los registros anteriores conservan conteos y SHA-256; solo se añadieron metadatos de Fase 3.")
    print("Manifiesto privado:",manifiesto.relative_to(RAIZ).as_posix())

if __name__=="__main__":
    ejecutar()
