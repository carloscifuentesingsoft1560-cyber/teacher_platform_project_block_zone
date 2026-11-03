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
entorno = raiz / ".venv-local"
if Path(sys.prefix).resolve() != entorno.resolve():
    site.addsitedir(os.getenv("ZDB_PAQUETES_PYTHON", str(entorno / "Lib" / "site-packages")))
    if os.name == "nt":
        libpq = Path(os.getenv("ZDB_LIBPQ_DIR", "C:/Program Files/PostgreSQL/17/bin"))
        if libpq.is_dir():
            os.environ["PATH"] = str(libpq) + os.pathsep + os.environ.get("PATH", "")
            os.environ.setdefault("PSYCOPG_IMPL", "python")
            directorio_dll = os.add_dll_directory(str(libpq))
sys.path.insert(0, str(raiz / "backend"))
sys.argv = ["manage.py", *sys.argv[1:]]
runpy.run_path(str(raiz / "backend" / "manage.py"), run_name="__main__")
