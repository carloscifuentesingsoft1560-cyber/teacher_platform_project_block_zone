# Servicios internos de ejecución progresiva — B3-B2

Fecha: 30 de octubre de 2026. Implementación y pruebas exclusivamente en PostgreSQL temporal aislado. **No se aplicó `0004` en `zona_bloque` ni se ejecutaron movimientos reales.**

## 1. Arquitectura y alcance

Se revisaron B1/B2/B3-B1, sus modelos, servicios, pruebas y SQL, el diseño B3-A y la documentación de B3-B1. Se implementa la alternativa progresiva aprobada sin duplicar modelos: `ResultadoAdministrativo` es el registro inmutable de cada movimiento confirmado, y `RevisionAdministrativa` conserva el plan completo que lo autorizó.

Se agrega `servicios_movimientos.py`. No se invoca `trasladar_bajo_bloqueo(... permite_nivel=True)`, porque pertenece al mecanismo antiguo bloqueado. Se reutiliza `crear_bajo_bloqueo(... permitir_nivel=True)` únicamente después de verificar aprobación institucional, revisión, afectaciones y continuidad. Este helper conserva `validar_nueva`: capacidad durante todo el intervalo, duplicados, estructura/periodo y cruces con las demás actividades del deportista.

No se llama a `contexto` ni `liberar_vencidas_bajo_bloqueo`: así una ejecución no procesa reservas de otros deportistas. El cupo del grupo no se modifica; cambia su ocupación real mediante cierre e ingreso de inscripciones.

No se añaden endpoints ni interfaz. No se cambia el reconocimiento de un nivel institucional efectivo, no se ejecuta un lote automáticamente y no se cierra una progresión.

## 2. Contrato de servicios

Servicio principal:

```python
ejecutar_reubicacion(
    actor, revision_id, version, afectacion_id, clave, motivo, fecha=None
) -> ResultadoAdministrativo
```

- Actor: usuario real, administrador activo o coordinador activo; se relee dentro del protocolo de bloqueo.
- Identificadores y versión: enteros positivos; versión del agregado `ProgresionInstitucional` observada por el operador.
- Clave: UUID idempotente proporcionado expresamente, sin generación silenciosa.
- Motivo: texto no vacío, máximo 240 caracteres por el contrato existente de `EventoInscripcion`.
- Fecha: si se proporciona, debe coincidir con hoy en `America/Bogota`. No se programan movimientos futuros ni retroactivos.
- Retorno: resultado con origen y destino como inscripciones, afectación, revisión, actor, fechas, motivo, clave y evidencia posterior al movimiento.

No se aceptan destino arbitrario, estado pedagógico o resultado de ejecución desde el cliente. El grupo destino procede exclusivamente de la disposición `reubicar` de la revisión indicada. Una revisión inexistente produce `NotFound`; permisos insuficientes producen `PermissionDenied`; las validaciones de entrada usan `ValidationError` y los estados/contextos obsoletos `Conflicto`.

`consultar_ejecucion(actor, identificador)` conserva su consulta restringida de administración/coordinación. Ahora incorpora resultados ejecutados de revisiones anteriores, distingue efectos propios de cambios externos, informa ejecución pendiente/parcial/completa y evalúa cierre. Los helpers `movimientos`, `foto` y `movimiento_vigente` son internos, no autorizaciones públicas.

## 3. Plan íntegro y permisos

Antes de ejecutar se exige:

1. Progresión pedagógica aprobada; no puede ser pendiente o rechazada.
2. Revisión administrativa más reciente, registrada por el procedimiento autorizado B3-B1.
3. Lista completa de afectaciones, sin `revisar`, con evidencia estructural válida y sin inscripciones nuevas ajenas al plan.
4. Identidad, disciplina, niveles, grupo, periodo, situaciones, versiones y huellas vigentes.
5. Fila seleccionada con disposición `reubicar` y destino expreso.
6. Ningún resultado ya registrado en esa fila/revisión ni movimiento ejecutado previo para la afectación.

