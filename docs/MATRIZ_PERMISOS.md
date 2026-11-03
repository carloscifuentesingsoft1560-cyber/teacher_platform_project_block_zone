# Matriz funcional — coordinación única de Zona de Bloque

> Estado de esta rama de desarrollo: facultades multirrol implementadas y revalidadas por acción/objeto. Profesor propone; coordinador decide pedagógicamente; administrador registra revisiones administrativas y formaliza. El coordinador conserva GET administrativos autorizados. Los roles routesetter/deportista/acudiente no abren módulos futuros ni información ajena por sí solos. [Contratos y evidencia](IMPLEMENTACION_ETAPA_2_NUCLEO.md). La matriz histórica siguiente se conserva para explicar la evolución.

> Noviembre de 2026: matriz histórica del núcleo de tres roles. El nuevo maestro prevé roles múltiples y formalización exclusiva administrativa de ascensos, pero Etapa 1 solo los documenta: [dependencias y matriz objetivo de Etapa 2](PROPUESTA_ETAPA_2_NUCLEO_INSTITUCIONAL.md). No interpretar esa propuesta como permiso operativo ya aplicado.

Decisión definitiva del propietario, 28 de octubre de 2026. **Implementación autorizada y probada; índice PostgreSQL de coordinador único aplicado y verificado.** Véanse [resultados](VERIFICACION_COORDINACION_TABLERO.md) y [plan de migración](MIGRACION_COORDINADOR_UNICO.md).

## Estructura institucional

- Un administrador principal con control institucional, usuarios, configuración, seguridad y reportes.
- Un único coordinador activo con responsabilidad operativa y pedagógica sobre todos los profesores y grupos de la empresa.
- Varios profesores, limitados a sus grupos y actividades propias.

Esta decisión sustituye la propuesta de supervisiones individuales, grupos delegados por coordinador y coordinadores simultáneos. No se requiere asignar cada profesor al coordinador ni mantener una jerarquía.

## Matriz objetivo

| Operación | Profesor | Coordinador activo único | Administrador principal |
|---|---|---|---|
| Crear usuarios, cambiar roles o privilegios | No | No | Sí, con validación y auditoría |
| Activar/desactivar cuentas o recuperar acceso | No | No | Sí, con procedimiento seguro |
| Designar, relevar o finalizar el cargo de coordinador | No | No, tampoco sobre sí mismo | Sí, transaccional y auditado |
| Consultar profesores | Su información propia | Todos, incluso sin grupo; datos operativos mínimos | Información institucional autorizada |
| Gestionar grupos: crear, editar y archivar | Consulta de los propios; gestión pedagógica autorizada | Todos los grupos, con las reglas de integridad vigentes | Control global |
| Elegir disciplina, nivel y periodo de un grupo | Consulta propia | Usar catálogos autorizados, sin redefinirlos | Control global |
| Crear/modificar catálogos y configuración institucional | No | No | Sí |
| Consultar horarios y calendario | Propios | Toda la operación deportiva | Global |
| Gestionar horarios oficiales | Consulta propia | Todos los grupos; validar impacto y cruces | Global |
| Crear/finalizar asignaciones de profesores | No | Toda la plantilla docente y grupos | Global |
| Crear asignaciones para ampliar sus privilegios | No | No; el cargo ya delimita su autoridad | Solo administración gestiona el cargo |
| Sesiones y actividades pedagógicas — futuras | Crear/gestionar las propias según reglas | Supervisar a todos los profesores; no sustituir automáticamente la autoría | Acceso institucional autorizado |
| Observaciones y seguimiento — futuros | Consultar y atender las propias | Registrar y seguir el trabajo docente institucional | Visión global |
| Preparar/confirmar asistencia — futura | Propia, con bloqueo según política | Supervisión; no captura o corrección delegada implícitamente | Según política aprobada |
| Consultar asistencia y cumplimiento — futuros | Propios autorizados | Todos los profesores y grupos | Consolidado institucional |
| Valoraciones — futuras | Permiso pendiente de definición | Según reglas específicas de valoración | Según reglas específicas de valoración |
| Consultar tablero organizativo | Resumen propio | Operación completa, sin información de seguridad | Estadísticas generales de la empresa |
| Consultar auditoría | Sin acceso general | Cambios operativos autorizados | Auditoría institucional, incluida seguridad |
| Reportes | Propios autorizados | Operativos y pedagógicos autorizados | Institucionales y de seguridad autorizados |
| Borrar usuarios, grupos o evidencias con historial | No | No | No por esta ampliación: conservar y desactivar/archivar |

Gestionar grupos no permite al profesor cambiar cupos, personal asignado o el horario oficial. Esas funciones organizativas corresponden a coordinación/administración. La gestión pedagógica del profesor se ampliará con los módulos aprobados posteriormente.

## Reglas del diseño simplificado

