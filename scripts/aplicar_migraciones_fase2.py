"""Aplica exclusivamente las cuatro migraciones autorizadas, con respaldo previo.

Ejecutar mediante scripts/django_local.py shell para reutilizar la conexión.
No imprime credenciales ni contenido de la base.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

from django.db import connection, transaction
from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import CreateModel, AddConstraint, RunPython
from django.db.migrations.recorder import MigrationRecorder

APROBADAS = {
    ("auditoria", "0001_initial"),
    ("cuentas", "0003_solicitudrestablecimiento"),
    ("organizacion", "0001_initial"),
    ("organizacion", "0002_catalogos_iniciales"),
}
# Destinos finales por app: 0001 de organización es dependencia de 0002.
# Incluir ambos como destinos al repetir provocaría un plan de reversión.
DESTINOS = [
    ("auditoria", "0001_initial"),
    ("cuentas", "0003_solicitudrestablecimiento"),
    ("organizacion", "0002_catalogos_iniciales"),
]
TABLAS_NUEVAS = {
    "auditoria_cambioadministrativo", "cuentas_solicitudrestablecimiento",
    "organizacion_disciplina", "organizacion_nivel", "organizacion_periodo",
    "organizacion_grupo", "organizacion_asignacion", "organizacion_horario",
}
raiz = Path(__file__).resolve().parent.parent


def sincronizar_metadatos():
    # Cierre estándar de Django: crea content types y permisos de modelos.
    # No asigna permisos a cuentas o grupos ni altera sus privilegios.
    for etiqueta in ("auditoria", "cuentas", "organizacion"):
        create_permissions(apps.get_app_config(etiqueta), verbosity=0,
            interactive=False, using=connection.alias, apps=apps)


def ejecutar():
    if connection.vendor != "postgresql" or connection.settings_dict["NAME"] != "zona_bloque":
        raise RuntimeError("Operación detenida: la configuración no es PostgreSQL/zona_bloque.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        if cursor.fetchone()[0] != "zona_bloque":
            raise RuntimeError("Operación detenida: la base efectiva no es zona_bloque.")
    print("Conexión comprobada: PostgreSQL / zona_bloque.")
    ejecutor = MigrationExecutor(connection)
    ejecutor.loader.check_consistent_history(connection)
    aplicadas_antes = set(MigrationRecorder(connection).applied_migrations())
    plan = ejecutor.migration_plan(DESTINOS)
    pendientes = {migracion for migracion in APROBADAS if migracion not in aplicadas_antes}
    if any(atras for _, atras in plan) or {(m.app_label, m.name) for m, _ in plan} != pendientes:
        raise RuntimeError("Operación detenida: el plan contiene cambios fuera de lo autorizado.")
    for migracion, _ in plan:
        for operacion in migracion.operations:
            if not isinstance(operacion, (CreateModel, AddConstraint, RunPython)):
                raise RuntimeError("Operación inesperada: no se modificó la base.")
            if isinstance(operacion, RunPython) and (
                migracion.app_label != "organizacion"
                or migracion.name != "0002_catalogos_iniciales"
                or operacion.code.__name__ != "cargar_catalogos"
            ):
                raise RuntimeError("Carga de datos inesperada.")
    print("Plan revisado: " + ", ".join(m.app_label + "." + m.name for m, _ in plan))
    if not plan:
        with transaction.atomic():
            sincronizar_metadatos()
        print("Las cuatro migraciones ya están aplicadas; esquema sin cambios y metadatos Django sincronizados.")
        return

    instante = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directorio = raiz / "respaldos"
    directorio.mkdir(exist_ok=True)
    respaldo = directorio / ("zona_bloque_antes_fase2_" + instante + ".dump")
    if respaldo.exists():
        raise RuntimeError("El archivo de respaldo ya existe; no se sobrescribió.")
    configuracion = connection.settings_dict
    entorno = os.environ.copy()
    entorno["PGPASSWORD"] = configuracion.get("PASSWORD") or ""
    argumentos = [
        "--host", str(configuracion.get("HOST") or "127.0.0.1"),
        "--port", str(configuracion.get("PORT") or "5432"),
        "--username", str(configuracion["USER"]),
        "--dbname", "zona_bloque", "--no-password",
    ]
    binarios = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin"))
    resultado = subprocess.run(
        [str(binarios / "pg_dump.exe"), *argumentos, "--format=custom", "--file", str(respaldo)],
        env=entorno, capture_output=True, timeout=180,
    )
    entorno.pop("PGPASSWORD", None)
    if resultado.returncode or not respaldo.exists() or respaldo.stat().st_size == 0:
        raise RuntimeError("Falló el respaldo; las migraciones NO se aplicaron. No se imprime la salida privada de pg_dump.")
    lista = subprocess.run([str(binarios / "pg_restore.exe"), "--list", str(respaldo)],
        capture_output=True, timeout=30)
    if lista.returncode or b"; Archive created at" not in lista.stdout:
        raise RuntimeError("El archivo no superó la comprobación de catálogo; no se aplicaron migraciones.")
    sha = hashlib.sha256(respaldo.read_bytes()).hexdigest()
    manifiesto = {
        "base": "zona_bloque", "respaldo": respaldo.relative_to(raiz).as_posix(),
        "tamano_bytes": respaldo.stat().st_size, "sha256": sha,
        "catalogo_respaldo_verificado": True,
        "migraciones_plan": [m.app_label + "." + m.name for m, _ in plan],
        "estado": "respaldo_verificado",
    }
    ruta_manifiesto = directorio / ("fase2_" + instante + ".json")
    ruta_manifiesto.write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    print("Respaldo privado creado y catálogo legible: " + respaldo.relative_to(raiz).as_posix())
    print("SHA-256: " + sha)
    with transaction.atomic():
        # Atomicidad global: si falla una migración, se revierte este conjunto.
        ejecutor.migrate(DESTINOS, plan=plan)
        sincronizar_metadatos()
        aplicadas_despues = set(MigrationRecorder(connection).applied_migrations())
        if aplicadas_despues - aplicadas_antes != pendientes:
            raise RuntimeError("El registro de migraciones no coincide; se revierte el conjunto.")
        if not TABLAS_NUEVAS.issubset(set(connection.introspection.table_names())):
            raise RuntimeError("Faltan tablas previstas; se revierte el conjunto.")
    manifiesto["estado"] = "migraciones_aplicadas"
    manifiesto["tablas_verificadas"] = sorted(TABLAS_NUEVAS)
    ruta_manifiesto.write_text(json.dumps(manifiesto, indent=2), encoding="utf-8")
    print("Aplicadas y registradas exclusivamente las migraciones aprobadas.")
    print("Tablas nuevas verificadas: " + ", ".join(sorted(TABLAS_NUEVAS)))


ejecutar()
