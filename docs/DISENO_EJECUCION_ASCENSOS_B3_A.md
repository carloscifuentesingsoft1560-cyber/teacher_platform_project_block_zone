# Ejecución administrativa de ascensos — Diseño B3-A

Fecha: 30 de octubre de 2026. Estado: propuesta para revisión; **no autoriza implementación ni ejecución**.

## 1. Resumen ejecutivo

La decisión pedagógica institucional ya está separada de las inscripciones. No existe todavía ejecución B3: el traslado ordinario cambia una sola inscripción y no puede utilizarse como motor de ascensos mediante su antiguo parámetro de cambio de nivel. B1 prohíbe `estado_plan='ejecutado'` en PostgreSQL.

La ejecución requiere un plan operativo versionado que contemple todas las inscripciones relevantes del deportista y disciplina, una proyección conjunta de sus movimientos y resultados administrativos auditados. No basta ejecutar en un bucle los traslados existentes ni cambiar el estado del plan.

Se comparan dos alternativas sin adoptarlas: A, lote obligatorio atómico; B, ejecución progresiva expresamente autorizada por inscripción. Se recomienda someter primero A a decisión institucional por su menor complejidad, con pendientes explícitos fuera de ejecución, y evaluar B solo si la disponibilidad de jornadas exige movimientos escalonados. Esa recomendación **no es una regla aprobada**. La elección afecta estados, permisos, tratamiento de excepciones y alcance de las migraciones futuras.

Bloqueos principales a resolver antes de programar: preparación posterior a la aprobación actualmente prohibida; evidencia de contexto que queda obsoleta con el tiempo; ausencia de resultados e idempotencia de ejecución; tratamiento no definido de reservas/futuras; exclusividad indefinida de progresiones aprobadas, que impediría el siguiente ascenso.

## 2. Estado actual verificado en archivos

### Fuentes y límites de esta revisión

Se inspeccionaron los documentos `DISENO_ASCENSOS_INSTITUCIONALES_INCREMENTO_2.md`, `IMPLEMENTACION_ASCENSOS_INCREMENTO_2_B1.md`, `IMPLEMENTACION_ASCENSOS_B2_2_A.md`, `IMPLEMENTACION_PLAN_ASCENSOS_B2_2_B1.md` e `IMPLEMENTACION_ASCENSOS_B2_2_B2.md`; modelos, servicios, consultas de revisión y migración B1 de `backend/inscripciones/`; modelos/validaciones de organización y pruebas de cupos, reservas, traslados, planes, decisiones y concurrencia.

Los documentos iniciales describen etapas históricas: por ejemplo, el diseño inicial antecede al bloqueo del tipo antiguo `nivel` y la cabecera de implementación B1 antecede a su aplicación real. Prevalecen el código actual y las decisiones posteriores del usuario. La aplicación de B1 y la verificación visual docente–coordinador se toman del contexto confirmado; no se consultó PostgreSQL para recertificarlas.

Esta etapa no ejecutó pruebas ni comandos Django, ni consultó bases de datos. Las 395 pruebas backend y 121 frontend/seis del cliente HTTP son antecedentes documentados, **no resultados nuevos de B3**. Solo se crea este documento.

### A. Traslado ordinario: cambios efectivos

En `servicios.py`, `trasladar` abre una transacción, llama a `contexto`, bloquea/relee el origen, verifica `version` y llama a `trasladar_bajo_bloqueo` con fecha de hoy. Este último:

1. Exige origen activo, fecha posterior al ingreso y exactamente la fecha local actual.
2. Exige otro grupo de la misma disciplina; por defecto conserva el nivel.
3. Cierra el origen: `fecha_salida`, `estado='finalizada'`, `causa_salida='traslado'`, actor y versión incrementada.
4. Valida y crea otra `Inscripcion` mediante `crear_bajo_bloqueo`, con ingreso en esa fecha y `inscripcion_anterior=origen`; registra evento de ingreso y `traslado_origen`, además de auditoría.

El destino obtiene nueva PK/version inicial; el deportista mantiene identidad y UUID. La relación `inscripcion_anterior` es **OneToOne**: un origen tiene como máximo una continuación. Una fusión de dos orígenes en una sola inscripción no está modelada y no debe improvisarse. No se reescribe el grupo/nivel del registro histórico.

`permite_nivel=True` llama primero a `bloquear_nivel_antiguo('nivel')`: **la vía está deshabilitada**, también para una llamada interna. B3 necesita un servicio institucional específico, no eliminar globalmente ese bloqueo. `resolver` conserva inscripción adicional y traslado al mismo nivel; al aprobar revalida autor, versión de origen y fecha operativa y deja `Propuesta` aplicada con inscripción resultante, actor, resolución y nueva versión. No debe convertirse en el decisor B3.

### B. Cupos, reservas y ocupación futura

