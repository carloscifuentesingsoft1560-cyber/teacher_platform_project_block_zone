# Interfaz de coordinación de ascensos — B2.2-B2

Fecha: 30 de octubre de 2026.

## Alcance

Se incorpora la revisión institucional a `/coordinacion/propuestas`, conservando la tabla anterior de inscripciones, traslados y propuestas históricas. Las progresiones mantienen su listado y sus identificadores independientes. No se crean interfaces de ejecución ni de autorización de excepciones.

Se revisaron los documentos de B2.2-A, B2.2-B1 y B2.1-B, sus contratos efectivos, los serializers y vistas de ascensos, y las consultas y permisos de organización. No fue necesario modificar backend ni contratos.

## Componentes y archivos

- `frontend/src/paginas/Propuestas.jsx`: incorpora el listado institucional al espacio del coordinador y actualiza el texto introductorio; conserva los flujos administrativos y docentes anteriores.
- `frontend/src/componentes/ListadoAscensos.jsx`: añade modo de coordinación, autor/fecha y apertura de revisión; conserva filtros y paginación y el modo docente existente.
- `frontend/src/componentes/RevisionAscenso.jsx`: nuevo detalle, horarios autorizados, advertencias, disposiciones, excepciones, eventos y decisiones motivadas.
- `frontend/src/pruebas/RevisionAscensos.test.jsx`: pruebas con API simulada de coordinación, seguridad de presentación y flujos de revisión.
- Este documento.

Se reutilizan `Campo`, `ErrorGestion`, `useListado`, `PieListado`, `SelectorCatalogo`, `solicitar` y `guardar` con CSRF. Se conservan las clases y estilos institucionales existentes. No se modifican componentes compartidos, estilos generales, dependencias, roles ni credenciales.

## Contratos utilizados

| Operación | Contrato real |
| --- | --- |
| Listar | `GET /api/ascensos/?estado_decision=...&page=...`; no se envía `search` |
| Consultar revisión | `GET /api/ascensos/{id}/`; contiene datos mínimos, versión, inscripciones, excepciones, eventos y resumen `revision` |
| Preparar disposición | `POST /api/ascensos/{id}/disponer/`, con `version`, `afectacion`, `disposicion`, `motivo`, `destino` |
| Aprobar | `POST /api/ascensos/{id}/aprobar/`, con `version`, `decision: "aprobar"`, `resolucion` |
| Rechazar | `POST /api/ascensos/{id}/rechazar/`, con `version`, `decision: "rechazar"`, `resolucion` |
| Elegir destino | `GET /api/organizacion/grupos/?disciplina=...&nivel=...&activo=true&search=...`, con paginación del selector existente |
| Consultar horarios/nombre de grupo | `GET /api/organizacion/grupos/{id}/` |
| Historial administrativo anterior | `/api/propuestas/`, sin conversión de registros |

El detalle ya contiene afectaciones y advertencias completas, por lo que no se duplican peticiones a `/afectaciones/` ni `/advertencias/`. Después de una escritura se utiliza el detalle actualizado que devuelve el POST y se recarga el listado institucional. La actualización manual vuelve a consultar el detalle y descarta el formulario anterior.

La consulta de destinos **sí existe y está autorizada**: `GrupoVista.get_queryset` utiliza `grupos_permitidos`, que permite consulta institucional al coordinador activo. `filtrar_grupos` admite disciplina, nivel y actividad. `GrupoSerializer` devuelve nombres, periodo y horarios activos, sin expedientes de deportistas. No se utiliza un endpoint docente para ampliar su ámbito ni se inventa uno nuevo.

El detalle de ascensos no incluye horarios. Se completan mediante la consulta autorizada de cada grupo mostrado. Un fallo de esa consulta se muestra localmente y no se sustituye por datos inventados. Los destinos guardados se identifican también mediante esa consulta.

## Revisión y disposiciones

La revisión muestra deportista y disciplina, origen/destino pedagógicos, proponente, fecha, justificación, decisión, plan y versión. Para cada inscripción muestra grupo, nivel, periodo, fechas, estado, situación actual, disposición/motivo, destino y reservas vigentes. Incluye excepciones con situación y límite y un historial de eventos con responsable y motivo.

Opciones disponibles:

- `revisar`, `reubicar` y `pendiente`, en afectaciones que el backend permite preparar.
- `reserva`, únicamente para situación observada `reserva`.
- `futura`, únicamente para situación observada `futura`.
- `continuidad`, únicamente si el backend devuelve una excepción de esa afectación con situación `vigente`.

Las filas sin afectación registrada no permiten preparar. Los formularios solo aparecen para progresiones pendientes; se deshabilitan si `revision.puede_preparar` es falso. Toda escritura se revalida definitivamente en Django.

No se asigna una disposición por defecto ni se envía automáticamente una selección guardada. El coordinador debe elegir expresamente una opción y motivarla. `reubicar` exige selección del catálogo; las otras opciones envían `destino: null`. El formulario no crea excepciones ni interpreta parentescos, texto o estados como autorización.

