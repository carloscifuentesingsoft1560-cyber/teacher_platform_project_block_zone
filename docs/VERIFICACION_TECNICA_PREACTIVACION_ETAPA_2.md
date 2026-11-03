# Verificación técnica previa a activación de Etapa 2

Fecha: 2026-11-02. **No se autoriza técnicamente la activación todavía.** Se completó la integridad Git en una copia independiente y la inspección del documento histórico. Se identificó el destino PostgreSQL declarado y el servicio local, pero no existe evidencia suficiente de una vía estrictamente de lectura para consultar el servidor. No se abrió conexión PostgreSQL, no se extrajeron datos operativos, no se restauró ninguna base ni se migró o desplegó nada.

Este informe complementa, sin reemplazar, `PREPARACION_ACTIVACION_ETAPA_2.md`, el informe de ensayo y el procedimiento de recuperación. El procedimiento reproducible de restauración propuesto se detalla en `ENSAYO_FINAL_ETAPA_2_PROCEDIMIENTO.md`; sus comandos no se ejecutaron.

## 1. Historial y contenido del objeto recuperado

El objeto `9e0d3f820d05a550eb640111207f2487c883136a`, archivo histórico `Esquema de la idea`, tiene 19002 bytes y SHA256 `5cb6633a364e4ac58741456c4337d47f6e1c27aad1532a90e475032c9692cfc3`. Se revisaron el cuerpo OOXML, las partes del contenedor y las relaciones, sin ejecutar Word, macros o enlaces externos.

El cuerpo es una especificación inicial de interfaz y funcionalidades. No se observaron contraseñas, tokens, contactos personales, identificadores ni datos de deportistas. No hay partes de macros, objetos embebidos, imágenes ni relaciones externas en el archivo inspeccionado. **Sí existen metadatos de autor y última modificación:** pueden identificar personas; no se reproducen en este informe. No sería correcto afirmar que el binario carece totalmente de información personal. Su integridad puede aprobarse para conservación privada; antes de publicar debe aprobarse el tratamiento de esos metadatos. No se sanitizó el original porque cambiar sus bytes rompería su SHA histórico.

Se copió únicamente la base `.git` de integración a `respaldos/verificacion_tecnica_20261102/historial_independiente/.git`, bajo DACL restringida. Allí se incorporaron los bytes verificados mediante `git hash-object -w --stdin`. Resultado:

- `git fsck --full`: **código 0**, sin objetos ausentes o corruptos.
- Referencias iguales a integración; sin commits nuevos ni reescritura de historia.
- Se conservaron los 15 objetos dangling que informa esa copia; no se ejecutó garbage collection.
- Los 324 archivos originales de `.git` de integración conservaron sus SHA256 tras el trabajo.
- Se conservaron los 290 hashes del proyecto original. No hubo checkout, reset, pull o push.

La integridad está resuelta **en la copia privada**, no en el repositorio de integración anterior, donde el objeto sigue sin insertarse. No se modificó ningún repositorio original. La copia no es todavía un paquete publicable ni un checkout operativo.

Reconciliación histórica: el documento inicial proponía eliminación definitiva de sesiones y tres roles separados. El maestro posterior exige historial/correcciones auditadas y roles múltiples. El documento se preserva como antecedente y no reactiva decisiones sustituidas ni autoriza implementar sesiones en esta fase.

## 2. Identificación de PostgreSQL sin conexión

Se analizaron estáticamente las claves de destino en `.env` y su precedencia en `backend/configuracion/settings.py`, sin cargar ese archivo al entorno, imprimir secretos ni arrancar Django. El código admite que variables del proceso prevalezcan sobre `.env`.

| Evidencia | Resultado |
|---|---|
| Destino declarado | `127.0.0.1:5432`, base y rol `zona_bloque` |
| Variables de destino del proceso de verificación | Ninguna sobreescribe esas cuatro claves; no demuestra el entorno del proceso de aplicación |
| Servicio | `postgresql-x64-17`, RUNNING |
| Binario de servicio | `C:/Program Files/PostgreSQL/17/bin/pg_ctl.exe runservice` |
| Directorio de datos declarado por servicio | `C:/Program Files/PostgreSQL/17/data` |
| Cuenta de servicio | NetworkService; no es prueba de privilegios del rol SQL |
| Procesos observados | Servicio pg_ctl PID 5952 y postgres PID 8172; son identificadores transitorios |
| Escucha observada | PID 8172 en `0.0.0.0:5432` |
| Acceso a configuración del clúster | Listado del directorio de datos denegado; no se elevó permiso ni se cambiaron ACL |
| Versión binarios disponible | PostgreSQL 17.11, evidencia local previa; versión efectiva SQL no consultada |

Estas evidencias son compatibles con el servidor histórico documentado, pero **no prueban el destino efectivo de un proceso de aplicación en ejecución**. Hay que contrastar su configuración autorizada y las consultas de identidad del servidor por vía de lectura antes de declararlo confirmado.