`intervalo` representa ocupación mediante `[fecha_ingreso, fin_exclusivo)`, limitada por `periodo.fecha_fin + 1 día`. Para suspendidas usa una reserva no liberada hasta su vencimiento inclusivo; sin reserva, su intervalo queda vacío. `ocupacion_maxima` calcula el máximo de ocupación sobre el intervalo solicitado mediante entradas/salidas ordenadas; una salida y una entrada el mismo día no suman dos plazas. Incluye altas futuras cuando sus intervalos coinciden.

`validar_nueva` comprueba estructura activa, fechas dentro del periodo, horarios activos, capacidad máxima durante la vigencia, duplicidad y cruces con otras inscripciones del deportista. Las reservas se incorporan mediante sus intervalos. `cruzan` usa el día semanal y franjas activas, dentro de la intersección de fechas; horarios contiguos no se solapan. No existe cupo por sesión ni participación individual por días.

`GET /api/inscripciones/cupos/` distingue ocupación actual y máxima, reservas vigentes y disponibilidad; no libera reservas al consultar. Una disponibilidad de consulta no constituye garantía al ejecutar.

**Efecto lateral relevante:** `contexto` invoca `liberar_vencidas_bajo_bloqueo`, que procesa reservas vencidas **de toda la base**, no solo del deportista. Puede liberar reservas, finalizar suspendidas con salida `vencimiento+1`, incrementar versiones y crear eventos. No es una utilidad de lectura ni una entrada apropiada para una simulación B3. Debe evitarse ese alcance implícito en una ejecución institucional acotada; cualquier limpieza persistente se diseñará separadamente o se limitará y auditará con autorización.

El cálculo actual responde a las inscripciones y reservas en su estado actual: no es una reconstrucción completa de ocupación histórica. Por ejemplo, una suspendida usa como inicio el ingreso de la inscripción, y una reserva ya liberada deja de aportar su intervalo mediante ese cálculo. Reportes históricos B3 deberán usar eventos/evidencias, no recalcular el pasado solamente con los estados presentes.

### C. Fechas y versiones

`inscripcion_fechas_validas` exige salida estrictamente posterior al ingreso; `inscripcion_cierre_coherente` liga estado, salida y causa. El mismo día no puede crearse un tramo de duración cero. El fin del periodo es inclusivo, mientras la salida de inscripción es exclusiva. B3 debe definir si se permite cerrar el día posterior al fin del periodo; no deducirlo de la ausencia de un CHECK adicional.

Suspender, reanudar, retirar, liberar una reserva vencida y trasladar incrementan la versión de inscripción. Reanudar no cambia su ingreso: una reanudación hoy no impide por sí sola trasladar si el ingreso original es anterior; si ambos son hoy, continúa prohibido cerrar hoy. La propuesta institucional tiene versión propia y cada afectación conserva versión/situación observadas. Grupos, horarios y periodos no tienen esa misma versión de agregado; la evidencia JSON de B2 compara estructura y fechas.

### D. Bloqueos y protecciones existentes

Los servicios operativos bloquean usuarios globalmente y releen permisos; luego deportista/grupos y las filas específicas. B1/B2 bloquean usuarios, progresión, deportista y, mediante `bloquear_contexto`, inscripciones originales/pertinentes, grupos de origen/destino y reservas ordenados por ID. El bloqueo global de usuarios serializa escritores institucionales aunque sus otros órdenes difieran. No debe eliminarse sin un diseño coordinado de todos los servicios.

Las pruebas existentes incluyen último cupo con conexiones independientes, altas incompatibles concurrentes del mismo deportista, propuestas/decisiones/preparaciones duplicadas, desactivación del coordinador, rollback de traslado sin cupo y protección SQL de eventos/excepciones. No prueban todavía ejecución institucional B3 ni una proyección de varios movimientos.

### E. B1/B2: preparación no equivale a ejecución

`actualizar_plan` deriva `pendiente` cuando todas las disposiciones son `revisar`, `preparado` cuando todas son `reubicar`, y `parcial` en las restantes combinaciones revisadas. **`parcial` no significa parcialmente trasladado.** `AfectacionInscripcion` no tiene inscripción resultante, fecha ni estado de ejecución.

`disponer_inscripcion` permite preparar solo si la decisión está pendiente. `decidir_progresion` exige disposiciones expresas antes de aprobar; puede aprobar con reubicaciones pendientes. `relevantes` incluye abiertas de la disciplina con periodo no terminado, también suspendidas sin reserva y futuras; el periodo de cabecera no limita el conjunto a un único ciclo.

`advertencias_revision` compara el conjunto actual y evidencia de creación/destinos; trata una decisión ya resuelta como bloqueo de revisión. No es un verificador de ejecución de progresiones aprobadas. El primer traslado cambiaría el conjunto y versiones; reutilizar sin más esta función bloquearía los siguientes movimientos de una alternativa B.

### F. Restricciones SQL B1 que condicionan B3

