# Ascensos institucionales — Incremento 2, B2.1-A

Estado: backend implementado y probado; pendiente conectar React en B2.1-B. No se inicia revisión coordinadora B2.2 ni ejecución B3.

## 1. Alcance y arquitectura

Se revisaron el diseño de integración B2.1, el diseño institucional del Incremento 2, la implementación/aplicación B1 y el Incremento 1, además de modelos, servicios, serializers, rutas, permisos y pruebas existentes. Prevalecen las decisiones de este encargo sobre las alternativas pendientes del diseño anterior.

La API nueva utiliza `ProgresionInstitucional` y llama al servicio real `proponer_progresion(actor, referencia_id, nivel_destino, justificacion)`. No duplica la creación del agregado, afectaciones o eventos en las vistas. Se mantienen los modelos y las protecciones SQL de B1, incluida la prohibición de `ejecutado`.

No se añadieron dependencias, modelos, migraciones ni cambios de configuración general. No se modificó React. La única consulta a `zona_bloque` realizada en este encargo fue la lectura del catálogo de niveles dentro de una transacción READ ONLY, verificando previamente base y esquema. No se enviaron POST a producción, no se crearon progresiones reales ni se ejecutaron decisiones o traslados reales.

## 2. Endpoints y contratos

Se añade el registro `ascensos` al router DRF existente. Las respuestas de listado usan la paginación actual: `count`, `next`, `previous`, `results`, con 25 filas por página. No se permite sobrescribir el tamaño de página. Parámetros desconocidos o repetidos, páginas no positivas e IDs inválidos producen 400; una página inexistente produce 404.

### GET `/api/ascensos/contexto/`

Solo profesor activo. Parámetros:

| Parámetro | Requisito |
| --- | --- |
| `deportista` | ID interno obligatorio, resuelto dentro del ámbito vigente |
| `disciplina` | ID opcional para filtrar referencias propias |
| `vista` | `referencias` por defecto o `disciplinas` |
| `search` | Búsqueda opcional de hasta 120 caracteres |
| `page` | Entero positivo opcional |

Con vista referencias, cada resultado contiene el ID de la inscripción, deportista, disciplina/nombre, código/nombre del grupo propio, periodo/nombre, nivel de origen, nivel siguiente, posibilidad de proponer y aviso. Los metadatos de nivel son `id`, `codigo`, `nombre`, `disciplina`, `orden`.

Con vista disciplinas se devuelven únicamente ID, nombre y código de disciplinas obtenidas de referencias activas autorizadas del deportista. No se agrega oferta ajena para completar opciones.

El profesor debe seleccionar expresamente una referencia: el backend devuelve opciones, no elige `.first()` ni hace opcional ese campo en el POST. Alto rendimiento o un siguiente nivel desactivado producen referencia con `nivel_siguiente=null`, `puede_proponer=false` y explicación, sin saltar al posterior.

La búsqueda de referencias contempla código/nombre de grupo, nombre de nivel y periodo; la de disciplinas contempla nombre/código. Un deportista visible únicamente mediante una reserva puede devolver contexto vacío, porque no constituye una referencia activa para proponer.

### GET `/api/ascensos/niveles/`

Solo profesor activo. Requiere `deportista`, `disciplina` e `inscripcion_referencia`; admite `search` de hasta 120 caracteres y `page` positivo. La referencia debe pertenecer al deportista, disciplina y asignación vigente del solicitante.

Devuelve cero o un nivel: exclusivamente el inmediatamente superior activo. No exige que el profesor lo imparta ni que exista grupo de destino con cupo. No devuelve grupos, profesores, alumnado ni datos personales de ese nivel.

### GET `/api/ascensos/` y `/api/ascensos/{id}/`

Consulta mínima autorizada por rol. Filtros admitidos: `estado_decision` (`pendiente`, `aprobada`, `rechazada`), `disciplina`, `deportista`, `page`. No se acepta `search`, profesor ajeno, versión o estado arbitrario de plan como filtro.

- Profesor: solo progresiones propias con deportista y referencia todavía visibles en su ámbito vigente, reutilizando `progresiones_visibles`.
- Administrador y coordinador activo: lectura institucional mínima. No se incorpora aquí una API global del plan ni su pantalla de revisión.
- Actor inactivo o anónimo: denegado. Un profesor ajeno recibe listado vacío o 404 de detalle, sin identificar al autor del expediente.

