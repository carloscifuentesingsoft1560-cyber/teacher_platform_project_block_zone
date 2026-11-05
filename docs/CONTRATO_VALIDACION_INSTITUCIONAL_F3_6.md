# Contrato de validación institucional — F3.6-A

Fecha: 5 de noviembre de 2026. Estado: **borrador pendiente de aprobación institucional**.

## 1. Base y alcance

Revisión estática del repositorio `C:\Users\57310\Desktop\Proyectos_Carlos\zona-de-bloque-github`, rama `interfaz-sesiones-react`, commit `5de9718cba1af68bf2487e6bdcd0626397d53d47`.

Este documento define una propuesta para validar institucionalmente sesiones registradas. **Su creación no aprueba reglas, no concede autorizaciones funcionales ni habilita el paso a `realizada`.** «Implementado» significa presente en el código revisado; no certifica despliegue ni aplicación de migraciones en una base concreta. No se consultó PostgreSQL ni se ejecutaron Django, migraciones o pruebas.

Se distinguen cuatro actos: registrar lo ocurrido, cerrar la asistencia y el informe, acreditar habilitación funcional para cada participante y actividad, y validar institucionalmente la sesión. Consentimientos, matrícula, presencia, aprobación curricular y seguimiento pedagógico no sustituyen esos actos.

### Clasificación de las reglas

- **Implementado:** comportamiento descrito en las secciones 2 y 3 y en los párrafos expresamente identificados de las secciones 7 y 8; limitado a la evidencia estática indicada.
- **Recomendación técnica:** estructura de matriz, evidencias, intervalos, eventos y controles futuros descritos en las secciones 5 a 8. Son requisitos sugeridos para un diseño posterior, sin efecto operativo actual.
- **Decisión institucional pendiente:** atribuciones y separación de autoridades, prohibición de autovalidación, criterios de aceptación o rechazo y tratamiento de sesiones sin práctica. Las propuestas de las secciones 4 a 9 requieren aprobación expresa; una recomendación técnica no sustituye esa aprobación.

## 2. Comportamiento implementado

| Materia | Evidencia y límite actual |
| --- | --- |
| Frontera funcional | `verificar_autorizacion_funcional()` deniega siempre. La acción HTTP `realizar` invoca `validar_realizada`; no constituye una vía habilitada de validación. |
| Actor de ejecución | `operar()` exige al profesor responsable activo, con rol docente y asignación vigente hoy y aplicable a la fecha de sesión, salvo la corrección administrativa de asistencia. Esta condición también precede al intento de `validar_realizada`; aún no existe un comando de validación para coordinación o administración. |
| Informe y estado | Finalizar ejecución cierra asistencia si procede, registra autor y fecha del cierre y conserva `validacion_funcional: pendiente`. La lectura distingue `registrada_pendiente_validacion` de `realizada`; cerrar no valida. |
| Padrón | Se obtiene de inscripciones aplicables al grupo y fecha, con intervalo de matrícula `[ingreso, salida)`. Se detectan inscripciones superpuestas y diferencias entre padrón actual y guardado. La preparación es explícita; no elimina silenciosamente asistencias con estado registrado. |
| Cierre | Exige estados explícitos de todo el padrón y fecha no futura. El informe requiere un plan sellado de la sesión y exactamente sus tareas, sin duplicados ni tareas ajenas. |
| Registro de actividades | Cada tarea tiene resultado `realizada`, `modificada` u `omitida`. Una modificación exige adaptación descrita; una omisión exige motivo y cero minutos. Las duraciones deben ser coherentes con el intervalo real. No existe una matriz que acredite qué participante realizó cada actividad. |
| Concurrencia | Comandos atómicos, bloqueo de usuarios, grupo y sesión, control de versión y eventos por actor y clave. Se reevalúan facultades antes de recuperar un reintento. |
| Protección persistente definida | La migración `0005_cierre_definitivo.py` incluye triggers que rechazan insertar o pasar una sesión a `realizada`, impiden reabrir asistencia y protegen contexto cerrado, ejecución finalizada y eventos. Su presencia en el repositorio no demuestra que estén instalados en PostgreSQL. |
| Corrección de asistencia | Solo administrador activo con rol vigente; coordinación por sí sola no basta. Exige cierre, estado anterior coincidente, estado nuevo diferente y válido, motivo y evento asociado. No valida funcionalmente la sesión. |
| Seguimiento | Solo coordinación vigente registra seguimiento; cada entrada conserva referencia a la anterior. Los indicadores son descriptivos y no certifican habilitación, práctica individual ni aprendizaje. |