La migración aplicada `0002_progresioninstitucional_eventoprogresion_and_more` contiene 17 operaciones, cuatro funciones y seis triggers en `public`. No se propone editarla.

- El CHECK **`ascenso_plan_valido`** admite exclusivamente `pendiente`, `parcial`, `preparado`; bloquea `ejecutado` por ORM o SQL, incluso con decisión aprobada. El modelo refleja la misma lista. No existe actualmente un trigger de ejecución que se pueda simplemente «activar».
- `ascenso_decision_coherente` exige responsable/fecha/resolución para decisiones resueltas. `ascenso_abierto_unico` impide otra progresión del mismo deportista/disciplina mientras la anterior esté pendiente **o aprobada**, sin distinguir ejecución.
- `zdb_validar_ascenso_b1` mantiene identidad de progresión/afectación y decisión registrada; valida deportista, disciplina, niveles, periodo y destinos. No deben sustituirse los FK originales por inscripciones resultantes.
- `zdb_historial_ascenso_inmutable` bloquea UPDATE/DELETE de eventos; `zdb_nivel_ascenso_estable` impide cambiar la disciplina de niveles referenciados.
- La excepción conserva originales inmutables. Su revocación exige coordinador activo y evento coincidente verificado por `zdb_revocacion_ascenso_auditada`, con trigger diferido. Una ejecución administrativa de otro rol no puede apropiarse de esa facultad.
- Funciones `SECURITY INVOKER`, referencias explícitas `public`, `search_path=pg_catalog`; deben preservarse esas garantías en futuras migraciones.

## 3. Reglas institucionales confirmadas

Son requisitos de entrada, no alternativas: decisión pedagógica independiente; aprobación exclusiva del coordinador activo; profesores sin ejecución; disposiciones expresas para todas las inscripciones pertinentes; inclusión de activas, suspendidas/reservas y futuras; continuidad temporal solo con excepción expresa y vencimiento; revalidación de cupos al ejecutar; ningún traslado incompatible ni parcial inadvertido; conservación íntegra de identidad e historia.

Una progresión puede quedar aprobada con reubicaciones pendientes. Esto no decide si es posible ejecutar un subconjunto ni si la falta de destino autoriza continuidad ordinaria. La prohibición de cerrar el mismo día del ingreso se mantiene por la decisión institucional previa y el CHECK existente. No se incluyen retroactividad, rectificaciones, sesiones, malla ni cupos por sesión.

## 4. Brechas y riesgos

| Riesgo | Gravedad | Tratamiento propuesto |
| --- | --- | --- |
| Bucle de traslados valida contra orígenes que el mismo lote cerrará o permite mezclas arbitrarias con un booleano | Alta | Proyección completa de intervalos finales y servicio exclusivo B3 |
| Reintento tras perder respuesta duplica movimientos | Alta | Clave idempotente y resultados persistidos en la misma transacción |
| Plan aprobado no editable, evidencia envejecida o destino sin cupo | Alta | Revisiones administrativas versionadas, sin reabrir/reemplazar la aprobación pedagógica |
| Una aprobación ocupa indefinidamente la unicidad e impide otro ascenso | Alta | Ciclo de expediente separado y cierre explícito; no reinterpretar «rechazada» para liberar unicidad |
| Reservas/futuras transferidas como si fueran activas | Alta | Política expresa; bloqueo conservador hasta aprobarla |
| Liberación global de vencidas por `contexto` | Alta | No reutilizar esa entrada sin limitar sus efectos y aprobar el cambio |
| SQL/ORM ordinario marca ejecución sin resultados | Alta | Integridad nueva entre autorización, lote, detalles y eventos; sin desactivar protecciones |
| Continuidad/excepción vencida ignorada durante semanas | Alta | Conciliación informativa y revisión institucional, nunca traslado/cierre automático |
| Estado `parcial` ambiguo o reporte que interpreta aprobado como nivel adquirido | Alta | Dimensiones separadas para preparación, ejecución y reconocimiento pedagógico |
| Bloqueo global de usuarios y contención de DDL | Media | Operaciones cortas, orden estable y timeouts; revisión de escalabilidad independiente |
| Informes históricos recalculados desde horarios/reservas actuales | Media | Evidencias temporales mínimas e historial; no afirmar que existe calendario histórico completo |

## 5. Comparación de alternativas

