# Identificación documental de deportistas — implementación y verificación

Este informe conserva el análisis y los resultados anteriores a la aplicación. **Estado actualizado: migración aplicada con autorización y verificada; cero pendientes.** Consultar [informe de aplicación y cierre](APLICACION_IDENTIFICACION_DOCUMENTAL.md), que reemplaza las indicaciones de espera y 503 descritas históricamente aquí.

Fecha de la verificación previa: 28 de octubre de 2026 (Colombia). En esa etapa la migración real no se había aplicado y no se habían realizado modificaciones persistentes.

## Modelo y reglas implementadas

Se conservan `Deportista.id`, `identificador_publico`, el código interno ZB y todas las claves foráneas. Las rutas siguen utilizando UUID. El documento identifica la ficha en la interfaz; no reemplaza su identidad técnica.

Se añaden `tipo_documento` (FK al código estable del catálogo), `numero_documento` (texto de hasta 40 caracteres normalizados) y `pais_emisor` (ISO de dos letras). Los tres son nulos cuando el documento está pendiente. No se inventan números ni se completan documentos anteriores automáticamente.

El catálogo inicial contiene RC, TI, CC, CE, PA (pasaporte), PPT y DNI. Los cinco tipos colombianos RC/TI/CC/CE/PPT utilizan CO; los restantes exigen país explícito. Administración puede registrar tipos concretos adicionales con referencia de aprobación; no existe un comodín «otro» que eluda validaciones. No se infiere nacionalidad ni se cambia el documento automáticamente por edad.

La normalización aplica NFKC, mayúsculas y eliminación de espacios, conservando letras y ceros iniciales. En tipos colombianos elimina puntos y guiones de presentación; admite identificadores alfanuméricos históricos. En pasaportes y otros tipos conserva guion y barra significativos; no admite puntos ambiguos. La base exige formato canónico y unicidad por **tipo + país + número**, incluso para fichas inactivas. Estas verificaciones sintácticas no certifican autenticidad ni titularidad del documento.

Los cambios se realizan mediante servicio transaccional, bloqueo de filas y versión optimista. Se comprueban nuevamente los permisos; dos solicitudes sobre la misma versión no pueden sobrescribirse. Un cambio conserva la ficha y sus relaciones. La anulación requiere motivo específico. Una solicitud sin cambio efectivo no añade un evento ficticio.

`CambioDocumentoDeportista` conserva responsable, fecha, motivo codificado, versión y tipos/países/máscaras anterior y nueva. **No almacena números históricos completos** ni motivos libres que puedan copiarlos. La auditoría administrativa registra los nombres de campos, sin sus valores documentales. La máscara muestra como máximo los últimos cuatro caracteres; los números de cuatro caracteres o menos se ocultan completamente.

## Permisos y API

| Operación | Administrador | Coordinador activo | Profesor |
| --- | --- | --- | --- |
| Documento actual completo | Sí, ámbito institucional autorizado | Sí, gestión operativa | Nunca |
| Tipo y máscara | Sí | Sí | Solo deportistas de sus grupos autorizados |
| Cambiar documento e historial enmascarado | Sí | Sí | No |
| Buscar documento exacto | Sí | Sí | No |
| Consultar catálogo | Sí | Sí | Sí |
| Crear/modificar tipos del catálogo | Sí | No | No |

Las respuestas docentes excluyen número completo, país, código interno y fecha de nacimiento. Las restricciones se aplican antes de validar cuerpos en rutas administrativas. Los mensajes de error no reproducen números introducidos.

- `GET/POST /api/tipos-documento/`; `PATCH /api/tipos-documento/{codigo}/`.
- `POST /api/deportistas/buscar-documento/`: búsqueda exacta en cuerpo protegido por sesión/CSRF, sin números en URL.
- `POST /api/deportistas/{uuid}/cambiar-documento/`: versión, documento actual propuesto y motivo codificado.
- `GET /api/deportistas/{uuid}/historial-documental/`: historial exclusivamente enmascarado.
- Las rutas anteriores conservan sus UUID. El PATCH general no permite eludir el servicio de cambio documental.

