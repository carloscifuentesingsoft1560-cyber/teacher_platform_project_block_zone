# Etapa 4 — Incremento D: ejecución registrada y asistencia definitiva

Base `0a9edca`, rama `funcionalidad-sesiones-asistencia`. Se reutilizan A/B/C,
sus permisos por objeto, claves idempotentes, versiones, planes sellados y
eventos. No se inicia E/F. No se consulta ni modifica la base operativa.

## Resultado y única operación bloqueada

Se implementan APIs funcionales para registrar y consultar ejecución real,
finalizar su informe, preparar/guardar/cerrar asistencia, consultar participantes
y resumen, y corregir excepcionalmente asistencia cerrada por administración.
Los cierres generan evidencia inmutable y eventos en transacción.

**La validación a `realizada` sigue bloqueada por una definición institucional
pendiente.** El repositorio no contiene fuente competente de autorización
funcional por participante y actividad, restricciones estructuradas y vigencia.
Las autorizaciones de `deportistas` son consentimientos/finalidades y facultades
de otorgantes, no una autorización de práctica. El contrato compartido exige que
la falta de información funcional no se convierta en permitido. Ver
`CONTRATOS_COMPARTIDOS_FUTUROS.md`, sección de planificación/restricciones, y la
continuidad de C. No se inventa una facultad clínica para profesor, coordinador
o administrador ni se introduce una casilla cliente para eludirla.

Se separan el registro retrospectivo de hechos declarados y la validación
institucional. Finalizar el informe registra lo ocurrido y lo congela; no
autoriza práctica ni certifica seguridad. La sesión conserva `estado=planificada`
y expone `estado_ejecucion=registrada_pendiente_validacion`. Este segundo estado
es explícito para evitar presentar el informe cerrado como una clase futura o
como una ejecución autorizada. `plan_ejecutado`, `inicio_real` y `fin_real` de la
sesión se reservan para la validación; los tiempos declarados y el plan exacto
ya existen en EjecucionSesion y su API.

`POST realizar` pasa ahora por un comando de dominio con permisos, estado,
versión, ejecución finalizada y asistencia cerrada. La frontera
`verificar_autorizacion_funcional` rechaza con 403 al faltar la fuente competente.
Una protección adicional de PostgreSQL impide saltar directamente a realizada
mediante INSERT/UPDATE. No se libera el estado desde una vista o serializer.

## Endpoints

Todas las rutas siguientes parten de `/api/sesiones/{id}/`, con ID numérico.
Reutilizan sesión Django, CSRF y el ámbito de B. Escrituras requieren `clave`
UUID y `version` de sesión. Respuesta de comando: `{sesion, asistencia}` con la
versión resultante. GET de ejecución devuelve `{version, ejecucion}`.

| Método | Sufijo | Operación |
| --- | --- | --- |
| GET | `participantes/` | Participantes elegibles actuales; padrón histórico si está cerrado |
| POST | `asistencia/preparar/` | Actualizar explícitamente padrón abierto, con motivo |
| GET | `asistencia/` | Padrón, estados guardados/cerrados y correcciones |
| POST | `asistencia/` | Guardar lote completo, aún editable si no está cerrado |
| POST | `asistencia/cerrar/` | Cerrar asistencia definitivamente |
| GET | `asistencia/resumen/` | Conteos por estado, faltantes y necesidad de preparar padrón |
| POST | `asistencia/corregir/` | Corrección administrativa de un deportista, con valor anterior/nuevo y motivo |
| GET | `ejecucion/` | Plan exacto e informe, actividades y tiempos reales |
| POST | `ejecucion/` | Crear o actualizar borrador retrospectivo completo |
| POST | `ejecucion/finalizar/` | Finalizar informe; cerrar asistencia completa en la misma transacción si aún está abierta |
| POST | `realizar/` | Validar sesión: bloqueada únicamente por la autorización funcional pendiente |

Los JSON son estrictos en raíz y actividades. Actor, responsable, timestamps
de registro/cierre, estado y autorizaciones no se aceptan del cliente. No hay
DELETE ni sustitución administrativa del lote cerrado. Entradas inválidas son
400; objetos fuera de ámbito, 404; facultades insuficientes, 403; versión/clave
en conflicto o valor anterior obsoleto, 409. Repetir exactamente una operación
confirmada devuelve 200 y el estado actual sin duplicar eventos. Para repetir,
se envían clave, versión original y cuerpo originales; una clave nueva no es
un reintento de la anterior.

## Registro de ejecución

