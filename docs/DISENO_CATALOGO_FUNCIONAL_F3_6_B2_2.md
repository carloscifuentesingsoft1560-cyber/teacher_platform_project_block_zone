# F3.6-B2.2 — Catálogo funcional versionado

Base: `interfaz-sesiones-react`, `fde9075a134d0270413b24318c05c23a4f724c5b`.
Implementación técnica de propuestas. **Pendiente de revisión y aprobación institucional.**
No contiene catálogos, competencias ni autorizaciones reales. No habilita B2.3.

## Separación de decisiones

- Un perfil propuesto describe exigencias; no determina aptitud ni autoriza personas.
- Una revisión documental registra observaciones; no aprueba funcionalmente el contenido.
- Una correspondencia propuesta vincula referencias exactas; no demuestra cobertura individual.
- La aprobación editorial existente de un ejercicio sigue siendo exclusivamente editorial.
- No existen comandos, estados ni permisos de aprobación funcional institucional.
- Las autorizaciones individuales y la validación de sesiones están fuera de alcance.
- Los expedientes B1/B2.1 siguen pendientes: no constituyen acreditaciones vigentes.

El registro interno exige administración vigente e identidad acreditada. Es una barrera
de custodia documental, no el reconocimiento de competencia profesional. La autoridad
que pueda aprobar perfiles o correspondencias requiere una decisión institucional y
otro incremento autorizado. No hay endpoints ni integración automática con APIs.

## Entidades y relaciones

`PerfilFuncional` conserva UUID y disciplina. `PerfilFuncionalVersion` conserva número,
antecesora, nombre y alcance. El contenido es inmutable desde su inserción; para cambiarlo
se registra una versión completa nueva. No se modifican versiones anteriores.

`ExigenciaPerfilFuncional` reutiliza `TerminoActividad` del namespace `exigencia_funcional`.
Conserva código, nombre y significado históricos, estado del conocimiento, tipo, operador,
valor y unidad propuesta. Desconocido o pendiente de revisión exige ausencia de valores;
un número exige unidad explícita, un booleano/texto no admite unidad numérica. Los valores
son declaraciones documentales propuestas, sin evaluación clínica ni umbrales aprobados.
Una unidad propuesta no se interpreta como unidad institucional normalizada.
`TerminoActividad` ya está protegido contra UPDATE/DELETE por recursos 0003 y no dispone
de ediciones propias. Una entrada distinta no modifica la anterior ni constituye una
equivalencia o sucesión institucional: solo una nueva versión explícita del perfil puede
referenciarla, conservando el término y significado de las versiones anteriores.

`CondicionPerfilFuncional` referencia una exigencia de la misma versión y describe condición
y método verificable. `AdaptacionPerfilFuncional` referencia una condición de esa versión,
con alternativa y límites. Estas relaciones no son restricciones personales ni una prueba
automática de compatibilidad de la adaptación ejecutada.

`ProcedenciaPerfilFuncional` referencia un fragmento documental exacto e inmutable del
dominio recursos y registra su justificación. No contiene evidencia clínica individual.
Se exige al menos una exigencia y una procedencia al confirmar una versión.

`CorrespondenciaFuncional` conserva UUID y exactamente un destino protegido:
`EjercicioVersion`, `TareaSesion` o `ActividadEjecutada`. Una identidad por destino evita
cadenas paralelas; sus sucesivas versiones pueden documentar cambios de interpretación.
`CorrespondenciaFuncionalVersion` referencia el perfil exacto, su último evento documental,
una instantánea verificable del contexto, justificación y adaptación explícita opcional.

`EventoPerfilFuncional` y `EventoCorrespondenciaFuncional` conservan acciones exclusivamente
`propuesta`, `revision` y `retiro`, secuencia, antecesor, actor, persona histórica, enlace,
versión y evidencia de identidad, clave de idempotencia, solicitud y motivo. Los servicios
también registran la auditoría administrativa existente, en la misma transacción.

## Referencias exactas e historia

- Ejercicio: edición editorial aprobada, con instantánea de sus campos persistentes.
- Tarea: plan sellado, tarea y plan exactos; no se altera el plan.
- Actividad: ejecución finalizada, actividad, tarea y ejecución exactas. Una actividad
  omitida no es destino funcional de práctica; una modificada exige adaptación explícita
  de la misma versión de perfil. Su correspondencia continúa siendo una propuesta.
- No se heredan vínculos del ejercicio a la tarea ni de la tarea a la práctica.
- No se generan equivalencias por nombres o por valores booleanos del frontend.
- Un perfil sustituido/retirado o una revisión obsoleta no fundamenta nuevas actuaciones.
  Se conserva el vínculo histórico; para cambiar su fundamento se crea otra versión.
