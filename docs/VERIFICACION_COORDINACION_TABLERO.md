> Estado vigente, 28 de octubre de 2026: cuentas.0004_usuario_un_coordinador_activo fue autorizada y aplicada exclusivamente en zona_bloque, con respaldo integral verificado. Índice válido, sin migraciones pendientes, 21 comprobaciones PostgreSQL y dos rechazos concurrentes aprobados; datos existentes intactos. [Informe de aplicación](APLICACION_COORDINADOR_UNICO.md). Las referencias a migración pendiente o integración aún no ejecutada del documento siguiente describen el estado anterior a esta aplicación.

# Ampliación de coordinación y tablero administrativo

Fecha: 28 de octubre de 2026. Implementación autorizada por el propietario. **No se aplicó ninguna migración nueva en PostgreSQL.**

## Funcionalidades implementadas

- Unicidad de coordinador activo en servicio administrativo y mediante una restricción de modelo/migración pendiente de aplicar.
- Creación/activación de una segunda cuenta coordinadora rechazada; cuentas históricas inactivas permitidas.
- Relevo administrativo transaccional con verificación del titular esperado, para evitar sobrescribir un relevo concurrente ya realizado.
- Eventos coordinacion_fin y coordinacion_inicio con usuario afectado, fecha y administrador autorizante; sin borrar cuentas.
- La cuenta saliente se desactiva. No se cambia automáticamente a profesor ni se borran asignaciones incompatibles del entrante: el servicio rechaza ese cambio y revierte el relevo.
- Comprobación de identidad vigente del coordinador, incluso frente a una referencia en caché anterior al relevo.
- Historial del cargo visible solo a administración; conserva usuarios que posteriormente cambien de rol.
- Coordinador con toda la plantilla docente, incluidos profesores sin grupo e inactivos, y sus grupos/horarios vigentes.
- Gestión de grupos, horarios y asignaciones docentes con permisos por operación, auditoría y revalidación transaccional.
- Consulta de calendario institucional e historial docente, sin necesidad de asignaciones de coordinador por grupo.
- Usuarios, credenciales, roles, seguridad y escritura de catálogos permanecen administrativos.
- Tablero general del administrador y resumen operativo del coordinador, con datos reales y filtros.
- Profesor limitado a grupos propios, sin indicadores ni acciones institucionales.

No se crearon tablas nuevas, jerarquías, supervisiones por profesor, estudiantes, sesiones, asistencia o valoraciones.

## Estadísticas y filtros

Se calculan desde Usuario, Grupo, Periodo, Asignacion, Disciplina y Nivel:
- Profesores activos/inactivos y activos sin grupo operativo.
- Coordinador actual o vacante; no se selecciona arbitrariamente un titular si hay inconsistencias anteriores a la restricción.
- Grupos activos/inactivos.
- Periodos totales, activos y en curso.
- Asignaciones docentes vigentes y operativas.
- Resumen de grupos por disciplina y nivel, incluidos catálogos con cero grupos.

Filtros: fecha de corte, periodo, disciplina y nivel. El estado de cuentas y grupos es el actual, no una reconstrucción histórica de esos estados. La fecha de corte determina vigencias; personal activo/inactivo es institucional y se etiqueta expresamente. Los accesos a grupos, docentes sin grupo y asignaciones transportan los filtros al detalle.

No hay cifras de sesiones, asistencia, cumplimiento o valoraciones.

## API nueva y ampliada

| Ruta | Permisos |
|---|---|
| GET /api/organizacion/coordinacion/ | Administrador: titular e historial paginado |
| POST /api/organizacion/coordinacion/relevar/ | Administrador; usuario entrante y coordinador_actual esperado (ID o null) |
| GET /api/paneles/administrador/resumen/ | Administrador, alcance institucional |
| GET /api/paneles/coordinador/resumen/ | Coordinador activo único, resumen operativo |
| /api/organizacion/profesores/ | Coordinación/administración: plantilla completa, filtros y grupos/horarios mínimos |
| /api/organizacion/grupos/ | Coordinación/administración: operación autorizada; profesor: lectura propia |
| /api/organizacion/asignaciones/ | Coordinación: historial y gestión solo de tipo profesor; administración conserva compatibilidad de historial |
| /api/organizacion/calendario/ | Coordinación/administración: calendario general; profesor: propio |

