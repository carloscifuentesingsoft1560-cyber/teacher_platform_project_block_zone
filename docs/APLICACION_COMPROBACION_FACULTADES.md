# Aplicación de comprobaciones de facultades de acudientes

Fecha: **28 de octubre de 2026, Colombia**. Migración aplicada exclusivamente: **deportistas.0003_comprobacion_facultades**, por autorización expresa del usuario. Destino efectivo confirmado antes de proceder: PostgreSQL **zona_bloque**, esquema **public**.

## Resultado de aplicación

La migración figura aplicada y no quedan migraciones pendientes. Se completaron las ocho operaciones aprobadas:

| Operación | Cantidad | Verificación |
| --- | ---: | --- |
| CreateModel | 1 | Tabla `deportistas_comprobacionfacultad`, inicialmente vacía |
| AddField | 1 | `deportistas_autorizacion.comprobacion_facultad_id` nullable, FK a la tabla nueva |
| AddConstraint | 5 | Una UNIQUE y cuatro CHECK presentes y validadas |
| RunPython | 1 | Función y trigger PostgreSQL de protección creados y habilitados |

Restricciones: `facultad_version_unica`, `facultad_metodo_valido`, `facultad_resultado_valido`, `facultad_revision_suficiente` y `facultad_vigencia_valida`. Se comprobaron asimismo la FK real, los índices válidos/listos y ausencia de restricciones sin validar en las tablas afectadas.

Función: `public.zdb_facultad_historial_inmutable()`. Trigger: `zdb_facultad_no_modificar`, habilitado, por fila, BEFORE UPDATE OR DELETE de la tabla nueva. El tipo interno PostgreSQL comprobado fue 27 (ROW + BEFORE + UPDATE + DELETE); enlaza con la función prevista.

La aplicación fue atómica y respetó las dependencias ya aplicadas: `deportistas.0002_identificacion_documental` y el modelo de usuario intercambiable. El registro de migraciones añadió únicamente 0003. Se crearon el tipo de contenido y el permiso `view_comprobacionfacultad` estándar, sin conceder permisos a usuarios ni grupos. No se alteró ningún archivo de migración.

SHA-256 del archivo aplicado: `eb74789677295641b97013087e14c391bb164ee18a5667bdfd939bc59d7dce54`, coincidente con el inventario aprobado.

## Respaldo previo y restauración funcional

- Archivo: `respaldos/facultades_aplicacion_20261029T031211Z/zona_bloque_antes_facultades.dump`.
- Manifiesto: `respaldos/facultades_aplicacion_20261029T031211Z/manifiesto.json`.
- Tamaño: **155036 bytes**.
- SHA-256: **af42489db15fab7d648748ea62e0a57db618c5baab30e858c534df6a18d2414b**.
- Estado del manifiesto: `aplicada_y_confirmada`.

El nombre usa UTC: `20261029T031211Z` corresponde al 28 de octubre a las 22:12:11 en Colombia.

Antes de modificar el esquema se generó un respaldo custom nuevo con pg_dump, se comprobó el catálogo mediante pg_restore --list y se leyó el archivo completo con pg_restore. Se calculó y volvió a comprobar su SHA-256. Las credenciales se suministraron solo al subproceso, sin imprimirse ni incorporarse a archivos del proyecto.

Se inicializó un clúster PostgreSQL independiente, limitado a loopback y puerto temporal. Se comprobaron su directorio efectivo y PID antes de crear la base de recuperación. Se restauró el archivo completo con `--no-owner --no-privileges --exit-on-error` en `recuperacion_documental` (nombre técnico reutilizado del verificador; no es zona_bloque). Se compararon las **31 tablas restauradas** con las del origen: conteos y huellas idénticos, igualando la sesión a UTC. El clúster se detuvo al finalizar.

La evidencia de esa restauración está en `huellas_restauracion.json`, el catálogo del archivo y el log privado del servidor, junto al manifiesto. En la comprobación posterior se recalculó el hash del dump y se confirmó que las huellas restauradas coinciden con `huellas_antes` y `huellas_despues`. No se restauró sobre la base institucional ni se reemplazaron bases de otros proyectos.

