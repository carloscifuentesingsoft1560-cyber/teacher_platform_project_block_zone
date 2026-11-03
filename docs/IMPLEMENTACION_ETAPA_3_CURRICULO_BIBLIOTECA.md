# Implementación de Etapa 3 en integración aislada

Fecha: 2026-11-02. Alcance: currículo, ejercicios y materiales. Implementación exclusivamente en `respaldos/etapa2_20261102T182622Z/integracion`. **No es una activación operativa ni autorización de publicación.** Etapa 2 continúa sin aplicarse a la base operativa. No se inició ninguna etapa deportiva posterior ni IA.

## 1. Arquitectura y reutilización

Se mantiene Django/DRF/PostgreSQL y React/Vite/Sass. Se reutilizan cuentas multirrol, `roles_vigentes`, `puede`, bloqueo de autoridad de cuentas, coordinador único, `Nivel`, `Disciplina`, asignaciones/grupos, auditoría, CSRF, respuestas de error y conflictos 409. No se crean usuarios, deportistas, grupos, matrículas ni niveles duplicados. No se modifican las 14 migraciones históricas ni las cuatro migraciones de Etapa 2.

Apps nuevas: `recursos`, `curriculo`, `biblioteca`. El arranque normal de integración sigue bloqueado por sus settings; solo están habilitados perfiles de desarrollo/prueba autorizados. No se copió `.env` operativo ni se introdujeron dependencias nuevas.

## 2. Los seis incrementos

| Incremento | Implementación entregada | Verificación y límites |
|---|---|---|
| 3A Procedencia y privacidad | Blobs opacos privados, validación de tamaño/firma/ZIP, checksum, fuentes/documentos/versiones/fragmentos; API y pantalla de custodia | Archivo rechazado no crea fila. Derechos/finalidad explícitos. Descarga backend reautoriza; no URL pública. Validación síncrona antes de persistir, sin servicio de cuarentena externo |
| 3B Currículo versionado | Programa enlazado 1:1 a Nivel, Malla/MallaVersion, fases/semanas/clases/elementos, ubicaciones múltiples y procedencia | Original cerrado y edición publicada congelados por PostgreSQL; derivación conserva claves lógicas con nuevas PK. Una clase prevista nunca crea sesión/asistencia |
| 3C Importación/revisión | Perfil `mallas-zdb-v1`, extracción y confirmación de cuatro hojas, vista previa, originales archivados y propuestas derivadas, eventos de revisión/publicación | Fuente+perfil y claves de reintento evitan duplicados. No evalúa fórmulas. Columnas editoriales no son aprobación. Original no publicable directamente: derivar y revisar |
| 3D Biblioteca | Ejercicios/versiones, pasos, adaptaciones, requisitos/exigencias, población, programas, taxonomía y procedencia, búsqueda y filtros; modelo/API de candidatos | Cero importación automática de 224 candidatos o piloto. Estilos separados de capacidades; duración desconocida null. No inferencia clínica, RIC/carga o baremos |
| 3E Materiales | MaterialDocente/Version, archivo privado o referencia HTTPS, derechos y destinatarios, vinculación a ejercicios, derivación y edición de borrador | Las versiones y bytes previos permanecen. El mismo archivo no confiere permisos entre contextos. Descarga por edición vuelve a filtrar rol/objeto/asignación |
| 3F Interfaz/contratos | Currículo, Biblioteca, Materiales, Fuentes/importación; navegación por rol, estados, formularios etiquetados, fuentes por celda/rango, controles de revisión y conflictos | React/DOM y build comprobados; sin validación visual completa en navegador/dispositivo real. Contratos futuros sin tablas ficticias de sesiones/evaluación/Route Setting |

Los incrementos comparten modelos/servicios y se integraron con el grafo de dependencias completo antes de habilitar sus rutas en el entorno de prueba. Las pruebas dirigidas recorren varias capas; no se atribuye a cada incremento una ejecución independiente inexistente.

## 3. Modelos y migraciones

