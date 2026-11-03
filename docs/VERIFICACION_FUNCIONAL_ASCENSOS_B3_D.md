# B3-D — Verificación funcional final de ascensos institucionales

Fecha: 30 de octubre de 2026 en Bogotá; comprobaciones UTC del 31 de octubre.

## 1. Alcance y método

Se verificó la integración B1/B2/B3: propuesta docente, decisión pedagógica, revisión administrativa versionada, consulta de destinos, ejecución individual, historial e idempotencia. Se conservaron las reglas existentes; no se desarrollaron sesiones docentes ni otros módulos.

En `zona_bloque` solo se realizaron consultas y evaluación de permisos, dentro de transacciones PostgreSQL **REPEATABLE READ, READ ONLY**. No se enviaron POST, no se inició sesión, no se aprobaron progresiones ni se invocaron servicios de escritura. Las comprobaciones de escritura y fallos transaccionales utilizaron exclusivamente datos ficticios en un clúster PostgreSQL temporal separado, verificado por directorio y PID antes de conectar Django.

## 2. Base real y API

Conexión confirmada: **PostgreSQL 17.11, 127.0.0.1:5432, zona_bloque, public**. `0004` está instalada y sus protecciones operativas se reconocen. No hay migraciones pendientes.

Se utilizaron `APIClient` y `force_authenticate` con las cuentas existentes para despachar solicitudes GET por las rutas y middleware reales de Django. Este mecanismo no crea sesiones ni cambia `last_login`. La transacción de solo lectura habría rechazado cualquier escritura SQL accidental.

| Comprobación | Resultado |
|---|---|
| Consultas GET por pasada | **18**; **36** entre la pasada inicial y la final |
| Respuestas satisfactorias | **15 HTTP 200** por pasada; **30** en total |
| Denegaciones previstas al profesor | **3 HTTP 403** por pasada; **6** en total |
| Errores inesperados o respuestas 500 | **Ninguno** |
| Progresión ficticia existente, ID 1 | **Rechazada**, decisión y tres eventos de auditoría intactos |
| Inscripción 18 | **Activa**, sin fecha de cierre, sin inscripción sucesora ni traslado |
| Revisiones administrativas B3 reales | **0**, consulta paginada vacía correcta |
| Resultados administrativos B3 reales | **0**, consulta paginada vacía correcta |
| Huellas antes/después de las consultas | **Idénticas** para todo el inventario |

Coordinación y administración consultaron listado/detalle de ascensos, ejecución, revisiones, resultados, cupos e historial de la inscripción. El profesor consultó su listado autorizado y recibió 403 en ejecución, revisiones y resultados institucionales. La propuesta rechazada se presenta sin una fila habilitada para ejecutar, aunque la infraestructura `0004` ya esté instalada.

Para comprobar las acciones prohibidas **no se enviaron POST en producción**. Se evaluó la misma clase de permisos de la vista, con el usuario actual y las acciones `ejecutar`/`aprobar`: profesor sin ejecución ni aprobación; administrador con autoridad administrativa y sin aprobación pedagógica; coordinador activo con ambas facultades diferenciadas. Los rechazos HTTP de POST por rol se probaron en la base aislada.

### ESC-N1-001

| Dato a fecha operativa 2026-10-30 | Valor |
|---|---:|
| Cupo máximo | **15** |
| Ocupación actual | **1** |
| Reservas vigentes que ocupan cupo | **0** |
| Plazas disponibles actuales | **14** |
| Ocupación máxima en el intervalo consultado | **1** |
| Disponibilidad conservadora en ese intervalo | **14** |

El grupo, sus horarios, la inscripción, las reservas y todos sus eventos coinciden con las huellas posteriores a la instalación de `0004`. La existencia de un registro histórico de reserva no implica que esté vigente: la API informa cero reservas vigentes y no se procesó ni liberó ninguna reserva durante esta verificación.

### Observación sobre el total de registros

Al comenzar B3-D existían **38 tablas y 270 registros**, frente a 268 al finalizar la instalación. Antes de estas comprobaciones ya había un registro adicional en `cuentas_eventoacceso` y otro en `django_session`, y la huella de `cuentas_usuario` era distinta. No se inspeccionaron ni publicaron campos personales para atribuir el cambio de usuario a un campo concreto. Las tablas deportivas relevantes seguían coincidiendo exactamente con la instalación.

