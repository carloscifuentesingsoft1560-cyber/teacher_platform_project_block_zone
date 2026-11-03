# Facultades de acudientes: implementación y migración propuesta

Este documento conserva el inventario y las verificaciones anteriores a migrar. **Estado actualizado: 0003 aplicada con autorización; cero pendientes.** El [informe de aplicación](APLICACION_COMPROBACION_FACULTADES.md) reemplaza las indicaciones históricas de espera y 503 contenidas aquí.

Verificación de implementación: 28 de octubre de 2026, Colombia. Sustituye el flujo de confirmación vacía descrito en [el análisis aprobado](ANALISIS_VERIFICACION_FACULTAD_ACUDIENTES.md).

## Resultado funcional

Parentesco declarado, contacto principal, facultad comprobada y autorización específica permanecen separados. Crear un vínculo no acredita facultades. La ruta existente `POST /api/vinculos-acudientes/{id}/verificar/` conserva su URL pero exige ahora una decisión completa: **ni version ni numero_version por sí solos permiten verificar**. No hay una ruta alternativa de confirmación vacía.

Administrador y único coordinador activo pueden registrar decisiones; el profesor no puede consultar evidencia ni registrar decisiones. Sesiones y CSRF se conservan. Los permisos se revalidan bajo bloqueo de usuarios para impedir escrituras con un coordinador relevado o inactivo.

### Comprobación y evidencia

`ComprobacionFacultad` es un evento inmutable vinculado a un vínculo y a un `TipoAutorizacion` existente, incluida su versión. No se crean finalidades o textos de autorización nuevos automáticamente.

Campos: vínculo, tipo de autorización, método presencial/documental, referencia privada UUID, resultado, indicadores de identidad contrastada y facultad contrastada, fecha/hora de comprobación, fecha/hora de registro, responsable, inicio/fin de vigencia y versión resultante del vínculo.

Resultados admitidos: **pendiente, verificada, rechazada y revocada**. Un vínculo recién creado sigue pendiente sin un evento inventado. Ambos indicadores de revisión deben ser verdaderos para acreditar; elegir el método por sí solo no demuestra suficiencia. Si la revisión es insuficiente, solo puede registrarse un resultado que no acredite. Revocada exige una acreditación anterior del mismo alcance y genera un evento nuevo.

Todos los resultados requieren método, referencia, alcance y fecha de comprobación; responsable y fecha de registro los fija el servidor. Para un resultado pendiente o rechazado la referencia identifica la gestión/revisión realizada, no un documento inexistente. Si no hubo revisión, se conserva pendiente sin guardar una decisión ficticia. El vencimiento se registra cuando corresponda y es inclusivo; debe caber en las fechas del vínculo, cuyo fin es exclusivo.

La referencia acepta **UUID v4** opaco de un registro de custodia externa. Se rechazan referencias vacías, números de documento, URLs, UUID nulo y valores con formato no admitido. No existen campos de archivos, imágenes, números documentales ni notas libres en el historial. Las referencias se entregan únicamente en la consulta de historial restringida; no se incluyen en el listado de vínculos ni en la auditoría administrativa general.

**Límite institucional:** la aplicación no se conecta a un gestor documental ni certifica automáticamente la existencia, autenticidad o suficiencia jurídica de una evidencia externa. El personal autorizado debe disponer de la referencia de custodia protegida, revisar efectivamente identidad y facultad y registrar su resultado. Una clave con formato válido no es por sí misma prueba; las dos declaraciones de revisión atribuyen responsabilidad al operador, no automatizan la evaluación. No se creó un módulo de archivos ni se inventaron documentos o reglas legales. La institución debe custodiar las evidencias y aplicar sus políticas de acceso, conservación y supresión, sin plazos universales incorporados.

### Vigencia, historial y autorizaciones

Cada decisión incrementa la versión del vínculo bajo transacción y bloqueo. Se consulta el último evento de cada finalidad/version: rechazada, pendiente o revocada sustituyen la aptitud anterior de ese alcance. Una acreditación fuera de fechas se informa como pendiente efectiva, sin editar su resultado histórico ni necesitar un proceso que escriba al vencer.

Los campos globales antiguos de facultad del vínculo se conservan **sin backfill ni transformación** para preservar el historial previo. No conceden permisos. La respuesta API calcula el resumen y una colección `facultades` por finalidad; la interfaz muestra cada alcance y su estado efectivo. Una marca anterior sin evento estructurado requiere revisión antes de un nuevo otorgamiento.