1. El coordinador tiene alcance operativo institucional; no depende de compartir grupo, de una delegación por profesor o de Asignacion de tipo coordinador.
2. Un profesor nuevo pasa al equipo operativo del coordinador sin crear una relación adicional.
3. Profesor inactivo sigue siendo consultable por coordinación como registro operativo, pero no recibe nuevas asignaciones hasta que administración active la cuenta.
4. Solo el administrador gestiona cuentas, credenciales, privilegios, configuración y el relevo del cargo.
5. El backend comprueba sesión, cuenta activa y rol en cada operación. La futura restricción de unicidad permite como máximo un coordinador activo.
6. La edición operativa comprueba todos los afectados por un horario y rechaza cruces incompatibles. Compartir horario entre profesores no exige permisos de varios coordinadores.
7. Las operaciones sobre usuarios no se habilitan al coordinador mediante solicitudes anidadas, campos ocultos o endpoints genéricos.
8. El profesor conserva filtrado por asignación propia en listas, detalles, calendarios, futuras actividades y reportes. No obtiene estadísticas institucionales.
9. Las escrituras y sus auditorías son atómicas. El relevo revoca la autoridad del saliente en la siguiente solicitud, también si conserva una sesión abierta.
10. No se cambia la autoría de acciones históricas al nombrar un sustituto.
11. Se conserva la regla de sesiones sin aprobación previa obligatoria y la prohibición de editar asistencia confirmada sin política excepcional.
12. No se conceden permisos nuevos de valoración ni se calculan indicadores de módulos inexistentes.

## Referencia de la base anterior frente a la ampliación

| Área | Base de Fase 2 anterior | Ampliación implementada / regla objetivo |
|---|---|---|
| Equipo del coordinador | Derivado de grupos compartidos | Todos los profesores por rol, tengan o no grupo |
| Alcance sobre grupos | Consulta de grupos asignados | Gestión operativa de todos los grupos |
| Horarios/asignaciones | Escritura administrativa | Administrador y coordinador activo, por operación autorizada |
| Número de coordinadores | Sin restricción específica de unicidad | Máximo uno activo |
| Relevo | Cambios de usuario auditados de forma genérica | Eventos explícitos de inicio/fin de cargo, atómicos |
| Tablero general | Panel inicial | Estadísticas reales con los modelos existentes |
| Sesiones/asistencia/valoraciones | No implementadas | Incorporación posterior, con reglas propias |

La ampliación está implementada y pasó 114 pruebas backend y 33 frontend. El índice adicional solo se aplicó en pruebas en memoria; sigue pendiente en PostgreSQL. Los módulos pedagógicos de la matriz siguen siendo futuros.

## Fase 3 — Permisos implementados, esquema real aplicado

Estas reglas concretan la autorización de deportistas e inscripciones. Las dos migraciones ya se aplicaron con autorización en zona_bloque. Se aprobaron 69 comprobaciones reales con rollback y 172 pruebas en PostgreSQL aislado. Las rutas privadas deniegan permisos antes de validar cuerpos. [Informe de aplicación](APLICACION_MIGRACIONES_FASE_3.md).

| Operación | Administrador | Coordinador activo | Profesor |
| --- | --- | --- | --- |
| Fichas, inscripciones, reservas y traslados al mismo nivel | Gestión global autorizada | Gestión operativa global | Consulta de inscritos de grupos vigentes |
| Acudientes, vínculos y declaraciones de autorización | Gestión auditada | Gestión operativa auditada | Sin acceso |
| Tipos de autorización y políticas de datos | Crear/versionar y configurar | Consultar | Sin acceso |
| Proponer inscripciones/traslados/cambios de nivel | Ejecuta gestión administrativa directa cuando corresponde | Ejecuta gestión operativa directa cuando corresponde | Proponer en ámbito actual y efectivo |
| Aprobar/rechazar propuesta administrativa | Sí | Sí | No |
| Aprobar/rechazar cambio de nivel | No sustituye decisión pedagógica | Sí, titular vigente | No |
| Cancelar propuesta pendiente | Gestión auditada | Gestión auditada | Solo propia y en ámbito autorizado |
| Fecha de nacimiento y motivos administrativos | Según necesidad institucional | Según gestión autorizada | No se exponen |
| Autenticación de deportistas/acudientes o medios | No habilitados | No habilitados | No habilitados |

No se cambian facultades anteriores de usuarios, seguridad o catálogos. [Detalle de ámbito, API, pruebas y migraciones](IMPLEMENTACION_FASE_3.md).

## Identificación documental — implementada y migración aplicada

| Operación | Administrador | Coordinador activo | Profesor |
| --- | --- | --- | --- |
| Documento actual completo | Consulta institucional autorizada | Consulta operativa autorizada | Nunca |
| Tipo y número enmascarado | Sí | Sí | Solo fichas de sus grupos autorizados |
| Cambiar documento e historial enmascarado | Sí, auditado | Sí, auditado | No |
| Búsqueda documental exacta mediante POST | Sí | Sí | No |
| Consultar catálogo documental | Sí | Sí | Sí |
| Crear o editar tipos concretos del catálogo | Sí | No | No |

