# Cierre de preparación de Etapa 2 y operaciones pendientes

Fecha: 2026-11-02. Este documento concreta la siguiente intervención sin repetir auditorías. **No se ejecutaron conexiones PostgreSQL ni respaldos, restauraciones, migraciones o despliegues.** Se conserva sin cambios la copia Git íntegra de `respaldos/verificacion_tecnica_20261102/historial_independiente/.git`; no es necesario volver a recuperar objetos o repetir fsck para avanzar mientras esa evidencia no cambie.

## 1. Evidencia reutilizada

- `ENSAYO_MIGRACION_ETAPA_2.md`: cuatro migraciones, conservación, rollback y 538 pruebas backend/5 de aislamiento aprobadas en copia histórica. No son pruebas nuevas de esta sesión.
- `VERIFICACION_TECNICA_PREACTIVACION_ETAPA_2.md`: historial íntegro en copia, documento revisado con autoría pendiente antes de publicar, destino declarado `127.0.0.1:5432/zona_bloque`, servicio PostgreSQL 17 observado. No certifica configuración SQL efectiva.
- `ENSAYO_FINAL_ETAPA_2_PROCEDIMIENTO.md`: entradas, aislamiento, restauración, pruebas y paradas. Se reutiliza completo para el ensayo final.
- `PROCEDIMIENTO_ACTIVACION_RECUPERACION_ETAPA_2.md`: ventana, respaldo final, activación coordinada y recuperación. Sigue sin ejecutar.

No falta una nueva auditoría integral. Faltan datos/privilegios actuales y autorización de operaciones concretas. El procedimiento siguiente distingue obtención de lectura, captura, restauración y activación; no las agrupa en una autorización implícita.

## 2. Acceso mínimo de lectura: siguiente paso concreto

**Vía preferida:** el responsable PostgreSQL entrega por canal privado metadatos y un respaldo consistente mediante su procedimiento existente. Evita ampliar accesos y no exige crear una cuenta en esta sesión.

**Alternativa:** acreditar una cuenta existente dedicada a metadatos/respaldo, con destino y finalidad autorizados. Antes de conectarse, el responsable debe documentar que no es propietario de objetos operativos, no es superusuario ni hereda escritura/DDL, no administra roles/bases, no dispone de funciones con privilegios que permitan escribir y no puede modificar tablas/secuencias/esquemas operativos. Debe tener CONNECT, USAGE de los esquemas necesarios y SELECT suficiente de todas las tablas/secuencias que se capturarán; verificar RLS y ausencia de omisiones. No conceder `pg_read_all_data` global como atajo. Revisar privilegios PUBLIC y membresías: quitar permisos solo al rol no revoca lo heredado de PUBLIC.

Si no existe esa cuenta o no se puede demostrar su alcance, **parar**. Crear rol, cambiar GRANT/REVOKE, pg_hba o firewall requiere autorización operativa específica y ejecución del administrador competente. No usar la cuenta de aplicación y descubrir sus privilegios después de entrar. No leer o copiar su contraseña de `.env` como sustituto.

Una vez acreditada la cuenta y autorizado su uso, verificar únicamente metadatos en transacción de lectura. Conexión explícita al host/puerto/base autorizados, sin cargar Django ni `.env`; passfile temporal restringido entregado por el responsable, sin contraseña en consola o argumentos. `default_transaction_read_only=on` y timeouts son defensas adicionales, no sustituyen permisos reales.

