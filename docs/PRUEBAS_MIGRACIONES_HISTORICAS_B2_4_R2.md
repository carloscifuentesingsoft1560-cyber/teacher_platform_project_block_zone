# F3.6-B2.4-R2-A — Contratos y barreras simuladas

Base: `interfaz-sesiones-react`, `e83510a9bd4566bde4eac08be972afd7113eaa5b`.
Alcance: infraestructura de validación sin conexiones. No implementa R2-B.

## Límites de ejecución

No se importa Django, settings, dotenv ni controladores PostgreSQL. No hay funciones de
creación/borrado de bases, ejecución SQL, migración, arranque/detención o lanzamiento de
procesos. La CLI de casos rechaza siempre la invocación independiente, incluso con un
nombre de escenario válido. No se amplió el contrato del runner existente.

Las pruebas usan un objeto de proceso ficticio y un árbol temporal nuevo por prueba.
No modifican postmaster.pid, manifiestos o evidencias de ejecuciones anteriores.
Las evidencias ficticias pertenecen a esas fixtures y se eliminan con su TemporaryDirectory;
no son evidencias de migraciones reales. Los resultados quedan en la salida de la herramienta.

## Registro cerrado de ocho clases

| ID | Clase | Recorrido ascendente propuesto |
|---|---|---|
| nucleo | MigracionNucleo | cuentas 0004 → hojas publicadas |
| documental | MigracionDocumentalPreservaDatos | deportistas 0001 + inscripciones 0001 → deportistas 0002 + inscripciones 0001 |
| facultades | MigracionFacultadesPreservaDatos | deportistas 0002 + inscripciones 0001 → deportistas 0003 + inscripciones 0001 |
| etapa3 | MigracionEtapa3 | estado sin recursos/currículo/biblioteca → hojas publicadas |
| seguridad_ascensos | SeguridadMigracionB1 | inscripciones 0001 → 0002 |
| api_anterior | ApiEsquemaAnterior | inscripciones 0003 → 0005 |
| movimientos | MigracionMovimientosB3B2 | inscripciones 0003 → 0005 |
| planes | MigracionPlanesExistentes | sesiones 0001 → 0007 |

El registro incluye archivo y clase exactos. Las descripciones anteriores no son objetivos
ejecutables ni sustituyen sus dependencias completas. Seguridad de ascensos y movimientos
conservan una marca explícita de cobertura de reversión pendiente. No se ejecuta ni se declara
satisfecha una reversión; no se crean reversas ficticias ni se alteran migraciones publicadas.

## Contexto del padre y propiedad

RegistroEjecucion recibe del padre el entorno saneado, repositorio, objeto de proceso
ya creado y nombre de la base principal Django. Reutiliza validar_entorno y sus controles
de raíz temporal, identidad, postmaster.pid, host, puerto, rutas, archivos libpq y clave
ficticia. Añade lista cerrada de variables, correspondencia con el repositorio del módulo,
PID independiente del objeto y poll, huella del manifiesto original, rechazo de redirecciones
y comprobación repetida antes de reservar, consumir o registrar evidencia.

Cada registro crea un UUID de ejecución y secreto HMAC aleatorios, exclusivamente en memoria.
Solo genera nombres de reserva propios, separados de la base principal y de postgres/templates.
La reserva se rechaza si su nombre figura como preexistente o ya reservado. El prefijo no
demuestra propiedad: esta depende del registro emisor, contexto, nonce, payload exacto y firma.
Otro registro, aunque utilice el mismo clúster simulado, no puede consumir el manifiesto.
No se recuperan registros después de reiniciar: los manifiestos anteriores quedan inutilizables.

