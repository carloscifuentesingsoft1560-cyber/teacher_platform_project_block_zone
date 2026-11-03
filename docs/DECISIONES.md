# Decisión definitiva: coordinación única de toda la empresa

> Etapa 2, copia de integración: se implementó el diseño autorizado de roles múltiples, cargo único y formalización administrativa exclusiva. Una persona con roles coordinador y administrador puede ejercer ambas facultades mediante acciones diferentes auditadas; no se exige separación personal adicional. No se migró la base operativa ni se publicaron cambios. [Informe de la copia aislada](IMPLEMENTACION_ETAPA_2_NUCLEO.md).

> Vigencia, 2 de noviembre de 2026: el contenido original se conserva como historial. Las referencias antiguas a migraciones pendientes y cifras de pruebas se interpretan con [la reconciliación vigente](RECONCILIACION_VIGENTE_2026_11.md). La autorización de Etapa 1 limita roles múltiples y separación de ascensos a diseño; no se implementan facultades nuevas. [Informe de la entrega](INFORME_ETAPA_1_ESTABILIZACION.md).

Fecha: 28 de octubre de 2026. Estado: implementación autorizada completada; migración de unicidad pendiente en PostgreSQL. [Informe](VERIFICACION_COORDINACION_TABLERO.md).

- Estructura inicial: administrador principal, un único coordinador activo y varios profesores.
- El coordinador es responsable operativo y pedagógico de todos los profesores, tengan o no grupo, sin supervisiones individuales ni delegaciones por profesor.
- Puede gestionar grupos, horarios y asignaciones docentes bajo las validaciones institucionales. El alcance es toda la operación de Zona de Bloque.
- Administración conserva usuarios, privilegios, credenciales, configuración institucional, seguridad y reportes. El coordinador no se nombra ni se amplía privilegios.
- Cada profesor conserva acceso exclusivo a sus grupos y actividades pedagógicas autorizadas.
- Se descarta AsignacionSupervision y la estructura de coordinadores simultáneos. No se añaden tablas de jerarquía o supervisión.
- Se propone reutilizar Usuario.rol/is_active y una futura restricción condicional de unicidad para coordinación activa.
- El historial del cargo se registrará con CambioAdministrativo mediante acciones explícitas de inicio/fin, dentro del relevo transaccional.
- Cambiar de coordinador no borra personas ni reasigna la autoría de registros previos, y no exige trasladar profesor por profesor.
- El tablero administrativo inicial usará datos reales de profesores, grupos, coordinador, periodos y asignaciones, incluidos profesores sin grupo.
- Indicadores de sesiones, asistencia, cumplimiento y valoraciones quedan para entregas posteriores, con fuentes y reglas propias.
- Se mantienen las sesiones Django/CSRF, la auditoría de cambios sensibles, las bajas lógicas y las reglas de conservación.
- Se implementaron permisos, relevo, historial y tableros. Se generó una migración de unicidad, sin aplicarla en PostgreSQL; requiere aprobación específica del propietario.

Esta decisión sustituye la propuesta anterior de supervisión por parejas y grupos delegados. La cuestión de varios coordinadores está cerrada: solo uno activo. Las dependencias restantes son técnicas de implementación y las reglas de los módulos pedagógicos futuros.

Referencias: [matriz](MATRIZ_PERMISOS.md), [propuesta simplificada](AMPLIACION_COORDINACION.md) y [tableros](PLAN_TABLEROS.md).

## Referencia de decisiones y entregas anteriores

> Actualización del 28 de octubre de 2026: las cuatro migraciones de Fase 2 ya están aprobadas y aplicadas en zona_bloque, con respaldo previo y 88 comprobaciones de integración. [Informe de aplicación](APLICACION_MIGRACIONES_FASE_2.md). Las menciones posteriores a aprobación pendiente corresponden al estado histórico.

# Actualización — Fase 2