La salida contiene ID, deportista/nombre, disciplina/nombre, referencia, niveles/nombres, periodo/nombre, justificación, fecha de creación y estados separados de decisión y plan. No contiene documentos, nacimiento, contactos, afectaciones, excepciones, resoluciones administrativas, versiones de auditoría ni grupos ajenos.

### POST `/api/ascensos/`

Solo profesor activo; no admite query params. Payload exacto:

```json
{
  "deportista": 9,
  "disciplina": 1,
  "inscripcion_referencia": 18,
  "nivel_destino": 3,
  "justificacion": "Justificación pedagógica y deportiva"
}
```

Los números ilustran el formato, no son una instrucción para enviar una propuesta sobre registros reales. Los IDs se obtienen de los selectores autorizados. La justificación es obligatoria, se recortan espacios extremos y admite hasta 500 caracteres. No se aceptan campos adicionales, incluyendo autor, responsable, periodo, nivel de origen, grupo destino, fecha efectiva, versión, estados, afectaciones o resolución.

El servidor comprueba que los IDs declarados correspondan a la referencia autorizada, y el servicio deriva la cabecera desde ella. Autor, marcas de tiempo, estados y afectaciones nunca se toman del cliente. Respuesta 201 con la proyección mínima descrita: decisión `pendiente`, plan `pendiente`.

No se crean inscripciones ni reservas, no se cambian grupos, cupos, fechas o niveles reconocidos. La intención pedagógica puede registrarse el día del ingreso porque no cierra ningún tramo; la restricción temporal de los traslados administrativos permanece intacta.

### Acciones deliberadamente ausentes

No hay endpoints de aprobar, rechazar, revocar, editar planes, excepciones o ejecutar progresiones. Intentar esas subrutas devuelve 404; PATCH/DELETE no son métodos habilitados. No se expone un CRUD genérico. Los servicios internos de decisión B1 no se convierten en API pública en esta etapa.

## 3. Autorización y privacidad

Se conserva autenticación por sesiones Django y CSRF. La clase específica `AccesoAscensos` aplica el rol antes del tratamiento de entrada; `AccesoFase3` conserva las comprobaciones existentes de autenticación y esquema.

`referencias_docentes` reutiliza `inscripciones_visibles`, restringe a estado activa y exige persona, nivel y disciplina activos; el ámbito existente verifica grupos/periodos vigentes y asignación docente. Los POST resuelven primero la referencia mediante un queryset autorizado, rechazando referencias ajenas, suspendidas, futuras o incoherentes sin revelar su existencia.

El profesor puede proponer usando una referencia propia aunque B1 capture internamente otras inscripciones de la misma persona/disciplina. Estas afectaciones no aparecen en la respuesta 201 ni en sus consultas. El contexto muestra solo referencias propias y un aviso general; no devuelve siquiera un conteo global de inscripciones ocultas. No se amplió la consulta ordinaria de grupos ni el catálogo general de niveles.

Se usa la autoridad vigente del coordinador definida por B1 para la lectura institucional, sin conceder al administrador una autoridad pedagógica adicional. No se crearon permisos de modelo ni se asignaron privilegios nuevos; las restricciones son de dominio en backend.

## 4. Orden pedagógico comprobado

La migración histórica `organizacion.0002_catalogos_iniciales` y una consulta real de solo lectura coinciden:

| Código estable | Nombre institucional | `orden` |
| --- | --- | ---: |
| ludico | Lúdico | 1 |
| nivel-1 | Nivel 1 | 2 |
| nivel-2 | Nivel 2 | 3 |
| especializacion | Escuela de especialización semicompetitiva | 4 |
| alto-rendimiento | Alto rendimiento | 5 |

`nivel_inmediatamente_superior` comprueba códigos y orden de la disciplina contra esa secuencia, no IDs ni nombres de presentación. Una configuración incompleta, con órdenes repetidos, alterados o niveles adicionales no definidos en esta secuencia falla de forma cerrada con 409 y solicita revisión. No se renombra ni ordena el catálogo automáticamente.

