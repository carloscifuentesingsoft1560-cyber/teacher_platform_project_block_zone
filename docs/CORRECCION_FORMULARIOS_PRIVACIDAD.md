# Corrección de payloads de acudientes y autorizaciones

Fecha: 28 de octubre de 2026. Alcance: fallo de creación de acudientes en `/administracion/autorizaciones?deportista=9`.

## Causa reproducida

`RegistroPrivado`, en `frontend/src/paginas/AcudientesAutorizaciones.jsx`, pasaba `{ fecha_inicio: fechaBogota(), numero_version: 1 }` como estado inicial a todas las secciones y operaciones distintas de editar. `FormularioRegistro` conserva ese objeto y lo entrega completo a `guardar`; no limita el estado a los controles visibles. `enviar` copia el objeto y el cliente HTTP lo serializa sin eliminar esos campos.

Por ello, crear el contacto con los nombres, teléfono y correo indicados añadía dos propiedades invisibles al POST `/api/acudientes/`. `AcudienteSerializer`, derivado de `Estricto`, las rechazaba correctamente con estado 400 y `errores.fecha_inicio` / `errores.numero_version`: «Campo no permitido». No eran campos requeridos del acudiente ni un problema de la migración documental. El parámetro `deportista=9` solo filtra vínculos y autorizaciones; no provoca la inyección.

La misma inicialización contaminaba vínculos con `numero_version`, autorizaciones con ambos campos, tipos de autorización con `fecha_inicio`, políticas con ambos y acciones como revocar con ambos. Las pruebas de React anteriores simulaban éxito sin validar el contrato, por lo que no detectaban el fallo.

## Corrección mínima

Se declaran valores iniciales por sección: únicamente los vínculos reciben `fecha_inicio`, y únicamente los tipos de autorización reciben `numero_version: 1`. Estos valores se utilizan solo al crear. Las acciones comienzan con un objeto vacío y las ediciones conservan su construcción anterior de campos y versión.

No se modificó el componente genérico de formularios, el cliente HTTP, serializers, modelos, permisos o rutas. No se flexibilizó la validación estricta del backend ni se eliminaron campos válidos de otros formularios. No hubo rediseño.

## Pruebas automatizadas

Se reprodujo el flujo React desde la ruta filtrada y se capturó el POST generado por el cliente HTTP real de la aplicación, con la respuesta de la API simulada conforme al contrato estricto. Antes de corregir, seis comprobaciones fallaron: las cinco creaciones y el payload de revocación incluían campos ajenos. No se presenta esta simulación como una prueba de navegador conectado a la base real.

La regresión comprueba el cuerpo exacto de las cinco creaciones, utilizando en acudientes los datos ficticios facilitados. Comprueba que vínculos conserven su fecha y tipos su versión del texto, y que la revocación envíe únicamente motivo y versión de concurrencia. La fecha de declaración se compara con la conversión ISO de la zona local para evitar una expectativa dependiente del huso horario de la máquina.

Las nuevas pruebas API de Django reproducen el payload incorrecto y verifican su 400, y comprueban el 201 del administrador con el contacto corregido, datos guardados y auditoría. También prueban creación de vínculo, verificación de facultad, autorización con evidencia ficticia y revocación. El profesor recibe 403 en las tres rutas tanto con datos válidos como con campos ajenos; no se crean contactos, vínculos ni autorizaciones en esos intentos.

Resultados finales:

- Frontend completo: **59 pruebas aprobadas**, cinco archivos.
- Backend completo: **208 pruebas aprobadas** en PostgreSQL temporal aislado, incluidas las cuatro regresiones nuevas y las seis pruebas de concurrencia existentes.
- `makemigrations --check --dry-run --settings=configuracion.settings_pruebas`: **sin cambios detectados**. No genera ni aplica migraciones.

Durante el desarrollo de las pruebas API se corrigieron sus aserciones para leer el envoltorio estándar `errores` de la aplicación. Esto no requirió cambios de producción en el backend.

## Archivos

- Modificado `frontend/src/paginas/AcudientesAutorizaciones.jsx`: inicialización por sección y operación; única modificación de código de producción.
- Modificado `frontend/src/pruebas/Fase3.test.jsx`: contratos simulados estrictos, cinco creaciones nuevas y aserción exacta de revocación.
- Creado `backend/deportistas/test_formularios_privacidad.py`: cuatro pruebas de reproducción, éxito administrativo, contratos relacionados y rechazo docente.
- Creado este informe.

Las escrituras de prueba se realizaron exclusivamente en el clúster temporal creado por `scripts/pruebas_postgresql_aisladas.py`, que se detuvo al finalizar. No se crearon ni modificaron registros, sesiones, roles o relaciones persistentes en `zona_bloque`. No se generaron migraciones, commits ni push.

## Comprobación visual pendiente

Volver a la ruta indicada con la sesión administrativa existente, abrir «Crear registro de acudientes» y repetir los datos proporcionados. El POST deberá incluir solo nombres, apellidos, teléfono y correo. El guardado manual supondrá una escritura institucional: no se realizó automáticamente durante esta corrección. Se detiene el trabajo para repetir la prueba visual con el usuario.
