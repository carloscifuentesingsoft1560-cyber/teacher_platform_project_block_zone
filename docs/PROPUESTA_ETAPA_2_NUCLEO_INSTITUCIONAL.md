# Propuesta detallada de Etapa 2 — núcleo institucional

Diseño pendiente de aprobación. Etapa 1 no implementa esta propuesta. Se conserva Usuario y la base existente; no cambiar AUTH_USER_MODEL, duplicar personas o reescribir migraciones históricas.

## Dependencias y secuencia de incrementos

### 2A. Contrato de facultades e inventario de dependencias

Construir matriz de acciones, objeto y alcance por rol antes de modificar comportamiento. Separar cuenta activa, rol vigente, cargo coordinador único, asignación docente y titularidad/vínculo de portal. Una cuenta multirrol no obtiene autoridad médica ni acceso irrestricto a menores.

| Capa existente | Dependencia del rol único | Cambio futuro necesario |
|---|---|---|
| cuentas/models.py y migraciones cuentas 0001/0004 | CharField rol, check de tres valores, índice único coordinador activo | Modelo aditivo de pertenencia de rol/vigencia y representación transaccional del cargo único; conservar campo durante transición |
| cuentas/servicios_usuarios.py, coordinacion.py, serializers y admin | Altas/edición/relevo; hoy relevo desactiva toda la cuenta saliente | Distinguir retirada de facultad coordinadora de desactivación global. Una persona puede conservar rol profesor; no alterar retrospectivamente relevos pasados |
| organizacion/permisos.py, alcance.py, servicios.py | Asignacion.tipo debe coincidir con usuario.rol; bloqueos globales de cuentas | Validar facultad docente/coordinadora vigente y mantener asignación/fechas; preservar orden de bloqueos hasta probar sustitución |
| deportistas/permisos.py, servicios.py, facultades.py y serializers | es_gestor y proyecciones según rol | Autorización por acción y finalidad, proyección mínima, cuenta-perfil comprobada; revocación sin filtrar terceros |
| inscripciones/views.py, views_ascensos.py y api_ejecucion.py | Acciones diferenciadas por cadenas de rol | Permisos explícitos proponer/revisar/consultar/formalizar; comprobación en backend y servicios |
| servicios_ascensos.py, servicios_ejecucion.py y servicios_movimientos.py | autorizado compartido permite coordinador/admin | Separar revisión pedagógica, lectura administrativa y formalización; no restringir un helper genérico sin revisar todos sus consumidores |
| SQL histórico inscripciones 0003/0004 | Funciones verifican roles en cuentas_usuario | Nueva migración que reemplace funciones afectadas; no editar SQL histórico. Inventario de triggers y pruebas directas SQL |
| paneles/resumen.py y vistas | Conteos/filtros por rol único | Evitar doble contar personas multirrol; indicadores documentan si cuentan personas, cuentas o pertenencias |
| React ContextoAutenticacion, Aplicacion, Estructura y páginas | usuario.rol y ruta única determinan espacio/acciones | Contrato de roles/facultades y espacio activo explícito; backend sigue siendo autoridad; conservar login y estilos |
| Pruebas y fixtures existentes | Suposición de rol exclusivo y ejecución compartida | Conservar regresión y cambiar expectativas solo al aprobar política nueva; añadir combinaciones y SQL/concurrencia |

Inventario indicativo, no una lista exhaustiva de líneas. La búsqueda de `rol`, `es_coordinador_activo`, `administrador` y comparaciones SQL debe repetirse sobre el árbol exacto que se vaya a modificar. No basta cambiar el selector ni el permiso de una vista.

### 2B. Identidad y roles aditivos

Proponer entidad de persona/enlace estable o asociación comprobada equivalente tras revisar los registros: actualmente Usuario, Deportista y Acudiente no están unidos. No asumir que cada cuenta es persona nueva. Crear plan de conciliación con casos pendientes y responsables; no fusionar nombres/correos ni atribuir identidad automáticamente.

Pertenencia de rol candidata: usuario, rol, vigencia, estado, otorgante, motivo breve y versión/historial. Backfill limitado al rol ya registrado por usuario, sin añadir facultades. Decidir representación de cargo único (puesto institucional con titular vigente o unicidad equivalente) y probar nombramientos simultáneos; índice actual no protege roles adicionales por sí solo. Mantener rol de compatibilidad hasta migrar todos los consumidores y acordar su retirada en otra entrega.

Roles previstos: administrador, coordinador, profesor, routesetter, deportista y acudiente. Añadir pertenencia no activa un portal inexistente ni publica información. Una misma persona cuenta una vez como evaluador RIC en etapas futuras.