| Criterio | A — lote obligatorio atómico | B — progresiva por inscripción |
| --- | --- | --- |
| Unidad | Todas las reubicaciones obligatorias del plan vigente | Una fila o lote expresamente autorizado dentro del plan integral |
| Integridad | Todos los movimientos del lote se confirman juntos | Cada movimiento es atómico; el expediente puede quedar ejecutado en parte |
| Falta de destinos | Ninguna reubicación obligatoria se realiza hasta completar viabilidad | Se puede avanzar solo si las restantes tienen disposición y continuidad institucionalmente válidas |
| Disponibilidad | Más espera y posibles pérdidas de plazas antes del lote | Mayor flexibilidad entre jornadas, con vigilancia de pendientes |
| Horarios/cupos | Simulación final conjunta relativamente acotada | Simulación del estado posterior a cada paso y del remanente, incluidas excepciones y reservas |
| Seguridad | Menos superficies de transición | Más autorizaciones, revisiones, caducidades y riesgo de mezcla de niveles |
| Concurrencia | Bloqueos de todos los movimientos y destinos del lote | Mismos controles del agregado, aunque se ejecute una fila; no ignorar las demás |
| Auditoría | Una ejecución con varios resultados | Varias ejecuciones y vínculos inequívocos por afectación/revisión |
| Fallo | Rollback del lote entero | Rollback de la petición actual; movimientos ya confirmados permanecen históricos |
| Recuperación | Reintento idempotente sencillo | Conciliación entre resultados previos, plan vigente y pasos aún autorizados |
| Complejidad | Menor, pero requiere definir qué significa obligatorio | Mayor; requiere gobernanza de continuidad y cambios de plan |

En A no se debe llamar «completo» a ejecutar únicamente las filas que casualmente tengan destino: el conjunto obligatorio y la disposición de las otras filas deben haberse aprobado explícitamente. Una reserva, futura o continuidad no se considera trasladada para completar un contador.

En B una inscripción pendiente no equivale a excepción. Si el resultado deja al deportista en niveles distintos, su permanencia debe estar expresamente respaldada por la política y excepciones aplicables; no basta la aprobación pedagógica. La ausencia de grupo superior no autoriza por sí sola esa mezcla. **Ambas alternativas quedan pendientes de decisión institucional.**

## 6. Matriz de escenarios

Comportamientos de B3 propuestos, condicionados a la elección de alternativa y políticas indicadas; ninguno está implementado.

| Caso | A | B / salvaguarda común |
| --- | --- | --- |
| 1. Una inscripción y destino compatible | Ejecutar el lote único tras revalidar | Ejecutar esa fila; conservar origen y resultado |
| 2. Dos inscripciones con destinos compatibles | Ambas en una transacción; validar también destinos entre sí | Uno o dos pasos explícitos, solo si el estado intermedio está autorizado |
| 3. Dos inscripciones, solo un destino disponible | Bloquear lote obligatorio; mantener aprobado pendiente | No avanzar silenciosamente: exigir disposición y legitimidad de la permanencia de la otra; si no existen, bloquear |
| 4. Sin cupo al ejecutar | Conflicto sin movimientos | Conflicto para petición; no alterar ejecuciones anteriores ni reservar automáticamente |
| 5. Cruce horario sobrevenido | Bloquear todo el lote | Bloquear el paso si su estado final/intermedio es incompatible con otras actividades |
| 6. Suspendida con reserva | Incluirla explícitamente; no reactivarla ni transferirla por defecto | Mantener pendiente hasta definir destino de reserva o esperar reanudación; política pendiente |
| 7. Inscripción futura | No cerrar hoy ni usar traslado de activa | Planificar expresamente; modificación/sustitución futura necesita política y modelo temporal, sin tramo cero |
| 8. Excepción vigente | Puede justificar continuidad fuera del lote obligatorio según política aprobada | Puede justificar estado intermedio; no crea cupo ni extiende fechas |
| 9. Excepción vencida | Advertencia bloqueante de ejecución si sustenta el plan | No ejecutar pasos dependientes; revisión coordinadora; sin cierre o expulsión automática |
| 10. Fecha igual al ingreso | Rechazar el movimiento y el lote | Rechazar la fila; no cambiar el ingreso para sortear el CHECK; reanudación usa ingreso original |
| 11. Otra disciplina | Rechazar siempre | Igual; no reinterpretar como nueva disciplina o evaluación |
| 12. Grupo/periodo inactivo | Rechazar destino; revisar plan | Igual; origen inactivo inesperado requiere conciliación, no reactivación implícita |
| 13. Dos operadores, mismo plan | Una ejecución lógica; reintento idéntico recupera resultado | Serialización del agregado y unicidad por fila; ninguna doble continuación |
| 14. Inscripción cambió tras aprobación | Bloquear ejecución y exigir revisión versionada | Diferenciar cambios previstos por ejecuciones anteriores de cambios externos; bloquear estos últimos |
| 15. Interrupción dentro de transacción | Rollback de cierres, altas, resultados y eventos | Rollback de la petición, no de pasos confirmados anteriormente |
| 16. Aprobado pendiente semanas | Conciliación muestra antigüedad, cambios y faltantes | Además muestra pasos realizados y continuidad pendiente/vencida; no caducar aprobación por inventar plazo |
| 17. Historia origen/destino | Origen finalizado y nueva inscripción enlazada, con fecha/actor y ejecución | Igual por paso; nunca cambiar el grupo del registro anterior |
| 18. Cambian cupos/reservas después | Servicios ordinarios validan ocupación real resultante; no se mantiene cupo ficticio de origen | Igual; movimientos ejecutados quedan históricos, no se deshacen automáticamente |