Se añaden filtros de estado/rol en usuarios y filtros organizativos en grupos, profesores y asignaciones. Coordinación no utiliza /api/usuarios/ para seleccionar profesores.

El endpoint de relevo devuelve 409 si cambió el titular desde la consulta del formulario. Los intentos de cuenta/privilegio/configuración por coordinación permanecen denegados. Campos administrativos ocultos en operaciones coordinadoras se rechazan.

## Resultados reales

| Verificación | Resultado |
|---|---|
| Backend completo | 114/114 aprobadas, SQLite temporal en memoria |
| Regresión anterior | 73 casos conservados; expectativas de política actualizadas en cinco casos |
| Casos backend nuevos | 41: cargo/relevo, operación, estadísticas y reconciliación |
| Frontend | 33/33 aprobadas: 24 anteriores y 9 nuevas |
| Cliente HTTP con Node | 6/6 aprobadas |
| Build Vite | Aprobado, 59 módulos |
| Navegador, vistas anteriores | 10 aprobadas |
| Navegador, ampliación | 12 aprobadas a 390, 768 y 1366 px |
| Total navegador | 22 vistas, sin errores JS ni desbordamiento horizontal |
| Django check --database default | Sin incidencias |
| makemigrations --check --dry-run | No changes detected |
| PostgreSQL zona_bloque | Destino configurado y efectivo comprobado |
| Resumen sobre datos PostgreSQL | Verificado en transacción SET TRANSACTION READ ONLY |
| Coordinadores activos en revisión previa | 1, sin imprimir identidad ni datos de contacto |
| Plan PostgreSQL | Solo cuentas.0004_usuario_un_coordinador_activo, pendiente |
| SQL de migración | Generado en solo lectura; CREATE UNIQUE INDEX condicional |
| npm audit | Ejecutado; sin respuesta del registro por conectividad |

La comprobación PostgreSQL solo leyó datos. No se ejecutaron escrituras de integración, nuevas migraciones ni pruebas de concurrencia sobre esa base. La unicidad del índice se probó en memoria; su protección física en PostgreSQL queda pendiente de aprobación y aplicación.

Las vistas de navegador usan API interceptada y datos ficticios, y rechazan escrituras. No sustituyen integración real de escritura en PostgreSQL.

## Regresión y límites

Se conservaron los 73 casos anteriores y se adaptaron cinco expectativas que la decisión institucional cambió:
1. El caso de cambio de rol libera antes el único cargo coordinador, conservando la prueba de revocación por rol.
2. La creación de una cuenta coordinadora añade su evento de inicio; el conteo de creación de usuarios sigue siendo tres.
3. La edición de un profesor hacia coordinador registra modificación e inicio, conservando la comprobación de actor.
4. Coordinación ahora ve toda la plantilla y los grupos, en lugar de solo los compartidos.
5. Escrituras coordinadoras de grupos/asignaciones pasan a validar datos, mientras catálogos siguen devolviendo denegación.

No se eliminaron casos para ocultar regresiones. Las restricciones de profesores y la protección administrativa se mantienen y tienen pruebas nuevas.

El script histórico de integración escritora fue adaptado a la política actual y protegido: exige la migración aplicada y ausencia de un coordinador real activo. No se ejecutó ahora, porque existe un titular real y no se altera su cuenta para introducir un coordinador ficticio.

No se afirma ausencia de vulnerabilidades: npm audit no pudo contactar con registry.npmjs.org. No se midieron carreras concurrentes en PostgreSQL antes de autorizar la migración.

## Conservación visual y privacidad

Se verificó por huellas que los tres archivos Sass existentes, login, contexto de autenticación, package.json, package-lock.json y configuración Vite no cambiaron. No se añadieron dependencias. Se reutilizan tarjetas, formularios, tablas y navegación actuales.

