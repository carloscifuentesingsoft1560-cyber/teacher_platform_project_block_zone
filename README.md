# Zona de Bloque | Gestión Deportiva y Pedagógica

**Estado de la rama `desarrollo-zona-de-bloque`: Etapas 2 y 3 en integración aislada.** Currículo versionado, biblioteca y materiales privados se describen en el [informe de Etapa 3](docs/IMPLEMENTACION_ETAPA_3_CURRICULO_BIBLIOTECA.md). La base operativa y el proyecto original no se modificaron. El arranque operativo sigue bloqueado; las migraciones se ensayan exclusivamente con el ejecutor PostgreSQL temporal.

La copia Git íntegra se utiliza con directorio Git explícito, sin sustituir el repositorio anterior. Revisar [publicación propuesta](docs/PUBLICACION_PROPUESTA_ETAPAS_2_3.md) e [inventario exacto](docs/INVENTARIO_PUBLICACION_ETAPAS_2_3.md). **No hay push ni despliegue autorizados.** Los contenidos originales/candidatos requieren revisión institucional independiente; pasar pruebas no los aprueba.

## Notas históricas de las entregas anteriores

> **Integración aislada de Etapa 2.** Esta carpeta implementa identidad acreditada, roles múltiples, coordinador institucional único y formalización administrativa de ascensos. No se aplicó al proyecto original ni a su base. El perfil normal de ejecución está bloqueado en esta rama; usar únicamente el ejecutor PostgreSQL temporal. Consultar [informe de implementación](docs/IMPLEMENTACION_ETAPA_2_NUCLEO.md) y [archivos de la entrega](docs/ARCHIVOS_ETAPA_2.md). La recuperación del historial Git es parcial: falta un objeto histórico y no está lista para publicar. Las notas de Etapa 1 siguientes se conservan como historia de la copia de origen.

> **Estado vigente — Etapa 1, 2 de noviembre de 2026.** Esta entrega estabiliza pruebas y documentación; conserva el comportamiento institucional. Roles múltiples y separación de formalización de ascensos están diseñados, pendientes de implementación. No se modificó la base operativa. Las cifras y comandos del cuerpo anterior se conservan como historial; para la suite completa usar [PostgreSQL temporal aislado](docs/PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md), con runtime Python ejecutable y sin generar migraciones. Resultado de esta entrega: 505 pruebas backend, 5 de infraestructura, 150 frontend, 6 HTTP y build aprobados.
>
> Consultar [informe y archivos modificados](docs/INFORME_ETAPA_1_ESTABILIZACION.md), [reconciliación y línea base](docs/RECONCILIACION_VIGENTE_2026_11.md), [contratos futuros](docs/CONTRATOS_COMPARTIDOS_FUTUROS.md) y [propuesta de Etapa 2](docs/PROPUESTA_ETAPA_2_NUCLEO_INSTITUCIONAL.md). La carpeta sigue sin repositorio Git: se preservó un snapshot fuente previo, sin sincronizar con el remoto.

Django/DRF + PostgreSQL y React/JavaScript/Vite/Sass. Autenticación por sesiones, cookies HttpOnly y CSRF.

**Fase 1 verificada funcionalmente. Fase 2 migrada y verificada en PostgreSQL zona_bloque el 28 de octubre de 2026.** Fase 3 (deportistas e inscripciones) aplicada y verificada en zona_bloque con autorización y respaldo; verificación visual conjunta pendiente. No se desarrollaron sesiones, asistencia ni valoraciones.

## Coordinación única y tablero administrativo implementados

La estructura inicial será un administrador principal, un único coordinador activo para todos los profesores y varios profesores con sus grupos. El coordinador gestionará grupos, horarios y asignaciones de toda la empresa. Administración conservará usuarios, configuración, seguridad y reportes, con un tablero general de estadísticas reales de profesores, grupos, coordinador, periodos y asignaciones. El profesor seguirá limitado a sus grupos y actividades.

Se reutilizan Usuario y la auditoría para el titular y sus relevos. El backend valida un único coordinador activo y el relevo se confirma con historial transaccional. La restricción adicional de base cuentas.0004_usuario_un_coordinador_activo fue autorizada y aplicada en PostgreSQL zona_bloque; su índice único quedó verificado.

La ampliación autorizada incluye gestión coordinadora de profesores/grupos/horarios/asignaciones y un tablero con datos reales. Se conserva el diseño visual y el login. [Resultados actuales](docs/VERIFICACION_COORDINACION_TABLERO.md) y [migración aplicada y verificada](docs/APLICACION_COORDINADOR_UNICO.md).

- [Matriz de permisos objetivo](docs/MATRIZ_PERMISOS.md)
- [Propuesta técnica y dependencias de coordinación](docs/AMPLIACION_COORDINACION.md)
- [Plan de los tres tableros e indicadores](docs/PLAN_TABLEROS.md)

## Estado comprobado