**Límite importante:** no se consulta un catálogo real de bases ni un servidor. El inventario
de bases existentes y el grafo/historial son entradas del futuro padre confiable. R2-A prueba
rechazos sobre entradas simuladas; no acredita propiedad de una base física ni la identidad
actual de un servidor mediante SQL. El objeto de proceso debe proceder del runner; este
módulo no puede demostrar por sí solo quién lo creó. No es una frontera contra un usuario
local malicioso que pueda sustituir código, objetos y archivos del ejecutor.

## Manifiestos y comunicación

Payload cerrado: versión, escenario, ejecución, nonce, base generada, base principal, PID,
host, puerto, clúster, SHA-256 de identidad, SHA-256 del contrato de plan y modo
`validacion_simulada`; firma HMAC-SHA256 exterior. El secreto no se serializa ni registra.
Se rechazan cambios incluso en un único campo, firma incorrecta y consumo repetido.
El consumo se serializa con RLock y marca el nonce antes de escribir evidencia; un fallo
de escritura no permite reutilizarlo. No existe un estado de migración satisfactoria.

El mensaje JSON acepta solo versión 1, operación `validar_plan_simulado`, manifiesto,
historial y pasos. Rechaza campos adicionales, claves duplicadas, JSON no finito y mensajes
excesivos. No hay host/base/DSN/settings elegibles por CLI ni operaciones fake, alteración
de triggers o edición de django_migrations. Es el contrato del receptor del padre para
validación; el transporte entre procesos y la ejecución histórica siguen deshabilitados.

## Contrato de planes

ContratoPlan congela un grafo y dos estados declarados por el padre. Rechaza nodos repetidos,
dependencias ausentes/circulares y estados sin cierre de dependencias. El estado final debe
contener íntegro el anterior: no puede ocultarse una reversión detrás de un objetivo superior.
El historial observado debe coincidir exactamente con el esperado, sin extras ni duplicados.
Cada paso requiere exclusivamente nodo y atras=False; no admite opciones fake/SQL. Se rechazan
dependencias fuera de orden, pasos repetidos, nodos ajenos y destinos incompletos.

R2-B tendrá que obtener el grafo auténtico con MigrationLoader, fijarlo al HEAD y contrastar
el historial real antes de DDL. Estos controles sobre datos no equivalen a haber validado
un plan de Django contra una base real. Las hojas publicadas aún no se resuelven automáticamente.

## Evidencia y fallos simulados

Solo se crean archivos JSON nuevos con modo exclusivo en un directorio nuevo del registro,
bajo la raíz temporal validada. Se comprueban ruta/identidad del directorio, y se rechaza
sobrescritura o redirección hacia recursos ajenos. Cada evento incluye simulacion=true,
ejecución y etapa. Solo admite reserva, consumo y fallo simulado.

Los fallos de creación, ejecución y timeout son objetos de excepción ficticios: nunca se
invoca una función de infraestructura. Se registra su tipo, no credenciales ni contenido
sensible; se propaga el mismo objeto original. Si falla también la evidencia, se añade una
nota y se conserva el diagnóstico original. No hay procedimientos de limpieza de recursos ajenos.

## Verificación R2-A

La versión inicial preparó 39 pruebas unittest, con socket.connect, create_connection,
Popen y subprocess.run bloqueados durante cada caso. Sus importaciones iniciales del
proyecto precedían a esos bloqueos; esa limitación se corrige en la revisión siguiente.
El examen AST comprueba que el módulo y receptor no importan capacidades de red/procesos/BD.
Resultados históricos de la versión inicial de R2-A: sintaxis de los tres archivos Python correcta, sin importar el proyecto;
39 pruebas simuladas descubiertas y ejecutadas una vez, 39 aprobadas, cero fallidas, cero
errores y cero omitidas, en 1.862 segundos. Código de salida 0. Incluyen el examen AST y
la comprobación de ausencia de Django/dotenv/psycopg en los módulos cargados. No se ejecutaron
las pruebas históricas ni PostgreSQL. No hay resultados de migraciones reales que atribuir.
La salida completa de la herramienta conserva el listado de los 39 casos. Las carpetas
de fixture nuevas se retiraron por TemporaryDirectory; no se tocaron evidencias preexistentes.

