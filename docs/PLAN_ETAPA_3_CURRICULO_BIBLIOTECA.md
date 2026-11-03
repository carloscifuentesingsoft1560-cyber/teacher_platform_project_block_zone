# Plan técnico de Etapa 3 — Currículo y biblioteca

Versión de diseño 1.0, 2026-11-02. **Propuesta para aprobar implementación; nada de este módulo está implementado.** Se trabaja en la copia de integración, sin alterar originales, datos operativos o remoto. No se crean modelos, endpoints, pantallas o migraciones en esta entrega. La activación operativa de Etapa 2 continúa pendiente, pero el diseño y desarrollo aislado de Etapa 3 pueden apoyarse en su núcleo ya ensayado.

## 1. Decisiones de continuidad y límites

Se reutilizan Django/DRF/PostgreSQL, React/Vite/Sass, sesión/CSRF, `Usuario`, `Persona`, roles vigentes y `puede`, `Disciplina`, `Nivel`, `Grupo`, `Asignacion`, `Inscripcion`, auditoría y patrón de conflictos por versión. No hay todavía mallas, biblioteca, sesiones ni almacenamiento privado común: se propone crearlos sin duplicar personas, niveles, grupos o bloques.

Se proponen tres límites Django: `recursos` para archivos privados y procedencia documental, `curriculo` para mallas y extracción revisada, `biblioteca` para ejercicios y materiales docentes. `recursos` no gestionará deportistas, autorizaciones clínicas o captura audiovisual; ofrecerá posteriormente el mismo almacenamiento y control de descarga a esos módulos, que conservarán sus propios permisos y finalidades. No crear una nueva plataforma ni servicios externos obligatorios.

Las versiones curriculares se aprueban como contenido, no como autorización previa de cada sesión. El profesor podrá preparar actividades propias dentro de su ámbito sin aprobación universal. No se incorporan motores de evaluación, planificación, RSD, Route Setting, captura de deportistas ni IA. No se usa dificultad/color/RIC como carga o nota curricular.

## 2. Fuentes revisadas y reconciliación

Las cuatro mallas originales disponibles son **cuatro hojas de un único archivo**: `docs/referencias/ESTRUCTURA ACTUALIZACIÓN MALLAS CURRICULARES (1) (1) (1).xlsx`, SHA256 `3dd3f805d072ef726193ea5966d82836d48949a9171b66cfa31273ce0318efb2`. No se afirman cuatro archivos independientes. Se leyó OOXML sin recálculo, exportación o cambios; el mapeo nuevo se limita al diseño de importación y no repite auditorías de seguridad o pruebas completas ya documentadas.

| Hoja exacta | Cabeceras de fase | Datos de fase, incluyendo columna H | Semanas por fase | Clases por fase | Combinaciones |
|---|---|---|---|---|---:|
| LUDICO | A4 / A50 / A96 | A10:H49 / A56:H95 / A102:H181 | 10 / 10 / 20 | 20 / 20 / 40 | 230 |
| NIVEL 1 | A4 / A66 / A128 | A10:H65 / A72:H127 / A134:H181 | 14 / 14 / 12 | 28 / 28 / 24 | 230 |
| NIVEL 2 | A4 / A66 / A128 | A10:H65 / A72:H127 / A134:H181 | 14 / 14 / 12 | 28 / 28 / 24 | 238 |
| ESPECIALIZACION SEMICOMPETITIVA | A4 / A66 / A128 | A10:H65 / A72:H127 / A134:H181 | 14 / 14 / 12 | 28 / 28 / 24 | 230 |

Cada hoja contiene 40 semanas y 80 clases numeradas; no se encontraron fórmulas en estas cuatro hojas. Eso no valida sus contenidos metodológicos. Los recuentos de semanas no son semanas de calendario fechadas ni sesiones efectivamente ejecutadas.

Mapeo semántico propuesto, con confirmación humana:

- A2/A3: disciplina/nombre en fuente; enlazar a códigos existentes mediante mapa explícito, sin crear niveles por diferencias ortográficas.
- A4 y equivalentes: fase. G5:H5 y equivalentes: objetivo general de fase; H6/H7/H8: objetivos motriz/lúdico/cognitivo. Preservar texto, espacios y erratas en fuente.
- A10:A13: semana 1. B10:B11: clase prevista 1; B12:B13: clase prevista 2. Resolver la pertenencia usando el rango combinado, no rellenar todas las celdas como registros nuevos.
- G10:G11: tema de la clase 1. H10/H11: dos enunciados de desempeño distintos; no son dos clases ni necesariamente dos competencias autónomas.
- C10:C49 en LUDICO y C10:C65 en NIVEL 1: dimensión motivacional de fase; D/E/F corresponden a desarrollo personal, ciudadanía y convivencia. Su alcance debe permanecer de fase, sin copiar el párrafo como una competencia nueva por cada fila.
- Anotaciones laterales I–M y metadatos: conservar en custodia de origen y mostrar solo a revisores cuando proceda; marcas “ok”, nombres o notas no demuestran aprobación. No volcarlas en el catálogo docente.

