> Estado vigente, 28 de octubre de 2026: cuentas.0004_usuario_un_coordinador_activo fue autorizada y aplicada exclusivamente en zona_bloque, con respaldo integral verificado. Índice válido, sin migraciones pendientes, 21 comprobaciones PostgreSQL y dos rechazos concurrentes aprobados; datos existentes intactos. [Informe de aplicación](APLICACION_COORDINADOR_UNICO.md). Las referencias a migración pendiente o integración aún no ejecutada del documento siguiente describen el estado anterior a esta aplicación.

# Propuesta simplificada: un coordinador para toda la empresa

Decisión definitiva del propietario, 28 de octubre de 2026. Estado: **ampliación implementada y probada; migración generada, sin aplicar en PostgreSQL**. [Informe actual](VERIFICACION_COORDINACION_TABLERO.md).

## 1. Decisión y simplificación

Zona de Bloque tendrá inicialmente un administrador principal, un único coordinador activo y varios profesores.

El coordinador es responsable de toda la operación docente: consulta a todos los profesores y gestiona sus grupos, horarios y asignaciones. No administra cuentas, privilegios, seguridad ni configuración institucional. El profesor conserva solo sus responsabilidades y grupos.

Quedan descartadas:
- AsignacionSupervision entre parejas coordinador–profesor.
- Delegaciones por profesor o grupo para el cargo coordinador.
- Jerarquías, equipos de varios coordinadores o resolución de supervisiones simultáneas.
- Tablas o interfaces de supervisión individual.

La [matriz](MATRIZ_PERMISOS.md) y el [plan de tableros](PLAN_TABLEROS.md) reflejan este acuerdo. La incertidumbre sobre coordinadores simultáneos queda resuelta: no se admiten.

## 2. Aprovechamiento del modelo existente

| Modelo o función existente | Uso propuesto |
|---|---|
| Usuario.rol e is_active | Identificar administrador, coordinador activo y profesores |
| Grupo, Disciplina, Nivel y Periodo | Organización de toda la escuela |
| Horario | Calendario y cambios de entrenamiento, conservando filas anteriores |
| Asignacion de tipo profesor | Asignación de docentes a grupos, con vigencia y fin de periodo |
| CambioAdministrativo | Auditoría y registro de relevos del cargo |
| Servicios de organización | Reutilizar validaciones de cupos, fechas, catálogos, cruces e integridad |
| Componentes React de gestión | Reutilizar formularios, errores, confirmaciones, listados y paginación |
| PanelVista | Ampliar posteriormente con resúmenes calculados desde datos reales |

No se propone ninguna tabla nueva para supervisión o jerarquías.

Las Asignacion de tipo coordinador que ya existan se conservan como historial; dejarán de ser la fuente del alcance operativo. No habrá que crear una por cada grupo nuevo. Las asignaciones docentes se mantienen como fuente de los grupos de cada profesor.

## 3. Coordinador activo único

Fuente de verdad propuesta: una cuenta activa con rol coordinador. No se añade otro rol ni un indicador duplicado en otra tabla.

Para la futura implementación:
- Validación administrativa que impida crear o activar un segundo coordinador.
- Restricción condicional de unicidad en Usuario para rol coordinador con is_active verdadero.
- Revalidación transaccional ante cambios concurrentes.
- Cero coordinadores se representa como vacante; nunca se crea una cuenta ficticia ni se elige arbitrariamente un titular.
- Si la revisión previa detecta más de uno activo, administración resolverá la situación antes de aplicar la restricción; no se desactivarán cuentas automáticamente.
- La estructura inicial prevé una cuenta administradora principal, sin crear niveles administrativos adicionales ni modificar cuentas existentes por implicación.

Esta restricción está en cuentas.0004_usuario_un_coordinador_activo, **generada pero no aplicada en PostgreSQL**. [Plan pendiente de aprobación](MIGRACION_COORDINADOR_UNICO.md). Las cuatro migraciones de Fase 2 aplicadas permanecen intactas.

## 4. Historial del cargo sin nuevas tablas

CambioAdministrativo ya conserva actor, entidad, identificador, acción y fecha de servidor. Se propone usar acciones explícitas:
- coordinacion_inicio: identifica a la persona que asume el cargo.
- coordinacion_fin: identifica a la persona que lo deja.