Fuentes: [ejecución](../backend/sesiones/ejecucion.py), [comandos y eventos](../backend/sesiones/servicios.py), [ámbitos](../backend/sesiones/permisos.py), [acciones HTTP](../backend/sesiones/views.py), [lectura de sesión](../backend/sesiones/serializers.py), [lectura de ejecución](../backend/sesiones/serializers_ejecucion.py), [modelos](../backend/sesiones/models.py), [protecciones de cierre](../backend/sesiones/migrations/0005_cierre_definitivo.py) y [seguimiento](../backend/sesiones/seguimiento.py).

## 3. Consentimientos y facultades existentes: separación obligatoria

`TipoAutorizacion` identifica código, versión, finalidad y referencia de texto. `Autorizacion` registra la decisión de un deportista o de un acudiente acreditado. No es un modelo de aptitud o habilitación deportiva por participante y actividad.

En el código de deportistas ya existen estos controles:

- La facultad del acudiente se comprueba por vínculo y tipo/versión concretos, con método, evidencia privada mediante UUID v4, responsable, resultado y vigencia. Parentesco o contacto principal no conceden facultad universal.
- Una comprobación verificada exige identidad y facultad contrastadas. Se conserva historial; la evaluación usa la comprobación más reciente del alcance, el estado del vínculo, contacto y tipo, y sus fechas.
- El vínculo termina de forma exclusiva en `fecha_fin`; la fecha final de comprobación es inclusiva. No deben confundirse esos límites con los de asignaciones docentes o con futuros intervalos funcionales.
- Las declaraciones no se editan: se revocan y se registra una nueva. La revocación exige versión y motivo; repetirla genera conflicto. Los textos utilizados solo permiten cambiar su estado activo, debiendo crearse otra versión para cambiar su contenido.
- Registrar autorización personal exige una política activa de autonomía coherente y comprobar edad a la fecha de declaración. No se fija aquí una edad institucional.

Fuentes: [modelos de deportistas](../backend/deportistas/models.py), [facultades](../backend/deportistas/facultades.py) y [servicios](../backend/deportistas/servicios.py). El [catálogo propuesto](PROPUESTA_CATALOGO_AUTORIZACIONES.md) sigue siendo borrador y no acredita textos aprobados. No se propone cargarlo ni reutilizarlo como habilitación de práctica.

## 4. Autoridad validadora propuesta — pendiente de aprobación

**Coordinador: validador principal.** Se propone que una cuenta activa con pertenencia vigente de coordinación y ámbito institucional aplicable pueda emitir la decisión sobre una sesión cerrada. Debe revisar la evidencia y resolver observaciones; el seguimiento pedagógico existente no equivale a esa decisión.

**Administrador: facultad excepcional justificada.** Se propone permitir validación excepcional con administración vigente, causa concreta, referencia de respaldo institucional, alcance y motivo de la sustitución del coordinador. La decisión debe señalar explícitamente el carácter excepcional y quedar disponible para revisión de coordinación. No basta con ser administrador para omitir controles funcionales, restricciones o revocaciones.

**Profesor responsable:** registra y finaliza el informe; propone aclaraciones. El rol docente por sí solo no habilitaría validación institucional.

