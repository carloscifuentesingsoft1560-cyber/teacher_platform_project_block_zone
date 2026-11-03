> Estado vigente, 28 de octubre de 2026: cuentas.0004_usuario_un_coordinador_activo fue autorizada y aplicada exclusivamente en zona_bloque, con respaldo integral verificado. Índice válido, sin migraciones pendientes, 21 comprobaciones PostgreSQL y dos rechazos concurrentes aprobados; datos existentes intactos. [Informe de aplicación](APLICACION_COORDINADOR_UNICO.md). Las referencias a migración pendiente o integración aún no ejecutada del documento siguiente describen el estado anterior a esta aplicación.

# Plan simplificado de tableros — empresa pequeña

Decisión definitiva del 28 de octubre de 2026: administrador principal, único coordinador activo y varios profesores. **Tableros organizativos implementados y probados; migración de coordinador único pendiente.** [Resultados actuales](VERIFICACION_COORDINACION_TABLERO.md).

Referencias: [matriz](MATRIZ_PERMISOS.md) y [propuesta simplificada](AMPLIACION_COORDINACION.md). Se sustituyen la planificación de equipos de varios coordinadores y los indicadores de supervisión individual.

## 1. Tablero general del administrador

Objetivo: mostrar el estado real de la empresa y facilitar el acceso a usuarios, grupos, catálogos, periodos, asignaciones y reportes autorizados.

Cobertura del tablero y evolución propuesta:
- Tarjetas con profesores activos/inactivos, grupos activos/inactivos, coordinador actual o vacante, periodos y asignaciones docentes vigentes.
- Listas de profesores sin grupo, grupos sin profesor y grupos sin horario.
- Desglose de grupos por disciplina, nivel y periodo.
- Calendario institucional.
- Historial de cambios de coordinador y acceso al relevo, exclusivo de administración.
- Accesos a usuarios, configuración institucional, seguridad, auditoría y reportes existentes/autorizados.

La entrega implementada cubre los indicadores solicitados de profesores, grupos, coordinador, periodos y asignaciones, filtros, resumen de disciplinas/niveles e historial del cargo. Las listas adicionales de grupos sin profesor o sin horario quedan como evolución posterior, sin cifras simuladas.

Se usan Usuario, Grupo, Periodo, Asignacion, Horario y CambioAdministrativo. No hacen falta tablas nuevas de estadísticas, jerarquías ni supervisiones.

El titular único no se obtiene del endpoint actual de profesores por grupos; se obtiene de Usuario.rol e is_active. Los docentes sin asignación forman parte de la empresa y deben incluirse.

## 2. Panel del coordinador

Objetivo: gestionar toda la operación docente con una interfaz sencilla.

Secciones propuestas:
1. Resumen operativo de profesores, grupos, periodos y asignaciones.
2. Profesores: toda la plantilla, con estado y grupos; los inactivos se consultan, pero no reciben asignaciones nuevas.
3. Grupos: crear, editar, archivar y consultar, reutilizando formularios actuales.
4. Asignaciones: asignar/finalizar profesores a grupos y revisar vigencias.
5. Horarios y calendario: visualizar toda la operación, editar entrenamientos y comprobar cruces.
6. Historial operativo: actor, fecha y cambios autorizados.
7. Supervisión pedagógica: se incorporará después de implementar sesiones, asistencia, observaciones y reglas de seguimiento.

No tendrá pantallas de gestión de cuentas, privilegios, credenciales o configuración de seguridad. No habrá selector de coordinador, administración de equipos coordinadores ni pantalla para asignar cada profesor a un supervisor.

Los profesores nuevos se incorporan al listado automáticamente por su rol. El relevo no obliga a reasignar uno por uno los grupos o profesores.

## 3. Panel del profesor

Mantiene sus grupos, horarios oficiales y calendario propio. Gestionará sus actividades pedagógicas cuando esos módulos estén implementados y autorizados.

No muestra estadísticas generales, fichas de otros profesores, asignaciones ajenas o administración de grupos institucionales. La gestión pedagógica propia no permite modificar el horario oficial ni las asignaciones de personal.

## 4. Definiciones propuestas para estadísticas iniciales reales

| Dato | Fuente y definición | Nota |
|---|---|---|
| Profesores activos/inactivos | Usuarios con rol profesor, separados por is_active | Estado actual de la cuenta; incluye docentes sin grupo |
| Coordinador actual | Único Usuario activo con rol coordinador | Ninguno: vacante; varios antes de activar la restricción: incidencia, sin elegir arbitrariamente |
| Grupos activos/inactivos | Grupo separado por activo, filtrable por disciplina/nivel/periodo | Personas asignadas no multiplican el conteo |
| Periodos activos/inactivos | Periodo separado por activo | Distinguir estado configurado de fecha de inicio/fin |
| Periodo en curso | Fecha de corte entre inicio y fin, inclusivos | Puede haber más de un periodo formativo en curso; no confundir con el cargo coordinador |
| Asignaciones docentes vigentes | Tipo profesor; inicio hasta corte; fin efectivo igual a fecha_fin o fin del periodo | Desglosar actividad de usuario/grupo/periodo para identificar las operativas |
| Asignaciones operativas | Vigentes más cuenta, grupo y periodo activos | No equivale a cumplimiento pedagógico |
| Profesores activos sin grupo operativo | Docentes activos sin asignación operativa en el periodo/corte consultado | Etiquetar el filtro para no sugerir que carecen de grupo en toda su historia |
| Grupos activos sin profesor | Grupo activo sin asignación docente operativa en el corte | No contar asignaciones de tipo coordinador como docentes |
| Grupos activos sin horario | Grupo activo sin Horario activo | Dato organizativo, sin deducir sesiones incumplidas |
| Grupos por nivel/disciplina/periodo | Conteo de grupos distintos por dimensión | Cada tarjeta indica sus filtros |
| Historial del coordinador | Eventos coordinacion_inicio/coordinacion_fin en CambioAdministrativo | Solo fechas conocidas, sin inventar historia anterior |