`pendiente` es una disposición expresa, pero no es final ni concede continuidad por sí sola. Si después del movimiento otra inscripción activa permanece en el nivel anterior, debe tener excepción coordinadora vigente, incluso cuando esté pendiente de destino. Una pendiente sin esa autorización bloquea el movimiento. Una excepción no concede cupo ni altera horarios.

El profesor no ejecuta ni consulta el estado institucional global. Administrador y coordinador activo pueden ejecutar administrativamente; el administrador no puede aprobar pedagógicamente ni autorizar/revocar excepciones. La pérdida de vigencia del ejecutor se comprueba con el usuario actual. La aprobación anterior conserva actor, fecha y resolución; no se convierte al ejecutor en aprobador.

## 4. Transacción y validaciones operativas

La operación completa se encuentra dentro de `transaction.atomic`:

1. Bloqueo global de usuarios, compatible con las operaciones existentes; validación de autoridad y UUID.
2. Comprobación de idempotencia o bloqueo del agregado, deportista, inscripciones/grupos/reservas del contexto B1.
3. Bloqueo de todas las inscripciones y reservas del deportista, incluidas otras disciplinas, y destinos JSON en orden de ID.
4. Revalidación del plan completo y de la afectación concreta.
5. Comprobación de excepciones para permanencias y bloqueo conservador de situaciones sin política de ejecución.
6. Cierre de **solo** el origen seleccionado y creación de su continuación mediante validaciones de capacidad y horarios existentes.
7. Eventos deportivos, resultado inmutable, incremento de versión del agregado y evento institucional, en la misma transacción.

El origen debe estar activo, sin reserva no liberada y con ingreso anterior a hoy. Su grupo, disciplina, nivel y periodo deben estar activos y vigentes. Se conserva `inscripcion_fechas_validas`: no hay tramo de duración cero. La reanudación no cambia el ingreso original ni elude esa regla.

El destino debe existir, estar activo, corresponder a disciplina y nivel consecutivo aprobados, tener horarios y periodo vigente y disponer de cupo durante la vigencia completa del nuevo ingreso. `validar_nueva` verifica además duplicados y cruces con todas las otras inscripciones/reservas del deportista. No basta la disponibilidad presentada al preparar el plan.

El cierre del origen precede a la validación de alta dentro de la transacción: su intervalo deja de ocupar desde la fecha de traslado, sin ignorar las demás actividades. Si falla cupo, horario, estado, registro de resultado, evento o constraint diferido, se revierte la petición completa. No se realizan reparaciones destructivas ni restauraciones automáticas.

El bloqueo global serializa los escritores institucionales actuales; se mantiene deliberadamente. No se afirma garantía de capacidad frente a un operador SQL privilegiado que cree inscripciones omitiendo todos los servicios y protocolos. No hay esperas de usuario ni llamadas externas dentro de la transacción.

## 5. Historial, evidencia e idempotencia

El origen conserva PK, deportista y grupo originales, y pasa a finalizado con fecha de salida, causa `cambio_nivel`, responsable y nueva versión. La nueva inscripción tiene su propia PK y `inscripcion_anterior=origen`, con fecha de ingreso igual al cierre exclusivo de origen. El UUID/identidad permanente del deportista no cambia.

Se registran `ingreso`, `traslado_origen` y `ejecutar_reubicacion`, además del resultado administrativo y auditoría existente. No se copia el expediente pedagógico ni documentos personales a la evidencia.

El nuevo campo `evidencia_ejecucion` almacena dos fotografías, origen y destino, con ID, versión, huella y campos deportivos mínimos del registro. Sirve para distinguir el cambio intencional confirmado de una modificación externa sin incremento de versión. No es una firma digital ni sustituye autorización.

La clave es única por revisión. Misma revisión/clave/afectación/motivo/fecha recupera el resultado confirmado sin crear otra inscripción, evento o versión; en una recuperación con fecha omitida se conserva la fecha registrada. Distinto contenido produce conflicto. Las unicidades globales de afectación y origen ejecutados impiden duplicar el movimiento con otra clave o revisión.

