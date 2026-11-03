# Etapa 4, Incremento B: API REST de sesiones docentes

Base: `0a96efb`, rama `funcionalidad-sesiones-asistencia`. Se reutilizan sin
reconstrucción los modelos, la migración y los comandos del Incremento A.
No se añaden migraciones, tablas, interfaz React ni APIs de asistencia.

## Rutas y contrato

Todas las rutas usan sesión Django, CSRF y el formato vigente de errores
`detalle` y, cuando corresponde, `errores`. Listas paginadas según DRF.
El identificador de detalle es el ID numérico existente; UUID también se devuelve.

| Método | Ruta | Comportamiento |
| --- | --- | --- |
| GET | `/api/sesiones/` | Lista dentro del ámbito efectivo; filtro opcional `grupo` |
| POST | `/api/sesiones/` | Crear con `clave`, `grupo`, `fecha`, `hora_inicio`, `hora_fin`; `profesor` opcional, por defecto el actor |
| GET | `/api/sesiones/{id}/` | Consulta con revisiones del plan y sus tareas |
| PATCH | `/api/sesiones/{id}/` | Crear revisión completa del plan con `clave`, `version`, `objetivo`, `tareas` y referencias curriculares opcionales |
| POST | `/api/sesiones/{id}/cancelar/` | Cancelar con `clave`, `version`, `motivo` |
| POST | `/api/sesiones/{id}/realizar/` | Reservada, devuelve 403 para objeto visible hasta completar autorización funcional |
| GET | `/api/sesiones/grupos/` | Grupos activos de período activo disponibles al actor; datos mínimos |

PATCH edita la planificación pedagógica creando una revisión, incluso aunque
el método se llame PATCH: requiere el plan completo. No cambia fecha, franja,
grupo, profesor ni padrón. La reprogramación permanece pendiente del comando
de dominio descrito en A; no se eluden sus invariantes con `serializer.save()`.
No hay PUT, DELETE, cambios directos de estado ni endpoint de comandos arbitrarios.

Cada tarea requiere `fase` (`inicial`, `central`, `final`), `minutos` e
`instrucciones`; admite `ejercicio_version_id`. El plan admite
`malla_version_id` y `clase_id`. Se conserva la validación del servicio de
aprobación, disciplina, nivel, duración y pertenencia a la versión curricular.
Además se comprueba visibilidad de malla/ejercicio con los permisos efectivos
de recursos, sin abrir un catálogo paralelo.

Se rechazan campos desconocidos en todos los niveles, listas o escalares como
objeto raíz, actor o timestamps enviados por cliente, y estados/asistencia
enviados directamente. La franja usa minutos completos locales de
America/Bogota sin offset. El servidor fija actor, versión y evento.
No se devuelven padrón, identidades personales de inscritos ni eventos internos.

## Permisos y concurrencia

Se consulta la cuenta activa en base de datos y se evalúan pertenencias de rol
vigentes, sin usar exclusivamente el rol principal ni guardar resultados en
caché. Administrador o coordinador único activo conservan ámbito institucional.
Una cuenta con varios roles mantiene solo las facultades efectivas de cada
rol: perder administrador y conservar profesor no conserva acceso institucional.
Acudiente, deportista y routesetter por sí solos no acceden a sesiones.

El profesor solo ve y modifica sesiones donde es el profesor responsable y
existe una asignación docente del grupo que cubra tanto hoy como la fecha
de la sesión. Una asignación nueva no abre automáticamente historia previa.
La misma política se usa para crear dentro de grupos disponibles, listar,
consultar por ID y escribir. Sesión o grupo ajeno devuelve 404; falta de rol
docente/gestor o cuenta inactiva devuelve 403. Un profesor no puede crear a
nombre de otro. Los gestores pueden crear para profesores asignados usando las
validaciones de dominio existentes.

Se revalida ámbito tras bloquear usuarios dentro de la transacción de escritura;
el comando vuelve a verificar autoridad y bloquea grupo/sesión en el orden de A.
Las revocaciones que usan los servicios institucionales y bloqueos de usuario
existentes se serializan con estas escrituras. No se ofrece garantía ante SQL
administrativo que omita esos bloqueos.

