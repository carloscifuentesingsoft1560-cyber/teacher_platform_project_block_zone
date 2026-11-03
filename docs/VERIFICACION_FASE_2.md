# Estado actualizado — 28 de octubre de 2026

Las cuatro migraciones fueron aprobadas, respaldadas y aplicadas en PostgreSQL zona_bloque. Integración real: 88 comprobaciones aprobadas; backend 73/73, frontend 24/24 y build aprobado. npm audit sigue bloqueado por conectividad. Consulta [el informe actual](APLICACION_MIGRACIONES_FASE_2.md). El contenido siguiente conserva el estado histórico previo a la autorización.

# Verificación de Fase 2

Fecha local: 27 de octubre de 2026, America/Bogota.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Pruebas backend originales | 21/21 aprobadas |
| Pruebas nuevas de usuarios/recuperación | 20/20 aprobadas |
| Pruebas nuevas de organización | 32/32 aprobadas |
| Total backend | 73/73, SQLite en memoria |
| Pruebas frontend originales | 10/10 aprobadas |
| Pruebas frontend nuevas | 14/14 aprobadas |
| Total Vitest | 24/24 aprobadas |
| Cliente HTTP con Node | 6/6 aprobadas |
| npm run build | Aprobado con cargador runner |
| Django check --database default | Sin incidencias |
| makemigrations --check --dry-run | No changes detected |
| Conexión PostgreSQL existente | Confirmada sin exponer configuración ni datos |
| Plan de migraciones PostgreSQL | Cuatro migraciones nuevas pendientes |
| SQL organizacion/0001 | Generado y revisado, no ejecutado |
| Exclusiones Git | Siete rutas privadas comprobadas con Git, incluidos ambos Excel y ambos entornos |
| Navegador Edge, API ficticia | Diez vistas sin errores JavaScript ni desbordamiento horizontal |
| npm audit | Ejecutado; no pudo comunicarse con el registro |
| Migraciones reales de Fase 2 | No aplicadas |
| Pruebas de integración/concurrencia en PostgreSQL de Fase 2 | Pendientes de aprobación y aplicación del esquema |

## Alcance de las pruebas

Backend: altas/modificaciones, roles y banderas técnicas, desactivación, protección de cuentas, auditoría sin secretos, CSRF, reautenticación de recuperación, token de un uso, caducidad, revocación de enlaces, revocación de sesiones, cuentas inactivas, catálogos, cupos, nivel/disciplina, fechas, horarios, duplicados, cruces de profesores, coordinación simultánea, ámbitos, asignaciones futuras/finalizadas, cierre por fin de periodo y rollback de horarios inválidos.

Frontend: crear/buscar/editar/desactivar usuarios, cancelar confirmaciones, solicitar enlaces, crear disciplina, consultar niveles/periodos, crear grupo y asignación, consultar grupos y horarios como profesor, profesores/calendario como coordinador, rechazar rutas de otro rol, mostrar errores y consumir un enlace de recuperación.

Navegador: grupos/detalle del profesor, profesores del coordinador y formulario administrativo de usuarios a 390, 768 y 1366 px; además login móvil. Usa interceptación estricta de /api/ con datos ficticios y rechaza escrituras. No es una prueba de integración con PostgreSQL ni una evaluación completa de accesibilidad/contraste.

## Entorno y comandos reales

.venv-local existe y contiene Django 5.2.18 y DRF 3.18.3. Su ejecutable apunta a Python 3.13, que devolvió acceso denegado desde el entorno del agente. Se usó el Python 3.12.14 disponible con scripts/django_local.py, que carga los paquetes del entorno existente sin modificarlo. Para libpq se usó psycopg en modo Python; no se instalaron dependencias globales.

```powershell
$pythonVerificacion = 'C:\Users\57310\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonVerificacion scripts/django_local.py test cuentas organizacion --settings=configuracion.settings_pruebas
& $pythonVerificacion scripts/django_local.py makemigrations --check --dry-run --settings=configuracion.settings_pruebas
& $pythonVerificacion scripts/django_local.py check --database default
& $pythonVerificacion scripts/django_local.py migrate --plan
& $pythonVerificacion scripts/django_local.py sqlmigrate organizacion 0001
node --test frontend/pruebas/cliente.node.mjs
```

En frontend:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd audit --json --cache ../.npm-cache
```

La carga por defecto de configuración Vite fallaba al inspeccionar directorios ancestros restringidos. --configLoader runner resolvió la ejecución sin alterar el login ni instalar dependencias.

## Verificación de navegador reproducible

El entorno de herramientas ya dispone de Playwright; no se añadió como dependencia global ni se instaló otro navegador. Se inició un Vite temporal en 5176:

```powershell
# En frontend, durante la comprobación:
npm.cmd run dev -- --port 5176
```

Desde la raíz, con las rutas de herramientas disponibles en este equipo:

```powershell
$env:ZDB_PLAYWRIGHT = 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
$env:ZDB_NAVEGADOR = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
node frontend/pruebas/navegador.cjs
```

El script admite ZDB_FRONTEND_URL para otra dirección. La primera ejecución de esta comprobación tuvo un error en el patrón de interceptación (también interceptaba el módulo src/api/cliente.js); se corrigió para interceptar únicamente rutas que comienzan por /api/. La ejecución corregida aprobó las diez vistas.

## Privacidad y límites

No se mostró ni copió .env. No se ejecutaron consultas de datos personales de producción. No se modificaron bases de otros proyectos, cuentas PostgreSQL, referencias ni antigravity-app. No se hicieron commits ni push.

La raíz continúa sin repositorio Git. La verificación de patrones usó un repositorio efímero aislado dentro del proyecto y lo retiró al terminar; no hay un índice real que permita comprobar archivos ya versionados. .gitignore no retira archivos de un índice existente.

npm audit sigue pendiente por conectividad; no se afirma que las dependencias estén libres de vulnerabilidades. Tampoco se afirma que los módulos nuevos estén operativos en PostgreSQL hasta recibir aprobación, migrar y probarlos.
