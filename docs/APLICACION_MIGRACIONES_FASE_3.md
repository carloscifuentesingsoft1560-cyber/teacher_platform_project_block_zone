# Aplicación de migraciones de Fase 3

Fecha: 28 de octubre de 2026. **Aplicación autorizada completada en PostgreSQL zona_bloque.**

Se aplicaron exclusivamente:

- deportistas.0001_initial
- inscripciones.0001_initial

No quedan migraciones pendientes. No se crearon datos ficticios persistentes, no se modificaron deportistas reales y no se avanzó a módulos posteriores. Sin commits o push.

## 1. Verificación previa

- Conexión configurada y efectiva: PostgreSQL, base zona_bloque, esquema public.
- Historial de Django consistente; el plan global contenía exactamente las dos migraciones autorizadas, hacia adelante y en orden de dependencia.
- Se revisaron los objetos de migración y el SQL generado: únicamente CreateModel, AddIndex y AddConstraint.
- No existían tablas, secuencias o índices previos con los nombres de destino; tampoco colisiones con restricciones o metadatos de las aplicaciones nuevas.
- La revisión incluyó nombres de índices y restricciones generados automáticamente por Django, además de los explícitos.
- Se bloquearon temporalmente escrituras sobre las tablas anteriores mientras se respaldó, aplicó y comparó la información. Las lecturas continuaron disponibles.

Los archivos de migración aprobados no se modificaron durante esta aplicación. Sus SHA-256 y la huella del SQL revisado están en el manifiesto privado.

## 2. Respaldo generado y verificado

| Dato | Resultado |
| --- | --- |
| Archivo privado | respaldos/zona_bloque_antes_fase3_20261028T205425Z.dump |
| Tamaño | 66 814 bytes |
| Formato | PostgreSQL custom |
| SHA-256 | a4f1e7709eb1b3089e3b1eb3229583ba47899665378600c6a500526020208d7b |
| Catálogo con pg_restore --list | Correcto |
| Lectura/descompresión íntegra con pg_restore --file NUL | Correcta |
| Relectura SHA-256 al cerrar la verificación | Coincide |

Manifiesto: respaldos/fase3_20261028T205425Z.json. Contiene inventario, hashes de migraciones/SQL, conteos y huellas agregadas, estado de aplicación y los 69 casos de integración.

No se imprimieron contraseñas, cookies, datos de fichas o contenido del respaldo. respaldos/ y *.dump continúan excluidos mediante .gitignore.

La verificación recorrió el archivo completo sin restaurarlo a ninguna base. No se realizó un ensayo adicional de restauración: no era necesario para la lectura integral solicitada. Cualquier recuperación que reemplace datos reales necesitaría un plan y aprobación específicos.

## 3. Esquema creado

### Diez tablas

| Aplicación | Tabla |
| --- | --- |
| deportistas | deportistas_deportista |
| deportistas | deportistas_acudiente |
| deportistas | deportistas_vinculoacudiente |
| deportistas | deportistas_tipoautorizacion |
| deportistas | deportistas_autorizacion |
| deportistas | deportistas_politicadatos |
| inscripciones | inscripciones_inscripcion |
| inscripciones | inscripciones_eventoinscripcion |
| inscripciones | inscripciones_reservacupo |
| inscripciones | inscripciones_propuesta |

Todas quedaron vacías después de migrar y siguen vacías tras las pruebas revertidas.

### Tres índices explícitos

- deportista_estado_nombre
- inscripcion_grupo_fecha
- inscripcion_persona_fecha

### Veintidós restricciones explícitas

| Tabla | Nombres comprobados |
| --- | --- |
| deportistas_deportista | deportista_estado_valido |
| deportistas_tipoautorizacion | tipo_autorizacion_version_unica |
| deportistas_vinculoacudiente | vinculo_fechas_validas; vinculo_inicio_unico; vinculo_facultad_valida; vinculo_verificacion_completa |
| deportistas_autorizacion | autorizacion_otorgante_coherente; autorizacion_vigencia_valida; autorizacion_decision_valida |
| inscripciones_inscripcion | inscripcion_fechas_validas; inscripcion_estado_valido; inscripcion_cierre_coherente; inscripcion_inicio_unico; inscripcion_abierta_unica |
| inscripciones_propuesta | propuesta_tipo_valido; propuesta_estado_valido; propuesta_resolucion_coherente; propuesta_origen_coherente; propuesta_origen_pendiente_unica; propuesta_destino_pendiente_unico |
| inscripciones_reservacupo | reserva_fechas_validas; reserva_pendiente_unica |

