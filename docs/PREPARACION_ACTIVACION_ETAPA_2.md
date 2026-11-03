# Verificación de preparación para activar Etapa 2

Fecha: 2026-11-02. **Resultado: NO lista para activación operativa.** El ensayo histórico es satisfactorio, pero faltan comprobaciones del destino actual, respaldo reciente representativo y configuración de despliegue. Esta revisión no ejecuta migraciones, despliegues, cambios de permisos, escrituras operativas, commits ni push.

## 1. Evidencia revisada y comprobaciones de esta sesión

Se revisaron `ENSAYO_MIGRACION_ETAPA_2.md`, `PROCEDIMIENTO_ACTIVACION_RECUPERACION_ETAPA_2.md`, implementación 2A–2E, manifiestos, historial de preparación de 0004, ejecutores y paquete de integración. Se conserva la documentación anterior sin sobrescribirla; este informe actualiza las conclusiones sobre Git y precisa las condiciones del ensayo final.

| Condición | Evidencia y estado |
|---|---|
| Conservación de fuentes | 290 archivos originales y 293 fuentes aprobadas de integración: hashes coincidentes, cero diferencias |
| Ensayo histórico | Evidencia anterior: cuatro migraciones, 538 pruebas backend y 5 de aislamiento aprobadas; no repetidas en esta sesión |
| Clústeres anteriores | Los tres sin `postmaster.pid`; no se iniciaron servidores para esta revisión |
| Servicio PostgreSQL local | `Get-Service`: `postgresql-x64-17` en ejecución; no demuestra versión efectiva, destino ni autorización de datos |
| Inventario de servicios por CIM | Acceso denegado; sin escalación ni cambio de servicio. La consulta alternativa anterior fue solo lectura |
| Herramientas locales | `pg_dump --version`: 17.11; no acredita versión del servidor en ejecución |
| Copia reciente | No se encontró un respaldo operativo más reciente entre los `.dump` locales examinados; las copias del 2 de noviembre derivan del dump histórico, no son nuevas capturas operativas |
| Acceso al origen | No se abrió ninguna conexión PostgreSQL ni se leyeron filas reales en esta sesión. No se cargó `.env` ni se usaron sus credenciales |
| Protección de configuración original | `.env` tiene ACL heredada con varios principales. No se inspeccionaron sus valores ni se cambiaron permisos. Hace falta validar quiénes son los titulares y si su acceso es apropiado; la herencia por sí sola no demuestra una exposición |
| Privacidad del nuevo trabajo | Carpeta de evidencia con DACL restringida antes de descargar el objeto: usuario ejecutor, SYSTEM y Administrators; sin publicación |
| Git | Binario histórico recuperado y validado fuera de Git; repositorio sigue incompleto hasta integración autorizada del objeto |
| Paquete | ZIP validado por CRC, lista permitida y SHA256 de cada entrada; análisis estático sin secretos operativos identificados |
| Perfil operativo | Pendiente: rama actual bloquea settings normales y solo admite pruebas; no se retiró esa barrera |

Las verificaciones documentales, de archivos, ZIP y objetos Git no son nuevas pruebas funcionales de la aplicación. No se inicia Etapa 3 ni Climbing Vision AI.

## 2. ¿Puede obtenerse un respaldo reciente sin riesgo indebido?

**Viable técnicamente, pero todavía no demostrado para este destino. No se obtuvo en esta sesión.** `pg_dump` permite una captura lógica mediante lectura; aun así consume E/S, mantiene una instantánea y toma bloqueos de lectura. No se puede prometer impacto cero ni inferir permisos de datos a partir del acceso al sistema de archivos o al conector GitHub.

La autorización actual cubre la verificación de preparación. Se detiene el acceso real porque faltan pruebas previas de: identidad vigente del destino, responsable de datos, cuenta de lectura apropiada, alcance completo del respaldo y condiciones de aislamiento. No se crea una cuenta, no se modifica pg_hba/ACL de producción y no se reutiliza una credencial administrativa como atajo.

Antes de extraer datos, el responsable debe confirmar por canal protegido:

1. Host/puerto/base exactos, propietario institucional y finalidad de la copia; identidad del servidor contrastable con la configuración autorizada. No incluir secretos en este informe.
2. Cuenta existente apta para respaldo de solo lectura, sin superusuario ni capacidad de escritura/DDL; permisos suficientes sobre todas las tablas y secuencias requeridas. Revisar membresías heredadas, propiedad de objetos, funciones con privilegios y RLS, no únicamente `default_transaction_read_only`. Si exige crear o cambiar permisos, detener y solicitar autorización separada al responsable operativo.
3. Acceso autorizado a menores y datos sensibles, ubicación local restringida, personas con acceso, retención, espacio disponible y medidas del equipo para proteger las copias. DACL local no acredita cifrado de disco ni protección frente a administradores del equipo.
4. Carga y ventana de extracción aceptables, límites de bloqueo/duración, mecanismo para cancelar la lectura y monitorizar actividad. No detener el servicio ni usuarios para preparar el ensayo sin aprobación.

Preferencia: entrega de un respaldo reciente generado por el responsable mediante su procedimiento validado y acompañado de hash/inventario/configuración. Si se autoriza capturarlo aquí y supera estas comprobaciones, usar proceso exclusivo de lectura con destino explícito y credenciales efímeras protegidas; nunca el arranque Django operativo. Mantener metadatos, filas y logs fuera de Git.

Un respaldo pequeño puede ser representativo del estado real si producción tiene ese volumen. No agregar personas ficticias a producción para aumentar la muestra: las pruebas de volumen y de estados ausentes se construyen en una segunda base sintética aislada y se distinguen de la conservación del origen.

## 3. PostgreSQL: diferencias comprobadas y pendientes

| Característica | Origen histórico 31 de octubre | Ensayo Etapa 2 | Destino operativo actual |
|---|---|---|---|
| Versión | 17.11, manifiesto previo | Herramientas/clúster 17.11 | No consultada; servicio identificado como 17 |
| LC_COLLATE / LC_CTYPE | `Spanish_Colombia.1252` / `Spanish_Colombia.1252` | Locale `C`, initdb `--no-locale` | Pendiente |
| Extensiones | No hay CREATE EXTENSION en esquema exportado inspeccionado; no equivale a inventario completo de instaladas | No se incorporaron extensiones adicionales | Pendiente consultar `pg_extension` y versiones |
| Proveedor/versiones de collation | No consta evidencia suficiente | No se comprobó equivalencia | Pendiente, junto con versión del sistema/librerías |
| Formato/encoding/zonas horarias | Evidencia histórica parcial | UTF8; hashes de filas normalizados a UTC e ISO/YMD | Pendiente confirmar encoding, TimeZone y DateStyle |
| Roles/propiedad/ACL/RLS | Fuera del alcance del inventario histórico revisado | Restauración `--no-owner --no-privileges`, superusuario local aislado | Pendiente verificar con rol operativo de mínimos privilegios |

**Diferencia real:** el ensayo con locale C no certifica ordenación, equivalencia de índices ni restricciones textuales bajo Spanish_Colombia.1252. El ensayo final debe crear base y clúster con características verificadas del destino y comprobar índices/ordenación, sin cambiar collation operativa ni ejecutar REINDEX allí.

Consulta de metadatos propuesta, **no ejecutada**, únicamente después de validar acceso y destino:

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SHOW transaction_read_only;
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SHOW server_version;
SHOW server_encoding;
SHOW TimeZone;
SHOW DateStyle;
SELECT datcollate, datctype FROM pg_catalog.pg_database
 WHERE datname = current_database();
SELECT extname, extversion FROM pg_catalog.pg_extension ORDER BY extname;
SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
 FROM pg_catalog.pg_roles WHERE rolname = current_user;