Si ya existe evidencia pendiente/resuelta en la fila de esa revisión, no se actualiza ni elimina: debe registrarse una revisión administrativa nueva y expresa antes de ejecutar. Los reintentos no eluden las comprobaciones de identidad o de evidencia del resultado. Un cambio material posterior puede requerir conciliación, en lugar de repetir la ejecución.

## 6. Progresión parcial y revisiones posteriores

Las demás inscripciones no se cierran ni actualizan. La consulta suma resultados confirmados de todas las revisiones y excluye sus continuaciones del conjunto de inscripciones nuevas no planificadas. La primera ejecución no vuelve obsoleto por sí mismo el conjunto completo.

Una revisión nueva puede ajustar destinos de filas no ejecutadas y ratificar expresamente cambios de metadatos de grupo/horario/capacidad. Conserva las versiones anteriores y la aprobación pedagógica. No puede redefinir el destino o disposición de un movimiento ya confirmado; esa prohibición se comprueba también en SQL.

Para una fila ejecutada se comparan los campos deportivos congelados y versiones de sus dos inscripciones. Los cambios de metadatos del grupo quedan señalados hasta una revisión nueva que los ratifique; esa ratificación no permite reescribir registros deportivos ni modificar el resultado anterior. Cambios posteriores reales de estado/versiones de la inscripción resultante requieren conciliación específica, no se ocultan mediante una nueva huella.

Estados derivados:

- `pendiente`: aún no hay movimientos ejecutados.
- `parcialmente_ejecutado`: existe al menos uno y quedan afectaciones sin ejecutar.
- `ejecutado`: todas las afectaciones de la revisión tienen movimiento confirmado.
- `cerrado`: nunca se establece automáticamente en esta etapa; se devuelve `cerrado=False` y `puede_cerrar` como evaluación.

`estado_plan` B1 continúa significando preparación; no se amplía su CHECK con `ejecutado`. El indicador histórico `ejecucion_habilitada=False` conserva la ausencia de ejecución **pública**: no se exponen rutas ni botones. No debe interpretarse como sustituto del control del nuevo servicio interno ni cambiarse desde React para eludirlo.

Una excepción permanece abierta aunque la inscripción se traslade o llegue su vencimiento. El administrador no la revoca automáticamente. No se puede cerrar mientras haya excepciones abiertas o situaciones pendientes. El cierre institucional y la liberación de exclusividad para otro ascenso siguen fuera de este servicio.

## 7. Situaciones bloqueadas y decisiones pendientes

No se implementa traslado de una inscripción suspendida con reserva ni sustitución de alta futura: implicarían decidir si transferir/extender/liberar reserva, reanudar o cambiar fechas sin una política aprobada. Se incluyen en la revisión pero se rechaza ejecutarlas. También bloquean un estado intermedio cuando otra afectación suspendida/futura seguiría en el nivel anterior sin una disposición operativa definida.

No se realizan saltos, rectificaciones, retroactividad, fusiones de orígenes, reservas de plaza al preparar destino, cupos por sesión ni planes individuales por días. No se reactiva una reserva vencida ni se procesa automáticamente ninguna reserva de otro deportista.

## 8. Migración nueva pendiente

`inscripciones.0004_ejecucion_administrativa`

Dependencias: `inscripciones.0003_revisionadministrativa_resultadoadministrativo_and_more` y dependencia intercambiable del usuario Django.

Ocho operaciones:

1. `RunSQL`: `SET LOCAL search_path TO public, pg_catalog, pg_temp`.
2. Quitar `resultado_admin_b1_sin_ejecucion` en la tabla B3 de resultados.
3. Añadir `evidencia_ejecucion` JSON; `{}` significa ausencia de evidencia de movimiento para registros pendientes/resueltos anteriores, nunca evidencia ejecutada ficticia.
4. Actualizar la etiqueta/opciones de `estado` para documentar `ejecutada`.
5. Unicidad parcial `movimiento_afectacion_unico` para estados ejecutados.
6. Unicidad parcial `movimiento_origen_unico` para estados ejecutados.
7. CHECK `resultado_admin_estado_coherente`: pendiente/resuelta sin destino efectivo y sin evidencia de movimiento; ejecutada con destino, fecha y evidencia no vacía.
8. `RunSQL`: reforzar las dos funciones B3 y añadir la verificación diferida del movimiento.