Se verificaron nombre, tabla y naturaleza de cada objeto. Las restricciones únicas condicionales se materializan como índices únicos parciales en PostgreSQL; no todas aparecen como filas independientes de pg_constraint.

También se comprobó que todos los índices de las tablas nuevas estén válidos y listos y que sus restricciones PostgreSQL estén validadas. Las PK, FK y unicidades de campos generadas por Django se suman al inventario explícito.

## 4. Conservación de registros

Se compararon conteos y SHA-256 de los registros de las **19 tablas anteriores** dentro de la transacción de aplicación. Todos los registros anteriores son idénticos.

| Tabla anterior | Antes | Después de migrar y probar |
| --- | ---: | ---: |
| cuentas_usuario | 3 | 3 |
| organizacion_grupo | 1 | 1 |
| organizacion_horario | 3 | 3 |
| organizacion_asignacion | 2 | 2 |
| organizacion_periodo | 1 | 1 |
| auditoria_cambioadministrativo | 7 | 7 |

La comparación incluyó las demás tablas de catálogos, autenticación, relaciones y sesiones. No se modificó al administrador o coordinador reales para fabricar escenarios.

Cambios de metadatos previstos:

- Dos registros nuevos en django_migrations; se conservaron los registros anteriores y sus marcas temporales.
- Diez content types y 40 permisos estándar de modelo nuevos.
- Ninguna asignación adicional de permisos a personas o grupos; las relaciones anteriores conservaron sus huellas.

Para metadatos se comparó el subconjunto de registros preexistentes, excluyendo únicamente las entradas nuevas autorizadas de Fase 3.

Después se obtuvo una huella completa de las **29 tablas** ya migradas y se comparó antes/después de la integración con rollback. Todas fueron idénticas, incluidos los metadatos nuevos. También se repitió la comparación completa tras las peticiones HTTP locales.

Los rollback no retroceden secuencias PostgreSQL: pueden quedar saltos en identificadores después de pruebas ficticias. No se reajustaron secuencias ni se alteraron IDs existentes.

## 5. Integración y permisos sobre zona_bloque

**69 comprobaciones aprobadas**, con todos los destinos ficticios dentro de una transacción revertida.

Se utilizaron cuentas reales de administrador/coordinador únicamente como actores internos de APIClient, sin iniciarles sesión ni modificar sus atributos. Las cuentas docentes y la sesión utilizada para probar CSRF/logout fueron ficticias y se revirtieron.

Áreas comprobadas:

- Disponibilidad de ambos resúmenes y del módulo de deportistas.
- Alta y corrección versionada de identidad, código permanente y rechazo de nacimiento futuro.
- Profesor sin facultad de alta o ejecución; ficha y propuestas limitadas a su ámbito; ausencia de fecha de nacimiento y datos privados en su vista.
- Inscripciones compatibles en varios grupos, rechazo de duplicados y horarios incompatibles.
- Propuesta sin ejecución inmediata, decisión administrativa autorizada, rechazo de doble aprobación y rollback ante conflicto.
- Suspensión con vencimiento obligatorio, reserva dentro de ocupación y rechazo de sobrecupo.
- GET que reconoce vencimiento sin escribir; liberación transaccional, idempotente y auditada; conservación de la inscripción y reingreso.
- Propuesta docente de nivel, rechazo de sustitución administrativa, aprobación coordinadora y conservación del nivel anterior.
- Ediciones posteriores de capacidad/horarios rechazadas cuando afectaban a inscritos.
- Separación de contacto y representación; verificación explícita de facultad; declaración y revocación de autorización con auditoría.
- Denegación a profesor de contactos, autorizaciones y políticas.
- Pérdida de acceso tras desactivar únicamente una cuenta ficticia.
- Sesión Django ficticia, CSRF y cierre de sesión.
- Continuidad de ambos paneles después de los flujos.

Las pruebas que cambian de día usan una fecha operativa simulada dentro de la transacción; no modifican el reloj del sistema ni crean tareas reales. La prueba se niega a ejecutarse si las tablas nuevas ya contienen datos, evitando tocar registros reales de deportistas o reservas.

Los HTTP 400/403/404/409 de los casos negativos son resultados esperados. Los primeros intentos del script corrigieron dos escenarios ficticios: un reingreso que habría supuesto cambiar de nivel sin aprobación, y una asignación docente ficticia incompatible que contaminaba el caso de edición de cupo. Ambos intentos se revirtieron íntegramente; no se relajaron las reglas de negocio.

## 6. Ajuste mínimo de privacidad detectado al verificar

La comprobación descubrió que algunas rutas privadas podían validar un cuerpo antes de denegar la escritura al profesor. Aunque la escritura se rechazaba, ese orden podía permitir sondear relaciones por diferencias de respuesta.