Hallazgos para revisión curricular, sin corregir originales: NIVEL 1!G5 es una instrucción pendiente de completar; Especialización combina objetivos generales básicos con temas avanzados; NIVEL 2!G5/H6 menciona dificultad aunque el inventario institucional documenta boulder. No convertir esas referencias en autorización para actividades con cuerda. Los términos psicosociales se conservan como objetivos de observación, sin diagnósticos o puntuaciones psicológicas.

Se reutilizan `CONTRATOS_COMPARTIDOS_FUTUROS.md`, `RECONCILIACION_VIGENTE_2026_11.md`, F03/F04/F05 y el paquete de investigación. Las frases de Etapa 1 que describen identidad/roles como futuros son históricas: en integración ya existen los incrementos 2A–2E, sin implicar activación operativa. F04 propone validación del coordinador; se conserva para contenido de biblioteca, no para sesiones ordinarias. Sus estilos descriptivos se distinguen de los cuatro estilos institucionales del maestro.

Los 224 registros son candidatos mixtos, no 224 ejercicios únicos aprobados; el piloto de 16 se solapa y el manual contiene 12 fichas. No se importan ni habilitan. La revisión ya documentada de las 42 hojas de `Valoraciones formuladas  (1).xlsx` se reutiliza: no se reevalúan sus fórmulas ni se trasladan porcentajes, denominadores o ascensos al 80 %. No se afirma validación de las páginas de PDF ausentes.

Babys: programa propuesto sin malla original; observación mediante juego y duración orientativa 40–45 min, sin máximos. Alto Rendimiento: planificación individual sin original curricular comprobado. No se inventan 40 semanas/80 clases para ninguno. Lúdico: aproximadamente 60 min y criterio conservador para primera infancia. Especialización conserva currículo y futura periodización sobre una sola sesión canónica.

## 3. Identidad, versiones y estados

Separar tres ejes:

1. `naturaleza`: `original_institucional`, `propuesta_revisada`, `adaptacion_docente`. Describe procedencia, no aprobación.
2. `estado_editorial`: `borrador`, `en_revision`, `aprobado`, `retirado`. La extracción original se conserva aparte y no se marca aprobada automáticamente.
3. `visibilidad`: `privado_autor`, `revision_institucional`, `catalogo_docente`. No hay visibilidad pública o portales de menores en esta etapa.

Cada identidad estable tiene UUID público/código y revisiones con PK propias. Cada revisión tiene `numero`, `revision_concurrencia`, creador/fecha, `derivada_de`, motivo de cambio cuando corresponda, revisor y decisión. La revisión de concurrencia de un borrador no es el número de edición publicada. Original fuente, revisión y decisión de aprobación se conservan sin sobrescribirlas.

MallaVersion es una instantánea agregada: al crear una edición se copian sus hijos con nuevas PK, preservando `clave_logica` UUID para comparar el mismo concepto entre ediciones. Una clave lógica no es FK a “la última versión”. No se crea un repositorio global de competencias duplicando o desvinculando textos de su malla.

Contenido aprobado y fuente importada son inmutables. Una corrección crea nueva edición; retiro conserva consulta histórica autorizada, pero impide selección para uso futuro. Los eventos editoriales y la vigencia de catálogo se guardan fuera del contenido congelado. Una corrección de seguridad puede retirar inmediatamente una versión, sin alterar referencias históricas ni garantizar que una actividad sea compatible con cada deportista.

Propuesta de autoridad: coordinador institucional único revisa y aprueba/publica currículo y biblioteca mediante un comando; administrador gestiona acceso y puede retirar por razón administrativa/seguridad, pero su rol no concede aprobación metodológica. Profesor crea/revisa sus borradores y propone contenido; routesetter puede proponer ejercicios propios de su ámbito técnico. Estas facultades nuevas se implementarán explícitamente, no mediante `is_staff` o el rol principal. Aprobar este plan aprueba este reparto propuesto, no contenido científico alguno.

## 4. Modelos propuestos y relaciones

Campos comunes de identidad/versionado se especificarán por modelos concretos; evitar un modelo genérico de permisos o GenericForeignKey que dificulte aislamiento. FKs históricas con PROTECT; fechas con zona y día institucional America/Bogota. Textos de fuente separados de textos editados. JSON se limita a extracción, localizadores o parámetros variables validados; las relaciones de negocio no quedan ocultas en JSON.

### 4.1 Recursos, fuentes y extracción

