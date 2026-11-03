# Ensayo protegido de migración de Etapa 2 — 2026-11-02

## Alcance y resultado

**Ensayo aprobado:** cuatro migraciones aplicadas únicamente a la copia, datos previos conservados, 538 pruebas backend y 5 de aislamiento aprobadas. Clústeres detenidos. Sin conexión a la base operativa, sin cambios en las fuentes originales y sin publicación Git. No equivale a autorización de despliegue ni acredita el estado operativo actual.

Se utilizó la carpeta independiente `respaldos/etapa2_20261102T182622Z/integracion`. Los únicos archivos fuente añadidos para este ensayo son `scripts/ensayo_copia_restaurada.py`, este informe y `docs/PROCEDIMIENTO_ACTIVACION_RECUPERACION_ETAPA_2.md`. No se modificaron modelos, migraciones, API o React de la entrega aprobada.

## Respaldo y protección

- Origen: `respaldos/preparacion_0004_20261031T005057Z/zona_bloque_pre_0004_20261031T005057Z.dump`, 239448 bytes.
- SHA256: `f51c94153a68261ea95b9b711424fad793e0639f5267358a52d69a3403a542c1`; coincide con archivo lateral, documentación de aplicación de 0004 y copia utilizada.
- Evidencia histórica: `restauracion_verificada.json`, inventarios de origen/restaurado y `docs/APLICACION_MIGRACION_EJECUCION_ASCENSOS_B3_B2.md`. Se cotejaron columnas, conteos y huellas de todas las tablas con `inventario_origen.json`.
- El respaldo es del 31 de octubre, anterior a `inscripciones.0004`. No se consultó producción para comprobar actualidad. Se reconstruyó el punto previo aplicando **esa única migración histórica solo en la copia**, antes de las cuatro nuevas.
- Datos potencialmente personales: directorio privado con herencia DACL retirada antes de copiar el dump; permisos exclusivamente usuario ejecutor, SYSTEM y Administrators. No hay anonimización del dump. Las pruebas añadidas usan identidades ficticias y transacciones revertidas; no se imprimen filas originales.
- Clúster PostgreSQL 17.11 nuevo, escucha exclusivamente 127.0.0.1, puerto aleatorio diferente de 5432, contraseña aleatoria SCRAM-SHA-256; contraseña incorrecta rechazada. Se descartan variables heredadas PG/POSTGRES/DJANGO/ZDB. Destino explícito, comprobación de PID, directorio real, nombre de base y nonce; perfil normal de la rama bloqueado. No hay servidor HTTP.
- Se inspeccionó el catálogo/esquema del archivo antes de restaurar: no se identificaron servidores externos, suscripciones, dblink, COPY PROGRAM o extensiones ajenas. `pg_restore --exit-on-error --single-transaction --no-owner --no-privileges`, sin `--create`.
- La protección supone que el usuario local, SYSTEM y administradores del equipo son de confianza; no pretende impedir acceso de un administrador del sistema. Los archivos privados no deben enviarse a Git, servicios externos ni adjuntarse al informe público.

## Migraciones y conservación

Plan validado exactamente, sin migraciones pendientes posteriores:

1. `cuentas.0005_enlaceidentidad_eventorol_persona_pertenenciarol_and_more`.
2. `cuentas.0006_roles_compatibilidad`.
3. `cuentas.0007_remove_pertenenciarol_pertenencia_estado_coherente_and_more`.
4. `inscripciones.0005_facultades_multirrol`.

El esquema pasa de 38 a 42 tablas. El respaldo restaurado contiene 267 filas; tras alinear la migración histórica, 268; después de Etapa 2, 328. Las 60 altas son 3 pertenencias, 3 eventos de rol, 10 content types, 40 permisos y 4 registros de migración. Se guardan inventarios antes/después con columnas, restricciones, índices, funciones, triggers, migraciones, conteos e identificadores y huellas de filas; no contienen las filas originales. Las filas preexistentes se comparan usando sus columnas originales e identificadores, para permitir las altas técnicas esperadas sin ocultar cambios en datos anteriores.

