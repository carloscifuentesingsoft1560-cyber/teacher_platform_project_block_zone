# Procedimiento reproducible propuesto para el ensayo final de Etapa 2

**Preparado, no ejecutado.** Requiere autorización posterior para obtener el respaldo y restaurar datos en copia. Ningún comando de restauración o migración se debe ejecutar en el equipo operativo sin destino aislado acreditado. No modifica el procedimiento histórico ni permite saltarse sus barreras.

## 1. Entradas y criterios obligatorios

El responsable debe proporcionar un manifiesto protegido con: fecha y origen verificables; hash/tamaño del archivo custom; versión exacta PostgreSQL; encoding; LC_COLLATE/LC_CTYPE y proveedor/versiones de collation; extensiones/versiones; migraciones aplicadas; inventario de esquema y filas de la misma instantánea; tablas/secuencias/ACL/RLS relevantes. Proporcionar también versión de código anterior/nueva y manifiesto de fuentes. El manifiesto no debe contener contraseñas.

Para obtenerlo: cuenta existente validada de lectura o extracción por el responsable. En una conexión explícita y transacción REPEATABLE READ READ ONLY, exportar snapshot y mantenerla abierta mientras inventario y `pg_dump --snapshot=<id>` leen la misma base. El inventario no debe ejecutar funciones de negocio. Establecer timeouts y supervisión; el dump puede ejercer presión de E/S o bloquear DDL. No usar una cuenta de escritura como sustituto ni aceptar omisiones por RLS/permisos. Guardar dump/logs con ACL restrictiva. Esta operación todavía no se realizó.

**Parada A:** sin procedencia, permisos de lectura acreditados, snapshot común, integridad o configuración efectiva, no capturar/restaurar. La extracción no exige migraciones ni escritura de registros; cualquier cambio de rol/firewall es una autorización aparte.

## 2. Aislamiento antes de copiar

Preparar una VM/equipo de ensayo independiente con ruta al servidor operativo denegada y evidencia de esa política. Si comparte host, definir una barrera equivalente verificable con el responsable; la escucha en loopback no impide por sí sola que el proceso cliente acceda al origen. No conservar `.env`, password files o credenciales operativas en ese entorno.

Crear carpeta de ensayo nueva, sin enlaces/reparse points hacia original, y limitar DACL al ejecutor autorizado, SYSTEM y Administrators antes de copiar archivos. Validar permisos de hijos. Confirmar espacio para dump, base restaurada, restauración de recuperación y logs. Acordar retención y protección del disco; no subir a servicios públicos o compartidos. No arrancar HTTP, correo o tareas que contacten destinatarios reales.

**Parada B:** sin aislamiento y acceso restringido demostrables, no transferir ni restaurar datos personales. Preferir datos sintéticos para regresión; no sirven por sí solos para acreditar conservación de una captura real.

## 3. Validación offline del respaldo

Con binarios compatibles con la versión de origen, comparar tamaño/SHA256 con manifiesto, leer catálogo y decodificar el archivo íntegro a salida privada. Revisar esquema antes de ejecutar contenido: extensiones, servidores/FDW, suscripciones, event triggers, lenguajes, funciones o comandos externos. El dump es código y datos de confianza condicionada; no ejecutar objetos desconocidos como superusuario sin revisión.

Comandos de referencia; las variables deben provenir del manifiesto y carpeta protegida, no del entorno operativo:

```powershell
# SOLO tras autorización y validación del destino. Este bloque no fue ejecutado.
$hashCalculado = (Get-FileHash -LiteralPath $archivoDump -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hashCalculado -ne $hashAprobado -or (Get-Item -LiteralPath $archivoDump).Length -ne $bytesAprobados) {
    throw 'El respaldo no coincide con el manifiesto'
}
& (Join-Path $binPg 'pg_restore.exe') --list $archivoDump > $catalogoPrivado
if ($LASTEXITCODE -ne 0) { throw 'Catalogo invalido' }
& (Join-Path $binPg 'pg_restore.exe') --file=$lecturaPrivada $archivoDump
if ($LASTEXITCODE -ne 0) { throw 'Lectura incompleta' }
& (Join-Path $binPg 'pg_restore.exe') --schema-only --no-owner --no-privileges --file=$esquemaPrivado $archivoDump
if ($LASTEXITCODE -ne 0) { throw 'Esquema ilegible' }
```

