"""B2.1 sin conexiones ni .env. --generar crea solo la migración 0010 ausente."""
import ast
from pathlib import Path
import os
import site
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
raiz = Path(__file__).resolve().parents[1]
if os.environ.get('ZDB_PAQUETES_PYTHON'):
    site.addsitedir(os.environ['ZDB_PAQUETES_PYTHON'])
sys.path.insert(0, str(raiz / 'backend'))
from django.conf import settings

settings.configure(SECRET_KEY='b21-estatico-sin-credenciales',
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'cuentas', 'deportistas',
                    'organizacion', 'inscripciones', 'auditoria', 'recursos', 'curriculo', 'biblioteca', 'sesiones'],
    AUTH_USER_MODEL='cuentas.Usuario', DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}}, USE_TZ=True)
from django.db.backends.base.base import BaseDatabaseWrapper

with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=AssertionError('Conexión prohibida')):
    import django
    django.setup()
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.writer import MigrationWriter
    from django.core.exceptions import ValidationError
    from cuentas.models import (MandatoInstitucional, EventoMandatoInstitucional,
                                AcreditacionEmisora, EventoAcreditacionEmisora)

    destino = raiz / 'backend/cuentas/migrations/0010_mandatos_acreditaciones_b2_1.py'
    if sys.argv[1:] == ['--generar']:
        if destino.exists():
            raise RuntimeError('No se sobrescribe una migración existente')
        cargar_disco = MigrationLoader.load_disk

        def cargar_sin_guardia_pendiente(loader):
            cargar_disco(loader)
            loader.disk_migrations.pop(('cuentas', '0011_guardias_mandatos_acreditaciones_b2_1'), None)

        with patch.object(MigrationLoader, 'load_disk', cargar_sin_guardia_pendiente):
            loader = MigrationLoader(None)
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(
            graph=loader.graph, migration_name='mandatos_acreditaciones_b2_1')
        assert set(cambios) == {'cuentas'} and len(cambios['cuentas']) == 1
        escritor = MigrationWriter(cambios['cuentas'][0])
        assert Path(escritor.path).resolve() == destino
        with destino.open('x', encoding='utf-8') as archivo:
            archivo.write(escritor.as_string())
        print('OK: 0010 generada con backend dummy y MigrationLoader(None), sin SQL ni .env.')
    elif sys.argv[1:]:
        raise RuntimeError('Única opción admitida: --generar')
    else:
        archivos = ['backend/cuentas/modelos_acreditaciones_emisoras.py', 'backend/cuentas/models.py',
                    'backend/cuentas/servicios_competencias_emisoras.py',
                    'backend/cuentas/migrations/0010_mandatos_acreditaciones_b2_1.py',
                    'backend/cuentas/migrations/0011_guardias_mandatos_acreditaciones_b2_1.py',
                    'backend/cuentas/tests/test_acreditaciones_emisoras.py',
                    'scripts/verificar_acreditaciones_emisoras_b2_1_estatico.py']
        for nombre in archivos:
            texto = (raiz / nombre).read_text(encoding='utf-8')
            ast.parse(texto, filename=nombre)
            assert all(linea.rstrip() == linea for linea in texto.splitlines()), nombre
        loader = MigrationLoader(None)
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(graph=loader.graph)
        assert not cambios, list(cambios)
        for modelo in (MandatoInstitucional, EventoMandatoInstitucional, AcreditacionEmisora, EventoAcreditacionEmisora):
            assert not modelo.check(), modelo.check()
            assert modelo._meta.default_permissions == ('view',)
            assert not {'activo', 'aprobado', 'vigente'}.intersection(f.name for f in modelo._meta.fields)
            for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                              lambda: modelo.objects.all().update(id=1), lambda: modelo.objects.all().delete(),
                              lambda: modelo.objects.bulk_update([], ['id'])):
                try:
                    operacion()
                except ValidationError:
                    pass
                else:
                    raise AssertionError('Guardia ORM ausente')
        for modelo in (EventoMandatoInstitucional, EventoAcreditacionEmisora):
            assert {v for v, _ in modelo._meta.get_field('accion').choices} == {'propuesta', 'revision', 'retiro'}
        print('OK: siete archivos Python, grafo/modelos coherentes, checks de cuatro modelos y veinte guardias ORM.')
        print('OK: solo lectura predeterminada; acciones pendientes sin aprobación ni activación. Sin ejecutar SQL.')