## 7. Propuesta técnica para aprobar antes de implementar

### Dimensiones y estados separados

Conservar `estado_decision` y su resolución inmutable. Conservar `estado_plan` como **preparación** B1, sin reutilizarlo para progreso administrativo. Se propone añadir una dimensión de ejecución independiente: `pendiente`, `en_revision`, `parcial` (solo alternativa B), `completa`; y un cierre explícito del expediente separado. Un bloqueo de validación puede ser resultado de consulta o intento, sin cambiar silenciosamente la decisión a rechazada.

Por fila se proponen resultados `pendiente`, `ejecutada`, `diferida`; una disposición no es un resultado. «Diferida» exige razón/política expresa y no significa realizada. Un fallo revertido no deja una fila ejecutada. `en_curso` solo tendría sentido como estado transaccional o proceso persistente recuperable; se recomienda operación síncrona corta inicialmente, sin filas eternamente en curso tras caída del proceso.

Transiciones propuestas: aprobado + plan vigente → validación → ejecución A completa o B parcial/completa; conflicto → permanece en el estado anterior con diagnóstico; revisión administrativa → nueva revisión de plan, sin tocar resolución. Una modificación de disciplina/nivel objetivo es nueva decisión pedagógica, no revisión de destino. El criterio de cierre con diferidas/excepciones debe acordarse antes de liberar unicidad.

### API mínima propuesta — no existente

| Endpoint conceptual | Finalidad |
| --- | --- |
| `GET /api/ascensos/{id}/ejecucion/` | Estado operativo, resultados previos y pendientes, sin mutaciones |
| `POST /api/ascensos/{id}/validar-ejecucion/` | Simulación sin escrituras: versión de progresión/revisión, fecha propuesta; devuelve bloqueos por fila y del conjunto; no reserva plazas |
| `POST /api/ascensos/{id}/revisiones-plan/` | Revisión explícita de un plan aprobado: motivos, disposiciones, nuevos destinos y cambios detectados, con versión y autoridad por aprobar |
| `POST /api/ascensos/{id}/ejecuciones/` | Ejecutar la revisión vigente autorizada, con versión observada, fecha, motivo y clave idempotente; en B, conjunto explícito de filas permitido por el plan |

El servidor deriva actor, timestamps, estados finales, versiones de inscripciones y resultados; no acepta estados `ejecutada` impuestos por cliente. A no acepta un subconjunto arbitrario; B exige validar su autorización contra el plan completo. No exponer CRUD de resultados ni un booleano público `permitir_nivel`. GET nunca llama a `contexto`, libera reservas ni confirma validaciones.

Errores propuestos: `400` entrada incoherente, `403` autoridad insuficiente/perdida, `404` fuera de ámbito, `409` versión/contexto/cupo/conflicto o clave reutilizada con otro contenido. Mensajes por fila comprensibles, sin documentos personales ni trazas SQL. Un timeout no debe interpretarse como fracaso definitivo: consultar resultado por clave antes de reintentar. Una respuesta de simulación siempre avisa que no garantiza disponibilidad.

### Idempotencia y unidad de trabajo

Proponer clave idempotente única por progresión con huella canónica del comando (revisión, versión, filas, fecha y motivo), actor y resultado. Misma clave/contenido devuelve el resultado confirmado, previa comprobación de acceso actual; clave con otro contenido da conflicto. Una fila ejecutada en un intento anterior no vuelve a cerrarse aunque cambie la clave. Distinguir retry legítimo de una segunda ejecución incompatible.

La confirmación, resultados y clave consumida se guardan dentro de la misma transacción. Si se necesita conservar intentos fallidos, usar registro operativo mínimo separado tras rollback, sin fotografiar un estado intermedio como confirmado. No es obligatorio persistir errores de simulación ni datos sensibles.

### Transacción y proyección conjunta

1. Validar forma del comando; abrir transacción; bloquear usuarios y releer autoridad de ejecución.
2. Bloquear progresión, revisión operativa vigente y deportista; confirmar aprobación pedagógica intacta, versión e idempotencia.
3. Identificar todas las inscripciones pertinentes y resultados ya confirmados, incluidas actividades de otras disciplinas que puedan cruzarse. Bloquear inscripciones/afectaciones, grupos de origen/destino y reservas en un orden documentado compatible con los demás servicios.
4. Reconstruir evidencia actual, niveles consecutivos por `orden`, estructura/periodos/horarios activos y versiones. Diferenciar cambio externo, envejecimiento temporal y efecto propio de ejecución; cambios materiales requieren revisión explícita, no reemplazar la foto original.
5. Construir en memoria la proyección: cierres propuestos, altas, permanencias, reservas y futuras. Comprobar ventanas temporales, duplicaciones, nivel/disciplina, excepciones y compatibilidad del estado final (e intermedio en B).
6. Calcular cupo máximo sobre el intervalo completo, considerando inscripciones externas, reservas válidas, altas futuras y **todas las altas del lote**. No sumar solamente ocupación de hoy ni excluir globalmente todos los orígenes sin cortar sus intervalos en la fecha efectiva. Detectar destinos repetidos y no fusionar inscripciones automáticamente.
7. Solo con proyección válida, cerrar orígenes autorizados y crear continuaciones; guardar resultados enlazados, nuevas versiones y auditoría, sin utilizar la vía antigua deshabilitada.
8. Derivar estado de ejecución desde resultados/disposiciones; confirmar con restricciones y eventos coherentes. Cualquier excepción revierte todo el lote de esa petición.