Las tres salidas pueden contener información privada. No imprimirlas en consola compartida ni añadirlas al repositorio. No basta `pg_restore --list` para probar restaurabilidad.

## 4. Crear el clúster equivalente y comprobar identidad

Elegir puerto libre distinto de 5432 y nombre `test_zdb_final_<nonce>`, sin reutilizar directorios existentes. Fijar todas las variables de conexión; descartar PG*, POSTGRES*, DJANGO*, ZDB_* heredadas, especialmente PGSERVICE y PGPASSFILE de origen. Generar secreto exclusivo de ensayo en archivo restringido y no pasarlo como argumento de contraseña. Usar SCRAM, no trust.

Inicialización de referencia para origen con proveedor libc, **no ejecutar hasta confirmar proveedor/locale**:

```powershell
& (Join-Path $binPg 'initdb.exe') -D $clusterNuevo -U postgres -A scram-sha-256 `
    --pwfile=$clavePrivada --encoding=$encodingAprobado `
    --lc-collate=$collateAprobado --lc-ctype=$ctypeAprobado
if ($LASTEXITCODE -ne 0) { throw 'Clúster no inicializado' }
```

Para otro proveedor, preparar parámetros específicos de la versión validada; detener en lugar de sustituir por C. Registrar versiones del sistema y librerías que afectan collations. El ejecutor anterior usa `--no-locale` y **no debe reutilizarse sin adaptar y probar primero con datos ficticios**.

Arrancar exclusivamente ese clúster en loopback con puerto fijado, proceso oculto y logs privados. Guardar PID hijo y nonce en el directorio; no registrar como servicio. Esperar disponibilidad y conectar solo con secreto de ensayo. Antes de CREATE DATABASE/restauración/migración validar en esa conexión:

- `SHOW data_directory` resuelto igual al directorio nuevo, sin enlaces al origen.
- Puerto/base/usuario reales iguales a los permitidos; PID del postmaster igual al proceso hijo y nonce correcto.
- Rechazo de contraseña incorrecta; ninguna autenticación trust que admita terceros locales.
- Versión, encoding, collations y extensiones compatibles con manifiesto.

Crear base nueva desde template0 con encoding/locale aprobados. Base/cadena de destino operativos no deben estar presentes en el entorno del restaurador. Instalar extensiones solo si fueron revisadas, disponibles y autorizadas en el ensayo. **Parada C:** identidad/configuración distinta, puerto ocupado, directorio existente o secreto rechazado: detener sin probar otro servidor.

## 5. Restauración y equivalencia

Con destino validado en el paso anterior, usar conexión explícita en todos los comandos. PGPASSFILE debe contener únicamente la entrada del clúster nuevo y estar protegido; no incluir secretos del origen. No utilizar `--create`, `--clean` o nombres recuperados del dump para elegir la base.

```powershell
# $baseNueva debe cumplir ^test_zdb_final_[a-f0-9]+$; puerto no operativo.
if ($baseNueva -notmatch '^test_zdb_final_[a-f0-9]+$' -or $puertoNuevo -eq 5432) {
    throw 'Destino de ensayo rechazado'
}
& (Join-Path $binPg 'pg_restore.exe') --exit-on-error --single-transaction `
    --no-owner --no-privileges -h 127.0.0.1 -p $puertoNuevo -U postgres `
    -d $baseNueva $archivoDump
if ($LASTEXITCODE -ne 0) { throw 'Restauracion fallida; no migrar' }
```

La expresión de nombre/puerto es defensa adicional; no sustituye las comprobaciones de PID/directorio/red. Restaurar sin owners/ACL exige reconstruir **en copia** privilegios mínimos revisados para roles de migración y aplicación. No afirmar que simula privilegios operativos mientras funcione solo como postgres.

Generar inventario antes de migrar con el mismo algoritmo del origen: columnas en orden físico, JSON de cada fila ordenado, SHA256 de `json.dumps(filas, ensure_ascii=False)` con misma zona horaria y DateStyle; conservar PK originales, secuencias, schema, índices, constraints, funciones, triggers y migraciones. Para tablas sin PK definir una comparación multiconjunto consistente. No almacenar filas en el informe público.

