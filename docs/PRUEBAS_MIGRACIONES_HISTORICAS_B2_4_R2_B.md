# F3.6-B2.4-R2-B1 — Contratos documentales exclusivamente simulados

Base: rama `interfaz-sesiones-react`, HEAD
`ef302a467be04c281ff058bed6b3b6ef959623b4`.
Antecedentes: R1 110/110 y R2-A 48/48, resultados históricos, no repetidos aquí.

## Alcance y archivos

Este incremento crea únicamente:

- `scripts/postgresql_historico_controlado.py`
- `scripts/hijo_migracion_documental.py`
- `scripts/test_postgresql_historico_controlado.py`
- `scripts/test_hijo_migracion_documental.py`
- Este documento.

Los módulos de implementación no tienen E/S de archivos, sockets, SQL, drivers,
Django, conexiones, procesos ni funciones para crear/eliminar bases o migrar.
Las evidencias y el canal son objetos en memoria. No se crean carpetas de fixture.
Ambas entradas independientes fallan, incluso si se ejecuta directamente el archivo.
No se modifica el ejecutor, R2-A, settings, modelos, migraciones ni pruebas históricas.

## Identidad y propiedad simuladas

Solo se admite el escenario `documental`. IdentidadSimulada congela PID, loopback,
puerto, raíz Windows absoluta normalizada, directorio cluster y sello de identidad.
La raíz debe tener nombre zdb_pg_; se rechazan rutas relativas, componentes de
retroceso y directorios que no sean cluster bajo esa raíz. No se consultan rutas
reales ni se detectan junctions, permisos, procesos vivos o servidores.

El padre recibe esa identidad ficticia confiable y fija su representación canónica.
Genera ejecución, canal, base, usuario y secreto aleatorios. El inventario de bases
es una lista ficticia: una colisión se rechaza sin reutilización. Base y usuario
no son seleccionables mediante solicitud. El prefijo no prueba propiedad: esta
depende del registro emisor, objeto exacto de contexto, marca privada, contexto
canónico, canal, firma, secuencia y nonce. Otro registro no puede usar ese contexto.

No existe prueba criptográfica de identidad PostgreSQL en este incremento. Los
hashes de código y sello son declaraciones fijadas; B1 no lee archivos ni calcula
la identidad de un proceso o servidor real. La comparación con observaciones
simuladas detecta cambios de PID, puerto, directorio, código, contrato y destinos.

## Mensajes y secuencia

Protocolo `zdb_documental_r2b1`, versión 1, modo fijo `simulacion`. No acepta
manifiestos de R2-A ni transforma sus permisos de validación en permisos DDL.
La única secuencia es:

1. identidad_declarada
2. grafo_declarado
3. reserva_simulada
4. configuracion_declarada
5. plan_declarado
6. resultado_simulado
7. cierre_simulado

Cada etapa requiere solicitud del padre, recepción única por el hijo y confirmación
del padre. Solo hay una solicitud pendiente. Cada payload incluye versión,
protocolo, modo, escenario, ejecución, canal, emisor, secuencia, nonce, etapa y
contexto. La respuesta añade huella de solicitud y resultado fijo de validación
simulada. El contexto incluye identidad, base/usuario generados y hashes de
código/contrato. No hay DSN, contraseña ni clave en las tramas.

El esquema exige campos y tipos concretos. JSON canónico diferencia int, bool,
float, str y null también en estructuras anidadas. Se recalcula HMAC-SHA256
sobre el payload recibido y se compara en tiempo constante; además se contrasta
con la solicitud pendiente original. La firma no sustituye propiedad y secuencia.
El secreto queda en el registro del padre en memoria; no se serializa ni registra.

Una trama es bytes UTF-8/JSON y un delimitador final LF, con máximo 65536 bytes
incluyendo el delimitador. Se rechazan múltiples tramas, claves duplicadas,
tipos arbitrarios, JSON no finito, EOF prematuro y mensajes incompletos.

El reloj se inyecta como enteros de milisegundos ficticios, monotónicos, con un
plazo total máximo de 30000 ms. El límite es exclusivo: al alcanzarlo se rechaza.
Los intercambios no renuevan ese plazo. No hay espera, reloj real ni timer de SO.
El nonce se invalida antes de registrar una confirmación; fallos terminales
invalidan la solicitud pendiente y cierran el contexto propio. No hay reintentos.