No se ofrecen saltos, retrocesos ni mismo nivel. Si el siguiente está inactivo no se pasa al siguiente activo. Otra disciplina se rechaza. La última posición no tiene superior. Los grados/colores de escalada no participan.

La validación se incorporó al servicio B1 de propuesta, dentro de la transacción y después de bloquear/releer usuarios; el nivel destino se relee desde PostgreSQL, sin confiar en el objeto validado antes de adquirir el bloqueo. También se aplica a contexto y catálogo docente. No se añadió una restricción SQL nueva a la migración aplicada: la regla consecutiva se impone en el servicio y la API; B1 conserva sus restricciones SQL de coherencia y unicidad.

Una disciplina futura necesita configurar esta misma secuencia institucional antes de admitir propuestas. Cambiar la secuencia aprobada exige revisión posterior; no se deduce una regla nueva por añadir un registro de catálogo.

## 5. Transacción, duplicados y afectaciones

Se mantiene `proponer_progresion` como única creación de dominio. Conserva bloqueos globales de usuarios y del deportista, validación de referencia, persona/estructura activas y generación de afectaciones/eventos. `relevantes()` mantiene inclusión de activas, suspendidas con o sin reserva y futuras abiertas de la disciplina cuyo periodo no haya terminado. No se limita al periodo de referencia ni a grupos del proponente.

Se añade conflicto explícito 409 cuando existe progresión pendiente o aprobada de la misma persona/disciplina. La unicidad SQL `ascenso_abierto_unico` sigue siendo la defensa final. Su IntegrityError específico se traduce fuera de un savepoint; otros errores no se confunden con un duplicado ni se utiliza una transacción rota.

Una propuesta antigua tipo nivel pendiente sigue bloqueando el alta institucional con mensaje administrativo. No se cancela, transforma ni resuelve automáticamente. El segundo profesor no recibe ID, autor o contenido de un expediente ajeno al producirse un conflicto.

El POST crea únicamente progresión, afectaciones y auditoría autorizadas. La prueba concurrente con dos profesores y referencias distintas confirma un 201 y un 409, un agregado y todas sus afectaciones, sin crear inscripciones. No se sustituye esta protección por deshabilitar un botón en React.

## 6. Bloqueo del mecanismo antiguo

`bloquear_nivel_antiguo` centraliza la respuesta 409: mecanismo deshabilitado, conservación histórica y necesidad del nuevo procedimiento.

- Creación antigua: `proponer` bloquea tipo nivel antes de escribir o validar destinos operativos.
- Consulta antigua de destinos: `contexto_docente` bloquea nivel. Se retiró la rama ya inalcanzable de ascenso individual para no mantener una segunda política.
- Aprobación antigua: `resolver` mantiene la comprobación de autoridad y bloquea aprobar nivel antes de llamar a `contexto`, procesar reservas o ejecutar movimientos.
- Servicio individual: `trasladar_bajo_bloqueo(... permite_nivel=True)` también rechaza la operación. Con False conserva la exigencia de mismo nivel; la ruta HTTP de traslado no permite eludirla.

Se conserva lectura histórica, rechazo y cancelación motivados con los permisos anteriores. No se cambian estados de registros existentes por el despliegue. Las respuestas antiguas añaden `mecanismo_deshabilitado` y `aviso_procedimiento`, de solo lectura, para que B2.1-B distinga estos registros sin reinterpretar su historia. No se modifican choices del modelo ni se elimina `tipo='nivel'`.

Inscripción adicional y traslado al mismo nivel siguen usando los servicios y payloads anteriores. Se mantienen sus límites temporales, cupos, reservas, compatibilidad horaria, historial y autoridad administrativa.

## 7. Pruebas ejecutadas

Todas las escrituras de prueba se ejecutaron en clústeres PostgreSQL efímeros independientes mediante `scripts/pruebas_postgresql_aisladas.py`. El ejecutor verifica puerto, directorio de datos y PID antes de configurar la conexión y Django crea una base de nombre único. No utiliza `zona_bloque` para esas escrituras.

| Verificación | Resultado real |
| --- | --- |
| Pruebas focalizadas nuevas de API | 29 aprobadas, 6,979 segundos |
| Regresión completa backend | **348 aprobadas**, 65,133 segundos |
| Comprobación Django en ejecución completa | Sin incidencias |
| `makemigrations --check --dry-run` aislado | `No changes detected`; no se generaron archivos |
| Archivo B1 ya aplicado | SHA-256 intacto: `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f` |

