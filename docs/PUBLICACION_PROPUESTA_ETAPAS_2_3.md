# Publicación propuesta de Etapas 2 y 3

Fecha: 2026-11-02. **Solo preparación local. No se ejecutó push, despliegue ni migración operativa.** La rama propuesta es exclusivamente `desarrollo-zona-de-bloque`. Este documento y el inventario deben revisarse antes de confirmar el primer push.

## Historial y rama

Repositorio: `https://github.com/carloscifuentesingsoft1560-cyber/teacher_platform_project_block_zone`.

Base original de main: `decda62bff95f782e124394fb221626f12990f6d`, padre `26c4f1d137411003294c8ac701db54c375b88056`. El conector GitHub de lectura confirmó que main remoto continúa en la misma base durante esta preparación; no se actualizaron referencias remotas por escritura. main local se conserva idéntico.

Se utilizó una copia de la base de objetos íntegra ya verificada: `respaldos/etapa3_implementacion/git-completo`, dentro de integración. Esa copia es el directorio Git; el árbol de trabajo explícito es la carpeta de integración. No se sustituyó `.git` anterior, no se crearon historiales sin padres ni se reescribieron commits. La rama desarrollo parte de main y conserva sus dos commits originales.

Primer commit local: **`1e02fc8c242501c7d62496f55e9890430d500bd8`**, integración de Etapa 2. Contiene las 293 fuentes seleccionadas de esa entrega, con el historial original preservado. Segundo: **`9b67f121cc7d64c9ceecf185d98ee69d01049874`**, Etapa 3, pruebas, protección de datos y documentación. Los commits posteriores cierran documentación y corrigen la codificación del inventario, sin modificar implementación ni reescribir commits; el manifiesto de entrega registra sus SHA. El mensaje del segundo commit tiene una sustitución de carácter por la codificación de la terminal; se conserva sin amend para respetar el historial, y las fuentes/documentación se verifican en UTF-8.

Los comandos locales reproducibles de inspección, desde integración, son:

```powershell
$trabajo = (Get-Location).Path
$gitSeguro = Join-Path $trabajo 'respaldos/etapa3_implementacion/git-completo'
git --git-dir=$gitSeguro --work-tree=$trabajo log --oneline desarrollo-zona-de-bloque
git --git-dir=$gitSeguro --work-tree=$trabajo diff --stat main..desarrollo-zona-de-bloque
git --git-dir=$gitSeguro --work-tree=$trabajo fsck --full
```

La copia privada de objetos permanece fuera del inventario. La URL de push local continúa bloqueada con `NO_PUBLICAR_SIN_AUTORIZACION`; no se levantó esa barrera. Tras aprobación específica será necesario indicar el destino real de push solo para esa operación y la rama exacta, sin force ni actualización de main. Este informe no proporciona una ejecución automática ni ejecutó el comando.

## Inventario y exclusiones

`INVENTARIO_PUBLICACION_ETAPAS_2_3.md` enumera cada archivo del árbol previsto y su condición respecto a main. El manifiesto privado contiene SHA256/tamaño y la lista permitida usada para preparar el índice. Se seleccionan rutas explícitas; no se usa `git add .` ni se recorren automáticamente los respaldos, Excel o investigación para publicarlos.

Se excluyen `.env` y secretos, credenciales, bases SQLite/PostgreSQL, dumps y respaldos, logs/evidencias privadas, configuraciones de acceso reales, grabaciones, fotografías privadas, información de salud/menores, Excel/PDF/Word originales nuevos, investigación no autorizada, entornos virtuales, cachés, node_modules y dist/build. Las excepciones son únicamente fuentes/documentación propias seleccionadas y el historial original que se conserva. Los Excel de referencia y los 224 candidatos no se agregan al árbol de fuentes, ni como fixtures: los tests generan un Excel sintético en memoria.

`.gitignore` se amplió para respaldos, media/uploads/grabaciones, pgpass, volcados, archivos Office/PDF, ZIP y vídeos, además de las exclusiones ya existentes. Ignorar un patrón no elimina archivos ya rastreados ni los borra del historial: por eso se revisan índice y objetos alcanzables, no solo nombres del directorio.

## Revisión de seguridad

Se comprobaron las fuentes seleccionadas, diferencias y blobs alcanzables de todas las referencias locales. Se buscaron claves privadas, tokens GitHub/AWS, URI de bases con contraseña, coincidencias exactas con secretos configurados de origen sin imprimirlos y literales de contraseña/secretos. Los valores secretos solo se compararon en memoria; no se cargaron como entorno ni se usaron para conectar.

La revisión inicial de historia alcanzable examinó 278 blobs deduplicados; no detectó tokens o secretos configurados. Los cuatro literales encontrados corresponden a fixtures de auditoría/migración, cliente HTTP de prueba y clave declarada ficticia del runner. No son credenciales operativas. El cierre vuelve a revisar los blobs nuevos de Etapa 3 y confirma que no entran rutas prohibidas. Un análisis por patrones no equivale a garantía absoluta de ausencia semántica de datos personales.

**Decisión de privacidad pendiente:** main remoto ya contiene `Esquema de la idea` (blob `9e0d3f820d05a550eb640111207f2487c883136a`). Se revisó como documento funcional histórico; no se observaron credenciales o datos de deportistas, pero sí metadatos de autoría. La rama conserva ese objeto exactamente y no añade una nueva versión o copia del binario. No se modificó, sanitizó, borró o reescribió el historial. Antes del push, el titular debe confirmar si acepta conservar esa autoría histórica o requiere otra solución revisada. Si exige eliminarla del historial, detener publicación y acordar el tratamiento; no realizar reescritura automática ni force.

La revisión no publica archivos privados por el hecho de que el remoto ya sea público. No se incluyen el binario recuperado de la carpeta de evidencias, documentos de extracción con anotaciones, manifiestos con IDs de personas o archivos de pruebas de restauración.

## Puerta de publicación y activación

Para el primer push deben estar revisados: inventario exacto, commits de implementación y cierre, main preservado, fsck sin objetos faltantes, resultados de regresión/build, exclusiones y decisión de autoría histórica. Si algo difiere al momento de ejecutar, detener y actualizar evidencia. Publicar una rama no autoriza migrar la base ni desplegar.

La activación operativa de Etapas 2/3 sigue pendiente de las condiciones y autorizaciones de `CIERRE_PREPARACION_ETAPA_2_PASOS_MINIMOS.md`. El ensayo con datos ficticios no reemplaza una captura reciente protegida, locale/configuración equivalentes, permisos mínimos, ventana y plan de recuperación aprobados.

**Punto de parada:** no publicar ahora. Esperar confirmación específica del usuario para el primer push normal de `desarrollo-zona-de-bloque`, después de resolver las decisiones anteriores. Ninguna otra rama está autorizada para escritura remota.