`recursos`: ArchivoPrivado, FuenteDocumento, FuenteVersion, FragmentoFuente; bases abstractas Identidad/Edicion/Evento. `curriculo`: ProgramaFormativo, Malla, MallaVersion, FaseCurricular, SemanaCurricular, ClasePrevista, ElementoCurricular, UbicacionCurricular, ProcedenciaCurricular, LoteImportacion, EventoMalla, ActividadCurricular. `biblioteca`: TerminoActividad, Ejercicio/EjercicioVersion, PasoEjercicio, AdaptacionEjercicio, ExigenciaEjercicio, ProcedenciaEjercicio, MaterialDocente/MaterialDocenteVersion, MaterialEjercicio, CandidatoBiblioteca, EventoEjercicio/EventoMaterial.

Nueve migraciones nuevas, ensayadas solo en clústeres temporales:

- recursos: `0001_initial`, `0002_integridad_editorial`, `0003_identidades_estables`.
- curriculo: `0001_initial`, `0002_ubicacioncurricular`, `0003_mallaversion_clave_derivacion`.
- biblioteca: `0001_initial`, `0002_initial`, `0003_ejercicioversion_clave_derivacion_and_more`.

El generador separó las relaciones iniciales para resolver la dependencia currículo↔biblioteca sin ciclo. Las migraciones propias se generaron sin aplicar cambios de base; su aplicación/integridad se comprobó posteriormente en PostgreSQL temporal, nunca mediante SQLite. Las funciones/triggers son de PostgreSQL y la instalación de integridad rechaza otros motores.

Las publicaciones se representan mediante estado/revisor/fecha/vigencia de la edición y eventos editoriales inmutables, sin otra copia del contenido en tablas de publicación. Una aprobación sustituye la edición vigente de esa identidad bajo bloqueo e índice único; la anterior mantiene contenido y decisión histórica. El retiro no borra filas. Los borradores se editan con revisión optimista; una edición derivada conserva texto/relaciones anteriores sin sobrescribirlos. Las ubicaciones adicionales permiten reutilizar un elemento en varias clases sin clonarlo como competencias distintas.

Defensas SQL: fuentes/archivos/eventos inmutables, raíces estables, contenido de ediciones no borrador congelado, hijos y M2M congelados, coherencia de versión entre fase/semana/clase/elemento/ubicación, ausencia de ciclos curriculares y clases globales duplicadas. Publicación requiere revisor coordinador vigente; no pretende impedir a un propietario PostgreSQL desactivar sus propios triggers. La retirada inversa de integridad se bloquea si hay contenido: no es un rollback operativo automático.

## 4. Semántica curricular y procedencia

El perfil lee exactamente las cuatro hojas del Excel original. Extracción real sin importación a base: LUDICO 40/80, fases 10/10/20, 230 combinaciones; NIVEL 1 40/80 y 14/14/12, 230; NIVEL 2 40/80 y 14/14/12, 238; ESPECIALIZACION SEMICOMPETITIVA 40/80 y 14/14/12, 230. Evidencia privada `extraccion_original_sin_db.json`.

El ensayo de confirmación usa un Excel sintético de cuatro hojas: conserva 320 clases previstas en total, fuentes/anclas/rangos, objetivos de fase, temas y desempeños; no inventa competencias a partir de celdas combinadas. El original autorizado se abrió en modo lectura para comprobar el extractor, sin cargar nombres/anotaciones reales en tablas de prueba ni distribuir el Excel.

El texto original y su contexto quedan en FragmentoFuente. ElementoCurricular contiene texto curricular derivado con vínculo explícito. C–F se interpretan por fase; B y G combinadas no se multiplican; H10/H11 son desempeños de una clase. Notas laterales solo para custodia, sin marcas de aprobación. El perfil rechaza estructura/fórmulas inesperadas en lugar de recalcular o adivinar. Un cambio de formato requiere otro perfil revisado.

Naturaleza (`original_institucional`, `propuesta_revisada`, `adaptacion_docente`) y estado editorial son ejes separados. El original se archiva con `original_cerrado=true`; su estado técnico de borrador no permite edición ni publicación directa. La propuesta derivada sí se revisa y, solo por coordinador, se aprueba/publica.

NIVEL 1!G5 contiene un placeholder y bloquea propuesta hasta revisar su texto derivado; no se corrige en la fuente. Las referencias a dificultad/instalaciones y la adecuación de Especialización se mantienen como incidencias metodológicas. Babys y Alto Rendimiento usan el catálogo organizativo existente o una vinculación futura explícita, sin mallas originales inventadas. Crear un programa pendiente y formalizarlo es configuración explícita, no aprobación automática de su contenido.