POST de borrador recibe los campos siguientes, además de clave y versión:

```json
{
  "plan": 12,
  "inicio": "2026-11-02T10:00:00-05:00",
  "fin": "2026-11-02T10:45:00-05:00",
  "observaciones": "Observaciones pedagógicas, sin datos clínicos",
  "incidencias_pedagogicas": "Incidencias no clínicas",
  "actividades": [
    {"tarea": 31, "resultado": "realizada", "minutos": 10, "descripcion": "Actividad efectuada"},
    {"tarea": 32, "resultado": "modificada", "minutos": 20, "descripcion": "Lo que se hizo", "adaptacion_metodologica": "Cómo se adaptó"},
    {"tarea": 33, "resultado": "omitida", "minutos": 0, "motivo_omision": "Motivo docente"}
  ]
}
```

Los IDs del ejemplo son ilustrativos. El plan debe pertenecer a la sesión y
estar sellado. Se selecciona una revisión exacta; una revisión posterior no
la sustituye automáticamente. Todas sus tareas deben figurar exactamente una
vez. No se admite una tarea ajena ni una lista parcial/duplicada.

Realizada exige minutos positivos y descripción. Modificada exige además
adaptación metodológica. Omitida exige cero minutos y motivo, sin adaptación
ejecutada. No se mezclan motivos de omisión con realización. Una sustitución
metodológica se describe como modificación de la tarea original; no se crean
ejercicios institucionales ni tareas planificadas retroactivas.

Inicio/fin requieren ISO con zona explícita; el servidor normaliza a UTC.
Inicio debe caer en el día de sesión en America/Bogota, fin debe ser posterior
y no futuro. El intervalo máximo de este registro es 24 horas. La duración real
se obtiene del intervalo, separada de los minutos planificados. La suma de
minutos efectivos no puede excederlo; el tiempo restante se devuelve como
`tiempo_no_distribuido_minutos` (por ejemplo pausas/transiciones), sin inventar
actividad ni convertirlo en carga o intensidad.

El borrador se reemplaza únicamente antes del cierre, conservando solicitudes
anteriores en eventos. Una nueva revisión curricular puede coexistir con un
borrador ya referido a una revisión anterior. Tras finalizar informe, no se
edita el registro ni sus actividades, ni se modifica la planificación por vías
ordinarias. No se añade un mecanismo de corrección de ejecución finalizada en D.

Puede registrarse retrospectivamente una exposición a una versión retirada
después de planificar: se conserva lo declarado, sin permitir seleccionar esa
fuente en un nuevo plan ni declarar segura su práctica. La API muestra la
revisión histórica y sus referencias curriculares/biblioteca exactas.

## Elegibilidad y asistencia

Se reutiliza Asistencia y su FK a Inscripcion. Se añade FK protegida al
Deportista como identidad estable, con unicidad por sesión/deportista además de
sesión/inscripción. No se duplica persona ni matrícula. Se valida el intervalo
de inscripción `[fecha_ingreso, fecha_salida)`, grupo y día de sesión. Una
inscripción finalizada después del día conserva su elegibilidad histórica;
una que empieza después o termina ese día no entra. El estado administrativo
actual no reconstruye suspensiones históricas inexistentes en el modelo:
figurar en padrón no equivale a permiso de práctica.

Inscripciones superpuestas del mismo deportista producen error de revisión de
matrícula: no se elige silenciosamente una ni se registra dos veces. Si cambió
la matrícula desde A, la consulta abierta informa `requiere_preparacion`;
guardar/cerrar exige sincronización explícita. Preparar requiere motivo, agrega
elegibles y elimina únicamente sobrantes sin estado guardado. Si hay estados
guardados fuera del padrón o cambia la identidad de una inscripción, se exige
revisión administrativa sin perder/asignar datos a otra persona. El evento
conserva padrón anterior y resultante.

Guardar recibe `registros`, diccionario de IDs de inscripción como claves y
valores `asistio`, `no_asistio`, `tarde`, `excusa`, `retiro` o vacío mientras se
prepara. Debe incluir exactamente el padrón, sin IDs añadidos o eliminados.
Cerrar exige todos los estados explícitos y elegibilidad revalidada. No se
cierra una fecha futura. El padrón vacío no genera asistencias ficticias ni
valida práctica: el cierre es administrativo y la validación funcional continúa
bloqueada.