- Backend actual: 271 pruebas aprobadas en PostgreSQL temporal aislado, incluidas doce de concurrencia. Los resultados anteriores se conservan en los informes históricos.
- Frontend actual: 88 pruebas aprobadas. Propuestas: nueve recorridos de navegador aislados aprobados; los 18 de selectores/cupos se conservan como evidencia del incremento anterior.
- Cliente HTTP: 6 pruebas aprobadas.
- Build Vite aprobado.
- Migraciones de Fase 2, cuentas.0004, las dos iniciales de Fase 3 y deportistas.0002/0003 aplicadas con autorización. Cero pendientes. Las columnas y registros preexistentes de las 31 tablas conservan conteos y huellas; el vínculo 3 sigue pendiente, sin acreditación automática.
- Verificación posterior de coordinador único: 21 comprobaciones PostgreSQL, dos rechazos concurrentes y datos existentes intactos. [Informe](docs/APLICACION_COORDINADOR_UNICO.md).
- Integración histórica de Fase 2: 88 comprobaciones aprobadas. En esta ampliación se verificó el resumen sobre PostgreSQL en transacción de solo lectura; no se modificó al coordinador real.
- Fase 3: 18 vistas/formularios de navegador con API ficticia a 390/768/1366 px. Las 22 verificaciones de Fase 2 se conservan como evidencia histórica.
- npm audit ejecutado pero sin respuesta del registro: resultado pendiente.

Consulta [cierre de Fase 1](docs/CIERRE_FASE_1.md), [verificación de Fase 2](docs/VERIFICACION_FASE_2.md) y [migraciones aplicadas](docs/APLICACION_MIGRACIONES_FASE_2.md).

## Fase 3 aplicada, verificación visual pendiente

Deportistas, acudientes, autorizaciones, inscripciones múltiples, reservas con vencimiento y propuestas docentes. [Detalle de implementación](docs/IMPLEMENTACION_FASE_3.md) e [informe de aplicación y respaldo](docs/APLICACION_MIGRACIONES_FASE_3.md). Identificación documental y comprobaciones de facultades están migradas con autorización, respaldo y restauración aislada. Las APIs autorizadas de fichas, vínculos, autorizaciones y paneles responden 200. [Aplicación de facultades y cierre actual](docs/APLICACION_COMPROBACION_FACULTADES.md).

## Funcionalidades implementadas

Incremento operativo 1: propuestas hacia destinos institucionales compatibles de otros profesores/jornadas mediante información mínima. Se rechazan destinos inválidos antes de guardar y se revalida al aprobar. Las promociones con varias inscripciones efectivas de la disciplina quedan bloqueadas hasta el Incremento 2. No se implementan cupos por sesión ni planes individuales. [Contrato, permisos, pruebas y criterios visuales](docs/AJUSTES_PROPUESTAS_TRASLADOS.md).

Deportistas permite filtrar por nombres de grupo, periodo, disciplina y nivel mediante selectores buscables. Inscripciones consulta capacidad, plazas activas, reservas vigentes y disponibilidad al elegir un grupo por código/nombre/periodo. Se conservan IDs, permisos y diseño. [Cambios y verificación de selectores/cupos](docs/MEJORA_SELECTORES_CUPOS.md).

La comprobación de facultades de acudientes incorpora evidencia privada, método, resultado, alcance/version, responsable, fechas e historial inmutable. **Su migración real fue aplicada y verificada con autorización**. Las APIs ya no tienen el 503 temporal de esquema pendiente. No se crearon comprobaciones ni se acreditaron autorizaciones anteriores automáticamente. El vínculo 3 sigue pendiente para revisión humana, no para confirmación vacía. [Aplicación, respaldo, pruebas y conservación](docs/APLICACION_COMPROBACION_FACULTADES.md).

Administrador: crear, buscar y editar usuarios, roles y estados; restablecer acceso mediante reautenticación y enlace de un solo uso; gestionar disciplinas, niveles, periodos, grupos, horarios y asignaciones.

Profesor: consultar solo sus grupos/asignaciones vigentes, horarios e información general; calendario inicial.

Coordinador: toda la plantilla, grupos, horarios, calendario e historial de asignaciones; escrituras operativas autorizadas sin administración de cuentas, roles o seguridad.

Se conservan los títulos, login y estilo de los paneles. Las pantallas de gestión añaden controles legibles, confirmaciones, errores por campo, paginación y navegación adaptable.

Las cuatro migraciones de la base Fase 2 y la migración adicional de coordinador único están aplicadas. La garantía del índice fue comprobada en PostgreSQL.

## Estructura

- backend/cuentas/: usuario, sesiones y recuperación segura.
- backend/organizacion/: catálogos, grupos, horarios, asignaciones, alcance y calendario.
- backend/auditoria/: cambios administrativos sin credenciales ni valores sensibles.
- backend/paneles/ y backend/comun/: paneles iniciales, errores y respuestas privadas.
- frontend/src/paginas/: pantallas por rol.
- frontend/src/componentes/: marca, navegación, campos y listados reutilizables.
- frontend/src/estilos/: tokens institucionales y estilos Sass.
- scripts/django_local.py: ejecutor que utiliza los paquetes .venv-local existentes.
- docs/: arquitectura, requisitos, decisiones y verificaciones.

## Inicio local