Listado, ficha y formularios muestran documento o «Documento pendiente». El ZB se conserva en la base pero se oculta en la presentación habitual. Las acciones del listado utilizan un contenedor interno flexible con separación, objetivos de 44 px y disposición vertical en pantallas estrechas. No se renovó el resto del diseño.

## Inventario exacto de migración

Archivo único pendiente: `backend/deportistas/migrations/0002_identificacion_documental.py`.

Dependencias: `deportistas.0001_initial` y dependencia intercambiable de `AUTH_USER_MODEL` (resuelta a `cuentas.0001_initial` en este proyecto).

| Operaciones Django | Cantidad | Contenido |
| --- | ---: | --- |
| AddField | 3 | numero_documento, pais_emisor, tipo_documento en Deportista |
| CreateModel | 2 | TipoDocumento y CambioDocumentoDeportista |
| AddConstraint | 9 | Cinco en Deportista y cuatro en CambioDocumentoDeportista |
| RunPython | 1 | Siete filas técnicas de catálogo; ninguna actualización de deportistas |
| Total | 15 | Sin RemoveField, DeleteModel ni transformación de claves |

Diez restricciones explícitas: `documento_completo_o_pendiente`, `numero_documento_canonico`, `pais_documento_iso_valido`, `documento_colombiano_canonico`, `documento_deportista_unico`, `cambio_documental_version_unico`, `cambio_documental_motivo_valido`, `historia_anterior_solo_mascara`, `historia_nueva_solo_mascara` y `tipo_documento_codigo_canonico` (esta última incluida en CreateModel). Son ocho CHECK y dos UNIQUE explícitos. Se añaden además las PK, FK y unicidad de código propias de los nuevos modelos. No hay AddIndex; la unicidad documental crea un índice único parcial. Los índices automáticos de las relaciones y claves se generan por Django.

SHA-256 del archivo verificado: `82f67e30a11c8c5d6fc1a035458d74d0787c2c6505cac38be69ee3401464040d`.

## Pruebas y conservación

| Comprobación | Resultado real |
| --- | --- |
| Backend completo, PostgreSQL temporal independiente | 204 aprobadas, incluidas seis pruebas de concurrencia |
| Backend completo, SQLite en memoria | 198 aprobadas y seis omitidas por requerir concurrencia PostgreSQL |
| React | 54 aprobadas |
| Cliente HTTP Node | 6 aprobadas |
| Navegador automatizado, API simulada, tres roles y tres anchos | 18 recorridos aprobados |
| Vite build | Aprobado, 67 módulos |
| Django check / divergencias de migración | Sin incidencias / sin cambios pendientes de generar |
| npm audit | Intentado; conectividad con el registro impidió obtener resultado. No se afirma ausencia de vulnerabilidades |

La suite incluye duplicados normalizados, ceros/letras, países, restricciones SQL directas, documentos pendientes, historial sin texto completo, permisos revocados, máscara docente, búsqueda y cambios restringidos, versiones incompatibles y dos reclamaciones concurrentes del mismo documento. También incluye migración desde el esquema anterior con identidad, campos y relaciones comparados, y regresión de las fases anteriores.

La base temporal PostgreSQL fue creada y detenida por `scripts/pruebas_postgresql_aisladas.py`; no usa la base institucional para fixtures. Evidencia local excluida de Git: `respaldos/pruebas_fase3_vd68zbju/`.

En la base real se utilizó una transacción de **solo lectura**: conteos y SHA-256 de filas de las 29 tablas coinciden con la referencia previa `respaldos/identificacion_antes_20261029T001740Z.json`. El deportista ficticio existente (uno) y las relaciones permanecen intactos. No existen aún las tres columnas ni las dos tablas documentales; la única migración pendiente es la aquí descrita. `scripts/verificar_identificacion_pendiente.py` reproduce esa comprobación sin imprimir datos personales.

**Limitación durante la espera:** el código actualizado requiere el nuevo esquema para Fase 3. Sus APIs devuelven 503 controlado hasta aplicar la migración. En la misma comprobación real, los resúmenes de administrador y coordinador y la consulta de grupos devolvieron 200. Las escrituras de grupos con inscripciones comprueban disponibilidad documental antes de continuar, para evitar eludir validaciones. La interfaz documental se verificó con respuestas simuladas y el backend completo con esquema temporal; no se afirma una verificación documental completa en navegador contra la base real antes de migrar.

