# B3-C — API e interfaz de reubicaciones administrativas

Fecha: 30 de octubre de 2026. Desarrollo y pruebas con escrituras exclusivamente en PostgreSQL temporal aislado. **No se aplicó `0004` a `zona_bloque`, no se ejecutaron operaciones sobre sus registros ni se hicieron commits o push.**

## 1. Integración realizada

Se revisaron `IMPLEMENTACION_EJECUCION_ASCENSOS_B3_B2.md`, los servicios B1/B2/B3, sus permisos, serializers, rutas, componentes y pruebas. Se conserva el servicio transaccional `ejecutar_reubicacion` sin duplicar su operación deportiva ni reabrir el antiguo cambio individual de nivel.

Se incorporó un mixin de acciones específicas a `AscensoVista`, bajo el router de ascensos existente. No se creó un CRUD de resultados ni una mutación genérica del estado de la progresión. La preparación administrativa usa `revisar_plan`, no `disponer_inscripcion`, reservado al circuito pedagógico anterior a la decisión.

La ejecución de una fila y su resultado siguen siendo una unidad transaccional del servicio B3-B2. Sus bloqueos, validaciones y triggers son la autoridad definitiva. La elegibilidad mostrada por una consulta es informativa y puede cambiar antes de ejecutar.

## 2. Permisos y separación de responsabilidades

| Operación | Coordinador activo | Administrador activo | Profesor |
|---|---|---|---|
| Consultar plan administrativo, revisiones y resultados | Sí | Sí | No |
| Registrar revisión administrativa de progresión aprobada | Sí | Sí | No |
| Ejecutar reubicación expresamente preparada | Sí | Sí | No |
| Aprobar o rechazar pedagógicamente | Conserva facultad existente | No | No |
| Autorizar excepción pedagógica | Conserva servicio existente | No | No |
| Alterar libremente estados/resultados históricos | No | No | No |

Los permisos se comprueban en Django con el usuario actual. El servicio vuelve a comprobar la autoridad durante los bloqueos. No se modificaron roles, credenciales, reglas globales de autenticación, sesiones ni CSRF. Una sesión sin CSRF válido no puede ejecutar. La vista del administrador no monta el componente de decisiones pedagógicas.

## 3. Bloqueo por instalación pendiente

`instalacion_verificada()` consulta la conexión actual, sin caché de navegador o proceso:

1. PostgreSQL y registro aplicado de `inscripciones.0004_ejecucion_administrativa`.
2. Columna `public.inscripciones_resultadoadministrativo.evidencia_ejecucion`.
3. Trigger `zdb_movimiento_ascenso_verificado` activo en modo ordinario, diferible e inicialmente diferido, sobre la tabla esperada, con función del mismo nombre en `public`.
4. CHECK validado `resultado_admin_estado_coherente`.
5. Índices `movimiento_afectacion_unico` y `movimiento_origen_unico` en la tabla y esquema esperados.

Si falta alguna condición, la respuesta de consulta declara `ejecucion_habilitada=false`, bloquea todas las filas y muestra el aviso de instalación. Los POST de revisión y ejecución responden **503**, antes de invocar servicios con escrituras. Las consultas de historial seleccionan explícitamente columnas compatibles con `0003`; no consultan el campo aún ausente. Se probó realmente este comportamiento revirtiendo `0004` en PostgreSQL temporal y reaplicándola al terminar.

Esta comprobación operativa no sustituye la auditoría de la migración ni el procedimiento autorizado de respaldo, instalación y verificación. No instala automáticamente nada ni protege frente a un propietario PostgreSQL que deliberadamente suplante objetos o desactive otras protecciones institucionales.

## 4. Contratos REST

Prefijo existente: `/api/ascensos/{id}/`, donde `{id}` identifica la progresión. Todos requieren sesión autenticada y autorización administrativa.

### GET `ejecucion/`

Sin parámetros. Retorna:

- `progresion`, `version`, `revision`, `revision_numero`, `estado_decision`, `estado_ejecucion`.
- Nombres mínimos de deportista, disciplina y niveles; IDs institucionales de disciplina y nivel de destino para el selector autorizado.
- `ejecucion_habilitada`, `aviso_instalacion`, `plan_completo`, `discrepancias`, `inscripciones_nuevas`, `advertencias_destinos` y evaluación `puede_cerrar`.
- `afectaciones`: inscripción de origen, estado/situación, fechas, disposición/motivo, destino previsto, indicador de movimiento realizado, `puede_ejecutar` y lista de `bloqueos`.
- Para origen/destino existentes: código, nombre, nivel, periodo, horarios activos, capacidad, ocupación máxima desde hoy/inicio de periodo hasta su fin, reservas vigentes y disponibilidad conservadora.
- Excepciones con situación, vigencia, motivo y responsable mínimo.