Trabajar desde la raíz del proyecto. **Usar .venv-local; no recrearlo ni instalar dependencias globales.** .env ya existe: no mostrarlo, copiarlo ni reemplazarlo. La configuración se lee internamente desde ese archivo; .env.example contiene únicamente la plantilla.

### Comprobar el esquema aplicado

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py check --database default
& .\.venv-local\Scripts\python.exe scripts/django_local.py migrate --plan
```

El plan actual no muestra migraciones pendientes. No repetir la aplicación de deportistas.0002_identificacion_documental ni deportistas.0003_comprobacion_facultades. Consulta [el cierre de facultades](docs/APLICACION_COMPROBACION_FACULTADES.md) y [el informe documental anterior](docs/APLICACION_IDENTIFICACION_DOCUMENTAL.md).

### Backend

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py runserver 127.0.0.1:8000
```

En el entorno restringido del agente, el lanzador .venv-local no pudo acceder a su Python base. Se verificó esta alternativa, que reutiliza sus paquetes sin alterar el entorno:

```powershell
$pythonLocal = 'C:\Users\57310\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonLocal scripts/django_local.py check --database default
& $pythonLocal scripts/django_local.py runserver 127.0.0.1:8000
```

La alternativa usa paquetes puros compatibles y psycopg/libpq en modo Python. No modifica el Python del sistema ni el entorno existente. Preferir el ejecutable .venv-local cuando esté disponible.

### Frontend, otra terminal

```powershell
Set-Location frontend
npm.cmd run dev
```

Abrir http://127.0.0.1:5173 usando siempre el mismo hostname. Vite reenvía /api al backend; no se habilita CORS abierto. Los scripts usan --configLoader runner para evitar la inspección de directorios ancestros restringidos.

Las dependencias locales ya existen. Si fuera necesario restaurarlas en otra máquina con acceso al registro, usar npm.cmd ci --cache ../.npm-cache en frontend y pip del entorno .venv-local con backend/requirements.txt. No instalar globalmente.

## Pruebas sin modificar PostgreSQL

Desde la raíz:

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py test cuentas organizacion paneles deportistas inscripciones --settings=configuracion.settings_pruebas
& .\.venv-local\Scripts\python.exe scripts/django_local.py makemigrations --check --dry-run --settings=configuracion.settings_pruebas
node --test frontend/pruebas/cliente.node.mjs
```

En frontend:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd audit --cache ../.npm-cache
```

La suite actual tiene 271 pruebas backend y 88 frontend, aprobadas tras el Incremento 1 de propuestas/traslados, sin nuevas migraciones. Para PostgreSQL completamente aislado, ejecutar scripts/pruebas_postgresql_aisladas.py con el Python local. No ejecutar fixtures históricos contra zona_bloque. Los nueve recorridos de navegador de propuestas utilizan API simulada. Las 32 tablas reales conservan conteos y huellas; las consultas GET de propuestas, destinos y paneles se comprobaron sin escribir registros. La revisión visual conjunta queda pendiente. npm audit conserva su limitación anterior de conectividad con el registro.

## Datos iniciales y prueba manual

La migración de catálogos añadió Escalada y Lúdico, Nivel 1, Nivel 2, Escuela de especialización semicompetitiva y Alto rendimiento. No crea periodos, grupos, usuarios, estudiantes ni contenidos curriculares.

Con las migraciones aplicadas, ingresar con la cuenta administrativa existente, crear un periodo y un grupo, crear cuentas ficticias de profesor/coordinador y asignarlas con fechas. Los recorridos y rutas se detallan en [FASE_2.md](docs/FASE_2.md).

La recuperación exige contraseña actual del administrador; el destinatario escoge su nueva clave mediante un enlace válido durante 30 minutos. No se envían correos ni mensajes reales. Las escrituras de usuarios se centralizan en React/API; la consola Django queda de consulta. El cargo e historial se gestionan en /administracion/coordinacion. La cuenta saliente se desactiva y el relevo se revierte si el entrante tiene asignaciones incompatibles.

## Privacidad

.gitignore excluye .env, .venv, .venv-local, archivos privados, respaldos, bases locales y todas las referencias salvo el prompt maestro. Los siete casos comprobados incluyen ambos Excel originales.

La raíz no tiene repositorio Git: no se realizaron commits, push ni cambios remotos. No se modificaron antigravity-app ni los documentos originales. No se incorporan datos personales en fixtures.

## Documentación

- [Verificación de coordinación y tablero](docs/VERIFICACION_COORDINACION_TABLERO.md)
- [Plan pendiente del índice único](docs/MIGRACION_COORDINADOR_UNICO.md)
- [Arquitectura](docs/ARQUITECTURA.md)
- [Requisitos](docs/REQUISITOS.md)
- [Decisiones](docs/DECISIONES.md)
- [Fase 2: modelos, API, permisos y pantallas](docs/FASE_2.md)
- [Migraciones aplicadas y respaldo](docs/APLICACION_MIGRACIONES_FASE_2.md)
- [Resultados de verificación](docs/VERIFICACION_FASE_2.md)
- [Referencia de importación futura](docs/IMPORTACION_EXCEL.md)
