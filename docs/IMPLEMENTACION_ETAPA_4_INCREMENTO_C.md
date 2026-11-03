# Etapa 4 — Incremento C: currículo y ejercicios en la planificación

Base `1a88602`, rama `funcionalidad-sesiones-asistencia`. Se extienden los
modelos y comandos de A y las APIs/permisos de B. No se reconstruyen currículo,
biblioteca ni sus flujos editoriales. No se publican contenidos institucionales,
no se convierten candidatos en ejercicios y no se habilitan ejecución/asistencia.

## Selección y escritura

Nuevo selector paginado por sesión visible:

`GET /api/sesiones/{id}/opciones-plan/?tipo=programas`

| `tipo` | Parámetros adicionales | Resultado |
| --- | --- | --- |
| programas | ninguno | Programa formalizado del nivel y disciplina del grupo |
| versiones | ninguno | Mallas aprobadas y vigentes de ese programa, dentro del ámbito editorial |
| fases | `malla_version` | Fases de la versión exacta |
| semanas | `malla_version`, `fase` opcional | Semanas de esa versión/fase |
| clases | `malla_version`, `semana` opcional | Clases previstas de esa versión/semana |
| competencias | `malla_version` | Solo elementos de tipo competencia de esa versión |
| ejercicios | ninguno | Versiones aprobadas y vigentes de ejercicios compatibles con el programa |

Los parámetros de referencia son IDs numéricos; los resultados incluyen UUID
y ordinales/nombres cuando corresponde. La ruta requiere el mismo ámbito de
sesión que lista/detalle/escritura. No sirve como catálogo global accesible por
roles no docentes ni como consulta de grupos ajenos. Una clase prevista sigue
siendo una referencia pedagógica, nunca evidencia de sesión ejecutada.

Se amplía `PATCH /api/sesiones/{id}/`, conservando revisión completa del plan,
UUID idempotente y versión de sesión obligatorios. Ejemplo de forma de entrada
(los IDs son ilustrativos; usar los seleccionados por la API):

```json
{
  "clave": "8306b579-f365-4ce4-a2bf-946874716009",
  "version": 1,
  "objetivo": "Objetivo redactado por el profesor",
  "programa_id": 1,
  "malla_version_id": 3,
  "fase_curricular_id": 7,
  "semana_id": 12,
  "clase_id": 25,
  "competencias_ids": [40],
  "tareas": [
    {"fase": "inicial", "minutos": 15, "objetivo": "Preparar la actividad", "instrucciones": "Instrucción docente", "ejercicio_version_id": 9},
    {"fase": "central", "minutos": 30, "objetivo": "Objetivo docente", "instrucciones": "Actividad propia"},
    {"fase": "final", "minutos": 15, "objetivo": "Cierre", "instrucciones": "Reflexión docente"}
  ]
}
```

El total del ejemplo requiere una sesión prevista de 60 minutos. Los momentos
`fase` de tarea (`inicial`, `central`, `final`) son distintos de la referencia
`fase_curricular_id` del plan. Una tarea puede ser propia o referenciar ejercicio;
sus instrucciones y objetivo docente se conservan sin alterar la biblioteca.
El objetivo del ejercicio también queda disponible desde su versión exacta.

Programa, malla, estructura y competencias son opcionales para respetar la
autonomía metodológica. Al seleccionar malla se deriva su programa; clase deriva
semana y fase, y semana deriva fase. Una referencia explícita incompatible se
rechaza, en lugar de sobrescribirla silenciosamente. Sin malla no se admiten
fase, semana, clase ni competencias. Si solo se usan ejercicios, se registra
el programa compatible del grupo. Una actividad propia puede no tener currículo.

Competencias se seleccionan explícitamente dentro de la misma versión, sin
inferirlas ni inventarlas a partir de objetivos o clases. Pueden abarcar distintas
ubicaciones de esa malla según la decisión del profesor: no se fuerza una
equivalencia de competencia con la clase escogida. Duplicados y elementos de
otro tipo/version se rechazan.

## Compatibilidad, publicación y concurrencia

Un nuevo plan exige malla aprobada **y vigente**, de programa formalizado y
compatible con el nivel/disciplina del grupo. Un ejercicio nuevo exige aprobación,
vigencia, disciplina coincidente y vinculación explícita al programa del grupo.
Acceso técnico, autoría del borrador o rol administrador no dispensan estas
reglas. Un ejercicio sin programa no se presume universal. No se equipara
compatibilidad de programa con autorización funcional individual.

Se mantiene la suma exacta de minutos con la franja de sesión, duración positiva,
las tres fases y orden secuencial. Además se respetan los límites mínimo/máximo
de duración del ejercicio cuando están informados; null no se convierte en cero
ni en una duración predeterminada. No se modelan actividades simultáneas.

La validación curricular se centraliza en el servicio, después de comprobar
estado, versión e idempotencia, y se aplica también a llamadas internas. Bloqueo:
usuarios por PK → grupo → sesión → malla seleccionada → ejercicios por PK.
La publicación editorial existente bloquea usuarios antes de versiones, lo que
serializa publicación/retiro con la planificación. También se bloquean las
versiones y se revalida su elegibilidad tras bloquearlas. No se añade un atajo
que permita publicar contenido desde sesiones.

Retiro concurrente: si se confirma primero el plan, guarda una referencia
histórica válida; si se confirma primero el retiro, la selección se rechaza.
Dos planes concurrentes con la misma versión siguen produciendo un éxito y
un 409, sin dos revisiones confirmadas. Se conservan los controles de cuenta,
roles múltiples, asignaciones y revocación de B.

