# Diseño funcional definitivo — empresa pequeña y coordinador único

Decisión del propietario del 28 de octubre de 2026. **Ampliación autorizada implementada: 114 pruebas backend, 33 frontend; migración PostgreSQL pendiente.** Véanse [verificación](VERIFICACION_COORDINACION_TABLERO.md) y [plan](MIGRACION_COORDINADOR_UNICO.md).

| ID | Requisito objetivo | Criterio de aceptación futuro |
|---|---|---|
| OR-01 | Administrador principal, un coordinador activo y varios profesores | Sin jerarquías ni supervisiones individuales |
| CO-01 | Coordinador responsable de toda la plantilla docente | Incluye profesores nuevos y sin grupo sin asignación de supervisor |
| CO-02 | Consultar/gestionar grupos, horarios y asignaciones docentes | Reutilizar modelos y servicios; validar cupos, fechas, historial y cruces |
| CO-03 | Máximo un coordinador activo | Validación de backend y futura restricción condicional en Usuario |
| CO-04 | Conservar historial de relevos | Eventos de inicio/fin con actor, usuario y fecha; no borrar cuentas ni reatribuir evidencias |
| AD-01 | Control administrativo global | Usuarios, configuración institucional, seguridad y reportes separados de la gestión coordinadora |
| AD-02 | Tablero general con estadísticas reales | Profesores, grupos, coordinador actual/vacante, periodos y asignaciones; detalles reconciliables |
| PR-01 | Profesor limitado a sus grupos y actividades | Sin administración de personal, horarios institucionales o estadísticas generales |
| SE-01 | Backend como autoridad | Sesión, rol, cuenta activa y autorización por operación; CSRF y transacciones |
| AU-01 | Auditar operaciones sensibles | CambioAdministrativo para cambios y relevo; sin secretos |
| FU-01 | Indicadores pedagógicos posteriores | Dependen de sesiones, asistencia, cumplimiento y valoraciones aún no implementados |
| EV-01 | Separar código autorizado de migración pendiente | Implementación aprobada; no aplicar la nueva migración PostgreSQL sin otra aprobación |

El diseño reemplaza la supervisión por parejas coordinador–profesor, los grupos delegados y la duda sobre múltiples coordinadores. No se propone una tabla nueva de supervisión ni de jerarquías.

Referencias: [matriz](MATRIZ_PERMISOS.md), [propuesta técnica e implementación](AMPLIACION_COORDINACION.md) y [plan de tableros](PLAN_TABLEROS.md).

La documentación de Fase 2 siguiente conserva la referencia anterior. La implementación actual de coordinación y tableros se describe en el nuevo informe; sesiones, asistencia y valoraciones siguen fuera de alcance.

> Actualización del 28 de octubre de 2026: las cuatro migraciones de Fase 2 ya están aprobadas y aplicadas en zona_bloque, con respaldo previo y 88 comprobaciones de integración. [Informe de aplicación](APLICACION_MIGRACIONES_FASE_2.md). Las menciones posteriores a aprobación pendiente corresponden al estado histórico.

# Requisitos implementados — Fase 2

Fase 1 verificada: 21 pruebas backend, 10 frontend y build aprobados; npm audit pendiente de conectividad. Fase 2 ya migrada con aprobación expresa; cualquier ampliación adicional requiere su revisión y autorización.

| Requisito | Implementación | Verificación |
|---|---|---|
| A: Usuarios | cuentas/servicios_usuarios, recuperación y Usuarios.jsx | 20 pruebas nuevas de backend y pruebas de pantalla |
| B: Disciplinas/niveles | organizacion, migración inicial de catálogos y Catalogos.jsx | Restricciones, cinco niveles y formularios |
| C: Grupos/asignaciones | Grupo, Horario, Periodo, Asignacion y servicios | 32 pruebas de organización |
| D: Profesor | Alcance por asignación vigente, Grupos y Calendario | Rechazo de grupos ajenos y caducidad |
| E: Coordinador | Grupos, Profesores y Asignaciones filtradas | Rechazo de grupos ajenos y profesores fuera de ámbito |
| F: Administración React | Usuarios, Catalogos, Grupos, Asignaciones | 14 pruebas nuevas de interfaz y navegador |
| Seguridad transversal | Sesiones/CSRF, transacciones, auditoría y bajas lógicas | Suite completa 73 backend, 24 frontend, 6 cliente HTTP |