No se agregan las reservas otra vez a la ocupación: ya participan del cálculo institucional. La disponibilidad es una proyección de capacidad durante la vigencia restante, no una garantía de plaza ni una estadística de sesiones. Un destino desaparecido conserva su ID y se devuelve como objeto nulo, con `destino_inexistente` cuando pertenece a la revisión vigente; nunca se sustituye automáticamente.

### GET `revisiones/?page=1`

Historial paginado, más reciente primero: `count`, `next`, `previous`, `results`. Cada versión conserva ID, número, revisión anterior, actor, fecha, motivo, versión de la progresión y disposiciones históricas reducidas a afectación, origen, disposición, destino y motivo. No devuelve huellas internas ni el JSON completo de contexto.

### POST `revisiones/`

```json
{
  "version": 8,
  "motivo": "Motivo administrativo expreso",
  "disposiciones": [
    {"afectacion": 11, "disposicion": "reubicar", "destino": 101, "motivo": "Destino revisado"},
    {"afectacion": 12, "disposicion": "pendiente", "destino": null, "motivo": "Sin destino compatible"}
  ]
}
```

Los números son ejemplos de contrato, no referencias a registros reales. Exige todas las afectaciones exactamente una vez. Admite las disposiciones B1 según las condiciones reales: `revisar`, `reubicar`, `pendiente`, `continuidad`, `reserva`, `futura`. Solo `reubicar` admite y exige destino. Continuidad exige excepción coordinadora vigente; reserva/futura requieren su situación correspondiente. No se concede una excepción mediante texto ni se alteran filas ya ejecutadas en versiones posteriores. Una revisión puede conservar pendientes, pero no toda revisión permite ejecutar.

Retorna **201** con `id`, `numero`, `version`. Actor, fecha, número y evidencia se generan en el servidor. No modifica la decisión pedagógica ni las inscripciones. Un doble envío se controla mediante versión y bloqueo; ante respuesta perdida se consulta el historial y se actualiza, sin asumir que no se registró.

### GET `resultados/?page=1`

Historial paginado, más reciente primero, de todas las revisiones: IDs de resultado/revisión/afectación/origen/destino, estado, fecha efectiva, responsable, motivo y fecha de registro. No devuelve evidencia JSON, documentos, datos de contacto ni clave idempotente. El destino de un resultado es una **inscripción**, mientras que el destino previsto de una revisión es un **grupo**.

### POST `ejecutar/`

```json
{
  "revision": 9,
  "version": 8,
  "afectacion": 11,
  "clave": "9b331c65-8fc5-45d2-a910-35b5c5cbfda4",
  "motivo": "Motivo expreso del movimiento"
}
```

Solo estos campos; motivo máximo 240 caracteres. No admite actor, estado, destino arbitrario, fecha efectiva, decisiones ni campos extra. La revisión debe pertenecer a la progresión de la URL, también durante reintentos. Ejecuta exclusivamente el servicio B3-B2 existente.

Retorna **200** tanto en ejecución como en recuperación idempotente: `resultado`, `revision`, `afectacion`, `origen`, `destino`, `estado`, `fecha_efectiva`. Repetir la misma clave y contenido devuelve el mismo resultado; otra clave no duplica una afectación ya ejecutada. No modifica la aprobación pedagógica ni cierra la progresión.

### Errores

- **400:** campos no permitidos, tipos o contrato inválidos; validaciones de negocio existentes.
- **403:** rol o sesión sin autoridad vigente; CSRF inválido.
- **404:** progresión/revisión no existente o revisión ajena a la URL.
- **409:** versión o contexto obsoleto, plan incompleto, cupo agotado, destino desaparecido, operación duplicada u otra discrepancia del servicio.
- **503:** instalación `0004` no verificada.

Las consultas de historial solo admiten `page`; consulta de ejecución y POST no admiten parámetros de consulta. Se conservan las respuestas de error institucionales, sin trazas SQL ni datos personales adicionales.

## 5. Pantallas y comportamiento

Se reutiliza el módulo Propuestas existente:

- Coordinación: `/coordinacion/propuestas` conserva revisión/decisión pedagógica y agrega **Reubicaciones del ascenso**.
- Administración: `/administracion/propuestas` agrega el listado institucional y **Reubicaciones del ascenso**, sin botón de revisión pedagógica.
- Profesor: conserva propuestas docentes y lectura autorizada; no consulta ni ve controles de ejecución administrativa.

