# Preparación expresa del plan de ascensos — B2.2-B1

Fecha: 30 de octubre de 2026.

## Implementación y alcance

Se revisaron los modelos, servicios y pruebas B1, el backend de revisión B2.2-A y sus documentos de implementación. Se reutiliza `disponer_inscripcion(actor, identificador, version, afectacion_id, disposicion, motivo, destino_id=None)`, reforzado antes de exponerlo por API. No se duplican los modelos ni el motor de preparación.

Esta entrega prepara el plan **antes de la decisión pedagógica**. Solo admite progresiones pendientes de decisión; una decisión ya registrada requiere otro procedimiento expresamente autorizado para revisar posteriormente su plan. No se altera su resolución. Preparar, aprobar y ejecutar siguen siendo operaciones distintas. No hay endpoint ni servicio de ejecución nuevo.

## API y permisos

El router existente de `/api/ascensos/` incorpora las acciones del mismo ViewSet, sin modificar `urls.py`.

| Método y ruta | Resultado | Permiso |
| --- | --- | --- |
| `GET /api/ascensos/{id}/afectaciones/` | Todas las filas del plan, versión, estados y advertencias | Coordinador activo |
| `POST /api/ascensos/{id}/disponer/` | Registra una disposición individual y devuelve el detalle institucional actualizado | Coordinador activo |
| `GET /api/ascensos/{id}/` | Detalle institucional existente, ahora con motivo e indicadores de pendientes en cada fila | Se conserva la proyección restringida por rol de B2.2-A |
| `GET /api/ascensos/{id}/advertencias/` | Advertencias existentes y nuevo indicador `puede_preparar` | Coordinador activo |

El profesor y el administrador reciben `403` en las dos acciones nuevas. No se amplía la proyección docente ni la consulta administrativa anterior. El coordinador inactivo o relevado pierde el permiso, y se vuelve a validar el usuario real dentro de la transacción del servicio. Se conserva autenticación por sesiones y CSRF.

Petición ilustrativa para una disposición sin destino:

```json
{
  "version": 1,
  "afectacion": 10,
  "disposicion": "pendiente",
  "motivo": "Revisada expresamente; pendiente de reubicación"
}
```

Los números del ejemplo no identifican registros reales. `version` es la versión observada de la **progresión completa**, no de la inscripción o afectación. `afectacion` debe pertenecer a la progresión de la ruta. Para `reubicar` se exige además `destino`, un ID de grupo existente. En otras disposiciones se omite o se envía `null`. Se rechaza cualquier destino no nulo en esas otras disposiciones.

Los identificadores deben ser enteros positivos; motivo obligatorio, sin espacios vacíos y de máximo 500 caracteres. Las opciones proceden directamente de los `choices` del modelo. No se admiten autor, estado pedagógico, estado del plan, datos de excepción, fechas de auditoría, versión de inscripción ni otras propiedades. Tampoco parámetros de consulta para estas acciones; se rechazan campos repetidos/desconocidos.

`GET afectaciones` responde con `id`, `version`, `estado_decision`, `estado_plan`, `inscripciones` y `revision`. Devuelve el conjunto completo para revisar conjuntamente el plan del deportista; no es un catálogo general de expedientes. Conserva la unión de afectaciones originales y actuales de B2.2-A, señalando entradas posteriores sin incorporarlas automáticamente.

Cada fila incluye los datos deportivos existentes, `disposicion`, `destino_propuesto`, `motivo`, `requiere_revision` y `reubicacion_pendiente`. `requiere_revision` identifica filas no incorporadas o con disposición `revisar`; no sustituye las demás advertencias. `reubicacion_pendiente` identifica la disposición `pendiente`. Reservas y situaciones futuras se muestran separadamente. `revision.puede_preparar` es informativo: el POST siempre vuelve a validar.

Respuestas: `200` para consulta o preparación correcta; `400` para datos/disposición/destino inválidos o continuidad sin excepción vigente; `403` por falta de permiso; `404` si progresión, afectación del ámbito indicado o destino no están disponibles; `409` para versión obsoleta, progresión resuelta o contexto material desactualizado. Ante errores no se incrementa la versión ni se registra una preparación parcial.

## Disposiciones y estados reales