| Modelo propuesto | Campos y relaciones principales | Integridad |
|---|---|---|
| ArchivoPrivado | UUID, clave de almacenamiento opaca, SHA256, bytes, tipo/firma verificados, autor, fecha, estado cuarentena/disponible/rechazado, finalidad y retención | Blob inmutable; ruta nunca tomada del nombre del usuario; sin URL pública. Hash no concede autorización ni deduplica permisos entre contextos |
| FuenteDocumento | Identidad bibliográfica/institucional, título, autoría autorizada, tipo de fuente | No es archivo ni aprobación; sin datos personales innecesarios |
| FuenteVersion | Fuente, número, ArchivoPrivado opcional, hash, referencia/URL externa, fecha, licencia/derechos y disponibilidad de revisión | Bytes/localizador fijados; corrección crea otra versión; no descargar URL automáticamente |
| FragmentoFuente | FuenteVersion, hoja exacta/parte OOXML y celda/rango o página/sección/registro CSV, ancla combinada, texto original, fórmula opaca y valor cacheado si existen | Unicidad fuente+localizador canónico; no recalcular fórmulas; distinguir vacío, texto y número |
| LoteImportacion | FuenteVersion, perfil de mapeo/version/hash, actor, clave idempotente, estado extraído/revisado/confirmado/fallido | Misma fuente+mapa+clave no duplica; no crea contenido aprobado |
| PropuestaMapeo | Lote, FragmentoFuente, tipo destino propuesto, contexto fase/semana/clase, transformación, estado y observación del revisor | Resolver ambigüedades antes de confirmar; conservar fragmentos no mapeados sin convertirlos en competencias |

`ArchivoPrivado` es una identidad de blob: cada nueva edición de un material apunta a otro archivo, no sobrescribe el anterior. FuenteVersion y MaterialDocenteVersion pueden referenciar el mismo blob autorizado sin duplicar almacenamiento; la descarga valida el contexto de cada referencia. No hay deduplicación que revele si otro usuario tiene el mismo archivo.

### 4.2 Currículo

| Modelo | Campos/relaciones | Reglas |
|---|---|---|
| ProgramaFormativo | UUID/código, Nivel existente protegido, modalidad curricular/mixta/individual, estado de formalización y descripción | Un programa por Nivel en esta etapa; Disciplina se obtiene de Nivel. Nombre visible no es clave |
| Malla | UUID/código, ProgramaFormativo, propósito | Identidad estable; varias líneas de malla posibles con elección explícita, no “una malla por grupo” |
| MallaVersion | Malla, número, naturaleza, estado/visibilidad, derivada_de, semanas/clases esperadas opcionales, fuente principal, metadatos de revisión | Original y propuesta no se confunden; solo edición aprobada elegible como catálogo |
| FaseCurricular | MallaVersion, clave_logica, código exploracion/apropiacion/dominio u otro documentado, orden, nombre | Orden único por versión; no es mesociclo deportivo |
| SemanaCurricular | MallaVersion, FaseCurricular, clave_logica, ordinal global, ordinal en fase | Unicidad por versión+ordinal global; pertenencia a misma versión |
| ClasePrevista | SemanaCurricular, clave_logica, ordinal global y orden semanal | Son posiciones curriculares, no Sesion/Horario/asistencia; no genera calendario |
| ElementoCurricular | MallaVersion, clave_logica, tipo competencia/objetivo/contenido/desempeno, texto editado, dimensión y subdimensión opcional, padre opcional | Padre de misma versión, sin ciclos; objetivo general puede existir sin competencia inventada |
| UbicacionCurricular | Elemento, alcance malla/fase/semana/clase y FK concreta correspondiente, orden | Una sola granularidad por fila; varias ubicaciones legítimas sin duplicar elemento; misma versión en todas las referencias |
| ProcedenciaCurricular | FragmentoFuente, exactamente uno de versión/fase/semana/clase/elemento, tipo copia/adaptacion/sintesis y explicación | Varias fuentes por elemento y varios elementos por fragmento; no usar relación genérica sin FK |
| ActividadCurricular | Elemento o ClasePrevista (exactamente uno), EjercicioVersion, finalidad/orden | Solo enlaza versiones concretas visibles y elegibles; no inventa ejecución ni dosificación individual |

Dimensiones iniciales: motriz, cognitiva, lúdica, técnica, táctica, psicosocial. Motivación, desarrollo personal, ciudadanía y convivencia son subdimensiones conservadas, sin convertirlas automáticamente en escalas. Otros términos necesitan registro explícito, no puntuaciones inferidas.

No crear InstrumentoEvaluacion operativo en Etapa 3. Un desempeño puede llevar `descripcion_instrumento_propuesto` y procedencia como texto no ejecutable; se migrará mediante relación explícita a Protocolo/InstrumentoVersion de su etapa, sin crear protocolos aprobados o FKs a tablas inexistentes.

### 4.3 Biblioteca y materiales