**Prohibición de autovalidación — decisión institucional pendiente:** se propone prohibir que quien ejecutó, registró o finalizó su propia ejecución valide esa sesión, incluso si posee simultáneamente roles de profesor, coordinador y administrador. Cambiar de rol o usar otra cuenta de la misma persona no elimina el conflicto. La excepción administrativa tampoco lo permite: debe intervenir otra persona competente e independiente. Si no existe un validador independiente habilitado, la sesión conserva su informe pendiente; no se resuelve mediante autovalidación. La institución debe aprobar esta regla y el procedimiento de suplencia.

**Autoridad emisora y autoridad validadora — competencias distintas:** la primera acredita la habilitación funcional de un participante para una actividad, con vigencia y restricciones; la segunda contrasta esa habilitación y los hechos para decidir sobre la sesión. Validar una sesión no permite emitir, ampliar, renovar o reconstruir retroactivamente una autorización faltante. Ser coordinador o administrador no acredita por sí mismo competencia emisora. La institución debe designar por separado ambas competencias y decidir si una misma persona puede ejercerlas en casos sin conflicto, manteniendo siempre la prohibición de autovalidación.

Estas atribuciones son futuras: los permisos de contenido, ascensos, organización y corrección de asistencia no se trasladan automáticamente a la validación de sesiones. El catálogo actual de [acciones por rol](../backend/cuentas/autorizacion.py) tampoco define esta competencia.

## 5. Autorización funcional propuesta por participante y actividad

Se propone una fuente institucional específica, verificable y versionada. Cada autorización debe identificar al menos:

| Dato propuesto | Regla para aprobación |
| --- | --- |
| Participante | Identificador estable del deportista y relación con la inscripción de referencia; nunca solo nombre o pertenencia al grupo. |
| Actividad | Identificador de tarea y referencia a versión del ejercicio cuando exista; alcance explícito que permita contrastar la actividad real y sus adaptaciones. |
| Competencia de quien habilita | Responsable y facultad institucional para emitir esa autorización. La institución debe designar esta autoridad; no se presume competencia médica o técnica por tener un rol informático. |
| Vigencia | Inicio y fin opcional con zona horaria y límites inequívocos. Se propone intervalo `[desde, hasta)` y evaluación sobre todo el intervalo real de participación. |
| Condiciones | Restricciones estructuradas, adaptaciones permitidas, supervisión y otros límites aprobados; una observación libre no debe convertirse automáticamente en permiso. |
| Evidencia | Referencia privada localizable, versión, emisor, fecha de emisión y fecha de registro. No incluir diagnósticos ni documentos sensibles en eventos generales. |
| Ciclo de vida | Decisión explícita, sustituciones y revocaciones con fecha efectiva y responsable, conservando antecedentes. |

La fuente, sus estados y la matriz participante–actividad **no existen como contrato operativo en el módulo de sesiones actual**. Tampoco se debe afirmar que una actividad agregada `realizada` prueba participación de todos los asistentes.

### 5.1. Matriz participante–actividad — recomendación técnica

Se propone una fila por combinación del padrón cerrado y las actividades del informe, con participante, inscripción, tarea, estado de participación, intervalos efectivos cuando correspondan, evidencia y responsable del registro. El resultado agregado de la actividad y la asistencia global deben conservarse como datos distintos.

| Estado propuesto de participación | Significado y evidencia requerida | Efecto propuesto sobre la validación |
| --- | --- | --- |
| Participación efectiva | Práctica acreditada en esa actividad, completa o parcial, con intervalo y referencia de evidencia. | Exige autorización funcional compatible que cubra todo el intervalo efectivo. |
| No participación | Se acredita que no practicó esa actividad; conservar causa, por ejemplo ausencia, llegada posterior, retiro previo u omisión. | No exige habilitación para una práctica que no ocurrió; no suma práctica ni aprendizaje acreditado. |
| Participación no acreditada | No puede determinarse si practicó o faltan datos fiables del alcance o intervalo. Una celda vacía pertenece a este supuesto, no al de no participación. | Impide la validación favorable de la sesión hasta aclaración; una autorización vigente no prueba que hubo participación. |

