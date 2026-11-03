# Integración de propuestas docentes y ascensos institucionales — B2.1

Fecha: 29 de octubre de 2026. Estado: análisis y diseño para revisión. No autoriza implementación, migraciones ni decisiones pedagógicas reales.

**Recomendación:** mantener un único punto de entrada visual para el profesor, con dos circuitos administrativos existentes y un circuito institucional de ascenso. «Inscripción adicional» y «Traslado al mismo nivel» seguirían en `/api/propuestas/`; «Cambio de nivel / Proponer ascenso institucional» utilizaría exclusivamente `/api/ascensos/`, respaldado por `ProgresionInstitucional`. La creación y aprobación de tipo nivel por la vía antigua deben cerrarse también en backend, preservando sus registros históricos. No traducir silenciosamente una propuesta antigua en una progresión.

## 1. Diagnóstico del flujo actual

### Alcance y fuentes verificadas

Se inspeccionaron `backend/inscripciones/models.py`, `modelos_ascensos.py`, `servicios.py`, `servicios_ascensos.py`, `compatibilidad_propuestas.py`, `serializers.py`, `views.py`, `urls.py` y `cancelacion.py`; pruebas B1 y propuestas; permisos de deportistas y catálogo de niveles de organización; `FormularioPropuesta.jsx`, `Propuestas.jsx` y `SelectorCatalogo.jsx`.

Referencias: [diseño del Incremento 2](DISENO_ASCENSOS_INSTITUCIONALES_INCREMENTO_2.md), [implementación B1](IMPLEMENTACION_ASCENSOS_INCREMENTO_2_B1.md) e [informe de aplicación real](APLICACION_MIGRACION_ASCENSOS_B1.md). La cabecera histórica de implementación B1 aún dice «migración NO aplicada»; para el estado de despliegue prevalece el informe posterior de aplicación. No se modifica ninguno de esos documentos en este encargo.

No se consultó PostgreSQL ni se ejecutaron pruebas, servicios, solicitudes HTTP o migraciones en esta etapa documental. Las 319 pruebas backend y la aplicación B1 son antecedentes documentados, no comprobaciones repetidas aquí. Único archivo creado: este documento.

### Flujo antiguo y estructura nueva

| Elemento | Comportamiento actual verificado | Implicación para B2.1 |
| --- | --- | --- |
| `Propuesta` | Tipos inscripción/traslado/nivel; un origen, grupo destino obligatorio, fecha efectiva y una inscripción resultante | No sirve como cabecera de ascenso institucional sin alterar su contrato |
| `FormularioPropuesta` | Los tres tipos comparten envío a `/propuestas/`; nivel exige origen y grupo destino | Debe distinguir intención pedagógica de elección de destino operativo |
| `contexto_docente` | Para nivel impone fecha operativa, ingreso anterior y bloqueo de otras inscripciones relevantes | No reutilizarlo como validador de creación institucional: trasladaría límites que B1 ya separó |
| `resolver` | Aprobar tipo nivel, por coordinador, decide y ejecuta la continuación de una inscripción | Mientras siga habilitado existe una vía individual ejecutable, aunque haya protecciones de convivencia |
| `ProgresionInstitucional` | Deportista, disciplina, niveles, periodo e inscripción de referencia; decisión y plan separados | Representa la intención institucional sin exigir grupo destino |
| Servicios B1 | Propuesta interna, afectaciones automáticas, lectura por rol, revisión y decisión internas | Todavía no tienen endpoints ni pantallas públicas |
| `Propuestas.jsx` | Una lista de propuestas antiguas; mensajes y botones asocian aprobar con ejecutar | No presentar sus botones ni mensajes como interfaz de una progresión |
| `NivelVista` | Un profesor ve niveles de sus grupos permitidos | El catálogo ordinario puede ocultar el nivel que pretende proponer |

Las protecciones B1 actuales evitan convivencia de una progresión abierta y una propuesta individual pendiente de nivel de la misma disciplina. No sustituyen la retirada de la creación/aprobación antigua: cuando no hay progresión abierta, el circuito individual sigue disponible.

