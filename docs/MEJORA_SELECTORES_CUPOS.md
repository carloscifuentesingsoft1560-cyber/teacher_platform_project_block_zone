# Mejora limitada de selectores y consulta de cupos

Fecha: 29 de octubre de 2026. Alcance: filtros de Deportistas y consulta de cupos de Inscripciones. No se modifican modelos, relaciones, claves primarias, migraciones ni permisos.

## Comportamiento implementado

En Deportistas se sustituyen los cuatro campos numéricos por selectores buscables de grupos, periodos, disciplinas y niveles. Las opciones muestran código y nombre; los grupos incorporan el periodo y los niveles su disciplina. Las peticiones y los parámetros de URL siguen utilizando los IDs existentes. Cambiar un filtro conserva los demás y vuelve a la primera página del listado. Una selección recibida por URL se resuelve a su etiqueta sin solicitar al usuario un identificador.

En Inscripciones se selecciona el grupo por código/nombre/periodo y se consulta automáticamente su disponibilidad. Sin grupo seleccionado no se consulta cupos. Es posible actualizar el resultado explícitamente; también se refresca tras una operación de inscripción o procesamiento de reservas realizada desde esa pantalla. Quitar o cambiar el grupo limpia el resultado anterior e ignora respuestas tardías.

Los catálogos utilizan las rutas existentes y su filtrado de permisos. El componente reutiliza Campo y ErrorGestion y añade búsqueda con espera de 300 ms, paginación explícita, caché por instancia, recuperación de errores y conservación de la selección al cambiar la búsqueda. No descarga todas las páginas ni utiliza una caché global entre sesiones. La consulta de detalle solo se requiere para una selección válida que no figure ya en los resultados conocidos.

La etiqueta accesible del select es explícita y estable: no depende del texto de la opción seleccionada. Se añade únicamente una regla de min-width para evitar que las opciones largas desborden el contenedor. No se cambiaron colores, tipografía ni navegación institucional.

## Cupos: extensión de lectura, sin modificar permisos

La respuesta anterior de `GET /api/inscripciones/cupos/?grupo={id}` incluía capacidad, ocupación máxima del intervalo y disponibilidad mínima para todo ese intervalo. No distinguía plazas activas y reservas a la fecha de consulta. Para mostrar esos datos reales se amplió la respuesta de forma aditiva; se mantienen las claves y semántica anteriores:

| Campo | Significado |
| --- | --- |
| grupo / cupo_maximo | Identificador técnico y capacidad existente |
| ocupacion_maxima / disponibles | Mayor ocupación y plazas disponibles durante todo el intervalo consultado |
| fecha_corte | Fecha local utilizada para el desglose actual |
| desde / hasta | Intervalo de la consulta, inclusivo para el usuario |
| inscripciones_activas | Plazas efectivas a la fecha de corte, sin las suspensiones con reserva |
| reservas_vigentes | Suspensiones que conservan plaza a esa fecha, sin reservas liberadas o vencidas |
| ocupacion_actual | Suma del desglose actual |
| disponibles_actuales | Capacidad menos ocupación actual, con mínimo cero |

Las inscripciones futuras no cuentan como ocupación actual, pero sí pueden limitar las plazas disponibles durante el intervalo restante. La fecha de vencimiento de una reserva es inclusiva, de acuerdo con las reglas existentes. Una reserva vencida deja de computar por sus fechas; el GET **no la libera, finaliza ni escribe historial**.

El cálculo reutiliza los intervalos existentes y precarga inscripciones/reservas para no repetir consultas por cada suspensión. Las llamadas anteriores a ocupacion_maxima conservan su comportamiento; el nuevo argumento opcional permite reutilizar los datos precargados solo en la consulta. No se cambia el control transaccional de altas, traslados o suspensiones.

El intervalo predeterminado sigue siendo hoy hasta el fin del periodo. Si el intervalo no está permitido, la API conserva su rechazo y la pantalla muestra el error, sin inventar disponibilidad. Consultar no reserva plazas: guardar una inscripción vuelve a validar cupo y compatibilidad en el backend.

## Permisos y conservación

Administrador y coordinador siguen utilizando su ámbito autorizado. El profesor recibe únicamente los grupos permitidos por la API existente y puede consultar sus cupos; no recibe botones ni facultades administrativas nuevas. Una consulta a grupo ajeno sigue devolviendo 404 y un visitante recibe 403. No se editaron clases de permisos, usuarios, asignaciones o credenciales.