Reutilizar algoritmos puros `intervalo`, `cruzan` y barrido de ocupación cuando su contrato sea suficiente; extraer un validador de proyección explícito, sin relajar `validar_nueva` globalmente. Ejecutar secuencialmente el traslado ordinario podría ver cruces con orígenes aún abiertos del propio lote. No debe sortearse con exclusiones arbitrarias ni desactivando restricciones.

Mantener inicialmente el bloqueo global de usuarios. Si se refina después, habrá que coordinar altas, horarios, capacidad, reservas, relevos y propuestas; `select_for_update` de filas existentes por sí solo no bloquea nuevas inscripciones ni todos los cambios de catálogos. Timeouts locales prudentes, transacciones breves, sin llamadas externas ni espera humana bajo bloqueo. Reintentos de deadlock deben conservar idempotencia y nunca forzar sesiones ajenas.

### Fechas, reservas, futuras y excepciones

Como primer alcance técnico se sugiere ejecución de activas con fecha de hoy y posterior al ingreso, manteniendo suspendidas/futuras expresamente pendientes hasta aprobar sus políticas. Esta limitación es propuesta, no una exclusión del análisis global. No prometer ejecución completa si quedan esas obligaciones.

Transferir una suspensión no equivale a reanudar: habría que definir vencimiento, autorización, ocupación de origen/destino e historia de liberación/nueva reserva, sin duplicar ni extender cupo tácitamente. Sustituir una alta futura no puede pasar por cierre anterior o igual al ingreso. Programar una ejecución futura también plantea si la plaza se reserva desde la planificación o solo al ejecutar; requiere decisión, no una tarea automática ahora.

Las excepciones mantienen su autoridad coordinadora. Registrar ejecución por administrador, si se autoriza, no lo habilita a conceder o revocar excepciones. Su vencimiento no ejecuta por sí mismo retiros ni cambios; conciliación y decisión expresa deben resolverlo.

### Conciliación y semanas pendientes

Proponer consulta de conciliación de solo lectura por antigüedad, próximos vencimientos, reservas/futuras, destinos faltantes, niveles mezclados y discrepancias con revisión autorizada. Mostrar la fecha de aprobación y último examen, sin inventar un plazo de caducidad universal. Las notificaciones o tareas periódicas serían otro alcance autorizado, nunca ejecución automática.

Un plan aprobado puede conservar su resolución durante semanas; eso no garantiza vigencia operativa. Revisar destinos y disposiciones con una revisión nueva enlazada a la anterior, conservando evidencia de creación/aprobación. No reutilizar directamente los booleanos de `advertencias_revision`, que hoy bloquean cualquier propuesta resuelta. La pérdida de asignación del proponente después de la aprobación no debe borrar su decisión: si obliga a ratificación o solo a advertencia queda pendiente de política.

## 8. Datos y migraciones potenciales

Modelo conceptual, **sin crear clases ni archivos de migración**:

- `RevisionPlanAscenso`: progresión, número/versión, revisión precedente, autor/fecha/motivo, autoridad de validación y foto de inscripciones/disposiciones/condiciones examinadas. Detalles versionados para nuevos destinos o altas relevantes, sin reemplazar las afectaciones originales protegidas.
- `EjecucionAscenso`: progresión/revisión, actor, fecha efectiva y de registro, clave idempotente, huella del comando y resultado del lote.
- `ResultadoEjecucionAscenso`: ejecución, fila de revisión/afectación, origen, inscripción resultante y datos mínimos de transición; identidad histórica protegida. Una continuación por origen y una ejecución confirmada por obligación, no una unicidad indiscriminada que impida mantener intentos no consumados.
- Dimensión de estado operativo y ciclo de expediente, preferiblemente derivable de resultados; si se materializa, restringir consistencia. No agregar un campo de nivel institucional efectivo sin política aprobada.

Unidades de migración posibles: tablas/índices/FK `PROTECT` de revisiones/ejecuciones; unicidades de versión e idempotencia; coherencia de origen/destino/progresión y decisión aprobada; protección de resultados/eventos contra reescritura; control SQL de estados operativos frente a escrituras ordinarias que omitan servicios. Definir eventos coincidentes dentro de la misma transacción sin habilitar SQL arbitrario como autoridad humana.

