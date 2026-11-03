# Etapa 2 — núcleo institucional en integración aislada

Fecha de entrega: 2 de noviembre de 2026. Estado: implementación de desarrollo, pendiente de publicación y aplicación operativa. Este informe corresponde exclusivamente a la carpeta independiente `respaldos/etapa2_20261102T182622Z/integracion/`. Los archivos del proyecto original permanecen intactos.

## 1. Conservación y control de versiones

Antes de editar se creó `estado_original_privado.zip`, junto con `manifest_original.json`, en la carpeta padre de integración. Se comprobaron CRC del ZIP y SHA-256 de sus 290 entradas. Incluye configuración y referencias privadas para recuperación local; no es un candidato Git y no contiene una nueva copia de la base PostgreSQL. No se modificaron ni sustituyeron los respaldos históricos.

SHA-256 del ZIP privado: `8d7f95c4b51d1aea16a42b9545e8b2489357d9fd6c9ed74bdd0294e29a088f5b`. La comparación final contra el manifiesto confirma cero cambios en esos 290 archivos del proyecto original. La copia de integración tiene 56 archivos previos modificados y 21 nuevos, enumerados en [ARCHIVOS_ETAPA_2.md](ARCHIVOS_ETAPA_2.md).

El intento de `git clone --no-checkout` por HTTPS falló por restricciones de red de la terminal. El conector de lectura permitió recuperar y reconstruir los dos commits y los seis árboles, comprobando sus SHA Git exactos. Rama local: `integracion/etapa-2`; base: `decda62bff95f782e124394fb221626f12990f6d`; padre: `26c4f1d137411003294c8ac701db54c375b88056`. El árbol de la base es `faa7200eadc93fcc16afd05239c97f7e81a0c732`. Corrige la identificación errónea de commit como árbol de la documentación histórica, que se conserva como referencia.

**La recuperación Git es parcial, no un clon completo.** `git fsck --full` identifica un único blob ausente: `9e0d3f820d05a550eb640111207f2487c883136a`, correspondiente al archivo histórico `Esquema de la idea`. El conector rechaza su codificación y el host de navegador no está disponible. Se conserva su referencia en los árboles y en el índice, sin fabricar bytes, borrar el documento o cambiar los commits. No se crearon commits nuevos sobre una recuperación incompleta.

El contenido fuente se prepara en el índice local para revisión y como parche, conservando los archivos originales antigravity-app. El documento ausente tiene temporalmente skip-worktree para no convertir su ausencia física en una eliminación. La URL de push de origin está deshabilitada localmente (`NO_PUBLICAR_SIN_AUTORIZACION`); no se hizo push, PR, publicación ni cambio remoto.

Cuando vuelva el acceso Git, completar en esta copia con una recuperación íntegra de objetos (por ejemplo `git fetch --refetch origin main`, revisando soporte de la versión instalada), comprobar `git fsck --full` sin objetos faltantes y recuperar solamente el archivo histórico ausente. No usar pull ni reset sobre el trabajo de integración. Alternativa: clon completo en otra carpeta y aplicación del parche revisado. No publicar mientras falte este objeto o la revisión de privacidad.

Las exclusiones cubren .env, claves privadas, respaldos, dependencias, compilados, bases y referencias privadas. No se copiaron .env, deportistas reales, consentimientos, grabaciones ni documentos privados al árbol fuente de integración. Las referencias curriculares y el paquete de investigación no forman parte de los archivos nuevos seleccionados. El historial remoto existente se preserva; su documento binario pendiente aún requiere revisión independiente antes de cualquier publicación.

## 2. Incrementos implementados