Las respuestas docentes excluyen número completo, país emisor, código interno y fecha de nacimiento. El historial y la auditoría no conservan números históricos completos. Las decisiones revalidan permisos en transacción frente a relevos y desactivaciones. UUID, clave interna y relaciones no cambian.

La migración deportistas.0002_identificacion_documental se aplicó con autorización en zona_bloque. En aquel cierre no había pendientes: las APIs autorizadas y paneles respondían 200 y los accesos restringidos comprobados devolvían 403. Resultados de aquel encargo: 204 pruebas PostgreSQL aisladas y 54 frontend aprobadas. El estado posterior de facultades figura en la sección siguiente. [Aplicación, respaldo y conservación](APLICACION_IDENTIFICACION_DOCUMENTAL.md).

## Facultades de acudientes — actualización posterior

Esta sección actualiza el estado histórico anterior: `deportistas.0003_comprobacion_facultades` fue autorizada, aplicada y verificada en zona_bloque. No quedan migraciones pendientes. Las consultas autorizadas de autorizaciones e historial de comprobación responden 200; contactos, vínculos y paneles siguen disponibles. No se generaron acreditaciones automáticas ni se cambió el estado pendiente del vínculo 3.

| Operación | Administrador | Coordinador activo | Profesor |
| --- | --- | --- | --- |
| Registrar revisión por finalidad/version, con método, evidencia, resultado y fechas | Sí, auditado | Sí, auditado | No |
| Registrar rechazo, revisión pendiente o revocación con historial | Sí | Sí | No |
| Consultar referencias privadas e historial de comprobación | Sí, necesidad institucional | Sí, necesidad operativa | No |
| Conceder facultad por parentesco/contacto o confirmación sin evidencia | Nunca | Nunca | Nunca |
| Registrar autorización de acudiente sin facultad verificada vigente del alcance exacto | No | No | No |

El responsable y la fecha de registro se derivan del servidor. La fecha de comprobación se registra con la revisión, sin aceptar fechas futuras. No se admiten responsables falsificados ni números de identidad, archivos o imágenes en el historial. Una decisión nueva conserva el evento anterior; el estado global antiguo no acredita ninguna finalidad. No se conceden privilegios nuevos a profesores. Las autorizaciones históricas se conservan y muestran si su fundamento sigue vigente; no se revocan masivamente por una migración.

Resultados posteriores a migrar: 235 pruebas backend PostgreSQL aisladas y 68 frontend aprobadas, 19 comprobaciones GET de permisos/compatibilidad y Django check sin incidencias. El build anterior continúa como evidencia de implementación. [Aplicación, respaldo restaurado, conservación y pruebas](APLICACION_COMPROBACION_FACULTADES.md).

## Incremento operativo 1 — destinos de propuestas entre profesores

El profesor puede proponer para un deportista de su ámbito vigente hacia un destino institucional compatible aunque no esté asignado allí. La excepción se limita a `GET /api/propuestas/destinos/` con contexto autorizado y al envío de la propuesta. Devuelve código/nombre/nivel/jornada/horarios/periodo y disponibilidad agregada. No amplía los querysets ordinarios de grupos, deportistas, inscripciones, cupos o expedientes del destino.

| Operación | Administrador | Coordinador activo | Profesor |
| --- | --- | --- | --- |
| Proponer inscripción adicional/traslado/cambio de nivel | Mantiene gestión administrativa, no suplanta autoría docente | Mantiene gestión operativa, no suplanta autoría docente | Sí, para deportista/origen de su ámbito y destino compatible |
| Consultar candidatos institucionales mediante la ruta docente específica | Utiliza consultas institucionales generales existentes | Utiliza consultas institucionales generales existentes | Solo metadatos mínimos, con contexto válido |
| Aprobar/rechazar inscripción adicional o traslado al mismo nivel | Facultades administrativas anteriores conservadas | Sí | No |
| Aprobar/rechazar cambio de nivel | No | Sí, exclusivamente | No |
| Ejecutar inscripción o traslado directamente | Facultades administrativas anteriores | Facultades operativas anteriores | No |
| Consultar alumnos/expedientes del grupo de destino ajeno por haberlo seleccionado | Según ámbito institucional existente | Según ámbito institucional existente | No |

Cambios de nivel con otra inscripción efectiva de la disciplina, incluidas reservas vigentes o altas futuras: bloqueo preventivo de propuesta y de aprobación hasta el Incremento 2. No se ejecuta un cambio parcial. Se revalidan autor, asignación de origen, vigencia, cupos, horarios, estado y versiones al aprobar; no se exige asignación del autor al destino. No hay roles nuevos ni migraciones.

Resultados: 271 pruebas PostgreSQL aisladas, 88 frontend, build y nueve recorridos de navegador aprobados. [Entrega y limitaciones](AJUSTES_PROPUESTAS_TRASLADOS.md).