Dos opciones para el CHECK actual: ampliar controladamente `estado_plan` con nuevas restricciones de ejecución, o **conservarlo como preparación y mantener prohibido `ejecutado`, creando estado de ejecución separado**. Se recomienda estudiar la segunda por claridad y para que `actualizar_plan` no sobrescriba ejecución; no queda adoptada. Aun así, hacen falta migraciones para nuevas entidades y para el ciclo de exclusividad.

`ascenso_abierto_unico` necesita diseño explícito de cuándo el expediente deja de estar abierto, sin perder el historial de decisión aprobada. Un CHECK/índice condicionado a un campo de ciclo del mismo agregado es una posibilidad; no basarlo en un JOIN no admitido en el predicado del índice. No liberar unicidad al completar solo un subconjunto o vencer una excepción. Definir también el nivel de origen del siguiente ascenso, pues hoy se deriva de una inscripción y no hay nivel efectivo independiente.

Compatibilidad: mantener las cuatro tablas B1 y sus IDs, decisiones y eventos; conservar FK de referencia a origen, no sustituir por resultados. No backfill automático que marque aprobados históricos como ejecutados. Expedientes existentes entran a revisión operativa explícita cuando corresponda. Las APIs B2 conservan su significado y las revisiones aprobadas utilizarán un servicio distinto de la preparación pendiente actual.

Una migración futura será nueva y auditada, nunca modificación de `0002` aplicada. Exigir plan SQL, respaldo con SHA-256 y restauración aislada, aislamiento de pruebas, conteos/huellas previos y autorización expresa antes de producción. Reversión de esquema con datos B3 destruiría resultados y no desharía inscripciones creadas: no presentarla como recuperación funcional.

## 9. Permisos, auditoría y recuperación

| Operación | Profesor | Coordinador activo | Administrador |
| --- | --- | --- | --- |
| Proponer | Ámbito vigente, como hoy | No suplanta autor | No suplanta autor |
| Aprobar/rechazar pedagógicamente | No | Sí, exclusivo | No |
| Autorizar/revocar excepción | No | Sí, procedimiento expreso | No |
| Consultar ejecución | Solo proyección autorizada de su ámbito, por diseñar | Institucional operativa | Institucional según contrato autorizado |
| Revisar plan aprobado | No | Candidato para autoridad de revisión | Posible preparación administrativa, sin excepción ni decisión pedagógica; pendiente |
| Ejecutar administrativamente | No | Alternativa por aprobar | Alternativa por aprobar, sin convertirlo en aprobador pedagógico |

Tres políticas de ejecución posibles: coordinador solo, administrador solo, ambos. Coordinador solo simplifica la validación de continuidad; administrador solo separa funciones pero requiere validación coordinadora previa de toda excepción/cambio pedagógico; ambos favorece disponibilidad pero exige idéntico servicio y arbitraje por versión. **Ninguna se presume aprobada por sus permisos ordinarios actuales.**

Auditar propuesta/decisión original, revisión utilizada, actor ejecutor, fecha efectiva/registro, versiones observadas/resultantes, origen/destino/resultado, clave/huella y disposiciones diferidas/excepciones pertinentes. Evitar documentos, contactos o evaluaciones en JSON y errores. Los profesores no heredan expedientes ajenos por haber propuesto un ascenso; permisos actuales del backend se releen al consultar resultados.

Ante fallo antes de commit, rollback total de cierres, altas, reservas modificadas si alguna política futura lo autorizara, resultados y eventos. Ante respuesta perdida después del commit, recuperar resultado idempotente; no volver a cerrar el origen. Ante corrección de una ejecución ya confirmada, **no borrar origen, destino ni auditoría**: eventual operación compensatoria nueva, con autoridad, fechas y cupos revalidados, requiere diseño separado. No restaurar un dump sobre producción ni revertir manualmente tablas como respuesta automática.

Reportes distinguirán cantidad de aprobaciones, reubicaciones confirmadas, diferidas, pendientes y continuidades; mostrarán trayectoria por enlaces origen–destino y fecha efectiva. No contarán aprobado como inscrito en destino, no duplicarán al deportista permanente y no atribuirán un nivel institucional efectivo todavía no definido. La ocupación actual se calculará desde inscripciones/reservas reales, no desde destinos del plan.

## 10. Estrategia de pruebas futura

Solo PostgreSQL temporal aislado con identidad/destino comprobados antes de escribir. No ejecutar pruebas B3 sobre `zona_bloque`. Criterios mínimos:

