# Ascensos institucionales — Backend B2.2-A

Fecha: 30 de octubre de 2026.

## Alcance y arquitectura implementada

Se amplía el ViewSet existente de `/api/ascensos/`, con el mismo router, autenticación por sesión y protección CSRF. Las decisiones reutilizan `decidir_progresion(actor, identificador, version, aprobar, resolucion)` de B1. No se implementa otro motor de decisiones ni se modifica el frontend.

Se revisaron el diseño del Incremento 2, la implementación B1, la integración B2.1, sus entregas backend/frontend y los servicios y pruebas existentes. B1 distingue decisión pedagógica, disposición de cada inscripción y estado del plan. Esa separación se conserva.

Las únicas escrituras de una decisión son sobre progresión, eventos, auditoría administrativa y, al rechazar, las revocaciones de excepciones y disposiciones de continuidad que ya establece B1. No se escriben inscripciones, eventos deportivos, grupos, horarios, asignaciones, cupos ni reservas. No se habilita ejecución administrativa.

## Contratos REST

| Método y ruta | Contrato | Autorización |
| --- | --- | --- |
| `GET /api/ascensos/` | Lista paginada; filtros opcionales `estado_decision`, `deportista`, `disciplina`, `page` | Coordinador activo: institucional; profesor: propuestas propias dentro de su ámbito vigente; administrador: lectura existente |
| `GET /api/ascensos/{id}/` | Detalle institucional para coordinador; proyección mínima anterior para profesor/administrador | Mismo ámbito de lectura existente; detalle ampliado exclusivo del coordinador activo |
| `GET /api/ascensos/{id}/advertencias/` | `version`, advertencias con código/mensaje e indicadores de bloqueo, `puede_aprobar`, `puede_rechazar`, `ejecucion_habilitada: false` | Solo coordinador activo |
| `POST /api/ascensos/{id}/aprobar/` | Decisión explícita `aprobar`, versión observada y resolución | Solo coordinador activo |
| `POST /api/ascensos/{id}/rechazar/` | Decisión explícita `rechazar`, versión observada y resolución | Solo coordinador activo |

Los endpoints docentes de creación, contexto y niveles de B2.1-A conservan sus contratos. No se añaden rutas de edición de afectaciones, excepciones, revocación o ejecución.

Ejemplo de estructura de petición de decisión, únicamente ilustrativo:

```json
{
  "version": 2,
  "decision": "aprobar",
  "resolucion": "Motivación pedagógica de la resolución"
}
```

El identificador proviene de la ruta; la versión debe ser un entero positivo. La resolución es obligatoria, recortada y de máximo 500 caracteres. La decisión debe coincidir con la acción de la ruta. Se rechazan campos desconocidos o repetidos y parámetros de consulta en acciones de decisión/advertencias. No se aceptan actor, fecha, estados, destinos ni datos de ejecución del cliente.

La lista del coordinador añade `version` y `profesor_proponente` (ID y nombre). El detalle añade:

- Datos mínimos de deportista, disciplina, niveles, referencia, periodo, justificación y estados de la progresión.
- Unión de inscripciones originalmente afectadas y actualmente pertinentes, identificando incorporaciones posteriores y registros que ya no pertenecen al conjunto vigente.
- ID, versiones actual/observada, fechas, estado, situación activa/reserva/futura/suspendida o finalizada, grupo, nivel, periodo, reservas vigentes, disposición y destino propuesto por inscripción.
- Excepciones con situación temporal y datos de autorización/revocación ya registrados en B1.
- Decisión con responsable, fecha y resolución; eventos con tipo, versión, fecha, responsable y motivo.
- Resumen de advertencias; nunca una instrucción de traslado.

No se devuelve el JSON interno de evidencias de los eventos, números documentales, fecha de nacimiento, teléfonos, correos ni documentación de acudientes. Los profesores no reciben el detalle institucional, los eventos, las excepciones ni inscripciones de grupos ajenos. El administrador mantiene su consulta anterior y no obtiene autoridad pedagógica ni acceso al nuevo resumen restringido.

Respuestas: `200` para consulta/decisión satisfactoria; `400` para entrada inválida o disposición incompleta; `403` para decisión no autorizada; `404` para objeto fuera del ámbito de lectura; `409` para versión obsoleta, decisión repetida o cambios materiales. La respuesta de una decisión satisfactoria es el detalle institucional actualizado.

## Revalidaciones y evidencia material

El servicio B1 vuelve a comprobar el coordinador activo dentro de la transacción, aunque el permiso HTTP se haya comprobado antes. Verifica versión y estado pendiente, coherencia de deportista/disciplina/niveles, orden pedagógico consecutivo y conjunto de inscripciones. La aprobación exige que el profesor siga teniendo una referencia activa autorizada. La pérdida de asignación no impide por sí sola rechazar, manteniendo la semántica B1.