| Incremento | Implementación y reutilización | Verificación |
|---|---|---|
| 2A — facultades | `cuentas.autorizacion`: roles efectivos consultados en base, acciones conocidas y denegación de acciones desconocidas. Los servicios y permisos reutilizan Usuario y ámbitos existentes; se eliminan decisiones basadas exclusivamente en un rol de un objeto en caché | Acciones, anónimo, rol falsificado en memoria, cuenta desactivada y actor revocado; regresiones de permisos originales |
| 2B — identidad | Persona mínima con UUID y EnlaceIdentidad hacia Usuario/Deportista/Acudiente existentes, evidencia opaca, responsable, versión y revocación. Acreditación explícita administrativa; sin carga automática ni coincidencias de nombres/correos | Enlace de los tres perfiles sin duplicarlos; prevención de doble enlace vigente; revocación conservando perfiles y matrícula; API exige contraste explícito |
| 2C — roles | PertenenciaRol y EventoRol; seis roles, carga del rol preexistente, comandos de otorgamiento/revocación, restricciones de unicidad y cargo coordinador único, relevo sin retirar facultades docentes adicionales | Nombramientos concurrentes, SQL único, eventos inmutables, revocación con sesión/actor abiertos, proyección administrativa y conservación de otras facultades |
| 2D — ascensos | Profesor propone, coordinador decide pedagógicamente; administrador crea revisión administrativa y formaliza. Lectura coordinadora conservada. Validación por API, servicio y función PostgreSQL. Se conservan cupos, fechas, reservas, historial e idempotencia | Rechazo de coordinador por API/servicio/SQL; administrador no decide por su rol; doble rol explícito y revocación; regresión B1/B2/B3 |
| 2E — API/React | Respuesta de sesión aditiva, selección de espacio, gestión de roles y acreditación de identidad, actualización de permisos al recuperar foco/recibir denegación y periódicamente. Los roles nuevos solo tienen espacio reservado y perfil; no abren módulos deportivos | Navegación multirrol, entrada por URL con rol revocado, foco, formularios de otorgar/revocar/acreditar, consulta coordinadora sin formalización y regresión frontend |

No se cambia AUTH_USER_MODEL ni se recrean usuarios, deportistas, acudientes, grupos o inscripciones. Las nuevas identidades quedan pendientes de acreditación: no se inventan equivalencias. La identidad compartida no concede autorización legal, audiovisual ni acceso a menores. Los indicadores organizativos cuentan cuentas con una pertenencia concreta, sin duplicar por varios roles; no afirman contar personas reconciliadas cuando sus enlaces siguen pendientes.

Trazabilidad del alcance: todos los estados siguientes significan verificado en desarrollo aislado; no aplicado en operación.

| Requisito | Entidad / API / pantalla | Permiso y evento | Prueba concreta |
|---|---|---|---|
| Identidad compartida sin duplicación | Persona, EnlaceIdentidad; /identidad/; Identidades | Administración, acreditación explícita y CambioAdministrativo | IdentidadMultirrol.test_persona_compartida_conserva_tres_perfiles_y_matricula |
| Roles múltiples sin elevación implícita | PertenenciaRol; /usuarios/{id}/roles/; RolesCuenta | Otorgamiento administrativo, EventoRol | NucleoInstitucional.test_2a_roles_combinados_no_dan_autoridad_clinica |
| Revocación inmediata | Cuenta/pertenencia vigente; misma API; actualización de sesión | Revalidación de backend, revocar_rol | test_2c_revocacion_inmediata_con_actor_en_cache; test_ultimo_rol_revocado_no_reaparece_por_desactivar_o_reactivar |
| Coordinador único | PertenenciaRol, índice parcial, pantalla de cargo | Relevo serializado, eventos inicio/fin | ConcurrenciaRoles.test_dos_nombramientos_solo_un_coordinador |
| Propuesta/revisión/formalización | ProgresionInstitucional y entidades B3; /ascensos/; Propuestas | Facultad por acción, EventoProgresion, guardia SQL | FacultadesAscensosEtapa2 y ApiEjecucion.test_guardia_sql_anterior_no_habilita_formalizacion |
| Aislamiento horizontal | Deportista/Inscripcion, consultas por asignación | Objeto y ámbito; consultar_ficha | IdentidadMultirrol.test_profesor_routesetter_no_ve_ni_modifica_persona_ajena |
| Conservación al migrar | Usuario y perfiles originales | Sin enlaces inferidos, procedencia de migración | MigracionNucleo.test_backfill_preserva_usuario_y_no_acredita_persona |
| Interfaz y compatibilidad | ContextoAutenticacion, rutas existentes y nuevas | El espacio de pantalla no concede facultades | NucleoInstitucional.test.jsx, GestionNucleo.test.jsx, regresión frontend |

## 3. Semántica de facultades y compatibilidad

