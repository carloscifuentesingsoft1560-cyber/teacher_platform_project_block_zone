"""Aplicación exclusiva autorizada de 0002, con restauración aislada y huellas.

Ejecutar mediante django_local.py shell. No imprime filas ni credenciales.
No es reutilizable para otras migraciones; rechaza una segunda aplicación.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

from django.apps import apps
from django.contrib.auth.management import create_permissions
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations import AddField, CreateModel, AddConstraint, RunPython
from django.db.migrations.recorder import MigrationRecorder
import psycopg

RAIZ = Path(__file__).resolve().parent.parent
OBJETIVO = ('deportistas', '0002_identificacion_documental')
SHA_APROBADO = '82f67e30a11c8c5d6fc1a035458d74d0787c2c6505cac38be69ee3401464040d'
NUEVAS = {'deportistas_tipodocumento', 'deportistas_cambiodocumentodeportista'}
MODELOS = ('tipodocumento', 'cambiodocumentodeportista')
BIN = Path(os.getenv('ZDB_LIBPQ_DIR', 'C:/Program Files/PostgreSQL/17/bin'))

def exigir(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)

def guardar(ruta, datos):
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding='utf-8')

def destino():
    exigir(connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'zona_bloque', 'Configuración no autorizada.')
    with connection.cursor() as c:
        c.execute('SELECT current_database(),current_schema()')
        exigir(c.fetchone() == ('zona_bloque', 'public'), 'Conexión efectiva no autorizada.')

def plan_exclusivo():
    archivo = RAIZ / 'backend/deportistas/migrations/0002_identificacion_documental.py'
    exigir(hashlib.sha256(archivo.read_bytes()).hexdigest() == SHA_APROBADO, 'El archivo difiere del inventario aprobado.')
    e = MigrationExecutor(connection)
    e.loader.check_consistent_history(connection)
    plan = e.migration_plan(e.loader.graph.leaf_nodes())
    exigir([(m.app_label, m.name, b) for m, b in plan] == [(*OBJETIVO, False)], 'No es la única migración pendiente.')
    m = plan[0][0]
    cantidades = {t.__name__: sum(isinstance(o, t) for o in m.operations) for t in (AddField, CreateModel, AddConstraint, RunPython)}
    exigir(cantidades == {'AddField': 3, 'CreateModel': 2, 'AddConstraint': 9, 'RunPython': 1} and len(m.operations) == 15, 'Inventario no aprobado.')
    estado = e._create_project_state(with_applied_migrations=True)
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        m.apply(estado, editor, collect_sql=True)
    sql = '\n'.join(editor.collected_sql)
    exigir(not re.search(r'\b(DROP|DELETE|TRUNCATE|UPDATE)\b', sql, re.I), 'SQL destructivo inesperado.')
    restricciones = {}
    for o in m.operations:
        if isinstance(o, AddConstraint):
            restricciones[o.constraint.name] = m.app_label + '_' + o.model_name
        elif isinstance(o, CreateModel):
            for r in o.options.get('constraints', []):
                restricciones[r.name] = m.app_label + '_' + o.name.lower()
    exigir(len(restricciones) == 10, 'Restricciones explícitas inesperadas.')
    with connection.cursor() as c:
        c.execute("SELECT relname FROM pg_class WHERE relnamespace='public'::regnamespace")
        existentes = {r[0] for r in c.fetchall()}
        nombres = NUEVAS | {t + '_id_seq' for t in NUEVAS} | set(re.findall(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+"([^"]+)"', sql, re.I))
        exigir(not existentes & nombres, 'Colisión de tabla, secuencia o índice.')
        c.execute("SELECT conname FROM pg_constraint WHERE connamespace='public'::regnamespace")
        exigir(not {r[0] for r in c.fetchall()} & (set(restricciones) | set(re.findall(r'CONSTRAINT\s+"([^"]+)"', sql))), 'Colisión de restricción.')
        columnas = {f.name for f in connection.introspection.get_table_description(c, 'deportistas_deportista')}
        exigir(not columnas & {'tipo_documento_id', 'numero_documento', 'pais_emisor'}, 'Columnas documentales ya presentes.')
    return e, plan, cantidades, restricciones, sql

def filtro(tabla):
    if tabla == 'django_migrations':
        return " WHERE NOT (app='deportistas' AND name='0002_identificacion_documental')"
    if tabla == 'django_content_type':
        return " WHERE NOT (app_label='deportistas' AND model IN ('tipodocumento','cambiodocumentodeportista'))"
    if tabla == 'auth_permission':
        return " WHERE content_type_id NOT IN (SELECT id FROM django_content_type WHERE app_label='deportistas' AND model IN ('tipodocumento','cambiodocumentodeportista'))"
    return ''

def huellas(con, columnas):
    resultado = {}
    q = connection.ops.quote_name
    with con.cursor() as c:
        for tabla, campos in sorted(columnas.items()):
            c.execute('SELECT row_to_json(t)::text FROM (SELECT ' + ','.join(q(f) for f in campos) + ' FROM ' + q(tabla) + filtro(tabla) + ') t')
            filas = sorted(r[0] for r in c.fetchall())
            resultado[tabla] = {'filas': len(filas), 'sha256': hashlib.sha256(json.dumps(filas, ensure_ascii=False).encode()).hexdigest()}
    return resultado

def comando(args, carpeta, nombre, env=None, timeout=120):
    r = subprocess.run([str(a) for a in args], capture_output=True, env=env, timeout=timeout,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if r.returncode:
        (carpeta / (nombre + '.log')).write_bytes(r.stdout + r.stderr)
        raise RuntimeError('Falló ' + nombre + '; revisar evidencia privada. No se imprimen datos.')
    return r

def restaurar_aislado(archivo, carpeta, columnas, antes):
    datos = carpeta / 'cluster_recuperacion'
    comando([BIN/'initdb.exe', '-D', datos, '-U', 'postgres', '-A', 'trust', '--encoding=UTF8', '--no-locale'], carpeta, 'initdb')
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        puerto = s.getsockname()[1]
    with (carpeta/'recuperacion_servidor.log').open('wb') as log:
        servidor = subprocess.Popen([str(BIN/'postgres.exe'), '-D', str(datos), '-h', '127.0.0.1', '-p', str(puerto)],
            stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for _ in range(100):
                r = subprocess.run([str(BIN/'pg_isready.exe'), '-h', '127.0.0.1', '-p', str(puerto), '-U', 'postgres'], capture_output=True, timeout=5)
                if r.returncode == 0:
                    break
                exigir(servidor.poll() is None, 'No inició recuperación aislada.')
                time.sleep(.1)
            else:
                raise RuntimeError('Timeout de recuperación aislada.')
            with psycopg.connect(host='127.0.0.1', port=puerto, user='postgres', dbname='postgres', autocommit=True) as con:
                ruta = con.execute('SHOW data_directory').fetchone()[0]
                exigir(Path(ruta).resolve() == datos.resolve() and int((datos/'postmaster.pid').read_text().splitlines()[0]) == servidor.pid, 'Destino de recuperación inesperado.')
                con.execute('CREATE DATABASE recuperacion_documental')
            comando([BIN/'pg_restore.exe', '-h', '127.0.0.1', '-p', puerto, '-U', 'postgres', '-d', 'recuperacion_documental', '--no-owner', '--no-privileges', '--exit-on-error', archivo], carpeta, 'restauracion', timeout=180)
            with psycopg.connect(host='127.0.0.1', port=puerto, user='postgres', dbname='recuperacion_documental') as con:
                # Django representa timestamptz en UTC; igualar la sesión al comparar JSON.
                con.execute("SET TIME ZONE 'UTC'")
                recuperadas = huellas(con, columnas)
                guardar(carpeta/'huellas_restauracion.json', recuperadas)
                exigir(recuperadas == antes, 'La restauración no conserva todas las filas originales.')
            return {'restauracion_completa': True, 'tablas_recuperadas': len(columnas), 'huellas_identicas': True, 'cluster_detenido_al_finalizar': True}
        finally:
            if servidor.poll() is None:
                subprocess.run([str(BIN/'pg_ctl.exe'), '-D', str(datos), '-m', 'fast', '-w', 'stop'], capture_output=True, timeout=60)
                if servidor.poll() is None:
                    servidor.terminate()
                servidor.wait(timeout=30)

def ejecutar():
    destino()
    e, plan, cantidades, restricciones, sql = plan_exclusivo()
    instante = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    carpeta = RAIZ/'respaldos'/('identificacion_aplicacion_'+instante)
    carpeta.mkdir(parents=True, exist_ok=False)
    manifiesto = carpeta/'manifiesto.json'
    archivo = carpeta/'zona_bloque_antes_identificacion.dump'
    datos = {'base': 'zona_bloque', 'fecha_utc': instante, 'migracion': '.'.join(OBJETIVO), 'sha256_migracion': SHA_APROBADO,
             'operaciones': cantidades, 'restricciones': restricciones, 'estado': 'preflight_correcto'}
    (carpeta/'plan.sql').write_text(sql, encoding='utf-8')
    print('Destino efectivo: zona_bloque/public. Única pendiente: deportistas.0002_identificacion_documental. Inventario: 15 operaciones; sin colisiones.', flush=True)
    try:
        with transaction.atomic():
            with connection.cursor() as c:
                c.execute("SET LOCAL lock_timeout='10s'")
                c.execute("SET LOCAL statement_timeout='120s'")
                tablas = connection.introspection.table_names()
                c.execute('LOCK TABLE '+','.join(connection.ops.quote_name(t) for t in sorted(tablas))+' IN SHARE MODE')
                columnas = {t: [f.name for f in connection.introspection.get_table_description(c, t)] for t in tablas}
            destino()
            e, plan, _, _, _ = plan_exclusivo()
            aplicadas = set(MigrationRecorder(connection).applied_migrations())
            antes = huellas(connection, columnas)
            datos.update(columnas_originales=columnas, huellas_antes=antes)
            guardar(manifiesto, datos)
            cfg = connection.settings_dict
            env = os.environ.copy()
            env['PGPASSWORD'] = cfg.get('PASSWORD') or ''
            try:
                comando([BIN/'pg_dump.exe', '-h', cfg.get('HOST') or '127.0.0.1', '-p', cfg.get('PORT') or 5432, '-U', cfg['USER'], '-d', 'zona_bloque', '--no-password', '-Fc', '-f', archivo], carpeta, 'respaldo', env=env, timeout=180)
            finally:
                env.pop('PGPASSWORD', None)
            exigir(archivo.is_file() and archivo.stat().st_size > 0, 'Respaldo vacío.')
            toc = comando([BIN/'pg_restore.exe', '--list', archivo], carpeta, 'catalogo')
            (carpeta/'catalogo_respaldo.txt').write_bytes(toc.stdout)
            comando([BIN/'pg_restore.exe', '--file', os.devnull, archivo], carpeta, 'lectura_completa', timeout=180)
            datos.update(respaldo=archivo.relative_to(RAIZ).as_posix(), bytes=archivo.stat().st_size,
                         sha256_respaldo=hashlib.sha256(archivo.read_bytes()).hexdigest(), lectura_completa=True)
            datos['recuperacion'] = restaurar_aislado(archivo, carpeta, columnas, antes)
            datos['estado'] = 'respaldo_leido_y_restaurado'
            guardar(manifiesto, datos)
            print('Respaldo nuevo leído y restaurado en clúster aislado; 29 tablas con huellas idénticas. Clúster detenido.', flush=True)
            print('Respaldo:', datos['respaldo'], 'SHA-256:', datos['sha256_respaldo'], flush=True)
            exigir(huellas(connection, columnas) == antes, 'Cambios detectados antes de migrar.')
            e.migrate([OBJETIVO], plan=plan)
            create_permissions(apps.get_app_config('deportistas'), verbosity=0, interactive=False, using=connection.alias, apps=apps)
            exigir(set(MigrationRecorder(connection).applied_migrations()) - aplicadas == {OBJETIVO}, 'Registro de migraciones inesperado.')
            exigir(aplicadas.issubset(set(MigrationRecorder(connection).applied_migrations())), 'Se perdió historial de migraciones.')
            exigir(set(connection.introspection.table_names()) == set(tablas) | NUEVAS, 'Inventario de tablas inesperado.')
            with connection.cursor() as c:
                for nombre, tabla in restricciones.items():
                    info = connection.introspection.get_constraints(c, tabla)
                    exigir(nombre in info and (info[nombre].get('check') or info[nombre].get('unique')), 'Falta restricción '+nombre)
                c.execute('SELECT codigo FROM deportistas_tipodocumento ORDER BY codigo')
                exigir([r[0] for r in c.fetchall()] == ['CC','CE','DNI','PA','PPT','RC','TI'], 'Catálogo inicial inesperado.')
                c.execute('SELECT COUNT(*) FROM deportistas_cambiodocumentodeportista')
                exigir(c.fetchone()[0] == 0, 'Historial documental inventado.')
                c.execute('SELECT COUNT(*) FROM deportistas_deportista WHERE tipo_documento_id IS NOT NULL OR numero_documento IS NOT NULL OR pais_emisor IS NOT NULL')
                exigir(c.fetchone()[0] == 0, 'Documento asignado a registro anterior.')
                c.execute("SELECT COUNT(*) FROM django_content_type WHERE app_label='deportistas' AND model IN ('tipodocumento','cambiodocumentodeportista')")
                exigir(c.fetchone()[0] == 2, 'Tipos de contenido inesperados.')
                c.execute("SELECT COUNT(*) FROM auth_permission WHERE content_type_id IN (SELECT id FROM django_content_type WHERE app_label='deportistas' AND model IN ('tipodocumento','cambiodocumentodeportista'))")
                exigir(c.fetchone()[0] == 8, 'Permisos de modelo inesperados.')
                c.execute("SELECT COUNT(*) FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid WHERE t.relname=ANY(%s) AND (NOT i.indisvalid OR NOT i.indisready)", [sorted(NUEVAS | {'deportistas_deportista'})])
                exigir(c.fetchone()[0] == 0, 'Índice inválido.')
                c.execute("SELECT COUNT(*) FROM pg_constraint WHERE conrelid IN (SELECT oid FROM pg_class WHERE relname=ANY(%s)) AND NOT convalidated", [sorted(NUEVAS | {'deportistas_deportista'})])
                exigir(c.fetchone()[0] == 0, 'Restricción sin validar.')
            despues = huellas(connection, columnas)
            exigir(despues == antes, 'Cambios en registros preexistentes: se revierte.')
            final = MigrationExecutor(connection)
            exigir(not final.migration_plan(final.loader.graph.leaf_nodes()), 'Quedan migraciones pendientes.')
            datos.update(estado='verificada_dentro_transaccion', huellas_despues=despues, tipos_catalogo=7,
                         historial_documental=0, documentos_asignados=0, metadatos_nuevos={'content_types':2,'permissions':8}, pendientes=[])
        datos['estado'] = 'aplicada_y_confirmada'
        guardar(manifiesto, datos)
    except Exception as error:
        datos.update(estado='detenida_transaccion_revertida', tipo_error=type(error).__name__)
        guardar(manifiesto, datos)
        if isinstance(error, RuntimeError):
            raise SystemExit(str(error))
        raise SystemExit('Operación detenida; revisar manifiesto privado. Tipo: '+type(error).__name__)
    print('Aplicada exclusivamente deportistas.0002_identificacion_documental. 15 operaciones, siete tipos, diez restricciones; cero pendientes.', flush=True)
    print('Las 29 tablas preexistentes conservan sus filas y huellas de columnas originales. Identidad y relaciones intactas; documentos pendientes.', flush=True)
    print('Manifiesto:', manifiesto.relative_to(RAIZ).as_posix(), flush=True)

if __name__ == '__main__':
    ejecutar()