## 2. Compatibilidad con los servicios B1 y contradicciones a resolver

### Compatibilidad principal

`proponer_progresion(actor, referencia_id, nivel_destino, justificacion)` ya:

- Comprueba profesor activo y asignación vigente mediante inscripción activa visible de referencia.
- Deriva deportista, disciplina, nivel de origen y periodo de esa referencia.
- Exige persona y estructura activas, justificación y niveles distintos de la misma disciplina.
- Rechaza una propuesta antigua tipo nivel pendiente de esa disciplina.
- Crea el agregado, sus afectaciones y eventos en una transacción; no modifica inscripciones, reservas ni cupos.

`relevantes()` incluye todas las inscripciones abiertas de la disciplina cuyo periodo no haya terminado: activas, suspendidas con reserva, suspendidas sin reserva vigente y futuras, también en otros periodos. No las limita a las asignaciones del profesor ni al periodo de referencia. Las finalizadas quedan en la trayectoria histórica. Una inscripción de periodo terminado no se incluye aunque su estado persistente aún no diga finalizada; no inventar afectación operativa sobre ella.

El encabezado sigue necesitando una inscripción de referencia: esto identifica autoría y ámbito, **no delimita el alcance institucional de la revisión**. No hace falta modificar modelos ni migraciones para exponer ese servicio.

### Diferencias con la experiencia solicitada

| Cuestión | Alternativas | Recomendación para revisión |
| --- | --- | --- |
| Proponer por deportista/disciplina sin seleccionar destino | Conservar el formulario antiguo o utilizar el agregado B1 | Utilizar B1 sin grupo destino; no enviar `fecha_efectiva` del circuito antiguo |
| Referencia obligatoria en B1 | Elegir una referencia docente explícita; resolverla automáticamente; eliminarla del modelo | Mantener FK. Autoseleccionar si hay una sola referencia válida; si hay varias, mostrar selector de referencia propio. No eliminarla ni escoger el mayor nivel |
| Nivel actual institucional | Inferirlo del máximo nivel inscrito o reconocer que aún no existe | Mostrar «Nivel de origen de la inscripción de referencia». No llamarlo nivel institucional reconocido |
| Solo tiene referencias suspendidas/futuras | Ampliar B1 para poder proponer desde ellas o mantener requisito activo | Mantener requisito activo en B2.1; informar la limitación. Cambiarlo requiere una decisión expresa, no solo un ajuste visual |
| Identificar todas las inscripciones al profesor | Mostrar detalle global o separar alcance operativo y presentación | Registrar todas en backend; mostrar solo las propias autorizadas y un aviso general de revisión integral |
| Niveles superiores no impartidos por el profesor | Ampliar el catálogo global o abrir una consulta mínima contextual | Consulta específica de niveles para proponer, sin abrir grupos, alumnado o expedientes |

El servicio B1 admite intención pedagógica el mismo día del ingreso y decisión en otra fecha; no ejecuta cierres. La prohibición de cerrar el mismo día y el CHECK `inscripcion_fechas_validas` permanecen para operaciones administrativas. No imponer al nuevo formulario la caducidad diaria del circuito antiguo ni inventar un plazo de revisión.

Una mezcla de niveles de la disciplina puede incorporarse al expediente B1, pero su aprobación se bloquea para revisión institucional. B2.1 no debe elegir un nivel global por orden del catálogo ni revelar al profesor los detalles ajenos para explicar esa situación.

## 3. Estrategia para evitar propuestas duplicadas y circuitos paralelos

### Comparación de integración

| Alternativa | Resultado | Evaluación |
| --- | --- | --- |
| Cambiar solo la opción React | API antigua sigue admitiendo solicitudes manipuladas | Insuficiente |
| Redirigir silenciosamente POST `/propuestas/` tipo nivel a B1 | Cambia modelo de respuesta, ID, estados y campos requeridos | No recomendado: rompe contratos y dificulta auditoría |
| Ruta institucional explícita y cierre del circuito antiguo de nivel | Cada tipo usa su contrato; historia anterior intacta | Recomendado |

### Corte controlado propuesto

