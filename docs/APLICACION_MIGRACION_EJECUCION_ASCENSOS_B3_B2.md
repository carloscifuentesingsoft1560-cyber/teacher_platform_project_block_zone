# Instalación controlada de B3 — migración 0004

**Resultado definitivo: INSTALACIÓN SATISFACTORIA en el segundo intento autorizado. `0004` está aplicada y no quedan migraciones pendientes.**

## Segundo intento — instalación confirmada

- Inicio: **31 de octubre de 2026, 01:29:08 UTC**; **30 de octubre, 20:29:08 en Bogotá**.
- Fin verificado: **01:29:10 UTC**; **20:29:10 en Bogotá**.
- Conexión efectiva: **PostgreSQL 17.11, 127.0.0.1:5432, base zona_bloque, esquema public**.
- Migración aplicada exclusivamente: **`inscripciones.0004_ejecucion_administrativa`**.
- Se reutilizó el instalador corregido, sin modificarlo, y se redirigió su salida a una carpeta nueva. No se sobrescribió la evidencia del primer intento.

### Verificaciones previas del segundo intento

Todas fueron satisfactorias antes de ejecutar el DDL:

1. Identidad efectiva y configuración Django coincidentes con el destino autorizado.
2. `0003` aplicada y `0004` como única migración pendiente; historial consistente.
3. Respaldo existente, **239448 bytes**, SHA-256:

   `f51c94153a68261ea95b9b711424fad793e0639f5267358a52d69a3403a542c1`

   Ruta: `respaldos/preparacion_0004_20261031T005057Z/zona_bloque_pre_0004_20261031T005057Z.dump`.
4. Las **38 tablas y 267 registros anteriores**, incluidos usuarios, permisos e historial, conservaban sus conteos y huellas. El inventario de esquema también coincidía con la referencia de origen.
5. Comparador corregido SHA-256 `001ac6489fee765dcec05ebb9b5dc0d6e0c2a925992e9cccfd3598e38230a661`.
6. Certificado SHA-256 `234059d583bb438f53c58a0da3884abf27993b0ecd0afb2e7a9094ca9c21e109`, idéntico al de las **24 pruebas aisladas aprobadas** y la integración del comprobador en lectura. Su huella también se verificó mediante la constante fijada en el módulo, antes del DDL.
7. Instalador corregido SHA-256 `4beeae2e582b9dea47e5922c797728897f2d9b2684a86bb15d365fc33bc2ea71`; hashes de las migraciones `0002`, `0003` y `0004` intactos.
8. Sin actividad ajena incompatible en la comprobación de la ventana; no se desconectaron sesiones.

### Aplicación y comprobaciones posteriores

Se efectuó una sola invocación con objetivo y plan explícitos para `0004`. La transacción externa utilizó `lock_timeout=5s`, `statement_timeout=120s` y bloqueos `SHARE` sobre las tablas existentes en orden estable. Se repitieron las comprobaciones de respaldo, plan y huellas después de adquirir los bloqueos.

Las validaciones posteriores dentro de la transacción fueron satisfactorias y se confirmó el commit. Después se volvió a verificar el estado persistente en una transacción **READ ONLY**.

| Comprobación | Resultado definitivo |
|---|---|
| Registro de `0004` | **Aplicada** |
| Otras migraciones aplicadas por el procedimiento | **Ninguna** |
| Migraciones pendientes | **Ninguna** |
| Tablas | **38**, sin tablas adicionales |
| Registros históricos | **267**, huellas de todas sus columnas anteriores idénticas |
| Registros totales posteriores | **268**: los 267 anteriores y una fila nueva en `django_migrations` |
| Usuarios, roles y permisos | Sin cambios, comprobados mediante huellas |
| Inscripciones, deportistas, grupos, cupos, reservas y horarios | Sin cambios, comprobados mediante huellas |
| Funciones de usuario | **8** |
| Triggers de usuario | **12**, todos habilitados |
| Restricciones de catálogo | **233**, incluidas las del nuevo constraint trigger; todas validadas |
| Índices | **184**, todos válidos y listos |
| Revisiones administrativas | **0** |
| Resultados administrativos | **0** |
| Operaciones deportivas ejecutadas | **0** |
| Django system check | Sin incidencias, 0 silenciadas |

El esquema pasó el comparador corregido, incluyendo los 21 CHECK y el índice parcial con representaciones acreditadas. No se omitieron restricciones, índices, funciones ni triggers. La comprobación operativa B3-C también confirmó la instalación de las protecciones.

Cambios de esquema autorizados y verificados:

