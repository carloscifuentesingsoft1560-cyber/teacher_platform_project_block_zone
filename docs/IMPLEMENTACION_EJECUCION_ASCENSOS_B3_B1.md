# Estructura administrativa de ascensos — B3-B1

Fecha: 30 de octubre de 2026. Migración generada y probada solo en PostgreSQL aislado; **no aplicada en `zona_bloque`**.

## 1. Alcance y arquitectura real

Se revisaron el diseño B3-A, el diseño del Incremento 2, la implementación B1, B2.2-A y B2.2-B1, modelos/servicios de inscripciones y organización, reservas/cupos/traslados, protecciones SQL y pruebas anteriores. Prevalece la nueva decisión institucional: ejecución progresiva con autoridad administrativa de administrador y coordinador activo, sin atribuir al administrador aprobación pedagógica.

Se agregan dos modelos de evidencia administrativa. No se duplican deportistas, grupos, niveles, inscripciones, afectaciones ni excepciones. Se reutilizan `ProgresionInstitucional`, sus versiones, `EventoProgresion`, `CambioAdministrativo` y los bloqueos institucionales. `AfectacionInscripcion` sigue siendo la identidad de la obligación; las revisiones posteriores no sobrescriben su disposición original ni la decisión pedagógica.

**No existe ejecución de traslados en esta entrega.** Ningún servicio B3-B1 crea/cierra inscripciones, libera reservas, asigna cupos o cambia grupos/horarios. No llama a `contexto`, cuya liberación global de reservas vencidas sería un efecto lateral inadecuado para esta estructura.

## 2. Modelos y relaciones

| Entidad | Campos y responsabilidad |
| --- | --- |
| `RevisionAdministrativa` | Progresión aprobada, número secuencial, revisión anterior OneToOne, actor, fecha automática, motivo, versión de progresión y JSON estructurado de disposiciones |
| `ResultadoAdministrativo` | Revisión, afectación, inscripción origen, inscripción destino opcional reservada para una etapa posterior, estado, fecha efectiva, actor, fecha de registro, motivo, versión de progresión y clave UUID idempotente |

Ambos son inmutables después de insertarse, mediante modelo y PostgreSQL. Todas las FK son `PROTECT`. La sucesión de revisiones no admite ramas ni reutilizar un número dentro de la progresión.

Cada fila de revisión conserva afectación, origen, versión de inscripción, situación observada actual, disposición, destino propuesto opcional, motivo y huella estructural de grupo, periodo, horarios, reservas y catálogo de niveles. No contiene documentos personales, contactos ni imágenes. Los destinos son IDs de **grupos**; el campo destino del resultado es una FK de **inscripción**, y permanece nulo en B3-B1.

Las disposiciones siguen siendo exactamente `revisar`, `reubicar`, `pendiente`, `continuidad`, `reserva`, `futura`. Se exige incluir todas las afectaciones una sola vez. Una inscripción relevante nueva sin afectación bloquea la revisión: no se añade ni elimina una afectación silenciosamente. Ese caso requiere un procedimiento institucional posterior.

La nueva revisión puede reflejar cambios materiales y versiones actuales sin reescribir la evidencia original ni la resolución pedagógica. Conserva la cadena anterior y los resultados de todas las revisiones. El resumen interpreta la revisión más reciente; las anteriores permanecen consultables por ORM interno, sin convertir sus resultados en resultados de la revisión nueva automáticamente.

## 3. Estados y cierre

Se distinguen cuatro dimensiones:

1. **Decisión pedagógica:** pendiente/aprobada/rechazada de B1, sin cambios.
2. **Preparación B1:** `estado_plan` pendiente/parcial/preparado, sin cambios. «Parcial» sigue sin significar parcialmente trasladado.
3. **Resultado de una afectación:** `pendiente` o `resuelta` en B3-B1. `ejecutada` está identificada como opción futura pero **excluida por CHECK**, incluso mediante INSERT SQL directo.
4. **Ejecución y cierre institucional:** resumen interno independiente. Define las categorías pendiente/parcialmente_ejecutado/ejecutado según resultados verificables y separa `cerrado`; en esta etapa solo es alcanzable ejecución `pendiente`, `ejecucion_habilitada=False` y `cerrado=False`.