1. Mantener `Propuesta.tipo='nivel'` en modelo/serializer de lectura para interpretar historia. No eliminar columnas, choices ni filas.
2. Rechazar nuevas creaciones antiguas de nivel antes de guardarlas. Aplicar el control en servicio y API, no solo en selector React.
3. Rechazar consultas antiguas de destinos con `tipo=nivel`, con instrucción comprensible de utilizar la propuesta institucional.
4. Bloquear `resolver(... aprobar=True)` para propuestas históricas tipo nivel antes de invocar `contexto`, liberar reservas o ejecutar movimientos. La decisión antigua no puede continuar siendo una vía de ascenso paralela.
5. Conservar consulta y cierre motivado por rechazo/cancelación según los permisos actuales, sin convertirlos en aprobación institucional. La cancelación no debe ampliar el ámbito docente existente.
6. Mantener bloqueos B1 frente a propuestas antiguas pendientes. Su cierre será una acción humana autorizada, nunca una actualización masiva de despliegue.

### Duplicados y concurrencia

La restricción PostgreSQL `ascenso_abierto_unico` permite una progresión pendiente o aprobada por deportista/disciplina; una aprobada sigue abierta en B1, pues el estado ejecutado está prohibido. No bloquear por periodo solamente ni por un origen concreto. Dos profesores que atienden distintos grupos del mismo deportista no pueden abrir expedientes incompatibles de la misma disciplina.

Mantener el bloqueo global de usuarios y del deportista del servicio actual. Dentro de esa transacción se propone una comprobación explícita de agregado abierto para devolver **409**. Actualmente un duplicado detectado por `full_clean()` termina como ValidationError genérico **400**; la API no debe prometer que ya existe un contrato específico de conflicto.

Conservar la unicidad SQL como defensa final. Si hace falta traducir IntegrityError, identificar exclusivamente `ascenso_abierto_unico` y capturarlo fuera de un savepoint interno, sin reutilizar una transacción rota ni cambiar el manejador global de otros formularios.

El segundo envío debe recibir un mensaje genérico: «Existe una progresión abierta para esta disciplina. Solicita revisión a coordinación». No devolver el ID, autor ni expediente de otra persona. Proponer no garantiza cupo. Un bloqueo de botón evita dobles clics, pero no reemplaza la restricción SQL ni garantiza idempotencia tras una respuesta de red perdida; en ese caso consultar la propia bandeja antes de reenviar.

## 4. Diseño de endpoints y permisos

Se conserva `/api/ascensos/`, coherente con el diseño del Incremento 2. Son rutas propuestas, no implementadas.

| Endpoint | Método | Contrato y permiso |
| --- | --- | --- |
| `/api/ascensos/contexto/?deportista={id}&disciplina={id}` | GET | Profesor vigente. Disciplinas y referencias activas propias, niveles derivados y resumen visible; sin afectaciones ajenas |
| `/api/ascensos/niveles/?deportista={id}&disciplina={id}&search=...&page=...` | GET | Profesor con referencia válida en esa disciplina; niveles activos institucionales de la misma disciplina, metadatos mínimos |
| `/api/ascensos/` | POST | Solo profesor vigente, delegando en `proponer_progresion` |
| `/api/ascensos/?estado_decision=...&disciplina=...` | GET | Profesor: propias dentro de ámbito vigente; administrador/coordinador activo: consulta institucional según servicios B1 |
| `/api/ascensos/{id}/` | GET | Proyección por rol; consulta ajena no revela existencia |

En contexto, `deportista` es obligatorio y `disciplina` es opcional en la primera consulta: sin ella se ofrecen únicamente las disciplinas con referencias activas propias; al elegirla se obtiene su contexto filtrado. Así se evita depender del catálogo general y hacer una consulta por cada inscripción. Niveles sí requiere ambos parámetros. Paginar los listados, reutilizar el contexto durante la edición y reconstruirlo si cambia la selección; no recorrer todas las páginas institucionales para filtrar en React.

