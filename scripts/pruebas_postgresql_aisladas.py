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

RAIZ = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(RAIZ / 'backend'))
from configuracion.aislamiento_pruebas import (
    CLAVE_FICTICIA, validar_entorno, validar_raiz, variables_libpq, verificar_identidad,
)


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


def entorno_aislado(origen, datos, puerto, base_temporal, paquetes, binarios):
    # Lista positiva: no heredar credenciales, .env, PATH ni overrides Python/libpq.
    permitidas = {'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT',
                  'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE'}
    entorno = {k.upper(): v for k, v in origen.items() if k.upper() in permitidas}
    carpeta = Path(datos).resolve().parent
    sistema = Path(entorno.get('SYSTEMROOT', 'C:/Windows')) / 'System32'
    entorno.update(
        POSTGRES_DB="postgres", POSTGRES_USER="postgres", POSTGRES_PASSWORD="",
        POSTGRES_HOST="127.0.0.1", POSTGRES_PORT=str(puerto),
        ZDB_PG_TEST_CLUSTER=str(datos.resolve()), PYTHONDONTWRITEBYTECODE="1",
        ZDB_PG_TEST_RUN=str(carpeta), ZDB_PG_TEST_BASE=str(Path(base_temporal).resolve()),
        ZDB_PAQUETES_PYTHON=str(Path(paquetes).resolve()), ZDB_LIBPQ_DIR=str(Path(binarios).resolve()),
        PATH=os.pathsep.join((str(Path(binarios).resolve()), str(Path(sys.executable).parent), str(sistema))),
        TEMP=str(carpeta / 'tmp'), TMP=str(carpeta / 'tmp'), TMPDIR=str(carpeta / 'tmp'),
        HOME=str(carpeta / 'home'), USERPROFILE=str(carpeta / 'home'),
        APPDATA=str(carpeta / 'home'), LOCALAPPDATA=str(carpeta / 'home'),
        PSYCOPG_IMPL='python',
        DJANGO_SETTINGS_MODULE='configuracion.settings_pruebas_postgresql',
        PYTHONIOENCODING="utf-8",
        DJANGO_SECRET_KEY=CLAVE_FICTICIA,
    )
    entorno.update(variables_libpq(carpeta))
    return entorno


def detener_cluster_propio(servidor, datos, puerto, carpeta, binarios, entorno, oculto):
    """No propaga fallos de limpieza; nunca busca procesos ni confía solo en -D.

    pg_ctl requiere identidad revalidada y el hijo aún vivo. Si no se acredita,
    únicamente se usa el objeto Popen propio (handle del hijo en Windows).
    """
    estado = dict(identidad_revalidada=False, pg_ctl_solicitado=False,
                  terminacion_propia=False, detenido=servidor is None, incidentes=[])

    def incidente(etapa, error):
        estado['incidentes'].append(f'{etapa}: {type(error).__name__}: {error}')

    if servidor is None:
        return estado
    try:
        if servidor.poll() is not None:
            estado['detenido'] = True
            return estado
        # No basta con que el manifiesto concuerde consigo mismo: contrastar el
        # archivo PID nuevamente con el PID independiente de nuestro Popen.
        raiz_validada, puerto_validado = validar_entorno(entorno, RAIZ)
        if raiz_validada != Path(carpeta).resolve() or puerto_validado != puerto:
            raise ValueError('Contexto de limpieza distinto de la ejecución creada')
        if Path(datos).is_symlink() or Path(datos).resolve() != raiz_validada / 'cluster':
            raise ValueError('Directorio de datos de limpieza incompatible')
        if Path(binarios).resolve() != Path(entorno['ZDB_LIBPQ_DIR']).resolve():
            raise ValueError('Binarios de limpieza incompatibles')
        verificar_identidad(datos, servidor.pid, puerto, datos, '127.0.0.1', puerto)
        if servidor.poll() is not None:
            estado['detenido'] = True
            return estado
        estado['identidad_revalidada'] = True
        estado['pg_ctl_solicitado'] = True
        cierre = subprocess.run([str(Path(binarios) / 'pg_ctl.exe'), '-D', str(datos),
                                '-m', 'fast', '-w', 'stop'], capture_output=True,
                               timeout=45, cwd=carpeta, env=entorno, **oculto)
        if cierre.returncode:
            raise RuntimeError(f'pg_ctl no confirmó el cierre (código {cierre.returncode})')
    except BaseException as error:
        incidente('Cierre controlado omitido o fallido', error)
    # Incluso tras un error de identidad, esta referencia es exclusivamente la
    # del hijo creado; no usar os.kill, nombres de proceso ni PID leídos de disco.
    try:
        if servidor.poll() is None:
            estado['terminacion_propia'] = True
            servidor.terminate()
        servidor.wait(timeout=30)
    except BaseException as error:
        incidente('Terminación del proceso hijo propio', error)
    try:
        estado['detenido'] = servidor.poll() is not None
    except BaseException as error:
        incidente('Confirmación de detención del hijo', error)
    return estado


