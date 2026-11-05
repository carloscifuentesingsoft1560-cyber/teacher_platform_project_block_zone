# F3.6-B1 — estructura de propuestas de competencia emisora

Estado: implementación verificada con 24/24 pruebas de aislamiento y 13/13 pruebas B1 PostgreSQL satisfactorias. No habilitada operativamente. No constituye aprobación institucional.

Base revisada: rama `interfaz-sesiones-react`, commit `ecdad5503f79fa1ac4446598f5db2ab3aa90bcc3`.

## Alcance y decisiones técnicas

Se añaden dos modelos en cuentas, siguiendo las relaciones protegidas y la separación entre `Persona`, cuenta y enlace acreditado existentes:

- `CompetenciaEmisora`: propuesta de identidad y ámbito por disciplina. Conserva persona, cuenta, enlace, versión y referencia UUID de evidencia de identidad, además de autor y fecha de registro. El enlace debe estar vigente y coincidir al insertar. Las referencias y su copia histórica no se actualizan al revocar posteriormente el enlace.
- `EventoCompetenciaEmisora`: cadena numerada de propuesta inicial, revisiones de fechas propuestas y retiro terminal. Conserva autor, motivo, evidencia UUID, clave de solicitud, intervalo propuesto y antecedente. No existen acciones de aprobación, activación o concesión. El retiro retira una propuesta; no representa revocar una facultad real.

El ámbito es inmutable: un cambio de disciplina, identidad o alcance exige otra propuesta. Una revisión permite cambiar la evidencia, motivo e intervalo propuestos conservando el antecedente. Se admiten propuestas coexistentes: no existe una unicidad de «competencia vigente», porque B1 no define competencias aprobadas.

La versión se representa por el número del evento; no hay una cabecera mutable con estado ni un indicador activo. El antecedente y número esperado permiten rechazar versiones obsoletas. La clave por actor impide duplicar eventos, pero B1 no implementa un servicio de reintento que devuelva una respuesta histórica.

`alcance_propuesto` es texto descriptivo de una candidatura, no un catálogo evaluable de restricciones ni una autorización por actividad. La institución debe definir ese catálogo y su semántica antes de utilizarlo para emitir autorizaciones funcionales.

No se añaden endpoints, serializadores, acciones de autorización, registro en administración ni servicios de concesión. Los modelos solo declaran permiso predeterminado de lectura; no se reutilizan facultades de administrador/coordinador para emitir. No se crea ni carga ninguna propuesta o autoridad en la base operativa. Las fixtures utilizadas en PostgreSQL temporal son exclusivamente datos ficticios de pruebas.

## Integridad y auditoría

La migración `0008_competencia_emisora_b1` contiene únicamente creación de tablas, restricciones e índice. Se generó mediante `MigrationLoader(None)` y el autodetector, con settings configurados en memoria y backend dummy; no se importaron los settings del proyecto ni `.env`, ni se ejecutó SQL.

La migración aditiva `0009_competencia_emisora_guardias_b1` incorpora:

- Inmutabilidad SQL de ambas tablas frente a UPDATE/DELETE, además de las guardias ORM de instancia, queryset y bulk_update.
- Contraste de persona, usuario, versión y evidencia contra el enlace vigente, bloqueándolo al insertar la propuesta.
- Bloqueo de cabecera al añadir eventos; número consecutivo y antecedente exactamente igual al último evento, sin bifurcaciones ni reapertura tras retiro.
- Primer evento obligatorio con autor coincidente con el registro de cabecera. Una restricción diferida exige su presencia antes de confirmar la transacción.
- Fechas de registro fijadas por el servidor. Las fechas del intervalo son propuestas, nunca vigencias de autoridad ya aprobada.

Las claves foráneas protegen las referencias; las restricciones comprueban versión positiva, motivo y alcance con contenido, intervalo final estrictamente posterior al inicial, acciones permitidas y forma del origen. Hay unicidad por competencia/número, actor/clave y antecedente; índice por persona/disciplina y los índices de las relaciones.

Los eventos son la evidencia de dominio auditable. No se escribe en `CambioAdministrativo` porque no hay servicios operativos de escritura; su integración corresponderá a una fase posterior. Ninguna declaración de inmutabilidad protege contra un administrador de base de datos que elimine guardias o tablas: no es el modelo de amenaza de estas restricciones.

La migración de guardias se declara sin reversión automática para impedir retirar protecciones y perder evidencia sin un procedimiento revisado. Antes de desplegar debe aprobarse una estrategia de recuperación; `0008` y `0009` se aplicaron satisfactoriamente solo en PostgreSQL temporal, sin migraciones operativas. No se alteran migraciones históricas ni funciones o triggers de sesiones.

## Comprobaciones realizadas

- Rama, commit base y estado de Git, sin modificar los diez archivos ajenos sin seguimiento.
- Lectura de convenciones de identidad, roles, auditoría, organización y migraciones.
- Revisión de la migración generada y del SQL aditivo, con aplicación posterior satisfactoria exclusivamente en el clúster temporal aislado.
- Verificador estático: sintaxis Python, checks de los dos modelos, grafo sin diferencias entre modelos y migraciones y cinco guardias ORM por modelo. Configura exclusivamente backend dummy y prohíbe `ensure_connection`; no importa `.env` ni settings del proyecto.
- 24/24 pruebas de infraestructura de aislamiento satisfactorias: argumentos peligrosos rechazados, entorno saneado, settings sin dotenv ni conexiones y limpieza simulada del hijo propio. Estas pruebas de barreras no inician PostgreSQL; las 13 pruebas B1 se ejecutaron posteriormente en un clúster temporal nuevo.