No crear en B2.1 rutas de aprobar, rechazar progresiones institucionales, ejecutar, modificar planes, autorizar excepciones, editar libremente o eliminar. Los servicios internos B1 de decisión siguen siendo base para B2.2; no se exponen todavía. Mantener sesiones Django, HttpOnly y CSRF.

### Creación y respuesta mínima

Campos de entrada recomendados:

```json
{
  "deportista": "ID interno seleccionado",
  "disciplina": "ID interno seleccionado",
  "inscripcion_referencia": "ID de referencia propia",
  "nivel_destino": "ID del nivel propuesto",
  "justificacion": "Motivo pedagógico y deportivo"
}
```

En la implementación los IDs serán enteros, no las cadenas explicativas del ejemplo. No se solicitan por escritura manual. Deportista/disciplina son contexto declarado para validar coherencia; el servidor deriva la cabecera desde la referencia y rechaza cualquier discrepancia, sin confiar en los datos React. La referencia autoseleccionada también viaja y se revalida. No aceptar `nivel_origen`, periodo, actor, fechas, estados, disposiciones o decisiones escritos por el cliente; se derivan o fijan en servidor.

Rechazar campos desconocidos mediante serializer estricto. Resolver relaciones primero mediante querysets autorizados, para no enviar un ID ajeno al `.get()` sin control del servicio. Convertir ausencias de referencia en error de dominio/404 sin mostrar si el expediente ajeno existe ni producir un 500.

Respuesta **201**: ID de progresión, fecha de creación, justificación, nombres/códigos mínimos de disciplina y niveles, decisión `pendiente`, plan `pendiente`, versión y aviso de que no se ejecutaron movimientos. Para profesores, excluir afectaciones globales, excepciones, reservas, motivos administrativos y eventos con detalles de otros ámbitos. `leer_progresion` ya separa la proyección, pero faltan campos legibles para una bandeja; añadir solo los necesarios, sin serializar el modelo completo.

La referencia de origen autoriza proponer; el resultado no concede acceso a otras inscripciones. Administrador conserva consulta institucional; coordinador activo conserva autoridad pedagógica, sin habilitarla mediante un endpoint B2.1.

El informe de aplicación B1 confirma que no se ejecutó post_migrate para crear permisos/content types de estos modelos. No adoptar `DjangoModelPermissions` ni asignar nuevos permisos globales automáticamente para hacer funcionar el módulo. Usar permisos de dominio por rol y ámbito, coherentes con B1 y los servicios existentes.

### Información de contexto y catálogos

Solo se devuelven referencias propias con código/nombre de grupo, nivel, periodo, fecha de ingreso y estado operativo mínimo. La lista informativa de inscripciones incluye únicamente `inscripciones_visibles` en la disciplina seleccionada; las futuras no se vuelven visibles por el hecho de existir una progresión. El servicio B1 seguirá capturándolas institucionalmente, aunque el docente no pueda consultarlas.

Texto sugerido: «La coordinación revisará todas las inscripciones pertinentes de esta disciplina, incluidas suspendidas y futuras. Aquí se muestran únicamente las que puedes consultar». No mostrar números de inscripciones ocultas ni sus grupos, profesores, reservas o fechas para justificar un conflicto.

La consulta contextual de niveles devuelve ID, código, nombre y disciplina, sin destinos ni personas. B1 valida nivel distinto y misma disciplina, pero **no define aún una regla de ascenso inmediato ni saltos**. No interpretar `Nivel.orden` como autorización pedagógica. El filtrado definitivo de niveles superiores o consecutivos necesita aprobación funcional antes de codificarse; véase apartado 9.

## 5. Diseño de interfaz docente

Reutilizar la página «Propuestas y decisiones» con dos secciones o pestañas claramente identificadas: **Inscripciones y traslados** y **Ascensos institucionales**. No mezclar IDs ni estados en una misma tabla sin discriminador: usar claves como `propuesta:{id}` y `ascenso:{id}` y endpoints propios. Una progresión no tiene cancelación genérica en B1 y no debe recibir el botón antiguo «Cancelar propuesta».

El selector de tipo conserva inscripción adicional y traslado; elegir cambio de nivel abre un formulario específico de ascenso, no una variante que conserve escondido el grupo destino. Puede etiquetarse «Cambio de nivel — ascenso institucional» durante la transición.