Comparar todas las tablas con snapshot, no solo entidades principales. Revisar normalizaciones de representación SQL de forma explícita; no ignorar globalmente cambios de expresiones. Validar secuencias y su siguiente valor respecto a filas antes de realizar escrituras sintéticas. **Parada D:** cualquier diferencia de datos o esquema no explicada detiene las migraciones.

## 6. Migraciones y pruebas exclusivamente en copia

1. Crear respaldo custom del punto previo ya validado. Preparar entorno Django que no cargue `.env` operativa, con nombre/puerto/directorio/nonce explícitos y barrera contra origen.
2. Comprobar `django_migrations`, consistencia del grafo y SHA256 de las cuatro fuentes del informe técnico. El plan debe contener exactamente cuentas 0005/0006/0007 e inscripciones 0005 y ningún retroceso. Si aparece 0004 u otra migración, detener y reconciliar antes de continuar; no usar `--fake`.
3. Ejecutar las cuatro más post_migrate dentro de transacción global y forzar excepción controlada; comparar rollback con inventario completo previo. Aceptar solo avances de secuencias explicados que no representen pérdida de filas.
4. Aplicar el lote completo a la copia. Confirmar cero pendientes, nuevos modelos de identidad vacíos, backfill acorde a todos los usuarios y sin nuevas facultades efectivas no previstas. Comparar filas previas por PK/columnas originales y conteos de cada tabla. Las altas de content types/permisos se validan por modelos/codenames, no por número fijo. Las tablas de asignaciones no deben cambiar indebidamente.
5. Constraints validadas, índices válidos/listos, triggers activos y función SQL de formalización vigente. Probar negativa y positiva con rol de aplicación mínimo en copia; no limitar validación al superusuario.
6. Casos sobre copia con identidades ficticias y rollback: roles combinados, revocación inmediata, aislamiento de objetos, acudiente revocado, coordinador único y separación de ascensos. No dejar movimientos reales simulados en la copia de conservación.
7. Suite backend en otra base sintética del clúster, concurrencia mediante conexiones distintas, frontend/HTTP/build y pruebas manuales por rol. Guardar comandos/versiones/códigos/duración; no declarar pruebas históricas como repetidas. El antecedente es 538 backend, 160 frontend, 6 HTTP y 5 de infraestructura; no asumir que cuenta fija equivale a cobertura suficiente.
8. Pruebas de volumen/estados ausentes en otra base sintética sin modificar producción. Una copia seudonimizada solo se genera con transformación revisada que preserve relaciones; no existe aún un transformador aprobado. No mezclar sus huellas con la conservación exacta del origen.

El orquestador actual contiene funciones reutilizables de inventario/conservación, pero sus rutas/hash/locale y supuestos de punto inicial son históricos. Preparar su adaptación en archivo nuevo y verificar barreras con datos ficticios antes de ejecutar estos pasos; nunca apuntarlo al origen o ejecutar el verificador histórico que abre conexiones operativas.

## 7. Recuperación, cierre y criterio de aprobación

Restaurar el respaldo del punto previo en otra base independiente del ensayo; cotejar esquema, datos, secuencias y versión anterior de aplicación. Medir restauración y validar permisos por rol; rollback global no sustituye este ejercicio. No ejecutar inversas automáticas si se crearon eventos multirrol o identidades incompatibles.

Comparar nuevamente la copia de conservación tras pruebas. Detener exclusivamente el proceso propio cuyo PID/directorio/nonce se verificaron, usando pg_ctl dirigido a ese directorio, incluso ante fallo. Registrar clúster detenido, bases/copia conservadas y acceso restringido. No borrar respaldos o evidencia sin política/autorización de retención.

Informe de cierre obligatorio: procedencia/hash/fecha, versión/locale/extensiones, inventario antes/después, plan y SQL, tiempos/bloqueos, resultados exactos de pruebas, restauración de recuperación, integridad de originales, riesgos y ninguna conexión de escritura al origen. Si cualquier etapa falla, documentar y detener; no ejecutar despliegue como reparación.

**Parada final:** aun con ensayo aprobado, no activar. Se requieren autorizaciones independientes para perfil operativo/paquete final, ventana, respaldo final de activación, migración real, cambio de conexión, reapertura y cualquier publicación Git. Con nuevas escrituras en operación una recuperación antigua implica conciliación de datos: no reducir roles ni descartar historial para facilitar reversión.