## Canal y fallos

ContextoHijoSimulado representa una capacidad privada compartida en el mismo
intérprete. No es un pipe ni un canal entre procesos reales. El receptor delega
verificación y firma al registro propietario, cuyo secreto no necesita copiar.
No se reconstruye autoridad desde un JSON, archivo o argumento CLI.

La futura transmisión deberá usar handles/pipes privados heredados y protocolo
acotado, sin secretos en argumentos ni selección libre de servidor. El emisor
real, aislamiento de handles y recepción incremental requieren otro incremento;
la simulación actual solo admite una trama completa. No implementa buffering real.

Las evidencias contienen versión, simulacion=true, ejecución, etapa, secuencia,
estado y nombre del tipo de error. No incluyen claves, mensajes de excepción ni
datos de fixtures. Se devuelven copias para evitar mutación desde el consumidor.
El primer error se conserva y propaga como el mismo objeto. Si también falla la
evidencia simulada se añade una nota sin sustituirlo. El cierre solo invalida el
contexto del registro propio; no toca otros registros, archivos o procesos.
Un fallo durante la confirmación de cierre produce estado fallida, nunca éxito.
Una vez completado el cierre, las solicitudes posteriores se rechazan sin cambiar
estado, evidencias, nonces, confirmaciones, reloj ni información del cierre; no se
registran como un fallo de la ejecución finalizada.

## Plan y configuración Django futura

El plan tiene historial, pasos y destino declarados, con máximo 256 filas por
sección. Rechaza duplicados, nodos arbitrarios, destinos incompletos, pasos
repetidos, opciones extra, atras distinto de False y retrocesos indirectos.
Su huella se fija al crear el registro y se revalida durante los intercambios.
No acredita dependencias ni orden topológico de Django. grafo_declarado es una
etapa de protocolo, no un grafo auténtico validado.

El hijo solo describe un futuro default dirigido a la base y usuario generados,
sin otros aliases, dotenv, conexiones iniciadas o Django inicializado. Rechaza
overrides y tipos equivalentes; grafo_real_validado permanece False. El descriptor
no es un diccionario de settings operativo y no inicializa conexiones.

R2-B2 deberá obtener el grafo con Django real, sin conexiones, verificar procedencia
y huellas de paquetes/código y contrastar cierres y hojas con el contrato. No debe
ejecutar la clase histórica original, que puede retroceder desde un esquema completo.
Los recuentos 19/20/60 de la auditoría anterior siguen siendo inferencias estáticas
pendientes de preflight; B1 no los certifica. La configuración real de default
antes de Django y los adaptadores de conexión tampoco se implementan aquí.

## Barreras de pruebas y comprobación estática

Las barreras se instalan antes de las primeras importaciones de los dos módulos
y durante cada caso. Se rechazan Django, dotenv y los drivers psycopg, psycopg2,
asyncpg y pg8000 mediante __import__ y el buscador de importlib; se comprueba que
no estén previamente cargados. Se bloquean red/resolución, lanzadores habituales
de subprocess/os y lectura de .env. Un loader ficticio en memoria intenta efectos
secundarios durante una importación. No se escribe código de ese loader en disco.

El examen AST limita las importaciones de implementación a stdlib y al módulo puro
hermano; rechaza llamadas de archivos, evaluación dinámica, red, procesos, SQL y
migraciones. Antes de ejecutar se revisarán sintaxis, importaciones, conteo de casos,
estado de Git e integridad de los diez archivos preexistentes. El análisis de
sintaxis no importa ni ejecuta los módulos de implementación.

## Resultado histórico de la implementación inicial

Comprobación estática previa satisfactoria: sintaxis de los cuatro archivos Python
mediante AST/compile, sin importarlos ni ejecutarlos; imports/capacidades revisados
y 54 casos definidos (30 del coordinador y 24 del receptor). Git no mostró cambios
versionados o preparados ajenos. Los cinco archivos nuevos son los autorizados.

Única ronda ejecutada: 54 pruebas descubiertas y ejecutadas, 54 aprobadas,
cero fallidas, cero errores y cero omitidas, en 0.242 segundos. Código de salida 0.
La salida de la herramienta conserva el listado completo de los 54 casos.
No se repitió la ronda, no se ejecutaron suites generales ni las de R2-A/R1.
Se aprobaron los intentos ficticios de efectos secundarios durante importaciones,
las barreras de red/procesos/.env, EOF, truncamiento, timeouts, tipos estrictos,
HMAC, propiedad, replay, planes inversos y fallos de evidencia/cierre.