Consultas mínimas propuestas, **no ejecutadas**:

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
SELECT app, name FROM public.django_migrations ORDER BY app, name;
ROLLBACK;
```

El responsable completará la evidencia de privilegios efectivos, proveedor/versiones de collation y configuración del proceso de aplicación. Si identidad, privilegios o esquema difieren de lo autorizado, detener antes de leer tablas de negocio. Registrar solo metadatos necesarios en carpeta privada; no publicar endpoints/usuarios secretos o configuración completa.

## 3. Captura consistente reciente: pasos exactos propuestos

Requiere aprobación de captura y protección de datos, o entrega equivalente por el responsable. No se ejecuta aquí.

1. Preparar carpeta privada nueva con herencia DACL retirada y permisos solo ejecutor autorizado, SYSTEM y Administrators, antes de generar archivos. Validar disco/espacio, finalidad, acceso y retención. No usar carpeta compartida o pública. Elegir hora/límites aceptables: pg_dump lee, pero consume E/S y mantiene locks/instantánea.
2. Registrar manifiesto del destino/configuración/código y versiones de herramientas. En proceso exclusivo descartar variables PG/POSTGRES/DJANGO heredadas y servicios libpq. Fijar explícitamente host/puerto/base/rol aprobados y PGPASSFILE privado. No escribir secretos en el manifiesto.
3. Sesión A con cuenta acreditada: iniciar `BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;`, verificar identidad como arriba, ejecutar `SELECT pg_export_snapshot();`. Guardar el identificador privado y mantener esa transacción abierta mientras se completa captura e inventario.
4. En la misma sesión A generar inventario del esquema y filas; o importar el snapshot en otra transacción READ ONLY/REPEATABLE READ antes de su primera consulta. Debe ser exactamente la misma instantánea. Reutilizar algoritmo de inventario de `ensayo_copia_restaurada.py` adaptado a conexión explícita de lectura y snapshot; **no ejecutar el script histórico `verificacion.py` ni sus conexiones embebidas al origen**. El adaptador aún debe prepararse/revisarse antes de esa operación autorizada.
5. Sesión B: pg_dump custom con ese snapshot y destino explícito. Ejemplo PowerShell parametrizado, solo tras aprobación; valores y rutas se suministran desde manifiesto privado, nunca desde `.env`:

```powershell
# NO EJECUTADO. Solo cuenta de lectura ya acreditada, con snapshot A abierto.
$env:PGPASSFILE = $passfileOrigenPrivado
$env:PGOPTIONS = '-c default_transaction_read_only=on -c lock_timeout=5000 -c statement_timeout=600000'
& (Join-Path $binPg 'pg_dump.exe') --format=custom --snapshot=$snapshotId `
    --lock-wait-timeout=5s -h $hostAprobado -p $puertoAprobado `
    -U $lectorAprobado -d $baseAprobada --file=$dumpPrivado 2> $logPrivado
if ($LASTEXITCODE -ne 0) { throw 'Captura fallida: conservar evidencia y detener' }
```

Los límites son una propuesta inicial que el responsable debe aceptar según carga, no una garantía de ausencia de impacto. No usar `--enable-row-security` para aceptar silenciosamente una captura parcial. Si permisos/RLS no permiten respaldo completo, abortar y resolver con el responsable, sin elevar la cuenta automáticamente.

6. Registrar tamaño/SHA256, resultado del proceso y lectura completa `pg_restore --file=<salida-privada> <dump>` y `--list`; inspeccionar esquema/objetos externos antes de restaurar. Comparar con inventario del mismo snapshot. Tras terminar dump e inventario, cerrar sesión A con ROLLBACK y retirar secretos del proceso según política; no destruir evidencia sin autorización.
7. Transferir únicamente dump/manifiesto/inventario autorizados al entorno aislado. Nunca copiar passfile, `.env`, sesiones/credenciales de conexión operativa o logs públicos. Un checksum sin procedencia ni restauración probada no acredita respaldo suficiente.

## 4. Restauración privada y ensayo: secuencia mínima

Requiere autorización independiente de restauración/ensayo. Se reutilizan las verificaciones y comandos detallados de `ENSAYO_FINAL_ETAPA_2_PROCEDIMIENTO.md`, sin ejecutar nada aquí:

1. Entorno sin ruta permitida a producción, sin sus secretos, con evidencia de aislamiento. Carpeta privada nueva, sin enlaces al original; puerto exclusivo distinto de 5432 y base `test_zdb_final_<nonce>`.
2. Confirmar versión, encoding, locale/proveedor/extensiones **vigentes** del origen. Histórico Spanish_Colombia.1252; ensayo anterior C. No asumir ninguno como vigente ni usar `--no-locale` por comodidad.
3. Inicializar clúster SCRAM y clave exclusiva de ensayo, arrancar proceso oculto solo en loopback y verificar PID hijo/data_directory/puerto/nonce. Contraseña incorrecta debe fallar. Crear base nueva desde template0 con parámetros aprobados. No registrar servicio ni cambiar producción.
4. Restaurar con destino explícito, sin `--create`, `--clean` o archivos operativos de configuración. Ejemplo posterior a las validaciones del procedimiento completo:

```powershell
# NO EJECUTADO. PGPASSFILE contiene solo el secreto del clúster aislado.
if ($baseNueva -notmatch '^test_zdb_final_[a-f0-9]+$' -or $puertoNuevo -eq 5432) {
    throw 'Destino de restauracion rechazado'
}
& (Join-Path $binPg 'pg_restore.exe') --exit-on-error --single-transaction `
    --no-owner --no-privileges -h 127.0.0.1 -p $puertoNuevo -U postgres `
    -d $baseNueva $dumpPrivado