| Entidad / tabla | Antes | Después |
|---|---:|---:|
| Usuarios | 3 | 3 |
| Deportistas | 1 | 1 |
| Acudientes | 1 | 1 |
| Vínculos de acudiente | 1 | 1 |
| Autorizaciones | 0 | 0 |
| Grupos | 1 | 1 |
| Matrículas | 1 | 1 |
| Progresiones | 1 | 1 |
| Eventos de matrícula | 3 | 3 |
| Eventos de progresión | 3 | 3 |
| Revisiones / resultados administrativos | 0 / 0 | 0 / 0 |
| Nuevas personas / enlaces acreditados | inexistentes | 0 / 0 |
| Nuevas pertenencias / eventos de rol | inexistentes | 3 / 3 |
| Content types | 28 | 38 |
| Permisos Django | 109 | 149 |
| Migraciones registradas | 32 | 36 |

Todas las filas de las 38 tablas previas se conservan idénticas. No se acreditaron personas ni se fusionaron perfiles automáticamente. Los tres roles iniciales mantienen facultades previas. Todas las restricciones están validadas, índices válidos/listos y triggers habilitados. Las tablas inicialmente vacías no prueban conservación de casos reales inexistentes; esos flujos se cubren con fixtures en la regresión.

`post_migrate` crea diez content types y cuarenta permisos: cuatro modelos nuevos y metadatos faltantes de seis modelos históricos. Se valida cada clave natural contra modelos/permisos declarados por Django y se comprueba que las tablas de asignaciones a usuarios/grupos no cambien. Crear metadatos no concede roles nuevos. Esta diferencia debe incluirse en la revisión del despliegue; no atribuir todo a las cuatro tablas nuevas.

## Verificaciones y fallos del ensayo

- Restauración e integridad histórica: aprobadas antes de migrar.
- Simulación de fallo: las cuatro migraciones y post_migrate se ejecutan dentro de una transacción que se revierte deliberadamente. Esquema, datos e historial vuelven exactamente al punto previo. Las secuencias pueden avanzar sin pérdida de filas; no se promete identidad de sus contadores.
- Aplicación real únicamente a la copia: cuatro migraciones aprobadas; cero pendientes.
- Pruebas sobre copia restaurada, todas revertidas: combinación profesor/routesetter sin elevación; usuario sin asignación no lista deportistas y recibe 404 al consultar uno ajeno; revocación de administración inmediata incluso con actor ya cargado; rechazo SQL de segundo coordinador; acreditación explícita y revocación de enlace; coordinador rechazado al formalizar; administrador con formalización y sin facultad pedagógica por defecto; comprobador SQL vigente.
- Regresión completa en otra base temporal del mismo clúster, con datos ficticios: **538 aprobadas en 228,144 s**, sin fallos ni skips. Incluye pruebas con conexiones/hilos independientes de nombramiento de coordinador, revocación/relevo, cupos, propuestas, decisiones y ejecución idempotente. No es una prueba de carga a escala productiva. Django system check sin incidencias y `makemigrations --check --dry-run`: `No changes detected`. Base ficticia destruida por el runner; copia restaurada comprobada idéntica tras la suite.
- Verificación de fuentes: 290 archivos originales y 293 fuentes aprobadas de integración coinciden con sus manifiestos, sin diferencias.
- Infraestructura aislada: 5 pruebas aprobadas en 0,094 s con ruta de paquetes explícita. Un primer lanzamiento omitió `ZDB_PAQUETES_PYTHON`: 4 aprobaron y una falló por no poder importar Django; al reproducir el entorno documentado las 5 aprobaron, sin cambios de código.

Incidencias conservadas, sin ocultarlas:

1. Primer intento: restauración correcta, pero comparador de huellas usaba unión por saltos de línea frente al JSON histórico. Se detuvo antes de migrar. Se corrigió el verificador para usar la serialización histórica; no se alteró el respaldo.
2. Segundo intento: las cuatro migraciones y rollback aprobados; se detuvo en una expectativa demasiado restrictiva de +4 content types/+16 permisos. La evidencia mostró metadatos históricos incompletos. Se sustituyó la constante por validación de claves declaradas y conservación de asignaciones; no se modificó código de aplicación.
3. Tercer intento: restauración independiente desde el mismo dump, preservando las dos evidencias anteriores. Los clústeres se detienen incluso al fallar; no se sobrescribe un directorio de clúster existente.