La entidad será cuentas.usuario y el identificador será el usuario afectado; el actor será el administrador que autoriza. Se conservan las cuentas anteriores y todos los eventos. El historial se reconstruye por persona y fecha de esos eventos, sin copiar nombres o credenciales en el registro. No se filtra por el rol actual de la persona: si un excoordinador pasa a profesor, su etapa anterior se conserva.

No se inventarán fechas anteriores a esta política. Para el titular inicial se registrará una confirmación administrativa desde una fecha conocida, indicando cuando no exista historia previa verificable.

### Relevo propuesto

1. Administración selecciona a la persona entrante y confirma el relevo.
2. El servicio bloquea las cuentas afectadas en orden estable y revalida autoridad administrativa, elegibilidad del entrante y cualquier asignación incompatible con un cambio de rol. No fuerza ni borra dichas asignaciones.
3. Retira la condición de coordinador activo al saliente y registra coordinacion_fin.
4. Activa el rol de coordinador del entrante y registra coordinacion_inicio.
5. Confirma ambas modificaciones y eventos en la misma transacción.
6. Si cualquier validación falla, revierte el conjunto: nunca deja dos coordinadores activos.
7. El saliente pierde permisos de coordinación en su siguiente solicitud. No se transfiere su identidad ni la autoría de registros previos.

No se decide automáticamente si el saliente continúa como profesor o sale de la empresa. Administración debe indicar si se desactiva su cuenta o se le asigna otro rol, respetando las incompatibilidades actuales y cerrando las asignaciones que corresponda. No se alteran las asignaciones de los profesores por cambiar el coordinador.

Crear, activar, desactivar o cambiar el rol de una cuenta coordinadora debe pasar por este mismo servicio y su auditoría; un PATCH de usuario no puede evitarlo. Las fechas de inicio/fin del cargo son las de los eventos reales, sin añadir programación futura del puesto.

## 5. Autorización operativa simplificada

| Rol | Alcance | Escrituras |
|---|---|---|
| Administrador principal | Toda la institución autorizada | Usuarios, configuración, seguridad y operación |
| Coordinador activo único | Todos los profesores y grupos de la empresa | Grupos, horarios, asignaciones docentes y seguimiento autorizado |
| Profesor | Sus grupos y responsabilidades | Funciones pedagógicas propias según módulo |

Grupos que podrá gestionar coordinación: código, nombre, cupo, estado, horarios y selección de disciplina/nivel/periodo existentes. Se mantienen las restricciones que impiden reescribir la estructura de grupos con historial; coordinación no crea catálogos ni modifica seguridad.

Cambiar un horario compartido requiere comprobar y mostrar los profesores afectados y validar conflictos. Como hay un único coordinador, no hay permisos de otros equipos coordinadores que conciliar.

No basta ampliar LecturaOAdministracion globalmente: esa clase también protege catálogos. Se propone autorizar coordinación solo en las vistas/servicios de grupos, horarios, calendario y asignaciones docentes.

bloquear_usuarios mantiene la separación entre bloqueo y autorización por acción. EsAdministrador no se amplía para admitir coordinadores en cuentas o recuperación.

La autorización sigue comprobándose en servidor, antes y dentro de transacciones, con sesiones Django y CSRF. Los datos sensibles no necesarios para la operación continúan fuera de las respuestas coordinadoras.

## 6. API propuesta para reutilizar

| Ruta | Cambio futuro propuesto |
|---|---|
| GET /api/organizacion/profesores/ | Coordinador: todos los profesores, incluidos los que no tienen grupo; filtros de estado |
| GET/POST/PATCH /api/organizacion/grupos/ y :id/ | Permitir gestión operativa al coordinador, con validaciones y sin DELETE |
| GET /api/organizacion/calendario/ | Coordinador: calendario operativo de la empresa; profesor: solo propio |
| GET/POST /api/organizacion/asignaciones/ | Coordinador: asignaciones docentes institucionales; profesor: solo propias |
| POST /api/organizacion/asignaciones/:id/finalizar/ | Permitir al coordinador finalizar asignaciones docentes, preservando historial |
| GET /api/organizacion/coordinacion/ | Titular actual; historial del cargo disponible a administración |
| POST /api/organizacion/coordinacion/relevar/ | Solo administrador: relevo o primera designación, en transacción |
| GET /api/paneles/administrador/resumen/ | Estadísticas institucionales organizativas reales |
| GET /api/paneles/coordinador/resumen/ | Resumen operativo institucional, sin datos de seguridad |
| /api/usuarios/ y catálogos | Conservan escritura administrativa |

