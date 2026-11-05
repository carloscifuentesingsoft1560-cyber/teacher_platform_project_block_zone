"""Pruebas aisladas: Django crea y elimina una base temporal con nombre único."""
import os
from pathlib import Path
import uuid
from django.core.exceptions import ImproperlyConfigured
from .aislamiento_pruebas import validar_entorno

# Fallar antes de cargar .env o abrir conexiones si no se usa el ejecutor aislado.
_raiz = Path(__file__).resolve().parents[2]
try:
    _carpeta, _puerto = validar_entorno(os.environ, _raiz)
except (OSError, ValueError, IndexError, KeyError) as error:
    raise ImproperlyConfigured("Usa scripts/pruebas_postgresql_aisladas.py; se rechaza cualquier base no aislada.") from error

from .settings import *  # noqa: E402,F403
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql', 'NAME': 'postgres', 'USER': 'postgres',
    'PASSWORD': '', 'HOST': '127.0.0.1', 'PORT': str(_puerto), 'CONN_MAX_AGE': 0,
    'OPTIONS': {'connect_timeout': 5, 'passfile': str(_carpeta / 'pgpass-vacio'), 'sslmode': 'disable'},
    'TEST': {'NAME': 'test_zdb_fase3_' + uuid.uuid4().hex[:12]},
}}
ZDB_ARCHIVOS_PRIVADOS = _carpeta / 'archivos_privados'
MEDIA_ROOT = _carpeta / 'archivos_privados'
STATIC_ROOT = _carpeta / 'staticfiles'
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
ALLOWED_HOSTS = ["testserver","localhost","127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173","http://127.0.0.1:5173"]
