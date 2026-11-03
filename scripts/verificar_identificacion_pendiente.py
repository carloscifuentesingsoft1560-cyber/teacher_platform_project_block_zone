"""Comprobación reproducible de SOLO LECTURA sobre zona_bloque, antes de aprobar 0002.

Rechaza cambios de registros, tablas nuevas o cualquier plan distinto.
No crea fixtures, sesiones ni documentos.
"""
import hashlib
import json
from pathlib import Path
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from cuentas.models import Usuario

RAIZ=Path(__file__).resolve().parent.parent

def exigir(condicion,mensaje):
    if not condicion:
        raise RuntimeError(mensaje)

def verificar():
    ruta=sorted((RAIZ/"respaldos").glob("identificacion_antes_*.json"))[-1]
    referencia=json.loads(ruta.read_text(encoding="utf-8"))
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET TRANSACTION READ ONLY")
            c.execute("SELECT current_database()")
            exigir(connection.vendor=="postgresql" and connection.settings_dict["NAME"]=="zona_bloque" and c.fetchone()[0]=="zona_bloque","Destino no autorizado.")
            actuales={}
            tablas=connection.introspection.table_names()
            for tabla in tablas:
                c.execute("SELECT row_to_json(t)::text FROM "+connection.ops.quote_name(tabla)+" t")
                filas=sorted(r[0] for r in c.fetchall())
                actuales[tabla]={"filas":len(filas),"sha256":hashlib.sha256(json.dumps(filas,ensure_ascii=False).encode()).hexdigest()}
            exigir(actuales==referencia["tablas"],"Los registros cambiaron; revisar sin alterar datos.")
            columnas={f.name for f in connection.introspection.get_table_description(c,"deportistas_deportista")}
            exigir(not {"tipo_documento_id","numero_documento","pais_emisor"}&columnas,"Ya hay columnas documentales en la base.")
            exigir(not {"deportistas_tipodocumento","deportistas_cambiodocumentodeportista"}&set(tablas),"Ya hay tablas documentales en la base.")
        ejecutor=MigrationExecutor(connection)
        ejecutor.loader.check_consistent_history(connection)
        plan=ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes())
        exigir([(m.app_label,m.name,b) for m,b in plan]==[("deportistas","0002_identificacion_documental",False)],"Plan distinto de la migración propuesta.")
        c=APIClient(HTTP_HOST="localhost")
        comprobaciones=[]
        for rol in ("administrador","coordinador"):
            actor=Usuario.objects.filter(rol=rol,is_active=True).first()
            exigir(actor is not None,"Falta un actor autorizado para verificar el panel.")
            c.force_authenticate(actor)
            for url,esperado in [
                ("/api/paneles/"+rol+"/resumen/",200),
                ("/api/organizacion/grupos/",200),
                ("/api/deportistas/",503),
            ]:
                exigir(c.get(url).status_code==esperado,"Respuesta inesperada en comprobación de compatibilidad.")
                comprobaciones.append({"rol":rol,"ruta":url,"estado":esperado})
        print("Base real: zona_bloque. Conteos y SHA-256 de",len(actuales),"tablas idénticos.")
        print("Deportistas conservados:",actuales["deportistas_deportista"]["filas"],"; las relaciones y claves anteriores no cambiaron.")
        print("Columnas y tablas documentales ausentes. Única pendiente: deportistas.0002_identificacion_documental.")
        print("Compatibilidad:",json.dumps(comprobaciones))
    referencia["verificacion_final"]={"estado":"conservacion_confirmada_migracion_no_aplicada","tablas_identicas":len(actuales),
        "deportistas":actuales["deportistas_deportista"]["filas"],"comprobaciones_compatibilidad":comprobaciones,
        "migracion_propuesta":"deportistas.0002_identificacion_documental",
        "sha256_migracion":hashlib.sha256((RAIZ/"backend/deportistas/migrations/0002_identificacion_documental.py").read_bytes()).hexdigest()}
    ruta.write_text(json.dumps(referencia,indent=2),encoding="utf-8")
    return referencia["verificacion_final"]

if __name__=="__main__":
    verificar()
