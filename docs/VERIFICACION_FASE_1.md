# Actualización de verificación

La verificación posterior está documentada en [CIERRE_FASE_1.md](CIERRE_FASE_1.md): 21/21 backend, 10/10 frontend, build y conexión PostgreSQL aprobados. npm audit pendiente por conectividad. El informe que sigue conserva el resultado histórico de la primera entrega.

# Verificación de Fase 1

Fecha: 27 de octubre de 2026, America/Bogota.

## Estado real

La base técnica está creada. **No se ha demostrado todavía el funcionamiento integral de la aplicación.** Las descargas de dependencias están bloqueadas en este entorno.

| Verificación | Resultado observado |
|---|---|
| Inspección del remoto | Completada por conector GitHub; árbol y archivos conservados |
| Node | 24.20.0 |
| Python del entorno de herramientas | 3.12.14; se creó .venv local |
| PostgreSQL 17 | Servicio activo; pg_isready confirma que acepta conexiones |
| Credenciales/base de aplicación | No configuradas; no se consultaron bases ajenas ni se modificó el servicio |
| Instalación pip | Falló: no se pudo obtener Django; No matching distribution found |
| Instalación npm | Falló con EACCES al acceder a registry.npmjs.org |
| Cliente HTTP con Node | 6 pruebas aprobadas, 0 fallidas |
| Sintaxis Python | AST y compileall aprobados |
| Sintaxis JS/JSX | Transformación de sintaxis aprobada con esbuild disponible en el entorno |
| Pruebas Django | No llegaron a ejecutarse: ModuleNotFoundError: django |
| Comprobación de migraciones Django | No llegó a ejecutarse por falta de Django |
| Pruebas Vitest | No llegaron a ejecutarse: vitest no instalado |
| Build Vite | Falló; sin instalación local completa, un Vite externo se resolvió desde el entorno y no pudo leer/resolver configuración por restricciones de acceso |
| Interfaz en navegador y capturas | No realizadas: no existe build/servidor funcional validado |

## Pruebas incluidas

### Ejecutadas: cliente HTTP, 6 casos

- Mismo origen y cabeceras de consulta.
- Obtención de CSRF y uso del token rotado tras login.
- Logout por POST con CSRF y descarte del token.
- Preservación de mensajes y códigos de acceso denegado.
- Distinción entre caída de red y rechazo de acceso.
- Manejo de respuestas no JSON sin exponer HTML.

### Pendientes: Django, 21 casos

CSRF de login, credenciales, cuentas inactivas, cookies HttpOnly/SameSite/Secure, sesión restaurada, matriz completa de roles, intento de elevación por parámetros, revocación al desactivar, cambio de rol, logout, rotación de sesión y CSRF, orígenes, validación de campos, limitación de intentos, integridad de rol, superusuario, restricción del admin y auditoría mínima.

### Pendientes: interfaz, 10 casos

Redirección de anónimos, restauración de los tres roles, ruta de otro rol, ingreso/cierre con CSRF, error de credenciales, servidor caído, menú/perfil y bloqueo de doble cierre.

Los mocks de interfaz no sustituyen las pruebas Django ni una prueba real en PostgreSQL.

## Comandos ejecutados

Desde la raíz:

```powershell
node --test frontend/pruebas/cliente.node.mjs
& .\.venv\Scripts\python.exe -m compileall -q backend
& .\.venv\Scripts\python.exe backend/manage.py test cuentas --settings=configuracion.settings_pruebas
& .\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run --settings=configuracion.settings_pruebas
& 'C:\Program Files\PostgreSQL\17\bin\pg_isready.exe' -h 127.0.0.1 -p 5432
```

Desde frontend:

```powershell
npm.cmd test -- --reporter=verbose
npm.cmd run build
```

También se revisó sintaxis mediante AST de Python y transformSync de esbuild, leyendo únicamente el código creado.

## Condiciones para cerrar la validación

1. Recuperar acceso a PyPI/npm y resolver dependencias; generar y revisar el lockfile npm real.
2. Configurar .env y una base PostgreSQL exclusiva.
3. Ejecutar check, migraciones, pruebas aisladas y makemigrations --check.
4. Ejecutar pruebas en PostgreSQL con cuenta de pruebas dedicada y base temporal autorizada.
5. Ejecutar Vitest y build.
6. Revisar login, tres paneles, perfil, cierre, expiración y acceso cruzado en navegador.
7. Verificar escritorio, tableta, móvil, foco por teclado y contraste.

No se incluyen credenciales, datos personales, fixtures reales, capturas ficticias ni resultados de pruebas no ejecutadas.