## 5. API y permisos reales

Prefijos nuevos: `/api/recursos/`, `/api/curriculo/`, `/api/biblioteca/`. Las rutas de edición son canónicas sobre versión; no se creó un segundo catálogo REST de mallas con contenido duplicado.

| Rutas | Operaciones |
|---|---|
| recursos/archivos/ | POST multipart con finalidad y declaración; respuesta de metadatos, sin ruta de disco |
| recursos/archivos/{uuid}/descarga/ | GET del propio archivo, cuenta/rol actuales |
| recursos/fuentes/, fuentes-version/, fragmentos/ | GET/POST de custodia institucional; sin ediciones destructivas de fuentes |
| curriculo/programas/ y /{id}/ | GET por ámbito, POST y PATCH de modalidad/formalización por custodia; Nivel vinculado estable |
| curriculo/versiones/ y /{uuid}/ | GET y creación de borrador, PATCH de contenido permitido con revisión esperada |
| curriculo/versiones/{uuid}/estructura/ | Árbol, ubicaciones, actividades y procedencia visible sin notas editoriales privadas |
| curriculo/versiones/{uuid}/agregar/, editar-elemento/, actividad/ | Comandos de borrador; FK y pertenencia revalidadas |
| curriculo/importaciones/ y /{uuid}/confirmar/ | Staging privado y confirmación idempotente con mapa explícito de programas por hoja |
| biblioteca/versiones/ y /{uuid}/ | Fichas de ejercicio y versiones, edición de borradores; filtros buscar/programa/disciplina/poblacion/duracion_max/capacidad/material/instalacion/estilo/movimiento |
| biblioteca/versiones/{uuid}/agregar/ | Pasos, adaptaciones, exigencias, procedencias autorizadas y materiales |
| biblioteca/materiales/ y /{uuid}/descarga/ | Versiones y descargas por contexto de material, no por URL pública de archivo |
| biblioteca/terminos/, candidatos/ | Catálogo semántico de lectura docente y escritura de custodia; candidatos internos sin vía de publicación automática |
| */{uuid}/derivar/, proponer/, aprobar/, devolver/, retirar/, eventos/ | Transiciones comunes y traza por versión; derivar requiere clave UUID estable de reintento |

Las acciones editoriales sobre versiones están disponibles para mallas, ejercicios y materiales. Campos del servidor no se aceptan en entradas. PATCH requiere revisión; conflicto 409. Repetición de comando con clave/payload idéntico conserva resultado, con payload incompatible falla. Las derivaciones tienen clave propia y no duplican edición al reintentar.

El coordinador único revisa/publica y puede devolver con observación. Administrador custodia/configura y puede retirar administrativamente, sin aprobación metodológica implícita. Profesor crea borradores y consulta catálogo pertinente a programas asignados; rutas y queryset se revalidan por cuenta/facultad actuales. Routesetter ve catálogo técnico y borradores propios, sin adquirir acceso a deportistas/currículo por ese rol. Portales de deportista/acudiente no obtienen contenido docente interno. Mezclar roles no duplica facultades ni evita revocación.

Los hijos no tienen escritura libre por ID: pasan por edición padre bloqueada y comprobada. `resolver_referencia` diferencia selección nueva aprobada/vigente de consulta histórica restringida. Una actividad curricular institucional enlaza edición exacta de ejercicio; no crea un bloque paralelo ni aprobación previa de sesiones. La actividad propia de una futura sesión conservará su contrato propio de autonomía docente.

## 6. Archivos privados y derechos

Límite 25 MiB. Tipos: documentos PDF/TXT/Office sin contenido activo, imágenes PNG/JPEG y contenedores MP4/MOV reconocidos por firma; extensión/tipo verificados. Office: límites de entradas/tamaño expandido, rechazo de rutas inseguras, cifrado, macros, embeddings y relaciones externas. No se ejecutan macros, fórmulas, URLs o descargas remotas.

Los blobs se guardan por UUID en `ZDB_ARCHIVOS_PRIVADOS`, por defecto bajo `respaldos/archivos_docentes_privados` de integración; nunca MEDIA_URL pública. En Windows se restringe y comprueba la DACL completa antes de escribir bytes: ejecutor, SYSTEM, Administrators. No se requieren privilegios SACL. En POSIX se usa directorio 0700. La cuenta de servicio y disco protegidos siguen siendo responsabilidad de configuración del destino; no se cambió la aplicación operativa.