Claves UUID y versiones son obligatorias para escribir. Reintento idéntico no
duplica sesión/revisión/evento; clave reutilizada con otro contenido y versión
obsoleta devuelven 409. El reintento revalida facultades. Crear devuelve 201
también en reintentos; PATCH/cancelar devuelven 200 y la sesión actual, conforme
al comportamiento del comando de A. Errores de validación del modelo se
convierten a 400 sin exponer una excepción interna. CSRF se exige a escrituras
con sesión real; no se incorporan autenticación alternativa ni exenciones.

## Transiciones y límites de este incremento

Se habilita planificada → cancelada. Las revisiones solo se admiten mientras
la sesión está planificada. La ejecución HTTP sigue bloqueada por el requisito
expreso de autorización funcional de actividades documentado en A. No basta
la aprobación curricular o del ejercicio para habilitar práctica segura.
La ruta reservada verifica primero ámbito: una sesión ajena sigue siendo 404.
Confirmación/corrección de asistencia, ejecución real y seguimiento conservan
sus servicios internos, sin publicación HTTP en este incremento.

Antes de habilitar ejecución, completar el contrato funcional y sus pruebas;
antes de editar calendario, añadir reprogramación auditable y decisión de padrón.
El siguiente incremento debe reutilizar estos permisos y rutas sin abrir
acceso genérico mediante un ModelViewSet con escrituras directas.

## Archivos

- `backend/sesiones/permisos.py`: acceso efectivo, ámbito de sesiones y grupos.
- `backend/sesiones/serializers.py`: entradas estrictas y respuestas mínimas.
- `backend/sesiones/views.py`: rutas de consulta y adaptadores de comandos.
- `backend/sesiones/urls.py` y `backend/configuracion/urls.py`: registro de rutas.
- `backend/sesiones/test_api.py`: autorización, revocaciones, roles múltiples,
  CSRF, errores, idempotencia y concurrencia HTTP en PostgreSQL real.
- Este informe. Modelos, servicios y migraciones de A permanecen intactos.

## Validación aislada

Se usa el ejecutor temporal del repositorio, Python 3.12.14 del runtime y las
dependencias existentes indicadas en el informe A, mediante
`ZDB_PAQUETES_PYTHON`. No se instalan paquetes ni se usa la base operativa.

```powershell
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --etiqueta sesiones --etiqueta cuentas.tests.test_acceso --failfast --verbosity 1
```

La prueba concurrente HTTP usa conexiones distintas y una barrera: dos PATCH
con la misma versión y claves diferentes producen 200 y 409; queda una sola
revisión y un solo evento. Se conservan las pruebas concurrentes de dominio
para límite diario y reintento simultáneo del Incremento A.

Primera ejecución: 28 pruebas de sesiones aprobadas, chequeo de migraciones sin
diferencias, clúster detenido; evidencia privada en
`respaldos/pruebas_etapa1_m9t6pcwl/`. La ejecución final añade revocación durante
entrada/comando, coordinador, pérdida de rol gestor y validación complementaria.
Resultado final: **50 pruebas aprobadas** en 9,597 segundos (31 de sesiones y
19 de acceso/autenticación). `makemigrations --check --dry-run` sin diferencias,
system check sin incidencias y clúster detenido. Evidencia privada en
`respaldos/pruebas_etapa1_fiff5cgj/resultado.json` y logs del mismo directorio.
No se repite la suite general de etapas previas; la selección cubre el dominio
afectado y el mecanismo de sesión/CSRF reutilizado. `git diff --check` sin errores.

Sin cambios a `main`, sin push. El script privado
`scripts/ensayo_copia_restaurada.py` permanece fuera del commit y debe conservarse.
SHA-256 verificado sin cambios respecto a A:
`DFA5CA6798DC3FA87C0053007316A97DAEF070F32CF42AC1D43737D00063B315`.
