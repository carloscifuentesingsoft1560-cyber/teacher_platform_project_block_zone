# Ajustes operativos — Incremento 1: propuestas y traslados

Fecha: **29 de octubre de 2026**. Implementación autorizada a partir de [la revisión de organización](REVISION_ORGANIZACION_REAL_ESCUELA.md). Se implementan únicamente propuestas y traslados; no ascensos globales, participación individual ni cupos por sesión.

## 1. Diagnóstico y resultado

El formulario anterior ofrecía deportista, origen y destino como selecciones independientes. El servicio aceptaba un traslado al mismo grupo como pendiente y dejaba varias comprobaciones para la aprobación. Además, exigía al autor estar asignado al destino, impidiendo propuestas entre profesores/jornadas.

Ahora la consulta, el alta y la aprobación comparten validación de viabilidad. El profesor propone para un deportista de su ámbito actual hacia grupos institucionales compatibles, sin recibir asignación al destino ni permisos para ejecutar el cambio. El formulario depende de deportista/tipo/origen y solo presenta los candidatos devueltos por Django. Se mantienen IDs, claves y relaciones existentes.

## 2. Reglas y validaciones implementadas

### Contexto y propuesta

- Autor profesor activo, con deportista visible mediante inscripciones/reservas y asignaciones vigentes. No se abre el padrón institucional de deportistas.
- Fecha operativa actual. No se implementan propuestas retroactivas ni programadas.
- En traslado/nivel, origen activo, del mismo deportista, vigente y dentro de la asignación del autor; debe tener un tramo previo de al menos un día, como exigía el traslado ejecutable existente.
- Inscripción adicional sin origen que cerrar. No admite un destino con inscripción o reserva solapada del deportista.
- Traslado a grupo distinto, misma disciplina y mismo nivel.
- Cambio de nivel a grupo distinto y nivel diferente, dentro de la misma disciplina. No se inventan ascensos automáticos, reglas de puntuación ni saltos de nivel basados en `orden`.
- Destino y estructura activos, fecha dentro de su periodo, horarios definidos, cupo disponible durante la vigencia y ausencia de incompatibilidades con las demás inscripciones/reservas.
- Duplicados de propuestas pendientes por origen o por deportista/destino: conflicto 409, sin registrar otra pendiente ni producir un error 500.

El cierre del origen se **proyecta** al comprobar el destino: se excluye esa inscripción de la comparación futura, sin modificarla. Así se permite reemplazarla por otro grupo con una franja que coincidía con el origen, siempre que sea compatible con las demás inscripciones. Consultar o proponer no cierra, crea ni modifica inscripciones y no reserva plazas.

Las comprobaciones anticipadas no sustituyen las restricciones de integridad ni la validación de aprobación. Las escrituras de propuesta y auditoría son atómicas, con el protocolo de bloqueo de usuarios ya compartido por la plataforma. La restricción de unicidad sigue actuando como respaldo ante duplicados concurrentes.

### Decisión del coordinador y permisos administrativos conservados

El coordinador activo puede aprobar/rechazar y se revalida su autoridad al decidir. Los **cambios de nivel siguen siendo exclusivos del coordinador**, tanto para aprobación como para rechazo, como en el contrato anterior. El profesor nunca puede resolver ni ejecutar su propuesta.

Para cumplir la restricción de no alterar permisos administrativos, se conservan las facultades que el administrador ya tenía para decisiones administrativas de inscripción adicional/traslado al mismo nivel y cancelación; no se le concede una excepción de promoción deportiva. No se modifican roles, credenciales, permisos de gestión de usuarios ni clases generales de acceso a grupos.

Al aprobar se comprueban nuevamente cuenta/rol del actor, estado pendiente, versión de propuesta, fecha, autor activo, ámbito vigente del autor, origen/versión/estado, estructura del destino, cupos, duplicados, compatibilidad y bloqueo de ascenso parcial. La asignación exigida al profesor es la del origen y su ámbito sobre el deportista; **no se exige que enseñe en el destino**.

El protocolo existente de bloqueo y la transacción protegen propuesta, cierre de origen, alta de continuación, eventos y auditoría. Una aprobación duplicada o una plaza que dejó de estar libre provoca conflicto y no deja un cierre parcial. Se conserva la autoría, justificación, fecha, resolución, responsables e inscripción resultante.

## 3. Consulta institucional mínima, sin acceso a expedientes

Nueva ruta de lectura:

`GET /api/propuestas/destinos/?tipo=traslado&deportista={id}&inscripcion_origen={id}&fecha_efectiva={fecha}`

También admite `tipo=inscripcion` sin origen y `tipo=nivel` con origen, búsqueda `search` y página `page`. La fecha se valida como la fecha operativa actual. Es una consulta específica del profesor que propone; administrador/coordinador conservan sus consultas institucionales generales, sin necesitar esta excepción.