La matriz y API detalladas están en [FASE_2.md](FASE_2.md); los resultados y límites en [VERIFICACION_FASE_2.md](VERIFICACION_FASE_2.md).

El apartado de Fase 1 siguiente conserva su estado histórico; las funciones que allí figuran como posteriores, pero están incluidas en A–F, ya se implementaron.

# Requisitos y trazabilidad

Estado: Fase 1 autorizada. Implementación presente; validación funcional integral pendiente según VERIFICACION_FASE_1.md.

| ID | Requisito autorizado | Implementación / pantalla | API o modelo | Validación prevista |
|---|---|---|---|---|
| F1-01 | React, JavaScript, Vite, Sass | frontend/src y vite.config.js | No aplica | Build y pruebas de interfaz |
| F1-02 | Django/DRF modular | backend/configuracion, cuentas, paneles, comun | Rutas API | Django check |
| F1-03 | PostgreSQL por entorno | .env.example y settings.py | Base PostgreSQL | Migraciones y suite PostgreSQL |
| F1-04 | Sesiones seguras | Ingreso, contexto y cliente HTTP | csrf, ingresar, sesion, salir | CSRF, cookies, rotación y logout |
| F1-05 | Tres roles en servidor | TieneRolDelPanel | Usuario.rol y restricción DB | Matriz de 3 x 3 accesos |
| F1-06 | Paneles iniciales | Panel, Estructura y Perfil | /api/paneles/{rol}/ | Restauración, denegación y menú |
| F1-07 | Identidad y logo pendiente | Marca y tokens Sass | Sin recursos externos | Revisión visual cuando haya build |
| F1-08 | Secretos y privacidad | .gitignore, .env.example | Sin credenciales por defecto | Revisar índice antes de publicar |
| F1-09 | Pruebas de acceso | cuentas/tests y frontend/src/pruebas | IsAuthenticated | Anónimo, inactivo, cambio de rol |
| F1-10 | Trazabilidad básica de acceso | EventoAcceso | ingreso/salida/fallo | Pruebas de auditoría |
| F1-11 | Conservar remoto | REPOSITORIO_REMOTO.md | Lectura de GitHub | Sin modificaciones remotas |

## Contrato API de Fase 1

| Método y ruta | Acceso | Entrada / salida |
|---|---|---|
| GET /api/autenticacion/csrf/ | Público | csrfToken; establece cookie CSRF |
| POST /api/autenticacion/ingresar/ | Público con CSRF | usuario, contrasena; devuelve usuario y csrfToken rotado |
| GET /api/autenticacion/sesion/ | Autenticado | usuario: id, username, nombre, rol |
| POST /api/autenticacion/salir/ | Autenticado con CSRF | detalle de cierre |
| GET /api/paneles/profesor/ | Profesor | rol, nombre, mensaje |
| GET /api/paneles/coordinador/ | Coordinador | rol, nombre, mensaje |
| GET /api/paneles/administrador/ | Administrador | rol, nombre, mensaje |

Errores tratados: detalle textual y errores por campo cuando corresponda. Sesión ausente o acceso denegado devuelven 403 con SessionAuthentication. Credenciales inválidas devuelven 400; exceso de solicitudes 429. No se envía la contraseña en respuestas.

## Rutas de interfaz

- /ingresar
- /profesor y /profesor/perfil
- /coordinacion y /coordinacion/perfil
- /administracion y /administracion/perfil

Los módulos siguientes se muestran como próximos, sin botones que simulen operaciones inexistentes.

## Criterios de aceptación pendientes de ejecución integral

- Sin sesión no se consulta ningún panel.
- Cada rol solo consulta su endpoint de panel.
- Un rol enviado por el cliente no modifica permisos.
- Desactivar una cuenta o cambiar su rol surte efecto en la siguiente solicitud.
- Login sin CSRF u origen externo se rechaza.
- Logout requiere POST y CSRF y revoca la sesión anterior.
- La aplicación opera con PostgreSQL y no requiere credenciales en el código.
- Los tres paneles se revisan a 390 px, 768 px y escritorio, con teclado y sin desbordamiento.
- El logo oficial y datos reales siguen ausentes.

## Fuera de alcance

Estudiantes, inscripciones, grupos operativos, sesiones de clase, asistencia, semáforo, valoraciones, ascensos automáticos, importadores, correo real, despliegue y push. Su planificación se conserva en el prompt maestro.