El workspace no contiene `.venv-local`; para estas comprobaciones se reutilizó en lectura Django 5.2.18 del entorno ya existente del proyecto contiguo con Python 3.12. No se instalaron paquetes ni se leyeron sus configuraciones o credenciales.

## Aislamiento y resultados verificados — actualización F3.6-B1.1

Se endurecieron `scripts/pruebas_postgresql_aisladas.py`, `scripts/django_local.py` y los settings PostgreSQL aislados. El nuevo auxiliar puro `backend/configuracion/aislamiento_pruebas.py` comparte la validación del manifiesto, identidad y entorno sin importar Django ni dotenv. Se mantienen las comprobaciones de directorio/PID y se contrastan también host y puerto del servidor. No se carga `.env` para este perfil.

El clúster y toda la evidencia se crean exclusivamente en una carpeta nueva `zdb_pg_<aleatorio>` del temporal del sistema, fuera del repositorio. Se aíslan temporales, almacenamiento privado, directorios de usuario y archivos libpq. El entorno hijo usa lista positiva y rutas explícitas de paquetes/binarios. La reubicación modifica coordinadamente las barreras, sin aceptarlas desde `respaldos/` ni reutilizar clústeres anteriores. PostgreSQL se ejecutó únicamente en los clústeres temporales expresamente autorizados. Procedimiento y destinos en [la guía técnica](PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md).

Se ejecutaron y aprobaron las trece pruebas B1: las ocho originales, tres adicionales de restricciones/irreversibilidad y dos de transacciones. La concurrencia acepta únicamente SQLSTATE y causas de conflicto esperadas; propaga timeouts, deadlocks y errores de infraestructura. Se verificaron rollback completo de cabecera/eventos y fallo de la restricción diferida en COMMIT, además de alcance vacío, versión no positiva, autor inicial incompatible e intervalos vacíos/invertidos. La irreversibilidad de `0009` se comprobó sin retirar guardias, esperando `NotImplementedError` en la llamada directa a `RunSQL.database_backwards()` de Django 5.2.18.

La migración `0009` permanece deliberadamente irreversible. No habilitar escrituras en una instalación detenida en `0008`: todavía faltan las guardias de `0009`. No se modificaron las dos migraciones preparadas durante B1.1.

Resultados finales: 24/24 pruebas de barreras y 13/13 pruebas B1 PostgreSQL satisfactorias; cero fallidas u omitidas en la segunda ejecución controlada. También pasaron sintaxis/espacios, verificador estático B1 y `git diff --check`. Las migraciones `0008` y `0009`, restricciones SQL, triggers, inmutabilidad, rollback y concurrencia quedaron verificados dentro del alcance B1. El chequeo posterior de modelos/migraciones terminó con `No changes detected` y código 0. La primera ejecución se detuvo por la expectativa de excepción de irreversibilidad; la segunda utilizó un clúster nuevo después de corregir únicamente esa expectativa.

Las evidencias de la ejecución satisfactoria se conservaron en `C:\Users\57310\AppData\Local\Temp\zdb_pg_chbim1fd`, base `test_zdb_fase3_f2159c956366`. El hijo PID 25776, puerto 58338, quedó detenido mediante cierre controlado con identidad revalidada y sin incidentes; el log confirma el apagado. Los archivos de la ejecución anterior permanecen intactos.

La suite completa de regresión, incluido sesiones, no se ejecutó en esta validación: la autorización se limitó al módulo B1 y al chequeo posterior de correspondencia. Estos resultados no certifican otras suites ni habilitan despliegue operativo.

## Decisiones institucionales pendientes

Quién acredita al emisor; evidencia y custodia admitidas; catálogo de ámbitos/restricciones; independencia y prohibición de autoacreditación; duración, renovaciones y efectos de revocar la identidad; sustituciones, autoridad externa y relación con futuras competencias aprobadas. B1 no decide ni habilita ninguno de esos actos.

## Archivos de B1

- `backend/cuentas/models.py`: importa los nuevos modelos.
- `backend/cuentas/modelos_competencias.py`: estructura y guardias ORM.
- `backend/cuentas/migrations/0008_competencia_emisora_b1.py`: esquema aditivo.
- `backend/cuentas/migrations/0009_competencia_emisora_guardias_b1.py`: guardias SQL aditivas.
- `backend/cuentas/tests/test_competencias_b1.py`: trece pruebas verificadas en PostgreSQL aislado.
- `scripts/verificar_competencias_b1_estatico.py`: verificación sin conexión ni archivos generados.
- Este documento.

Archivos adicionales modificados por B1.1: `scripts/pruebas_postgresql_aisladas.py`, `scripts/django_local.py`, `scripts/test_infraestructura_aislada.py`, `backend/configuracion/settings.py`, `backend/configuracion/settings_pruebas_postgresql.py`, nuevo `backend/configuracion/aislamiento_pruebas.py` y `docs/PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md`. También se amplió la prueba B1 ya enumerada. La implementación B1 fue revisada y su publicación autorizada después de la validación indicada.

No se modificaron React, flujo docente, `verificar_autorizacion_funcional()`, trigger de `realizada`, temporales preexistentes ni respaldos. No hubo conexión a `zona_bloque` ni migraciones operativas. B1 queda verificado en el alcance indicado; las decisiones institucionales permanecen pendientes.