`EjecucionAscenso` muestra origen/destino, horarios, disponibilidad, situaciones, advertencias, excepciones e historiales paginados. Permite preparar una revisión completa mediante los componentes `Campo` y `SelectorCatalogo`. El catálogo de grupos es el endpoint institucional existente, autorizado para administración/coordinación y filtrado por disciplina, nivel y estado; la validación definitiva permanece en los servicios.

Cada ejecución exige seleccionar una fila elegible, introducir motivo y aceptar una confirmación explícita que explica el cierre de origen y el ingreso de destino. Solo se envía la afectación seleccionada. Un bloqueo sincrónico con `useRef` y controles deshabilitados evita dobles envíos mientras se espera la respuesta.

El UUID idempotente y el payload se conservan en memoria para reintentar una respuesta perdida. En ese caso el motivo queda bloqueado y se repite exactamente la misma petición. Errores 400/403/409 exigen actualizar la revisión antes de continuar; no se reintentan automáticamente. No hay peticiones de ejecución automáticas al montar componentes. Después de éxito se recargan detalle, listado e historiales. Una recarga completa de navegador pierde la clave en memoria: primero se debe consultar el historial; la unicidad del servicio y PostgreSQL sigue impidiendo duplicar el movimiento.

No se ofrecen operaciones sobre suspendidas/futuras, reservas abiertas, destinos sin disponibilidad, planes incompletos, contextos obsoletos o afectaciones ejecutadas. La interfaz refuerza los indicadores del backend con el estado global del plan y la decisión aprobada; no los reemplaza. No hay controles de cierre institucional, autorización de excepciones ni aprobación pedagógica en esta nueva pantalla.

## 6. Validaciones y auditoría conservadas

- Progresión aprobada, última revisión completa y vigente, referencias coherentes, versiones y huellas.
- Revalidación de capacidad, intervalos, horarios, estructura, disciplina, nivel y periodo en el servicio transaccional.
- Solo inscripción activa con ingreso anterior a hoy Bogotá, sin reserva abierta. Suspendidas/futuras siguen bloqueadas.
- Toda permanencia abierta en el nivel anterior requiere excepción pedagógica vigente; una disposición pendiente no la sustituye.
- Resultado histórico inmutable y eventos deportivos/institucionales dentro de la misma transacción.
- Bloqueos existentes en orden estable y restricciones de unicidad mantienen la protección ante concurrencia.
- Aprobación, resolución, autor y fecha pedagógica se conservan ante revisión o ejecución administrativa.

No se cambiaron modelos ni migraciones durante B3-C. `0004_ejecucion_administrativa` permanece como requisito pendiente de instalación real separada. Huellas comprobadas:

| Migración | SHA-256 |
|---|---|
| `0002` | `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f` |
| `0003` | `5f6fdd0fe87f1bcb37ab5273110f652ca6dc32c3590ee3b8b107a140706c8658` |
| `0004` | `115e827fbc4d84e13db8006bbee71b6882ffda4944bcba69345636b1dc7082c6` |

## 7. Archivos de esta entrega

- `backend/inscripciones/api_ejecucion.py`: contratos estrictos, bloqueo por instalación, proyección administrativa y acciones REST.
- `backend/inscripciones/views_ascensos.py`: integración del mixin y permisos de sus acciones.
- `backend/inscripciones/test_api_ejecucion.py`: pruebas API, instalación pendiente real, CSRF y concurrencia.
- `backend/inscripciones/test_api_ascensos.py` y `test_plan_ascensos.py`: adaptación de expectativas anteriores de ruta inexistente al contrato específico B3-C, conservando prohibición de mutación libre.
- `frontend/src/componentes/EjecucionAscenso.jsx`: revisión y ejecución administrativa, confirmaciones, reintentos e historial.
- `frontend/src/componentes/ListadoAscensos.jsx`: acceso institucional a la pantalla de reubicaciones.
- `frontend/src/paginas/Propuestas.jsx`: integración de administración sin autoridad pedagógica.
- `frontend/src/pruebas/EjecucionAscensos.test.jsx`: pruebas de interfaz con API simulada.
- Este documento.

No se añadieron dependencias ni se modificaron estilos generales, credenciales, roles o documentos originales.

## 8. Pruebas y verificación

