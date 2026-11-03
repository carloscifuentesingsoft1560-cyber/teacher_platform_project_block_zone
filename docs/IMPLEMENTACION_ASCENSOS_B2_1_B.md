# Interfaz docente de ascensos institucionales — B2.1-B

Fecha: 29 de octubre de 2026. Estado: implementada y probada con API simulada; pendiente verificación visual conjunta. No se inicia B2.2 ni B3.

## 1. Revisión previa y alcance

Se revisaron [la integración diseñada](INTEGRACION_PROPUESTAS_ASCENSOS_B2_1.md), [el backend efectivo B2.1-A](IMPLEMENTACION_ASCENSOS_B2_1_A.md), `views_ascensos.py`, `serializers_ascensos.py`, `consultas_ascensos.py`, los componentes y pruebas existentes de React.

El backend ya ofrece los contratos necesarios. No se modificó código backend: se compararon SHA-256 de sus **120 archivos Python** antes y después, sin diferencias. No se generaron/aplicaron migraciones, no se alteraron permisos, roles o credenciales y no se consultó ni modificó `zona_bloque` durante esta entrega.

La pantalla sigue en `/profesor/propuestas`. Mantiene inscripción adicional y traslado al mismo nivel; sustituye la opción de creación «Cambio de nivel» por **Ascenso institucional**. Los registros antiguos no se borran ni convierten y permanecen en una tabla distinta.

## 2. Pantalla y componentes

### Formulario docente

`FormularioPropuesta.jsx` conserva el selector de modalidades:

1. Inscripción adicional.
2. Traslado al mismo nivel.
3. Ascenso institucional.

Los dos primeros conservan payload, selección de destino, fecha operativa y servicios anteriores. El tercero monta `FormularioAscenso.jsx`, con estados y envío propios. No se envía `tipo=nivel` ni se usa `/propuestas/destinos/` para un ascenso.

El nuevo formulario requiere selección expresa de:

- Deportista del catálogo docente autorizado, con presentación documental enmascarada proporcionada por el backend.
- Disciplina disponible para ese deportista.
- Inscripción activa de referencia propia, identificada por código/nombre de grupo, nivel y periodo.

Muestra el nivel de origen de esa referencia como información, sin afirmar que exista un nivel institucional reconocido independiente. Consulta el sucesor mediante la API y lo muestra de solo lectura: el profesor no elige un salto ni un grupo de destino. No necesita que exista grupo de destino con cupo para proponer la intención pedagógica.

La justificación es un textarea etiquetado, obligatorio, con máximo 500 caracteres, contador e instrucciones accesibles. Las validaciones controladas comprueban contexto completo, respuesta de nivel vigente y texto no vacío incluso si se fuerza submit.

Cambiar deportista limpia disciplina, referencia y nivel. Cambiar disciplina limpia referencia/nivel. Cambiar referencia invalida el nivel anterior. Los selectores buscables se remontan por contexto para no conservar selecciones/cachés ajenas. Las respuestas tardías de niveles se descartan y se comprueba que el resultado siga asociado a la clave del contexto actual.

### Listados separados

`Propuestas.jsx` distingue:

- **Inscripciones, traslados e historial anterior:** registros del modelo antiguo, estados y resoluciones históricos. Los de tipo nivel muestran `aviso_procedimiento` o una explicación de deshabilitación; no se ofrece aprobarlos. Se conservan las operaciones antiguas de cancelación motivada y rechazo por coordinador cuando corresponden, sin añadir facultades nuevas.
- **Ascensos institucionales:** nuevo `ListadoAscensos.jsx`, visible en esta integración docente. Muestra deportista, disciplina, niveles, periodo, justificación, decisión pedagógica y preparación administrativa. No tiene botones de aprobación, cancelación, revocación, modificación o ejecución institucional.

Las filas usan espacios de identificación distintos (`propuesta:{id}` y `ascenso:{id}`). No se reutilizan acciones del modelo antiguo sobre IDs de progresiones, aunque coincidan numéricamente. En los paneles de otros roles no se incorpora una nueva bandeja coordinadora: eso queda para B2.2; las operaciones administrativas anteriores continúan.

El listado institucional permite filtrar decisión, paginar y actualizar. Incluye mensajes propios de carga, vacío y error. Tras una creación confirmada, se remonta en la primera página con su filtro inicial para mostrar la nueva propuesta; no se fuerza una recarga innecesaria del historial antiguo, que no cambió.

## 3. Contratos de API utilizados

| Operación | Ruta y parámetros reales |
| --- | --- |
| Seleccionar persona | `GET /api/deportistas/?search=...` y paginación del selector existente |
| Seleccionar disciplina | `GET /api/ascensos/contexto/?deportista={id}&vista=disciplinas&search=...` |
| Seleccionar referencia | `GET /api/ascensos/contexto/?deportista={id}&disciplina={id}&vista=referencias&search=...` |
| Determinar sucesor | `GET /api/ascensos/niveles/?deportista={id}&disciplina={id}&inscripcion_referencia={id}` |
| Registrar intención | `POST /api/ascensos/`, sin query params |
| Consultar bandeja | `GET /api/ascensos/?page={n}` y opcional `estado_decision` |
| Consultar historial antiguo | `GET /api/propuestas/`, conservando filtros/paginación/búsqueda existentes |