Secuencia propuesta:

1. Deportista de su ámbito, con nombre e identificación documental enmascarada, reutilizando `/deportistas/`.
2. Disciplina con referencia docente activa; si solo hay una, mostrarla autoseleccionada.
3. Referencia propia: mostrarla automáticamente si es única; si hay varias, selector buscable con grupo, periodo y nivel. Explicar que no limita las inscripciones revisadas. Mostrar «Nivel de origen de la referencia», de solo lectura.
4. Nivel propuesto mediante consulta institucional mínima; no grupo destino. La política de transiciones deberá confirmarse antes de filtrar como ascensos autorizados.
5. Justificación pedagógica y deportiva obligatoria, máximo **500** caracteres de B1; el límite **240** del formulario administrativo no cambia.
6. Resumen informativo propio y aviso de revisión global restringida; no pedir al profesor construir el plan administrativo.
7. Confirmación: «Esta propuesta no cambia grupos, niveles reconocidos, cupos ni reservas. Requiere revisión del coordinador activo».

Al cambiar deportista, limpiar disciplina, referencia y nivel propuesto; al cambiar disciplina, limpiar referencia/nivel; al cambiar referencia, volver a comprobar el nivel de origen y el destino elegido. Reiniciar instancias/cachés mediante claves de contexto, sin compartir datos entre usuarios ni conservar respuestas de un contexto anterior.

`SelectorCatalogo` ya aporta búsqueda, paginación y descarte de respuestas obsoletas. Su recuperación de un valor no cacheado construye una ruta de detalle y elimina los query params del contexto. No utilizar ese mecanismo para recuperar niveles institucionales sin ámbito: en B2.1 la selección debe proceder de resultados autorizados y se reinicia por contexto. Si posteriormente se admiten enlaces preseleccionados, diseñar un detalle contextual y un resolvedor explícito, sin alterar el comportamiento global de otros formularios.

Tras **201**, recargar la bandeja de ascensos y mostrar «Ascenso propuesto; no se modificaron inscripciones». Las tarjetas/filas separan «Decisión pedagógica» y «Preparación administrativa». No llamar «aplicada» a una progresión aprobada ni ofrecer botones de decisión coordinadora en esta etapa.

Mensajes: 400 para campos incoherentes; 403/404 para rol o ámbito perdido; 409 para agregado abierto o contexto obsoleto. Mantener el contrato actual `{detalle, errores?}` del backend. Los códigos estructurados adicionales requerirían diseñar un contrato específico, no modificar silenciosamente `comun/errores.py` ni el cliente compartido.

## 6. Tratamiento de propuestas históricas

| Estado antiguo tipo nivel | Tratamiento recomendado |
| --- | --- |
| Aplicada | Consulta histórica, con origen/resultado y responsables intactos; no crear una progresión equivalente automáticamente |
| Rechazada o cancelada | Consulta histórica, sin reabrir ni transformar |
| Pendiente | Identificar como flujo anterior; impedir aprobar/ejecutar; permitir cierre motivado según permisos actuales |

Una pendiente antigua sigue impidiendo abrir el nuevo expediente por la misma disciplina, como B1 exige. Profesor con acceso y autoría puede solicitar/cancelar según su permiso vigente; coordinación o administración pueden cancelar administrativamente conforme al servicio actual. Rechazar pedagógicamente la antigua sigue siendo exclusivo del coordinador. No ampliar acceso del profesor que perdió su asignación para resolver ese bloqueo: deberá intervenir gestión autorizada.

No reutilizar automáticamente justificación, autor, fecha o resolución para fabricar una propuesta nueva. Si se desea facilitar una nueva intención a partir de una antigua, debe ser un acto explícito del profesor vigente, sin sustitución de autoría. Un enlace histórico formal entre modelos exigiría otro diseño y posiblemente migración; no es necesario para la integración mínima.

