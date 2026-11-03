> Estado vigente, 28 de octubre de 2026: cuentas.0004_usuario_un_coordinador_activo fue autorizada y aplicada exclusivamente en zona_bloque, con respaldo integral verificado. Índice válido, sin migraciones pendientes, 21 comprobaciones PostgreSQL y dos rechazos concurrentes aprobados; datos existentes intactos. [Informe de aplicación](APLICACION_COORDINADOR_UNICO.md). Las referencias a migración pendiente o integración aún no ejecutada del documento siguiente describen el estado anterior a esta aplicación.

# Plan pendiente de aprobación — coordinador activo único

Estado: migración generada y probada exclusivamente en SQLite en memoria. **No aplicada en PostgreSQL.**

## Migración propuesta

cuentas.0004_usuario_un_coordinador_activo

Archivo: backend/cuentas/migrations/0004_usuario_un_coordinador_activo.py

Dependencias: cuentas.0003_solicitudrestablecimiento y auth.0012_alter_user_first_name_max_length, ya aplicadas en zona_bloque.

Operación única: AddConstraint de unicidad condicional para Usuario.rol cuando rol = coordinador e is_active = true.

SQL generado para PostgreSQL:

```sql
CREATE UNIQUE INDEX "un_coordinador_activo"
ON "cuentas_usuario" ("rol")
WHERE ("is_active" AND "rol" = 'coordinador');
```

## Efecto y revisión previa

- Impide dos coordinadores activos, incluso si una escritura elude la validación de aplicación.
- Permite varias cuentas coordinadoras inactivas para conservar historial.
- No crea tablas ni columnas, no cambia contraseñas ni borra/reasigna datos.
- No se modificaron las migraciones de Fase 2 ya aplicadas.
- La consulta previa, en modo solo lectura, comprobó PostgreSQL zona_bloque y un coordinador activo. No se imprimió su identidad.
- Si aparece una duplicidad antes de la aplicación, debe detenerse el proceso para que administración la resuelva explícitamente. No hay limpieza automática.
- La construcción del índice puede bloquear escrituras brevemente; se verificará el plan y se hará un nuevo respaldo antes de aplicar.

## Plan mostrado por Django

```text
Planned operations:
cuentas.0004_usuario_un_coordinador_activo
    Create constraint un_coordinador_activo on model usuario
```

## Secuencia posterior, solo con aprobación

1. Reconfirmar destino efectivo zona_bloque y ausencia de cambios inesperados en el plan.
2. Generar y verificar un nuevo respaldo privado de esa base.
3. Aplicar únicamente cuentas.0004_usuario_un_coordinador_activo.
4. Verificar registro de migración e índice.
5. Reiniciar el backend del proyecto y comprobar la ampliación.
6. Ejecutar integración PostgreSQL apropiada sin modificar al coordinador real para fabricar pruebas.

Comando reservado para después de la aprobación, no ejecutado:

```powershell
& .\.venv-local\Scripts\python.exe scripts/django_local.py migrate cuentas 0004_usuario_un_coordinador_activo
```

El código de aplicación ya rechaza un segundo coordinador por validación transaccional. La garantía adicional del índice en PostgreSQL todavía no existe hasta aplicar esta migración.

No se solicita autorización para otras migraciones, otros proyectos, despliegues o GitHub.
