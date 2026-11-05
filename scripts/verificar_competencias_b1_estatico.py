"""Comprobaciones B1 sin .env, settings del proyecto, SQL ni conexiones.

Usar Python compatible con Django instalado; opcionalmente ZDB_PAQUETES_PYTHON
señala exclusivamente su directorio de paquetes. No genera archivos.
"""
import ast
import os
from pathlib import Path
import site
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
raiz = Path(__file__).resolve().parents[1]
paquetes = os.environ.get('ZDB_PAQUETES_PYTHON')
if paquetes:
    site.addsitedir(paquetes)
sys.path.insert(0, str(raiz / 'backend'))

from django.conf import settings

settings.configure(
    SECRET_KEY='b1-estatico-sin-credenciales',
    INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'cuentas',
                    'deportistas', 'organizacion', 'inscripciones', 'auditoria',
                    'recursos', 'curriculo', 'biblioteca', 'sesiones'],
    AUTH_USER_MODEL='cuentas.Usuario', DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    DATABASES={'default': {'ENGINE': 'django.db.backends.dummy'}}, USE_TZ=True,
)

from django.db.backends.base.base import BaseDatabaseWrapper

with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=AssertionError('Conexión prohibida')):
    import django
    django.setup()
    from django.core.exceptions import ValidationError
    from django.db.migrations.autodetector import MigrationAutodetector
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.state import ProjectState
    from cuentas.models import CompetenciaEmisora, EventoCompetenciaEmisora

    archivos = ['backend/cuentas/models.py', 'backend/cuentas/modelos_competencias.py',
                'backend/cuentas/migrations/0008_competencia_emisora_b1.py',
                'backend/cuentas/migrations/0009_competencia_emisora_guardias_b1.py',
                'backend/cuentas/tests/test_competencias_b1.py',
                'scripts/verificar_competencias_b1_estatico.py']
    for archivo in archivos:
        ast.parse((raiz / archivo).read_text(encoding='utf-8'), filename=archivo)
    print('OK: sintaxis de los seis archivos Python B1.')

    loader = MigrationLoader(None)
    cambios = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(django.apps.apps)).changes(graph=loader.graph)
    if cambios:
        raise AssertionError(f'Diferencias modelos/migraciones: {list(cambios)}')
    print('OK: grafo de migraciones y estado de modelos coincidentes, sin aplicar migraciones.')

    for modelo in (CompetenciaEmisora, EventoCompetenciaEmisora):
        errores = modelo.check()
        if errores:
            raise AssertionError(errores)
        if modelo._meta.default_permissions != ('view',):
            raise AssertionError('Permisos de escritura no admitidos en B1')
        for operacion in (lambda: modelo(pk=1).save(), lambda: modelo(pk=1).delete(),
                          lambda: modelo.objects.all().update(id=1), lambda: modelo.objects.all().delete(),
                          lambda: modelo.objects.bulk_update([], ['id'])):
            try:
                operacion()
            except ValidationError:
                pass
            else:
                raise AssertionError('Guardia ORM ausente')
    acciones = {valor for valor, _ in EventoCompetenciaEmisora._meta.get_field('accion').choices}
    if acciones != {'propuesta', 'revision', 'retiro'}:
        raise AssertionError('B1 no admite aprobación ni activación')
    print('OK: checks de modelos, cinco guardias ORM por modelo y acciones sin aprobación.')
    print('NO EJECUTADO: DDL, triggers, pruebas de base de datos o concurrencia PostgreSQL.')