Se refuerza una brecha de B1: comparar solo versión y situación de inscripción no detectaba cambios de horarios, capacidad o fechas de reserva realizados sin incrementar aquella versión. Los nuevos eventos incorporan evidencia estructural en su JSON existente, sin añadir campos ni tablas:

- `contexto_revision`: estado activo del deportista y disciplina, catálogo/orden/actividad de niveles, inscripciones pertinentes con versión, estado y fechas, estructura de sus grupos y periodos, horarios, capacidad y reservas con sus fechas y liberación.
- `contexto_destinos`: estructura de los destinos expresamente dispuestos mediante el servicio interno B1.

La evidencia original procede del evento inalterable `proponer_ascenso`. Se compara con el contexto actual mediante SHA-256 sobre JSON normalizado. Para cada destino se compara la evidencia del último evento `revisar_plan` correspondiente a esa afectación. Las decisiones y otros eventos posteriores no sustituyen la evidencia original de la propuesta ni reconstruyen su pasado.

Un cambio de conjunto, versión, situación, grupo, periodo, horario, capacidad, reserva, catálogo o destino bloquea la decisión con un mensaje de revisión. No se sincronizan ni eliminan afectaciones automáticamente. Las inscripciones suspendidas con reserva y las futuras se incluyen; tampoco se ignoran suspendidas sin reserva que B1 considera pertinentes.

Si una propuesta anterior carece de esta evidencia material, permanece consultable y conserva sus registros, pero las decisiones se bloquean. Hace falta definir posteriormente un procedimiento explícito y auditado de revisión; esta entrega no inventa una actualización de evidencia histórica.

## Disposiciones, aprobación y límites funcionales

Se conserva la precondición B1: todas las inscripciones deben tener disposición expresa antes de aprobar. Una disposición `pendiente` permite aprobación pedagógica sin destino ni plaza garantizada. Una disposición `continuidad` requiere excepción temporal vigente. Los niveles mixtos requieren revisión institucional.

Las propuestas nuevas de B2.1 nacen con disposición `revisar`. Esta entrega **no las transforma automáticamente** en `pendiente` y **no expone un endpoint para preparar el plan**. Una aprobación sin aquella preparación devuelve `400` y una advertencia por inscripción. Las pruebas de aprobación válida preparan el plan exclusivamente mediante el servicio interno B1 en fixtures aisladas. El rechazo de una propuesta sin preparar sí es posible cuando no hay otros bloqueos materiales.

Los estados `parcial` y `preparado` conservan su significado B1: disposición del plan, nunca ejecución ni garantía de viabilidad. No se verifica ni garantiza una plaza de destino como si se estuviera realizando un traslado. La evaluación operativa final de cupos y compatibilidad para ejecutar corresponde a B3; una aprobación pedagógica no modifica ocupación ni reserva recursos.

No se define una caducidad nueva de propuesta: no existe tal campo en el modelo actual. Los cambios temporales que alteran el conjunto o situación observada sí bloquean la decisión. No se crea nivel efectivo institucional ni se modifican niveles de grupos.

## Transacciones, concurrencia y auditoría

Se mantiene `transaction.atomic`, el orden global de bloqueo de usuarios compartido con los servicios institucionales, el bloqueo de progresión y deportista y la comprobación optimista de versión. Se bloquean además las inscripciones relevantes/originales, grupos de origen/destino y reservas, en orden de ID antes de reconstruir el contexto.

La segunda decisión sobre la misma versión o sobre un expediente resuelto falla sin generar un segundo evento. Un relevo/desactivación confirmado antes de entrar al servicio invalida al actor, aunque haya superado el permiso HTTP. Un fallo al registrar el evento revierte la decisión completa. Las revocaciones que B1 realiza al rechazar conservan su auditoría y protecciones transaccionales existentes.

No se cambian las funciones, triggers ni restricciones PostgreSQL de B1. Se mantienen la protección del historial y el bloqueo de `estado_plan='ejecutado'`, incluso mediante SQL directo, cubiertos por la regresión existente.

Los bloqueos institucionales serializan escrituras de aplicación. No se afirma protección contra un operador privilegiado que omita deliberadamente todos los servicios y altere tablas relacionadas mediante SQL concurrente; ese acceso requiere controles operativos. El bloqueo global de usuarios conserva la limitación de escalabilidad existente, razonable para la escuela pequeña, sin ampliar esta entrega a una reestructuración de concurrencia.

## Vía histórica de cambio de nivel

Se conserva el bloqueo de creación y aprobación del antiguo tipo `nivel`, incluido el acceso directo HTTP. Las propuestas históricas permanecen consultables y no se convierten, cancelan ni reescriben. Inscripción adicional y traslado al mismo nivel conservan sus servicios y pruebas.