## Evidencias y reproducción

Directorio privado definitivo: `respaldos/ensayo_restaurado_20261102_03/` dentro de integración. Contiene `procedencia.json`, `control_acceso.json`, `aislamiento.json`, `restaurado_inicial.json`, `alineacion_historica.json`, `antes_etapa2.dump`, `antes_etapa2.json`, `plan_autorizado.json`, `rollback_simulado.json`, `despues_etapa2.json`, `conservacion.json`, `metadatos_post_migrate.json`, `pruebas_funcionales.json`, `verificacion_migracion.json`, logs, `copia_intacta_tras_regresion.json`, `integridad_fuentes.json` y `resultado_final.json`. Contiene también secretos, datos e identificadores: mantener privado todo el directorio.

El script es un ejecutor controlado de este ensayo, con ruta y hash fijados, **no un comando genérico de producción**. Rechaza sobrescribir un clúster existente. Repetir exige preparar otra carpeta privada con DACL validada, copiar el mismo respaldo verificado y cambiar únicamente la constante del destino privado; revisar de nuevo el destino antes de ejecutar. Usar Python disponible y paquetes existentes con `PYTHONDONTWRITEBYTECODE=1`; no instalar dependencias ni usar settings operativos. Los workers se invocan por el orquestador, no manualmente contra otra base.

No se repiten frontend/build en este ensayo: no hay cambios React/HTTP y se conservan sus hashes aprobados. Sus resultados anteriores (160 frontend, 6 HTTP, build) son evidencia histórica, no nuevas ejecuciones. No se acredita revisión visual ni móvil.

## Riesgos y decisiones pendientes

- **Actualidad:** el dump histórico no garantiza compatibilidad con cambios posteriores de producción. Exigir respaldo reciente, inventario actual y ensayo autorizado antes de activar.
- **Representatividad:** muestra pequeña y tablas sensibles vacías; concurrencia con fixtures no predice tiempos con volumen real.
- **Locale:** el clúster efímero usa `--no-locale`; no certifica ordenación/collation idéntica a producción. Repetir ensayo final con locale/collation/versión/extensiones iguales al destino y medir índices, ordenaciones y duración.
- **Bloqueos:** backfill por usuario, índices/constraints y funciones requieren ventana sin escrituras; medir con volumen representativo. El ensayo usa lock_timeout/statement_timeout; no copiar tiempos sin medir.
- **Activación conjunta:** backend, SQL y React multirrol deben activarse como unidad; no mezclar clientes antiguos con facultades nuevas. Existe barrera de perfil aislado que debe sustituirse por configuración de despliegue revisada y autorizada, nunca eliminarse de forma improvisada.
- **Recuperación:** rollback transaccional simulado no sustituye restauración completa del respaldo ni garantiza reversión después de usar multirrol. Migración inversa bloquea estados incompatibles para proteger historial.
- **Git:** continúa pendiente el objeto histórico `9e0d3f820d05a550eb640111207f2487c883136a`; no se intentó recuperarlo ni se ejecutó push/publicación en esta sesión.
- **Privacidad:** retención/eliminación de las copias requiere decisión explícita. No se borran datos ni respaldos en este ensayo.

Siguiente paso permitido únicamente con autorización específica: resolver Git, preparar configuración de despliegue, obtener evidencia reciente protegida y revisar el procedimiento adjunto. No se inicia ninguna Etapa 3+ ni Climbing Vision AI.

## Cierre

`resultado_final.json`: `correcto=true`, `detenido=true`, `origen_contactado=false`. Los tres directorios de ensayo conservan DACL protegida y ninguno contiene `postmaster.pid` tras finalizar. La evidencia de fallos intermedios permanece privada; no se borraron respaldos ni datos. Fuentes originales y entrega aprobada verificadas de nuevo al cierre. Se detiene el trabajo; cualquier aplicación operativa, despliegue o publicación requiere autorización posterior específica.