| Disposición B1 | Significado y controles |
| --- | --- |
| `revisar` | Mantiene o reabre explícitamente la revisión; impide aprobar hasta disponerla expresamente de otro modo |
| `pendiente` | Inscripción revisada con reubicación pendiente; sin destino ni plaza garantizada |
| `reubicar` | Destino propuesto obligatorio, estructural y temporalmente compatible; no realiza traslado |
| `continuidad` | Permanencia temporal condicionada a una excepción pedagógica previamente autorizada y vigente |
| `reserva` | Solo para situación observada de reserva y contexto vigente; no crea, amplía ni libera reservas |
| `futura` | Solo para inscripción futura observada y contexto vigente; no adelanta ni modifica ingreso |

No se añadieron estados al modelo. B1 calcula `estado_plan` así: `pendiente` si todas las filas siguen en `revisar`; `preparado` si todas tienen `reubicar`; `parcial` si hay alguna disposición distinta de `revisar` y no todas son `reubicar`. Por tanto, un plan cuyas filas fueron revisadas expresamente como `pendiente`, `reserva` o `futura` puede seguir llamándose `parcial` y ser susceptible de aprobación pedagógica. El campo es estructural, no porcentaje de ejecución. La interfaz futura deberá distinguirlo de `revision.puede_aprobar`.

## Validación de destinos y límites operativos

El destino debe existir, estar activo y tener periodo, disciplina y nivel activos. Debe pertenecer a la disciplina de la progresión y a su nivel propuesto; no puede ser el grupo de origen. Se exige al menos un horario activo y una ventana temporal común no pasada, considerando fecha de ingreso y fechas de los periodos de origen/destino. No se presume igualdad de IDs de periodo ni se inventa una fecha efectiva de traslado.

Se preserva la semántica B1: el destino es **propuesto**, no una reserva ni una ejecución viable garantizada. Se permite prepararlo aunque esté lleno; en ese caso no se crea plaza ni se supera su capacidad. La compatibilidad definitiva de horarios y cupos del plan conjunto deberá revalidarse cuando se autorice B3. No se simulan movimientos parciales contra las inscripciones actuales, porque las otras inscripciones también podrían tener reubicaciones previstas. Esta API no permite utilizar `preparado` como permiso para ejecutar.

## Contexto, versiones y transacciones

Se extrae el bloqueo de contexto ya usado por la decisión a un helper compartido: usuarios en orden global, progresión, deportista, inscripciones originales/pertinentes, grupos y reservas por ID. La preparación incluye en los grupos bloqueados el nuevo destino, si existe.

Antes de escribir se comprueban la coherencia de deportista/disciplina/niveles, orden institucional, conjunto completo de inscripciones, versiones y situaciones observadas y evidencia material inalterable introducida en B2.2-A. Se mantienen activas, suspendidas con reserva, futuras y las suspendidas sin reserva que B1 considera pertinentes.

Se bloquea ante cambios materiales de grupo, horario, periodo, capacidad, reserva, versión, situación, catálogo de niveles o conjunto de inscripciones. También se bloquea si cambió un destino ya revisado o falta evidencia material anterior. No se utiliza esta acción para reconstruir el conjunto, subsanar un expediente desactualizado, rebasar la evidencia ni eliminar afectaciones. El procedimiento seguro de revisión integral sigue pendiente de autorización.

Se pueden corregir disposiciones no resueltas dentro de un contexto vigente: por ejemplo, pasar una continuidad sin excepción vigente a `pendiente`. Las advertencias de disposición sin revisar, excepción vencida o pérdida de referencia del profesor no se convierten en una autorización pedagógica. El servicio de decisión mantiene sus controles específicos, incluida la asignación vigente exigida al aprobar.

La escritura es atómica: disposición, estado del plan, versión de progresión, evento y auditoría se confirman juntos. Dos preparaciones concurrentes sobre una misma versión producen una única modificación y un conflicto para la otra. El bloqueo global de usuarios es el mecanismo institucional ya existente; no se rediseña su escalabilidad ni se afirma aislamiento frente a un propietario que omita los servicios mediante SQL arbitrario.

## Excepciones e historial

No se exponen acciones nuevas para autorizar o revocar excepciones. `continuidad` consulta las excepciones reales de la afectación y exige `situacion == 'vigente'`. Un motivo como «autorizada», un estado enviado por el cliente o un ID de excepción arbitrario no sustituye el procedimiento institucional.

Se conserva el servicio B1 de autorización/revocación con responsable, motivo y fechas, así como los triggers que protegen su historial. Una excepción revocada, vencida o programada no habilita continuidad vigente. La autorización expresa se probó mediante el servicio interno únicamente en fixtures aisladas. Si no existe una excepción autorizada, la API no la crea para completar el formulario.

