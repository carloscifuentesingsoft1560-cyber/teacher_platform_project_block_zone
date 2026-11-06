# F3.6-B2.4-R2-B2-A — Inventario y comparador documental sin Django

Base: `interfaz-sesiones-react`, `dc3ba22b88985ff454d7c2af1d6a2cd0551f70d5`.
Antecedentes históricos, no repetidos: R1 110/110, R2-A 48/48, R2-B1 64/64.

## Alcance cerrado

Solo se crean el comparador preflight_grafo_documental.py, las barreras
barreras_preflight_grafo.py, contrato_grafo_documental.json, las dos suites nuevas
y este documento. No se modifican archivos existentes. No se importa Django real,
no se ejecuta MigrationLoader ni se crean bases, conexiones, SQL o migraciones.
Las entradas independientes de ambos módulos rechazan su invocación.

El comparador es puro y recibe estructuras de datos. No lee el contrato del disco
ni obtiene huellas del servidor o del sistema de archivos. Las suites leen el JSON
estático y usan observaciones ficticias. Su resultado declara simulacion=true,
django_ejecutado=false, autoriza_ddl=false e historial_bd_verificado=false.

## Origen independiente del inventario

Se inspeccionaron los archivos fuente publicados y los paquetes externos del
entorno contiguo documentado. Un procedimiento puntual de lectura de AST, sin
importar el proyecto o paquetes Django, extrajo las declaraciones dependencies
de cada clase Migration. No utilizó ni importó el comparador implementado aquí.
El procedimiento no queda como regenerador automático: ninguna función de este
incremento actualiza el contrato cuando aparece una divergencia.

AUTH_USER_MODEL se leyó estáticamente de settings.py: cuentas.Usuario. Sus
dependencias intercambiables se resolvieron a cuentas/0001_initial. Las referencias
contenttypes/__first__ se resolvieron a contenttypes/0001_initial. Las demás
dependencias fueron tuplas explícitas. No se encontraron replaces o run_before
no vacíos. Cualquier expresión no acreditable habría detenido la construcción.
pendientes_relaciones queda vacío: el cierre de las relaciones del inventario es
estático, no una certificación del comportamiento de importación.

Los conjuntos anterior/posterior se seleccionaron de las fuentes inspeccionadas;
el conjunto completo es el inventario de archivos, y las hojas se enumeraron con
sus nombres publicados. No provienen de la salida del comparador. Las suites que
copian esa referencia son fixtures simuladas, no un contraste independiente con
MigrationLoader. La comprobación auténtica sigue pendiente de R2-B2-B.

Resultado de la inspección: 42 migraciones locales y 18 de Django, 60 nodos,
110 aristas resueltas, 19 relaciones intercambiables y 13 hojas por aplicación.
Los cierres estáticos son 19, 20 y 60. Las cifras fueron resultado de inspección,
no condiciones impuestas al procedimiento. Ahora son expectativas revisables de
esta referencia de fuentes; si la futura carga difiere se detiene, no se adapta.

## Dependencias, hojas y destinos

El anterior incluye las doce migraciones auth, las dos contenttypes, cuentas/0001,
organizacion/0001 y 0002, deportistas/0001 e inscripciones/0001. Cuentas/0001 depende
de auth/0012; auth/0006 y 0011 incorporan contenttypes/0002. Inscripciones/0001 exige
deportistas/0001 y organizacion/0002, además del usuario intercambiable.
El posterior añade exclusivamente deportistas/0002_identificacion_documental.

El JSON guarda nombres completos, declaraciones originales y resolución de cada
dependencia. Sus destinos y cierres son conjuntos exactos; anterior es subconjunto
del posterior y este del completo. El completo usa estas hojas:

| Aplicación | Hoja |
|---|---|
| auditoria | 0001_initial |
| biblioteca | 0005_guardias_catalogo_funcional_b2_2 |
| cuentas | 0011_guardias_mandatos_acreditaciones_b2_1 |
| curriculo | 0003_mallaversion_clave_derivacion |
| deportistas | 0005_guardias_expedientes_funcionales_b2_3 |
| inscripciones | 0005_facultades_multirrol |
| organizacion | 0002_catalogos_iniciales |
| recursos | 0003_identidades_estables |
| sesiones | 0007_seguimiento_inmutable |
| auth | 0012_alter_user_first_name_max_length |
| contenttypes | 0002_remove_content_type_name |
| admin | 0003_logentry_add_action_flag_choices |
| sessions | 0001_initial |

Una hoja carece de hijos en su propia app, aunque otras apps dependan de ella.
La estructura inter-app de biblioteca/curriculo y sus dependencias posteriores se
registra en las 110 aristas; no se reduce a una sucesión lineal por numeración.

## Huellas y procedencia

El JSON registra 4636 fuentes/recursos con SHA-256: migraciones y módulos locales
pertinentes (apps, modelos y auxiliares, señales, admin e inicializadores), settings.py
solo como fuente de perfil, requirements.txt y los árboles de paquetes externos
con sus metadatos. No incluye .env, credenciales o datos de aplicación. Se excluyeron
cachés .pyc/.pyo. También registra versión, cache_tag y huella del ejecutable Python.

Paquetes leídos, nunca importados por este incremento:

| Paquete | Versión |
|---|---|
| Django | 5.2.18 |
| djangorestframework | 3.18.3 |
| asgiref | 3.13.0 |
| sqlparse | 0.6.0 |
| tzdata | 2026.5 |

Huella SHA-256 de la representación JSON canónica del contrato:
`c207ab34193144abeabacd64aa1f570659625b8ef35bba0cfbd37e4d69b10659`.
La entrada comparar_documental la fija en el código y no acepta reemplazarla desde
la observación. La función genérica recibe una raíz de confianza explícita del
revisor; no debe obtenerla de un mensaje no confiable. Cambiar el contrato y su pin
requiere revisión nueva. La huella canónica no es la huella de los bytes indentados.

No se afirma que las 4636 huellas prueben una ejecución: las observaciones de las
suites son datos ficticios. El inventario de importaciones transitivas efectivamente
utilizado, recursos nativos, intérprete completo y configuración sin conexiones
deberán contrastarse cuando se autorice B2-B. El código/huella de los archivos nuevos
se fijará en su auditoría/publicación, sin autorreferencias dentro del JSON.

## Comparador

Valida esquemas y tipos concretos, duplicados, referencias desconocidas, ciclos
mediante ordenación topológica, conflictos y hojas por app. Contrasta conjuntos
exactos de nodos, aristas, relaciones especiales, fuentes y cierres. Rechaza
relaciones replaces/run_before inesperadas en lugar de intentar resolverlas.
Recorre padres para calcular cierres y exige la diferencia documental exacta.
Las declaraciones fuente deben cubrir precisamente las aristas resueltas.
Rechaza rutas relativas con retrocesos, duplicados Windows por mayúsculas y huellas
incompatibles. No interpreta operaciones RunPython/RunSQL, no aplica migraciones
ni verifica historial real. El perfil solo describe un futuro default dummy,
sin routers, sustituciones de migraciones ni configuraciones operativas.

## Barreras simuladas

Un bootstrap de pruebas stdlib instala bloqueos antes incluso de importar el
módulo de barreras. La primera importación del comparador ocurre bajo la guardia
y verifica ruta y bytes de su fuente. El cargador compila exactamente los bytes
aprobados, sin consultar caché .pyc; la fuente se revalida al entrar y al salir.

Las barreras bloquean sockets/resolución y lanzadores habituales subprocess/os,
lectura de .env incluso con mayúsculas, settings operativos y módulos no aprobados.
Se rechazan también solicitudes directas de módulos nativos de sockets/SSL/procesos.
Las importaciones normales e importlib se controlan, incluyendo módulos en caché.
Se verifica el origen de stdlib y se rechazan dependencias externas sin aprobación.
Fuentes aprobadas no pueden redirigirse mediante symlink o junction. Un entorno
con Django, drivers, settings precargados, perfil configurado o variables de
conexión/configuración heredadas se rechaza. Una guardia no se reutiliza ni anida.

