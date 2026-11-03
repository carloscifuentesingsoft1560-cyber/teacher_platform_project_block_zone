"""Aplicación acotada y verificable de la migración institucional autorizada."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.operations import AddConstraint
from django.db.models import UniqueConstraint, Q
from cuentas.models import Usuario

OBJETIVO = ("cuentas", "0004_usuario_un_coordinador_activo")
RAIZ = Path(__file__).resolve().parent.parent

def huellas():
    resultado = {}
    with connection.cursor() as c:
        for tabla in sorted(connection.introspection.table_names()):
            if tabla == "django_migrations":
                continue
            c.execute("SELECT row_to_json(t)::text FROM " + connection.ops.quote_name(tabla) + " t")
            filas = sorted(r[0] for r in c.fetchall())
            resultado[tabla] = {"filas": len(filas), "sha256": hashlib.sha256(
                json.dumps(filas, ensure_ascii=False).encode()).hexdigest()}
    return resultado

def ejecutar():
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "zona_bloque", "Destino no autorizado"
    with connection.cursor() as c:
        c.execute("SELECT current_database()")
        assert c.fetchone()[0] == "zona_bloque", "Base efectiva incorrecta"
    e = MigrationExecutor(connection)
    e.loader.check_consistent_history(connection)
    plan = e.migration_plan(e.loader.graph.leaf_nodes())
    assert len(plan) == 1 and (plan[0][0].app_label, plan[0][0].name) == OBJETIVO and not plan[0][1], "Plan distinto del autorizado"
    operaciones = plan[0][0].operations
    esperado = UniqueConstraint(fields=("rol",), condition=Q(("is_active", True), ("rol", "coordinador")), name="un_coordinador_activo")
    assert len(operaciones) == 1 and isinstance(operaciones[0], AddConstraint), "Operaciones inesperadas"
    assert operaciones[0].model_name == "usuario" and operaciones[0].constraint == esperado, "Restricción inesperada"
    activos = Usuario.objects.filter(rol="coordinador", is_active=True).count()
    assert activos <= 1, "Duplicidad de coordinadores: proceso detenido"
    antes = huellas()
    aplicadas = set(MigrationRecorder(connection).applied_migrations())
    print("Destino confirmado: PostgreSQL zona_bloque. Coordinadores activos:", activos)
    print("Única migración pendiente: cuentas.0004_usuario_un_coordinador_activo; solo crea índice único parcial.")
    instante = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    carpeta = RAIZ / "respaldos"
    carpeta.mkdir(exist_ok=True)
    archivo = carpeta / ("zona_bloque_antes_coordinador_unico_" + instante + ".dump")
    manifiesto = carpeta / ("coordinador_unico_" + instante + ".json")
    assert not archivo.exists() and not manifiesto.exists(), "Respaldo ya existente"
    cfg = connection.settings_dict
    entorno = os.environ.copy()
    entorno["PGPASSWORD"] = cfg.get("PASSWORD") or ""
    binarios = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin"))
    args = ["--host", str(cfg.get("HOST") or "127.0.0.1"), "--port", str(cfg.get("PORT") or "5432"),
            "--username", str(cfg["USER"]), "--dbname", "zona_bloque", "--no-password"]
    r = subprocess.run([str(binarios/"pg_dump.exe"), *args, "--format=custom", "--file", str(archivo)],
                       env=entorno, capture_output=True, timeout=180)
    entorno.pop("PGPASSWORD", None)
    assert r.returncode == 0 and archivo.exists() and archivo.stat().st_size > 0, "Respaldo fallido; no se aplicó migración"
    r = subprocess.run([str(binarios/"pg_restore.exe"), "--list", str(archivo)], capture_output=True, timeout=60)
    assert r.returncode == 0 and b"; Archive created at" in r.stdout, "Catálogo inválido"
    # Recorre y descomprime TODO el archivo sin conexión ni restauración a ninguna base.
    r = subprocess.run([str(binarios/"pg_restore.exe"), "--file", os.devnull, str(archivo)],
                       capture_output=True, timeout=180)
    assert r.returncode == 0, "Lectura completa del respaldo fallida"
    datos = {"base": "zona_bloque", "fecha_utc": instante, "respaldo": archivo.relative_to(RAIZ).as_posix(),
             "bytes": archivo.stat().st_size, "sha256": hashlib.sha256(archivo.read_bytes()).hexdigest(),
             "catalogo_verificado": True, "lectura_completa_verificada": True, "estado": "respaldo_verificado",
             "huellas_antes": antes, "migracion": ".".join(OBJETIVO)}
    manifiesto.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print("Nuevo respaldo verificado (catálogo y lectura completa):", datos["respaldo"])
    print("Bytes:", datos["bytes"], "SHA-256:", datos["sha256"])
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL lock_timeout = '10s'")
            c.execute("SET LOCAL statement_timeout = '60s'")
            tablas = sorted(antes)
            c.execute("LOCK TABLE " + ", ".join(connection.ops.quote_name(t) for t in tablas) + " IN SHARE MODE")
        assert huellas() == antes, "Cambios concurrentes antes de migrar; operación detenida"
        assert Usuario.objects.filter(rol="coordinador", is_active=True).count() <= 1
        e.migrate([OBJETIVO], plan=plan)
        despues = set(MigrationRecorder(connection).applied_migrations())
        assert despues - aplicadas == {OBJETIVO} and not aplicadas - despues, "Registro inesperado"
        assert huellas() == antes, "Datos alterados; se revierte la migración"
        with connection.cursor() as c:
            c.execute("""SELECT i.indisunique, i.indisvalid, i.indisready, pg_get_expr(i.indpred,i.indrelid)
                         FROM pg_index i JOIN pg_class x ON x.oid=i.indexrelid
                         WHERE x.relname='un_coordinador_activo' AND i.indrelid='cuentas_usuario'::regclass""")
            indice = c.fetchone()
            assert indice and all(indice[:3]) and "coordinador" in indice[3] and "is_active" in indice[3], "Índice inválido"
    assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes()), "Migraciones pendientes"
    datos.update(estado="aplicada_y_verificada", datos_intactos=True, indice_unico_valido=True, pendientes=[])
    manifiesto.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print("Aplicada exclusivamente la migración autorizada. Índice válido. Ninguna migración pendiente.")
    print("Todas las tablas de datos permanecen idénticas (conteos y SHA-256); solo cambió django_migrations y el índice.")
    print("Manifiesto privado:", manifiesto.relative_to(RAIZ).as_posix())

if __name__ == "__main__":
    ejecutar()