| Modelo | Campos y relaciones principales |
|---|---|
| Ejercicio | UUID/código, autor propietario, alcance privado/institucional; identidad estable |
| EjercicioVersion | Ejercicio, número, naturaleza/estado/visibilidad, nombre, Disciplina, modalidad, objetivo, metodología, descripción, organización, población, edades orientativas opcionales, desarrollo/prerrequisitos, duración_min/max en minutos opcional, supervisión, riesgos y controles, fuentes, revisión |
| PasoEjercicio | Versión, orden, fase/instrucción, duración orientativa opcional; no ejecución individual |
| AdaptacionEjercicio | Versión, población/condición documentada, alternativa y límites; sin diagnóstico ni deportista |
| TerminoActividad | namespace+código, nombre, activo: capacidad, estilo, movimiento, geometría, implemento, instalación, exigencia funcional. Catálogo semántico compartible, no catálogos de muros/presas/bloques |
| EtiquetaEjercicio | EjercicioVersion+TerminoActividad únicos; precisión/origen de etiqueta cuando es propuesta |
| ProgramaEjercicio | Versión+ProgramaFormativo únicos; pertinencia, prerrequisitos y limitaciones; nivel por Programa, sin duplicarlo |
| ExigenciaEjercicio | Versión, término funcional, operador/unidad/valor cuando aplica y explicación; información conocida/desconocida/pendiente_revisión, sin porcentajes de seguridad |
| ProcedenciaEjercicio | EjercicioVersion+FragmentoFuente, tipo de adaptación, licencia y limitaciones |
| MaterialDocente | Identidad UUID/código, autor/custodia y alcance |
| MaterialDocenteVersion | Material, número, título/resumen, tipo, ArchivoPrivado o referencia externa (exactamente uno), naturaleza/estado, licencia/derecho de uso, revisión, público docente pertinente |
| MaterialEjercicio | EjercicioVersion+MaterialDocenteVersion+finalidad; mismo permiso no se deduce de la relación |

Población es contexto y no diagnóstico: conservar edad o rango sin inventar maduración, intensidad o aptitud. Dosis sugeridas, si se incluyen, son parámetros por tipo/unidad (minutos, repeticiones, series, intentos, descanso), cada uno con fuente y carácter orientativo; no computar carga fisiológica. Duración desconocida es null, no cero. Recurso audiovisual docente debe ser propio/licenciado y autorizado; no aceptar vídeos identificables de menores como atajo para captura deportiva.

Taxonomía: estilos institucionales físico, eléctrico, coordinativo y técnico/equilibrio; capacidades como potencia o resistencia van en otro namespace. Movimiento y geometría reutilizarán códigos en futuro Route Setting, sin crear otra entidad Bloque. No convertir etiquetas históricas a estilos equivalentes sin mapa revisado. Implemento físico (banda/colchoneta) no es MaterialDocente (manual/vídeo).

### 4.4 Eventos, decisiones y restricciones de base

Cada agregado curricular/ejercicio/material tendrá su evento editorial concreto con actor, fecha, transición, edición y motivo proporcional; transacción conjunta con decisión. Reutilizar `auditoria.servicios.registrar` para la traza mínima existente, sin guardar documentos o datos sensibles en `CambioAdministrativo`. Eventos inmutables; idempotencia por actor+acción+objeto+UUID y hash canónico de payload. Reintento revalida permisos.

Modelos de apoyo explícitos: `EventoMalla`, `EventoEjercicio`, `EventoMaterial` para transiciones; `PublicacionMalla`, `PublicacionEjercicio`, `PublicacionMaterial` para versión publicada, inicio/fin de vigencia y decisión; `ComandoMalla`, `ComandoEjercicio`, `ComandoMaterial` para clave/hash/resultado confirmado sin payload sensible. Cada publicación pertenece a la misma identidad que su versión. El reemplazo cierra vigencia previa y abre la nueva atómicamente; su evento conserva la aprobación, aunque más tarde se retire. `ProgramaMaterial` enlaza la edición documental y programas destinatarios sin duplicar sus niveles. No derivar acceso institucional solo de que el archivo exista.

Restricciones PostgreSQL previstas: códigos y números únicos por identidad, ordinales positivos, edad/duración mínima ≤ máxima cuando ambas existen, coherencia de estado/revisor/fecha, unicidad de enlaces, exclusividad de destinatario/localizador, PROTECT de historia e índices de alcance/estado/disciplina/programa. Una sola versión de catálogo vigente por malla/ejercicio/material, con índice parcial en su registro de vigencia. Nueva aprobación puede sustituir la vigente bajo bloqueo; no reescribe ediciones previas.

Las invariantes entre filas —mismo MallaVersion, padre sin ciclo, edición congelada y alcance— no pueden atribuirse a un CheckConstraint con joins. Se validarán en servicios y, para integridad crítica, mediante triggers/restricciones diferibles revisados en PostgreSQL; pruebas SQL directas y carreras concurrentes. Unicidad/CheckConstraint sí cubren lo local. Bloqueo: autoridad vigente → identidad agregada → revisión → hijos, orden estable; coordinar con el orden de cuentas ya usado en Etapa 2 para evitar deadlocks.