Para registrar una autorización de acudiente, el backend comprueba vínculo correcto y vigente, contacto activo, último evento verificado y vigente del **mismo tipo/version**, y cobertura de la fecha de declaración y de la vigencia solicitada. La declaración no puede anteceder a la comprobación. Una autorización sin fecha final no cabe en una facultad con vencimiento. Se conserva además la evidencia propia del otorgamiento exigida previamente: la acreditación no sustituye esa evidencia.

La nueva FK nullable `Autorizacion.comprobacion_facultad` se asigna en el servidor; el cliente no puede escogerla o falsificarla. Las autorizaciones anteriores conservan NULL y todos sus campos anteriores. No se borran ni se revocan masivamente. La respuesta `facultad_vigente` indica si el fundamento sigue siendo el evento vigente de ese alcance; tras revocación, sustitución, vencimiento o fin del vínculo se informa falso. Para un otorgante deportista este indicador es null, pues no corresponde acreditar un acudiente; no representa por sí solo la validez integral de esa autorización.

Los tipos/textos utilizados en comprobaciones no pueden reescribirse desde el API: se crea una versión nueva. Su desactivación se permite y deja sin vigencia operativa ese alcance. No se habilitan imágenes, vídeos, portales, biometría ni IA por una decisión de facultad o una autorización registrada.

## Interfaz y API

- `POST /api/vinculos-acudientes/{id}/verificar/`: serializer específico, decisión completa; respuesta de evento con estado HTTP 200. Versión obsoleta: 409. Datos insuficientes/no admitidos: 400. Sin permisos: 403.
- `GET /api/vinculos-acudientes/{id}/historial-facultades/`: eventos ordenados por versión, solo administrador/coordinador activo.
- Las rutas de vínculos y autorizaciones anteriores se conservan. No hay PUT, PATCH o DELETE de comprobaciones ni escritura genérica del estado del vínculo.

React muestra el contexto del vínculo, parentesco explícitamente declarado, prioridad de contacto y explicaciones. El formulario solicita alcance/version, método, clave privada, fecha de comprobación, resultado, indicadores de revisión y vigencia. No solicita responsable ni fecha de registro. Muestra historial bajo una sección desplegable y conserva el formulario ante un conflicto, sin reintentar automáticamente una decisión con una versión nueva. Si no puede consultar el historial, no permite decidir.

**Durante la espera de migración:** el backend detecta la ausencia del nuevo esquema. La acción y el historial de facultades y las APIs de autorizaciones devuelven **503 controlado**. El botón de comprobación se deshabilita con explicación; acudientes, vínculos, fichas y paneles permanecen disponibles. No se mantiene el flujo antiguo de verificación para evitar una ventana de autorizaciones inseguras. La renovación visual general sigue fuera de alcance.

## Inventario exacto de migración pendiente

Único archivo: `backend/deportistas/migrations/0003_comprobacion_facultades.py`.

Dependencias: `deportistas.0002_identificacion_documental` y dependencia intercambiable de `AUTH_USER_MODEL` (`cuentas.0001_initial` en este proyecto). Se verificó que esta es la única migración pendiente real.

| Operación Django | Cantidad | Efecto |
| --- | ---: | --- |
| CreateModel | 1 | Tabla `deportistas_comprobacionfacultad`, 14 columnas, tres FK PROTECT |
| AddField | 1 | `comprobacion_facultad_id` nullable en `deportistas_autorizacion`, FK PROTECT |
| AddConstraint | 5 | Una UNIQUE y cuatro CHECK en la tabla nueva |
| RunPython | 1 | Solo en PostgreSQL: CREATE FUNCTION y CREATE TRIGGER para impedir UPDATE/DELETE de eventos |
| **Total** | **8** | Sin importación, UPDATE ni DELETE de datos anteriores |

Restricciones explícitas: `facultad_version_unica` (vínculo/version_resultante), `facultad_metodo_valido`, `facultad_resultado_valido`, `facultad_revision_suficiente` y `facultad_vigencia_valida`. Se añaden PK, FK e índices automáticos de las relaciones/clave única; no hay AddIndex explícito.