Se elimina la antigua implicación de base `asistencia_confirmada → realizada`:
la asistencia puede cerrarse independientemente del flujo funcional pendiente.
No se altera silenciosamente el estado para satisfacer esa restricción. Una
sesión cancelada no admite escrituras ni asistencia cerrada. Tampoco se cancela
por el comando ordinario una sesión con informe registrado o asistencia cerrada.

Tras cierre, GET devuelve el padrón guardado, no recalcula participantes desde
la matrícula actual. Los identificadores permanecen aunque cambie después la
inscripción. Nombres/apellidos se muestran desde la identidad actual, sin
documento, fecha de nacimiento, contactos ni información de otros grupos.

## Correcciones excepcionales

Se exige **administración vigente**, no coordinación. Profesor responsable,
coordinador sin administración, acudiente y deportista no pueden corregir.
Tener varios roles conserva únicamente las facultades vigentes; perder
administrador y conservar coordinador no permite continuar corrigiendo.

Entrada: `deportista`, `anterior`, `nuevo`, `motivo`, clave y versión. La sesión
y persona deben identificar una asistencia cerrada dentro del ámbito del actor.
Anterior debe coincidir con el estado actual; nuevo debe ser distinto y válido.
Un ID ajeno no se usa para buscar fuera de esa sesión.

CorreccionAsistencia conserva asistencia/inscripción/persona, anterior/nuevo,
actor y timestamp de servidor, motivo y evento exclusivo. El evento enlaza la
corrección anterior del mismo registro, o el cierre original. Se crea también
CambioAdministrativo con nombres de campos, sin copiar valores personales o
texto clínico al registro administrativo general. Evento, corrección y cambio
de la proyección Asistencia se confirman atómicamente. Si falla auditoría,
revierte incluso el cambio aplicado por trigger.

La corrección se inserta como evidencia inmutable; un trigger valida rol,
cuenta activa, cierre, valor anterior y correspondencia exacta del evento antes
de actualizar la proyección. No se usa un flag cliente o setting de conexión
para permitir UPDATE ordinario. No se borran eventos ni correcciones previas.

## Transacciones, seguridad e inmutabilidad

Orden de escritura: usuarios por PK → grupo → sesión → filas de asistencia o
ejecución. El ámbito se reconsulta tras bloquear usuarios. Se reutiliza el
protocolo de bloqueo de matrícula/roles existente; SQL administrativo que
ignore ese protocolo no es un canal de aplicación soportado.

Solo el profesor responsable con rol activo y asignación que cubra hoy y el día
de sesión registra/cierra ejecución o asistencia. Administración/coordinación
pueden consultar su ámbito institucional, pero su rol de gestión no suplanta
al profesor para registrar actividad. La corrección usa la facultad separada
de administración y puede hacerse tras baja del profesor original.

PostgreSQL protege:

- Unicidad de asistencia por persona/sesión y por inscripción/sesión.
- Elegibilidad y coherencia de identidad al insertar participantes.
- Identidad de cada asistencia contra reasignación.
- Asistencia cerrada contra modificación, eliminación, ampliación y reapertura.
- Contexto de sesión cerrado contra cambios de grupo, profesor, fecha y franja.
- Informe finalizado y actividades contra edición/eliminación/traslado.
- Pertenencia de tareas al plan elegido y coherencia de resultados/duraciones.
- Eventos y correcciones contra actualización/eliminación.
- Entrada directa a realizada mientras siga pendiente el contrato funcional.

Las protecciones son de aplicación/base, no una defensa frente al propietario
PostgreSQL que deshabilite triggers o altere el esquema.

## Archivos y compatibilidad

- `backend/sesiones/models.py`: registro de ejecución, actividades, correcciones
  y FK/unicidad por deportista en Asistencia; cierre desacoplado de realizada.
- `backend/sesiones/ejecucion.py`: comandos, elegibilidad, cierres, corrección,
  resúmenes y frontera funcional cerrada.
- `backend/sesiones/serializers_ejecucion.py`: entradas estrictas y consulta de informe.
- `backend/sesiones/views.py`: endpoints nuevos y adaptación de realizar al comando.
- `backend/sesiones/serializers.py`: estado de registro de ejecución en la sesión.
- `backend/sesiones/servicios.py`: se retiran atajos internos antiguos de realizar/
  confirmar/corregir; se conservan creación y planificación con nuevas protecciones.
- `backend/sesiones/migrations/0004_actividadejecutada_correccionasistencia_and_more.py`:
  esquema aditivo y desacoplamiento de asistencia.