`resuelta` no significa traslado realizado. Solo registra una situación administrativa final que **ya existe**: el origen está finalizado, tiene salida posterior al ingreso y la fecha efectiva del resultado coincide con esa salida. No finaliza la inscripción. Se necesita motivo expreso. No permite acreditar una inscripción activa como resuelta ni inventar una fecha.

`consultar_ejecucion` evalúa `plan_completo` y `puede_cerrar` sin escribir. Un plan puede estar estructuralmente completo con disposiciones `pendiente`, pero **no puede cerrarse** por ello. Cierre evaluable exige aprobación pedagógica, revisión completa sin discrepancias, resultados finales resueltos para todas las filas, ninguna disposición `pendiente`/`revisar` y ninguna excepción autorizada abierta. Una excepción autorizada vencida sigue abierta; no se revoca automáticamente. Una continuidad exige excepción vigente para considerar completa su preparación.

Un resumen favorable no confirma cierre ni libera `ascenso_abierto_unico`. No hay columna pública ni servicio para marcar cerrado, ejecutado o parcialmente ejecutado. Esos estados efectivos requieren el servicio seguro y los controles de la etapa siguiente. B3-B1 no afirma haberlos producido o probado con traslados.

## 4. Servicios internos

Archivo: `backend/inscripciones/servicios_ejecucion.py`. No se añaden rutas ni serializers públicos.

| Servicio | Contrato |
| --- | --- |
| `revisar_plan(actor, identificador, version, disposiciones, motivo)` | Registra una nueva revisión de una progresión aprobada, con número, enlace previo y evento; incrementa versión del agregado |
| `registrar_resultado(actor, revision_id, version, afectacion_id, clave, motivo, estado='pendiente')` | Registra evidencia pendiente o situación final ya resuelta, solo en la revisión vigente; jamás ejecuta movimientos |
| `consultar_ejecucion(actor, identificador)` | Consulta de estado, filas/resultados, versión, revisión vigente, completitud, discrepancias, nuevas inscripciones, pendientes y condiciones de cierre |

Cada disposición de entrada contiene únicamente `afectacion`, `disposicion`, `motivo` y `destino` opcional. Las versiones, situación y huellas se derivan del servidor. No se aceptan disposiciones no contempladas por B1. `reubicar` exige otro grupo activo, de la disciplina y nivel destino aprobados, con estructura activa. Reserva/futura deben corresponder a la situación actual. Continuidad exige una excepción ya autorizada y vigente, también al revisar como administrador.

La preparación de destinos no garantiza cupo ni ejecución; no simula aún la proyección de traslados. Las comprobaciones completas de vigencia, fechas efectivas y compatibilidad temporal de movimientos pertenecen a B3-B2. Cambiar destino en una revisión no cambia el nivel pedagógico aprobado ni puede saltar a otra disciplina.

El control de contexto de resultados compara versiones y huellas con la revisión vigente. Detecta cambios de estructura/horarios/capacidad, reservas, catálogo, estado y paso del tiempo que cambie una futura o reserva de situación. Requiere una nueva revisión expresa si encuentra discrepancias; no sustituye automáticamente evidencias. Una solicitud sobre revisión anterior falla, salvo recuperación idempotente de un resultado ya confirmado con la misma clave/contenido.

## 5. Autoridad, transacciones y auditoría

Administrador activo y coordinador activo pueden usar los servicios administrativos; profesores no pueden revisar, registrar resultados ni consultar el resumen global. Se relee el usuario bajo el bloqueo global existente. No se cambian roles ni los permisos de las APIs anteriores. Administrador no puede usar `decidir_progresion` ni otorgar/revocar excepciones: se conserva la autoridad coordinadora y las protecciones B1.

Se mantiene orden global de usuarios, progresión y deportista, y bloqueo de contexto deportivo. La versión del agregado detecta una revisión obsoleta. Revisión o resultado, incremento de versión, evento B1 y auditoría se guardan en una transacción. Un fallo de auditoría revierte la escritura completa.

Los eventos `revision_administrativa` y `resultado_administrativo` conservan actor, versión, fecha, motivo y referencia al nuevo registro. El JSON completo de una revisión conserva el cambio de disposición; la revisión precedente permanece intacta. Las funciones SQL exigen un evento coincidente dentro de la misma transacción, mediante triggers diferidos.