Primero se valida el ámbito del profesor sobre deportista/origen. Solo después se buscan grupos institucionales activos y se filtran por operación, vigencia, cupos y compatibilidad. Se pagina **después** de determinar viabilidad: no se excluyen candidatos válidos por revisar únicamente la primera página de grupos. La búsqueda contempla código, nombre, nivel y nombre del periodo.

Respuesta permitida por destino:

- ID técnico, código y nombre del grupo.
- ID/nombre de nivel, ID/nombre y fechas del periodo.
- Jornada derivada de horarios activos: Entre semana, Sábado, Domingo o Mixta.
- Días y horas, sin información de profesores o alumnos.
- Capacidad y plazas disponibles agregadas para el intervalo autorizado.

No devuelve listas de deportistas, documentos, acudientes, evaluaciones, expedientes, autores de reservas ni datos personales del personal del destino. No crea una relación de asignación docente ni amplía `GrupoVista`, el listado general de grupos, la consulta general de cupos o los querysets de alumnos/historiales. Las rutas ordinarias del grupo ajeno siguen restringidas.

Las propuestas almacenadas incorporan a su respuesta código/nombre/periodo del destino como campos de lectura, sin columnas nuevas. El profesor sigue viendo únicamente las propuestas permitidas por su ámbito vigente; este incremento no abre historia personal después de perder ese ámbito.

## 4. Cambios de nivel y límite del Incremento 2

Los ascensos globales por deportista/disciplina están aprobados institucionalmente, pero **no se implementan aquí**. Si hay otra inscripción efectiva de esa disciplina desde la fecha de operación en adelante, distinta del origen, se bloquea la propuesta nueva de nivel y también la aprobación de una propuesta previa. Se incluyen reservas vigentes e inscripciones futuras; se excluyen tramos históricos terminados y reservas vencidas según sus intervalos.

Mensaje: «El cambio de nivel afecta varias inscripciones de esta disciplina. Requiere el ascenso global del Incremento 2; no se realizará un cambio parcial.»

El bloqueo es conservador: no intenta cerrar automáticamente varias inscripciones ni decidir cuáles conservar. Tampoco revela al profesor el detalle de inscripciones ajenas a su ámbito para explicar el bloqueo. Si una segunda inscripción aparece después de proponer, la aprobación falla y conserva propuesta/origen sin aplicar cambios. No se altera el nivel histórico de ningún grupo.

Con una única inscripción efectiva de la disciplina, el flujo individual existente sigue siendo posible mediante decisión del coordinador. Toda transición global, elección de varios destinos y capacidad por sesión quedan para los incrementos autorizados posteriormente.

## 5. Interfaz

Formulario específico y controlado, construido con Campo, ErrorGestion, BotonesFormulario y el selector buscable existente:

1. Elegir tipo y deportista de los grupos autorizados, con identificación documental enmascarada según el backend docente.
2. Para traslado/nivel, elegir solo inscripciones activas de ese deportista como origen.
3. Consultar destinos compatibles institucionales y seleccionar por código, nombre, nivel, jornada y periodo.
4. Revisar únicamente horarios y disponibilidad agregada; justificar y enviar una propuesta, sin ejecutar una inscripción.

Cambiar deportista limpia origen/destino; cambiar origen o tipo limpia destino. El selector de destinos se crea solo cuando existe el contexto necesario y se reinicia por contexto. Conserva búsqueda/paginación, pero no reutiliza una selección de otra operación. Permite actualizar candidatos tras un conflicto; los errores permanecen visibles sin reenvío automático. No se solicitan IDs escritos manualmente ni se abre la página general del grupo de destino.

La tabla muestra código/nombre/periodo en lugar de depender de «Grupo [id]». Se conserva el diseño institucional y la navegación. Los únicos botones de decisión de nivel visibles corresponden al coordinador, sin sustituir la protección backend.

## 6. Pruebas y resultados

| Verificación final | Resultado |
| --- | --- |
| Backend completo PostgreSQL temporal aislado | **271 aprobadas**, 241 anteriores y 30 nuevas; 35,216 segundos |
| Frontend completo | **88 aprobadas**, 79 anteriores y nueve nuevas; ocho archivos |
| Navegador automatizado con APIs simuladas | **9 recorridos aprobados**, tres roles en 390/768/1366 px |
| Vite build | Aprobado, 70 módulos |
| Comprobación de cambios de modelos en seco | No changes detected; ningún archivo generado |