Durante las consultas B3-D, el inventario completo permaneció idéntico: **270 antes y 270 después**, comprobado también mediante una instantánea fresca. No se atribuyen esos cambios previos de autenticación a esta ejecución.

Evidencia privada inicial: `respaldos/verificacion_b3_d_20261031T014216Z/`, con `resultado.json`, `inventario_antes.json` e `inventario_despues.json`. Se repitió la comprobación de lectura después de toda la regresión: `respaldos/verificacion_b3_d_20261031T014921Z/`. La comparación entre el inventario inicial de todo el ciclo y el final fue exactamente idéntica; queda registrada en `comparacion_ciclo_completo.json`. No se almacenaron respuestas API completas con nombres o expedientes en el informe de resultados.

## 3. Integración funcional aislada

Se añadió `backend/inscripciones/test_integracion_b3_d.py`. Cada prueba exige, **antes de crear fixtures**, una base `test_zdb_fase3_…` y un puerto distinto de 5432. El ejecutor crea el clúster hijo y verifica `data_directory` y PID antes de configurar las variables de conexión.

El flujo probado utiliza los contratos efectivos:

1. Profesor con asignación vigente presenta `POST /api/ascensos/`, con referencia propia y nivel consecutivo.
2. Coordinador consulta grupos institucionales mediante `/api/organizacion/grupos/` filtrado por disciplina, nivel y actividad, y consulta sus cupos.
3. Coordinador prepara expresamente las afectaciones mediante `POST /api/ascensos/{id}/disponer/`.
4. Coordinador decide mediante `POST /api/ascensos/{id}/aprobar/`.
5. Se registran dos versiones completas mediante `POST /api/ascensos/{id}/revisiones/`, sin modificar la aprobación pedagógica.
6. Se consulta `/ejecucion/` y se ejecuta una sola afectación mediante `/ejecutar/`, con UUID idempotente y versión observada.
7. Se consulta el estado, las revisiones, resultados y cupos actualizados, y se repite exactamente la petición para recuperar el mismo resultado sin escrituras adicionales.

Las seis pruebas nuevas verifican:

- Ejecución por administrador de un ascenso aprobado por coordinador, conservación de decisión/fecha/resolución, enlace histórico origen-destino, eventos y actualización real de ocupación.
- Dos inscripciones: ejecución por coordinador de una sola; la otra permanece pendiente e intacta, con excepción pedagógica temporal expresamente autorizada mediante el servicio institucional existente. El plan queda parcialmente ejecutado y no puede cerrarse.
- Fallo intencional al registrar auditoría institucional: cierre, inscripción nueva, resultado, eventos y versión se revierten juntos.
- Cupo agotado después de revisar el plan: 409, sin cambios parciales.
- Horario modificado después de la revisión: 409, sin cambios parciales.
- Profesor sin ejecución y administrador sin aprobación: 403 y ninguna modificación.

No se simuló una excepción mediante texto o estado. La autorización del caso parcial usa el servicio interno B1 de excepción, con coordinador, motivo, inicio y vencimiento, exclusivamente en fixtures aisladas.

## 4. React y rutas

Se añadió `frontend/src/pruebas/AscensosB3DRutas.test.jsx`: **nueve pruebas** con `Aplicacion`, `MemoryRouter`, proveedor de autenticación y cliente HTTP reales, frente a una API simulada en memoria. No hay solicitudes de pruebas hacia la base real.

Se verificaron ambas rutas completas:

- `/coordinacion/propuestas`.
- `/administracion/propuestas`.

Cobertura nueva:

- Propuesta rechazada con revisiones/resultados vacíos, sin errores ni POST.
- Estado de ejecución, advertencias, horarios y disponibilidad proporcionados por la API.
- Selección de una fila, motivo y confirmación explícita.
- Envío del contrato correcto con token CSRF y recarga del resultado histórico.
- Sin envío automático de aprobación pedagógica desde la operación administrativa.
- Bloqueos de reserva/suspensión, alta futura y plan incompleto.
- Doble clic mientras se espera la respuesta: un solo POST.
- Profesor rechazado al entrar directamente en la ruta de coordinación.

La regresión conserva las pruebas B3-C de revisión versionada, confirmación cancelada, versiones obsoletas, permisos, idempotencia tras respuesta perdida, prevención de doble envío y ausencia de controles pedagógicos para administración.