No se editan `0002` ni `0003`. La migración obtiene sus definiciones SQL históricas inalteradas y construye las diferencias explícitas B3-B2; la dependencia fija su orden. No contiene SQL dinámico en PostgreSQL ni usa `SECURITY DEFINER`. `sqlmigrate` permite inspeccionar el SQL resultante antes de una eventual instalación autorizada.

Los cambios afectan a la tabla de resultados B3 y sus funciones, no al esquema de usuarios/grupos ni a las restricciones de fechas de inscripción. No se elimina historia B3-B1. El campo nuevo es aditivo y las pruebas migran con evidencia administrativa anterior.

## 9. Protecciones PostgreSQL

Se conservan los triggers que rechazan UPDATE/DELETE de resultados y revisiones. Una simple actualización de `estado`, fecha, destino o evidencia no puede representar una ejecución.

La guardia B3 exige para INSERT ejecutado: aprobación, actor administrativo activo, versión, afectación y origen correctos; origen finalizado por cambio de nivel y cierre posterior al ingreso; fecha operativa de Bogotá; destino activo con la misma identidad, disciplina y nivel aprobados, `inscripcion_anterior` correcto y mismo ingreso efectivo. El destino debe ser el grupo expresamente dispuesto; el origen debe tener la versión anterior observada más uno.

La auditoría diferida existente distingue `ejecutar_reubicacion` de resultados administrativos pendientes. Se añade `public.zdb_movimiento_ascenso_verificado` y su constraint trigger homónimo: comprueba evidencia y campos deportivos contra origen/destino reales, eventos deportivos coincidentes en actor/motivo/fecha, plan sin filas `revisar` y permanencias respaldadas por excepciones vigentes. Las nuevas revisiones no pueden redefinir movimientos confirmados.

Las funciones son `SECURITY INVOKER`, usan `search_path=pg_catalog` y referencias explícitas a `public`. El nuevo trigger es AFTER INSERT, diferido inicialmente, solo para `ejecutada`. Las restricciones de unicidad se suman al vínculo OneToOne de continuación existente y a la unicidad de destino de resultado. No se desactivan triggers para ejecutar.

Las protecciones no convierten en confiable un propietario que pueda fabricar cambios deportivos y eventos por SQL, eliminar funciones o desactivar restricciones. La autoridad humana se comprueba en los servicios y las escrituras ordinarias de aplicación deben respetar sus bloqueos.

### Reversión

El SQL inverso retira el nuevo trigger/función y restaura las funciones B3-B1 antes de revertir el campo y las restricciones. Se probó reversión/reaplicación con resultados pendientes, conservando sus filas e historial deportivo.

**Si existen resultados ejecutados, la reversión a B3-B1 se rechaza al recuperar el CHECK anterior.** La transacción DDL revierte íntegramente y conserva evidencia/datos. No se borran movimientos para forzarla. Una recuperación después de movimientos reales requiere diseño y autorización específicos; revertir esquema no es deshacer traslados.

## 10. Archivos

- `backend/inscripciones/servicios_movimientos.py`: nuevo servicio transaccional y validación de evidencia confirmada.
- `backend/inscripciones/servicios_ejecucion.py`: compatibilidad de revisión/consulta con movimientos parciales y revisiones posteriores.
- `backend/inscripciones/modelos_ejecucion.py`: evidencia y restricciones de resultado ejecutado.
- `backend/inscripciones/migrations/0004_ejecucion_administrativa.py`: nueva migración pendiente.
- `backend/inscripciones/test_movimientos_b3_b2.py`: movimientos, conflictos, permisos, concurrencia y migración.
- `backend/inscripciones/test_seguridad_migracion_b1.py`: repone la hoja `0004` al terminar sus ciclos históricos aislados.
- `backend/inscripciones/test_ejecucion_b3_b1.py`: repone `0004` tras su prueba histórica de reversión/reaplicación.
- Este documento.

No se modificaron frontend, URLs, vistas, roles, credenciales ni migraciones aplicadas. No se instalaron dependencias nuevas.