Despliegue propuesto: backend cierra primero el alta/aprobación antiguas de nivel y ofrece la nueva creación; React cambia la opción y diferencia listas. Un cliente antiguo recibe un mensaje de sustitución, nunca produce una transferencia individual por continuar enviando IDs válidos. La lectura histórica permanece operativa durante todo el cambio.

## 7. Pruebas necesarias antes de implementar y publicar B2.1

Pruebas propuestas, **no ejecutadas en este encargo**:

| Área | Casos mínimos y resultado esperado |
| --- | --- |
| Ruta única | Tipo nivel antiguo rechazado al crear, consultar destinos y aprobar; sin efectos laterales; inscripción adicional y traslado mantienen contratos |
| Creación institucional | Con una y varias inscripciones del mismo nivel; sin grupo destino; cabecera coherente y afectaciones completas con estado inicial revisar |
| Suspensiones/futuros | Incluir reservas vigentes, suspendidas sin reserva y futuros de distintos periodos; no mostrarlos al docente si no son visibles; finalizadas no afectadas |
| Origen | Referencia de otra persona, disciplina, periodo u otro profesor rechazada; solo suspendidas/futuras no habilitan una referencia activa ficticia |
| Niveles | Mismo nivel, otra disciplina o inactivo rechazados; nivel activo no impartido puede consultarse como metadato contextual; política de saltos pendiente |
| Duplicados | Doble clic, reintento y dos profesores sobre distintos orígenes de la misma persona/disciplina: un agregado y un conflicto sin información ajena |
| Pendientes históricas | Bloqueo conservado; cierre motivado no ejecuta ni convierte; cancelación concurrente y nueva creación no producen incompatibilidad |
| Ámbito posterior | Pérdida de asignación, cambio de rol o desactivación entre contexto y POST: rechazo; profesor que pierde referencia no obtiene detalle histórico global |
| Privacidad REST | Listados/detalles/filtros manipulados, IDs ajenos, relaciones anidadas, errores y respuestas 201 sin afectaciones ajenas ni documentos completos |
| Sin efectos operativos | Comparar filas completas de inscripciones, reservas, eventos anteriores y grupos/cupos antes/después; solo se añaden progresión, afectaciones y auditoría autorizadas |
| Estados B1 | Creación solo pendiente/pendiente; no aceptar estados, decisiones, actor o disposiciones suministrados; ejecutado sigue prohibido por SQL |
| Fechas | Intención del día del ingreso posible sin cierre; sin caducidad diaria añadida; reglas de traslado del Incremento 1 intactas |
| Interfaz | Ascenso no muestra ni envía grupo destino/fecha efectiva; selección dependiente limpia valores; 500 caracteres, búsquedas, paginación, carga/error, 409 y respuesta de red perdida |
| Separación de listas | IDs numéricos coincidentes no cruzan acciones; no botón antiguo de aprobación/cancelación sobre progresiones; mensajes distinguen proponer y ejecutar |
| Seguridad general | CSRF, sesión expirada, anónimo, profesor, coordinador activo/inactivo y administrador; solo docente propone, nadie obtiene ejecución por la nueva API |

Reutilizar la suite B1 y las regresiones del Incremento 1. Actualizar las expectativas antiguas que dejan de ser válidas por retirada del alta/aprobación tipo nivel, reemplazándolas por regresiones de cierre de esa vía, sin eliminar cobertura de historia, permisos o integridad. Las pruebas de B1 internas de decisión siguen válidas: no equivalen a habilitar su API pública.

Concurrencia en PostgreSQL temporal con conexiones independientes y evidencia de un solo ganador; no simularla únicamente con mocks. Pruebas React con API simulada y flujo real contra una base aislada; ninguna propuesta ficticia persistente en `zona_bloque`. Antes de entrega futura, ejecutar backend completo, frontend y compilación y documentar resultados reales.

## 8. Cambios concretos propuestos para implementar B2.1