## Archivos creados o modificados

| Archivo | Cambio |
| --- | --- |
| `backend/inscripciones/revision_ascensos.py` | Nuevo módulo de evidencia material, advertencias y detalle institucional de lectura |
| `backend/inscripciones/servicios_ascensos.py` | Evidencia en eventos existentes y revalidación/bloqueos adicionales antes de decidir |
| `backend/inscripciones/serializers_ascensos.py` | Proyección de coordinación y entrada estricta de decisión |
| `backend/inscripciones/views_ascensos.py` | Detalle ampliado, advertencias y acciones específicas de decisión con permisos efectivos |
| `backend/inscripciones/test_revision_ascensos.py` | 24 pruebas nuevas, incluidas concurrencia y desactivación durante la petición |
| `backend/inscripciones/test_api_ascensos.py` | Ajuste de la expectativa anterior de inexistencia de decisiones; se conserva prohibición de ejecución/edición pública de plan |
| `docs/IMPLEMENTACION_ASCENSOS_B2_2_A.md` | Contratos, validaciones, resultados y límites de esta entrega |

El router descubre las acciones sin modificar URLs. No se modifican frontend, modelos ni migraciones.

## Verificaciones ejecutadas

Todas las escrituras de prueba se ejecutaron con `scripts/pruebas_postgresql_aisladas.py`, que inicializa un clúster hijo PostgreSQL independiente, comprueba su directorio de datos y PID y utiliza puerto efímero y base de pruebas separada. Los paquetes Django proceden de `.venv-local` mediante `scripts/django_local.py`. No se conectó a `zona_bloque` para ejecutar estas pruebas.

Comando de regresión completa:

```powershell
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

Resultados finales:

- **372 pruebas backend aprobadas**, sin fallos ni omisiones informadas; ejecución de pruebas: **77,116 segundos**.
- Incluyen los módulos cuentas, organización, paneles, deportistas e inscripciones; 348 pruebas previas y 24 nuevas.
- Verificación Django: `System check identified no issues (0 silenced)`.
- `makemigrations --check --dry-run`, contra el entorno aislado: `No changes detected`.
- Evidencia privada del ejecutor: `respaldos/pruebas_fase3_69h_0clt/`, puerto temporal `58020`; clúster detenido y base de pruebas destruida al terminar.
- Tanda focalizada anterior de 21 pruebas aprobada. Durante el desarrollo se corrigió una expectativa de prueba que usaba `aprobar` en lugar del tipo real de evento `aprobar_ascenso`; no fue necesario cambiar el contrato B1.

Las nuevas pruebas cubren filtros estrictos y paginación; detalle con inscripciones activas, reservas y futuras; aprobación/rechazo auditados sin movimientos; disposición no inventada; aislamiento por rol/ámbito; coordinador desactivado o relevado; CSRF; versión obsoleta y duplicación; inyección de propiedades protegidas; cambios de conjunto, versión, grupo, horario, periodo, reserva y destino; pérdida de asignación; expediente sin evidencia histórica; reversión ante fallo de evento; historial y estado ejecutado protegidos; aprobaciones simultáneas y desactivación entre el permiso HTTP y el servicio.

La regresión previa mantiene las comprobaciones SQL directas y de migración/reversión en PostgreSQL temporal, la protección de excepciones y el bloqueo del flujo antiguo. No se ejecutaron pruebas HTTP sobre datos reales ni se crearon decisiones reales. No se ejecutó frontend porque no se modificó en esta entrega.

Migraciones generadas: **ninguna**. Migraciones aplicadas a la base real: **ninguna**. No se consulta ni se afirma nuevamente el estado de migraciones de producción. La huella SHA-256 de la migración B1 permanece `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`.

## Requisitos para conectar la interfaz y pendientes

La interfaz futura del coordinador deberá presentar todas las filas, sus situaciones y advertencias, mantener visibles por separado decisión y plan, enviar la versión consultada, motivar cada decisión y gestionar `400/403/409` mediante nueva consulta. No debe ocultar filas nuevas o suspendidas/futuras ni ofrecer ejecución.

Antes de habilitar un ciclo completo de aprobación desde la interfaz se necesita autorizar la preparación explícita del plan, conservando las validaciones B1, y definir la revisión auditada de expedientes que cambiaron o carecen de evidencia. No se implementaron esas operaciones en B2.2-A ni se rellenaron registros anteriores.

Quedan fuera B2.2-B, B2.2-C y B3, traslados, excepciones públicas nuevas, nivel efectivo institucional, cupos por sesión, planes individuales, evaluaciones y malla curricular. No hubo cambios de roles, credenciales ni permisos institucionales, commits o push. La entrega se detiene para revisión.