- El retiro es terminal en la cadena afectada; no se reabre mediante otra versión.
- Las fechas de registro de las nuevas tablas se fijan en PostgreSQL al insertar.
  Documentar posteriormente una actividad no crea una autorización retroactiva.

## Integridad, concurrencia y límites

Relaciones PROTECT, unicidad por identidad/número, antecesoras sin bifurcaciones y checks
de contenido/destino se complementan con guardias SQL. Las verificaciones entre tablas
no se delegan a `clean()` ni a la API. Todos los modelos rechazan actualización,
eliminación y bulk_update en ORM; SQL rechaza UPDATE/DELETE incluso sin cambiar valores.
El primer evento sella los detalles. Los constraint triggers diferidos exigen primera
versión, primer evento, exigencias y procedencia al confirmar la transacción.

Los servicios siguen el orden global de bloqueo de usuarios de B1/B2.1 antes de identidades
y cabeceras. Los triggers comparten ese bloqueo. Esto serializa escrituras y cambios de
roles/identidad, con riesgo conocido de contención. Se controla versión esperada y clave
de idempotencia por actor entre ambos tipos de eventos. Un reintento idéntico recupera el
evento; otra solicitud o identidad se rechaza. Un error revierte la operación completa.

No se modifica `verificar_autorizacion_funcional()` ni los triggers de sesiones, fuentes,
B1 o B2.1. No se incorpora decisión favorable, consulta de aptitud ni concesión operativa.

## Migraciones

`0004_catalogo_funcional_b2_2` es aditiva: crea diez entidades, claves e índices de relaciones,
unicidad y checks. Depende de biblioteca 0003, cuentas 0011, recursos 0003 y sesiones 0007,
además de las dependencias de identidad/organización generadas por Django. Sesiones depende
de biblioteca 0003, por lo que la dependencia hacia sesiones 0007 no cierra un ciclo.

`0005_guardias_catalogo_funcional_b2_2` añade funciones y triggers con prefijo propio B2.2.
Es deliberadamente irreversible: retirar las guardias dejaría historial sin protección.
No debe habilitarse una instalación parcialmente migrada hasta 0004. No se reescriben
migraciones anteriores ni se cargan catálogos o correspondencias iniciales. Revertir 0004
aisladamente eliminaría las tablas; no es un procedimiento autorizado de despliegue.

## Verificación y ejecución aislada

La suite específica contiene 37 pruebas. Reutiliza exclusivamente fixtures ficticias B2.1
y comprueba referencias, tipos, historia, inmutabilidad, retiro, rollback, idempotencia,
concurrencia real, integridad SQL, planes y ejecuciones, B1/B2.1 y bloqueo de realizada.
Los timeouts/deadlocks/errores de infraestructura no se aceptan como rechazos esperados.
No sustituye una regresión completa del sistema.

Historial de verificaciones:

- Verificador estático satisfactorio: sintaxis de siete archivos Python, diez modelos,
  cincuenta barreras ORM, acciones cerradas, grafo acíclico y `No changes detected`.
  Se ejecutó con backend dummy y prohibición de conexión; no cargó settings ni .env.
- La invocación de barreras se detuvo antes de descubrir pruebas. Se utilizó
  `python -I -B scripts/test_infraestructura_aislada.py`; `-I` excluyó el directorio
  del script de la búsqueda de módulos y falló `import pruebas_postgresql_aisladas`.
  Error: `ModuleNotFoundError: No module named 'pruebas_postgresql_aisladas'`.
  Código de salida 1. Pruebas de barreras ejecutadas: cero de las 24 previstas.
- No se repitió la invocación ni se corrigió código después del fallo.
- PostgreSQL no se inició; pruebas B2.2 ejecutadas: cero de las 37 preparadas.
  Las migraciones 0004/0005 no se aplicaron. Su SQL, concurrencia e integridad real
  permanecen pendientes de verificación. No se creó un directorio de evidencias PostgreSQL.

- En la reanudación autorizada posterior pasaron 24/24 barreras sin `-I`. La primera
  ronda PostgreSQL descubrió 37 pruebas: 14 satisfactorias, una con error y 22 sin ejecutar.
  `test_15_significado_historico_del_termino` intentó renombrar directamente un término
  protegido. El trigger existente `zdb_e3_identidad` rechazó el UPDATE con SQLSTATE 23514
  (`CheckViolation`). La prueba esperaba que esa modificación fuera posible; el rechazo
  fue la protección correcta. Las migraciones 0004/0005 se aplicaron correctamente.
  Al imprimir la excepción hubo además un `UnicodeEncodeError`: la salida del ejecutor
  utilizaba CP1252 y no podía codificar U+FFFD procedente de la decodificación del mensaje.
  El ejecutor preservó evidencia parcial y detuvo su hijo sin incidentes. No ejecutó el
  chequeo de modelos/migraciones. Evidencia anterior intacta:
  `C:\Users\57310\AppData\Local\Temp\zdb_pg_hqx1p_it`.