Función nueva: `zdb_facultad_historial_inmutable()`. Trigger nuevo: `zdb_facultad_no_modificar`, BEFORE UPDATE OR DELETE, FOR EACH ROW. No modifica tablas existentes salvo añadir la FK nullable. El historial también bloquea modificación/borrado mediante modelo y QuerySet. En SQLite se aplican los modelos/controles de aplicación; la protección SQL adicional es PostgreSQL. Los administradores propietarios de la base siguen siendo una frontera de confianza: el trigger no protege contra un propietario que elimine objetos ni contra TRUNCATE administrativo; ninguna ruta de la aplicación ofrece esas operaciones.

No hay semillas, cambios de estados existentes ni datos personales en operaciones RunPython. La reversión de esa operación retiraría únicamente función/trigger nuevos; revertir el modelo eliminaría historial y **no está autorizado**. Django añadirá un tipo de contenido y un permiso estándar view del nuevo modelo, sin concederlo a usuarios. No se altera el control de acceso por rol de DRF.

SHA-256 del archivo propuesto: `eb74789677295641b97013087e14c391bb164ee18a5667bdfd939bc59d7dce54`.

## Archivos creados y modificados

Creados:

- `backend/deportistas/facultades.py`: contrato, comprobación transaccional, historial, estados efectivos y validación del otorgante.
- `backend/deportistas/migrations/0003_comprobacion_facultades.py`: esquema aditivo y protección PostgreSQL.
- `backend/deportistas/test_facultades.py`: validación, permisos, privacidad, inmutabilidad, rollback y concurrencia.
- `backend/deportistas/test_migracion_facultades.py`: conservación de campos y relaciones anteriores, incluido un vínculo de prueba con id 3 pendiente.
- `frontend/src/componentes/ComprobacionFacultad.jsx`: formulario explicado e historial restringido.
- `frontend/src/pruebas/Facultades.test.jsx`: nueve pruebas del formulario, resultados, insuficiencia, conflicto y bloqueo seguro.
- `scripts/verificar_facultades_pendientes.py`: comprobación reproducible de solo lectura de esquema, huellas, vínculo 3 y compatibilidad.
- Este informe.

Modificados:

- `backend/deportistas/models.py`, `serializers.py`, `views.py`, `servicios.py`: entidad, FK, permisos/contratos, integración del otorgamiento y preservación de textos usados.
- `backend/deportistas/tests.py`, `test_formularios_privacidad.py`: mantener regresiones y exigir ahora una decisión completa en vez del antiguo POST con solo versión. La prueba de autorización sin facultad sigue rechazando la operación.
- `frontend/src/paginas/AcudientesAutorizaciones.jsx`: integración del formulario y estados por alcance.
- `frontend/src/componentes/FormularioRegistro.jsx`: mostrar versión junto a finalidad en selectores; no altera payloads ni valores iniciales.
- `README.md`, `docs/MATRIZ_PERMISOS.md` y cabecera del análisis aprobado: estado y enlaces de esta ampliación.

## Pruebas, criterios de aceptación y límites

Resultados finales:

| Verificación | Resultado |
| --- | --- |
| Backend completo PostgreSQL temporal independiente | **235 aprobadas**, 208 anteriores y 27 nuevas; incluye nueve pruebas de concurrencia |
| Frontend completo | **68 aprobadas**, 59 anteriores y nueve nuevas |
| Vite build | Aprobado, 68 módulos |
| Django/makemigrations --check --dry-run (settings de pruebas) | Sin incidencias de sistema ni cambios por generar |

Las regresiones nuevas prueban: versión sola y numero_version; evidencia vacía/no opaca; método sin revisión suficiente; resultados pendiente/rechazada; responsable del servidor; administrador y coordinador; profesor, anónimo, desactivación y CSRF; vencimiento y cobertura de fechas; tipo/version/deportista distintos; revocación sin borrar autorizaciones; doble envío; prohibición de PATCH/falsificación; auditoría sin referencia; historial inmutable por ORM y SQL; rollback conjunto; esquema pendiente; migración conservadora.

Las tres concurrencias nuevas cubren dos decisiones sobre la misma versión, revocación frente a otorgamiento y desactivación de coordinación frente a comprobación. Se admite una autorización que ganó el bloqueo antes de la revocación como historia, pero su fundamento pasa a no vigente y los nuevos intentos se rechazan. La prueba de migración conserva exactamente campos de deportista/contacto/vínculo/autorización, deja el vínculo de prueba 3 pendiente y no fabrica comprobaciones ni referencias de autorizaciones históricas.