## 5. Importación segura: original → propuesta → aprobación

1. Archivo privado en cuarentena, límites de tamaño/expansión ZIP/hojas/celdas, tipo real y hash. Rechazar macros y enlaces externos activos; no evaluar fórmulas ni resolver recursos remotos. Fuente idempotente por bytes e identidad bibliográfica revisada, sin atribuir autoría automática.
2. Extraer a staging las cuatro hojas esperadas con perfil de mapeo versionado. Registrar hoja, celda/rango, ancla, tipo, texto y digest. Nombres, notas laterales, revisiones y celdas ocultas quedan separados como contexto restringido. Ausencia de `dimension` en OOXML no es error: recorrer celdas reales con límites.
3. Vista previa por hoja/fase/semana/clase. Resolver A/B/G combinadas sin multiplicar registros; mostrar relación de H10/H11 a una clase. No dividir C–F por saltos de línea en competencias. Un revisor puede proponer una competencia a partir de desempeños con derivación explícita; no afirmar que estaba en la fuente.
4. Señalar placeholders, notas, ambigüedades, clases repetidas y temas fuera de instalaciones. Confirmación crea versión `original_institucional` de archivo conceptual de consulta, no seleccionable como catálogo si no está aprobada. No “arreglar” textos originales ni marcar “ok” como aprobación.
5. Crear una propuesta derivada editable; cada cambio mantiene enlace al fragmento original y la decisión. Confirmar no publica. Coordinador revisa contenido/seguridad y aprueba una versión explícita; software verifica integridad, no validez científica.
6. Repetir mismo lote+mapa+clave produce el mismo resultado, no otra malla. Cambiar perfil de mapeo requiere nuevo lote con diff; mismo nombre de archivo con hash distinto no reemplaza fuente. Un cambio de solo nombre con mismos bytes no reimporta automáticamente.

No hay carga de 224 candidatos en estas operaciones. Si se aprueba después un flujo de candidatos, será staging separado y optativo, con CSV fila/ID/página/procedencia y revisión de duplicados; nunca una migración de datos masiva ni publicación de ejemplos de F04.

## 6. Acciones, permisos y API propuesta

Todas las rutas siguientes son nuevas y propuestas. UUID público, paginación y filtros por ámbito en queryset y detalle; fuera de ámbito 404, acción sin facultad 403, CSRF de sesión vigente, datos estrictos 400, versión obsoleta/clave incompatible 409. No aceptar actor/fecha/aprobación desde React. Materiales/archivo nunca devuelven claves de disco.

| Acción | Profesor | Coordinador único | Administrador | Routesetter | Deportista/acudiente |
|---|---|---|---|---|---|
| Catálogo aprobado docente | Para programas de grupos asignados y materiales autorizados | Institucional | Gestión documental autorizada | Ejercicios/materiales técnicos autorizados | Sin portal en etapa 3 |
| Borradores propios | Crear/editar/proponer | Crear/editar/revisar | Custodia, no aprobación metodológica implícita | Ejercicios propios técnicos | Denegado |
| Staging/original íntegro | Solo si se comparte expresamente para revisión | Revisión institucional | Custodia/importación | No por rol solamente | Denegado |
| Aprobar/publicar currículo/biblioteca | Denegado | Permitido | No por administrador solamente | Denegado | Denegado |
| Retirar contenido | Solicitar/retiro de borrador propio | Institucional | Retiro administrativo auditado | Propio borrador | Denegado |

Combinación de roles evalúa cada facultad y ámbito actual; administrador+profesor no obtiene revisión metodológica sin rol coordinador. Revocar profesor o asignación impide nuevas lecturas de catálogo restringido por ámbito; autoría por sí sola no mantiene acceso a datos institucionales sensibles. No se revisan metadatos privados de autoría de originales mediante el catálogo general.

