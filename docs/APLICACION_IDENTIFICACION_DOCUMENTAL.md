# Aplicación y cierre de identificación documental

Verificación final: 28 de octubre de 2026, hora Colombia. Migración autorizada: **deportistas.0002_identificacion_documental**. Base efectiva comprobada: PostgreSQL **zona_bloque**, esquema **public**.

## Resultado

La migración figura aplicada y no existen migraciones pendientes. En la continuación final no se ejecutaron migraciones, escrituras de datos ni pruebas con fixtures en la base institucional: se realizaron consultas dentro de una transacción declarada `READ ONLY`, peticiones GET y actualizaciones exclusivamente documentales. No hubo commits ni push.

Se confirmó el catálogo con siete tipos: RC, TI, CC, CE, PA, PPT y DNI. Se comprobaron las diez restricciones explícitas. El manifiesto registra las 15 operaciones aprobadas: tres AddField, dos CreateModel, nueve AddConstraint y un RunPython que incorpora únicamente los siete tipos técnicos. La décima restricción está incluida en CreateModel. Se añadieron los dos tipos de contenido y ocho permisos de modelo estándar, sin otorgarlos a usuarios.

El archivo aplicado conserva SHA-256 `82f67e30a11c8c5d6fc1a035458d74d0787c2c6505cac38be69ee3401464040d`. El inventario detallado está en [Identificación documental](IDENTIFICACION_DOCUMENTAL.md).

## Respaldo y recuperación comprobada

- Respaldo anterior a la migración: `respaldos/identificacion_aplicacion_20261029T011218Z/zona_bloque_antes_identificacion.dump`.
- Manifiesto: `respaldos/identificacion_aplicacion_20261029T011218Z/manifiesto.json`, estado `aplicada_y_confirmada`.
- Tamaño comprobado: **136388 bytes**.
- SHA-256 recalculado en la revisión final: **0da9e45dc83e1f66220c9c362e73878dd8a1bceb2eadaba9e918f5270e049a83**.

Antes de migrar se listó el catálogo del respaldo, se leyó el archivo completo con pg_restore y se restauró en `recuperacion_documental`, dentro de un clúster PostgreSQL independiente. Las 29 tablas restauradas coincidieron en conteos y huellas con el origen. El clúster se detuvo al finalizar. La revisión final confirmó el manifiesto y la igualdad de `huellas_restauracion.json`, `huellas_antes` y `huellas_despues`, además de recalcular el hash del archivo dump. No se repitió la restauración ni la aplicación.

Los nombres temporales utilizan UTC: `20261029T011218Z` corresponde al 28 de octubre a las 20:12:18 en Colombia. Los archivos permanecen en el directorio privado excluido del control de versiones.

## Conservación de datos e identidad

Las proyecciones de **todas las columnas preexistentes de las 29 tablas** mantienen conteos y SHA-256 idénticos, tanto después de aplicar como en la consulta final. Solo se excluyen de esa comparación los metadatos nuevos expresamente previstos: el registro de esta migración, los dos tipos de contenido nuevos y sus ocho permisos. Las tablas de relaciones y concesiones anteriores se comparan íntegramente.

Permanece **un deportista ficticio**, con los mismos `id`, `identificador_publico`, código interno, campos anteriores y relaciones. Sus tres campos documentales están NULL. No se le asignó un documento inventado ni se generaron eventos documentales: el historial documental tiene cero registros. Las rutas por UUID siguen funcionando. No se imprimen aquí identificadores ni datos personales.

## Comprobaciones GET finales

Consultas autenticadas mediante APIClient de Django, dentro de la transacción de solo lectura y con los usuarios existentes. Se utilizó autenticación forzada exclusivamente en memoria, sin iniciar sesiones persistentes ni simular un login en el navegador.

| Recurso | Administrador | Coordinador activo |
| --- | --- | --- |
| `/api/deportistas/` | 200 | 200 |
| `/api/deportistas/{uuid}/` | 200 | 200 |
| `/api/tipos-documento/` | 200 | 200 |
| `/api/deportistas/{uuid}/historial-documental/` | 200 | 200 |
| `/api/paneles/{rol}/resumen/` | 200 | 200 |
| `/api/organizacion/grupos/` | 200 | 200 |