Una declaración de derechos/finalidad es obligatoria; no equivale a validación de licencia ni consentimiento audiovisual de menores. No usar esta biblioteca para registrar grabaciones de deportistas o información clínica. Un material publicado no concede autorización para IA. Las descargas llevan no-store/private y nosniff, y se auditan; una revocación no puede retirar copias ya descargadas.

No hay eliminación física automática de documentos o eventos. Retención, cuotas globales y conciliación de blobs huérfanos ante fallos extraordinarios/rollback exterior quedan como operación administrativa pendiente; no se implementó un borrado destructivo. Los tiempos/limitaciones de vídeo y el reproductor de anotaciones corresponden a su etapa futura.

## 7. Pruebas y correcciones verificables

Resultados definitivos y antecedentes de esta ejecución:

| Ejecución | Resultado observado |
|---|---|
| Primera migración SQL de integridad | Detectó interpretación de `%` por el schema editor; corregida usando SQL sin parámetros |
| Primeras dirigidas recursos/currículo | Detectaron comparación dependiente del orden de Cache-Control y cierre de streaming del cliente de pruebas; corregido consumo/cierre del fixture sin relajar privacidad |
| Dirigidas de tres apps | 42 aprobadas antes de ampliaciones posteriores |
| Primera regresión general | 580 aprobadas, 291,678 s; migraciones sin cambios, núcleo anterior conservado |
| Refuerzo de DACL | Verificación detectó ACE adicionales y limitación de SeSecurityPrivilege en Set-Acl. Se mantuvo fallo cerrado y se corrigió con modificación DACL mediante icacls más lectura/verificación; sin escalación |
| Pase completo posterior | 586 aprobadas, 364,090 s; sin incidencias y No changes detected |
| Frontend de entrega | 173 aprobadas en 15 archivos, 23,22 s; incluye navegación por rol, etiquetas, estados, conflictos y CSRF |
| HTTP | 6 aprobadas |
| Infraestructura | 5 aprobadas |
| Build | Aprobado, 77 módulos; no se publicaron dist o dependencias |
| Pase completo de reintento/revocación | 587 aprobadas, 339,566 s; permisos actuales revalidados incluso para eventos repetidos |
| Pase completo de custodia y propósito de archivo | 589 aprobadas, 423,057 s; revocar custodia cierra originales aunque siga otro rol; fuente privada no se publica como material |
| Cierre backend con entradas malformadas | **592 aprobadas, 395,922 s**, sin fallos ni skips; system check sin incidencias y No changes detected; evidencia `pruebas_etapa1_yr4wybsp` |

La prueba añadida de revisión reintentada exige revalidar la facultad incluso cuando ya existe un evento idempotente. También se prueban actualización de Etapa 2→3 conservando cuenta/facultades ficticias, fuentes inmutables, dos publicaciones concurrentes, clases globales únicas, ciclos/ubicaciones entre versiones, derivación repetida, revocación conservando otro rol y descarga por grupo vigente. Todas las migraciones de pruebas ocurren en bases `test_zdb_*` de clúster verificado, no en zona_bloque.

El último refuerzo valida cuerpos JSON, tipos de comando e identificadores antes de consultar, devolviendo 400 en lugar de errores internos. Los bloqueos globales de cuentas del núcleo se conservaron para serializar revocación y cambios de contenido; no se midió rendimiento a volumen productivo. La validación local de custodia añade coste de E/S que debe medirse en el entorno de servicio antes de activar.

No se repitieron auditorías de configuración operativa: no hubo conexión al servidor operativo ni captura reciente. Los resultados no aprueban contenido científico ni sustituyen ensayo reciente de despliegue con locale/roles/volumen real. No se realizaron recorridos visuales de navegador o dispositivos; jsdom comprueba DOM/interacción, no toda responsividad o comportamiento móvil.

## 8. Reproducción aislada y prueba del usuario

Desde integración, con runtime y paquetes ya existentes, sin instalar dependencias:

```powershell
$pythonPruebas = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:ZDB_PAQUETES_PYTHON = Join-Path (Resolve-Path '../../..').Path '.venv-local/Lib/site-packages'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $pythonPruebas scripts/test_infraestructura_aislada.py
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --verbosity 1
# Dirigidas: --etiqueta recursos --etiqueta curriculo --etiqueta biblioteca
```