- `Usuario.rol` se conserva como rol principal de compatibilidad. Un trigger registra su transición y mantiene la pertenencia correspondiente. El acceso efectivo usa pertenencias vigentes y cuenta activa, no ese campo aislado.
- El flujo antiguo de cambio de rol principal se rechaza cuando la cuenta tiene varios roles; se utiliza la gestión explícita de pertenencias. No se amplían facultades propias desde la API administrativa y se conserva al menos un administrador activo mediante los servicios transaccionales.
- Revocar la última facultad desactiva la cuenta sin recrear una pertenencia. Reactivar no restaura roles revocados: primero debe otorgarse expresamente una facultad a la cuenta inactiva y después activarla. Una cuenta inactiva puede conservar facultades asignadas sin acceso efectivo. El cargo coordinador requiere cuenta activa y el flujo institucional. Los flags técnicos de un administrador asignado no se borran por la sola inactivación; la revocación administrativa sí los retira.
- El relevo mantiene como máximo un coordinador vigente. Si el saliente conserva otras facultades, su cuenta sigue activa. Si no conserva ninguna, queda inactiva. Las asignaciones docentes no se borran y requieren facultad docente vigente para producir acceso.
- Un coordinador con rol administrador también puede formalizar. No se impone separación de personas que el propietario no pidió. Las acciones pedagógica y administrativa conservan responsables/eventos diferentes aunque coincida la persona.
- El espacio elegido en React determina navegación y controles; no es una fuente de autoridad. Backend comprueba facultades y objeto de nuevo. Los permisos son la unión de facultades expresamente otorgadas; un rol adicional routesetter no convierte al profesor en gestor institucional.
- Revocar enlace de identidad no altera matrículas o consentimientos. Tampoco abre/cierra un portal aún inexistente. Sus futuras reglas deberán considerar enlace, rol, finalidad y vínculo vigente de acudiente de forma conjunta.
- La compatibilidad permite probar migraciones históricas en PostgreSQL temporal. No se introduce fallback de privilegios al rol principal si faltan las tablas nuevas.

## 4. Modelos, migraciones y PostgreSQL

Migraciones nuevas, creadas y ensayadas únicamente en bases temporales:

1. `cuentas.0005_enlaceidentidad_eventorol_persona_pertenenciarol_and_more`: tablas nuevas, relaciones protegidas, exclusividad de perfil por enlace, unicidad de enlace vigente, ampliación de opciones válidas de rol y restricciones de pertenencia.
2. `cuentas.0006_roles_compatibilidad`: carga del rol actual sin elevar privilegios, evento de procedencia de migración con actor histórico desconocido explícitamente nulo, función SQL de facultad efectiva, sincronización del campo principal y protección SQL de eventos. Las cuentas inactivas conservan su clasificación sin obtener acceso; un coordinador inactivo no ocupa el puesto vigente.
3. `cuentas.0007_remove_pertenenciarol_pertenencia_estado_coherente_and_more`: exige fecha final no nula al revocar, evitando que la lógica NULL de PostgreSQL admita una revocación incompleta.
4. `inscripciones.0005_facultades_multirrol`: reemplaza funciones mediante migración aditiva que reutiliza las definiciones históricas congeladas; formalización solo con pertenencia administrativa vigente y validación coordinadora compatible con roles múltiples.

Las 19 fuentes de migraciones históricas conservan sus hashes. No se editaron ni se reaplicaron sobre la base operativa. No hay nuevas dependencias de terceros ni extensiones PostgreSQL obligatorias.

El comprobador de instalación verifica ahora la migración nueva, las garantías B3 previas, el cuerpo de la función administrativa y de la función de rol efectivo, SECURITY INVOKER/search_path y el trigger de compatibilidad. Una función administrativa antigua no habilita formalización aunque permanezca registrada la migración.

Reversión: antes de retirar la estructura multirrol, la migración bloquea el retroceso si hay identidades nuevas, eventos posteriores incompatibles, roles múltiples o roles que el esquema anterior no admite. No promete convertirlos silenciosamente a un único rol. Los tests de migraciones históricas restauran el esquema vigente al terminar. Cualquier aplicación operativa necesitará inventario, SQL revisado, respaldo de base y restauración aislada propios; el backup fuente de esta entrega no los sustituye.

## 5. Contratos API y pantallas

Se conservan rutas existentes, sesión Django/CSRF, errores de dominio y versionado de matrículas/progresiones. Las escrituras de roles e identidad usan el mismo orden global de bloqueo de cuentas que la operación existente.