| Archivo o componente | Cambio acotado propuesto |
| --- | --- |
| `servicios_ascensos.py` | Mensajes específicos de duplicado, resolución segura del contexto de referencia y consultas mínimas sin escrituras; conservar transacción, generación de afectaciones y autoridad B1 |
| Nuevo `serializers_ascensos.py` | Entrada estricta, relaciones autorizadas y salidas docentes mínimas; no ModelSerializer global con todas las relaciones |
| Nuevo `views_ascensos.py` y `urls.py` | Solo contexto/niveles, crear, listar y consultar; métodos explícitamente limitados, sin acciones de decisión/ejecución |
| `servicios.py`, `views.py`, `compatibilidad_propuestas.py` | Cerrar creación, destinos y aprobación antiguas de tipo nivel; mantener lectura/cancelación/rechazo y resto de operaciones |
| Nuevo `FormularioAscenso.jsx` | Campos de intención pedagógica y contexto propio, reutilizando selectores, errores y botones |
| `FormularioPropuesta.jsx` | Mantener intactos los payloads de inscripción adicional/traslado; derivar la elección de ascenso al componente específico |
| `Propuestas.jsx` | Separar bandejas, estados y mensajes; no incluir acciones nuevas de coordinador ni aplicar acciones antiguas a IDs B1 |
| Pruebas y documentación | Nuevas pruebas REST/React/concurrencia y actualización de resultados cuando se ejecuten |

No se prevén modelos ni migraciones nuevos para esta integración mínima. No modificar B1 ya aplicada. Si al implementar se identifica que un requisito exige persistir otro dato, deberá presentarse un inventario separado antes de generar/aplicar cualquier cambio de esquema.

## 9. Riesgos y decisiones pendientes

1. **Referencia de origen:** confirmar la experiencia recomendada de autoselección si es única y elección explícita si hay varias. Una selección automática entre varias requiere una política determinista visible; no usar `.first()` sin explicación institucional.
2. **Transiciones deportivas:** confirmar si solo se ofrecen niveles superiores, el inmediato siguiente o saltos revisables. B1 solo exige distinto nivel de la misma disciplina; `orden` no es una regla aprobada de promoción ni los colores representan niveles pedagógicos.
3. **Solo suspendidos/futuros:** cualquier ampliación para permitir proponer sin referencia docente activa contradice el requisito actual B1 y necesita autorización específica. La inclusión de estas inscripciones en el análisis ya es compatible cuando existe una referencia activa.
4. **Pendientes antiguas:** aprobar el corte de creación/aprobación y el cierre humano motivado. Mantenerlas pendientes puede bloquear legítimamente el nuevo expediente; no resolverlo mediante migración o conversión automática.
5. **Reconocimiento institucional:** no existe un nivel independiente de las inscripciones; esta etapa no lo crea ni determina cuándo una aprobación futura cambia ese reconocimiento.
6. **Expediente aprobado abierto:** B1 mantiene exclusividad de una progresión aprobada y no tiene cancelación/sustitución de ese expediente. No introducir una nueva intención paralela ni liberar unicidad; el ciclo posterior corresponde a B2.2/B3 y decisiones futuras.
7. **Contexto cambiante:** referencias, reservas y nuevas inscripciones pueden cambiar después de la vista previa. El POST debe reconstruir el conjunto, nunca confiar en IDs de afectaciones del navegador. La reparación/versionado integral de un plan obsoleto sigue fuera de B2.1.
8. **Exposición de contexto global:** la frase «todas las inscripciones» describe lo que registra/revisa el sistema, no un permiso docente para consultar otros grupos. Mantener mensajes genéricos cuando el impedimento involucra ámbitos ajenos.
9. **Alcance B2.2:** diseñar después la revisión global y decisiones del coordinador, con permisos y excepciones ya previstos en B1. En B2.1 no hay botones ni rutas públicas para ello. El CHECK que bloquea ejecutado permanece intacto hasta una autorización B3.

**Recomendación final:** aprobar una integración mediante una API institucional explícita y formulario específico, conservando los dos circuitos administrativos actuales y cerrando el circuito antiguo de aprobación de nivel. Resolver primero referencia, transiciones y tratamiento de pendientes históricas. La implementación mínima puede reutilizar B1 sin migraciones, sin destinos obligatorios y sin nuevas facultades docentes. Este encargo termina aquí para revisión; no se implementó ninguna parte del diseño.