- `backend/sesiones/migrations/0005_cierre_definitivo.py`: completar identidad de
  asistencias anteriores, NOT NULL y triggers reversibles. Si existen duplicados
  históricos de persona/sesión, la actualización falla sin eliminarlos; exige
  revisión explícita antes de una futura activación.
- `backend/sesiones/test_ejecucion.py`: pruebas de D y concurrencia PostgreSQL.
- Pruebas `tests.py`, `test_api.py`, `test_curricular.py`: se adaptan al cierre
  independiente, retirada de atajos y restauración de migraciones hasta D.
  Se verifica también la actualización de asistencias antiguas desde A.
- Este informe. Sin cambios de modelos o permisos de otras apps.

## Pruebas y evidencia

Pruebas exclusivamente con el ejecutor PostgreSQL temporal verificado del
repositorio, Python 3.12.14 y dependencias locales reutilizadas indicadas en A.
La generación del esquema aditivo usa settings de SQLite en memoria sin aplicar
migraciones; no se ejecutan pruebas SQLite ni scripts operativos.

```powershell
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --etiqueta sesiones --etiqueta curriculo --etiqueta biblioteca --etiqueta recursos --etiqueta cuentas.tests.test_acceso --failfast --verbosity 1
```

Resultados intermedios aprobados:

- 46 pruebas anteriores de sesiones, incluidas nuevas migraciones y backfill.
- 17 pruebas iniciales de D, incluidas cierre/corrección concurrentes,
  12,735 segundos; `respaldos/pruebas_etapa1_au91qmw4/`.
- 86 pruebas de sesiones + autenticación/CSRF, 43,332 segundos;
  `respaldos/pruebas_etapa1_ithztw6m/`.

Las carreras con conexiones reales comprueban 200/409 para dos cierres con
claves distintas; 200/200 con un solo evento para el mismo cierre o finalización
reintentados simultáneamente; y una sola corrección/evento cuando compiten dos
rectificaciones. Se comprueban rollback ante fallo de evento/auditoría,
inmutabilidad SQL posterior, todos los estados, elegibilidad, CSRF, roles
múltiples, revocación, IDs ajenos, intervalos, planes históricos y restricción
funcional tanto en API como en UPDATE directo de PostgreSQL.

Una ejecución ampliada intermedia detectó que el trigger nuevo de eventos
dependía de la función inmutable de recursos sin declarar esa dependencia en
el grafo de migraciones. Falló al revertir Etapa 3 durante su ensayo aislado.
Se añadió la dependencia explícita de `0005` a `recursos.0002_integridad_editorial`,
sin alterar migraciones anteriores ni usar DROP CASCADE.

**Resultado final: 141 pruebas aprobadas en 123,912 segundos**: 68 de sesiones,
54 de currículo/biblioteca/recursos y 19 de acceso/autenticación. Incluye 22
pruebas nuevas de D. System check sin incidencias, `makemigrations --check
--dry-run` sin diferencias, clúster temporal detenido y `git diff --check` sin
errores. Evidencia privada en
`respaldos/pruebas_etapa1_5wqu7jif/resultado.json` y logs del mismo directorio.
No se repite la auditoría general ni la suite ajena al alcance.

## Continuidad: única decisión pendiente y seguimiento posterior

Para liberar validación a realizada hace falta definir institucionalmente:
quién emite autorización funcional y con qué facultad; fuente y vigencia por
participante; restricciones y actividades permitidas con versión; criterio
permitido/incompatible/requiere revisión; tratamiento de revocaciones entre
planificación, práctica y registro; y segregación de detalle clínico. Esas
decisiones deben implementarse en un proveedor verificable, con bloqueo y
evidencia, antes de reemplazar la frontera cerrada y su protección SQL. No basta
un mock, una variable de entorno, un consentimiento ni una declaración docente.

La posterior validación deberá fijar `plan_ejecutado` al plan del informe,
no al más reciente, y conservar tiempos reales e historial de autorización.
Seguimiento e informes deberán distinguir asistencia definitiva, informe
retrospectivo finalizado y ejecución validada, así como plan/real/omitido y
minutos efectivos/no distribuidos. No convertir asistencia en evaluación o
ascenso, ni contar varias revisiones como exposiciones nuevas. No se implementan
todavía esos informes, React, seguimiento E ni funcionalidad F.

Trabajo local exclusivamente en `funcionalidad-sesiones-asistencia`. Sin cambios
en `main`, sin push ni migraciones operativas. El script privado
`scripts/ensayo_copia_restaurada.py` permanece sin modificar y fuera del commit.