Se realizaron GET con una cuenta administrativa existente autenticada solo en memoria, dentro de una transacción PostgreSQL declarada READ ONLY. Destino confirmado: zona_bloque/public. Catálogos y filtro de deportistas respondieron 200. Para ESC-N1-001, grupo 7, al corte del 29 de octubre: capacidad 15, plazas activas 0, reservas vigentes 0, ocupación actual/máxima 0 y disponibles 15.

Conteos y huellas SHA-256 de las 32 tablas coincidieron antes y después de las consultas. No se hicieron POST reales ni se crearon inscripciones. El plan de migraciones real continúa vacío. La comprobación de generación en seco con settings de pruebas informó «No changes detected», sin generar archivos.

## Pruebas y resultados finales

| Verificación | Resultado |
| --- | --- |
| Backend completo PostgreSQL temporal aislado | **241 aprobadas**: 235 anteriores y seis nuevas, 36,046 segundos |
| Frontend completo Vitest | **79 aprobadas**: 68 anteriores y once nuevas, siete archivos |
| Navegador automatizado con GET simulados | **18 recorridos aprobados**: dos pantallas, tres roles, anchos 390/768/1366 |
| Compilación Vite | Aprobada, 69 módulos |
| Modelos/migraciones | Sin cambios ni operaciones pendientes |

Regresiones nuevas: filtros combinados con IDs internos, limpieza de filtro, reinicio de página, código/nombre/periodo, búsqueda agrupada y paginada, selección por URL, conservación de selección, ausencia de petición de cupos sin grupo, actualización sin recargar catálogos, errores de API/catálogo, respuestas tardías descartadas y roles. La revisión de navegador comprobó también ausencia de errores JavaScript y que los selectores permanecen dentro del viewport con nombres largos.

Las pruebas backend cubren el desglose con reservas y altas futuras, vencimiento sin escrituras, reserva liberada, intervalos inválidos, roles y filtrado de deportistas. Sus fixtures se crearon solo en bases aisladas. El clúster temporal terminó detenido; evidencia privada en `respaldos/pruebas_fase3__3t1bc2p/`.

Durante la QA se ajustó el script de navegador para interceptar exclusivamente rutas `/api/` y no módulos JavaScript bajo `/src/api/`, y se corrigió la etiqueta accesible del selector nuevo. La ejecución final pasó los 18 recorridos. Se detuvo el Vite temporal de pruebas; no se reiniciaron los servidores habituales de la aplicación.

## Archivos creados

- `frontend/src/componentes/SelectorCatalogo.jsx`: selector buscable y paginado, etiquetas comprensibles y caché por instancia.
- `frontend/src/pruebas/SelectoresCupos.test.jsx`: once pruebas de interfaz, filtros, peticiones y errores.
- `frontend/pruebas/navegador-selectores.cjs`: recorridos aislados en navegador, sin escrituras ni acceso a PostgreSQL.
- `backend/inscripciones/test_consulta_cupos.py`: seis pruebas de lectura, reservas, filtros y permisos existentes.
- Este documento.

## Archivos modificados

- `frontend/src/paginas/Deportistas.jsx`: cuatro selectores y reinicio de paginación al filtrar.
- `frontend/src/paginas/Inscripciones.jsx`: selección por nombre, desglose, actualización y manejo de respuestas/errores.
- `frontend/src/estilos/_gestion.scss`: min-width exclusivo del selector nuevo.
- `backend/inscripciones/views.py`: campos agregados de lectura en la respuesta de cupos; permiso y ruta sin cambios.
- `backend/inscripciones/servicios.py`: reutilización opcional de intervalos/datos precargados, sin escrituras añadidas.
- `README.md`: resultados y enlace al informe actual.

No se realizaron commits ni push. No se modificaron documentos originales ni se desarrollaron otros módulos.

## Punto de parada

Listo para revisión conjunta en `/administracion/inscripciones` y `/administracion/deportistas`, con rutas equivalentes según rol. Probar búsqueda de ESC-N1-001, selección, disponibilidad y filtros por nombre. No es necesario guardar una inscripción para verificar estas mejoras. Se detiene el trabajo para la comprobación visual con el usuario.