def ejecutar(argv=None):
    opciones = argumentos(argv)  # Rechazar overrides antes de crear archivos/procesos.
    if os.getenv("ZDB_GENERAR_ASCENSOS"):
        raise RuntimeError("ZDB_GENERAR_ASCENSOS ya no está permitido: este ejecutor no genera migraciones.")
    raiz = RAIZ
    binarios = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin")).resolve()
    paquetes = Path(os.getenv('ZDB_PAQUETES_PYTHON', str(raiz / '.venv-local/Lib/site-packages'))).resolve()
    for nombre in ('django', 'rest_framework', 'psycopg', 'dotenv'):
        if not (paquetes / nombre / '__init__.py').is_file():
            raise RuntimeError('Faltan paquetes Python explícitos de pruebas: ' + nombre)
    for nombre in ("initdb.exe", "postgres.exe", "pg_ctl.exe", "pg_isready.exe", "psql.exe"):
        if not (binarios / nombre).is_file():
            raise RuntimeError("Faltan binarios PostgreSQL de pruebas.")
    base_temporal = Path(tempfile.gettempdir()).resolve()
    if base_temporal.is_relative_to(raiz):
        raise RuntimeError('El temporal del sistema no puede estar dentro del repositorio')
    carpeta = Path(tempfile.mkdtemp(prefix='zdb_pg_', dir=base_temporal)).resolve()
    validar_raiz(carpeta, base_temporal, raiz)
    for nombre in ('tmp', 'archivos_privados', 'pgconf', 'home'):
        (carpeta / nombre).mkdir()
    for nombre in ('pgpass-vacio', 'pgservice-vacio'):
        with (carpeta / nombre).open('xb'):
            pass
    datos = carpeta / "cluster"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    entorno = entorno_aislado(os.environ, datos, puerto, base_temporal, paquetes, binarios)
    resultado = {"puerto": puerto, "cluster": str(datos.resolve()), "pruebas": None,
                 "migraciones_check": None, "detenido": False, "python": sys.version.split()[0],
                 'paquetes': str(paquetes), 'binarios': str(binarios), 'carpeta': str(carpeta)}
    oculto = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}

    def ejecutar_registrado(comando, nombre):
        # stdout/stderr completos quedan en evidencia privada y en la terminal.
        with (carpeta / nombre).open("x", encoding="utf-8") as evidencia:
            proceso = subprocess.Popen(comando, cwd=carpeta, env=entorno, stdout=subprocess.PIPE,
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
                           capture_output=True, timeout=60, cwd=carpeta, env=entorno, **oculto)
        (carpeta / "initdb.log").write_bytes(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError("No se pudo inicializar PostgreSQL aislado; revisar initdb.log.")
        with (carpeta / "servidor.log").open("xb") as log:
            servidor = subprocess.Popen([str(binarios / "postgres.exe"), "-D", str(datos),
                                         "-h", "127.0.0.1", "-p", str(puerto)],
                                        stdout=log, stderr=log, cwd=carpeta, env=entorno, **oculto)
            listo = False
            limite = time.monotonic() + 30
            while time.monotonic() < limite and servidor.poll() is None:
                r = subprocess.run([str(binarios / "pg_isready.exe"), "-h", "127.0.0.1",
                                    "-p", str(puerto), "-U", "postgres", '-d', 'postgres'],
                                   capture_output=True, timeout=2, cwd=carpeta, env=entorno, **oculto)
                if r.returncode == 0:
                    listo = True
                    break
                time.sleep(0.1)
            if not listo:
                raise RuntimeError("PostgreSQL aislado no inició; revisar servidor.log.")
            identidad = subprocess.run([str(binarios / "psql.exe"), "-X", '-w', '-v', 'ON_ERROR_STOP=1', "-h", "127.0.0.1",
                                       "-p", str(puerto), "-U", "postgres", "-d", "postgres",
                                       "-At", "-F", '\t', "-c", "SELECT current_setting('data_directory'), inet_server_addr(), inet_server_port()"],
                                      capture_output=True, timeout=10, cwd=carpeta, env=entorno, **oculto)
            if identidad.returncode:
                raise RuntimeError("El destino no es el clúster creado; ejecución cancelada.")
            directorio, host, puerto_real = os.fsdecode(identidad.stdout).strip().split('\t')
            verificar_identidad(datos, servidor.pid, puerto, directorio, host, puerto_real)
            if servidor.poll() is not None:
                raise RuntimeError('El proceso hijo terminó antes de verificar su identidad')
            with (carpeta / 'identidad.json').open('x', encoding='utf-8') as archivo:
                json.dump(dict(pid=servidor.pid, cluster=str(datos.resolve()), host=host,
                               puerto=puerto, paquetes=str(paquetes), binarios=str(binarios)), archivo)
            print("Clúster temporal verificado en puerto", puerto, "; sin conexión a zona_bloque.", flush=True)
            comando = [sys.executable, '-I', '-B', str(raiz / "scripts/django_local.py")]
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
        error_original = sys.exc_info()[1]
        limpieza = detener_cluster_propio(servidor, datos, puerto, carpeta, binarios, entorno, oculto)
        resultado['limpieza'] = limpieza
        resultado['detenido'] = limpieza['detenido']
        try:
            (carpeta / "resultado.json").write_text(json.dumps(resultado, indent=2), encoding="utf-8")
        except BaseException as error:
            limpieza['incidentes'].append(f'No se pudo guardar resultado.json: {type(error).__name__}: {error}')
        try:
            print("Proceso hijo detenido." if resultado["detenido"] else "ATENCIÓN: detención del hijo no confirmada.",
                  "Evidencia privada:", str(carpeta), flush=True)
            for incidente in limpieza['incidentes']:
                print('Incidente de limpieza:', incidente, file=sys.stderr, flush=True)
        except BaseException:
            # Una salida cerrada tampoco debe reemplazar la excepción original.
            pass
        if error_original is None and (limpieza['incidentes'] or not limpieza['detenido']):
            # Conservar también el código de una prueba fallida que esté retornando.
            if resultado['pruebas'] in (None, 0) and resultado['migraciones_check'] in (None, 0):
                raise RuntimeError('La limpieza registró incidentes o no confirmó la detención; revisar evidencias temporales')


if __name__ == "__main__":
    raise SystemExit(ejecutar())
