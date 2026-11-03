# Diagnóstico del 404 del tablero administrativo

Fecha: 28 de octubre de 2026.

## Causa confirmada

La ruta /api/paneles/administrador/resumen/ estaba correctamente registrada en backend/paneles/urls.py e incluida desde backend/configuracion/urls.py. El proxy /api de frontend/vite.config.js también era correcto: conserva la ruta y remite al backend local.

Existían dos procesos escuchando en 127.0.0.1:8000. El proceso antiguo PID 35028 (Python 3.12.14), iniciado previamente por el agente con --noreload, conservaba el URLconf anterior a la ampliación. El proceso actualizado PID 22500 (Python 3.13.7) coexistía en el puerto. El servidor Vite PID 28960 continuaba funcionando en 5173.

La respuesta 404, tanto por localhost:5173 como por 127.0.0.1:8000, llevaba Server: WSGIServer/0.2 CPython/3.12.14 y una página de depuración de Django. Su listado de rutas incluía únicamente los tres paneles antiguos; no incluía las rutas de resumen. Por tanto, el 404 se originaba en el Django antiguo, no en Vite, el periodo seleccionado ni los permisos del administrador.

## Corrección mínima

Se detuvo mediante Ctrl+C únicamente el servidor antiguo controlado por la sesión del agente. No se terminó el servidor actualizado ni Vite. Después quedó un solo listener en 8000, correspondiente al PID 22500.

No se modificaron rutas, proxy, autenticación, permisos, modelos, frontend ni variables de entorno. No se ejecutaron migraciones, instalaciones, commits ni push. El único archivo creado en esta intervención es este informe.

## Verificaciones

- El resolvedor del código actual identifica ResumenVista para la ruta del resumen administrativo.
- Conexión efectiva PostgreSQL zona_bloque comprobada en transacción de solo lectura.
- Periodo 4 existente comprobado.
- APIClient con administrador activo y fecha 2026-10-28/periodo 4: HTTP 200, dentro de transacción PostgreSQL de solo lectura.
- Antes de corregir: tres peticiones a cada dirección reprodujeron HTTP 404 HTML de Django antiguo.
- Después: peticiones anónimas directas y a través de Vite devuelven HTTP 403 JSON desde Python 3.13.7, resultado esperado para una ruta protegida existente.
- Reutilizando internamente una sesión administrativa vigente, sin crear sesiones ni exponer cookies:
  - GET http://127.0.0.1:8000/api/autenticacion/sesion/ -> 200.
  - GET http://127.0.0.1:8000/api/paneles/administrador/resumen/?fecha=2026-10-28&periodo=4 -> 200.
  - GET http://localhost:5173/api/autenticacion/sesion/ -> 200.
  - GET http://localhost:5173/api/paneles/administrador/resumen/?fecha=2026-10-28&periodo=4 -> 200.
- Comparación de conteos y SHA-256 de todas las tablas de datos, incluidas sesiones: idénticos antes y después de las peticiones HTTP.
- Suite completa de backend: 114 pruebas aprobadas, SQLite en memoria; comprobación Django sin incidencias.
- No se repitieron frontend/build: no hubo cambios de código ni configuración; el problema era exclusivamente el proceso servidor desactualizado.

## Verificación visual pendiente

La herramienta de control de Chrome se detuvo porque no pudo determinar con suficiente confianza la URL activa para aplicar sus controles. Se suspendió la automatización del navegador y no se intentó eludir el bloqueo.

Por ello no se afirma haber verificado visualmente las tarjetas después de la corrección. La consulta HTTP real autenticada sí quedó comprobada de extremo a extremo a través de Vite. Para cerrar la observación visual, recargar http://localhost:5173/administracion con la sesión administrativa y seleccionar el periodo de prueba existente. No es necesario reiniciar Vite ni modificar registros.

Para evitar recurrencias, mantener una sola instancia Django del proyecto en 8000. Si se utiliza --noreload durante el desarrollo, reiniciarla tras cambios de código; el comando de inicio habitual de README conserva la recarga automática.
