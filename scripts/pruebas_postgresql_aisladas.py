"""Pruebas en clúster efímero verificado; nunca usa la base operativa."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


def argumentos(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failfast", action="store_true")
    parser.add_argument("--etiqueta", action="append", default=[])
    parser.add_argument("--verbosity", type=int, choices=range(4), default=1)
    opciones = parser.parse_args(argv)
    import re
    if any(not re.fullmatch(r"(?:cuentas|organizacion|paneles|deportistas|inscripciones|recursos|curriculo|biblioteca|sesiones)(?:\.[A-Za-z_][A-Za-z0-9_]*)*", e) for e in opciones.etiqueta):
        parser.error("Etiqueta de pruebas no admitida")
    return opciones


def entorno_aislado(origen, datos, puerto):
    entorno = origen.copy()
    # No heredar servicios, opciones libpq ni selección alternativa de settings.
    for clave in list(entorno):
        if clave.upper().startswith("PG") or clave.upper() in (
            "DJANGO_SETTINGS_MODULE", "ZDB_GENERAR_ASCENSOS", "ZDB_PG_TEST_CLUSTER"
        ):
            entorno.pop(clave, None)
    entorno.update(
        POSTGRES_DB="postgres", POSTGRES_USER="postgres", POSTGRES_PASSWORD="",
        POSTGRES_HOST="127.0.0.1", POSTGRES_PORT=str(puerto),
        ZDB_PG_TEST_CLUSTER=str(datos.resolve()), PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
        DJANGO_SECRET_KEY="clave-ficticia-exclusiva-de-pruebas-aisladas-no-operativa-123456789",
    )
    return entorno


def ejecutar(argv=None):
    opciones = argumentos(argv)  # Rechazar overrides antes de crear archivos/procesos.
    if os.getenv("ZDB_GENERAR_ASCENSOS"):
        raise RuntimeError("ZDB_GENERAR_ASCENSOS ya no está permitido: este ejecutor no genera migraciones.")
    raiz = Path(__file__).resolve().parent.parent
    binarios = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin"))
    for nombre in ("initdb.exe", "postgres.exe", "pg_ctl.exe", "pg_isready.exe", "psql.exe"):
        if not (binarios / nombre).is_file():
            raise RuntimeError("Faltan binarios PostgreSQL de pruebas.")
    (raiz / "respaldos").mkdir(exist_ok=True)
    carpeta = Path(tempfile.mkdtemp(prefix="pruebas_etapa1_", dir=raiz / "respaldos"))
    datos = carpeta / "cluster"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    entorno = entorno_aislado(os.environ, datos, puerto)
    resultado = {"puerto": puerto, "cluster": str(datos.resolve()), "pruebas": None,
                 "migraciones_check": None, "detenido": False, "python": sys.version.split()[0]}
    oculto = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}

    def ejecutar_registrado(comando, nombre):
        # stdout/stderr completos quedan en evidencia privada y en la terminal.
        with (carpeta / nombre).open("w", encoding="utf-8") as evidencia:
            proceso = subprocess.Popen(comando, cwd=raiz, env=entorno, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       errors="replace", **oculto)
            try:
                for linea in proceso.stdout:
                    evidencia.write(linea)
                    evidencia.flush()
                    print(linea, end="", flush=True)
                return proceso.wait()
            finally:
                if proceso.poll() is None:
                    proceso.terminate()
                    proceso.wait(timeout=30)

    servidor = None
    try:
        r = subprocess.run([str(binarios / "initdb.exe"), "-D", str(datos), "-U", "postgres",
                            "-A", "trust", "--encoding=UTF8", "--no-locale"],
                           capture_output=True, timeout=60, env=entorno, **oculto)
        (carpeta / "initdb.log").write_bytes(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError("No se pudo inicializar PostgreSQL aislado; revisar initdb.log.")
        with (carpeta / "servidor.log").open("wb") as log:
            servidor = subprocess.Popen([str(binarios / "postgres.exe"), "-D", str(datos),
                                         "-h", "127.0.0.1", "-p", str(puerto)],
                                        stdout=log, stderr=log, env=entorno, **oculto)
            listo = False
            limite = time.monotonic() + 30
            while time.monotonic() < limite and servidor.poll() is None:
                r = subprocess.run([str(binarios / "pg_isready.exe"), "-h", "127.0.0.1",
                                    "-p", str(puerto), "-U", "postgres"],
                                   capture_output=True, timeout=2, env=entorno, **oculto)
                if r.returncode == 0:
                    listo = True
                    break
                time.sleep(0.1)
            if not listo:
                raise RuntimeError("PostgreSQL aislado no inició; revisar servidor.log.")
            identidad = subprocess.run([str(binarios / "psql.exe"), "-X", "-h", "127.0.0.1",
                                       "-p", str(puerto), "-U", "postgres", "-d", "postgres",
                                       "-At", "-c", "SHOW data_directory"],
                                      capture_output=True, timeout=10, env=entorno, **oculto)
            if identidad.returncode or Path(os.fsdecode(identidad.stdout).strip()).resolve() != datos.resolve():
                raise RuntimeError("El destino no es el clúster creado; ejecución cancelada.")
            if int((datos / "postmaster.pid").read_text().splitlines()[0]) != servidor.pid:
                raise RuntimeError("El PID PostgreSQL no coincide con el proceso hijo creado.")
            print("Clúster temporal verificado en puerto", puerto, "; sin conexión a zona_bloque.", flush=True)
            comando = [sys.executable, str(raiz / "scripts/django_local.py")]
            resultado["pruebas"] = ejecutar_registrado(comando + ["test", *(opciones.etiqueta or ["cuentas", "organizacion", "paneles", "deportistas", "inscripciones", "recursos", "curriculo", "biblioteca", "sesiones"]), "--settings=configuracion.settings_pruebas_postgresql",
                "--noinput", "--verbosity", str(opciones.verbosity)] + (["--failfast"] if opciones.failfast else []), "pruebas.log")
            if resultado["pruebas"] != 0:
                return resultado["pruebas"]
            resultado["migraciones_check"] = ejecutar_registrado(comando + ["makemigrations", "--check",
                "--dry-run", "--settings=configuracion.settings_pruebas_postgresql"], "migraciones_check.log")
            return resultado["migraciones_check"]
    except BaseException as error:
        resultado["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        try:
            if servidor is not None and servidor.poll() is None:
                try:
                    subprocess.run([str(binarios / "pg_ctl.exe"), "-D", str(datos), "-m", "fast", "-w", "stop"],
                                   capture_output=True, timeout=45, env=entorno, **oculto)
                finally:
                    if servidor.poll() is None:
                        servidor.terminate()
                    servidor.wait(timeout=30)
        finally:
            resultado["detenido"] = servidor is None or servidor.poll() is not None
            (carpeta / "resultado.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
            print("Clúster detenido." if resultado["detenido"] else "ATENCIÓN: revisar proceso temporal.",
                  "Evidencia privada:", carpeta.relative_to(raiz), flush=True)


if __name__ == "__main__":
    raise SystemExit(ejecutar())
