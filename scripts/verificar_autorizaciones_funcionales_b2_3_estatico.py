"""B2.3 A sin SQL ni .env. --generar crea únicamente 0004 ausente."""
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
settings.configure(SECRET_KEY='b23-estatico-sin-credenciales',
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
    from deportistas import modelos_autorizaciones_funcionales as m
    modelos = [getattr(m, nombre) for nombre in ('ExpedienteAutorizacionFuncional',
        'PropuestaDecisionFuncionalVersion', 'AlcanceDecisionFuncional', 'CondicionDecisionFuncional',
        'AdaptacionDecisionFuncional', 'ReferenciaEvidenciaFuncional', 'EventoExpedienteFuncional')]
    if sys.argv[1:] == ['--generar']:
        destino = RAIZ / 'backend/deportistas/migrations/0004_expedientes_funcionales_b2_3.py'
        if destino.exists():
            raise RuntimeError('No sobrescribir migraciones')
        original = MigrationLoader.load_disk

        def sin_guardia(loader):
            original(loader)
            loader.disk_migrations.pop(('deportistas', '0005_guardias_expedientes_funcionales_b2_3'), None)

        with patch.object(MigrationLoader, 'load_disk', sin_guardia):
            loader = MigrationLoader(None)
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(
            graph=loader.graph, migration_name='expedientes_funcionales_b2_3')
        assert set(cambios) == {'deportistas'} and len(cambios['deportistas']) == 1
        migracion = cambios['deportistas'][0]
        for dependencia in [('cuentas', '0011_guardias_mandatos_acreditaciones_b2_1'), ('biblioteca', '0005_guardias_catalogo_funcional_b2_2')]:
            if dependencia not in migracion.dependencies:
                migracion.dependencies.append(dependencia)
        escritor = MigrationWriter(migracion)
        assert Path(escritor.path).resolve() == destino
        with destino.open('x', encoding='utf-8') as archivo:
            archivo.write(escritor.as_string())
        print('0004 generada sin SQL, .env ni settings del proyecto.')
    elif sys.argv[1:]:
        raise RuntimeError('Opción no admitida')
    else:
        for nombre in ('backend/deportistas/modelos_autorizaciones_funcionales.py', 'backend/deportistas/models.py',
            'backend/deportistas/servicios_autorizaciones_funcionales.py', 'backend/deportistas/test_autorizaciones_funcionales.py',
            'backend/deportistas/migrations/0004_expedientes_funcionales_b2_3.py',
            'backend/deportistas/migrations/0005_guardias_expedientes_funcionales_b2_3.py',
            'scripts/verificar_autorizaciones_funcionales_b2_3_estatico.py'):
            texto = (RAIZ / nombre).read_text(encoding='utf-8')
            ast.parse(texto, filename=nombre)
            assert all(linea.rstrip() == linea for linea in texto.splitlines()), nombre
        loader = MigrationLoader(None)
        loader.graph.ensure_not_cyclic()
        cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(graph=loader.graph)
        assert not cambios, list(cambios)
        for modelo in modelos:
            assert not modelo.check(), modelo.check()
            assert modelo._meta.default_permissions == ()
            assert not {'aprobado', 'vigente', 'activo', 'autorizado'}.intersection(f.name for f in modelo._meta.fields)
            for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                              lambda: modelo.objects.all().update(id=1), lambda: modelo.objects.all().delete(),
                              lambda: modelo.objects.bulk_update([], ['id'])):
                try:
                    operacion()
                except ValidationError:
                    pass
                else:
                    raise AssertionError('Guardia ORM ausente')
        assert {v for v, _ in m.EventoExpedienteFuncional._meta.get_field('accion').choices} == {'propuesta', 'revision', 'retiro'}
        assert 'dotenv' not in sys.modules
        print('OK: 7 archivos Python, 7 modelos, 35 guardias ORM, sin permisos genéricos; grafo acíclico; No changes detected. Sin SQL ni .env.')