Se incorporó SoloGestion antes de ejecutar validación de serializers:

- backend/deportistas/permisos.py: rechazo previo por rol, con configuración de tipos/políticas reservada a administrador.
- backend/deportistas/views.py: aplica la protección a rutas de gestión; conserva la lectura mínima autorizada de deportistas para profesor.
- backend/deportistas/tests.py: dos regresiones para cuerpos vacíos y referencias ajenas, y configuración por coordinador.

No cambió el modelo ni fue necesaria ninguna migración adicional. No se ampliaron privilegios ni se modificaron cuentas o datos reales.

## 7. Pruebas adicionales y HTTP real

| Comprobación de este encargo | Resultado |
| --- | --- |
| PostgreSQL temporal aislado | **172 pruebas aprobadas**, incluidas las cuatro de concurrencia |
| SQLite en memoria | **168 aprobadas y 4 omisiones explícitas** de concurrencia PostgreSQL |
| React/Vitest | **45 aprobadas** |
| Cliente HTTP/Node | **6 aprobadas** |
| Django check --database default | Sin incidencias |
| makemigrations --check --dry-run | Sin cambios |
| showmigrations deportistas inscripciones | Ambas 0001_initial marcadas aplicadas |
| migrate --plan | Sin operaciones pendientes |

El clúster temporal y su base de pruebas se crearon con los binarios ya instalados y se detuvieron al finalizar. No se probaron carreras sobre datos reales ni se confirmó un fixture en zona_bloque.

Se reutilizaron internamente sesiones vigentes ya existentes, sin exponer cookies, para ocho GET reales:

| Rol | Directo a Django 127.0.0.1:8000 | A través de Vite localhost:5173 |
| --- | --- | --- |
| Administrador: resumen con fecha 2026-10-28 y periodo 4 | 200 | 200 |
| Administrador: /api/deportistas/ | 200 | 200 |
| Coordinador: resumen con fecha 2026-10-28 y periodo 4 | 200 | 200 |
| Coordinador: /api/deportistas/ | 200 | 200 |

Los resúmenes emplean /api/paneles/administrador/resumen/ y /api/paneles/coordinador/resumen/. No cambiaron filas o sesiones al hacer estas consultas.

No se repitió la compilación ni npm audit porque no se modificó frontend o dependencias en este encargo. La compilación anterior estaba aprobada; la auditoría npm anterior quedó sin resultado por conectividad. No se afirma ausencia de vulnerabilidades.

## 8. Archivos de esta intervención

Creados:

- scripts/aplicar_migraciones_fase3.py: guardas de destino/plan, detección de conflictos, respaldo, aplicación atómica, metadatos y preservación.
- scripts/verificar_fase3_postgresql.py: pruebas ficticias revertidas, permisos, historial y comprobación completa de filas.
- docs/APLICACION_MIGRACIONES_FASE_3.md: este informe.

Modificados:

- Los tres archivos del ajuste de privacidad indicado arriba.
- README.md y notas de estado en PLAN_FASE_3_DEPORTISTAS.md, IMPLEMENTACION_FASE_3.md y MATRIZ_PERMISOS.md.

El respaldo, manifiesto y evidencia de clúster temporal están en respaldos/, excluido del control de versiones. No se modificaron archivos de migración, credenciales, documentos Excel, frontend, diseño visual ni otros proyectos.

## 9. Punto de parada y verificación visual con el propietario

Aplicación técnica y verificaciones completadas. **La revisión visual conjunta queda pendiente y no se ha iniciado en este encargo.**

Direcciones disponibles con los servidores locales actuales:

- http://localhost:5173/administracion
- http://localhost:5173/administracion/deportistas
- http://localhost:5173/administracion/inscripciones
- http://localhost:5173/administracion/autorizaciones
- http://localhost:5173/coordinacion
- http://localhost:5173/coordinacion/deportistas
- http://localhost:5173/coordinacion/propuestas

Las listas nuevas aparecerán vacías, por diseño: no se dejaron datos de demostración. Los usuarios, grupos, horarios y asignaciones anteriores siguen presentes.

No se activó una tarea programada de reservas, no se cargaron textos/consentimientos o políticas institucionales, y no se avanzó a sesiones, asistencia, planificación, biblioteca, cargas, evaluaciones o ClimbVision-AI.

No volver a ejecutar el aplicador: rechaza planes distintos de las dos migraciones pendientes autorizadas, incluidas repeticiones. La comprobación de estado segura sigue siendo migrate --plan.

Trabajo detenido para realizar la verificación visual con el propietario.