| Endpoint propuesto | Contrato |
|---|---|
| GET /api/curriculo/programas/ | Mapa Programa↔Nivel, sin duplicar catálogo organizativo |
| GET/POST /api/curriculo/mallas/ | Consulta por ámbito; creación autorizada de identidad |
| GET/POST /api/curriculo/mallas/{uuid}/versiones/ | Historia o derivación por versión exacta; sin copiar identificadores de hijos |
| GET/PATCH /api/curriculo/versiones/{uuid}/ | Árbol paginado o secciones; PATCH de borrador con revision_concurrencia |
| POST /api/curriculo/versiones/{uuid}/proponer/, aprobar/, retirar/ | Comandos transaccionales; versión esperada y clave UUID; aprobación fija contenido |
| GET/POST /api/curriculo/importaciones/ | Lista/creación de staging con FuenteVersion y perfil permitido |
| GET /api/curriculo/importaciones/{uuid}/vista-previa/ | Diff y ambigüedades; nunca publicación implícita |
| POST /api/curriculo/importaciones/{uuid}/confirmar/ | Revisión del mapeo, creación idempotente del original, sin aprobar |
| GET/POST /api/biblioteca/ejercicios/ | Filtros por programa/capacidad/material/duración/estilo/población; borradores propios |
| GET/POST /api/biblioteca/ejercicios/{uuid}/versiones/ | Historia o nueva edición derivada |
| GET/PATCH /api/biblioteca/versiones/{uuid}/ | Ficha completa y cambios de borrador con versión esperada |
| POST /api/biblioteca/versiones/{uuid}/proponer/, aprobar/, retirar/ | Misma semántica editorial, permisos específicos |
| GET/POST /api/biblioteca/materiales/ y /{uuid}/versiones/ | Repositorio docente privado; versiones con licencia/contexto |
| POST /api/recursos/archivos/ | Subida contextual autorizada, checksum/estado; no subida libre sin contexto |
| GET /api/biblioteca/materiales-version/{uuid}/descarga/ | Descarga backend reautorizada en contexto, sin URL pública permanente |

Añadir acciones editoriales de material y consultas de fuentes restringidas de forma simétrica; no exponer CRUD de ArchivoPrivado que eluda permisos de contexto. Endpoints granulares de hijos curriculares reciben ID de versión padre y revalidan pertenencia; aprobación comprueba todos los hijos. No se permite DELETE físico de historia; borradores descartados mediante estado.

Ejemplo mínimo de referencia contractual futura, no una API existente:

```json
{
  "malla_version": "uuid-exacto",
  "clase_prevista": "uuid-exacto",
  "objetivos": ["uuid-elemento-de-esa-version"],
  "ejercicio_version": "uuid-exacto-o-null",
  "duracion_orientativa": {"valor": 10, "unidad": "min"},
  "origen": "propuesta_revisada"
}
```

## 7. Contratos con etapas siguientes

| Consumidor futuro | Referencias y garantías | Lo que no hace Etapa 3 |
|---|---|---|
| Sesiones | SesionVersion referencia MallaVersion/ClasePrevista/Elemento/EjercicioVersion exactos; registra adaptación local aparte | No crea Sesion por cada ClasePrevista ni exige aprobar cada actividad propia |
| Evaluación | Instrumento/ProtocoloVersion enlaza desempeños/competencias de edición exacta, estado de dato separado de descriptor ordinal | No calcula porcentajes, baremos o ascensos ni valida protocolos candidatos |
| Planificación | Programa orienta modalidad curricular/mixta/individual; objetivos versionados y duraciones orientativas | SemanaCurricular no es Microciclo; Especialización no duplica sesiones |
| Route Setting | Ejercicio aporta etiquetas técnicas y necesidades de geometría; montaje real se elegirá en tarea/estación y se validará vigente | No fija una FK a Bloque inexistente ni crea banco paralelo; RIC separado de seguridad |
| RSD/restricciones | Exigencias estructuradas con fuente; futura evaluación permitido/incompatible/requiere_revision según autorización vigente | No almacena historia clínica ni concede alta; ausencia de exigencias no significa seguridad |
| Archivos/captura | Servicio de blob/contexto reutilizable, con finalidad y autorización separadas por consumidor | Material docente no autoriza grabación, uso de menores o entrenamiento IA |
| Analítica | Identidades lógicas y versiones estables permiten futura cobertura curricular con datos de ejecución | No confunde número de textos importados con logro o desempeño del deportista |

Servicio de lectura propuesto `resolver_referencia(actor, tipo, uuid_version, finalidad, fecha)` devuelve contenido exacto y elegibilidad para uso futuro o consulta histórica autorizada. Retirar una versión no cambia sesiones ejecutadas, pero la selección nueva falla. La compatibilidad funcional se comprobará también al ejecutar, cuando exista ese módulo; no se promete control RSD operativo desde esta etapa.

## 8. React y experiencia propuesta

Conservar `frontend/src/Aplicacion.jsx`, `componentes/Estructura.jsx`, `Estado.jsx`, `SelectorCatalogo.jsx`, cliente HTTP/CSRF y tokens Sass. Espacios por rol, no aplicaciones independientes. Navegación “Currículo” y “Biblioteca” solo cuando backend y pantallas estén integrados y probados.

- Profesor: catálogo de programas asignados, árbol fase→semana→clase, objetivos y fuente citada mínima; búsqueda de ejercicios, ficha, variantes, materiales, Mis borradores y proponer. No mostrar textos editoriales privados o marcas de revisor como resultados.
- Coordinador: comparador original/propuesta, vista de procedencia por celda/rango, cola de revisión, incidencias de seguridad y aprobación explícita de versión; indicador de borrador/revisado/aprobado/retirado siempre visible.
- Administrador: fuentes/custodia/importación autorizada, acceso a archivos/estado de carga, retiro auditado; no botón de aprobación metodológica por ese rol solamente.
- Routesetter: ejercicios técnicos autorizados y propuestas propias; no navegación a deportistas ni aprobación curricular.

