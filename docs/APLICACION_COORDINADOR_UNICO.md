# Aplicación de coordinador único — 28 de octubre de 2026

## Resultado

Aplicada exclusivamente **cuentas.0004_usuario_un_coordinador_activo** en PostgreSQL **zona_bloque**, con autorización expresa del propietario. No quedan migraciones pendientes.

No se crearon tablas ni columnas. Se creó el índice único parcial **un_coordinador_activo** sobre cuentas_usuario.rol, condicionado a is_active y rol coordinador. PostgreSQL confirma que el índice es único, válido y listo. El registro django_migrations incorporó exclusivamente la migración autorizada, sin retirar registros.

## Comprobaciones previas y respaldo

- Destino configurado y efectivo comprobado mediante SELECT current_database(): zona_bloque.
- Historial de migraciones consistente y plan global de una sola operación pendiente.
- Revisión del objeto de migración: un único AddConstraint exactamente igual al aprobado; sin borrados, cambios de datos ni operaciones adicionales.
- Un coordinador activo antes y después.
- Nuevo respaldo privado: respaldos/zona_bloque_antes_coordinador_unico_20261028T191127Z.dump.
- Tamaño: 66 391 bytes.
- SHA-256: 3976e855909af7aa88e0a3098b9ba6ab0d8f6841fb8df177330436781ad3241a.
- pg_dump en formato custom completado; pg_restore --list y lectura/descompresión completa mediante pg_restore --file NUL completados.
- No se restauró el archivo en ninguna base. Estas verificaciones comprueban legibilidad integral del archivo; no sustituyen un ensayo independiente de restauración.
- Respaldo y manifiesto quedan excluidos mediante respaldos/ y *.dump en .gitignore. No contienen salidas públicas de datos ni credenciales.

## Conservación de información

Conteos y SHA-256 de las filas completas de todas las tablas, excepto django_migrations, idénticos antes y después de migrar y después de las pruebas PostgreSQL. Se bloquearon escrituras durante la comparación y aplicación transaccional; lecturas disponibles. No se modificaron cuentas reales para probar el relevo.

| Tabla | Filas antes | Filas después de migrar y probar |
| --- | ---: | ---: |
| cuentas_usuario | 3 | 3 |
| organizacion_grupo | 1 | 1 |
| organizacion_horario | 3 | 3 |
| organizacion_asignacion | 2 | 2 |

También se compararon catálogos, auditoría, sesiones y las demás tablas existentes. No se imprimieron filas, identidades ni hashes individuales de contraseñas. Las escrituras ficticias de integración se ejecutaron en una transacción revertida. PostgreSQL puede consumir números de secuencia aunque una transacción se revierta; no se reajustaron secuencias ni se alteraron registros existentes.

## Verificaciones posteriores

| Comprobación ejecutada | Resultado |
| --- | --- |
| Registro de migración e índice PostgreSQL | Correctos |
| showmigrations cuentas | 0001, 0002, 0003 y 0004 aplicadas |
| migrate --plan | Sin operaciones pendientes |
| check --database default | Sin incidencias |
| makemigrations --check --dry-run | Sin cambios |
| Integración sobre zona_bloque | 21 comprobaciones aprobadas |
| Concurrencia PostgreSQL | 2 intentos simultáneos rechazados por un_coordinador_activo |
| Backend, SQLite en memoria | 114 pruebas aprobadas |
| Frontend, Vitest | 33 pruebas aprobadas |
| Cliente HTTP, Node | 6 pruebas aprobadas |
| npm run build | Correcto, 59 módulos |
| npm audit | No completado: error al consultar el registro npm |

La integración PostgreSQL comprobó consulta coordinadora de profesores y tablero, prohibición de crear usuarios/cambiar roles/configuración/acceder al tablero administrativo, asignaciones docentes válidas, rechazo de duplicados y horarios incompatibles, aceptación de horarios compatibles con historial y auditoría, aislamiento del profesor y acceso global administrativo. También comprobó rechazo de acceso anónimo. APIClient se utilizó internamente sin emitir credenciales; las escrituras apuntaron a entidades ficticias y se revirtieron. Las pruebas de sesiones y CSRF están incluidas en la suite de backend y del cliente HTTP.

La prueba concurrente usa dos conexiones independientes que intentan insertar un segundo coordinador activo mientras permanece el titular real. Ambas reciben la restricción esperada. No se simuló un relevo real, una carrera con el cargo vacante ni carga de producción.

Los HTTP 400, 403 y 404 de las pruebas negativas son resultados esperados. El primer intento del script de integración usó identificadores ficticios negativos para grupos, incompatibles con el identificador positivo de auditoría. Se revirtió automáticamente y se corrigió únicamente el script de prueba usando identificadores positivos. La repetición completa pasó y verificó todas las huellas originales. No hubo errores al aplicar la migración. No se pudo determinar el estado de vulnerabilidades npm por el fallo del registro.

Las 22 verificaciones de navegador con API simulada del informe anterior son históricas; no se repitieron en esta aplicación de migración.

## Archivos de esta intervención

- scripts/aplicar_migracion_coordinador_unico.py: guardas de destino y plan exacto, respaldo, verificación integral, aplicación atómica y comparación de datos. Rechaza volver a aplicar cuando el plan ya no sea exactamente el autorizado.
- scripts/verificar_migracion_coordinador_unico.py: permisos, horarios y asignaciones ficticias revertidas, concurrencia y conservación de todas las tablas.
- Este informe, README y notas de estado de arquitectura/coordinación/tableros/verificación.
- El archivo de migración, los modelos, los permisos y la interfaz no se modificaron.

Se utilizaron los paquetes existentes de .venv-local mediante scripts/django_local.py y el Python auxiliar documentado en README, dado que el lanzador del entorno no accede a su Python base en este entorno restringido. No se instalaron dependencias globales.

## Acceso local

Con el backend en 127.0.0.1:8000 y Vite en 127.0.0.1:5173:

- Inicio de sesión: http://127.0.0.1:5173/
- Tablero general: http://127.0.0.1:5173/administracion
- Tablero coordinador: http://127.0.0.1:5173/coordinacion
- Gestión del cargo: http://127.0.0.1:5173/administracion/coordinacion
- API de resumen administrativo: http://127.0.0.1:8000/api/paneles/administrador/resumen/
- API de resumen coordinador: http://127.0.0.1:8000/api/paneles/coordinador/resumen/

Las rutas requieren sesión y rol correspondiente. Estas direcciones indican la configuración local; no se iniciaron ni reiniciaron servidores en esta intervención. Los comandos de inicio permanecen en README.

Trabajo detenido tras la migración autorizada y sus verificaciones. Sin commits, push ni desarrollo de fases posteriores.