### 2C. Separación de ascensos

| Acción | Profesor objetivo | Coordinador objetivo | Administrador objetivo | Hoy |
|---|---|---|---|---|
| Proponer desde matrícula propia | Sí | No por su cargo | No por su cargo | Profesor |
| Revisar evidencia y decidir pedagógicamente | No | Sí | No por su cargo | Coordinador |
| Consultar expediente | Su ámbito autorizado | Institucional autorizado | Datos necesarios para formalizar | Proyecciones existentes por rol |
| Preparar disposiciones pedagógicas/excepción | No | Sí | No por su cargo | Coordinador |
| Revisión administrativa y ejecución de matrícula | No | Consulta/observación; no formalización | Sí | Coordinador y administrador |

Alcance exacto de preparar una revisión administrativa frente a confirmarla debe aprobarse antes del cambio; propuesta: coordinador conserva evidencia/disposiciones pedagógicas y lectura, administrador crea la revisión administrativa formal y ejecuta. Historial y claves idempotentes de decisiones anteriores siguen válidos. No reasignar actor ni invalidar evidencia porque su autor ya no tiene esa facultad. Reintentos de escrituras no autorizadas tras revocación no conceden nuevos privilegios.

Para persona con roles coordinador y administrador, definir si se exige separación personal entre decisión y formalización o solo separación por facultad/contexto. El maestro exige etapas y autoridades, pero no ordena explícitamente dos personas distintas; no inventar esa prohibición. Mantener estados y bloqueos actuales de suspendidas/futuras, fecha operativa, reservas, cupos y cierre no automático.

### 2D. Autorizaciones y auditoría del núcleo

Reutilizar VinculoAcudiente, ComprobacionFacultad, TipoAutorizacion, Autorizacion y PoliticaDatos. Definir enlace de cuenta comprobado y revocación, sin confundir facultad para autorizar con permiso para consultar portal. No crear consentimientos, tipos aprobados o políticas ficticias. Documentar finalidad, vigencia, alcance, minimización y retención; introducir auditoría de lecturas sensibles con datos mínimos y pruebas de no registrar documentos/claves.

Etapa 2 deja el contrato de acceso listo; interfaces deportivas, medios privados completos, RSD y portales siguen en sus etapas. Corregir duplicación de get_queryset en AutorizacionVista solo en un incremento aprobado con prueba de instalación incompleta y filtrado, sin ampliar permisos por accidente.

## Puertas de aceptación y migración

1. Aprobar matriz de facultades, semántica del cargo único, enlace de personas y tratamiento de roles combinados. Prototipo de payload de sesión conserva compatibilidad antes de cambiar React.
2. Presentar migraciones nuevas y SQL, inventario de funciones/triggers afectados y política de backfill. Ejecutarlas solo en clúster temporal; comprobar migración desde esquema anterior, reversibilidad cuando sea posible y conservación de IDs/autores/versiones.
3. Pruebas: rol actual conserva alcance; cuenta multirrol no duplica persona; profesor ajeno recibe denegación; revocación inmediata; relevo no elimina otras facultades; dos coordinadores concurrentes rechazados; coordinador solo no formaliza ni por API ni servicio ni SQL; admin solo no decide pedagógicamente; idempotencia y cupos conservados.
4. Regresión backend PostgreSQL, frontend/HTTP/build y recorridos de navegador ficticios. Verificar conteos por persona y accesibilidad de selección de espacio. Aprobación técnica no valida contenido deportivo.
5. Antes de cualquier aplicación operativa: autorización concreta, respaldo y restauración aislada comprobados, plan de conservación y ventana de aplicación. Etapa 1 no autoriza esa operación ni un despliegue.

## Decisiones pendientes para iniciar

- Confirmar la matriz propuesta para preparación/revisión administrativa y formalización de ascensos.
- Determinar si un coordinador-administrador puede completar ambas facultades o se requiere separación personal; no asumir requisito nuevo.
- Elegir diseño final de identidad compartida y responsables de acreditar enlaces sin fusionar datos ambiguos.
- Aprobar transición de rol principal a pertenencias y semántica del relevo multirrol, conservando cargo coordinador único.
- Configurar políticas/finalidades y alcances autorizados cuando se habiliten accesos de deportista/acudiente; no rellenarlos automáticamente.

Al aprobar el diseño se puede comenzar 2A y preparar implementación incremental en entorno aislado. Ninguna migración o escritura operativa está incluida en esta propuesta por defecto.
