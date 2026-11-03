# Etapa 4 — Incremento A: sesiones y asistencia

Trabajo local del 2 de noviembre de 2026, en `funcionalidad-sesiones-asistencia`,
creada desde `desarrollo-zona-de-bloque`, base
`9a8fbdab05c8acaf6b6069f1ed3b4b12a06a5410`.

## Alcance implementado

- `backend/sesiones/models.py`: sesión canónica con UUID, grupo y profesor;
  revisiones numeradas de planificación; tareas por fase; padrón por inscripción;
  eventos con actor, clave idempotente, versión, solicitud y datos de corrección.
- `backend/sesiones/servicios.py`: creación, revisión del plan, registro de
  ejecución, cancelación, confirmación completa de asistencia y corrección
  extraordinaria. Cada comando y su evento se confirman en una transacción.
- `backend/sesiones/migrations/0001_initial.py`: esquema inicial, claves
  protegidas, índices y restricciones. Sin migración de datos institucionales.
- `backend/sesiones/tests.py`: reglas, permisos, revocación, idempotencia,
  versión obsoleta, referencias protegidas, padrón histórico, correcciones,
  atomicidad, currículo y concurrencia PostgreSQL.
- `backend/configuracion/settings.py`: registro de la app; conserva la barrera
  que restringe esta rama a settings de pruebas.
- `scripts/pruebas_postgresql_aisladas.py`: añade `sesiones` a las etiquetas
  permitidas y a la suite predeterminada; conserva las barreras del ejecutor.
- Inicializadores del paquete y de migraciones, más este documento.

## Decisiones de dominio

Se reutilizan Usuario y sus roles vigentes, Grupo/Nivel/Disciplina/Periodo,
Asignacion, Inscripcion, MallaVersion, ClasePrevista y EjercicioVersion. No se
duplican personas, matrículas ni calendarios. El calendario no prueba ejecución.

Una sesión planificada o realizada cuenta para el máximo de dos sesiones por
profesor y día; una cancelada libera capacidad. Se bloquean usuarios en orden
de PK, después grupo y sesión. Bloquear al profesor serializa creaciones incluso
cuando aún no existen sesiones en la fecha. Se rechazan solapamientos tanto
del profesor como del grupo. La franja debe estar dentro del período activo.

Profesor activo con rol vigente y asignación que cubra la fecha; escritura por
ese profesor o gestor de operación vigente según el contrato existente. Las
correcciones extraordinarias exigen gestor y motivo. Se recupera al actor desde
base de datos y se revalida autorización incluso en reintentos. Clave única por
actor: misma operación, versión original y datos devuelve la sesión sin otro
evento; reutilización con datos diferentes produce 409. La respuesta del comando
es la sesión actual, no una copia serializada de la respuesta histórica.

El gestor puede cancelar, cerrar asistencia o corregir registros históricos
aunque el profesor original ya esté inactivo. Esto no lo habilita para crear
planes nuevos ni registrar nuevas ejecuciones con ese profesor dado de baja.

Cada revisión crea otro PlanSesion y sus tareas; los comandos no editan las
revisiones anteriores. La ejecución fija `plan_ejecutado` a una revisión exacta.
Malla aprobada del nivel del grupo, clase de esa versión y ejercicio aprobado
de su disciplina. No se exige que una versión histórica siga siendo la vigente.
Las tareas secuenciales completan las fases inicial, central y final, y suman
la franja prevista en minutos. No se impone una duración universal. Las tareas
propias conservan instrucciones y autor a través del plan. No se modela todavía
simultaneidad ni duración real por tarea.

El padrón se captura al crear la sesión por intervalo de inscripción
`[fecha_ingreso, fecha_salida)`, incluyendo inscripciones suspendidas: el padrón
es referencia administrativa, no autorización funcional para practicar. No se
reescribe al cerrar o trasladar una inscripción, ni se interpreta vacío como
ausencia. Para sesiones creadas antes de nuevas inscripciones se necesitará un
comando explícito y auditable de actualización del padrón antes del cierre.

| Estado de sesión | Asistencia | Operaciones de cambio permitidas |
| --- | --- | --- |
| planificada | pendiente | revisar plan, cancelar, registrar ejecución |
| cancelada | pendiente | ninguna |
| realizada | pendiente | confirmar padrón completo |
| realizada | confirmada | corregir padrón completo por gestor con motivo |

La ejecución exige plan e intervalo real con zona y día de inicio en
America/Bogota. No confirma asistencia. Confirmar requiere exactamente todas
las inscripciones del padrón y un estado explícito para cada una. Una corrección
guarda los valores anteriores y enlaza el evento previo; los nuevos valores
quedan en la solicitud del evento. Motivos y observaciones no deben contener
información clínica.