- Columna JSON `evidencia_ejecucion` en `inscripciones_resultadoadministrativo`.
- Sustitución del CHECK `resultado_admin_b1_sin_ejecucion` por `resultado_admin_estado_coherente`.
- Índices únicos parciales `movimiento_afectacion_unico` y `movimiento_origen_unico`.
- Nueva función y constraint trigger `public.zdb_movimiento_ascenso_verificado`.
- Actualización prevista de las funciones `public.zdb_administracion_b3_evento` y `public.zdb_administracion_b3_guardia`; las demás funciones anteriores se conservaron y todos los triggers anteriores mantienen sus definiciones. Estas modificaciones son las de `0004`, no cambios fuera de alcance.

Se comprobó nuevamente la separación de permisos sin llamar servicios de negocio: el coordinador activo conserva la decisión pedagógica; el administrador puede ejecutar administrativamente pero no aprobar ascensos; el profesor no recibe autoridad de decisión ni ejecución. No se aprobaron progresiones, no se crearon inscripciones, traslados, eventos deportivos, revisiones ni resultados ficticios. La progresión y las inscripciones existentes conservaron sus huellas.

No se ejecutaron pruebas con escrituras en la base real. Este intento reutilizó la evidencia aislada existente y realizó las comprobaciones de instalación y lectura solicitadas. No hubo incidencias en el segundo intento, restauraciones, commits ni push. No se modificaron frontend, servicios, modelos ni migraciones.

### Evidencia del segundo intento y punto de parada

Carpeta nueva: **`respaldos/aplicacion_0004_segundo_20261031T012845Z/`**.

- `archivos_verificados.json`: huellas de instalador, comparador, certificado y migraciones.
- `manifiesto.json`: conexión, commit confirmado, respaldo, conteos, protecciones, permisos y ausencia de pendientes.
- `inventario_antes.json`, `inventario_dentro_transaccion.json` e `inventario_despues.json`.
- `huellas_historicas_dentro_transaccion.json` y `huellas_historicas_despues.json`.
- `comparacion_esquema.json`: comprobación íntegra con pares acreditados.
- `django_check.log`: configuración Django sin incidencias.
- `ejecutar_autorizado.py`: instrumento de una sola ejecución, que rechaza repetir este intento si ya existe su manifiesto.

**La instalación de estructura está completada. El procedimiento se detiene antes de cualquier operación deportiva o movimiento administrativo.** La comprobación operativa de B3-C reconoce ahora `0004`, pero este trabajo no autoriza ni ejecuta movimientos sobre datos existentes.

---

## Antecedente histórico — primer intento

**El registro que sigue describe el primer intento: detenido y revertido entonces. Su estado pendiente fue sustituido por la instalación satisfactoria del segundo intento descrita arriba.**

## Fecha, destino y alcance

- Inicio: 31 de octubre de 2026, 01:12:29 UTC; 30 de octubre, 20:12:29 en Bogotá.
- Detención: 01:12:31 UTC; 20:12:31 en Bogotá.
- PostgreSQL **17.11**, servidor **127.0.0.1:5432**, base **zona_bloque**, esquema **public**.
- Única migración autorizada: `inscripciones.0004_ejecucion_administrativa`.
- Entorno: `scripts/django_local.py`, utilizando los paquetes existentes de `.venv-local`.

No se ejecutaron servicios deportivos, revisiones administrativas, aprobaciones, traslados ni fixtures en la base real. No se modificaron código de aplicación, frontend, modelos o migraciones. No se realizaron commits ni push.

## Verificaciones previas satisfactorias

1. Configuración y conexión efectiva coinciden exactamente con el destino autorizado, incluida la versión 17.11.
2. `inscripciones.0003_revisionadministrativa_resultadoadministrativo_and_more` está aplicada y `0004` era la única migración pendiente.
3. La migración conserva su SHA-256 verificado: `115e827fbc4d84e13db8006bbee71b6882ffda4944bcba69345636b1dc7082c6`; ocho operaciones y atomicidad Django comprobadas.
4. Respaldo existente y tamaño comprobados: **239448 bytes**.
5. SHA-256 del respaldo correcto:

   `f51c94153a68261ea95b9b711424fad793e0639f5267358a52d69a3403a542c1`

   Archivo: `respaldos/preparacion_0004_20261031T005057Z/zona_bloque_pre_0004_20261031T005057Z.dump`.
6. Manifiesto revisado: lectura completa, restauración aislada, aplicación aislada y 50 pruebas focalizadas satisfactorias. Estas pruebas pertenecen a la preparación anterior; no se repitieron sobre datos reales.
7. Las **38 tablas y los 267 registros**, sus columnas, huellas, restricciones, índices, funciones, triggers y migraciones coinciden con la referencia previa.
8. No había otras sesiones de cliente con actividad o transacciones abiertas al comprobar la ventana.
9. Verificación de permisos mediante consultas y evaluación de la clase de permisos, sin llamar servicios con escrituras: administrador ejecuta administrativamente pero no decide pedagógicamente; coordinador activo conserva ambas facultades; profesor no recibe ninguna de ellas. La ejecución efectiva seguía bloqueada por la instalación pendiente.

## Transacción y motivo de la detención