1. Cubrir los 18 escenarios de la matriz para la alternativa autorizada, comparando filas, versiones, eventos y enlaces antes/después.
2. Proyección conjunta: cierres y altas en misma fecha, horarios contiguos, ciclos diferentes/solapados, varias disciplinas, destinos repetidos, fusión no admitida y capacidades futuras.
3. Último cupo: dos planes de deportistas distintos y alta ordinaria concurrente; ningún exceso ni cierre parcial en A.
4. Mismo plan/fila/clave simultáneos; distinta clave y mismo origen; misma clave con distinto payload; pérdida de respuesta después de commit.
5. Cambio concurrente de capacidad/horario, reserva, inscripción, revisión del plan o relevo del ejecutor/coordinador. Admitir solo órdenes seriales válidos; no exigir cancelar una operación ya confirmada antes de un relevo.
6. Rollback inyectado después de primer cierre, primera alta y antes de evento/commit; conservar identidad, historia y datos ajenos al lote. Probar que no se liberan reservas de otros expedientes.
7. Excepción vigente/programada/revocada/vencida; intento administrativo de conceder facultad; reserva vencida y futura que pasa a vigente sin escritura.
8. SQL/ORM directos contra estados/resultados protegidos, eventos UPDATE/DELETE, referencias cruzadas e intento de usar ruta antigua de tipo `nivel`.
9. Migración/reversión/reaplicación con datos representativos, colisiones de objetos, esquema `public`, search_path adverso y preservación de tablas anteriores. Documentar pérdida B3 al revertir esquema, sin simular recuperación de negocio.
10. Regresión completa backend y posteriormente frontend; mismas restricciones de privacidad, autenticación/CSRF, autorización y consultas sin efectos laterales. Probar cierre de ciclo y siguiente ascenso sin liberar antes expedientes incompletos.

Estas son pruebas **por desarrollar**, no comprobaciones superadas por leer los servicios existentes.

## 11. Plan incremental condicionado a aprobación

1. Resolver decisiones del apartado 12, formalizar invariantes y seleccionar A o B antes de escribir código.
2. Diseñar revisión versionada de aprobados, ciclo y conciliación, contratos de autoridad e idempotencia. Presentar inventario concreto de migraciones para autorización separada.
3. Implementar primero proyección/validación sin escrituras deportivas y pruebas aisladas de cupos, horarios y todas las situaciones.
4. Implementar persistencia administrativa y servicio de ejecución de la alternativa autorizada, con auditoría y transacciones, sin UI ni cambios en producción.
5. Auditar restricciones SQL, reintentos y concurrencia; preparar respaldo/restauración y solicitar autorización de migraciones reales.
6. Integrar interfaz solo con contrato validado y autorización posterior; verificación visual primero de lectura/simulación. Guardados persistentes requieren ventana y permiso específicos.

La división exacta de B3-B/B3-C se acordará al aprobar el diseño. Esta etapa no los inicia ni instala estructuras futuras.

## 12. Decisiones institucionales pendientes

1. Elegir A o B y definir el conjunto obligatorio; cuándo una continuidad/reserva/futura puede diferir sin impedir otras ejecuciones.
2. Autoridad ejecutora: coordinador, administrador o ambos; autoridad para revisar destinos de un aprobado y separación de cambios pedagógicos.
3. Tratamiento de suspendidas: esperar reanudación o trasladar suspensión; destino, vencimiento y liberación de reservas sin extensión implícita.
4. Tratamiento de futuras: esperar ingreso o sustitución/programación expresa; si habrá reserva previa de plaza y bajo qué autorización.
5. Fechas operativas: inicialmente solo hoy, tratamiento del último día/fin del periodo y exclusión explícita de retroactividad. Mantener cierre posterior al ingreso.
6. Condiciones del estado intermedio con diferentes niveles: excepción necesaria, responsable y límite; falta de destino no equivale a permiso de permanencia.
7. Revisión de aprobados con contexto cambiado o evidencia insuficiente: quién ratifica, qué cambia sin nueva aprobación y cómo se conserva la evidencia original.
8. Antigüedad de pendientes: frecuencia/responsable de revisión, avisos y eventual caducidad institucional; sin inventar plazo ni revocar aprobación por tiempo transcurrido.
9. Definición de ejecución completa, cierre del ciclo y exclusividad; siguiente ascenso y reconocimiento de nivel institucional sin duplicar malla ni borrar inscripciones previas.
10. Qué hacer si el proponente pierde asignación después de una aprobación válida; no convertirlo tácitamente en anulación ni eludir la revisión vigente anterior a aprobar.
11. Alcance inicial frente a futura participación por días/cupos por sesión: hoy la unidad sigue siendo grupo/intervalo completo. No declarar B3 preparado para capacidad por sesión sin rediseñar su integridad.
12. Procedimiento eventual de compensación de movimientos confirmados, sin restauración de base ni borrado histórico automático.

**Cierre B3-A:** se creó únicamente este documento. No se modificaron código, modelos, migraciones, roles, credenciales o datos; no hubo consultas a la base, propuestas, traslados, commits ni push. Se detiene para revisión y autorización antes de B3-B/B3-C.