En frontend: `npm.cmd test`, `npm.cmd run test:api`, `npm.cmd run build`. El runner rechaza cambio de settings/base/keepdb y permite únicamente las apps de prueba explícitas. No usar el ejecutor histórico de copia restaurada para generar o aplicar estas migraciones a producción.

Para una revisión manual posterior, preparar entorno HTTP y cuentas **ficticias** dentro de una base aislada autorizada; no arrancar contra el origen. Recorrido: coordinador vincula programas a niveles existentes y confirma formalización → registra fuente/licencia y archivo autorizado → extrae vista previa → mapea cuatro hojas a sus programas → confirma original sin publicar → deriva propuesta → revisa placeholders y contenidos → propone/aprueba → profesor asignado consulta malla/ejercicios/materiales → profesor ajeno y acudiente quedan fuera → retirar o revocar acceso bloquea nuevas lecturas. No se generó un perfil operativo como parte de este recorrido documental.

## 9. Git y punto de parada

Se copió la base Git íntegra a `respaldos/etapa3_implementacion/git-completo`, sin sustituir `.git` de integración anterior. Todos los comandos de rama/commit usan `--git-dir` y `--work-tree` explícitos. Rama: `desarrollo-zona-de-bloque`; main local permanece `decda62bff95f782e124394fb221626f12990f6d`, mismo tip remoto comprobado mediante conector de lectura.

Commits locales: Etapa 2 `1e02fc8c242501c7d62496f55e9890430d500bd8`; Etapa 3 `9b67f121cc7d64c9ceecf185d98ee69d01049874`. Un commit posterior cierra documentación; su identificador queda en el manifiesto privado y mensaje de entrega para evitar referencia circular al propio hash. Autoría técnica de commits nuevos: Codex, correo local no operativo; no se atribuye implementación a otra persona. No se ejecutó push, PR, merge, fetch que altere referencias, reset, force o reescritura de historial.

Ver inventario/revisión final en `PUBLICACION_PROPUESTA_ETAPAS_2_3.md` e `INVENTARIO_PUBLICACION_ETAPAS_2_3.md`. Los documentos fuente privados y los logs permanecen excluidos. El objeto histórico se conserva, incluidos metadatos de autoría ya identificados: decisión de privacidad/publicación pendiente del titular; no se sanitizó su SHA ni se retiró del historial automáticamente.

## 10. Pendientes y límites de cierre

- Validación institucional de mallas derivadas, objetivos incompletos, adecuación de Especialización/instalaciones y dimensión psicosocial; ninguna aprobación automática por importar o pasar tests.
- Babys/Alto Rendimiento sin originales fabricados; catálogo de programas y formalización requieren decisiones reales, no se sembraron matrículas o mallas nuevas.
- Candidatos 224, piloto 16 y manual 12 siguen pendientes; licencias/páginas/seguridad antes de promover fichas, sin convertir fórmulas del Excel de valoraciones en calificaciones o ascensos.
- Etapas futuras: sesiones/asistencia, instrumentos de evaluación, planificación/cargas/RSD, catálogo oficial de bloques, captura/anotación y analítica permanecen fuera de alcance. No se entrenó, descargó ni integró IA.
- Antes de activar Etapas 2/3: acceso de lectura acreditado, respaldo reciente protegido, ensayo final con configuración equivalente y mínimo privilegio, perfil operativo, paquete final y autorización específica de migración/despliegue; siguen pendientes según procedimientos existentes.
- Antes del primer push: revisar inventario, decisión sobre autoría histórica y aprobación explícita de publicación **únicamente de desarrollo-zona-de-bloque**. Este informe no ejecuta esa operación.

## Cierre verificable

592 backend, 173 frontend, 6 HTTP, 5 de infraestructura y build aprobados. Original: 290 hashes sin diferencias. Los 23 archivos de migraciones previas (incluidos inicializadores) conservan sus hashes. Nuevas migraciones aplicadas solo a clústeres temporales detenidos; las bases de prueba fueron eliminadas por Django. Inventario propuesto: 345 archivos, incluidos seis heredados de main. No hubo SQL operativo, despliegue o push. El punto de parada sigue vigente.