Estos estados son propuestos y no agregan valores al modelo actual. Toda tarea omitida debe conservar su motivo; no puede tener participación efectiva sin resolver primero la contradicción del informe. La falta de autorización nunca debe subsanarse reclasificando una práctica ocurrida como no participación.

### 5.2. Llegadas tarde, retiros y participación parcial — recomendación técnica

`tarde` y `retiro` describen asistencia, pero no identifican automáticamente las actividades practicadas. Se propone registrar llegada y retiro efectivos, intervalos de actividad y su evidencia. En actividades anteriores a la llegada o posteriores al retiro solo se admite no participación cuando esté acreditada. Si participó en una parte de la actividad, se registra participación efectiva parcial y se evalúa la autorización durante todo ese tramo, incluidas adaptaciones y restricciones.

Si faltan horarios o evidencias suficientes para delimitar la práctica, se registra participación no acreditada y se bloquea la decisión favorable; no se presume participación completa, ausencia ni cobertura por toda la sesión. Los criterios y evidencias admisibles requieren aprobación institucional.

### 5.3. Sesiones sin práctica efectiva — decisión institucional pendiente

Se propone distinguir una sesión sin práctica de una sesión con práctica pendiente de acreditar. Solo puede clasificarse sin práctica efectiva cuando todas las combinaciones de la matriz acrediten no participación y el informe explique la causa, con resultados de actividad coherentes. Una matriz vacía, un padrón vacío o la ausencia de minutos no bastan por sí solos para esa conclusión: deben justificarse y revisarse las circunstancias. Si alguna participación es desconocida, no corresponde esta clasificación.

Para una sesión acreditada sin práctica se propone admitir el cierre y la revisión documental del hecho, sin exigir autorizaciones para actividades no practicadas y sin certificar práctica, aprendizaje o cumplimiento práctico. **No se propone pasarla a `realizada` como sesión con práctica validada.** La institución debe aprobar su clasificación y efectos en indicadores; no se crea aquí un estado persistente ni se habilita una nueva transición. La cancelación continúa sujeta a las restricciones implementadas y no sustituye el registro de lo ocurrido.

## 6. Vigencia, restricciones y revocaciones propuestas

1. Evaluar las autorizaciones funcionales contra la fecha e intervalo reales de práctica, y las facultades del validador contra el momento de decidir. La validación retrospectiva no debe inventar una habilitación previa ni presentarse como permiso para una práctica futura.
2. Bloquear ante ausencia de fuente, evidencia insuficiente, vigencia incompleta, incompatibilidad o restricción no resuelta. No aplicar consentimiento genérico, silencio o matrícula como sustitutos.
3. Una adaptación metodológica solo sería aceptable si está expresamente cubierta; describirla en el informe no acredita esa cobertura. Si la actividad excede lo permitido, conservar el hecho registrado y abrir revisión sin certificarlo como conforme.
4. Revocar o sustituir mediante un nuevo evento con fecha efectiva, fecha de registro, autor, motivo y alcance. Una revocación debe impedir nuevos usos afectados; no borrar evidencia anterior.
5. Ante una revocación registrada después de la práctica, distinguir si su efecto comienza después o afecta al intervalo ya evaluado. El primer caso conserva la decisión histórica; el segundo requiere revisión vinculada. La institución debe aprobar los efectos retroactivos y el tratamiento de evidencias contradictorias.
6. Una excepción administrativa solo sustituiría al decisor principal. No levantaría una prohibición funcional ni permitiría ignorar una revocación.

Estos criterios no están implementados para autorizaciones funcionales. Las fechas y revocaciones de consentimientos existentes no resuelven por sí solas esta evaluación.

## 7. Decisión, trazabilidad e idempotencia propuestas

Antes de validar se propone exigir: sesión no cancelada, informe finalizado, asistencia cerrada y coherente, plan sellado y actividades identificadas, matriz de participación completa y cobertura funcional sin incompatibilidades. La decisión deberá referirse a las versiones exactas revisadas.