Se abrió una transacción externa `transaction.atomic`, con `lock_timeout=5s` y `statement_timeout=120s`. Se adquirieron bloqueos `SHARE` sobre las tablas existentes en orden estable y se repitieron las verificaciones de huellas, plan único y respaldo antes del DDL.

Se invocó `MigrationExecutor.migrate` con objetivo explícito y plan exclusivo para `0004`, dentro de esa transacción. El DDL llegó a ejecutarse, pero **no se confirmó la transacción**: la validación posterior lanzó:

> El esquema real no coincide con la instalación aislada: restricciones

Al propagarse esa excepción fuera del bloque atómico, PostgreSQL revirtió tanto el esquema como el registro de `0004` en `django_migrations`. No se intentó otra migración, borrado de objetos ni restauración manual.

La causa identificada está en el comprobador de instalación: comparó literalmente todas las definiciones de restricciones del origen con las definiciones de la copia restaurada. Esa restauración normaliza casts de expresiones antiguas. La preparación ya había documentado y validado canónicamente **21 CHECK** equivalentes; sus textos no son idénticos. Estas diferencias preexistentes bastan para explicar el fallo del comparador.

No se encontró una diferencia nueva en los datos históricos. No obstante, la comprobación posterior completa de la instalación se interrumpió: no se considera `0004` instalada ni se afirma que se completaran todas sus verificaciones sobre la base real. El error es un criterio excesivamente estricto del comprobador preparado para este intento, no un error SQL informado por Django durante el DDL.

## Verificación posterior exclusivamente de lectura

Tras la detención se abrió una transacción `REPEATABLE READ, READ ONLY` y se comprobó:

| Elemento | Estado persistente verificado |
|---|---|
| `0003` | Aplicada |
| `0004` | **No aplicada; única pendiente** |
| Tablas existentes | **38**, idénticas a la referencia |
| Registros anteriores | **267**, conteos y huellas idénticos |
| Columnas y esquema anterior | Idénticos |
| Funciones de usuario | **7**, definiciones anteriores conservadas |
| Triggers de usuario | **11**, definiciones y estados anteriores conservados |
| Restricciones e índices | Idénticos al inventario anterior |
| Usuarios, roles y permisos | Huellas idénticas |
| Inscripciones, reservas, grupos y horarios | Huellas idénticas |
| Revisiones y resultados administrativos | Conservados; sin registros nuevos |

La evaluación de instalación B3-C permanece bloqueada al no existir el registro aplicado de `0004`. No se ejecutaron pruebas con escrituras en producción ni se activaron operaciones deportivas. No se continuó con comprobaciones que dependieran de una instalación confirmada.

## Evidencia conservada

Carpeta: `respaldos/aplicacion_0004_20261031T011121Z/`, excluida del control de versiones por la regla existente `respaldos/`.

- `aplicar.py`: instrumento exacto del intento; conservado sin corregir ni reejecutar.
- `manifiesto.json`: conexión, verificación del respaldo, fase alcanzada, error y ausencia del registro de migración tras el rollback.
- `inventario_antes.json`: inventario inmediatamente anterior.
- `verificar_rollback.py`: comprobación posterior exclusivamente de lectura.
- `inventario_tras_rollback.json`: inventario completo, idéntico al anterior.
- `verificacion_rollback.json`: resumen, única pendiente y las 21 diferencias textuales ya documentadas como equivalentes.

El respaldo aprobado y toda la evidencia de restauración anterior permanecen conservados. No se imprimieron contraseñas ni datos personales.

## Punto de parada y recomendación

Se respeta la condición de parada solicitada. **No se corregirá ni reintentará la instalación en este ciclo.**

Antes de un nuevo intento, debe revisarse el comparador para distinguir:

1. Objetos y huellas históricos, que deben compararse con el origen anterior.
2. Objetos introducidos o modificados por `0004`, que deben contrastarse con su definición esperada.
3. Diferencias de representación de casts, que requieren equivalencia canónica comprobada en PostgreSQL aislado, sin omitir restricciones ni desactivar protecciones.

La corrección del comprobador debe probarse de forma aislada. Un nuevo intento real requiere revisión e instrucciones expresas y repetir las comprobaciones previas sobre el estado vigente. No se propone restauración destructiva: el estado anterior ya se conserva íntegramente por rollback transaccional.

## Actualización intermedia: comprobador corregido sin reinstalación

Con autorización posterior se corrigió exclusivamente el comparador y se verificó en PostgreSQL aislado: 24 pruebas aprobadas e integración satisfactoria del comprobador en solo lectura. Véase [CORRECCION_COMPROBADOR_INSTALACION_0004.md](CORRECCION_COMPROBADOR_INSTALACION_0004.md). En esa etapa intermedia `0004` seguía pendiente y la base real conservaba 38 tablas y 267 registros; todavía no se había realizado el segundo intento que finalmente completó la instalación.