Backend mediante `scripts/pruebas_postgresql_aisladas.py`, usando paquetes de `.venv-local`. Antes de ejecutar Django, el script crea un clúster hijo PostgreSQL, verifica `data_directory` y PID y configura una base `test_zdb_fase3_…` en un puerto temporal. No utiliza la conexión real para escribir.

```powershell
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

Cobertura nueva: consulta y minimización, permisos, conservación de aprobación, payload estricto, revisión de otra URL, versiones obsoletas, cupos, destinos inactivos/desaparecidos, suspendidas/futuras, plan incompleto, revisión versionada, historial paginado, idempotencia, trigger deshabilitado, CSRF y dos peticiones concurrentes con la misma clave. La prueba de esquema anterior revierte a `0003`, consulta sin la columna nueva, comprueba 503 y repone `0004`, todo en base aislada.

Incidencias corregidas durante desarrollo: dos pruebas antiguas asumían que `/ejecutar/` debía responder 404; ahora verifican contrato obligatorio y exclusión docente. El fixture de destino desaparecido necesitaba retirar su asignación ficticia protegida antes de eliminar el grupo. Un mock frontend de detalle devolvía una página en lugar de un grupo y producía una advertencia de claves; se corrigió el mock, conservando el componente compartido.

Resultados verificados:

| Verificación | Resultado |
|---|---|
| Regresión backend completa | **499 aprobadas**, 186,193 s; PostgreSQL temporal, puerto 55460; evidencia `respaldos/pruebas_fase3_gu5a8u8i/` |
| API B3-C, tras mejorar el formato legible de advertencias | **20 aprobadas**, 15,919 s; PostgreSQL temporal, puerto 51475; evidencia `respaldos/pruebas_fase3_4qxhb9zn/` |
| Django system check | Sin incidencias, 0 silenciadas |
| `makemigrations --check --dry-run` aislado | `No changes detected`, en ambas ejecuciones satisfactorias |
| Regresión frontend `npm.cmd test -- --reporter=dot` | **141 aprobadas**, 11 archivos, 15,73 s; sin advertencias de React |
| Cliente HTTP `npm.cmd run test:api` | **6 aprobadas**, incluidas sesión/CSRF y errores de permisos/red |
| Compilación `npm.cmd run build` | Correcta, Vite 7.3.7, 74 módulos, 2,38 s |

La suite nueva B3-C contiene 20 pruebas backend y 21 pruebas frontend. La regresión completa también conserva las pruebas transaccionales, SQL directo, idempotencia y concurrencia de B3-B2 y los ciclos históricos de migraciones. Tras el último ajuste exclusivo del formato de mensajes de validación, se repitieron las 20 pruebas API y la sincronización de modelos. Los dos clústeres temporales finalizaron detenidos y sus bases de pruebas fueron eliminadas.

PowerShell bloqueó inicialmente el lanzador `npm.ps1`; se usó `npm.cmd` sin cambiar políticas del sistema. Ninguna prueba dependió de servidores React/Django reales ni realizó solicitudes a datos de la escuela: frontend usa API simulada y backend `APIClient` sobre el clúster aislado. Queda pendiente la comprobación visual acompañada; antes de `0004` solo debe comprobarse la consulta y el bloqueo, sin escrituras reales.

## 9. Límites y comprobación visual posterior

1. Antes de instalar `0004`, abrir Propuestas como administrador/coordinador, consultar reubicaciones e historial: debe verse el aviso de instalación y ningún control operativo habilitado. No intentar crear datos de demostración persistentes.
2. La instalación real requiere autorización expresa independiente, respaldo verificado y verificación de objetos SQL y conservación de datos. Este trabajo no la realiza.
3. Después de una instalación autorizada, comprobar inicialmente solo lectura. Las pruebas visuales que creen revisiones o movimientos requieren registros/entorno y autorización específicos; no usar automáticamente inscripciones existentes.
4. En entorno aislado, verificar revisión completa, confirmación de una sola fila, errores de versión/cupo, recarga y resultados históricos; comprobar que administración no recibe aprobación pedagógica y profesor no recibe controles administrativos.
5. Siguen pendientes las reglas para ejecutar suspendidas/futuras y traslado de reservas, el procedimiento de cierre institucional y la conciliación de cambios posteriores a un movimiento confirmado. No se presumen autorizados.
6. El servicio conserva resultados inmutables por fila/revisión: una evidencia pendiente ya registrada exige una revisión nueva para ejecutar. No se borra ni reescribe historia.
7. No se implementaron sesiones, asistencia, evaluaciones, malla curricular, vídeos ni ClimbVision. La entrega se detiene antes de cualquier operación sobre la base real.