Evidencia privada de ejecución completa: `respaldos/pruebas_fase3_o_cdvncx/`, puerto 53773; clúster detenido y base Django de pruebas destruida. Ejecución focalizada: `respaldos/pruebas_fase3_c3d696vy/`, puerto 61511. Son artefactos de pruebas, no respaldos de producción.

Las 29 pruebas añadidas cubren los veinte puntos del encargo: contexto propio; pérdida de asignación; persona ajena; referencias múltiples obligatorias; nivel no impartido; IDs que no siguen orden pedagógico; niveles iguales/no consecutivos/ajenos/inactivos; configuración ambigua; última posición; referencia suspendida; afectaciones de reservas y futuros invisibles; privacidad de respuestas; creación pendiente; intención del mismo día; inyección y justificación; parámetros/paginación/búsqueda; duplicados y concurrencia; lectura por roles; pérdida posterior de ámbito; inactividad; ausencia de rutas decisorias; CSRF; historia antigua; bloqueo antiguo y preservación operativa.

La suite anterior se mantiene con expectativas actualizadas únicamente donde se retiró el cambio individual: las pruebas históricas ahora crean fixtures antiguos en la base aislada y comprueban rechazo de ejecución, conservación del estado y mensajes. Se conserva el control temporal del traslado al mismo nivel. No se siguió creando tipo nivel por su endpoint deshabilitado para preparar fixtures.

El fixture común de Fase 3 configura los cinco niveles con sus órdenes también después de los flush de TransactionTestCase; no modifica catálogos reales. La regresión incluye las pruebas SQL de B1, su aplicación/reversión aislada, historial de excepciones, bloqueo de ejecutado y concurrencia anterior.

No se ejecutaron pruebas con escrituras ni migraciones en producción. No se repitieron frontend/build en esta entrega exclusivamente backend ni se afirma una integración visual nueva.

## 8. Archivos creados y modificados

Creados:

- `backend/inscripciones/consultas_ascensos.py`: contexto autorizado y regla consecutiva compartida.
- `backend/inscripciones/serializers_ascensos.py`: entradas/query params estrictos y salida mínima.
- `backend/inscripciones/views_ascensos.py`: consultas y creación sin acciones decisorias.
- `backend/inscripciones/test_api_ascensos.py`: 29 regresiones REST y concurrencia.
- Este documento.

Modificados:

- `backend/inscripciones/servicios_ascensos.py`: consecutividad, relectura del destino y duplicado explícito; reutilización de ámbito.
- `backend/inscripciones/compatibilidad_propuestas.py`: cierre centralizado de nivel antiguo.
- `backend/inscripciones/servicios.py`: bloqueo de creación/aprobación y ejecución individual antigua.
- `backend/inscripciones/serializers.py`: indicación histórica de mecanismo deshabilitado.
- `backend/inscripciones/urls.py`: registro de ascensos en router.
- `backend/inscripciones/test_propuestas_traslados.py` y `tests.py`: actualización de las expectativas sustituidas por el corte institucional.
- `backend/inscripciones/test_ascensos_b1.py`: expectativa de duplicado específico 409.
- `backend/deportistas/tests.py`: catálogo institucional completo en fixtures aislados.

No se modificaron modelos, migraciones, frontend, credenciales, roles ni configuración general de seguridad.

## 9. Riesgos, límites y conexión B2.1-B