## 5. Resultados de verificación

| Comando/verificación | Resultado |
|---|---|
| Nuevas pruebas backend focalizadas, `-k IntegracionAscensosB3D` | **6 aprobadas**, 7,876 s; puerto 50531; evidencia `respaldos/pruebas_fase3_7xk8wj50/` |
| Regresión backend completa aislada | **505 aprobadas**, 194,968 s; puerto 62409; evidencia `respaldos/pruebas_fase3_gfi407nc/` |
| `npm.cmd test -- --reporter=dot` | **150 aprobadas**, 12 archivos, 16,93 s |
| `npm.cmd run test:api` | **6 aprobadas** |
| `npm.cmd run build` | Correcta; Vite 7.3.7, 74 módulos, 2,14 s |
| API real, solo GET | **36 respuestas previstas** en dos pasadas: 30 satisfactorias y 6 denegaciones |

La regresión completa incluye las seis pruebas nuevas, además de las pruebas anteriores de concurrencia, restricciones SQL, suspendidas/futuras, idempotencia y ciclos aislados de migración. Django: `System check identified no issues (0 silenced)`. Verificación de modelos `makemigrations --check --dry-run` en el entorno aislado: `No changes detected`. Las bases de pruebas se eliminaron y los clústeres temporales terminaron detenidos.

Comandos reproducibles:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/django_local.py shell --no-imports -c "import runpy; runpy.run_path('scripts/verificar_ascensos_b3_d_lectura.py', run_name='__main__')"

Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

Desde `frontend/`:

```powershell
npm.cmd test -- --reporter=dot
npm.cmd run test:api
npm.cmd run build
```

## 6. Correcciones y archivos

No se detectaron fallos funcionales que requirieran modificar servicios, permisos, serializers, frontend productivo o migraciones. Los fallos de auditoría y cambios de disponibilidad de las pruebas son escenarios intencionales, no incidencias del sistema real.

Archivos añadidos:

- `scripts/verificar_ascensos_b3_d_lectura.py`: verificación reproducible protegida por transacciones READ ONLY, sin crear sesiones ni enviar operaciones.
- `backend/inscripciones/test_integracion_b3_d.py`: seis flujos API completos sobre fixtures aisladas.
- `frontend/src/pruebas/AscensosB3DRutas.test.jsx`: nueve pruebas de rutas completas.
- Este documento.

La evidencia de ejecución se conserva en `respaldos/`, excluido de Git por la regla existente. No se añadieron dependencias, no se hicieron commits ni push y no se aplicaron migraciones nuevas a `zona_bloque`.

## 7. Límites y estado institucional

El flujo queda funcionalmente verificado para **operación controlada con inscripciones activas**, planes completos y vigentes, cupos/horarios compatibles y las autoridades ya aprobadas. La instalación y las pruebas no equivalen a autorización para trasladar deportistas reales en esta entrega.

Se mantienen estas limitaciones explícitas:

1. Suspendidas, reservas abiertas y altas futuras no se ejecutan; no hay política aprobada para transferirlas o anticiparlas.
2. No se ejecutan cambios el día del ingreso ni fechas retroactivas/futuras: se conserva la integridad temporal existente.
3. Permanecer en el nivel anterior exige excepción vigente; el caso parcial se probó mediante el servicio interno existente. La nueva pantalla no ofrece autorización de excepciones ni debe presumirla.
4. No hay cierre institucional automático. Se informa la evaluación de cierre; pendientes y excepciones abiertas lo impiden.
5. La API real se verificó en proceso con Django/DRF y PostgreSQL, no mediante una sesión nueva de navegador. React se verificó automáticamente con API simulada: no se comprobó visualmente CSS/responsividad ni la configuración de servidores/proxy Vite en ejecución. Las pruebas no acreditan credenciales de inicio de sesión reales.

Para revisión visual posterior **sin escrituras reales**, con una sesión ya abierta: consultar ambas rutas según el rol, abrir la progresión rechazada, comprobar estado, advertencias e historiales vacíos y verificar que la inscripción 18 sigue activa. No crear revisiones ni confirmar reubicaciones. Los ensayos visuales de ejecución deberán hacerse en un entorno aislado con datos ficticios.

**Punto de parada:** no se inicia desarrollo de sesiones docentes ni ninguna operación deportiva sobre la base real.