Las rutas operativas y los resúmenes de esta propuesta ya están implementados. El único cambio de esquema está pendiente; no hay rutas de supervisiones por profesor. Los nuevos accesos no requieren modificar las rutas de autenticación ni suplantar roles.

## 7. Auditoría y conservación

- Reutilizar CambioAdministrativo para actor, objeto, operación, campos y fecha.
- Registrar creación/modificación/archivado de grupo, cambios de horario y altas/finalizaciones docentes.
- Conservar versiones de Horario y vigencias de Asignacion, como en los servicios existentes.
- Usar eventos explícitos para el cargo coordinador y mantener todas las identidades anteriores.
- No borrar usuarios, grupos con historial ni eventos de auditoría.
- Mantener contraseñas, tokens y datos personales innecesarios fuera de la auditoría operativa.
- Administración consulta auditoría completa autorizada; coordinación solo la operativa necesaria, sin información de seguridad.
- Las auditorías y cambios correspondientes se confirman o revierten juntos.

No se requiere ampliar el esquema de auditoría para registrar inicio/fin del cargo. Si posteriormente se necesita información adicional, se presentará como otro cambio específico.

## 8. Plan de implementación autorizado; migración PostgreSQL pendiente

| Incremento | Alcance | Reutilización / dependencia |
|---|---|---|
| S1: cargo único e historial | Unicidad, servicio de relevo y registro de inicio/fin | Usuario y CambioAdministrativo; aprobar la futura restricción antes de migrar |
| S2: coordinador operativo | Todos los profesores; gestión de grupos, horarios y asignaciones | APIs, validaciones y formularios existentes; permisos específicos |
| S3: tablero general administrativo | Conteos y listas reales de profesores, grupos, coordinador, periodos y asignaciones | ORM sobre modelos existentes; sin tablas de indicadores |
| S4: panel de coordinación | Equipo completo, calendario, grupos y accesos de gestión | Componentes React existentes y resumen operativo |
| S5: verificación | Regresión, permisos, concurrencia de relevo, auditoría y conteos | Datos ficticios, PostgreSQL y pruebas de interfaz |
| Posterior | Sesiones, asistencia, cumplimiento y valoraciones | Diseñar sus módulos y reglas antes de sus indicadores |

S3 no depende de una tabla de supervisiones. Se puede desarrollar con datos organizativos actuales cuando se autorice; el cambio completo de autoridad coordinadora deberá incorporar S1.

## 9. Criterios de aceptación futuros

- No se crea ni activa un segundo coordinador, tampoco con solicitudes concurrentes o rutas administrativas alternativas.
- El coordinador consulta profesores sin grupo y gestiona toda la operación docente, sin asignaciones personales de supervisión.
- Puede crear/editar/archivar grupos y gestionar horarios/asignaciones dentro de los campos permitidos.
- No puede crear cuentas, cambiar roles, recuperar credenciales, redefinir catálogos ni concederse privilegios.
- El profesor no consulta grupos ajenos ni modifica personal u horarios oficiales.
- El relevo conserva actor, saliente, entrante y fechas; nunca elimina identidades ni reatribuye evidencias.
- Un fallo a mitad del relevo revierte cuentas y auditorías; el saliente pierde autoridad aunque conserve una sesión abierta.
- Los datos de los tableros coinciden con los detalles consultables, sin duplicar personas por número de grupos.
- La ausencia de un coordinador se muestra como vacante y no como un titular inventado.
- Los indicadores de módulos inexistentes no muestran cifras ficticias o porcentajes.
- Se mantiene la suite existente y se añaden pruebas específicas de estos comportamientos.

## 10. Estado de esta entrega

La ampliación autorizada se implementó sin renovar los estilos ni alterar login. Se ejecutaron 114 pruebas backend, 33 frontend y 22 vistas de navegador con API ficticia. El resumen también se comprobó sobre zona_bloque en transacción de solo lectura. No se modificaron cuentas reales ni se aplicó la migración pendiente. La concurrencia y garantía del índice en PostgreSQL se verificarán después de su aprobación.