No se mostró ni copió .env, no se tocaron Excel ni otros proyectos y no se hicieron commits o push. La raíz sigue sin repositorio Git.

## Comandos ejecutados / reproducción

Se reutilizaron las dependencias .venv-local. En este entorno su ejecutable base no es accesible, por lo que se empleó el intérprete alternativo ya documentado:

```powershell
$pythonLocal = 'C:\Users\57310\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonLocal scripts/django_local.py test cuentas organizacion paneles --settings=configuracion.settings_pruebas
& $pythonLocal scripts/django_local.py check --database default
& $pythonLocal scripts/django_local.py makemigrations --check --dry-run --settings=configuracion.settings_pruebas
& $pythonLocal scripts/django_local.py migrate --plan
& $pythonLocal scripts/django_local.py sqlmigrate cuentas 0004
node --test frontend/pruebas/cliente.node.mjs
```

En frontend: npm.cmd test, npm.cmd run build y npm.cmd audit --json --cache ../.npm-cache.

QA: frontend/pruebas/navegador.cjs y frontend/pruebas/navegador-coordinacion.cjs, con el Playwright de herramientas y Edge local. Se inició y detuvo un Vite temporal en 5176, sin detener los servicios del usuario.

## Rutas de interfaz

Tras reiniciar el backend con el código nuevo:
- /administracion: tablero general.
- /administracion/coordinacion: titular, historial y relevo.
- /administracion/usuarios, /catalogos, /grupos y /asignaciones: módulos administrativos.
- /coordinacion: resumen operativo.
- /coordinacion/profesores: plantilla completa con grupos/horarios.
- /coordinacion/grupos, /asignaciones y /calendario: gestión operativa institucional.
- /profesor: mantiene responsabilidades y consultas propias.

No se debe considerar cerrado el despliegue de la regla hasta aprobar y aplicar el índice pendiente en PostgreSQL.

## Inventario de aplicación

Rutas nuevas o modificadas respecto a la entrega documental anterior (incluye las pruebas conservadas/adaptadas):

- backend/cuentas/management/commands/crear_usuario.py
- backend/cuentas/models.py
- backend/cuentas/serializers_usuarios.py
- backend/cuentas/servicios_usuarios.py
- backend/cuentas/tests/test_acceso.py
- backend/cuentas/tests/test_usuarios.py
- backend/cuentas/views_usuarios.py
- backend/organizacion/alcance.py
- backend/organizacion/serializers.py
- backend/organizacion/servicios.py
- backend/organizacion/tests/test_organizacion.py
- backend/organizacion/urls.py
- backend/organizacion/views.py
- backend/paneles/urls.py
- frontend/src/Aplicacion.jsx
- frontend/src/componentes/Estructura.jsx
- frontend/src/paginas/Asignaciones.jsx
- frontend/src/paginas/Catalogos.jsx
- frontend/src/paginas/Grupos.jsx
- frontend/src/paginas/Panel.jsx
- frontend/src/paginas/Profesores.jsx
- frontend/src/paginas/Usuarios.jsx
- scripts/verificar_integracion_postgres_fase2.py
- backend/cuentas/coordinacion.py
- backend/cuentas/migrations/0004_usuario_un_coordinador_activo.py
- backend/cuentas/tests/test_coordinacion.py
- backend/cuentas/views_coordinacion.py
- backend/organizacion/consultas.py
- backend/organizacion/permisos.py
- backend/organizacion/tests/test_operacion_coordinador.py
- backend/paneles/resumen.py
- backend/paneles/tests/test_resumen.py
- backend/paneles/tests/__init__.py
- backend/paneles/views_resumen.py
- frontend/src/componentes/ResumenInstitucional.jsx
- frontend/src/paginas/Coordinacion.jsx
- frontend/src/pruebas/CoordinacionTablero.test.jsx
- frontend/pruebas/navegador-coordinacion.cjs

La documentación de arquitectura, matriz, requisitos, decisiones, planificación y README se actualizó para distinguir implementación de migración pendiente.