Cada preparación registra `revisar_plan` con actor, fecha, motivo y nueva versión, más `CambioAdministrativo`. Se añade a la referencia del evento la disposición, destino y motivo anteriores; las fotografías de afectaciones en los nuevos eventos incluyen también su motivo. Esto conserva las correcciones sucesivas sin sobrescribir eventos anteriores. No se reconstruyen motivos ausentes en eventos históricos ni se alteran sus JSON.

Los nuevos endpoints usan la misma proyección mínima institucional de B2.2-A. No devuelven documentos, fechas de nacimiento, teléfonos, correos ni el JSON interno de evidencias.

## Archivos modificados

- `backend/inscripciones/servicios_ascensos.py`: preparación reforzada, bloqueo compartido y trazabilidad de cambios de disposición.
- `backend/inscripciones/serializers_ascensos.py`: entrada estricta `DisposicionAscensoSerializer`, basada en opciones reales del modelo.
- `backend/inscripciones/views_ascensos.py`: consulta de afectaciones y POST de disposición, exclusivos del coordinador activo.
- `backend/inscripciones/revision_ascensos.py`: indicador de preparación e información explícita de motivos y pendientes por inscripción.
- `backend/inscripciones/test_plan_ascensos.py`: 23 pruebas nuevas de API, integridad, excepciones y concurrencia.
- Este documento.

No se modifican modelos, migraciones, URLs, frontend, configuración de seguridad, roles o credenciales. La migración B1 conserva SHA-256 `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`.

## Pruebas y comprobaciones

Las pruebas con escrituras se ejecutaron exclusivamente con `scripts/pruebas_postgresql_aisladas.py`. El ejecutor inicializa un proceso hijo PostgreSQL en puerto efímero, comprueba su directorio de datos y PID y configura una base de pruebas independiente antes de ejecutar Django con los paquetes de `.venv-local`. No usa `zona_bloque` ni libera reservas reales.

Comando de regresión:

```powershell
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

La tanda focalizada aprobó **23 pruebas** en **10,768 segundos**, sin incidencias Django y con `makemigrations --check --dry-run`: `No changes detected`. Evidencia privada: `respaldos/pruebas_fase3_rhe8qt0r/`, puerto aislado `57835`, clúster detenido y base de pruebas destruida.

La suite nueva comprueba: consulta; disposición válida; múltiples inscripciones; reserva y futura; destino lleno sin asignar cupo; destino inexistente, inactivo, ajeno, sin horarios o sin vigencia común; payload estricto; denegación docente/administrador/inactivo; versión obsoleta; afectación ajena; cambios materiales y nuevas inscripciones; reserva/destino modificado; continuidad sin excepción, con autorización expresa, revocada o vencida; preservación de motivos y reapertura; rollback por fallo de auditoría; separación entre preparar/aprobar/ejecutar; CSRF y concurrencia con conexiones independientes.

Regresión completa final: **395 pruebas backend aprobadas** (372 anteriores y 23 nuevas), en **90,212 segundos**, sin fallos ni omisiones informadas. Incluye cuentas, organización, paneles, deportistas e inscripciones. Django informó `System check identified no issues (0 silenced)` y la comprobación de migraciones en seco en el clúster aislado informó `No changes detected`.

Evidencia privada final: `respaldos/pruebas_fase3_20jks77r/`, puerto aislado `63457`; clúster detenido y base de pruebas destruida. La regresión mantiene las protecciones SQL B1, pruebas de migración/reversión aisladas, decisiones y concurrencia B2.2-A, y el bloqueo del mecanismo antiguo de cambio individual de nivel. No se ejecutaron pruebas frontend porque no hubo cambios de interfaz. La comprobación en seco no equivale a consultar el estado de migraciones de producción, que no se verificó en esta entrega.

## Punto de parada

No hay nuevas migraciones. No se consultaron ni modificaron datos persistentes de `zona_bloque`; no se crearon progresiones ni decisiones reales. No se ejecutaron traslados, modificaciones de inscripciones, cupos, reservas u horarios. No se realizaron commits ni push.

Se detiene esta entrega para revisión. Quedan fuera la interfaz B2.2-B2, el procedimiento de revisión integral de contextos desactualizados, la gestión pública de excepciones y la ejecución B3.