| API | Uso y permiso |
|---|---|
| GET /api/autenticacion/sesion/ | Conserva usuario.id/username/nombre/rol; añade roles y facultades efectivas. No incluye credenciales ni evidencia |
| GET/POST /api/usuarios/{id}/roles/ | Administración consulta historial de pertenencias u otorga un rol con motivo |
| POST /api/usuarios/{id}/revocar-rol/ | Administración; pertenencia perteneciente al usuario de la URL, versión y motivo; un ID de otro usuario devuelve 404 |
| GET/POST /api/identidad/ | Administración; consulta/acredita enlaces; POST exige tipo/perfil, evidencia UUID v4 y contraste explícito; persona/version_persona cuando se enlaza identidad existente |
| GET /api/identidad/{id}/ | Detalle mínimo de enlace administrativo, con auditoría |
| POST /api/identidad/{id}/revocar/ | Administración; versión del enlace, conserva historial |
| GET /api/personas-institucionales/ y /{id}/ | Selección administrativa de identidad existente; nombre derivado de un perfil acreditado sin duplicar datos personales en Persona |
| POST /api/ascensos/{id}/revisiones/ y /ejecutar/ | Administración vigente exclusivamente; el coordinador conserva consultas GET y la revisión pedagógica |

Pantallas: `/administracion/usuarios` incorpora Facultades; `/administracion/identidad` permite acreditar perfiles; cargo único conserva su pantalla de relevo; los tres espacios actuales conservan rutas y estilo. Routesetter, deportista y acudiente tienen una reserva visible sin datos operativos futuros. Las correcciones de cuenta/perfil no se convierten en ascensos o autorizaciones médicas.

Las lecturas de ficha de deportista, identidad y roles seleccionadas se auditan sin copiar valores sensibles. No se afirma que exista todavía una política exhaustiva de auditoría/retención ni un portal completo de menores.

## 6. Pruebas y problemas encontrados

Los registros completos de ejecuciones están en `integracion/respaldos/pruebas_etapa1_*/`. El nombre del prefijo proviene del ejecutor reutilizado; son clústeres efímeros de esta Etapa 2. Ninguno usa zona_bloque. Cada resultado.json registra puerto, códigos y apagado.

| Comprobación | Resultado de desarrollo |
|---|---|
| Regresión inicial de cuentas previa al cambio | 58 aprobadas; evidencia savqhzre |
| Primera integración | Detectó expectativas antiguas de relevo/roles y acceso seguro de un actor revocado; corregidas |
| Primera regresión amplia | 524 ejecutadas, con 4 fallos y 6 errores; no se considera aprobada. Detectó clasificación inactiva perdida, serializers estrictos con formato incorrecto y fixtures que aún formalizaban como coordinador |
| Dirigidas tras correcciones | 140 aprobadas; evidencia nhrkf6qi; incluye migración y concurrencia |
| Regresión completa intermedia | 532 aprobadas en 233,977 s; evidencia g4xr1t3g; check sin incidencias y No changes detected |
| Cuentas tras formularios/cese secundario | 82 aprobadas, incluidas tres comprobaciones API adicionales; evidencia swln1k95 |
| Formalización/comprobador SQL final | 24 aprobadas; evidencia clpud2ct; incluye rechazo de función SQL anterior |
| Infraestructura aislada | 5 aprobadas |
| Frontend | 160 aprobadas en 14 archivos; JSON privado frontend_resultado.json |
| Cliente HTTP | 6 aprobadas |
| Build | Aprobado; 76 módulos, sin cambios de dependencias |
| Pase unificado de 536 antes de estabilizar fixture | Un error: la prueba de reservas/futuras asumía posiciones en una consulta sin orden. Se reemplazó por identificación de cada afectación, sin cambiar reglas productivas ni reducir aserciones |
| Reproducción de los dos casos temporales | 2 aprobadas; evidencia tdozv5yi |
| Repetición completa tras estabilizar orden de fixtures | 536 aprobadas en 227,305 s; evidencia u2kmwoof |
| Comprobaciones SQL negativas con actor administrativo válido | 35 aprobadas; evidencia 5nrj3hpc; conservan el objetivo original de integridad/auditoría sin pasar por rechazo temprano del rol coordinador |
| Cierre de la última facultad y reactivación explícita | 83 pruebas de cuentas aprobadas; evidencia l1yuoeui |
| Regresión final unificada | **538 aprobadas en 233,646 s**, sin fallos ni skips; evidencia euk3hcd9; system check sin incidencias y No changes detected |

Los cambios de expectativas se limitan a facultades aprobadas: ejecución ahora administrativa, seis roles, relevo que conserva docencia y restauración del esquema más reciente. Los escenarios de integridad, privacidad, idempotencia, concurrencia y cupos se mantienen. Se añadieron tests negativos explícitos para el coordinador y para roles combinados; no se ocultaron fallos mediante skips.