if ($LASTEXITCODE -ne 0) { throw 'Restauracion fallida: no migrar' }
```

5. Inventario restaurado idéntico al snapshot en tablas/filas/huellas y esquema; comprobar secuencias y explicar únicamente normalizaciones SQL identificadas. Privilegios owners/ACL no quedan probados por una restauración sin ellos: reconstruirlos solo en copia y ensayar con rol de aplicación mínimo.
6. Crear respaldo del punto previo. El plan debe contener exactamente cuentas 0005/0006/0007 e inscripciones 0005; si aparece 0004 u otra diferencia, detener y reconciliar. Simular rollback global; aplicar lote solo a copia; probar conservación, roles/revocación/coordinador único/formalización administrativa, concurrencia y regresión con fixtures sintéticos.
7. Ensayar recuperación desde respaldo previo en otra base aislada; cotejar esquema/filas/secuencias, medir tiempo y verificar arranque anterior. Detener procesos propios, conservar evidencia privada y emitir informe. No habilitar operación tras este ensayo.

El ejecutor histórico está fijado a dump/rutas/locale y alineación de 0004; necesita adaptación explícita en archivo nuevo y prueba sintética de barreras antes del ensayo final. Este documento no afirma que sea un comando universal listo para ejecutar contra una captura reciente.

## 5. Autorizaciones que faltan y punto de parada

| Próxima operación | Qué debe estar aprobado/verificado |
|---|---|
| Consultar metadatos SQL | Destino/responsable y evidencia previa de cuenta existente estrictamente de lectura; o exportación entregada por responsable |
| Crear/cambiar accesos | Autorización específica de modificación de roles/pg_hba/firewall si fuera necesaria; no incluida en la presente fase |
| Generar respaldo reciente | Finalidad, lectura completa, snapshot común, carga, carpeta/acceso/retención y ejecución autorizada |
| Restaurar/ensayar copia | Respaldo verificado, entorno aislado, locale/configuración equivalente y adaptación del ejecutor revisada |
| Preparar paquete/perfil operativo | Cambios concretos de configuración y documentación de ejecución; no retirar barrera de settings ni desplegar implícitamente |
| Aplicar cuatro migraciones reales | **Autorización específica a base/host/ventana y lote exactos**, tras ensayo final y respaldo final restaurable; rol de migración/reversión/responsables aprobados |
| Activar aplicación modificada | **Autorización específica de despliegue y reapertura**, backend/SQL/React coordinados, permisos mínimos, smoke tests y recuperación acordada |
| Publicar Git | Autorización separada; revisión de metadatos de autoría del objeto histórico y paquete final. No reescribir historia sin decisión explícita |

No hay autorización de migración real, despliegue o publicación vigente. La entrega actual cierra la preparación documental e inicia solo diseño de Etapa 3. No se bloquea el desarrollo aislado futuro por no haber desplegado Etapa 2, ni se confunde aprobación de diseño con autorización operativa.