La escucha en todas las interfaces IPv4 requiere revisar pg_hba y firewall con el responsable. No demuestra que acepte conexiones externas, pero no debe describirse como servicio exclusivamente loopback. No se alteraron escucha, firewall ni servicio.

## 3. Barrera de solo lectura y límite alcanzado

No se identificó una cuenta de respaldo acreditada como solo lectura ni evidencia actual de sus privilegios efectivos. La presencia de una contraseña de aplicación no autoriza usarla como cuenta administrativa. No se intentó autenticarse para averiguar después si tenía privilegios de escritura.

Una sesión con `default_transaction_read_only=on` es defensa adicional, **no prueba suficiente** de que una cuenta no pueda desactivarlo o escribir mediante sus privilegios. La aprobación previa debe incluir membresías, propiedad, permisos de tablas/secuencias/esquemas, creación de objetos y funciones con privilegios; también RLS y completitud de la captura. No basta que el rol no sea superusuario.

Vías propuestas, sin ejecutarlas:

1. Responsable PostgreSQL entrega evidencia de una cuenta existente de lectura adecuada para metadatos/respaldo, su destino y permisos. Después se validaría la identidad en una transacción de lectura, antes de acceder a filas.
2. El responsable ejecuta las consultas de metadatos y entrega exportación protegida, con procedencia verificable; puede generar el respaldo consistente mediante su procedimiento. No requiere conceder acceso adicional a esta sesión.
3. Si no existe cuenta apropiada, crear/configurar una es una modificación operativa: necesita autorización específica y ejecución por el administrador competente. No se crea aquí.

Se detiene cualquier consulta SQL operativa hasta resolver esta barrera. La aprobación de esta verificación no se interpreta como aprobación para modificar roles, pg_hba, datos o permisos del servidor.

## 4. Configuración y esquema: comparación comprobable

| Aspecto | Documentado / esperado | Estado actual |
|---|---|---|
| Versión servidor | Histórico 17.11 | No consultada; herramientas locales 17.11 y servicio 17 |
| LC_COLLATE/LC_CTYPE | Histórico `Spanish_Colombia.1252` | Vigente no consultado; ensayo anterior usó C |
| Extensiones | No hay CREATE EXTENSION adicional en el esquema histórico revisado | Inventario completo vigente pendiente; no inferir ausencia de extensiones desde el dump |
| Encoding, TimeZone, DateStyle | Ensayo UTF8; huellas normalizadas UTC/ISO | Configuración SQL efectiva pendiente |
| Collation provider/version | No acreditados para servidor actual | Pendiente con versión/OS/librerías equivalentes en ensayo |
| Migraciones propias originales | 14 archivos numerados | Iguales byte a byte a las históricas de integración |
| Migraciones propias de integración | 18 numeradas: 14 históricas + 4 nuevas | Sintaxis AST válida; no importadas/ejecutadas en esta revisión |
| Base previa documentada | 38 tablas; 32 migraciones registradas tras 0004, incluidas Django | No se puede confirmar actualidad sin metadatos vigentes |
| Base Etapa 2 ensayada | 42 tablas; 36 migraciones registradas | Evidencia del ensayo histórico, no estado de producción |

Los 14 archivos numerados no incluyen `__init__.py` ni migraciones de Django; no deben confundirse con los 19 archivos de migraciones incluidos en referencias históricas o los 32/36 registros SQL totales.

Nuevas migraciones autorizadas para un futuro ensayo sobre copia:

| Archivo | SHA256 |
|---|---|
| cuentas/0005_enlaceidentidad_eventorol_persona_pertenenciarol_and_more.py | `5df9caff02cd09c0f49f49b00bccd351b746fcf5818c2bbb3999d9adc8e38900` |
| cuentas/0006_roles_compatibilidad.py | `3c4de814e1a5997232906709ac9d67366c50d1a64e7c87b30c8d001d758531ff` |
| cuentas/0007_remove_pertenenciarol_pertenencia_estado_coherente_and_more.py | `e9c50dea486c7288d60ebcef658ba99ff0ccf2f48215d65ae809e616b73a7af9` |
| inscripciones/0005_facultades_multirrol.py | `f1f170d7499ba8f31056c941af416449896e97ced05ae577c8e0eba11daa8b1c` |

Incompatibilidades y discrepancias que detienen activación:

- El ensayo C no demuestra compatibilidad regional con Spanish_Colombia.1252. Repetir con configuración vigente comprobada; no cambiar la collation operativa.
- El respaldo histórico es anterior a 0004; el esquema original fuente ya incluye esa migración. El ensayo final no puede asumir que está pendiente ni reaplicarla. Cualquier diferencia en `django_migrations` exige reconciliación antes de migrar la copia.
- `post_migrate` completó metadatos históricos: +10 content types/+40 permisos en el ensayo, no solo los cuatro modelos nuevos. En una captura vigente las cantidades pueden variar; validar claves naturales y ausencia de asignaciones de permisos imprevistas, no una constante de filas.
- La restauración anterior sin owners/ACL y con superusuario no acredita privilegios del rol operativo ni funcionamiento bajo RLS. Probarlos en copia con roles de migración y ejecución separados.
- No existe `.env.example` dentro de la entrega de integración examinada. No impide las pruebas con entorno explícito, pero es una carencia de documentación del paquete final; no se creó ni copió un `.env` real.
- La barrera de settings de integración impide un arranque normal. No debe retirarse como atajo: hace falta un perfil de despliegue revisado y probado por separado.