La cobertura positiva se exige para cada participación efectiva; las no participaciones deben estar acreditadas y ninguna combinación puede quedar con participación no acreditada. Las sesiones sin práctica siguen el tratamiento diferenciado de la sección 5.3.

Se propone registrar un evento inmutable con sesión y versión, ejecución y plan, actor y rol ejercido, fecha del servidor, versión del contrato aprobado, fuentes funcionales evaluadas por participante y actividad, restricciones comprobadas, resultado, motivos y vínculo a decisiones anteriores. Una excepción administrativa debe tener justificación propia. Las evidencias privadas se referencian sin copiar sus contenidos a la respuesta o al historial general.

El resultado favorable permitiría la transición institucional a `realizada`; observaciones o rechazo conservarían el informe y la decisión sin fingir validación. Los nombres y la representación de esos resultados requieren diseño y aprobación; no son nuevos estados existentes del modelo.

Como base ya implementada, `EventoSesion` guarda operación, solicitud, detalle, actor, clave y versión resultante. `_reintento()` devuelve la sesión asociada al evento si coinciden actor, clave, operación y solicitud; una clave reutilizada con contenido distinto produce conflicto 409. No reproduce necesariamente una respuesta histórica idéntica: devuelve la sesión y la lectura puede reflejar su estado actual.

Para el futuro comando de validación se propone mantener esa unicidad y control de versión, revalidar facultades y ámbito antes de admitir incluso reintentos, y evaluar fuentes bajo controles de concurrencia compatibles con sus revocaciones. Un reintento exacto no debe crear otra decisión ni sustituir evidencias; una nueva evaluación requerirá otra clave y referencia al antecedente. Una versión obsoleta debe generar conflicto sin efectos parciales. Es necesario definir la respuesta histórica y cómo informar una decisión posteriormente revisada.

## 8. Correcciones posteriores

**Implementado:** corregir asistencia cerrada es una operación administrativa excepcional con motivo obligatorio, valor anterior comprobado, evento enlazado y registro de corrección. El trigger definido actualiza la proyección sin reescribir el historial. El informe finalizado y sus actividades quedan protegidos; el servicio no ofrece su edición ordinaria. El seguimiento permite añadir aclaraciones enlazadas, pero no modifica ni valida el informe.

**Propuesta pendiente:** una corrección que afecte participantes, actividad, intervalo o fuente funcional debe provocar revisión explícita de la decisión afectada. Conservar la validación original y emitir un resultado posterior que la confirme, sustituya o retire, con alcance, motivo, evidencia y responsables. No reabrir ni sobrescribir silenciosamente la sesión o la ejecución histórica. La corrección de asistencia existente no implementa esa reevaluación automática.

Para rectificar una ejecución finalizada se requiere aprobar un mecanismo específico de enmienda enlazada y sus efectos sobre indicadores. No reutilizar una corrección de asistencia o un comentario de seguimiento para alterar hechos de ejecución. Los informes futuros deberán distinguir hechos registrados, decisiones vigentes y decisiones sustituidas.

## 9. Aprobaciones necesarias y frontera de esta fase

Antes de cualquier implementación institucional se requiere aprobar expresamente:

- Coordinador como validador principal; causas y evidencia de excepción administrativa; suplencias, ámbitos y separación entre autor y validador.
- Autoridad competente y fuente de autorizaciones funcionales, granularidad por participante y actividad, restricciones, evidencia y custodia.
- Límites temporales, participación parcial, conflictos, revocación y efectos sobre decisiones históricas.
- Contenido del evento, resultados, correcciones, conservación y presentación de indicadores.
- Prohibición de autovalidación incluso con varios roles, designación separada de emisores y validadores, evidencia de no participación y clasificación de sesiones sin práctica efectiva.
- Una fase técnica posterior autorizada para modelos, permisos, comandos, interfaz y protecciones persistentes coherentes. El bloqueo también existe en el SQL de migración; cambiar solo la interfaz o el permiso de API sería insuficiente.