Los selectores siguen los enlaces `next` ya devueltos por la API. No se inventaron rutas de detalle para `/ascensos/niveles/{id}/` o `/ascensos/contexto/{id}/`: el formulario parte de valores vacíos y solo acepta selecciones de resultados autorizados, reiniciando el contexto cuando corresponde.

`useListado` añade normalmente `search`, pero el listado institucional no lo admite. Se agregó una opción **`permitirBusqueda: false`** al hook y se utiliza solo en ese listado. Por defecto conserva el comportamiento anterior. No se amplió el backend para tolerar parámetros indebidos ni se alteró el contrato de otros listados.

El payload del ascenso contiene exactamente:

| Campo | Origen |
| --- | --- |
| `deportista` | ID seleccionado del catálogo docente |
| `disciplina` | ID del contexto autorizado |
| `inscripcion_referencia` | Selección expresa del profesor |
| `nivel_destino` | ID del único sucesor devuelto por la API |
| `justificacion` | Texto recortado en los extremos, hasta 500 caracteres |

No se incluyen autor, fecha efectiva, origen editable, estados, periodo, versión, grupo destino, decisiones o afectaciones. Se reutiliza `guardar`, que obtiene CSRF y llama al cliente HTTP existente con cookies del mismo origen.

La confirmación visual solo se produce tras respuesta satisfactoria con ID y estados iniciales pendiente/pendiente. Presenta: «Ascenso institucional propuesto, pendiente de decisión pedagógica. No se modificaron inscripciones ni cupos». Un error no cierra el formulario ni confirma creación.

## 4. Seguridad y comportamiento ante errores

- El backend sigue siendo la autoridad de ámbito, secuencia, integridad y concurrencia. Las comprobaciones React solo previenen selecciones obsoletas o respuestas incompatibles; no conceden permisos.
- Se solicita exclusivamente información de contexto y niveles mínimos. No se consultan grupos ajenos, inscripciones globales, acudientes, valoraciones o expedientes de destino.
- El formulario explica que la referencia no limita la revisión global y que solo se muestra información del ámbito autorizado. No muestra cantidades ni detalles de las afectaciones internas ocultas.
- No existe selector de grupo destino para ascensos ni se hacen peticiones a endpoints de aprobación, ejecución o traslado por ese flujo.
- Mientras el envío está pendiente, un bloqueo síncrono evita doble submit, el formulario queda deshabilitado y tampoco permite cancelar o cambiar modalidad desde sus controles. La unicidad del backend sigue protegiendo otros clientes o reintentos posteriores.
- Antes del POST se pide confirmación explícita de que no se aprueba ni ejecuta nada. Cancelarla no envía la solicitud.
- Un 403/404 del contexto o referencia se muestra como error y no ofrece datos alternativos fuera de ámbito. El nivel puede reconsultarse mediante un botón; no hay reintentos automáticos de POST.
- Ante conflicto 409 se conserva la justificación y se muestra el mensaje del backend. Ante caída de red se advierte que el resultado puede ser incierto y se indica consultar el listado antes de reenviar.
- Si no hay disciplinas/referencias válidas, los selectores muestran vacío y no se puede enviar sin contexto. Si no existe un sucesor activo, se muestra «No disponible» y una explicación de que no se saltan niveles. Un destino de otra disciplina, un nivel no consecutivo o más de un candidato no se aceptan como selección válida.

## 5. Accesibilidad y diseño

Se conserva el diseño institucional. No se añadieron dependencias ni una renovación gráfica. El textarea reutiliza tipografía, colores, bordes y tamaños de los controles existentes; el formulario continúa con rejilla responsiva.

Se usan fieldset/legend, etiquetas para cada control, instrucciones asociadas con `aria-describedby`, salidas informativas etiquetadas, anuncio del nivel con `aria-live`, errores `role=alert` e indicadores `role=status`. La nueva tabla y su navegación de páginas tienen nombres accesibles propios.

## 6. Pruebas ejecutadas

Todas las solicitudes de prueba se simularon con fetch; no se enviaron a Django ni a PostgreSQL real. No fue necesario ejecutar pruebas backend con escrituras porque no hubo cambios backend. La validación previa de 348 pruebas backend corresponde a B2.1-A, no a una nueva ejecución de esta entrega.

| Comando en `frontend` | Resultado real |
| --- | --- |
| `npm.cmd test` | **107 pruebas aprobadas**, nueve archivos; ejecución final 14,48 segundos |
| `npm.cmd run test:api` | **6 pruebas aprobadas** del cliente HTTP: origen/cookies, CSRF, ingreso/salida y errores |
| `npm.cmd run build` | **Aprobado**, 72 módulos; ejecución final 5,69 segundos |