## 11. Pruebas

Ejecutor existente `scripts/pruebas_postgresql_aisladas.py`, que verifica directorio de datos y PID del proceso PostgreSQL temporal antes de configurar la conexión de Django. Se usaron los paquetes de `.venv-local` mediante `django_local.py`. Los ciclos de migración exigen la base temporal `test_zdb_fase3_…`.

```powershell
Remove-Item Env:ZDB_GENERAR_ASCENSOS -ErrorAction SilentlyContinue
$env:PYTHONDONTWRITEBYTECODE='1'
& 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' scripts/pruebas_postgresql_aisladas.py --failfast
```

La generación se hizo únicamente con la opción de generación aislada del ejecutor; no se ejecutó `makemigrations` ni `migrate` en la configuración real. La ejecución sin tests utilizada para generar el archivo no se cuenta como cobertura.

Antecedentes de desarrollo: 13 pruebas iniciales aprobadas; tanda B3-B2 de 29 pruebas aprobadas en 24,466 segundos, `respaldos/pruebas_fase3_p1kbb8i8/`, puerto 59428. Una comparación inicial de fixtures utilizó `__dict__` e incluyó el objeto interno `_state` de Django; se corrigió para comparar todos los campos persistidos mediante `values()`. Primera regresión completa de 470 pruebas aprobada en 151,151 segundos; corrida posterior de 477 aprobada en 156,219 segundos (`respaldos/pruebas_fase3_52qbu02q/`). Se añadieron después los casos de último cupo y modificación intermedia de horario.

La suite nueva contiene 33 pruebas y cubre: movimiento válido; dos inscripciones con una sola ejecutada y otra pendiente; segunda ejecución con revisión nueva; falta de excepción; excepción vencida; cupo lleno y actualización real de ocupación; destino eliminado/inactivo; cruce horario; suspensión/reserva y futura bloqueadas; versión obsoleta; doble ejecución y competencia con alta ordinaria por último cupo; idempotencia y clave inválida; fallo después del cierre y de auditoría; conservación de origen/continuación y de otras inscripciones; administrador/coordinador/profesor; rechazo de planes no aprobados; SQL UPDATE prohibido; grupos con historia protegidos; migración con evidencia anterior y reversión rechazada con ejecuciones existentes.

Resultado final verificado: **479 pruebas backend aprobadas en 158,250 segundos**, incluidas las 33 pruebas nuevas B3-B2. PostgreSQL temporal aislado en puerto 52527; evidencia privada en `respaldos/pruebas_fase3_sc70xblr/`. Django: `System check identified no issues (0 silenced)`. `makemigrations --check --dry-run`: `No changes detected`. La base de pruebas se eliminó y el clúster temporal quedó detenido. No se utilizó `zona_bloque` para estas operaciones.

## 12. Requisitos antes de B3-C o instalación real

1. Auditar la migración `0004` y el SQL generado, con atención a pruebas de evento diferido, conservación histórica e idempotencia.
2. Autorizar expresamente respaldo/restauración y aplicación de `0004` en `zona_bloque`; no invocar el nuevo servicio real antes de esa instalación.
3. Diseñar contratos REST y serializers estrictos para la interfaz posterior, sin permitir destinos arbitrarios o estado ejecutado proporcionado por cliente. Mantener validación de rol en backend, CSRF y errores que no expongan trazas SQL.
4. Mostrar todas las afectaciones y las excepciones necesarias para cualquier permanencia, sin presentar un destino propuesto como plaza garantizada. No ofrecer ejecución sobre suspendidas/futuras ni cierre automático.
5. Conservar versión, UUID y resultado de cada petición, y resolver respuesta perdida mediante idempotencia/consulta, nunca repitiendo movimientos con otra clave.
6. Resolver posteriormente políticas de traslado de reservas, sustitución de futuras, conciliación de estados posteriores de continuaciones y cierre institucional/liberación de exclusividad.

La entrega se detiene antes de cualquier operación real. No hubo traslados en `zona_bloque`, nuevas migraciones aplicadas, commits ni push. No se inicia interfaz B3-C.