Las métricas organizativas descritas se implementaron con ORM y filtros; el resumen se comprobó también en PostgreSQL en modo solo lectura. Las métricas pedagógicas del apartado siguiente siguen sin implementarse.

El filtro de periodo afecta a grupos/asignaciones y a las métricas que lo indiquen. La tarjeta de personal institucional seguirá indicando si representa el total actual o una población filtrada. No se reconstruye el rol o estado pasado de una cuenta usando únicamente sus campos actuales.

## 5. Indicadores posteriores

| Bloque futuro | Dependencia antes de calcular |
|---|---|
| Sesiones y planificación | Modelo de sesión, autoría, estados y fechas aprobados |
| Asistencia | Registro, bloqueo, población esperada y reglas de consulta |
| Cumplimiento y oportunidad | Responsabilidades, plazos, denominadores y políticas versionadas |
| Observaciones y atención de ajustes | Modelo e historial de observaciones, estados de seguimiento |
| Valoraciones | Instrumentos aprobados, escalas, cálculos y permisos específicos |

Por ahora se omiten estas cifras o se indica no disponible. No mostrar cero, 100 %, valoraciones simuladas o alertas de incumplimiento para módulos inexistentes.

No se introduce aprobación obligatoria del coordinador antes de publicar sesiones ni edición de asistencia confirmada. Estas reglas se mantienen según la planificación institucional previa.

## 6. Presentación y reutilización

- Reutilizar Estructura, Marca, Campo, listados, mensajes, confirmaciones y estilos Sass de gestión.
- Mantener login, sesiones y CSRF.
- Añadir resúmenes mediante agregaciones ORM sencillas sobre los datos existentes.
- Reutilizar páginas de Grupos, Asignaciones y Calendario en coordinación con botones autorizados; no copiar toda la aplicación.
- Mostrar filtros, fecha de corte y zona America/Bogota.
- Cada tarjeta debe llevar a su detalle autorizado y reconciliar su conteo.
- Contar profesores/grupos distintos para evitar duplicaciones por relaciones.
- Mantener tablas legibles, controles accesibles y navegación móvil.
- No incorporar por esta necesidad colas, jerarquías, permisos por supervisor o infraestructura adicional.

## 7. Wireframes conceptuales

```text
ADMINISTRADOR
[Fecha de corte · disciplina · nivel · periodo]
[Profesores] [Grupos] [Coordinador actual] [Periodos]
[Asignaciones vigentes] [Sin grupo] [Grupos sin profesor]
[Calendario institucional] [Listas de detalle]
[Usuarios] [Configuración] [Seguridad] [Auditoría]
[Historial y relevo del coordinador]
[Indicadores pedagógicos: posteriores]

COORDINADOR
[Resumen operativo de toda la escuela]
[Todos los profesores] [Grupos] [Asignaciones]
[Horarios y calendario] [Conflictos y confirmaciones]
[Gestión operativa e historial]
[Sesiones/asistencia/seguimiento: posteriores]

PROFESOR
[Mis grupos] [Mis horarios] [Mi calendario]
[Mis actividades y responsabilidades: según módulo]
```

Los wireframes describen la distribución funcional. La implementación reutiliza las tarjetas, formularios y tablas existentes, sin renovación gráfica.

## 8. Secuencia de implementación y estado

1. Cargo único e historial con Usuario y auditoría; revisar y aprobar la futura restricción de unicidad.
2. Permisos operativos del coordinador en servicios y APIs existentes, sin habilitar administración de cuentas.
3. Estadísticas reales y tablero administrativo con los modelos actuales.
4. Panel coordinador reutilizando gestión de grupos, asignaciones y calendario.
5. Pruebas de permisos, relevo concurrente, historial, conteos, estados vacíos y experiencia móvil.
6. Incorporar posteriormente sesiones, asistencia, cumplimiento y valoraciones con sus reglas específicas.

Las pruebas nuevas comprueban esos casos, además de permisos, rollback del relevo, conflictos compartidos y coherencia entre conteos y detalles. La nueva restricción de unicidad solo está pendiente de aprobación para PostgreSQL. Véase el [plan de migración](MIGRACION_COORDINADOR_UNICO.md).