La ficha devuelve «Documento pendiente». El listado docente devuelve 200 dentro de su ámbito; el profesor recibe 403 al solicitar el historial documental o cualquiera de los dos resúmenes reservados. Un visitante anónimo recibe 403 en el listado de deportistas. La privacidad con documentos completos ficticios se cubrió en las pruebas aisladas; no se añadió un documento al registro institucional para demostrarla.

Además se realizaron GET reales por red local, sin sesión:

| URL | Resultado |
| --- | --- |
| `http://localhost:8000/api/deportistas/` | 403 esperado: autenticación requerida |
| `http://localhost:5173/api/deportistas/` | 403 esperado a través del proxy Vite |
| `http://localhost:5173/administracion` | 200, aplicación React |
| `http://localhost:5173/coordinacion` | 200, aplicación React |

Estos resultados confirman disponibilidad de servidores y proxy. No sustituyen la comprobación visual autenticada. Las APIs ya no devuelven el 503 temporal de esquema pendiente.

## Pruebas: resultados finales de la ejecución precedente

| Suite | Resultado observado |
| --- | --- |
| Backend completo en PostgreSQL aislado | **204 aprobadas**, incluidas seis de concurrencia; 22,552 segundos |
| Frontend Vitest | **54 aprobadas**, cinco archivos; 8,38 segundos |

El clúster de la suite backend se detuvo; evidencia privada en `respaldos/pruebas_fase3_0modsb13/`. En esta continuación de solo lectura se confirman esos resultados de la ejecución inmediatamente anterior; no se vuelve a ejecutar la suite ni a generar fixtures. Las verificaciones actuales de manifiesto, huellas, catálogo, permisos GET y migraciones concluyeron sin fallos.

Como evidencia anterior de la implementación se mantienen seis pruebas del cliente HTTP, 18 recorridos de navegador con API simulada y build Vite aprobados. No se presentan como nuevas ejecuciones de esta continuación. npm audit no pudo obtener resultado por conectividad con el registro; sigue sin certificarse su resultado.

## Incidencias de la ejecución precedente

1. El primer ensayo de restauración detuvo el proceso **antes de migrar** al comparar representaciones JSON de fechas con diferentes zonas horarias. Se igualó la sesión de recuperación a UTC, como Django. El segundo ensayo, con un respaldo nuevo, confirmó igualdad de todas las huellas y permitió la aplicación. El primer intento quedó registrado privadamente como detenido; no alteró el esquema institucional.
2. Una prueba frontend falló porque su simulación respondía al resumen institucional con el objeto del panel inicial, sin `profesores.activos`. Durante la ejecución precedente se corrigió únicamente la respuesta simulada de `frontend/src/pruebas/Aplicacion.test.jsx`; la nueva ejecución aprobó las 54 pruebas. No se modificó código en la continuación final de solo lectura.

El script nuevo `scripts/aplicar_identificacion_documental.py` conserva el procedimiento exclusivo autorizado y rechaza su repetición cuando la migración ya está aplicada. **No debe volver a ejecutarse para verificar el estado.** El antiguo `scripts/verificar_identificacion_pendiente.py` corresponde al estado previo y ahora rechazaría correctamente el esquema aplicado.

## Procedimiento de recuperación

No se necesita recuperación: los datos anteriores y las verificaciones son correctos. Si se detectara una incidencia posterior, detener escrituras y preservar manifiesto, dump y evidencias. Antes de usar el respaldo, recalcular su SHA-256 y comprobar el catálogo. Restaurarlo primero en una base nueva y aislada con `pg_restore --no-owner --no-privileges --exit-on-error`, usando el archivo indicado; comparar las columnas originales con el manifiesto, igualando la sesión de comparación a UTC.

El respaldo representa el estado **anterior** a la identificación documental: cualquier recuperación de servicio debe coordinar también la versión del código y el esquema esperado. No restaurar encima de zona_bloque, eliminar tablas ni revertir migraciones sin un plan revisado y autorización expresa. Una recuperación institucional debe considerar cualquier escritura legítima posterior al respaldo. No se incluyen credenciales en comandos ni documentos.

## Punto de parada

Estado listo para comprobación visual conjunta en `http://localhost:5173/administracion` y `http://localhost:5173/coordinacion`, utilizando las cuentas existentes. Verificar listado y ficha, «Documento pendiente», separación de acciones y paneles. No es necesario guardar el formulario ni asignar documento para esta revisión. No se avanzó a otros módulos.