Idempotencia: clave única por revisión. Mismos clave/afectación/motivo/estado recuperan el resultado previo sin incrementar versión ni crear evento; distinto contenido produce conflicto. También hay una sola fila de resultado por revisión/afectación. Una revisión posterior no borra resultados anteriores. Los registros pendientes son evidencia de revisión/intención, **no intentos de traslado confirmados**. Los intentos rechazados revierten; no se introduce una bitácora persistente de errores con datos sensibles.

## 6. Migración exacta pendiente

`inscripciones.0003_revisionadministrativa_resultadoadministrativo_and_more`

Dependencias: `inscripciones.0002_progresioninstitucional_eventoprogresion_and_more` y dependencia intercambiable de `AUTH_USER_MODEL`.

Inventario de **nueve operaciones Django**:

1. `RunSQL`: fijar `SET LOCAL search_path TO public, pg_catalog, pg_temp`, con reversión equivalente.
2. `CreateModel RevisionAdministrativa` → `public.inscripciones_revisionadministrativa`.
3. `CreateModel ResultadoAdministrativo` → `public.inscripciones_resultadoadministrativo`.
4. `AddConstraint revision_admin_numero_unico` (progresión/número).
5. `AddConstraint revision_admin_numero_positivo`.
6. `AddConstraint resultado_admin_fila_unica` (revisión/afectación).
7. `AddConstraint resultado_admin_clave_unica` (revisión/clave).
8. `AddConstraint resultado_admin_b1_sin_ejecucion`: solo pendiente sin destino/fecha, o resuelta sin destino y con fecha.
9. `RunSQL`: dos funciones y cuatro triggers de integridad, inmutabilidad y auditoría; SQL inverso explícito.

Las relaciones OneToOne anterior y destino incluyen sus unicidades automáticas, además de PK, FK e índices Django; no se introducen índices explícitos adicionales. No hay transformaciones de inscripciones, backfill, eliminación o renombrado de tablas anteriores.

Funciones nuevas, con `SECURITY INVOKER SET search_path=pg_catalog` y referencias `public`:

- `public.zdb_administracion_b3_guardia`: valida INSERT y rechaza UPDATE/DELETE de revisiones/resultados; bloquea la progresión al validar secuencia y versión; comprueba aprobación, actor administrativo activo, motivos, alcance completo, origen/afectación, disciplina/nivel destino, situaciones y continuidad vigente.
- `public.zdb_administracion_b3_evento`: exige evento coincidente de actor, tipo, motivo, versión y referencia, con versión confirmada del agregado.

Triggers sobre las dos tablas nuevas exclusivamente: `zdb_revision_b3_inmutable`, `zdb_resultado_b3_inmutable` (BEFORE INSERT/UPDATE/DELETE); `zdb_revision_b3_evento`, `zdb_resultado_b3_evento` (constraint triggers AFTER INSERT, diferidos inicialmente). No se desactivan ni reemplazan los seis triggers B1.

La protección `ascenso_plan_valido` sigue intacta. La migración B1 conserva SHA-256 `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`. No se debilita el bloqueo del mecanismo antiguo `nivel`.

## 7. Reversión y conservación

La reversión elimina solo los cuatro triggers, dos funciones y dos tablas nuevos, con `search_path` local explícito. El ciclo aislado compara columnas, conteos y huellas de todas las tablas previas, excluyendo el registro esperado de migraciones. No modifica inscripciones ni su historial deportivo.

**Una reversión real perdería revisiones y resultados B3-B1.** Los eventos B1 ya guardados seguirían existiendo y sus referencias JSON a revisiones/resultados eliminados dejarían de poder resolverse. Por tanto, conservar datos anteriores no equivale a reversión funcional inocua. No debe ejecutarse sobre producción sin respaldo/restauración completa y autorización específica. La reaplicación crea tablas vacías, no recupera la historia borrada.

## 8. Pruebas realizadas

Generación de la migración mediante la opción existente `ZDB_GENERAR_ASCENSOS=1` del ejecutor aislado, tras verificar el clúster; después se eliminó esa variable para las pruebas. Una ejecución sin tests se utilizó solo para generar/comprobar modelos, no se cuenta como cobertura.

Primera tanda focalizada: **18 pruebas aprobadas**, 12,740 segundos, PostgreSQL temporal puerto `51699`, evidencia privada `respaldos/pruebas_fase3_y1ql7vt1/`. Primera regresión completa: **417 pruebas aprobadas**, 110,047 segundos, puerto `58193`, evidencia `respaldos/pruebas_fase3_tk5qpayo/`. Posteriormente se reforzó SQL y detección temporal y se añadieron dos pruebas; el resultado definitivo se registra a continuación.