1. El frontend actual todavía ofrece la opción antigua; al usarla recibirá el mensaje de deshabilitación. Es el corte deliberado del backend hasta autorizar B2.1-B, no una aprobación institucional ejecutable.
2. B2.1-B debe seleccionar explícitamente referencia y usar el contexto con `vista=disciplinas` y después referencias filtradas. No asumir un nivel institucional independiente: se muestra el nivel derivado de la referencia.
3. El catálogo de niveles requiere los tres IDs de contexto y devuelve solo el sucesor. Reiniciar selectores/cachés al cambiar persona/disciplina/referencia. No usar una recuperación de detalle que elimine esos parámetros: no existe `/ascensos/niveles/{id}/`.
4. La creación lleva cinco campos exclusivamente. No enviar los campos ocultos del formulario antiguo, versión o fecha efectiva. La respuesta no contiene plan global; no reconstruirlo mediante consultas a grupos ajenos.
5. Mantener listas y claves separadas para `Propuesta` y `ProgresionInstitucional`; no aplicar botones antiguos de aprobar/cancelar a un ID institucional. Usar estado_decision y estado_plan como conceptos distintos.
6. Las pendientes antiguas deben revisarse/cerrarse humanamente mediante permisos existentes. No se transforman ni se liberan automáticamente por este despliegue.
7. Una progresión aprobada continúa abierta y bloquea otra de la disciplina en B1. No se añade cancelación, sustitución o ejecución para sortear ese estado.
8. No hay simulación de destinos, cupos por sesión ni plan individual de días. La aprobación institucional futura B2.2 debe revalidar permisos y la política consecutiva vigente, además del conjunto y versiones, antes de decidir. No se habilitó su API en esta etapa.
9. La privacidad no depende de React: incluso mediante GET directo se excluyen las afectaciones ajenas. Los errores no devuelven documentos ni referencias de expedientes ocultos. El conflicto por propuesta abierta sí informa genéricamente que coordinación debe revisar la disciplina.
10. No hay migraciones nuevas o pendientes generadas por B2.1-A. Se conserva el archivo auditado B1; cualquier cambio de esquema futuro requiere autorización separada.

Se detiene la entrega para revisión de B2.1-A. No se realizaron commits ni push, no se conectó React y no se inició B2.1-B ni B2.2.

## 10. Reanudación segura: revisión y nueva verificación

La reanudación encontró completos los módulos, las rutas y las 29 pruebas API ya descritas. Se inspeccionaron los nueve archivos indicados en el encargo, los bloqueos de servicios y serializers y este informe antes de actuar. No se reinició la implementación ni se sobrescribieron decisiones previas. La revisión y la nueva ejecución no identificaron errores que requirieran cambios de código.

| Requisito de la reanudación | Estado comprobado |
| --- | --- |
| Backend existente y contratos | Conservados; ninguna implementación duplicada |
| Permisos efectivos y privacidad | Revisados y cubiertos por la suite: ámbito vigente, roles, pérdida de asignación, CSRF y exclusión de afectaciones ajenas |
| Progresión consecutiva | Códigos y campo orden validados contra la secuencia institucional; los IDs solo identifican registros, no determinan el orden |
| Cierre del mecanismo antiguo | Creación, consulta de destinos y aprobación de tipo nivel rechazadas; servicio individual con permite_nivel también bloqueado |
| Historia anterior | Conservada, con indicación de mecanismo deshabilitado; sin conversiones ni cancelaciones automáticas |
| Integridad operativa | Pruebas de filas completas antes/después conservan inscripciones, cupos, grupos, reservas y eventos anteriores |
| Suite completa backend repetida | **348 pruebas aprobadas**, 63,882 segundos |
| Comprobación Django | Sin incidencias |
| makemigrations --check --dry-run | **No changes detected**, ejecutado dentro del clúster aislado; sin archivos de migración generados |

Nueva evidencia privada: `respaldos/pruebas_fase3_hwgar67z/`, puerto temporal **65336**. El ejecutor verificó directorio de datos y PID antes de usar la conexión; Django creó/destruyó su base de prueba única y el clúster quedó detenido. Se deshabilitó expresamente la opción de generación de migraciones del ejecutor para esta comprobación.

Se tomaron y compararon huellas SHA-256 al inicio y al final de **69 archivos**: los nueve archivos backend solicitados, fuentes de React y migraciones existentes. Ninguno cambió. En esta reanudación solo se actualizó este informe entre los archivos de código/documentación; los artefactos de pruebas permanecen en el directorio privado de respaldos. No se consultó ni escribió `zona_bloque`.

No quedan tareas backend B2.1-A identificadas como incompletas. Siguen fuera del alcance la conexión React B2.1-B, la revisión/aprobación coordinadora B2.2 y la ejecución B3. Permanecen los límites del apartado 9, especialmente el catálogo institucional estricto y la deshabilitación del formulario antiguo hasta conectar la nueva interfaz. Se detiene nuevamente para revisión, sin commits ni push.