### 9.1. Matriz de aceptación y rechazo — decisiones institucionales propuestas

En esta tabla, «rechazo» significa denegar la validación favorable y conservar el informe con causa trazable; no borrar el hecho ni crear un estado nuevo. Salvo indicación contraria, se supone una sesión con práctica efectiva, cerrada y coherente, revisada por otra persona con facultad validadora vigente. Todos los casos son futuros: **hoy el paso a `realizada` continúa bloqueado**.

| Caso | Resultado propuesto | Criterio |
| --- | --- | --- |
| Todas las participaciones efectivas acreditadas, autorizaciones vigentes y compatibles, restantes combinaciones acreditadas sin participación | Aceptación de validación institucional | Cobertura completa y ausencia de conflictos; no equivale a certificar aprendizaje. |
| Autorización inexistente para una participación efectiva | Rechazo | Matrícula, consentimiento o excepción administrativa no la sustituyen. |
| Autorización vencida o todavía no vigente en todo o parte del intervalo practicado | Rechazo | La vigencia debe cubrir todo el tramo efectivo; renovar después no subsana retroactivamente. |
| Revocación efectiva antes o durante la práctica | Rechazo | Existe participación fuera de cobertura; conservar hechos y abrir revisión. |
| Revocación efectiva solo después de la práctica | Aceptación posible | Si la cobertura histórica y los demás requisitos se acreditan, la revocación posterior no invalida por sí sola ese intervalo; impide usos posteriores afectados. |
| Autorización de otra actividad, versión, participante o incompatible con restricciones o adaptación real | Rechazo | No se presume equivalencia ni se amplía el alcance al validar. |
| Participación no acreditada, aun con autorización válida | Rechazo hasta aclaración | Habilitación y prueba de participación son requisitos distintos. |
| Llegada tarde, retiro o práctica parcial con intervalos acreditados y cobertura completa de esos tramos | Aceptación posible | Solo se reconoce la práctica efectiva acreditada, sin inferir asistencia o práctica completa. |
| Llegada tarde, retiro o práctica parcial sin intervalos fiables | Rechazo hasta aclaración | Aplicar participación no acreditada a las combinaciones inciertas. |
| No participación acreditada de una persona en una actividad, sin autorización para esa combinación | No impide por sí sola aceptar la sesión con práctica de otros | No exigir permiso para una práctica inexistente ni contar esa combinación como práctica. |
| Todas las combinaciones acreditadas sin participación efectiva | Revisión documental diferenciada; no aceptación como práctica `realizada` | Aplicar sección 5.3 y conservar causa; clasificación institucional pendiente. |
| Matriz vacía o participación desconocida presentada como sesión sin práctica | Rechazo de esa conclusión hasta aclaración | Ausencia de registros no acredita ausencia de práctica. |
| Coordinador o administrador intenta validar su propia ejecución, incluso con varios roles | Rechazo | Debe decidir otra persona independiente habilitada. |
| Administrador independiente, excepción justificada y todos los requisitos cumplidos | Aceptación excepcional posible | La justificación sustituye al decisor principal, no a las autorizaciones ni a las restricciones. |
| Revocación concurrente o versión de sesión obsoleta | Sin validación hasta resolver el conflicto | Releer y reevaluar fuentes de manera consistente; no perder la revocación. |
| Reintento exacto de una decisión ya registrada | Sin duplicación de decisión | Revalidar acceso y aplicar idempotencia; no convertir el reintento en una evaluación nueva. |
| Corrección posterior que afecta participación o cobertura | Revisión enlazada | Conservar la decisión original y emitir el resultado posterior según sección 8. |

**Esta matriz contiene criterios pendientes de aprobación, no capacidades implementadas, pruebas ejecutadas ni resultados certificados.**

F3.6-A entrega exclusivamente este Markdown. No autoriza activar `realizada`, modificar código o migraciones, consultar `zona_bloque`, ejecutar Django o pruebas de base de datos, alterar respaldos o temporales, ni realizar commit o push.
