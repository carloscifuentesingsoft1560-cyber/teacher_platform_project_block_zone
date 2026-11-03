# Procedimiento propuesto: activación y recuperación de Etapa 2

**No ejecutado. Requiere autorización específica para destino, respaldo, ventana y despliegue.** El ejecutor de ensayo rechaza producción y no debe adaptarse para migrarla.

## Preparación verificable

1. Resolver el blob histórico Git faltante, verificar historial y revisión del diff. Revisar exclusiones: secretos, `.env`, dumps, archivos personales/audiovisuales, logs privados y dependencias fuera del paquete. No publicar sin autorización independiente.
2. Fijar versión de aplicación anterior/nueva y hashes de fuentes, dependencias y cuatro migraciones; preservar todas las migraciones históricas. Preparar backend, React y SQL coordinadamente. La rama actual solo admite perfiles de prueba: diseñar/revisar configuración de despliegue, sin copiar contraseñas a fuentes.
3. Identificar explícitamente host/puerto/base/rol y responsable del destino mediante canal protegido. Confirmar PostgreSQL/Django reales, locale/collation, extensiones, permisos de aplicación, espacio y versión. No usar variables heredadas ni destinos implícitos.
4. Con autorización, obtener respaldo reciente consistente de base completa; registrar hora, procedencia, hash, tamaño, esquema, secuencias y migraciones. Respaldar configuración y medios privados por procedimiento separado. Restaurar el respaldo en entorno protegido con características equivalentes al destino; cotejar datos/esquema e inventario y ensayar exactamente el plan autorizado. Este ensayo histórico no sustituye ese paso.
5. Registrar todos los conteos y huellas de tablas existentes; comprobar cuentas/roles válidos, coordinador único, matrículas/progresiones/historiales y ausencia de migraciones divergentes. Determinar metadatos Django faltantes y prohibir nuevas asignaciones de permisos no previstas. No resolver anomalías fusionando identidades ni borrando historia.
6. Definir responsables de ejecución, observación y decisión de abortar; acordar ventana sin escrituras, límites de bloqueo/tiempo medidos, conservación de evidencia y recuperación. Mantener acceso al respaldo restringido y confirmar restauración verificable, no solo generación de dump.

## Activación propuesta

1. Poner la aplicación en mantenimiento y detener trabajadores/escritores; confirmar ausencia de transacciones incompatibles. No permitir operación mixta con componentes de autoridad anteriores.
2. Tomar respaldo final tras detener escrituras; registrar inventario final y probar que el plan contiene únicamente las cuatro migraciones revisadas. Si no coincide, abortar antes de DDL.
3. Ejecutar migraciones con destino explícito y logs privados, monitoreando bloqueos y errores. Evaluar un envoltorio transaccional de las cuatro y post_migrate previamente ensayado con el procedimiento de despliegue; Django por defecto garantiza transacción por migración, no necesariamente por toda la secuencia.
4. Antes de habilitar escrituras, verificar constraints/índices/triggers, cuatro altas de historial, conservación de filas previas y metadatos esperados; tres pertenencias del ensayo son solo ejemplo, el número real debe igualar usuarios del inventario vigente. No deben crearse acreditaciones de identidad automáticas.
5. Activar de forma conjunta la versión backend y frontend revisada. Smoke tests con cuentas de prueba controladas: sesión/facultades, objetos ajenos denegados, revocación inmediata, combinación de roles sin elevación, coordinador único y ascenso profesor→coordinador→administrador. No usar personas reales para simular ascensos.
6. Abrir operación solo cuando responsable confirme verificaciones y no haya discrepancias. Registrar versión, hora, evidencias y facultades; no declarar aprobados contenidos metodológicos por desplegar infraestructura.

## Criterios de abortar y recuperación

- Antes de cambios: cancelar si respaldo/restauración no son verificables, destino dudoso, plan distinto, coordinadores duplicados, datos divergentes, falta de espacio/permisos o aislamiento insuficiente.
- Fallo dentro de envoltorio atómico: dejar revertir, verificar esquema/datos/migraciones contra inventario; no iniciar aplicación nueva. El ensayo demostró este caso, con posible avance de secuencias sin pérdida de filas.
- Fallo entre migraciones sin envoltorio global: mantener mantenimiento. Inventariar qué migraciones quedaron confirmadas y diagnosticar; no marcar migraciones como aplicadas con `--fake` ni lanzar inversas indiscriminadas. Preferir corrección hacia delante revisada o restauración íntegra autorizada.
- Recuperación desde respaldo: restaurar primero en base nueva restringida, comprobar hash/origen, esquema, filas, secuencias y medios/configuración compatibles con versión anterior; validar arranque y permisos sin escrituras. Cambiar destino de aplicación solo tras autorización específica; conservar base fallida aislada como evidencia. No sobrescribir ni borrar el origen para recuperar.
- Después de admitir escrituras multirrol/identidad: no ejecutar migración inversa automática. La protección puede bloquearla por información incompatible. Una restauración antigua perdería escrituras nuevas: conservarlas y diseñar conciliación auditada antes de decidir. Nunca reducir roles o eliminar eventos silenciosamente.
- Reapertura: confirmar consistencia, permisos e historial con responsable; documentar causa, alcance y cualquier dato conciliado. Probar revocación y formalización administrativa otra vez.

No se fija RTO/RPO ficticio: dependen de volumen, ventana y pruebas de restauración actuales. No se ejecuta ningún paso operativo de este documento en la presente autorización.
