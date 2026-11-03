# Instalación controlada de estructura administrativa B3-B1

Estado: **aplicada y verificada** bajo autorización expresa del usuario.

Inicio: 30 de octubre de 2026, 20:58:11 UTC (15:58:11 de Bogotá).
Finalización: 20:58:12,690261 UTC.

## Objetivo y destino

Se aplicó exclusivamente `inscripciones.0003_revisionadministrativa_resultadoadministrativo_and_more` mediante `scripts/django_local.py`, usando los paquetes del entorno existente y `MigrationExecutor` limitado al objetivo y al plan comprobado. No se ejecutó una orden que aplicara todas las migraciones pendientes ni señales de aprovisionamiento de permisos.

Destino efectivo comprobado antes de aplicar y utilizado en la instalación:

- PostgreSQL 17.11, `127.0.0.1:5432`.
- Base `zona_bloque`, esquema `public`.
- B1 `inscripciones.0002_progresioninstitucional_eventoprogresion_and_more` aplicada.
- Única migración pendiente: `0003` indicada arriba.

SHA-256 del archivo B3 aplicado: `5f6fdd0fe87f1bcb37ab5273110f652ca6dc32c3590ee3b8b107a140706c8658`.

B1 conservó su SHA-256 `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`; no se editaron migraciones ni código para esta instalación.

## Comprobaciones previas

La fase previa utilizó una sesión de lectura. Se confirmó identidad efectiva, historial coherente, ausencia de conflictos de migraciones y de colisiones de tablas/funciones/triggers B3. No se detectó actividad concurrente incompatible. `makemigrations --check --dry-run` informó `No changes detected`.

Se recalcularon las huellas de todas las filas de las **36 tablas y 266 registros** del inventario preparado: coincidieron exactamente con el respaldo autorizado. Se repitió la comparación dentro de la transacción inmediatamente antes de migrar, bajo bloqueo SHARE de las tablas previas.

Respaldo utilizado, comprobado nuevamente por lectura del archivo y SHA-256:

`respaldos/preparacion_b3_b1_20261030T204551Z/zona_bloque_pre_b3_b1_20261030T204551Z.dump`

SHA-256: `04e20cdb72507efc5593dffecaaa71f463e806f8fd0f623089f7ca7b20107659`.

Se revisó el manifiesto de preparación: lectura completa y restauración aislada correctas, datos/huellas coincidentes y configuración regional igual al origen. Esa restauración ya estaba documentada; no se repitió una auditoría ni se restauró sobre la base real.

## Aplicación

Se ejecutó una única aplicación de la migración, dentro de transacción atómica, con `lock_timeout=5s` y `statement_timeout=120s`. El bloqueo de tablas previas impidió cambios concurrentes durante la comparación, DDL y verificación transaccional. No se cerraron sesiones ajenas.

Nueve operaciones: dos `RunSQL`, dos `CreateModel` y cinco `AddConstraint`. El commit se confirmó después de verificar estructura y conservación de registros dentro de la transacción. Las verificaciones se repitieron en una sesión de lectura después del commit.

No hubo errores, rollback, reintento de aplicación ni restauración automática.

## Estructura instalada

| Tabla nueva | Columnas | FK verificadas | Registros |
| --- | ---: | ---: | ---: |
| `public.inscripciones_revisionadministrativa` | 9 | 3 | 0 |
| `public.inscripciones_resultadoadministrativo` | 12 | 5 | 0 |

Se verificaron todas las columnas contra los modelos, FK contra tablas/columnas destino y restricciones validadas. Restricciones explícitas de dominio:

- `revision_admin_numero_unico`.
- `revision_admin_numero_positivo`.
- `resultado_admin_fila_unica`.
- `resultado_admin_clave_unica`.
- `resultado_admin_b1_sin_ejecucion`.

Además permanecen PK, FK, unicidades OneToOne, comprobaciones numéricas e índices automáticos de Django, detallados en la evidencia de introspección.

Funciones nuevas en `public`: `zdb_administracion_b3_guardia`, `zdb_administracion_b3_evento`. Ambas verificadas como `SECURITY INVOKER` con `search_path=pg_catalog`.

Triggers activos sobre las dos tablas nuevas:

- `zdb_revision_b3_inmutable`.
- `zdb_resultado_b3_inmutable`.
- `zdb_revision_b3_evento`.
- `zdb_resultado_b3_evento`.

Se comprobó que los dos triggers de auditoría son diferidos inicialmente. El CHECK de resultados continúa excluyendo ejecución y destino efectivo; el CHECK B1 `ascenso_plan_valido` sigue sin admitir `ejecutado`. No se utilizaron INSERT/UPDATE de prueba para comprobarlo en producción: se inspeccionaron las definiciones y el estado de catálogo.

## Datos y estado posterior

**38 tablas**, **31 migraciones aplicadas**, **cero migraciones pendientes**. Las dos tablas B3 permanecen vacías.

Los **266 registros preexistentes** de las 36 tablas conservaron exactamente sus huellas, incluidos usuarios, permisos, datos deportivos, inscripciones, reservas, propuestas, progresiones e historial. La única adición es el registro de esta migración en `django_migrations`: las tablas anteriores suman ahora **267 filas**, sin alteración de sus 266 filas originales.

La comparación excluyó únicamente esa fila nueva por su combinación exacta `app/name`, y comprobó que no aparecieran otras migraciones añadidas ni desapareciera ninguna anterior. No se generaron content types ni permisos nuevos mediante señales posteriores: se respetó el alcance de instalación estructural y conservación de metadatos previos.

Se ejecutaron comprobaciones de lectura de tablas, columnas, restricciones, relaciones, funciones, triggers, conteos, huellas y plan Django. Resultados:

- `check`: `System check identified no issues (0 silenced)`.
- `makemigrations --check --dry-run`: `No changes detected`.
- Comparación de registros preexistentes: idéntica antes/después, dentro de transacción y después del commit.

No se repitieron pruebas con escrituras sobre producción. No se crearon revisiones, resultados, progresiones, decisiones, inscripciones o reservas de prueba.

## Evidencia y límites

Carpeta privada: `respaldos/aplicacion_b3_b1_20261030T205811Z/`.

- `manifiesto_instalacion.json`: destino, respaldo/huellas, operaciones, commit y estado final.
- `huellas_antes.json`.
- `huellas_despues_excluyendo_nuevo_registro_migracion.json`.
- `estructura_y_verificacion.json`.
- `verificacion_posterior_lectura.json`.

La instalación habilita únicamente la estructura y los servicios internos B3-B1 ya auditados. No habilita ejecución de traslados ni cierre efectivo. No se modificaron deportistas, inscripciones, grupos, horarios, cupos, reservas, roles o credenciales. No hubo commits ni push y no se inició B3-B2.

La reversión futura eliminaría las dos tablas B3 y sus registros, si llegaran a existir, y podría dejar referencias JSON históricas sin resolver. No debe usarse como recuperación automática ni restaurarse el dump sobre `zona_bloque` sin una autorización nueva. El respaldo confirmado es anterior a esta instalación; futuras escrituras requerirán un respaldo actualizado para otras intervenciones.

La entrega se detiene después de este informe.