Un reintento idéntico devuelve el resultado confirmado incluso si después se
retira la fuente, siempre que el actor aún conserve autoridad sobre la sesión.
Crear otra revisión exige nuevamente contenido vigente. La validación de fuentes
se movió del adaptador HTTP al comando para distinguir esos casos correctamente.

## Historia y persistencia

PlanSesion incorpora programa, fase curricular, semana, enlace a revisión
anterior, competencias mediante `CompetenciaPlan` y marca interna de sellado.
TareaSesion añade objetivo docente. Se mantienen las FK previas a malla, clase
y ejercicio. Todas las referencias nuevas de historia usan PROTECT.

Número 1 y `revision_anterior=null` identifican el plan original. Cada revisión
enlaza el plan inmediatamente anterior; no se actualiza su contenido. El comando
inserta plan, tareas y competencias, comprueba coherencia y sella el conjunto en
la misma transacción que actualiza la sesión y crea el evento. Fallos revierten
todo el conjunto, sin planes parciales publicados a otros lectores.

La migración PostgreSQL protege planes sellados contra UPDATE/DELETE y tareas/
competencias contra adiciones, ediciones, traslados o eliminaciones. Al sellar
comprueba además duración, secuencia y cadena de revisiones. Las referencias
cruzadas de currículo y elegibilidad se validan en el servicio: estos triggers
no son un sustituto de permisos de base frente a SQL administrativo arbitrario.
Un plan en construcción solo existe dentro de la transacción del comando.

La migración de actualización conserva planes preexistentes: deriva programa de
su malla, fase/semana de su clase cuando existen, enlaza revisiones consecutivas
y sella sus tareas. No crea competencias, objetivos institucionales ni currículo
faltante. El objetivo nuevo de tareas anteriores queda vacío. Se prueba el paso
desde el esquema de A hasta este esquema usando datos ficticios anteriores.

La consulta de B incluye planificación completa y referencias exactas, UUID,
número editorial, competencias y descripción del ejercicio. `estado_actual` y
`vigente_actual` son metadatos actuales de publicación, expresamente separados
del contenido histórico elegido. La lectura no busca la última versión ni exige
que una fuente histórica siga vigente. Los contenidos de ediciones publicadas
ya están congelados por las protecciones editoriales existentes.

## Archivos y migraciones

- `backend/sesiones/models.py`: extensiones mínimas de plan/tarea y enlace de competencias.
- `backend/sesiones/curricular.py`: elegibilidad y resolución de referencias.
- `backend/sesiones/servicios.py`: integración atómica, validación y sellado.
- `backend/sesiones/serializers.py`: nuevas entradas y lectura completa.
- `backend/sesiones/views.py`: selector por objeto y consulta precargada de revisiones.
- `backend/sesiones/migrations/0002_plansesion_fase_curricular_plansesion_programa_and_more.py`: esquema aditivo.
- `backend/sesiones/migrations/0003_planes_inmutables.py`: actualización de historia y protecciones PostgreSQL reversibles.
- `backend/sesiones/test_curricular.py`: integración, historia, migración y carrera con retiro.
- Este informe. Sin cambios de datos/código de publicación en currículo, biblioteca o recursos.

## Verificación aislada

Python 3.12.14 y dependencias reutilizadas mediante `ZDB_PAQUETES_PYTHON`, como
en A/B. El esquema aditivo se genera sin aplicar migraciones, con settings de
SQLite en memoria; **todas las pruebas se ejecutan únicamente en PostgreSQL
temporal**, con las barreras y apagado del ejecutor existente.

```powershell
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --etiqueta sesiones --etiqueta curriculo --etiqueta biblioteca --etiqueta recursos --failfast --verbosity 1
```

Ejecuciones intermedias aprobadas:

- 31 pruebas de regresión de sesiones con las nuevas migraciones.
- 96 pruebas de sesiones/currículo/biblioteca/recursos, 89,845 segundos,
  evidencia privada `respaldos/pruebas_etapa1_09hlm81e/`.
- 44 pruebas de sesiones incluyendo carrera con retiro y actualización desde A,
  19,945 segundos, evidencia privada `respaldos/pruebas_etapa1_6q2irqm_/`.

En todas, migraciones sin diferencias y clúster detenido. La ejecución final
incorpora los casos adicionales de malla retirada y ejercicio de otro programa:
**100 pruebas aprobadas en 97,443 segundos**, system check sin incidencias,
`makemigrations --check --dry-run` sin diferencias y clúster detenido.
Evidencia privada: `respaldos/pruebas_etapa1_heeajx59/resultado.json` y logs del
mismo directorio. `git diff --check` sin errores. No se repite la auditoría ni
la suite general de etapas anteriores.

## Continuidad hacia D

No hay transición HTTP a realizada ni comandos HTTP de asistencia nuevos.
Antes de habilitarlos debe resolverse la autorización funcional pendiente.
La ejecución futura debe fijar `plan_ejecutado` a un plan sellado exacto, conservar
objetivos/instrucciones originales y registrar realización/duración real por
separado; no convertir minutos planificados en reales. Si cambia una restricción
funcional después de planificar, debe revalidarse antes de ejecutar.

No inferir asistencia a partir de currículo, clase o ejecución. El padrón sigue
siendo el capturado en A; actualizarlo exige el comando auditable pendiente.
Confirmación y correcciones deben reutilizar sus versiones, eventos y ámbito
de B. Reprogramación, tareas simultáneas, adaptaciones individuales y React
quedan pendientes; esta entrega no inicia esos incrementos.

Sin cambios en `main`, sin push y sin migraciones ni consultas operativas.
El único script privado no versionado permanece intacto y excluido:
`scripts/ensayo_copia_restaurada.py`.