- El propietario autorizó módulos A–F y solicitó detenerse antes de aplicar migraciones reales. Se generaron cuatro migraciones y no se aplicaron en PostgreSQL.
- Se usaron los paquetes .venv-local existentes; no se instalaron dependencias globales ni se alteró su intérprete base.
- Se mantiene el login, sesiones y CSRF. Vite usa cargador runner por restricciones de inspección de directorios.
- Códigos únicos, campos mínimos de cuentas y catálogos configurables; sin mallas ni contenido inventado de Alto rendimiento.
- Asignación con fechas inclusivas y tipo histórico. Fecha final vacía vence al terminar el periodo. Las consultas se limitan al ámbito actual; el calendario no abre acceso a grupos ajenos o ya abandonados.
- Se rechazan solapamientos de la misma asignación y cruces docentes. Los coordinadores pueden cubrir grupos simultáneos. Horarios sin cruce de medianoche y con precisión de minutos.
- Cambios estructurales de grupos/periodos con historial requieren un registro nuevo; la finalización de una asignación no la elimina ni reabre.
- La recuperación exige reautenticación administrativa, token aleatorio almacenado como hash, caducidad de 30 minutos y un solo uso; no se envían mensajes reales.
- La consola Django queda de consulta de usuarios; la API administrativa centraliza cambios, permisos y auditoría.
- npm audit no pudo contactar al registro; queda pendiente, sin afirmar ausencia de vulnerabilidades.
- No se implementaron estudiantes, sesiones, asistencia, semáforo, evaluación ni promociones.

Los detalles y reglas están en [FASE_2.md](FASE_2.md). Las decisiones históricas de Fase 1 siguientes se conservan; las referencias a interfaz de gestión futura o dependencias no instaladas quedan sustituidas por esta actualización y por el cierre comprobado.

# Decisiones

## Aprobadas por el propietario

- Arquitectura general de Fase 0.
- Implementación de Fase 1 dentro del directorio actual.
- React/JavaScript/Vite/Sass, Django/DRF y PostgreSQL.
- Sesiones Django, cookies HttpOnly, CSRF y tres roles.
- Sin importaciones reales ni lógica de asistencia, semáforo o promoción.
- Sin push a GitHub.

## Decisiones de implementación de Fase 1

1. Nuevas carpetas backend/ y frontend/; no se reemplaza antigravity-app remoto.
2. AbstractUser con campo rol y restricción de base de datos. Nombres ingleses heredados se conservan por convención Django.
3. Django 5.2 LTS y DRF 3.18.x; versiones exactas y dependencias transitivas quedan pendientes de resolver al recuperar acceso a registros.
4. Autenticación de mismo origen mediante proxy Vite. No se incorporan JWT ni CORS abierto.
5. CSRF explícito en login anónimo. Token JSON en memoria y cookies HttpOnly.
6. Paneles específicos por rol, sin herencia automática entre sus rutas.
7. Auditoría mínima de autenticación, sin guardar credenciales ni identidad del intento fallido.
8. Sin creación automática de cuentas. Contraseñas interactivas y validación mínima de 12 caracteres para cuentas nuevas.
9. SQLite en memoria solo con settings_pruebas para pruebas aisladas; PostgreSQL para la aplicación y validación de integración.
10. No se genera un lockfile ficticio. npm install no completó; las dependencias aún no están resueltas ni auditadas.
11. La consola Django sirve como herramienta administrativa inicial; la gestión completa de cuentas en React se planifica después.
12. Los eventos de acceso son de solo lectura y las cuentas se desactivan desde la consola, sin opción de eliminación.

## Pendientes antes de módulos posteriores

- Acceso del profesor a captura, resultados e historial de valoraciones.
- Significado de RETIRO y correcciones administrativas de asistencia.
- Cómputo del tercer día, cierre de mes y entregas posteriores.
- Franjas múltiples por grupo y excepciones de duración.
- Identificación mínima de estudiante e incompatibilidad de inscripciones.
- Alcance de coordinadores y acceso histórico de profesores.
- Política de edición/archivado de sesiones con asistencia.
- Significado del límite de dos copias.
- Equivalencias de niveles y correcciones curriculares.
- Baremos, ponderaciones y política de promoción.
- Logo oficial autorizado.

El documento original existe como archivo remoto sin extensión, pero el conector rechazó su contenido por ser binario o no UTF-8. No fue importado, alterado ni usado para introducir reglas adicionales.
