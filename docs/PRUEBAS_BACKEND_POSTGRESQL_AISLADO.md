# Pruebas backend con PostgreSQL temporal aislado

Procedimiento vigente de Etapa 1, 2 de noviembre de 2026. Sustituye como guía integral las instrucciones históricas que ejecutan la suite completa con SQLite o directamente con settings_pruebas_postgresql. No modifica el procedimiento de operación de la aplicación.

## Preparación y comando

Desde la raíz del proyecto en PowerShell:

```powershell
$pythonPruebas = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $pythonPruebas --version
$env:PYTHONDONTWRITEBYTECODE = '1'
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
& $pythonPruebas scripts/test_infraestructura_aislada.py
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --failfast --verbosity 1
```

Revisar `$LASTEXITCODE` después de cada comando: debe ser 0. El runtime comprobado es Python 3.12.14. Se puede asignar otra ruta existente y compatible a `$pythonPruebas`; no instalar paquetes globales ni cambiar el intérprete base automáticamente. Los paquetes Django/DRF se reutilizan de `.venv-local/Lib/site-packages` mediante django_local.py. El lanzador `.venv-local/Scripts/python.exe` apunta actualmente a Python313 inaccesible y no es la ruta reproducible en esta máquina. La compatibilidad de paquetes binarios debe verificarse si cambia el intérprete; el lanzador utiliza psycopg en modo Python con libpq existente.

Se requieren los binarios locales PostgreSQL 17 `initdb.exe`, `postgres.exe`, `pg_ctl.exe`, `pg_isready.exe` y `psql.exe`. Ruta predeterminada: `C:/Program Files/PostgreSQL/17/bin`. Para otra instalación, establecer `$env:ZDB_LIBPQ_DIR` a su directorio antes del comando. La ausencia de binarios es un error, no motivo para recurrir a la base operativa. No requiere descargar dependencias ni disponer de las credenciales de la base real.

No se necesita habilitar ejecución de scripts PowerShell ni cambiar ExecutionPolicy: los comandos invocan directamente Python.

## Garantías y límites del ejecutor

1. Solo acepta `--failfast` y `--verbosity 0..3`; `--settings`, `--keepdb`, `--database` y otros argumentos se rechazan antes de crear el clúster. No se reenvían argumentos arbitrarios a Django.
2. Rechaza `ZDB_GENERAR_ASCENSOS` si tiene valor. La antigua vía opcional de generación de migraciones quedó retirada de este ejecutor. El chequeo final utiliza únicamente `makemigrations --check --dry-run`.
3. Crea un directorio nuevo dentro de `respaldos/pruebas_etapa1_*/cluster`, un puerto temporal y un proceso PostgreSQL hijo oculto, limitado a 127.0.0.1. Se conserva el uso de autenticación trust solo en ese clúster efímero local; no es configuración de producción.
4. Descarta variables libpq PG* heredadas, selección alternativa de settings y credenciales operativas; configura explícitamente host, puerto, base `postgres`, usuario temporal y clave Django ficticia.
5. Antes de Django compara SHOW data_directory y postmaster.pid con el directorio y el PID del hijo creado. Los settings de prueba comprueban además ruta bajo respaldos, directorio, puerto y base antes de importar settings/.env. Son barreras contra errores de operación, no aislamiento frente a un usuario local malicioso.
6. Django crea una base de prueba con nombre único dentro de ese clúster, aplica allí las migraciones históricas, ejecuta las apps existentes y destruye esa base al finalizar. Aplicar migraciones en ese destino temporal es parte de la prueba, no una migración operativa.
7. Si la suite pasa, ejecuta el chequeo de diferencias entre modelos y migraciones. Si falla, conserva el resultado y no declara validada la instalación.
8. El bloque finally detiene únicamente el clúster hijo y guarda resultado.json. No elimina recursivamente directorios ni respaldos. Un fallo de apagado requiere revisar el resultado y proceso concreto; no detener el servicio PostgreSQL operativo.

No ejecutar `django_local.py test --settings=configuracion.settings` ni usar settings_pruebas_postgresql directamente. Estos últimos ahora rechazan ausencia de un clúster temporal identificado. SQLite sigue disponible para pruebas específicas compatibles, pero la suite completa falla al aplicar el SQL PostgreSQL de ascensos: no modificar migraciones históricas para ocultarlo.

## Evidencia y diagnóstico

Cada ejecución conserva `initdb.log`, `servidor.log`, `pruebas.log`, `migraciones_check.log` cuando proceda y `resultado.json`. Este último registra versión Python, puerto, directorio, códigos de salida, error si existe y estado de apagado. Los resultados completos se imprimen también en terminal. Evidencia excluida de Git; no publicar logs sin revisión.

- Error antes de crear clúster: revisar argumentos, variable retirada y binarios.
- Error de arranque: revisar initdb.log/servidor.log, sin cambiar puertos o servicio operativo.
- Error de identidad: detener la prueba y revisar el clúster generado; no quitar las barreras.
- Fallo de tests o migraciones: código distinto de 0. Conservar evidencia, corregir únicamente dentro del alcance autorizado y repetir la comprobación afectada.
- `detenido: false` o proceso interrumpido externamente: comprobar PID/directorio del clúster temporal antes de cualquier acción manual. Un apagado forzado del equipo no está cubierto por finally.

La suite prueba fixtures ficticias. No cargar fixtures en zona_bloque ni llamar a scripts aplicar_*.py para realizar pruebas. El ejecutor no consulta la instalación operativa. Las verificaciones históricas de esa instalación no deben repetirse como requisito de esta etapa.

## Frontend y alcance de aceptación

Desde frontend: `npm.cmd test -- --reporter=dot`, `npm.cmd run test:api` y `npm.cmd run build`. Las pruebas React con jsdom y API simulada no sustituyen revisión visual ni un navegador conectado. La ejecución correcta del núcleo actual no acredita módulos deportivos futuros, escalas científicas ni compatibilidad móvil de captura todavía inexistente.