## Archivos creados y modificados

Backend, creados en `backend/deportistas/`: `documentos_reglas.py`, `documentos_servicios.py`, `documentos_serializers.py`, `documentos_views.py`, `test_documentos.py`, `test_migracion_documental.py` y `migrations/0002_identificacion_documental.py`.

Backend, modificados: `backend/deportistas/models.py`, `servicios.py`, `serializers.py`, `views.py`, `urls.py`, `permisos.py`; `backend/organizacion/servicios.py` y `backend/inscripciones/servicios.py` (guardas de disponibilidad de esquema).

Frontend, creados: `frontend/src/componentes/DocumentoDeportista.jsx`, `GestionDocumentoFicha.jsx`, `BusquedaDocumento.jsx`; `frontend/src/pruebas/DocumentoDeportista.test.jsx`; `frontend/pruebas/navegador-documentos.cjs`.

Frontend, modificados: `frontend/src/paginas/Deportistas.jsx`, `frontend/src/componentes/FormularioRegistro.jsx`, `Gestion.jsx`, la hoja Sass de gestión y la prueba de regresión `Fase3.test.jsx` (expectativas documentales y catálogo simulado).

Verificación/documentación: nuevo `scripts/verificar_identificacion_pendiente.py`, este informe; actualizados `README.md` y `docs/MATRIZ_PERMISOS.md`. Los respaldos/resultados privados y la compilación local no son datos para versionar.

## Aplicación segura propuesta — requiere autorización expresa

1. Coordinar una breve ventana sin escrituras. Confirmar base efectiva exactamente `zona_bloque` y plan que contenga solo esta migración. Revisar SQL, nombres existentes y ausencia de conflictos. No modificar credenciales.
2. Generar un respaldo nuevo con `pg_dump` en formato personalizado dentro del directorio privado excluido. Verificar código de salida, listar el archivo y leerlo completamente con `pg_restore --file` a un destino privado; registrar SHA-256. Una restauración de ensayo, si se autoriza, utilizará exclusivamente una base separada.
3. Capturar conteos y huellas de las tablas anteriores, usando la **proyección de sus columnas originales** para comparar después de añadir columnas; conservar claves, UUID, código, versiones y relaciones. Las huellas de fila completa cambiarían al incorporar columnas, por lo que no son comparables directamente después de migrar.
4. Solo tras aprobación, ejecutar `migrate deportistas 0002_identificacion_documental` y comprobar plan/log. No ejecutar una actualización indiscriminada. La migración es atómica; las siete filas nuevas son catálogo técnico aprobado, no deportistas ficticios. Django registrará además los tipos de contenido y permisos de los dos modelos nuevos, sin concederlos a usuarios.
5. Verificar tres columnas, dos tablas, siete tipos, diez restricciones explícitas, índice único parcial y ausencia de pendientes. Comparar las proyecciones originales de datos y relaciones. Los deportistas anteriores deben conservar documento NULL y no recibir historial documental inventado.
6. Ejecutar comprobaciones de permisos/privacidad y restricciones mediante pruebas aisladas o transacciones revertidas. Verificar paneles y recorrer las pantallas con el registro existente sin guardarlo. No introducir fixtures persistentes.
7. Ante fallo antes del commit, comprobar rollback atómico y registros previos. Ante fallo posterior, detener escrituras y conservar evidencia; no revertir modelos con eliminación de tablas ni restaurar sobre la base institucional sin una autorización adicional y un procedimiento revisado. El respaldo permite recuperación controlada en una base separada.

Los respaldos futuros pueden contener el documento vigente: deben permanecer privados y sujetos a la política institucional de conservación. Eso no habilita almacenamiento de números completos en el historial de la aplicación. No se inventan plazos legales universales.

No quedan decisiones técnicas bloqueantes para los siete tipos aprobados. Tipos/formatos adicionales necesitan definición institucional concreta. Conservar números históricos completos requeriría justificación y una autorización separada. No se desarrollaron portales de menores/acudientes, vídeos, sesiones, asistencia, evaluaciones ni IA.