Edición extensa en escritorio, consulta y ficha legibles en móvil, teclado/foco/etiquetas, filtros accesibles y estados de carga/error/vacío. No editor de cronograma ni reproductor de anotaciones deportivas en Etapa 3. Subida y descarga limitadas por backend, sin depender de ocultación de botones.

## 9. Implementación por incrementos y archivos previstos

Dependencias: 3A→3B→3C; 3A→3D; 3A→3E; 3C/3D/3E→3F. Cada incremento se desarrolla y ensaya en base temporal; requiere autorización de implementación antes de crear código. No depende de aplicar Etapa 2 en producción.

| Incremento | Componentes y archivos nuevos previstos | Cierre verificable |
|---|---|---|
| 3A Procedencia/privacidad | `backend/recursos/{models,almacenamiento,permisos,serializers,views,urls}.py`, servicios de fuente y tests; migración 0001 | Subida privada, checksum, cuarentena y descarga por contexto; fuente congelada y ningún acceso horizontal |
| 3B Currículo versionado | `backend/curriculo/{models,servicios,permisos,serializers,views,urls}.py`, tests; 0001 estructura | Programa enlaza Nivel existente, árbol coherente y revisiones sin sobrescribir; borrador nuevo no cambia edición anterior |
| 3C Importación/revisión | `curriculo/importacion/{xlsx,mapeo,validacion}.py`, servicios editoriales, tests de fixtures; 0002 staging/integridad | Cuatro hojas a vista previa; procedencia exacta, 40/80 y fases, combinadas sin duplicación, confirmación idempotente; aprobación separada |
| 3D Biblioteca | `backend/biblioteca/{models,servicios,permisos,serializers,views,urls}.py`, tests; 0001 ejercicios/taxonomía/decisiones | Ejercicio versionado, filtros, población/restricciones/fuentes; cero candidatos cargados automáticamente |
| 3E Materiales | Servicios/serializers/materiales en biblioteca y recursos; 0002 materiales/enlaces | Versiones/descargas/licencia protegidas; revocación y URLs copiadas no eluden permisos |
| 3F Interfaz/contratos/cierre | `frontend/src/componentes/{Curriculo,BibliotecaEjercicios,FichaEjercicio,RevisionContenido,ImportacionMalla,MaterialesDocentes}.jsx`, API helpers, Sass y pruebas; `curriculo.0003` enlaces de actividades tras biblioteca | Integración por rol, conflictos/estados visibles, pruebas cruzadas y manual móvil/escritorio; documentación de contratos y continuidad |

Archivos existentes a modificar al implementar: `backend/configuracion/settings.py` solo registro de apps en perfiles de desarrollo autorizados; `configuracion/urls.py`; `cuentas/autorizacion.py` nuevas acciones explícitas; ejecutor de pruebas/allowlist para incluir las tres apps; `frontend/src/Aplicacion.jsx`, `componentes/Estructura.jsx`, estilos/cliente cuando sea necesario. Si conviene compartir el serializer estricto actual, extraerlo sin cambiar comportamiento de deportistas y con regresión; no introducir importación de `deportistas` en `curriculo` solo para heredar un helper.

Números de migraciones son propuestos; se fijan al implementar según dependencias reales. FK al usuario usa swappable_dependency, Programa depende de `organizacion.0002`, biblioteca depende de recursos y currículo para ProgramaEjercicio; evitar ciclo: crear ActividadCurricular en migración posterior dependiente de biblioteca, nunca FK inversa inicial. SQL de inmutabilidad/coherencia solo en migraciones nuevas. No tocar las 14 migraciones históricas ni las cuatro de Etapa 2. No migraciones de datos con 224 registros ni bootstrap silencioso de niveles.

Babys requiere decidir un Nivel nuevo dentro del catálogo existente y su relación Programa; Alto Rendimiento reutiliza su Nivel. Ninguna edición “original” se crea para ellos. Se propone creación explícita y revisada de Programa/Nivel Babys durante implementación autorizada, sin cambiar matrículas/orden histórico. Si no se formaliza todavía, aparece como propuesta sin uso operativo.

## 10. Matriz de aceptación y trazabilidad

Todos los casos son **pruebas previstas, no ejecutadas**. PostgreSQL es obligatorio para integridad/concurrencia; SQLite no acredita triggers o permisos. Fixtures ficticios, Excel mínimo sintético en tests; el archivo privado original se usa solo en ensayo de extracción autorizado y no se empaqueta en Git.