La consulta de permisos se simplificó a una consulta actual de pertenencias/cuenta activa, evitando introspección repetida por cada comprobación. No se almacena una caché de autoridad que sobreviva a revocaciones. Los estados y datos observados de evaluaciones deportivas, las sesiones y RSD no se implementaron.

No se ejecutó revisión visual en navegador real ni dispositivos móviles en esta entrega; el host de navegador no está disponible. jsdom no acredita CSS/responsividad completa ni captura de cámara. No se descargaron dependencias, modelos IA o pesos, ni se enviaron comunicaciones externas.

## 7. Reproducción aislada

Desde la carpeta de integración, establecer ZDB_PAQUETES_PYTHON al directorio de paquetes existente del proyecto original; se usa solo para importar dependencias, con PYTHONDONTWRITEBYTECODE. Frontend tiene copia independiente de node_modules; no usa un enlace que escriba cachés en el proyecto original.

```powershell
$pythonPruebas = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$proyectoOriginal = (Resolve-Path '../../..').Path
$env:ZDB_PAQUETES_PYTHON = Join-Path $proyectoOriginal '.venv-local/Lib/site-packages'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $pythonPruebas scripts/test_infraestructura_aislada.py
& $pythonPruebas scripts/pruebas_postgresql_aisladas.py --verbosity 2
# Dirigidas: añadir --etiqueta cuentas o --etiqueta inscripciones.test_facultades_etapa2
```

Desde frontend: `npm.cmd test`, `npm.cmd run test:api`, `npm.cmd run build`. Las etiquetas backend admiten únicamente nombres de las apps de pruebas autorizadas; no pueden cambiar settings/base. El perfil normal de settings de esta rama se bloquea: solo funcionan los perfiles de prueba, y PostgreSQL exige el clúster verificado. No hay un servidor operativo habilitado automáticamente.

## 8. Límites, riesgos y siguiente autorización

- Git parcial: recuperar el blob original y revisar el documento histórico antes de completar un clon, commit o publicación. El código se entrega revisable en la carpeta independiente y en un parche; no afirmar fsck limpio.
- La identidad técnica está disponible; la acreditación institucional de personas reales sigue pendiente y no se ha realizado. No hay fusión masiva ni carga de consentimientos.
- La política clínica, finalidades de medios/IA, retención y portales siguen en sus etapas. El administrador no obtiene autoridad sanitaria.
- Los bloqueos globales actuales se conservan para integridad; no se ha probado rendimiento a gran escala. La protección SQL está dentro del rol de aplicación; no pretende impedir acciones de un propietario PostgreSQL con privilegios para desactivar triggers o falsificar datos.
- Históricos se preservan; rollback con datos nuevos se bloquea para evitar pérdidas. No ejecutar rollback automático en operación.
- Antes de aplicar: completar Git/privacidad, revisar diff y SQL, ensayar copia restaurada de base con autorización de acceso, preparar conservación y ventana de cambio. No basta la suite sobre fixtures para autorizar migraciones reales.

**Punto de parada:** no se publica ni se aplica al proyecto original/base operativa. Se requiere autorización específica posterior para cada destino y operación concreta. Currículo, sesiones, planificación, evaluaciones, Route Setting y recolección audiovisual conservan prioridad en las siguientes etapas; Climbing Vision AI permanece aplazado.

## 9. Cierre verificable y artefactos

Estado técnico final: 538 pruebas backend PostgreSQL, 160 frontend, 6 HTTP y 5 de infraestructura aprobadas; build aprobado. Todas las bases temporales finalizaron destruidas por el runner Django y sus clústeres quedaron detenidos. No se ejecutaron pruebas contra la base operativa. No se afirma validación visual o institucional de contenidos futuros.

El padre de esta carpeta contiene el respaldo privado, manifiesto original, revisión de candidatos y paquetes de entrega. `integracion_remota.patch` representa los archivos fuente seleccionados respecto al remoto histórico; `cambios_sobre_etapa1.patch` muestra los cambios respecto a la copia original de Etapa 1; `fuentes_etapa2.zip` contiene solo fuentes seleccionadas, sin .env, bases, respaldos, dependencias, compilados, Excel o vídeos. `manifest_entrega.json` registra sus hashes y los de las fuentes. Los artefactos son locales y no se publicaron. Ninguno sustituye completar el objeto Git faltante.

Los objetos Git dangling de versiones intermedias del índice no se eliminaron; no son pérdida del historial remoto. La única ausencia remota identificada sigue siendo el blob documentado en el apartado 1. El índice de la rama local está preparado, sin commit nuevo y sin eliminaciones de archivos remotos.
