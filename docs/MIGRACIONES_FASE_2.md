# Estado actualizado — 28 de octubre de 2026

Las cuatro migraciones fueron aprobadas, respaldadas y aplicadas en PostgreSQL zona_bloque. Integración real: 88 comprobaciones aprobadas; backend 73/73, frontend 24/24 y build aprobado. npm audit sigue bloqueado por conectividad. Consulta [el informe actual](APLICACION_MIGRACIONES_FASE_2.md). El contenido siguiente conserva el estado histórico previo a la autorización.

# Plan de migraciones de Fase 2 — pendiente de aprobación

No se ejecutaron nuevas migraciones en PostgreSQL. Las pruebas aplicaron el esquema solo en SQLite temporal en memoria.

El plan fue consultado mediante migrate --plan sobre la conexión PostgreSQL del proyecto. Se generó y revisó el SQL de organizacion/0001 con sqlmigrate, sin ejecutarlo.

## Estado observado

- cuentas/0001_initial: ya aplicada antes de este trabajo.
- cuentas/0002_eventoacceso: ya aplicada antes de este trabajo.
- auditoria/0001_initial: nueva, pendiente.
- cuentas/0003_solicitudrestablecimiento: nueva, pendiente.
- organizacion/0001_initial: nueva, pendiente.
- organizacion/0002_catalogos_iniciales: nueva, pendiente.

## Orden del plan

1. auditoria.0001_initial: crea CambioAdministrativo.
2. cuentas.0003_solicitudrestablecimiento: crea SolicitudRestablecimiento con hash de token y fechas.
3. organizacion.0001_initial: crea Disciplina, Nivel, Periodo, Grupo, Asignacion y Horario, claves foráneas, índices y restricciones.
4. organizacion.0002_catalogos_iniciales: añade Escalada y cinco niveles configurables:
   - Lúdico.
   - Nivel 1.
   - Nivel 2.
   - Escuela de especialización semicompetitiva.
   - Alto rendimiento.

La carga inicial usa get_or_create, no sobrescribe catálogos por código, no crea cuentas, grupos ni periodos y no importa documentos o datos personales. No crea contenido curricular de Alto rendimiento.

## Efecto

Se crean ocho tablas nuevas en la base configurada para este proyecto y los seis registros iniciales de catálogo. No se cambian columnas del usuario existente ni se borran registros. No se requieren extensiones PostgreSQL ni privilegios administrativos globales del servidor.

Hay claves foráneas con protección ORM, unicidad de códigos, cupos positivos, días válidos, orden de fechas/horas, tipos válidos y unicidad de asignaciones/inicios y horarios activos. Los solapamientos de intervalos se controlan adicionalmente en transacciones con bloqueos.

## Comandos de revisión, sin aplicar

Desde la raíz:

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py check --database default
& .\.venv-local\Scripts\python.exe scripts/django_local.py makemigrations --check --dry-run --settings=configuracion.settings_pruebas
& .\.venv-local\Scripts\python.exe scripts/django_local.py migrate --plan
```

## Comando reservado para después de aprobación expresa

```powershell
# NO ejecutado durante esta entrega. Requiere aprobación del propietario.
& .\.venv-local\Scripts\python.exe scripts/django_local.py migrate
```

Después se comprobarán el esquema y las pantallas con PostgreSQL. Las pruebas de concurrencia y de integración PostgreSQL no se consideran aprobadas todavía; no se creó ninguna base de prueba en ese servicio.

La aplicación de Fase 2 en navegador queda condicionada a este paso. Mientras falten tablas, no se deben usar las operaciones nuevas contra la base local.
