# Aplicación y verificación de migraciones — Fase 2

Fecha: 28 de octubre de 2026, America/Bogota. Autorización expresa del propietario limitada a cuatro migraciones.

## Destino y revisión previa

Se verificaron tanto ENGINE/NAME de la configuración como SELECT current_database(): PostgreSQL / zona_bloque. No se imprimió .env, usuarios de conexión, contraseñas ni datos de personas.

Antes de aplicar, las cuatro migraciones estaban pendientes. El plan contenía exclusivamente las autorizadas. Se revisaron los archivos y las operaciones: CreateModel, AddConstraint y la carga explícita de Escalada/niveles; sin eliminaciones, cambios de columnas existentes, SQL arbitrario ni dependencias nuevas pendientes.

## Copia de seguridad previa

- Archivo privado: respaldos/zona_bloque_antes_fase2_20261028T135728Z.dump
- Formato PostgreSQL custom, generado con pg_dump 17.
- Tamaño: 34.475 bytes.
- SHA-256: 204ff1d0585c287a845e97f0c35b1aa678bd1618e7b1786d89cd74a054c296e6
- pg_restore --list leyó correctamente el catálogo. No se restauró ni se abrió otra base.
- Respaldo y manifiesto permanecen excluidos de Git bajo respaldos/.
- La contraseña se transmitió solamente en el entorno del proceso hijo, nunca en argumentos, salidas o archivos de texto.

## Migraciones aplicadas

| Migración | Resultado |
|---|---|
| auditoria.0001_initial | Aplicada y registrada |
| cuentas.0003_solicitudrestablecimiento | Aplicada y registrada |
| organizacion.0001_initial | Aplicada y registrada |
| organizacion.0002_catalogos_iniciales | Aplicada y registrada |

La ejecución utilizó MigrationExecutor con destinos explícitos, validación exacta del plan y una transacción global. La diferencia entre el registro previo y el posterior coincide exactamente con las cuatro aprobadas. migrate --plan posterior: No planned migration operations. Se completó el cierre estándar de Django: ocho tipos de contenido y 32 permisos de modelo verificados, sin asignarlos a usuarios o grupos.

## Tablas creadas

1. auditoria_cambioadministrativo
2. cuentas_solicitudrestablecimiento
3. organizacion_disciplina
4. organizacion_nivel
5. organizacion_periodo
6. organizacion_grupo
7. organizacion_asignacion
8. organizacion_horario

Se verificó Escalada y los cinco niveles solicitados. No se agregaron contenidos curriculares, estudiantes, evaluaciones, sesiones ni asistencias.

## Pruebas posteriores

| Comprobación | Resultado |
|---|---|
| Integración real PostgreSQL / zona_bloque | 88 comprobaciones aprobadas |
| Backend completo, SQLite en memoria | 73/73 aprobadas |
| Frontend Vitest | 24/24 aprobadas |
| Cliente HTTP con Node | 6/6 aprobadas |
| npm run build | Aprobado |
| Django check --database default | Sin incidencias |
| makemigrations --check --dry-run | No changes detected |
| showmigrations | Cuatro aprobadas marcadas X |
| migrate --plan | Sin operaciones pendientes |
| npm audit | Reintentado; falló la conexión con registry.npmjs.org |

La integración usó la API Django/DRF real, CSRF y sesiones sobre zona_bloque. Creó únicamente cuentas, periodo, grupos, horarios y asignaciones ficticios dentro de una transacción revertida al terminar. Se comprobó que no quedaron usuarios ni grupos de prueba. Los contadores de secuencia PostgreSQL pueden avanzar aunque se reviertan filas.

Se verificaron: alta/búsqueda/edición de usuarios, auditoría, catálogos, grupos, asignaciones, duplicados y cruces docentes, ámbitos de profesor/coordinador, rechazo de accesos ajenos, calendario, restricción de cupo en PostgreSQL, recuperación con reautenticación/token de un solo uso, revocación por contraseña y estado, fin de asignación y logout.

Las 88 comprobaciones incluyen preparación/verificación de CSRF y aserciones de integración; no son 88 casos unitarios independientes. No se ejecutó una prueba de carga ni de concurrencia simultánea.

## Incidencias y límites

- Primera ejecución del script de integración: el rechazo de DELETE se comprobaba sin CSRF y devolvía correctamente 403 antes de evaluar el método. Se corrigió el script para enviar CSRF y comprobar 405. No requirió cambiar código de aplicación; su transacción se revirtió.
- Al comprobar la repetición del script, su guarda rechazó un plan que incluía un destino intermedio ya aplicado. Se ajustaron los destinos a la última migración aprobada por app; la guarda evitó cualquier reversión y la repetición posterior no modificó el esquema. La primera aplicación de las cuatro migraciones ya había concluido correctamente.
- npm audit sigue sin resultado por conectividad. No se afirma ausencia de vulnerabilidades.
- El lanzador .venv-local apunta a un Python base inaccesible desde el entorno del agente. Se reutilizaron sus paquetes con el ejecutor Python alternativo ya documentado, sin modificar el entorno ni instalar globalmente.
- El puerto 5173 ya estaba ocupado por el frontend de Zona de Bloque. Se conservó ese servicio y se verificó su respuesta; no se detuvo.
- No se detectaron errores funcionales en las verificaciones aprobadas.

## Scripts y reproducción

Archivos añadidos:

- scripts/aplicar_migraciones_fase2.py: guardas de destino, revisión de plan, respaldo privado y aplicación exclusiva del conjunto autorizado. No se ejecuta al arrancar la aplicación.
- scripts/verificar_integracion_postgres_fase2.py: integración con datos ficticios y rollback.

Desde la raíz, utilizando .venv-local cuando su ejecutable esté disponible:

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py showmigrations auditoria cuentas organizacion
& .\.venv-local\Scripts\python.exe scripts/django_local.py migrate --plan
& .\.venv-local\Scripts\python.exe scripts/django_local.py shell -c "import runpy; runpy.run_path('scripts/verificar_integracion_postgres_fase2.py', run_name='__main__')"
```

En este entorno se usó como intérprete alternativo:
C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe

## Direcciones comprobadas

- Frontend/login: http://127.0.0.1:5173/ingresar — HTTP 200.
- Backend: http://127.0.0.1:8000/api/autenticacion/sesion/ — HTTP 403 sin sesión, esperado.
- Proxy frontend/API: http://127.0.0.1:5173/api/autenticacion/sesion/ — HTTP 403 sin sesión, esperado.
- Administrador: /administracion/usuarios, /administracion/catalogos, /administracion/grupos, /administracion/asignaciones y /administracion/calendario.
- Profesor: /profesor/grupos, /profesor/asignaciones y /profesor/calendario.
- Coordinador: /coordinacion/grupos, /coordinacion/profesores, /coordinacion/asignaciones y /coordinacion/calendario.

Entrar con una cuenta existente y su rol correspondiente. Los datos ficticios de integración no se conservaron ni se publicaron credenciales de demostración.

No hubo commits, push, publicaciones ni avance a Fase 3. No se modificaron otras bases, .env, antigravity-app o documentos originales.