Última ejecución completa: 235 pruebas en 30,329 segundos; clúster temporal detenido, evidencia privada en `respaldos/pruebas_fase3_a5lf_sy0/`. Durante el desarrollo se corrigió el formato de errores de validación del serializer específico y la organización de una aserción de prueba; la ejecución final no presenta fallos. El build final transformó 68 módulos sin errores.

No se afirma una comprobación visual del nuevo flujo contra la base institucional: falta aplicar la migración autorizada y disponer de una finalidad/version y referencia de custodia genuinas. Las pruebas usan únicamente fixtures aislados. No se instalaron dependencias nuevas. npm audit no se repitió en este encargo; su limitación anterior de conectividad sigue documentada.

Criterios satisfechos: no se acredita por confirmación, parentesco ni contacto principal; una revisión insuficiente no verifica; el backend controla ámbito/versión/vigencia; las decisiones son trazables y no se sobrescriben; no se guardan copias/números de identidad; profesores no ganan permisos; no hay cambios persistentes en zona_bloque. La suficiencia de una evidencia externa continúa siendo responsabilidad de la revisión humana competente y no una certificación automática del sistema.

## Conservación de PostgreSQL real

Se capturó una referencia de **31 tablas** antes de implementar: `respaldos/facultades_antes_20261029T024903Z.json` (UTC; 28 de octubre en Colombia). Contiene únicamente conteos y huellas, no filas personales.

La comprobación posterior se ejecutó en una transacción declarada READ ONLY y confirmó igualdad exacta de todos los conteos/SHA-256 y **vínculo 3 pendiente**. La tabla y columna nuevas, función y trigger no existen aún en la base real. La única pendiente es 0003; no se aplicó.

GET internos con APIClient y autenticación en memoria, sin sesiones persistentes: administrador y coordinador reciben 200 en acudientes, vínculos filtrados y paneles; autorizaciones devuelve el 503 controlado esperado. No se enviaron POST institucionales, no se generaron evidencias ficticias persistentes y no se alteraron roles ni credenciales. No se realizaron commits ni push ni se avanzó a otros módulos.

## Respaldo y aplicación segura propuesta

1. Tras aprobación expresa, confirmar base efectiva zona_bloque/public, archivo/hash y plan de una sola migración. Revisar nombres de tabla, columna, índices, restricciones, función y trigger para evitar colisiones; no aplicar si aparece otro pendiente.
2. Coordinar ventana sin escrituras. Crear un respaldo nuevo en formato custom con pg_dump dentro de respaldos, sin credenciales en comandos/documentos. Comprobar código de salida, listado, lectura completa con pg_restore y SHA-256. Restaurar en una base/clúster aislados y comparar conteos/huellas antes de modificar zona_bloque.
3. Capturar el esquema y las proyecciones de todas las columnas anteriores. No comparar filas completas después de añadir columna sin excluir esa columna nueva. Registrar también los metadatos de migraciones, contenidos y permisos para distinguir las adiciones estándar.
4. Aplicar exclusivamente `migrate deportistas 0003_comprobacion_facultades`, respetando dependencias. Comprobar las ocho operaciones, tabla, columna nullable, cinco restricciones, función/trigger, índices válidos y único permiso view nuevo. Ninguna fila previa debe actualizarse.
5. Comprobar cero pendientes, todas las proyecciones anteriores idénticas, historial nuevo vacío, FK nueva NULL en autorizaciones anteriores y vínculo 3 aún pendiente. Verificar que ya no exista el 503 por esquema y que el POST incompleto se rechace, sin acreditar registros reales para probarlo.
6. Ejecutar pruebas escritoras exclusivamente aisladas o con transacciones revertidas, sin fixtures persistentes. Repetir comprobación visual con el usuario antes de registrar una revisión institucional real.
7. Ante fallo, conservar evidencia y detener escrituras; la migración es atómica. No eliminar el historial ni ejecutar una reversión destructiva. Restaurar primero en una base separada y comparar; una sustitución de la base institucional requeriría plan y autorización nuevos, considerando cualquier escritura legítima posterior al respaldo.

**Punto de parada:** solicitar autorización exclusivamente para la migración indicada. No aplicar ni marcar el vínculo 3 hasta recibir las autorizaciones correspondientes; aplicar el esquema no autoriza a inventar una comprobación de ese vínculo.