Backend: traslado entre profesores, jornadas distintas, origen idéntico, nivel idéntico, inscripción adicional duplicada, origen de otro alumno, destinos inactivos/sin horario/fuera de periodo, cupos/horarios al crear y aprobar, privacidad de DTO y rutas ordinarias, pérdida de asignación incluso si el autor sigue viendo al alumno por otro grupo, coordinador relevado, historial y autoría, duplicados, búsqueda, consultas sin escrituras y reservas/inscripciones futuras frente a promoción parcial.

Tres pruebas de concurrencia nuevas en PostgreSQL: dos aprobaciones de la misma propuesta; dos propuestas de personas distintas sobre la última plaza; y dos creaciones para un mismo origen. La suite completa incluye doce casos de concurrencia. Se comprueba que solo una operación gane y que la perdedora no cierre parcialmente su origen.

Se conserva la regresión anterior y se actualiza una expectativa que correspondía a la política sustituida: un destino sin asignación del autor ya no se rechaza por ese solo motivo; se admite la propuesta y se comprueba que la consulta general del grupo ajeno siga denegada. No se retiraron los controles de profesor que no ejecuta ni aprueba, ni los de promoción exclusiva del coordinador.

Frontend: contexto obligatorio, origen filtrado por persona, selección reiniciada, destinos por operación, detalle mínimo, payload con IDs, ausencia de POST a inscripciones/aprobaciones, bloqueo del Incremento 2, conflictos y actualización. El navegador verificó el flujo de propuesta con POST **interceptado y simulado**, y que los selectores no desborden en móvil. No hubo errores JavaScript.

Los fixtures se crearon únicamente en bases de pruebas. Las pruebas transaccionales revierten/limpian su base temporal, y el clúster se detuvo al finalizar. Evidencia privada de la última ejecución: `respaldos/pruebas_fase3_6zca5gpb/`. No se instalaron dependencias nuevas.

## 7. Conservación real y migraciones

**No se necesitan migraciones.** No se modificaron modelos ni se generaron o aplicaron archivos de migración. El plan real sigue sin operaciones pendientes.

Antes de implementar se capturó una referencia de solo lectura: `respaldos/ajustes_propuestas_antes_20261029T210730Z.json`, con conteos/SHA-256 de las 32 tablas, sin filas personales. La comprobación posterior en una transacción PostgreSQL READ ONLY confirmó destino `zona_bloque/public` e igualdad exacta de esas 32 tablas, incluidas inscripciones, propuestas, auditoría, usuarios y asignaciones.

GET reales mediante APIClient con cuentas existentes autenticadas solo en memoria: listas de propuestas y resúmenes de administrador/coordinador respondieron 200. La consulta de destinos con un contexto docente existente respondió 200 y **cero destinos compatibles**. No se añadieron grupos para forzar un ejemplo positivo: los casos entre profesores/jornadas se probaron con datos aislados. No se enviaron POST de negocio a zona_bloque ni se crearon sesiones persistentes.

No se modificaron inscripciones existentes, credenciales o roles institucionales. No hubo commits ni push.

## 8. Inventario de archivos

Creados:

- `backend/inscripciones/compatibilidad_propuestas.py`: validación compartida de contexto/viabilidad, bloqueo de ascenso parcial y DTO mínimo de destino.
- `backend/inscripciones/test_propuestas_traslados.py`: treinta pruebas funcionales, privacidad y concurrencia.
- `frontend/src/componentes/FormularioPropuesta.jsx`: formulario dependiente con información mínima de destino.
- `frontend/src/pruebas/PropuestasTraslados.test.jsx`: nueve regresiones de contexto, payload, privacidad y errores.
- `frontend/pruebas/navegador-propuestas.cjs`: QA aislada por rol y tamaño.
- Este documento.

Modificados:

- `backend/inscripciones/servicios.py`: propuesta anticipadamente validada, revalidación del autor/origen y bloqueo de aprobación parcial; manejo de pendientes concurrentes.
- `backend/inscripciones/views.py`: consulta de destinos y FK institucional para proponer, sin cambiar el queryset de grupos ni permisos administrativos.
- `backend/inscripciones/serializers.py`: metadatos de destino de solo lectura en propuestas.
- `backend/inscripciones/tests.py`: actualización de la regla institucional de destino entre profesores, manteniendo prueba de privacidad general.
- `frontend/src/paginas/Propuestas.jsx`: integración del formulario y presentación legible de destinos.
- `frontend/src/componentes/SelectorCatalogo.jsx`: función opcional para etiquetar registros; comportamiento predeterminado de los filtros existentes intacto.
- `frontend/src/pruebas/Fase3.test.jsx`: respuesta simulada de candidatos y espera de carga del selector, sin suprimir casos anteriores.
- README y matriz de permisos: estado, ampliación específica y resultados.

## 9. Limitaciones y criterios visuales