ROLLBACK;
```

Complementar con proveedor/versiones de collation disponibles en la versión confirmada, membresías y privilegios efectivos. No declarar rol seguro solo porque esos cinco indicadores sean falsos. La inspección debe abortar ante destino inesperado o falta de permiso; nunca sustituir por credenciales de mayor alcance sin revisión.

## 4. Ensayo final propuesto y puntos de parada

**P0 — autorización y protección:** confirmar las condiciones del apartado 2 y una ubicación independiente con permisos restrictivos antes de copiar. Preferir VM o entorno sin ruta al servidor operativo para restauración/pruebas. Si se usa el mismo equipo, hace falta una barrera de conectividad verificable; puerto distinto y variables saneadas no constituyen por sí solos aislamiento de red completo. Cambiar firewall/VM requiere aprobación propia, no se realizó aquí.

**P1 — captura coherente:** con rol y destino previamente verificados, transacción READ ONLY/REPEATABLE READ, exportar una instantánea y mantenerla abierta mientras inventario y `pg_dump --snapshot` comparten esa captura. Formato custom, sin propietarios/privilegios al restaurar. Conexión explícita sin variables/libpq heredadas; secreto en archivo restringido o gestor seguro, nunca argumentos, documentos o logs públicos. Fijar límites de bloqueo y tiempo y abortar ante presión operativa. Verificar permisos/RLS para evitar omisiones; no habilitar opciones que acepten silenciosamente un respaldo parcial. Esta fase solo lee, sin migraciones ni cambios de negocio.

**P2 — verificar respaldo:** registrar procedencia, fecha, tamaño y SHA256, resultado de dump y catálogo, lectura completa y esquema. Inventario del mismo snapshot: todas las tablas, columnas, conteos, huellas, secuencias, migraciones, constraints, índices, funciones y triggers. Revisar objetos externos, extensiones y código ejecutable del dump antes de restaurar. Un hash sin procedencia o una comparación de momentos distintos no bastan. Detener si falla cualquier comprobación.

**P3 — separar origen del ensayo:** transferir solo el respaldo protegido y metadatos necesarios; no `.env`, passfiles ni secretos del origen. El entorno de ensayo no conserva credenciales operativas ni ruta permitida a producción. Evidenciar la política de red o su denegación sin probar una escritura real. Permitir salida de notificaciones/tareas únicamente a sumideros de prueba; no arrancar servicios externos. Clúster con SCRAM, secreto aleatorio, loopback, puerto exclusivo, PID/directorio/nonce verificados y rechazo de contraseña incorrecta.

**P4 — restauración equivalente:** replicar versión, encoding, locale/proveedor y extensiones verificadas; crear una base independiente desde template0 y restaurar sin sobrescribir otra base. Restauración íntegra, sin `--create` que pueda recuperar nombres del origen. Comparar esquema y huellas con snapshot, normalizando solo diferencias de representación explicadas. Probar el rol de aplicación de mínimos privilegios en la copia, además del rol de migración; el superusuario del ensayo anterior no acredita permisos de despliegue. Si no se puede garantizar protección, detener antes de restaurar datos reales.

**P5 — conservación y seudonimización:** para probar conservación exacta se necesita una copia íntegra restringida; no publicar sus filas. Después de verificarla, generar una segunda copia seudonimizada para pruebas funcionales cuando sea suficiente, manteniendo relaciones y particularidades necesarias. Retirar contactos, documentos, contenidos libres y credenciales/sesiones reutilizables de esa segunda copia mediante transformación revisada y solo local. La seudonimización puede alterar colisiones/ordenación: no sustituye la comparación exacta ni debe presentarse como tal. No existe todavía un transformador validado: prepararlo y revisarlo antes de usarlo, sin improvisar actualizaciones sobre datos reales.

**P6 — plan estricto:** inventariar punto actual de migraciones. A diferencia del ensayo histórico, no asumir que falta `inscripciones.0004`: no reaplicarla ni reconstruir una línea base ficticia. Si el estado no es el predecesor revisado de las cuatro migraciones, detener y reconciliar. Comprobar SHA256 de las fuentes históricas/nuevas, coherencia del grafo, coordinador único, roles válidos y ausencia de anomalías. Generar SQL de revisión solo contra la copia, medir tiempos/bloqueos con volumen representativo.

**P7 — aplicar únicamente en copia:** respaldo del punto previo; simular fallo y rollback global de las cuatro migraciones más post_migrate, comparar; luego aplicación completa y comprobación de cero pendientes. Backfill: una pertenencia y un evento de origen por usuario según las reglas aprobadas, sin fusiones ni nuevas acreditaciones automáticas. Validar metadatos faltantes por claves naturales, no asumir +4/+16. Comparar filas originales por PK y columnas previas, y todas las tablas de asignaciones de permisos sin altas imprevistas. Validar constraints, índices y triggers.

**P8 — seguridad, concurrencia y regresión:** roles combinados sin elevación, revocación con sesión/actor ya cargado, aislamiento de objetos y acudientes revocados, coordinador único con dos conexiones, propuesta docente/revisión pedagógica/formalización administrativa, rechazo SQL a formalización no autorizada, idempotencia y conflictos de versiones/cupos. Repetir suite backend con datos ficticios en otra base del clúster; frontend/HTTP/build con paquete final y smoke tests manuales por rol en copia. Nunca emplear deportistas reales para simular movimientos ni enviar comunicaciones.

**P9 — recuperación y cierre:** restaurar el respaldo previo en otra base restringida, cotejar filas/esquema/secuencias y arranque con versión anterior. Medir tiempo y registrar RTO/RPO acordados, sin inventarlos. Verificar copia original intacta tras pruebas, detener clústeres, conservar evidencia restringida y acordar retención. Sin aprobación específica, terminar aquí: ningún comando de este ensayo debe apuntar al origen.

El ejecutor anterior está fijado al dump y rutas históricos y usa `--no-locale`; **no sirve sin revisión para este ensayo final**. No se cambió su código ni se ejecutó de nuevo.

## 5. Recuperación del objeto histórico Git

Se encontró una solución de solo lectura mediante el conector GitHub: `fetch_file` con `encoding=base64`, ruta `Esquema de la idea`, fijada al commit `decda62bff95f782e124394fb221626f12990f6d`. El intento previo usaba una vía que rechazaba el binario; esa limitación no impide esta descarga.

- Bytes recuperados: **19002**. Contenedor ZIP, sin abrir ni publicar su contenido documental.
- SHA Git calculado sobre `blob <longitud>\0<bytes>`: **`9e0d3f820d05a550eb640111207f2487c883136a`**, coincide con objeto y árbol histórico.
- SHA256 del contenido: `5cb6633a364e4ac58741456c4337d47f6e1c27aad1532a90e475032c9692cfc3`.
- Conservado en evidencia privada `objeto_historico_recuperado.bin`; no se insertó en `.git`, no hubo checkout/reset, cambios de índice, commits ni fetch/pull/push.
- `git fsck --full` sigue devolviendo 2 por el blob ausente en la base de objetos local. Los objetos dangling no se borraron. **Recuperación de bytes resuelta; integración en repositorio pendiente.**

Siguiente intervención propuesta: trabajar en otra copia independiente del repositorio de integración, comprobar de nuevo ambos hashes, incorporar únicamente ese blob con `git hash-object -w --stdin` allí, ejecutar fsck completo y verificar referencias/árboles/índice. No copiarlo ciegamente a fuentes ni sustituir el historial. Revisar el documento en entorno privado antes de cualquier publicación; si contiene datos sensibles, detener publicación y decidir tratamiento del historial con el titular, sin reescribirlo automáticamente.

El conector informa que el repositorio remoto **ya es público**; esta revisión no cambió su visibilidad ni publicó contenido nuevo. Que un archivo figure en un historial público no elimina la necesidad de revisión de privacidad. La URL de push de integración permanece `NO_PUBLICAR_SIN_AUTORIZACION`.

## 6. Revisión del paquete y exclusiones

`fuentes_etapa2.zip`: **293 entradas**, CRC correcto, lista exacta del manifiesto aprobado y 293 SHA256 coincidentes. No contiene rutas `.env` operativas, dependencias, bases, respaldos, medios, documentos personales o directorios privados según la inspección de nombres y extensiones. Se contrastaron `.gitignore`, ZIP, índice y rutas nuevas de ambos parches; no se confunde ZIP fuente con `estado_original_privado.zip`, que contiene material privado y **nunca es publicable**.

| Artefacto | SHA256 comprobado |
|---|---|
| fuentes_etapa2.zip | `4967b52e440f47af22343398896ccbd0d4240faff287295fd2eb50f6db8c99de` |
| integracion_remota.patch | `befb79ddeca7719ee89e3aed184ebf7ac486fbda68531fea5d012486342c5090` |
| cambios_sobre_etapa1.patch | `22364386bf6d5a501ce86fa3e1578821e90001e1fc24ffb8dfff69afce2b4cd9` |

Se analizaron patrones de claves privadas, tokens GitHub, claves AWS, URI de base con contraseña, literales de secretos y correos. Las cuatro alertas del ZIP se revisaron: tres apariciones de correo ficticio `example.com` en tests y una clave declarada exclusivamente para pruebas en el ejecutor aislado; no son secretos operativos. Las alertas equivalentes del parche remoto corresponden a las mismas fuentes. El parche sobre Etapa 1 no produjo alertas de estas reglas. No se afirma ausencia absoluta de información personal por un análisis de patrones; sigue siendo necesaria revisión humana de documentos y contenido antes de publicar.

El índice tiene 299 entradas y conserva el documento histórico sin extensión. Ese caso demuestra que filtrar solo extensiones no garantiza privacidad. También las exclusiones de `.gitignore` no eliminan archivos ya rastreados o históricos. No se modificaron índice, ZIP o parches. Los informes/ejecutor del ensayo y este informe son posteriores al ZIP: el paquete de activación deberá regenerarse por lista permitida, incluir documentación aprobada y recibir manifiesto nuevo, sin agregar todo el directorio con `git add .`.

## 7. Activación y recuperación propuestas: puerta de autorización

El procedimiento existente se mantiene y se complementa con estos criterios concretos; **ningún paso operativo ejecutado**:

1. **Antes de autorizar:** P0–P9 aprobados, Git íntegro y revisión privada, paquete final fijado por hashes, configuración operativa revisada, pruebas con rol mínimo, responsables y ventana acordados. Sin cualquiera de estas evidencias: NO activar.
2. **Antes de migrar:** mantenimiento y cese de escritores solo tras autorización; respaldo final restaurable y snapshot/inventario de ese instante. Si destino/plan/hashes difieren o hay transacciones incompatibles: parar sin DDL. El respaldo del ensayo no sustituye este último respaldo.
3. **Durante migración:** backend, SQL y frontend como una versión coordinada. Usar estrategia transaccional global previamente ensayada; la transacción por migración de Django no equivale al lote completo. Errores/tiempos excedidos: mantener mantenimiento y verificar qué quedó confirmado, sin `--fake` ni inversas automáticas.
4. **Antes de abrir escrituras:** cero pendientes, conservación de filas, backfill esperado, permisos asignados sin expansión, índices válidos, triggers activos y pruebas por rol. Ante diferencias: no abrir operación.
5. **Fallo antes de nuevas escrituras:** si rollback global validado, comprobar inventario y versión anterior. Si no, restaurar respaldo completo en otra base restringida y verificarla antes de proponer cambio de conexión. No sobrescribir el origen ni borrar evidencia.
6. **Fallo después de nuevas escrituras:** detener escritores con autorización y conservar datos nuevos; las inversas pueden estar bloqueadas por multirrol/identidad. Restauración antigua implica pérdida de nuevas operaciones: requiere conciliación auditada y aprobación del responsable. No reducir roles, borrar eventos o perder matrículas silenciosamente.
7. **Reapertura:** responsable valida versión/destino, datos, revocación y separación de facultades; documenta alcance, tiempos y cualquier conciliación. Sin aceptación verificable: mantenimiento.

## 8. Decisiones que requieren aprobación y pendientes

1. Confirmar responsable/destino y modalidad para un respaldo reciente: entrega protegida por el responsable o extracción de lectura bajo identidad existente validada. Si faltan permisos, autorizar un cambio separado al administrador competente; esta sesión no lo realiza.
2. Aprobar ubicación, acceso, retención y aislamiento de red del ensayo final, y cualquier cambio de VM/firewall necesario. Confirmar si puede emplearse copia íntegra protegida para conservación y una copia seudonimizada para pruebas.
3. Autorizar integración del blob recuperado **en otra copia Git**, más revisión privada de su contenido; no publicación ni reescritura del historial.
4. Autorizar preparación del perfil operativo y regeneración del paquete, sin activarlo; fijar condiciones de servicio, secretos y privilegios mínimos.
5. Tras el ensayo final, decidir ventana, responsables y recuperación; cualquier migración real, cambio de destino, despliegue o push sigue requiriendo autorización específica independiente.

Evidencia privada de esta sesión: `respaldos/preparacion_activacion_20261102/` en integración, con `recuperacion_git.json`, binario/base64 históricos, `auditoria_paquete.json` y `comprobaciones_finales.json`. El informe público no incluye credenciales, filas ni contenido del documento recuperado. Único archivo documental añadido fuera de ese directorio privado: este informe. No se modificó la aplicación original ni la operativa. Se detiene aquí la verificación.