Django real y sus drivers están prohibidos siempre en B2-A. No se ofrece una opción
para habilitarlos. Las superficies conexion/cursor/orm/sql/migrar/revertir/recorder
son objetos ficticios instrumentados: no son parches ya instalados en Django real.
Los módulos ficticios se ejecutan en memoria, bajo huella aprobada, para simular
efectos durante importación; no son archivos ni procesos hijos reales.

Cada intento prohibido deja evidencia antes de lanzar la excepción. Aunque el
módulo capture internamente la excepción, la salida de la guardia se rechaza.
Si ya hay un error de importación/ejecución se conserva el mismo objeto y se añade
una nota ante incidencias secundarias. Los eventos solo contienen versión,
simulacion, ordinal y categoría; no el contenido de excepciones ni secretos.
Se restauran los parches propios al salir o fallar la entrada.

## Pruebas y resultado

Preparadas 57 pruebas nuevas: 31 del comparador y 26 de barreras. Incluyen mismos
recuentos con arista/nodo sustituido, nodos extra/faltantes, dependencia desconocida,
ciclo, conflicto, hojas/cierres alterados, relaciones especiales inesperadas,
huellas/rutas/perfil/tipos, ausencia de autoactualización del contrato, contaminación,
lectura .env, red/procesos durante importación, intentos ocultados internamente,
instrumentación ficticia ORM/SQL/migraciones/recorder, fallos de importación,
evidencias y conservación de error original. No se ejecutan suites anteriores.

Revisión estática previa satisfactoria: AST/compile de los cuatro archivos Python
sin importarlos, imports y alcance inspeccionados, huella canónica del JSON correcta,
fuentes sin duplicados y 449 archivos preexistentes conservados. Se identificaron
exactamente los seis archivos nuevos autorizados antes de la ejecución.

Única ronda ejecutada: 57 pruebas descubiertas y ejecutadas, 57 aprobadas,
cero fallidas, cero errores y cero omitidas, en 4.249 segundos. Código de salida 0.
El listado completo queda en la salida de la herramienta. No se repitió la ronda.
No se ejecutaron pruebas generales, R1, R2-A o R2-B1. No se cargó Django real ni
MigrationLoader. Las llamadas negativas fueron interceptadas por las barreras;
no abrieron conexiones, no lanzaron procesos operativos ni leyeron .env.

Comando utilizado (sin Django real):

```powershell
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -X utf8 -B -m unittest -v -f scripts.test_preflight_grafo_documental scripts.test_barreras_preflight_grafo
```

Si falla un caso, detenerse sin repetir ni introducir arreglos posteriores a esa
ronda. No hay resultado de MigrationLoader ni de PostgreSQL que atribuir a B2-A.

## Límites y autorización de R2-B2-B

Estas barreras Python no constituyen un sandbox de SO, no son seguras ante código
malicioso nativo, sustitución de objetos o concurrencia no controlada. Los parches
son globales: se requiere un intérprete limpio y una única guardia activa. La
política de fuentes y el snapshot de entorno son entradas confiables del llamador;
no acreditan por sí solos el entorno real de un futuro proceso.

B2-B necesitará autorización explícita para importar Django auténtico, un perfil
en memoria sin settings existentes, ampliación revisada de la política de imports
y enganche real de los bloqueos Django antes de cargar apps/migraciones. Deberá
medir cero intentos aunque se oculten excepciones, verificar procedencia, fuentes,
paquetes e intérprete, y contrastar nodos/aristas/hojas/cierres con este contrato.
El HEAD base acredita las fuentes publicadas; el futuro commit del preflight y
sus archivos nuevos deberán fijarse por separado, sin exigir una autorreferencia.
Toda divergencia detiene; no se cambia la expectativa automáticamente.

R2-B2-A permanece pendiente de auditoría y autorización de publicación. No hay
staging, commit ni push, y no se avanza a B2-B ni B3.
