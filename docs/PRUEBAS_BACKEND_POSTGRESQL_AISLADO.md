# Pruebas backend con PostgreSQL temporal aislado

Procedimiento endurecido en F3.6-B1.1, 5 de noviembre de 2026. Sustituye las rutas históricas bajo `respaldos/`. No modifica el procedimiento operativo de la aplicación. Se verificaron 24/24 pruebas de barreras y 13/13 pruebas B1 en PostgreSQL temporal bajo autorización explícita. Cualquier nueva ejecución requiere su autorización correspondiente.

## Preparación y comando

Desde la raíz del proyecto en PowerShell:

```powershell
$pythonPruebas = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $pythonPruebas --version
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:ZDB_PAQUETES_PYTHON = 'C:/Users/57310/Desktop/Proyectos_Carlos/teacher_platform_project_block_zone/.venv-local/Lib/site-packages'
$env:ZDB_LIBPQ_DIR = 'C:/Program Files/PostgreSQL/17/bin'
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
& $pythonPruebas scripts/test_infraestructura_aislada.py
# Solo después de autorización para iniciar PostgreSQL:
& $pythonPruebas -I -B scripts/pruebas_postgresql_aisladas.py --etiqueta cuentas.tests.test_competencias_b1 --failfast --verbosity 2
```

Revisar `$LASTEXITCODE` después de cada comando: debe ser 0; detenerse ante un fallo. La ruta de paquetes indicada corresponde al entorno existente contiguo, reutilizado exclusivamente como dependencia. El workspace actual no contiene `.venv-local`. El ejecutor valida las carpetas `django`, `rest_framework`, `psycopg` y `dotenv` antes de crear archivos o procesos; no instala paquetes. Si se utiliza otro entorno, especificar su ruta absoluta y verificar su compatibilidad. El lanzador comprueba que Django procede de esa ruta, fuerza psycopg en modo Python y carga la libpq del directorio PostgreSQL explícito.

Se requieren los binarios locales PostgreSQL 17 `initdb.exe`, `postgres.exe`, `pg_ctl.exe`, `pg_isready.exe` y `psql.exe`. Ruta predeterminada: `C:/Program Files/PostgreSQL/17/bin`. Para otra instalación, establecer `$env:ZDB_LIBPQ_DIR` a su directorio antes del comando. La ausencia de binarios es un error, no motivo para recurrir a la base operativa. No requiere descargar dependencias ni disponer de las credenciales de la base real.

No se necesita habilitar ejecución de scripts PowerShell ni cambiar ExecutionPolicy: los comandos invocan directamente Python.

## Garantías y límites del ejecutor

1. Solo acepta `--failfast`, `--verbosity 0..3` y `--etiqueta` con nombres de módulos dentro de las apps admitidas. `--settings`, `--keepdb`, `--database` y otros argumentos se rechazan antes de crear el clúster. Sin etiquetas ejecuta la suite completa existente. No se reenvían argumentos arbitrarios a Django.
2. Rechaza `ZDB_GENERAR_ASCENSOS` si tiene valor. La antigua vía opcional de generación de migraciones quedó retirada de este ejecutor. El chequeo final utiliza únicamente `makemigrations --check --dry-run`.
3. Crea mediante `mkdtemp` una carpeta exclusiva `<temporal-del-sistema>/zdb_pg_<aleatorio>/`; rechaza un temporal situado dentro del repositorio. El clúster va en `cluster/`, con puerto temporal y proceso hijo oculto limitado a 127.0.0.1. No crea ni modifica nada en `respaldos/`. La autenticación trust se limita a este clúster local efímero.
4. Construye el entorno hijo mediante lista positiva de variables básicas de Windows. No hereda PATH, variables PG*, POSTGRES*, Django, secretos ni overrides Python. Configura explícitamente conexión local ficticia, binarios, paquetes, clave de prueba y psycopg. Crea archivos vacíos propios `pgpass-vacio` y `pgservice-vacio`, y un directorio `pgconf/`; solo permite las variables libpq asociadas a esos destinos, ssl deshabilitado y timeout de conexión. TEMP/TMP/TMPDIR apuntan a `tmp/`; HOME/USERPROFILE/APPDATA/LOCALAPPDATA a `home/`. El PATH hijo contiene binarios explícitos, directorio del intérprete y System32.
5. Antes de Django contrasta directorio, dirección y puerto devueltos por PostgreSQL con el destino nuevo, y PID, directorio, puerto y escucha de `postmaster.pid` con el hijo creado. Solo entonces escribe `identidad.json`. El lanzador y los settings revalidan ese manifiesto, los archivos vacíos, los destinos y el entorno. `settings.py` omite completamente dotenv para el perfil PostgreSQL aislado. Los settings fijan nuevamente la conexión sin valores operativos ni rutas a respaldos. Son barreras contra errores de operación, no una frontera frente a un usuario local malicioso que modifique código/manifiesto/procesos.
6. Django crea una base de prueba con nombre único dentro de ese clúster, aplica allí las migraciones históricas, ejecuta las apps existentes y destruye esa base al finalizar. Aplicar migraciones en ese destino temporal es parte de la prueba, no una migración operativa.
7. Si la suite pasa, ejecuta el chequeo de diferencias entre modelos y migraciones. Si falla, conserva el resultado y no declara validada la instalación.
8. El bloque finally detiene únicamente el clúster hijo y guarda resultado.json. No elimina directorios ni respaldos. La evidencia se conserva en el temporal, cuya ruta absoluta se imprime. Un fallo de apagado requiere revisar el resultado y proceso concreto; no detener el servicio PostgreSQL operativo.

