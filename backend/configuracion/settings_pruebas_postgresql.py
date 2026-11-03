"""Pruebas aisladas: Django crea y elimina una base temporal con nombre único."""
import os
from pathlib import Path
import uuid
from django.core.exceptions import ImproperlyConfigured

# Fallar antes de cargar .env o abrir conexiones si no se usa el ejecutor aislado.
_cluster = os.environ.get("ZDB_PG_TEST_CLUSTER", "")
_raiz = Path(__file__).resolve().parents[2]
try:
    _datos = Path(_cluster).resolve()
    _pid = (_datos / "postmaster.pid").read_text().splitlines()
    _ruta_valida = _datos.is_relative_to((_raiz / "respaldos").resolve()) and _datos.name == "cluster"
    _conexion_valida = (
        os.environ.get("POSTGRES_HOST") == "127.0.0.1"
        and os.environ.get("POSTGRES_DB") == "postgres"
        and os.environ.get("POSTGRES_USER") == "postgres"
        and os.environ.get("POSTGRES_PORT") == _pid[3]
        and int(_pid[0]) > 0 and Path(_pid[1]).resolve() == _datos
    )
except (OSError, ValueError, IndexError):
    _ruta_valida = _conexion_valida = False
if not _cluster or not _ruta_valida or not _conexion_valida:
    raise ImproperlyConfigured("Usa scripts/pruebas_postgresql_aisladas.py; se rechaza cualquier base no aislada.")

from .settings import *  # noqa: E402,F403
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": "test_zdb_fase3_" + uuid.uuid4().hex[:12]}  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["testserver","localhost","127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173","http://127.0.0.1:5173"]