La selección filtra disciplina, nivel propuesto y actividad. No garantiza vigencia temporal común, disponibilidad o viabilidad de ejecución: Django valida la preparación y devuelve los errores pertinentes. Conforme a B1, un grupo lleno puede ser destino propuesto sin reservar plaza. Las comprobaciones finales del plan conjunto para ejecutar pertenecen a B3.

## Decisiones y seguridad

Solo el modo de coordinación presenta la revisión; profesor y administrador conservan sus interfaces anteriores. Los permisos siguen siendo responsabilidad del backend. No se incorporan controles de ejecución ni acciones para cambiar niveles efectivos o inscripciones.

Se muestran advertencias antes de decidir. Aprobar requiere `revision.puede_aprobar`; rechazar requiere `revision.puede_rechazar`. Ambas decisiones requieren motivación no vacía y confirmación explícita, y envían la versión del detalle consultado. Un plan `parcial` no se interpreta automáticamente como incompleto: se respeta el indicador de requisitos del backend.

Los envíos usan un bloqueo síncrono con referencia React, además del estado de carga, para impedir duplicados. Durante el envío se bloquean formularios, cierre y recarga. Cualquier error de escritura se presenta mediante `ErrorGestion` y bloquea nuevos envíos hasta actualizar la revisión. Esto cubre versiones obsoletas, pérdida de permisos y cambios materiales, sin intentar repetir automáticamente la decisión. Los errores de carga no ofrecen formularios utilizables.

Los datos permanecen solo en memoria del componente; no se añaden logs de payload, almacenamiento local ni cachés persistentes. Las respuestas tardías no actualizan una revisión desmontada. Formularios, campos, grupos y estados de carga tienen etiquetas accesibles; se mantienen las tablas con desplazamiento responsivo de la aplicación.

## Verificaciones

Comandos locales, sin conexión a PostgreSQL:

```powershell
cd frontend
npm.cmd test -- --reporter=dot
npm.cmd run test:api
npm.cmd run build
```

Se utiliza `npm.cmd` porque la política PowerShell local bloquea `npm.ps1`; no se modificó dicha política ni se instalaron paquetes.

La compilación Vite terminó correctamente: 73 módulos, 2,13 segundos. Las **seis pruebas del cliente HTTP** pasaron, incluyendo sesiones/CSRF y mensajes de permisos. La regresión frontend definitiva aprobó **121 pruebas en 10 archivos**, en **14,68 segundos**, sin fallos. Incluye las 107 pruebas anteriores y 14 nuevas. Durante el desarrollo se corrigió un matcher de prueba de la celda de autor y se añadió la selección positiva de destino antes de la repetición final.

Las nuevas pruebas cubren listado/filtros, separación del historial anterior, detalle con múltiples inscripciones, reserva y futura, horarios, opciones por situación, excepción vigente, payload estricto de disposición, catálogo sin destino y selección autorizada, permisos, versión obsoleta y recarga, aprobación/rechazo motivados, bloqueo de plan incompleto, actualización del listado, doble envío y ausencia de controles de coordinación para profesor/administrador. Se emplean exclusivamente respuestas simuladas, no propuestas reales.

## Verificación visual conjunta pendiente

1. Entrar como coordinador activo y abrir `/coordinacion/propuestas`.
2. Comprobar listado institucional, filtros, autor/fecha y separación de la tabla histórica.
3. Abrir una progresión ya existente. Revisar todas las filas, horarios, reservas, situaciones futuras, excepciones y eventos.
4. Comprobar que un contexto bloqueado deshabilita preparación/aprobación y que la actualización ofrece la versión vigente.
5. Revisar los formularios y el catálogo sin guardar. Confirmar que continuidad no aparece sin excepción vigente y que no existe acción de ejecución.
6. Confirmar que profesor y administrador no reciben controles nuevos de decisión.

**Punto de parada:** registrar disposiciones o decisiones desde el navegador modifica datos persistentes. No se realizaron esas operaciones en esta entrega. La prueba visual con guardado queda para revisión y autorización del usuario; no se deben usar registros reales para ensayar errores o concurrencia.

## Limitaciones y cierre

No existe en esta interfaz un procedimiento para autorizar/revocar excepciones ni reconstruir un contexto obsoleto. Se conserva el bloqueo B2.2-A/B1 y sus mensajes. Tampoco se resuelven progresiones aprobadas cuyo plan necesite revisión posterior.

No se ejecutaron pruebas backend con escrituras: no se modificó backend y el antecedente de 395 pruebas corresponde a B2.2-B1. No se verificó ni modificó el estado de migraciones de producción. No se generaron/aplicaron migraciones, ni se crearon progresiones, decisiones o inscripciones en `zona_bloque`. No hubo commits ni push. No se inicia B3.