## Conservación de registros

Se mantuvieron bloqueadas las escrituras en las tablas anteriores mientras se capturaba el respaldo, se ensayaba su restauración y se aplicaba la migración. Inmediatamente antes de aplicar se volvieron a comprobar destino, plan, hash del archivo y huellas.

Las **31 tablas anteriores** conservan sus conteos y SHA-256, comparando todas las columnas preexistentes. Se excluyen únicamente los metadatos nuevos previstos (registro de 0003, tipo de contenido y su permiso). Las concesiones de permisos y las relaciones anteriores se compararon íntegramente. La nueva columna nullable se excluye de la proyección de columnas originales para que la comparación sea equivalente.

El vínculo ficticio **3** conserva todos sus campos originales, incluidas su identidad, relaciones, parentesco declarado y estado **pendiente**. No se registró una comprobación para ese vínculo ni para ningún otro: la tabla nueva contiene **cero eventos**.

Todas las autorizaciones anteriores conservan sus datos y tienen `comprobacion_facultad_id = NULL`. **Ninguna recibió facultad verificada retroactivamente.** Su consulta no devuelve `facultad_vigente = true` como consecuencia de la migración. Los registros históricos no se borraron ni se revocaron masivamente.

## Pruebas y comprobaciones posteriores

| Verificación | Resultado real |
| --- | --- |
| Backend completo en PostgreSQL temporal aislado | **235 aprobadas**, 31,419 segundos |
| Frontend completo Vitest | **68 aprobadas**, seis archivos, 19,08 segundos |
| Django check --database default | Sin incidencias |
| Plan posterior de migraciones | Vacío |
| Comprobaciones GET internas, base real en READ ONLY | 19 resultados esperados, sin escrituras |

Las pruebas backend incluyen: confirmación con solo versión o numero_version; evidencia ausente o no opaca; revisión insuficiente en los métodos presencial/documental; estados pendiente/rechazada; responsable y fecha del servidor; vigencia y vencimiento; facultad para otra finalidad/version/deportista; revocación; prohibición de falsificar el fundamento; privacidad; CSRF; restricciones de profesores; historial inmutable por ORM y SQL; rollback conjunto de evento, versión y auditoría; conservación en migración y regresión anterior.

Se aprobaron nueve pruebas de concurrencia en la suite completa. Las tres de esta ampliación cubren decisiones sobre una misma versión, revocación frente a otorgamiento y desactivación de coordinación frente a comprobación. Se admite como historia un otorgamiento que ganó el bloqueo antes de revocar; después de revocar su fundamento deja de ser vigente y los nuevos intentos se rechazan.

Los datos ficticios de estas pruebas se crearon exclusivamente en un clúster temporal: las pruebas TestCase revierten sus transacciones y las de concurrencia/transición limpian su base de pruebas. La suite destruyó su base y detuvo el clúster; evidencia privada en `respaldos/pruebas_fase3_hxd_tv9_/`. **No se ejecutaron POST ficticios contra zona_bloque** ni se avanzaron secuencias de sus registros de negocio para probar la función.

### API y paneles en la base institucional

Se utilizó APIClient de Django con los actores existentes autenticados solo en memoria, sin crear sesiones persistentes. Todas las peticiones fueron GET dentro de una transacción declarada READ ONLY.

Administrador y coordinador activo recibieron **200** en:

- `/api/autorizaciones/`.
- `/api/acudientes/`.
- `/api/vinculos-acudientes/?deportista=9`.
- `/api/vinculos-acudientes/3/`.
- `/api/vinculos-acudientes/3/historial-facultades/` (lista vacía).
- `/api/paneles/{rol}/resumen/`.
- `/api/deportistas/`.