- Cupos continúan calculándose por grupo/intervalo con las reglas actuales. La decisión institucional de participación individual y cupos por sesión requiere un incremento posterior; no se implementa ni se simula aquí.
- Las propuestas deben resolverse en su fecha operativa. Una propuesta vencida permanece en historial y deberá rechazarse/cancelarse de forma auditada; no se programa ni elimina automáticamente.
- Un traslado necesita al menos un día previo de inscripción. Si la inscripción ficticia real se creó hoy, el bloqueo temprano es esperado: no se cambian fechas reales para sortearlo.
- La consulta de candidatos no reserva plazas. Entre consulta, envío y aprobación pueden cambiar horarios, cupos o permisos; el resultado definitivo se decide transaccionalmente.
- No se exige una asignación ficticia al destino. La gestión real de su plantilla sigue en el módulo correspondiente; no se crean profesores ni asignaciones por proponer.
- La búsqueda de candidatos calcula viabilidad antes de paginar. Si crece significativamente el catálogo, medir y optimizar consultas manteniendo la misma validación; no truncar silenciosamente candidatos a la primera página.
- La coexistencia de varias inscripciones de una disciplina ante cambio de nivel está bloqueada, no resuelta globalmente. Las propuestas históricas afectadas conservan su estado pendiente ante un intento de aprobación fallido; su resolución requiere gestión o el Incremento 2.

Comprobación visual con el usuario:

1. Profesor: abrir `/profesor/propuestas`, crear propuesta y escoger tipo/deportista; verificar que no se ofrece destino antes de disponer del origen cuando corresponde.
2. En un entorno con oferta compatible existente, comprobar código/nombre/nivel/jornada/horarios/periodo y disponibilidad del destino, incluso si lo dirige otro profesor. Si no hay oferta compatible, el selector vacío es un resultado válido; no crear datos ficticios persistentes para demostrarlo.
3. Cambiar persona/origen/tipo y comprobar limpieza del destino. No deben aparecer origen idéntico ni niveles incompatibles.
4. Revisar que la información de destino no incluya enlaces a alumnos o expedientes y que el profesor no tenga botones administrativos.
5. Coordinador: revisar propuestas y mensaje de bloqueo de nivel si hay varias inscripciones; el administrador no obtiene decisión pedagógica de nivel por esta ampliación.
6. Cualquier envío o aprobación de una propuesta real será una actuación institucional explícita posterior; este encargo no realizó esos cambios. Los ensayos positivos con datos ficticios ya están cubiertos por las pruebas aisladas.

**Punto de parada:** Incremento 1 terminado para revisión visual. No iniciar el Incremento 2, los planes de participación, la malla, sesiones, asistencia, evaluaciones o ClimbVision-AI sin instrucciones posteriores.


## Cierre del Incremento 1: mensajes de integridad del historial (2026-10-29)

Se conserva sin cambios la comparación de fechas y la restricción de base de datos `inscripcion_fechas_validas`. No se incorporan rectificaciones ni retroactividad.

El mensaje compartido distingue **El traslado al mismo nivel** de **El cambio de nivel**, seguido de: «no puede ejecutarse el mismo día del ingreso por integridad del historial. La fecha efectiva debe ser posterior a la fecha de ingreso y la inscripción debe estar activa.» La consulta de destinos, la creación y la aprobación utilizan el mismo mensaje; el servicio de ejecución conserva esa coherencia.

Archivos modificados en este cierre:
- `backend/inscripciones/servicios.py`: función compartida de mensajes y uso en ejecución.
- `backend/inscripciones/compatibilidad_propuestas.py`: mensaje según operación, sin cambiar condiciones.
- `backend/inscripciones/test_propuestas_traslados.py`: cuatro regresiones nuevas, con subcasos para ambas operaciones.
- Este documento.

Las regresiones verifican consulta y creación rechazadas sin generar pendientes; aprobación rechazada sin ejecutar; suspensión y reanudación el mismo día conservando fecha y estado; y protección del servicio ejecutable sin cerrar el origen. Los ajustes de fechas de las pruebas pertenecen exclusivamente a sus fixtures aislados.

Verificación final:
- `python scripts/pruebas_postgresql_aisladas.py`: **275 pruebas aprobadas**, comprobaciones Django sin incidencias. Clúster efímero independiente, puerto 62185; sin conexión a `zona_bloque`.
- `npm.cmd test` en `frontend`: **88 pruebas aprobadas**, ocho archivos.
- La primera ejecución detectó errores en las aserciones nuevas y en la sustitución del mensaje; se corrigieron antes de la suite final aprobada.

No se modificaron modelos, permisos, migraciones ni datos persistentes de `zona_bloque`. No se hicieron commits ni push. Pendiente repetir la comprobación visual; no iniciar el siguiente incremento.