Comando previsto (no inicia PostgreSQL):

```powershell
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B scripts/test_migraciones_historicas_aisladas.py
```

## Corrección de manifiestos e importaciones

La comparación de diccionarios de Python equiparaba enteros con booleanos o decimales
equivalentes. Además, se comparaba la firma recibida con la almacenada sin recalcular
el HMAC sobre el payload recibido. Ahora se exige el conjunto exacto de campos y tipos
concretos: version/pid/puerto son int, los demás campos son str. bool, float y null no
sustituyen esos tipos. Se recalcula HMAC-SHA256 sobre el JSON canónico recibido, se
compara en tiempo constante con la firma recibida y la emitida, y se comprueba también
la representación canónica original. Se mantienen emisor, propiedad y nonce de un uso.

Antes se importaban configuracion.migraciones_historicas_aisladas,
configuracion.aislamiento_pruebas, pruebas_postgresql_aisladas y
casos_migraciones_historicas antes de setUp. Ahora una barrera común cubre sus primeras
importaciones sin caché y cada caso. Solo la stdlib necesaria para preparar la barrera
se importa antes. La inspección de las dependencias locales mostró definiciones de
funciones operativas en el runner, sin invocación al importarlo; solo se usa su función
pura entorno_aislado. No se modifica ni se llama al ejecutor operativo.

La barrera bloquea conexiones, envío de red, escucha/resolución y los lanzadores
habituales de subprocess/os. Rechaza Django, dotenv, psycopg y psycopg2 tanto mediante
__import__ como mediante el buscador de importlib. Se rechaza un proceso de pruebas
con módulos operativos o módulos del proyecto previamente cargados. Un loader en
memoria comprueba intentos de red y procesos durante una importación, sin ejecutables
ni módulos temporales en disco. Se conservan las 39 pruebas y se añaden nueve casos
para tipos, esquema, HMAC, propiedad, importaciones y replay tras fallo de evidencia.

Resultado de la única ronda posterior a esta corrección: 48 pruebas descubiertas y
ejecutadas, 48 aprobadas, cero fallidas, cero errores y cero omitidas, en 3.160 segundos.
Código de salida 0. Se utilizó el comando anterior con -X utf8 -B; no se repitió la ronda.
Las primeras importaciones del proyecto terminaron bajo barreras y sin módulos
operativos cargados. Pasaron los intentos ficticios de efectos secundarios durante
importación y los rechazos por __import__/importlib para los cuatro módulos prohibidos.
No se inició PostgreSQL, no se crearon bases ni se ejecutaron migraciones.

Límites: estas barreras son instrumentación de pruebas sobre las rutas Python
indicadas, no un sandbox del sistema operativo contra código malicioso o llamadas
nativas arbitrarias. No verifican un servidor PostgreSQL real, catálogo SQL, grafo
Django ni aislamiento físico. Los requisitos de R2-B siguientes siguen pendientes.

## Requisitos para R2-B

Antes de crear una base: autorización nueva, propiedad registrada e inventario SQL real
del clúster previamente identificado; nombre generado inexistente; verificación SQL de
host/puerto/data_directory/current_database; grafo/historial reales y plan sin reversas.
El transporte hijo, permisos de creación y cierre de sus conexiones necesitan implementación
y barreras adicionales. No se usará postgres como base de trabajo, ni DROP FORCE, fake,
desactivación de triggers o alteración del historial. El runner seguirá siendo el único
propietario de PostgreSQL y de su detención protegida.

Únicamente cuatro archivos nuevos: módulo de contratos, receptor cerrado, pruebas simuladas
y este documento. No cambian los ocho archivos históricos, runner, settings ni incrementos
publicados. Sin autorizaciones operativas, realizada, commit/push o avance a R2-B.