No se detectaron diferencias de bytes en migraciones históricas. **No se certifica que el esquema operativo vigente coincida**: no fue consultado.

## 5. Configuración necesaria para una ejecución posterior

Preparación documental, sin cambios de código ni servicio:

| Configuración | Requisito |
|---|---|
| Django settings | Perfil operativo independiente y autorizado; mantener barreras de ensayo. Nunca desplegar settings_pruebas ni su hasher MD5 |
| Python/dependencias | Fijar versiones efectivamente validadas desde entorno/lock aprobado; requirements actuales usan rangos. No actualizar por esta revisión |
| POSTGRES_HOST/PORT/DB/USER/PASSWORD | Destino explícito, secretos fuera de fuentes; rol de ejecución sin DDL y rol de migración temporal separado, privilegios previamente probados en copia |
| DJANGO_SECRET_KEY | Secreto protegido estable; decidir preservación/rotación con efecto en sesiones. No generar un reemplazo operativo sin aprobación |
| DJANGO_DEBUG | False |
| DJANGO_ALLOWED_HOSTS | Hosts reales concretos, sin comodín |
| DJANGO_CSRF_TRUSTED_ORIGINS | Orígenes completos de confianza; sesión/CSRF conservados |
| DJANGO_COOKIE_SECURE | True con HTTPS. Excepción HTTP local solo en desarrollo aislado |
| TLS y proxy | Servidor/proxy autorizado; revisar cabeceras y confianza antes de habilitar ajustes de proxy. No exponer runserver o Vite como producción |
| Frontend | Build revisado y rutas SPA/API compatibles. Vite usa BACKEND_PROXY_TARGET solo en desarrollo; secretos nunca en VITE_* |
| Static | STATIC_ROOT existente `backend/staticfiles`; collectstatic solo en destino autorizado, no sobre original en esta sesión |
| Medios/datos privados | Resolver almacenamiento y acceso privado por función existente, sin alias público indiscriminado. No adjuntar datos o respaldos al paquete |
| Correo/tareas | Backend actual de correo a consola; logs pueden contener contenido privado. En ensayo usar sumideros controlados sin destinatarios reales |
| Observabilidad | Logs restringidos y redactados; auditoría de facultades/ascensos, control de errores, sin contraseñas, sesiones o datos sensibles |

La configuración propuesta no habilita un servicio por sí misma. Antes de arrancarlo hay que aprobar perfil, paquete final, secretos, host y permisos, repetir pruebas por roles y `check --deploy` en un entorno autorizado. Este comando no se ejecutó contra settings operativos.

## 6. Condiciones cumplidas, pendientes y autorizaciones

**Cumplidas:** objeto verificado/revisado en privado; historial independiente íntegro; referencias preservadas; fuentes originales intactas; cuatro migraciones identificadas sin alteración histórica; destino declarado/servicio/escucha observados; procedimientos de ensayo y recuperación documentados; ninguna conexión operativa, copia de filas o publicación realizada.

**Pendientes:** revisión institucional de metadatos de autoría antes de publicar; acceso de lectura acreditado o evidencia del responsable; configuración SQL vigente; esquema actual y RLS; respaldo reciente; aislamiento de red final; restauración representativa con locale correcto; permisos mínimos; perfil operativo y paquete final con documentación actualizada.

Operaciones concretas que necesitan aprobación o entrega del responsable:

1. Entrega protegida de metadatos del servidor y prueba de privilegios de la cuenta de lectura existente. Si requiere crear/cambiar roles o accesos, aprobación operativa aparte.
2. Captura consistente reciente y destino protegido, con límites de carga, retención y acceso acordados. No se ejecutó ni se presume autorización para ampliaciones de permisos.
3. Restauración y ensayo final en copia aislada, tras validar el respaldo y aislamiento; no incluidos en esta ejecución porque se pidió detenerse antes de restaurar datos operativos.
4. Preparación del perfil de despliegue y paquete final, probados sin activación. Aprobar también tratamiento de autoría si se plantea publicación futura; no reescribir historia automáticamente.
5. Migración real, cambio de conexión, despliegue o push: autorización específica posterior independiente, condicionada a todas las verificaciones.

Evidencias privadas: `respaldos/verificacion_tecnica_20261102/` dentro de integración: `texto_objeto_privado.json`, `verificacion_historial.json`, `fsck_independiente.log`, copia Git, `destino_declarado.json`, `comparacion_migraciones.json` y manifiesto de cierre. No adjuntar ese directorio a Git. Los únicos documentos nuevos de entrega son este informe y el procedimiento de ensayo final. Se detiene la fase aquí.
