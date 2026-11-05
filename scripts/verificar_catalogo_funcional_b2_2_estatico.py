"""Verificación B2.2 sin SQL/settings/.env; --generar crea solo 0004 ausente."""
import ast
import os
from pathlib import Path
import site
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
paquetes = Path(os.environ['ZDB_PAQUETES_PYTHON']).resolve()
site.addsitedir(str(paquetes))
sys.path.insert(0, str(RAIZ / 'backend'))
from django.conf import settings
settings.configure(SECRET_KEY='b22-estatico-sin-credenciales',
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'cuentas', 'deportistas',
                    'organizacion', 'inscripciones', 'auditoria', 'recursos', 'curriculo', 'biblioteca', 'sesiones'],
    AUTH_USER_MODEL='cuentas.Usuario', DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}}, USE_TZ=True)
from django.db.backends.base.base import BaseDatabaseWrapper

with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=AssertionError('Conexión prohibida')):
    import django
    assert Path(django.__file__).resolve().is_relative_to(paquetes)
    django.setup()
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.writer import MigrationWriter
    from django.core.exceptions import ValidationError
    from biblioteca import modelos_funcionales as m
    modelos = [getattr(m, n) for n in ('PerfilFuncional', 'PerfilFuncionalVersion',
        'ExigenciaPerfilFuncional', 'CondicionPerfilFuncional', 'AdaptacionPerfilFuncional',
        'ProcedenciaPerfilFuncional', 'EventoPerfilFuncional', 'CorrespondenciaFuncional',
        'CorrespondenciaFuncionalVersion', 'EventoCorrespondenciaFuncional')]
    if sys.argv[1:] == ['--generar']:
        destino = RAIZ / 'backend/biblioteca/migrations/0004_catalogo_funcional_b2_2.py'
        if destino.exists():
            raise RuntimeError('No sobrescribir migraciones')
        original = MigrationLoader.load_disk

        def sin_guardia(loader):
            original(loader)
            loader.disk_migrations.pop(('biblioteca', '0005_guardias_catalogo_funcional_b2_2'), None)

        with patch.object(MigrationLoader, 'load_disk', sin_guardia):
            loader = MigrationLoader(None)
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(
            graph=loader.graph, migration_name='catalogo_funcional_b2_2')
        assert set(cambios) == {'biblioteca'} and len(cambios['biblioteca']) == 1
        migracion = cambios['biblioteca'][0]
        for dependencia in [('sesiones', '0007_seguimiento_inmutable'), ('recursos', '0003_identidades_estables')]:
            if dependencia not in migracion.dependencies:
                migracion.dependencies.append(dependencia)
        escritor = MigrationWriter(migracion)
        assert Path(escritor.path).resolve() == destino
        with destino.open('x', encoding='utf-8') as archivo:
            archivo.write(escritor.as_string())
        print('0004 generada sin conexión, settings del proyecto ni .env.')
    elif sys.argv[1:]:
        raise RuntimeError('Opción no admitida')
    else:
        archivos = ['backend/biblioteca/modelos_funcionales.py', 'backend/biblioteca/models.py',
            'backend/biblioteca/servicios_funcionales.py', 'backend/biblioteca/test_funcional.py',
            'backend/biblioteca/migrations/0004_catalogo_funcional_b2_2.py',
            'backend/biblioteca/migrations/0005_guardias_catalogo_funcional_b2_2.py',
            'scripts/verificar_catalogo_funcional_b2_2_estatico.py']
        for nombre in archivos:
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            ast.parse(texto, filename=nombre)
            assert all(linea == linea.rstrip() for linea in texto.splitlines()), nombre
        loader = MigrationLoader(None)
        loader.graph.validate_consistency()
        loader.graph.ensure_not_cyclic()
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(graph=loader.graph)
        assert not cambios, list(cambios)
        for modelo in modelos:
            assert not modelo.check(), modelo.check()
            assert modelo._meta.default_permissions == ('view',)
            assert not {'activo', 'aprobado', 'vigente', 'autorizado'}.intersection(f.name for f in modelo._meta.fields)
            for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                              lambda: modelo.objects.all().update(id=1), lambda: modelo.objects.all().delete(),
                              lambda: modelo.objects.bulk_update([], ['id'])):
                try:
                    operacion()
                except ValidationError:
                    pass
                else:
                    raise AssertionError('Guardia ORM ausente')
        for modelo in (m.EventoPerfilFuncional, m.EventoCorrespondenciaFuncional):
            assert {v for v, _ in modelo._meta.get_field('accion').choices} == {'propuesta', 'revision', 'retiro'}
        assert 'dotenv' not in sys.modules
        print('OK: 7 archivos Python; 10 modelos; 50 barreras ORM; acciones cerradas; grafo acíclico; No changes detected. Sin SQL ni .env.')