**Resultado definitivo: 419 pruebas backend aprobadas**, las 395 anteriores y 24 nuevas, en **110,656 segundos**, sin fallos ni omisiones informadas. Django: `System check identified no issues (0 silenced)`. Comprobación aislada `makemigrations --check --dry-run`: `No changes detected`. Puerto temporal `49823`, evidencia privada `respaldos/pruebas_fase3_2m6e8mro/`; base de pruebas destruida y clúster detenido al terminar. No se repitió frontend porque no se modificó.

Comando de verificación completa:

```powershell
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

El ejecutor comprueba directorio de datos y PID de su proceso PostgreSQL hijo y solo entonces configura el puerto efímero y base de pruebas independiente, usando paquetes de `.venv-local` mediante `django_local.py`. Los ciclos de migración exigen además nombre de base `test_zdb_fase3_...`. No hay escritura ni consulta a `zona_bloque` en estas comprobaciones.

Cobertura añadida: resultado pendiente y relaciones; duplicados e idempotencia; revisiones sucesivas e inmutabilidad SQL; autoridad administrativa y pedagógica; varias inscripciones, reservas y futuras; excepción vigente/vencida abierta; cierre bloqueado por pendientes; resolución de un origen previamente finalizado sin cerrarlo; estados ejecutados rechazados por servicio, ORM y SQL; auditoría diferida; cambio material y temporal; resultados de revisión anterior; fallo de evento; revisiones/resultados concurrentes; migración, reversión y reaplicación con huellas de tablas anteriores.

No se probó ejecución real B3 ni generación de destinos: esas operaciones no existen. Los cierres previos de fixtures aisladas solo construyen los escenarios de situación final y no son un servicio B3.

## 9. Archivos creados/modificados

- Nuevo `backend/inscripciones/modelos_ejecucion.py`.
- Nuevo `backend/inscripciones/servicios_ejecucion.py`.
- Nuevo `backend/inscripciones/migrations/0003_revisionadministrativa_resultadoadministrativo_and_more.py`.
- Nuevo `backend/inscripciones/test_ejecucion_b3_b1.py`.
- `backend/inscripciones/models.py`: registro de los dos modelos.
- `backend/inscripciones/test_seguridad_migracion_b1.py`: al finalizar la auditoría histórica B1 repone la hoja de migración vigente en el clúster de pruebas, pues revertir a B1 elimina descendientes. No cambia las comprobaciones SQL B1 ni una migración aplicada.
- Este documento.

## 10. Correcciones posteriores a auditoría

Esta sección sustituye el estado de verificación de la entrega inicial de 419 pruebas. Los resultados anteriores se conservan como antecedentes; no bastaban para detectar los dos hallazgos reproducidos por la auditoría.

### Integridad de identidad y disciplina

La huella original omitía el deportista; además, el trigger de resultados comprobaba el enlace afectación/origen pero no su pertenencia actual al deportista y disciplina de la progresión. Así, una inscripción secundaria modificada sin incrementar versión podía pasar inadvertida. No era necesario desactivar triggers: el caso fue reproducido mediante el servicio y SQL con auditoría.

Ahora cada fila de revisión incorpora IDs explícitos de `deportista`, `disciplina`, `grupo`, `nivel` y `periodo`, además de afectación/origen/versión. La huella incluye deportista y disciplina. La consulta revalida todos esos IDs, la estructura nivel/disciplina y todas las afectaciones, no solo la referencia. Una identidad cruzada produce discrepancia y bloquea resultados y nuevas revisiones, sin modificar la inscripción.

El modelo de resultado relee el origen desde PostgreSQL en `clean()`: no confía en un objeto relacionado que conserve información anterior en caché tras un UPDATE ORM. La guardia SQL de resultado valida deportista, disciplina del grupo y del nivel, e identifica cruces en **cualquier** afectación del agregado, aunque el resultado solicitado sea para otra fila sana. La revisión valida también los IDs del JSON contra las relaciones actuales.

La recuperación idempotente de un resultado previo vuelve a comprobar la integridad de todas las afectaciones. No se usa la clave como vía alternativa para devolver sin advertencia un resultado cuyo origen cambió posteriormente de identidad o disciplina. No crea un segundo evento ni modifica el registro histórico para corregirlo.

No se editaron ni reemplazaron funciones/triggers B1. Las operaciones nuevas permanecen sobre las dos tablas B3; las tablas anteriores solo se consultan/bloquean como ya estaba previsto. No se impide toda mutación histórica posible desde SQL privilegiado sobre otras aplicaciones; se detecta la inconsistencia y se rechaza incorporar evidencia B3 incompatible.

### Evidencia JSON y errores controlados

La causa del `KeyError` era aceptar un JSON parcialmente válido en SQL y asumir campos obligatorios al consultar. Se añadió `validar_disposiciones`, reutilizado por `RevisionAdministrativa.clean()` y la consulta. Exige lista no vacía, filas objeto con exactamente 13 campos, IDs enteros positivos (no booleanos), disposiciones/situaciones conocidas, motivo textual válido, destino entero o null según disposición, huella SHA-256 hexadecimal de 64 caracteres y afectaciones únicas. No se generan huellas ficticias ni se rellenan campos faltantes.

La migración pendiente contiene la misma validación estructural de tipos y campos antes de castear IDs o evaluar relaciones. SQL directo no puede omitir la huella, sustituir IDs por textos/null/booleanos ni insertar estructuras malformadas. Los servicios validan además los tipos del comando de disposición antes de construir la evidencia; no convierten un motivo null en texto aparente.

Una evidencia corrupta en una lectura —reproducida mediante objetos de prueba en memoria, sin desactivar protecciones— devuelve `Conflicto` con mensaje institucional y no `KeyError`, trazas ni valores personales. Una huella de formato correcto pero alterada se detecta por comparación con el contexto actual. La huella sirve para detectar cambios, no es una firma digital ni sustituye autoridad/auditoría.

### Fecha operativa y conservación de fechas

PostgreSQL `CURRENT_DATE` depende de la zona de sesión; Django tiene `TIME_ZONE='America/Bogota'`, `USE_TZ=True`. A las `2026-10-30T04:59:59Z` en Bogotá todavía es 29 de octubre; a las `05:00:00Z` comienza el 30. Una sesión UTC o de otra zona podía clasificar futuras/reservas/excepciones con otro día.

Todas las expresiones `CURRENT_DATE` de la migración B3 pendiente fueron sustituidas por una variable local por sentencia: `(pg_catalog.statement_timestamp() AT TIME ZONE 'America/Bogota')::date`. No se cambia la configuración institucional, la zona de sesión de producción ni fechas guardadas. La prueba compara instantes antes/después de medianoche de Bogotá y medianoche UTC, bajo sesiones UTC, Bogotá y Pacific/Kiritimati, y prueba una revisión real en el clúster aislado con zona distinta.

Durante esa prueba se detectó un efecto de reserializar una aprobación completa con otra zona de sesión: B1 rechazaba una aparente reescritura de su fecha. Se restringieron las escrituras administrativas a `version`, `actualizado_por` y `actualizado_en`, después de validar el agregado. No vuelven a enviar resolución, autoridad ni fecha histórica. Se verifica la conservación exacta del instante de aprobación comparando su epoch antes/después. No se debilitó el trigger B1 para admitirlo.

Condiciones operativas: mantener la zona institucional de Django en Bogotá, no activar una zona diferente para calcular fechas de negocio y conservar la conexión administrada por Django. SQL B3 calcula explícitamente Bogotá aunque otra sesión use otra zona. Si una operación atraviesa exactamente el cambio de día entre validación Python y sentencia SQL, las comprobaciones pueden rechazarla; debe releerse/reintentarse en el nuevo día, nunca forzar una fecha anterior. No hay ejecución automática ni rectificación histórica.

### Archivos de esta corrección

- `backend/inscripciones/modelos_ejecucion.py`: validación estructural JSON y relectura/validación de relaciones actuales del resultado.
- `backend/inscripciones/servicios_ejecucion.py`: identidad en huellas y filas, comprobación completa, errores controlados y actualización administrativa limitada a sus campos.
- `backend/inscripciones/migrations/0003_revisionadministrativa_resultadoadministrativo_and_more.py`: guardias SQL y fecha operativa explícita; mantiene nueve operaciones, dos tablas, cinco restricciones, dos funciones y cuatro triggers.
- Nuevo `backend/inscripciones/test_correcciones_b3_b1.py`: regresiones de identidad secundaria, ORM/SQL cruzado, tipos/estructura JSON, lectura corrupta, huella alterada y fechas.
- Este documento.

La migración B1 sigue con SHA-256 `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`. No se requieren nuevas columnas ni una migración adicional: solo se corrige la migración B3 aún no aplicada. No hay backfill, borrado ni actualización de evidencia anterior.

SHA-256 de la migración B3 corregida: `5f6fdd0fe87f1bcb37ab5273110f652ca6dc32c3590ee3b8b107a140706c8658`. Sigue pendiente una nueva auditoría y autorización antes de cualquier aplicación institucional.

### Verificaciones de la corrección

La tanda focalizada de 12 pruebas aprobó en 7,374 segundos (`respaldos/pruebas_fase3_7fhv6b9v/`, puerto 56099), con comprobación Django sin incidencias y `makemigrations --check --dry-run`: `No changes detected`. Posteriormente se añadieron continuidad vigente, conservación de epoch de aprobación y reintento idempotente ante identidad alterada.

**Verificación definitiva de las correcciones: 433 pruebas backend aprobadas** (419 anteriores y 14 nuevas), en **124,117 segundos**, sin fallos ni omisiones informadas. Incluye aplicación, reversión y reaplicación de la migración definitiva, huellas de tablas anteriores, concurrencia, permisos, auditoría y rechazo de ejecuciones. Django: `System check identified no issues (0 silenced)`. `makemigrations --check --dry-run` aislado: `No changes detected`.

Clúster temporal final: puerto `64203`, evidencia privada `respaldos/pruebas_fase3_dinzdw8r/`; se verificaron directorio y PID antes de escribir, se destruyó la base de pruebas y se detuvo el clúster. Corridas completas intermedias: 431 aprobadas en 118,475 segundos (`respaldos/pruebas_fase3_33uohilw/`) y 432 aprobadas en 119,388 segundos (`respaldos/pruebas_fase3_gvmvd9en/`). No se ejecutaron pruebas contra `zona_bloque`, ni se modificó frontend o configuración institucional.

**Estado para entrega:** corregidos los dos hallazgos y armonizada la fecha operativa; lista para una nueva auditoría técnica. Esto no es autorización de instalación. Persisten las limitaciones B3-B1, la necesidad de revisar contextos incompatibles y los riesgos de reversión descritos; no se habilitó ejecución ni cierre mutante.

En desarrollo se corrigió un mock de consulta que interceptaba también la lectura del usuario; la prueba de ORM confirmó además que un objeto relacionado en caché no sirve para comprobar identidad actual, por lo que el modelo ahora relee el origen. El rechazo del guardado completo bajo otra zona de sesión motivó la actualización exclusiva de campos administrativos descrita arriba. No se trasladaron esos problemas a producción.

## 11. Corrección de destino administrativo inexistente

Esta corrección responde exclusivamente al hallazgo posterior de la auditoría de aceptación: una revisión válida conserva el ID de grupo destino en su JSON, pero el grupo puede desaparecer por ORM después de eliminar sus dependencias. `huella_contexto` utilizaba `.get(pk=destino)` sin controlar `Grupo.DoesNotExist`, y la consulta no conseguía mostrar el expediente.

### Referencia histórica o FK

Se mantiene el almacenamiento histórico por ID y se aplica validación defensiva. Añadir una FK a cada destino del JSON implicaría normalizar detalles o añadir una relación/tabla adicional, decidir su ciclo de vida y restringir eliminaciones de grupos que hoy no están protegidas por esa referencia administrativa. Una FK también exigiría conciliar evidencia anterior sin reconstruir ni sustituir su historia. Ese cambio no es necesario para mantener consultable la revisión y queda fuera de esta corrección.

El ID desaparecido sigue en la evidencia inmutable y en el diagnóstico; no se sustituye por null, un grupo alternativo o una huella ficticia. La supresión de un grupo mediante SQL/ORM no se prohíbe globalmente por esta referencia JSON. Los servicios dependientes detectan su ausencia y la bloquean. El destino opcional de `ResultadoAdministrativo` continúa siendo una FK de inscripción, no del grupo propuesto, y sigue prohibido en B3-B1.

### Puntos revisados y solución aplicada

Todos los accesos al grupo destino dentro de `servicios_ejecucion.py` pasan por `obtener_destino_historico`:

- Construcción de revisión: resuelve el ID concreto, distingue inexistencia/inactividad/incompatibilidad y utiliza el objeto resuelto para calcular la huella. La ausencia produce `Conflicto` institucional, no `DoesNotExist`.
- Cálculo directo de `huella_contexto`: resuelve defensivamente el destino cuando no recibe un objeto ya consultado. También falla de forma controlada si se invoca directamente con un ID desaparecido.
- Consulta: resuelve cada destino histórico; si no existe, conserva su ID, añade la afectación a `discrepancias` y devuelve una advertencia identificable. Continúa examinando las demás filas, sin reescribir el expediente ni perder acceso a su estado y resultados.
- Registro de resultado y recuperación idempotente: validan evidencia y existencia de todos sus destinos antes de devolver/registrar el resultado. La escritura toma bloqueo de fila del grupo consultado para impedir su eliminación concurrente mientras se confirma la operación. Se conserva el bloqueo global de usuarios y la validación del agregado.

El validador controlado de evidencia se comparte entre consulta y registro, conservando el tratamiento de JSON corrupto de la corrección anterior. No se añaden rutas públicas ni se modifica el contrato docente o pedagógico.

### Diagnóstico por destino

El resumen interno añade `advertencias_destinos`, una lista con `afectacion`, `destino` (ID histórico), `codigo`, `mensaje` y `bloquea_resultado`.

| Código | Tratamiento |
| --- | --- |
| `destino_inexistente` | Discrepancia bloqueante; sin huella nueva ni grupo sustituto; exige revisión administrativa nueva |
| `destino_inactivo` | El grupo existe, pero él o su estructura están inactivos; se distingue de eliminación y bloquea resultados |
| `destino_incompatible` | Cambió disciplina o nivel respecto del ascenso aprobado; bloquea resultados |
| `destino_sin_horarios` | El grupo existe sin horarios activos; se muestra expresamente y bloquea resultados |
| `destino_sin_cupo` | Advertencia de disponibilidad; no es inexistencia y no reserva plaza; por sí sola no impide registrar evidencia pendiente |

Las alteraciones de contexto siguen contrastándose con la huella y versión. Un destino desaparecido hace que `plan_completo` y `puede_cerrar` sean falsos. Las consultas repetidas dan el mismo diagnóstico y no generan eventos o versiones.

La ocupación se consulta con `ocupacion_maxima`, sin invocar servicios de escritura o liberación de reservas. Mantener un destino propuesto lleno está permitido por B1: esta etapa no realiza traslados ni garantiza viabilidad. Las comprobaciones de ejecución efectiva continúan pendientes de B3-B2.

Una nueva revisión expresa puede sustituir el ID desaparecido por otro destino válido. Guarda motivo, actor, versión y enlace a la revisión anterior. El JSON anterior, sus huellas y resultados no cambian. Un reintento con clave de la revisión antigua no se convierte en resultado de la nueva: si su destino histórico desapareció, recibe conflicto. Para registrar en la revisión nueva se utiliza su propia identidad y clave, sin duplicar ni modificar historia.

### Archivos y migraciones

- `backend/inscripciones/servicios_ejecucion.py`: resolución defensiva, diagnósticos de destinos, bloqueos de escritura y validación de reintentos.
- Nuevo `backend/inscripciones/test_destinos_administrativos.py`: casos integrados de destinos históricos y efectos sobre las operaciones.
- Este documento.

No se modifican modelos ni migraciones. B1 conserva SHA-256 `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`; B3 pendiente conserva `5f6fdd0fe87f1bcb37ab5273110f652ca6dc32c3590ee3b8b107a140706c8658`. No hay nueva FK, backfill o transformación de datos.

### Pruebas de esta corrección

Tanda focalizada: **13 pruebas aprobadas**, en **9,858 segundos**, puerto temporal `65499`, evidencia privada `respaldos/pruebas_fase3_h8aqhj9w/`. Django sin incidencias y comprobación aislada de modelos/migraciones: `No changes detected`. Clúster detenido y base de pruebas destruida.

Las 13 pruebas cubren conjuntamente los 15 escenarios solicitados: destino compatible; eliminación posterior; consultas repetidas; inactividad; ausencia de horarios; disciplina/nivel cambiados; capacidad agotada; huella directa con ID inexistente; intento de registro y reintento idempotente; creación con destino ya desaparecido; sustitución explícita en nueva revisión; conservación del ID/JSON/eventos, aprobación y versiones; varias afectaciones y comparación íntegra de inscripciones, reservas, grupos y horarios antes/después de las operaciones no destructivas.

Las eliminaciones de horarios/grupos son preparaciones explícitas de fixtures únicamente en PostgreSQL temporal. No se realizaron sobre la escuela ni se ejecutó traslado alguno. Los registros probados son evidencia pendiente, no movimientos deportivos.

**Regresión final: 446 pruebas backend aprobadas** (433 anteriores y 13 nuevas), en **130,053 segundos**, sin fallos ni omisiones informadas. Django informó `System check identified no issues (0 silenced)` y `makemigrations --check --dry-run` aislado informó `No changes detected`.

Ejecución definitiva: puerto temporal `49962`, evidencia privada `respaldos/pruebas_fase3_jyqqwzzr/`; el ejecutor comprobó directorio y PID del clúster antes de las escrituras, destruyó la base de pruebas y detuvo su proceso PostgreSQL al terminar. No se necesita un ciclo adicional por cambios de migración, puesto que ambas migraciones quedaron intactas; la suite completa ejecutó también sus pruebas existentes de aplicación, reversión y reaplicación aisladas.

La corrección queda preparada para una nueva auditoría; no constituye autorización de instalación ni verificación visual con datos reales. No aparecieron fallos adicionales en las verificaciones ejecutadas.

### Riesgos residuales y punto de parada

La referencia por JSON no impide que un operador ORM/SQL elimine físicamente un grupo; sí conserva su ID y permite diagnosticarlo sin un error inesperado. Una política futura de prohibición de esas eliminaciones mediante FK requiere diseño y autorización independientes. Una consulta de lectura puede observar cambios concurrentes entre sentencias; no representa una reserva ni una autorización para ejecutar. Los escritores de aplicación revalidan dentro de transacción y bloquean el destino existente.

Se conservan las protecciones SQL B3 contra ejecución y reescritura, la autoridad pedagógica coordinadora y los riesgos de reversión documentados. Esta corrección no afirma blindaje frente a SQL privilegiado que omita los servicios ni habilita ejecución B3-B2. No se modificaron datos persistentes, frontend, roles o credenciales; no hubo commits ni push.

## 12. Limitaciones y requisitos B3-B2

1. Estados parcialmente ejecutado/ejecutado/cerrado no se confirman en B3-B1; resultado `ejecutada` y todo destino de inscripción permanecen prohibidos. B3-B2 necesitará una migración nueva para habilitarlos con pruebas de resultados verificables, vínculo origen/continuación y unicidad de ejecuciones entre revisiones.
2. La consulta interpreta resultados por revisión vigente; no transporta automáticamente resoluciones previas a una revisión nueva. Su eventual ratificación debe ser explícita y no duplicar movimientos reales.
3. Cierre es evaluación, no mutación. Sigue pendiente el servicio seguro de cierre, liberación controlada de `ascenso_abierto_unico` y reconocimiento del nivel institucional para un siguiente ascenso. No se utiliza rechazo para liberar un aprobado.
4. Nuevas inscripciones sin afectación requieren revisión humana; no se implementó sincronización ni alta automática de afectaciones.
5. Falta proyección conjunta de fechas/cupos/horarios, idempotencia de movimientos, tratamiento administrativo de suspendidas/reservas/futuras y estados intermedios. El contexto completo de otra disciplina para cruces no es todavía un ejecutor.
6. No hay endpoints, interfaz ni gestión pública de excepciones. No se habilitó el administrador para actuaciones pedagógicas.
7. Los triggers protegen escrituras ordinarias, no un propietario que desactive/elimine protecciones. Un operador SQL capaz de insertar eventos puede construir evidencia formal; la identidad humana se valida en servicios sin `SECURITY DEFINER` ni cambios de credenciales.
8. Se conserva el bloqueo global de usuarios: suficiente para serialización de servicios actuales, con limitación de escalabilidad. No se afirma aislamiento contra SQL privilegiado que omita los protocolos de aplicación.

Antes de aplicar la migración real se requiere inventario revisado, autorización expresa, conexión confirmada, ausencia de colisiones, respaldo nuevo verificado por SHA-256/restauración aislada y comparación previa/posterior de datos. **No se realizó ninguna aplicación real.** No se modificó frontend, permisos existentes, roles o credenciales; no hubo commits ni push. Se detiene para revisión, sin iniciar B3-B2/B3-C/B3-D.