No hay resultado de PostgreSQL real ni migraciones que atribuir a R2-B1.

Comando utilizado, sin pruebas generales ni R2-A:

```powershell
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B -m unittest -v -f scripts.test_postgresql_historico_controlado scripts.test_hijo_migracion_documental
```

Si falla un caso se detiene sin repetir la ronda ni ampliar alcance.

## Corrección controlada de las observaciones A y B

A: parse_constant rechazaba NaN e Infinity, pero el parse_float predeterminado
podía convertir exponentes como 1e400 en infinito sin pasar por parse_constant.
leer_trama incorpora ahora parse_float con conversión float y comprobación
math.isfinite. Se rechazan desbordamientos positivos y negativos también dentro
de objetos y listas. Los números finitos mantienen la conversión y tipos que
json.loads utilizaba anteriormente; no se cambia parse_int ni la representación
canónica/HMAC. No se sustituyen números no finitos por null, cadenas u otros valores.

B: _comprobar rechazaba correctamente el cierre, pero emitir/confirmar capturaban
ese rechazo y fallar cambiaba el resultado a fallida y añadía evidencia.
Se añade una barrera de cierre completado bajo el cerrojo, antes de esos manejadores
de fallo. _comprobar y fallar comparten esa protección. También protege la ruta de
recepción que comunica un rechazo mediante fallar. Una ejecución cerrada continúa
cerrada_simulada; el rechazo tardío no se guarda como error original ni reabre nada.
Los errores anteriores a completar el cierre siguen invalidando el contexto y
conservando la excepción original, incluido un fallo de evidencia durante el cierre.

Se conservan los 54 casos anteriores y se añaden diez métodos: cinco comprueban
emisión, confirmación, fallar, ausencia de escritura y comprobación directa tras
el cierre; cinco cubren constantes, desbordamientos, compatibilidad finita, error
de recepción antes de cerrar y rechazo de recepción después de cerrar.
Las comprobaciones de cierre comparan instantáneas de evidencias, nonces usados y
vistos, secuencia, solicitud pendiente, reloj, contexto y estado del canal.

Comprobaciones estáticas previas satisfactorias: sintaxis de los cuatro archivos
Python sin importarlos, imports/capacidades revisados y 64 casos definidos (35 del
coordinador y 29 del receptor). El único import nuevo de implementación es math,
de la biblioteca estándar, para comprobar finitud; no aporta capacidades operativas.

Resultado de la única ronda autorizada para esta corrección: 64 pruebas descubiertas
y ejecutadas, 64 aprobadas, cero fallidas, cero errores y cero omitidas, en 0.383
segundos. Código de salida 0. Se empleó el mismo comando anterior con -v -f y -B.
No se repitió la ronda. Los diez casos nuevos y los 54 anteriores pasaron, incluidos
los fallos durante el cierre que deben conservar estado fallida. Los rechazos
posteriores a un cierre completado conservaron estado, evidencias y nonces.
La ronda histórica 54/54 anterior no se presenta como una nueva ejecución ni como
evidencia de aislamiento PostgreSQL real.

Solo se modifican el coordinador, las dos suites y este documento. El receptor
hijo_migracion_documental.py permanece intacto. R2-B1 sigue pendiente de revisión
y autorización de publicación; sin staging, commit ni push.

## Límites y criterios de publicación futura

No es un sandbox frente a código Python malicioso con acceso a memoria, código
nativo o sustitución de objetos. No demuestra aislamiento PostgreSQL, autenticación
multiusuario, propiedad física, ausencia de carreras SQL o limpieza de servidores.
No existe transporte real, creación de bases, bootstrap Django ni ensayo histórico.

Antes de publicar: revisar exclusivamente los cinco archivos, confirmar sus hashes
y los de los diez preexistentes, ausencia de cambios versionados ajenos y secretos,
resultado satisfactorio de la única ronda, diff/check y autorización específica de
commit/push. R2-B2 y los incrementos B3/B4/B5 requieren autorizaciones separadas.
No se habilitan autorizaciones operativas ni el estado realizada de la aplicación.