- Con nueva autorización se corrigió únicamente la prueba 15: exige el rechazo SQL del
  renombrado, comprueba el término original intacto y crea otra entrada ficticia de
  vocabulario, referenciada por una nueva versión del perfil. Verifica tanto el nuevo
  vínculo como la permanencia del término, código, nombre y significado históricos.
  No se modificaron modelos, servicios, migraciones, triggers ni el ejecutor.
- La verificación estática posterior pasó: siete archivos Python, diez modelos, cincuenta
  barreras ORM, grafo acíclico y `No changes detected`, sin SQL ni .env. Pasaron 24/24
  barreras en una sola ejecución (1.285 segundos).
- La única ronda PostgreSQL de esta autorización descubrió y ejecutó 37 pruebas: 37
  aprobadas, cero fallidas, cero errores y cero omitidas, en 95.347 segundos. La base nueva
  fue `test_zdb_fase3_d7d5a29faa34`. Se aplicaron las migraciones anteriores y 0004/0005;
  pasaron referencias exactas, inmutabilidad ORM/SQL, eventos obligatorios, retiro,
  restricciones, rollback, concurrencia real, idempotencia concurrente y las protecciones
  específicas de B1/B2.1 y sesiones. La prueba 34 confirmó el bloqueo Python/SQL de
  `realizada`; no se habilitó aprobación institucional operativa. No hubo regresión completa.
- El chequeo posterior devolvió `No changes detected`, código 0. `resultado.json` confirma
  pruebas=0, migraciones_check=0, detenido=true, identidad revalidada y pg_ctl solicitado,
  sin terminación forzada ni incidentes de limpieza. El PID hijo fue 23640, host
  `127.0.0.1`, puerto 49887. Evidencias nuevas conservadas en:
  `C:\Users\57310\AppData\Local\Temp\zdb_pg_hh89j7o3`.

La invocación de barreras utiliza `-B`, sin `-I`. Se prepararon `PYTHONIOENCODING=utf-8`
y `PYTHONUTF8=1`; como el ejecutor usa `-I` e ignora esas variables Python, se añadió
`-X utf8` a su invocación para configurar explícitamente la salida del proceso padre.
No se alteró el entorno positivo de los hijos ni las barreras del ejecutor.
No se atribuyen resultados históricos a la ronda nueva. La publicación sigue pendiente
de revisión y autorización; no se hizo commit ni push.

Comando previsto, después de las comprobaciones estáticas y las 24 barreras:

```powershell
$pythonPruebas = 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:ZDB_PAQUETES_PYTHON = 'C:/Users/57310/Desktop/Proyectos_Carlos/teacher_platform_project_block_zone/.venv-local/Lib/site-packages'
$env:ZDB_LIBPQ_DIR = 'C:/Program Files/PostgreSQL/17/bin'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
& $pythonPruebas -B scripts/test_infraestructura_aislada.py
# Solo si las 24 barreras pasan y existe autorización para la ronda PostgreSQL:
& $pythonPruebas -X utf8 -I -B scripts/pruebas_postgresql_aisladas.py --etiqueta biblioteca.test_funcional --failfast --verbosity 2
```

El ejecutor existente crea un directorio temporal nuevo fuera del repositorio y respaldos,
sanea el entorno, no carga .env, comprueba manifiesto/PID/directorio/host/puerto y proceso
hijo y ejecuta solo la etiqueta indicada. Tras éxito comprueba modelos/migraciones.
La detención exige revalidar la identidad y conserva evidencias. No se accede a zona_bloque.

## Archivos del incremento

1. backend/biblioteca/modelos_funcionales.py
2. backend/biblioteca/models.py
3. backend/biblioteca/servicios_funcionales.py
4. backend/biblioteca/migrations/0004_catalogo_funcional_b2_2.py
5. backend/biblioteca/migrations/0005_guardias_catalogo_funcional_b2_2.py
6. backend/biblioteca/test_funcional.py
7. scripts/verificar_catalogo_funcional_b2_2_estatico.py
8. docs/DISENO_CATALOGO_FUNCIONAL_F3_6_B2_2.md

## Decisiones pendientes

Autoridad y procedimiento de aprobación funcional; vocabulario y unidades institucionales;
umbrales y evidencia admisible; resolución de interpretaciones contradictorias; evaluación
profesional de adaptaciones; efectos de retiros sobre usos anteriores. Ninguna recomendación
técnica ni registro documental sustituye estas decisiones. Las aprobaciones permanecen cerradas.
