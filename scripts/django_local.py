"""Ejecuta Django usando los paquetes del entorno .venv-local existente.

Para la suite completa usar scripts/pruebas_postgresql_aisladas.py con un Python
compatible ejecutable; ver docs/PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md.
Si el lanzador del entorno no es ejecutable, puede usarse otro Python compatible
para los paquetes puros, sin alterar .venv-local ni instalar paquetes globales.
"""
import os
from pathlib import Path
import runpy
import site
import sys

raiz = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(raiz / 'backend'))
if os.environ.get('DJANGO_SETTINGS_MODULE') == 'configuracion.settings_pruebas_postgresql' or os.environ.get('ZDB_PG_TEST_RUN'):
    from configuracion.aislamiento_pruebas import validar_entorno
    validar_entorno(os.environ, raiz)
    if len(sys.argv) < 2 or sys.argv[1] not in ('test', 'makemigrations'):
        raise RuntimeError('El lanzador aislado solo admite test y comprobación de migraciones')
    if any(a.startswith('--settings') and a != '--settings=configuracion.settings_pruebas_postgresql'
           for a in sys.argv[2:]):
        raise RuntimeError('No se permite sustituir los settings aislados')
    if any(a.startswith(('--database', '--keepdb')) for a in sys.argv[2:]):
        raise RuntimeError('No se permite reutilizar ni seleccionar bases existentes')
    if sys.argv[1] == 'makemigrations' and not {'--check', '--dry-run'}.issubset(sys.argv):
        raise RuntimeError('El lanzador aislado no genera ni aplica migraciones')
entorno = raiz / ".venv-local"
if Path(sys.prefix).resolve() != entorno.resolve():
    site.addsitedir(os.getenv("ZDB_PAQUETES_PYTHON", str(entorno / "Lib" / "site-packages")))
    if os.name == "nt":
        libpq = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin"))
        if libpq.is_dir():
            os.environ["PATH"] = str(libpq) + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("PSYCOPG_IMPL", "python")
            directorio_dll = os.add_dll_directory(str(libpq))
if os.environ.get('ZDB_PG_TEST_RUN'):
    import django
    if not Path(django.__file__).resolve().is_relative_to(Path(os.environ['ZDB_PAQUETES_PYTHON']).resolve()):
        raise RuntimeError('Django no procede del directorio explícito de paquetes')
sys.path.insert(0, str(raiz / "backend"))
sys.argv = ["manage.py", *sys.argv[1:]]
runpy.run_path(str(raiz / "backend" / "manage.py"), run_name="__main__")