| ID / requisito | Entidad, API y pantalla | Permiso / evento | Prueba de aceptación |
|---|---|---|---|
| C01 Fuente exacta | FuenteVersion/Fragmento; importaciones, comparador | Custodia/revisión; extracción | SHA y localizadores; ancla G10:G11 sin duplicación, filas ocultas/notas separadas |
| C02 Estructura | MallaVersion/Fase/Semana/Clase; árbol | Ámbito docente; creación | Lúdico 10/10/20, otros 14/14/12, 40/80, Semana≠sesión; rechazar cruces de versión |
| C03 Semántica | Elemento/Ubicacion; editor | Autor/revisor; derivación | C–F no se multiplican por fila; H10/H11 se conservan; placeholder bloquea propuesta de aprobación sin resolver |
| C04 Versiones | Malla/Ejercicio/MaterialVersion; detalle/historial | Aprobador; transición | Editar aprobado falla por API y SQL directo, nueva edición conserva referencias; retirada no borra historia |
| C05 Reintentos | Lote y comandos; vista previa | Actor actual; evento único | Misma clave mismo payload no duplica, payload distinto 409, dos confirmaciones concurrentes una sola versión |
| C06 Roles/revocación | Todas las listas/detalles/descargas | Facultad+objeto; acceso | Profesor no ve otro borrador, routesetter sin deportistas, admin sin revisión metodológica; revocación con actor/sesión cargados |
| C07 Biblioteca | Ejercicio/Adaptacion/Exigencia; búsqueda/ficha | Ámbito+revisión; publicación | Filtros combinados, null≠0, duraciones/edades coherentes; no derivar intensidad de grado/color |
| C08 Candidatos | Procedencia/lote; revisión | No autoaprobación | 224/16/12 permanecen referencias; ninguna migración o arranque los carga; no convertir conceptos mixtos en ejercicios |
| C09 Archivos | Archivo/MaterialVersion; subida/descarga | Contexto actual; auditoría | MIME/firma/tamaño/ZIP malicioso/ruta traversals/URLs externas; descarga ajena 404, revocación bloquea nueva lectura, sin ruta pública |
| C10 Contratos futuros | ActividadCurricular/referencias | Elegibilidad; consulta histórica | IDs exactos, retiro bloquea selección nueva sin modificar pasado, no crear bloque/sesión/protocolo paralelo |
| C11 Metodología | Elementos y metadatos | Revisión humana | No 80%, promedios ordinales, diagnóstico, malla AR/Babys inventada o máximos a menores; texto original intacto |
| C12 Regresión | Núcleo anterior, API y React | Roles Etapa 2 | Coordinador único/ascensos/asignaciones conservados; prueba de migración ida y restauración de copia; build y accesibilidad manual |

Cada incremento dejará informe con fuente reutilizada, modelo/API/pantalla/permiso/evento/prueba/estado, comandos y resultados, pendientes y limitaciones. Estados: no implementado al inicio; parcial durante desarrollo; existente y verificado solo tras comprobar; pendiente de validación metodológica aunque tests técnicos pasen. No afirmar funcionalidad por documentarla.

## 11. Riesgos, decisiones propuestas y aprobación solicitada

Riesgos: interpretación de celdas combinadas y textos de fase; notas privadas en origen; publicación indebida de candidatos/licencias; referencias interversión; seguridad de archivos; dependencias circulares; permisos de roles combinados; metadatos incompletos de restricciones. Mitigaciones especificadas arriba, sin introducir validación médica o aprobación previa de sesiones.

Decisiones propuestas para aprobar con la implementación: tres apps y límites descritos; revisión/publicación metodológica por coordinador único; originales archivados sin aprobación implícita; seis programas con Babys/AR pendientes de su formalización; malla agregada con hijos congelados, no un sistema global independiente de competencias; biblioteca privada/institucional con materiales de derechos comprobados. Si una decisión institucional difiere, ajustar este plan antes de codificar, no inferirla desde Excel.

Puntos de parada: autorización de implementación de 3A–3F antes de crear modelos/migraciones; aprobación de contenido independiente antes de hacerlo elegible; autorización separada para cualquier extracción/restauración de datos reales o activación operativa. Esta entrega no solicita que se aprueben científicamente mallas, juegos o instrumentos.

## 12. Entrega y continuidad

Se añadieron únicamente este plan y `CIERRE_PREPARACION_ETAPA_2_PASOS_MINIMOS.md` a documentación de integración; evidencia de lectura/mapeo permanece privada en `respaldos/diseno_etapa3_20261102/`. No se creó código de módulo ni migraciones; no hubo conexión SQL, importación a base, respaldo operativo, despliegue, cambio en Git o push. La copia Git íntegra anterior se conserva sin tocarla.

Siguiente sesión: leer estos dos documentos y `VERIFICACION_TECNICA_PREACTIVACION_ETAPA_2.md`; tras aprobación iniciar 3A en copia de desarrollo, sin repetir Fase 0 o reconstruir decisiones. La prioridad del proyecto integral se conserva y las etapas deportivas siguientes permanecen planificadas, con IA aplazada.