## Límites y continuidad

Esta entrega es un núcleo interno de dominio, sin rutas HTTP, panel de admin,
serializers ni interfaz React nuevos. No está habilitado para uso operativo.
Los comandos preservan revisiones y padrón; no se añaden triggers de
inmutabilidad ni permisos SQL por tabla: las escrituras ORM/SQL directas ajenas
al servicio pueden eludir reglas entre entidades y no son una API soportada.
Las restricciones locales, claves únicas y PROTECT sí se aplican en base.

Antes de habilitar ejecución para usuarios, los siguientes incrementos deben:

1. Definir e implementar la autorización funcional y revisión de compatibilidad
   de actividades del contrato compartido; esta entrega no emite altas clínicas
   ni declara segura una tarea por estar aprobada en biblioteca.
2. Añadir consultas por ámbito y serializers estrictos, convertir errores de
   entrada/objeto al contrato HTTP vigente, CSRF, y pruebas de API directa,
   objeto ajeno y roles combinados. Nunca aceptar actor o timestamps de registro
   del cliente.
3. Implementar reprogramación con la misma serialización por profesor, historial
   y decisión explícita de padrón; hoy se cancela y se crea otra sesión, sin
   endpoint automático ni modificación retrospectiva de la fecha original.
4. Añadir selección de elementos curriculares, materiales docentes, seguridad
   funcional, adaptaciones y ejecución detallada de tareas. Las referencias a
   versiones exactas ya tienen su base en el esquema.
5. Añadir actualización auditable del padrón pendiente, seguimiento sobre la
   sesión canónica y React, mostrando separadamente ejecución y asistencia.

No usar asistencia como evaluación, autorización funcional o ascenso automático.
No publicar este núcleo como funcionalidad operativa antes de completar esos
contratos. No se ejecutaron pruebas de frontend porque no hubo cambios allí.

## Aislamiento y reproducción

La carpeta de trabajo admite escritura; Git requiere autorización del entorno
para escribir `.git`. La excepción `safe.directory` se pasa solo al comando,
sin modificar configuración global. `main` permanece intacta.

El script privado `scripts/ensayo_copia_restaurada.py` conserva SHA-256
`DFA5CA6798DC3FA87C0053007316A97DAEF070F32CF42AC1D43737D00063B315`;
no se modifica ni se incluye en commits.

Se reutiliza Python 3.12 del runtime y las dependencias existentes mediante
`ZDB_PAQUETES_PYTHON`, porque este checkout no contiene `.venv-local`:

```powershell
$pythonPruebas = 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:ZDB_PAQUETES_PYTHON = 'C:/Users/57310/Desktop/Proyectos_Carlos/teacher_platform_project_block_zone/.venv-local/Lib/site-packages'
& $pythonPruebas scripts/test_infraestructura_aislada.py
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --etiqueta sesiones --failfast --verbosity 1
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --failfast --verbosity 1
```

La migración se genera con `makemigrations sesiones` y
`configuracion.settings_pruebas` (SQLite en memoria); solo se aplica en el
clúster PostgreSQL efímero verificado del ejecutor. No se consulta ni migra la
base operativa. No se hace push.

Resultados:

- Barreras de aislamiento: 5 pruebas aprobadas.
- Suite específica final: 14 pruebas aprobadas (incluye dos con conexiones
  concurrentes reales y corrección tras baja del profesor), 5,877 segundos.
  Migraciones sin diferencias, clúster detenido. Evidencia privada en
  `respaldos/pruebas_etapa1_axy32k1k/resultado.json` y logs del mismo directorio.
- Primera ejecución específica: 10 pruebas aprobadas. Al añadir concurrencia,
  una ejecución intermedia detectó ausencia del catálogo tras `flush`; se corrigió
  la preparación autónoma de datos ficticios, sin cambiar migraciones previas.
- Regresión completa: 605 pruebas aprobadas en 406,933 segundos, sin diferencias
  entre modelos y migraciones y clúster detenido. Evidencia privada en
  `respaldos/pruebas_etapa1_505q_qlf/resultado.json`. Esta ejecución cargó el
  código antes del último ajuste de corrección histórica; la suite específica
  posterior de 14 pruebas valida ese ajuste y añade su caso de regresión.
- `git diff --check`: sin errores de espacios.

Para continuar, partir del commit local de esta rama, mantener el script privado
fuera de Git y ejecutar nuevamente la etiqueta `sesiones` tras cambios del núcleo.
La aplicación operativa y la publicación remota siguen pendientes de otra etapa
autorizada; no ejecutar scripts `aplicar_*` ni migraciones contra la base real.