Se añadieron **19 casos** de interfaz de ascensos, incluyendo: tres modalidades y ausencia del tipo antiguo; contexto progresivo; payload exacto; doble envío pendiente; cambio de persona; respuesta tardía; falta de disciplinas/referencias; ausencia de sucesor; rechazo de nivel incompatible; permisos; reconsulta; conflicto; incertidumbre de red; validación accesible; confirmación cancelada; actualización de bandeja; IDs coincidentes entre historia y ascenso; filtro sin search; etiquetas/instrucciones/navegación.

Las regresiones de inscripción adicional y traslado siguen aprobadas. Dos pruebas antiguas que esperaban seleccionar un cambio de nivel individual ahora comprueban la nueva modalidad o la transición administrativa válida. La prueba de aprobación coordinadora existente se mantiene sobre un traslado administrativo del mismo nivel, sin fingir que se habilitó aprobación institucional.

No se afirma una verificación visual real con `profesor_prueba01` ni una prueba de POST contra datos reales. La cobertura automatizada de interfaz usa DOM simulado; la revisión responsiva en navegador queda para la sesión conjunta.

## 7. Archivos creados y modificados

Creados:

- `frontend/src/componentes/FormularioAscenso.jsx`
- `frontend/src/componentes/ListadoAscensos.jsx`
- `frontend/src/pruebas/AscensosInstitucionales.test.jsx`
- Este documento.

Modificados:

- `frontend/src/componentes/FormularioPropuesta.jsx`: tres modalidades y delegación del ascenso a su formulario.
- `frontend/src/componentes/Gestion.jsx`: búsqueda opcional en useListado, conservando el comportamiento predeterminado.
- `frontend/src/paginas/Propuestas.jsx`: bandejas separadas, mensajes históricos y actualización tras creación institucional.
- `frontend/src/estilos/_gestion.scss`: textarea coherente con controles existentes y fieldset del nuevo formulario.
- `frontend/src/pruebas/PropuestasTraslados.test.jsx`
- `frontend/src/pruebas/Fase3.test.jsx`

La compilación regeneró `frontend/dist`, artefacto de construcción. No se modificaron archivos backend, modelos, migraciones, roles, credenciales ni configuración sensible. No se hicieron commits ni push.

## 8. Verificación visual con profesor_prueba01

Para la revisión conjunta en la base real, limitarse a consultas y edición local del formulario; no registrar una propuesta real como prueba de esta entrega.

1. Con una sesión de profesor_prueba01 abierta por el usuario, entrar en `http://localhost:5173/profesor/propuestas`.
2. Confirmar que se distinguen historial administrativo y ascensos institucionales, cada uno con su tabla y paginación. Si no hay ascensos, debe aparecer el estado vacío, no un error por parámetro search.
3. Pulsar «Crear propuesta». Comprobar las tres modalidades y que «Cambio de nivel» no aparece como opción nueva.
4. Seleccionar «Ascenso institucional», un deportista ya visible, disciplina y una referencia activa propia. No crear ni ajustar inscripciones para obtener una opción.
5. Comprobar nivel de origen y nivel inmediatamente superior de solo lectura. No debe aparecer selector de grupo destino ni una opción para saltar niveles.
6. Cambiar persona o disciplina y verificar que se limpian las selecciones dependientes. Revisar instrucciones, cargas, mensajes y navegación con teclado.
7. Escribir una justificación solo para comprobar el campo/contador y pulsar **Cancelar**. No pulsar «Registrar propuesta de ascenso» en zona_bloque durante esta verificación de solo lectura.
8. Si existen registros históricos de nivel, confirmar la advertencia de deshabilitación y ausencia de aprobar. No pulsar cancelación/rechazo de registros reales como parte de esta prueba visual.
9. Revisar la disposición a 390 px y escritorio: etiquetas legibles, campos sin solaparse y tablas con desplazamiento horizontal cuando sea necesario.

La creación, el doble envío, los errores y la actualización de bandeja ya se probaron automáticamente con respuestas simuladas. Cualquier comprobación manual de POST debe hacerse en un entorno aislado o contar con una autorización distinta; no se introducen fixtures persistentes en la base real.

## 9. Límites y punto de parada

La revisión global del coordinador, las decisiones institucionales públicas, modificaciones del plan, excepciones, simulación de destinos y ejecución de traslados siguen fuera de esta etapa. Tampoco se implementan estudiantes nuevos, asistencia, sesiones, evaluaciones o IA.

Las pendientes antiguas pueden seguir bloqueando una propuesta institucional hasta su revisión administrativa autorizada; no se cancelan ni convierten por abrir esta interfaz. El nivel de origen es el derivado de la referencia, no un reconocimiento institucional independiente. La falta de un sucesor activo y la configuración de secuencia siguen resolviéndose definitivamente en Django.

La entrega se detiene para verificación visual conjunta. No se inicia B2.2 ni B3 sin autorización posterior.