El directorio de trabajo de los procesos es la carpeta nueva. Los archivos privados y MEDIA_ROOT apuntan a `archivos_privados/`, y STATIC_ROOT a `staticfiles/` dentro de ella. PostgreSQL crea sus archivos internos solo en `cluster/`. Los hijos Python se inician con `-I -B`; el lanzador aislado rechaza comandos distintos de `test` y `makemigrations --check --dry-run`, sustitución de settings y reutilización/selección de base.

No ejecutar `django_local.py test --settings=configuracion.settings` ni usar settings_pruebas_postgresql directamente. Estos últimos ahora rechazan ausencia de un clúster temporal identificado. SQLite sigue disponible para pruebas específicas compatibles, pero la suite completa falla al aplicar el SQL PostgreSQL de ascensos: no modificar migraciones históricas para ocultarlo.

## Evidencia y diagnóstico

Cada ejecución conserva `initdb.log`, `servidor.log`, `pruebas.log`, `migraciones_check.log` cuando proceda, `identidad.json` tras verificar el servidor y `resultado.json`. Este último registra versión Python, rutas explícitas de paquetes/binarios, puerto, directorio, códigos de salida, error si existe y estado de apagado. También quedan `tmp/`, `home/`, `pgconf/` y los archivos libpq propios. Todo se ubica en la carpeta temporal nueva fuera del repositorio; no publicar logs sin revisión.

Las 24 pruebas de barreras aprobadas crean únicamente carpetas temporales propias con archivos de identidad simulados. Prueban importación de settings sin dotenv y con conexiones prohibidas, desvíos de entorno/identidad, un fallo de initdb simulado y la detención protegida con subprocess sustituido. No arrancan PostgreSQL. Su resultado se complementó con la ejecución real aislada de B1 indicada a continuación.

La segunda ejecución controlada descubrió y ejecutó exclusivamente las 13 pruebas de `cuentas.tests.test_competencias_b1`: 13 aprobadas, cero fallidas y cero omitidas. `0008` y `0009` se aplicaron satisfactoriamente en la base temporal nueva `test_zdb_fase3_f2159c956366`; se aprobaron restricciones SQL, triggers, inmutabilidad, rollback y concurrencia. El chequeo posterior de modelos/migraciones devolvió `No changes detected`, código 0. El clúster hijo quedó detenido con identidad revalidada, cierre controlado y sin incidentes. Evidencia conservada en `C:\Users\57310\AppData\Local\Temp\zdb_pg_chbim1fd`. La ejecución previa y sus evidencias no se reutilizaron ni modificaron. No se ejecutaron otras suites de regresión ni migraciones operativas.

## Migraciones B1 y recuperación

`cuentas.0009_competencia_emisora_guardias_b1` es deliberadamente irreversible: no tiene `reverse_sql` y una reversión debe fallar antes de retirar guardias. No se debe habilitar una instalación detenida en `0008`, que contiene las tablas pero todavía no las protecciones SQL de `0009`. Una recuperación requiere procedimiento revisado; no se resuelve desactivando triggers ni editando migraciones históricas. Las pruebas de rollback de transacciones no equivalen a revertir migraciones.

- Error antes de crear clúster: revisar argumentos, variable retirada y binarios.
- Error de arranque: revisar initdb.log/servidor.log, sin cambiar puertos o servicio operativo.
- Error de identidad: detener la prueba y revisar el clúster generado; no quitar las barreras.
- Fallo de tests o migraciones: código distinto de 0. Conservar evidencia, corregir únicamente dentro del alcance autorizado y repetir la comprobación afectada.
- `detenido: false` o proceso interrumpido externamente: comprobar PID/directorio del clúster temporal antes de cualquier acción manual. Un apagado forzado del equipo no está cubierto por finally.

La suite prueba fixtures ficticias. No cargar fixtures en zona_bloque ni llamar a scripts aplicar_*.py para realizar pruebas. El ejecutor no consulta la instalación operativa. Las verificaciones históricas de esa instalación no deben repetirse como requisito de esta etapa.

## Frontend y alcance de aceptación

Desde frontend: `npm.cmd test -- --reporter=dot`, `npm.cmd run test:api` y `npm.cmd run build`. Las pruebas React con jsdom y API simulada no sustituyen revisión visual ni un navegador conectado. La ejecución correcta del núcleo actual no acredita módulos deportivos futuros, escalas científicas ni compatibilidad móvil de captura todavía inexistente.