Visitante: **403** en autorizaciones. Profesor: **403** en autorizaciones, historial de facultades y ambos resúmenes reservados. Las pruebas escritoras de permisos y decisiones se realizaron en el entorno aislado, no en la base institucional.

También se comprobaron GET por red local sin sesión:

| URL | Resultado |
| --- | --- |
| `http://localhost:8000/api/autorizaciones/` | 403 esperado: requiere autenticación |
| `http://localhost:5173/api/autorizaciones/` | 403 esperado a través de Vite |
| `http://localhost:5173/administracion` | 200, React disponible |
| `http://localhost:5173/coordinacion` | 200, React disponible |

El 503 temporal por esquema pendiente ha desaparecido para las consultas autorizadas. Estos controles confirman API y disponibilidad de servidores; no sustituyen una verificación visual autenticada del formulario ni certifican la suficiencia de una evidencia externa. Build y npm audit no se repitieron en este encargo: no se modificó frontend; el build previo aprobado y la limitación histórica de conectividad de audit siguen documentados.

## Incidencias y archivos

**No falló ninguna comprobación previa** y no hubo errores de respaldo, restauración, migración o verificaciones posteriores. Los 403 de accesos restringidos son resultados esperados, no incidencias. No se corrigió código de negocio ni se modificaron roles, credenciales o datos personales.

Creados:

- `scripts/aplicar_comprobacion_facultades.py`: aplicación exclusiva con preflight, respaldo, restauración y verificaciones atómicas; rechaza repetición o planes distintos. Reutiliza únicamente utilidades de respaldo del script anterior, sin ejecutar su migración 0002.
- `scripts/verificar_facultades_aplicadas.py`: consultas de cierre en READ ONLY y evidencia agregada en el manifiesto privado.
- Este informe.

Actualizados: README, matriz de permisos y cabeceras de los informes de análisis e implementación, para reflejar la migración aplicada. Los respaldos, clústeres y manifiestos permanecen en el directorio privado excluido del control de versiones. No hubo commits ni push ni desarrollo de otros módulos.

El verificador anterior `scripts/verificar_facultades_pendientes.py` corresponde al estado previo y ya no debe utilizarse como comprobación del estado aplicado. El script de aplicación no debe repetirse. El verificador posterior está diseñado para este cierre sin nuevos eventos: tras registrar decisiones institucionales válidas, sus expectativas de historial vacío y huellas previas dejarán de ser aplicables.

## Recuperación

No se requiere recuperación. Si apareciera una incidencia, detener escrituras y preservar dump, manifiesto y logs. Comprobar primero el SHA-256 indicado y listar el respaldo. Restaurarlo en una **base nueva y aislada** con pg_restore, usando `--no-owner --no-privileges --exit-on-error`; igualar la zona horaria de comparación a UTC y contrastar las columnas originales con el manifiesto. No mostrar credenciales ni filas al ejecutar el procedimiento.

El respaldo es **anterior a 0003**: carece de la tabla, FK, función y trigger nuevos. La recuperación del servicio debe coordinar esquema y versión de aplicación, y considerar cualquier escritura institucional posterior. No restaurar sobre zona_bloque ni ejecutar una reversión que elimine historial sin un plan revisado y autorización expresa. Una recuperación por error antes de confirmar la aplicación habría usado el rollback atómico; esta ejecución terminó confirmada y verificada.

## Punto de parada y comprobación visual

Listo para continuar con el usuario en `http://localhost:5173/administracion/autorizaciones?deportista=9` y, según rol, en `http://localhost:5173/coordinacion`.

En Vínculos con acudientes, el vínculo 3 debe seguir pendiente y la acción «Registrar comprobación de facultad 3» debe abrir contexto, método, alcance/version, referencia privada, resultado, indicadores de revisión y fechas. No es necesario guardar para comprobar la presentación. Registrar una verificación real exige evidencia custodiada y revisión humana efectiva; **la autorización de migración no constituye evidencia ni concede una facultad al vínculo 3**. No se guardó automáticamente ninguna decisión. Trabajo detenido para verificación visual conjunta.
