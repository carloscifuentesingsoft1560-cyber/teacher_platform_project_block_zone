# F3.6-B2.1 — mandatos y acreditaciones pendientes

Base: `interfaz-sesiones-react`, commit `2ba845592c5dc122af4ee2c4232883af745d4a38`. Implementación técnica sin concesión operativa. No constituye aprobación institucional.

## Entidades y límites

Se añaden cuatro entidades en cuentas:

- `MandatoInstitucional`: expediente de un titular propuesto, con persona, cuenta, enlace de identidad, versión y copia de la evidencia de identidad; disciplina, alcance descriptivo y registrador históricamente acreditado.
- `EventoMandatoInstitucional`: cadena numerada de propuesta, revisión y retiro, con identidad histórica del actor, evidencia, motivo, solicitud idempotente e intervalo propuesto.
- `AcreditacionEmisora`: expediente que relaciona una propuesta B1 y su evento exacto con un mandato pendiente y su evento exacto. No acredita facultades profesionales.
- `EventoAcreditacionEmisora`: cadena equivalente de actuaciones pendientes sobre esa relación.

Se reutilizan `Persona`, `EnlaceIdentidad`, los registros B1, las guardias ORM de `EvidenciaCompetencia`, la comprobación administrativa y los bloqueos existentes, y `auditoria.registrar`. No se crean aplicaciones, roles o servicios de aprobación paralelos.

No hay estados aprobados, activos o de concesión. Los modelos solo declaran permiso predeterminado de lectura; no se añaden endpoints, administración, permisos de emisión, datos iniciales ni autoridades aprobadas. El catálogo funcional y las autorizaciones individuales quedan fuera de B2.1. El alcance es descriptivo y nunca se interpreta como cobertura funcional.

## Integridad

`0010` es una migración aditiva de esquema, generada con settings en memoria, backend dummy y `MigrationLoader(None)`, sin `.env` ni SQL. `0011` agrega guardias nuevas, sin alterar `0008`, `0009` ni sesiones. Requiere la tabla de auditoría existente.

Las cuatro tablas son inmutables frente a UPDATE/DELETE; las guardias ORM rechazan también actualizaciones masivas. Las referencias son protegidas. Se fija la fecha de registro en el servidor, y se conserva la identidad utilizada aunque sus enlaces se revoquen después.

Toda actuación nueva requiere administración e identidad acreditada actuales. El registrador no puede coincidir por persona con el titular del mandato ni con el candidato B1; titular y candidato tampoco pueden coincidir. Se comparan identidades históricas del candidato, no solo cuentas o roles. Una revocación o cambio de enlace no permite eludir la separación utilizando otra cuenta.

La acreditación exige fuentes existentes, misma disciplina y los eventos últimos exactos de B1 y del mandato, sin retiro. Su intervalo propuesto debe quedar contenido en ambos intervalos de referencia. Si una fuente se revisa, no se trasladan automáticamente sus cambios al expediente anterior: nuevas actuaciones sobre la relación anterior se rechazan; otra relación puede referenciar el nuevo antecedente. Retirar una fuente tampoco borra expedientes previos.

Primer evento obligatorio, número consecutivo, antecedente de la misma cadena y retiro terminal. Una constraint diferida impide confirmar cabeceras sin su primer evento y eventos sin auditoría coincidente. Los triggers contrastan solicitud, actor y evidencia. Clave y referencia de evidencia de eventos deben ser UUID v4.

Los intervalos `[desde, hasta)` son exclusivamente propuestos. Se admiten propuestas pasadas o futuras para documentación, sin que ello habilite actividad alguna; se rechazan fechas sin zona desde los servicios e intervalos vacíos o invertidos. No existe aprobación o autorización retroactiva.

Las guardias `0011` no se revierten automáticamente: retirar protecciones históricas requiere un procedimiento revisado. No habilitar escrituras en una instalación detenida en `0010` sin `0011`.

## Transacciones, idempotencia y auditoría

Los tres comandos internos son `proponer_mandato`, `proponer_acreditacion` y `registrar_evento`. Solo operan sobre expedientes pendientes. Toda creación incluye cabecera, evento y auditoría en la misma transacción.

Se mantiene el bloqueo global de usuarios por PK, compartido con roles e identidad, antes de consultar identidades y expedientes. Las guardias SQL también lo aplican; bloquean cabeceras y fundamentos. Esto serializa escrituras, incluidas claves concurrentes entre los dos tipos de evento, con coste de contención conocido.

Una clave por actor se comparte lógicamente entre ambas cadenas. El reintento exacto devuelve el evento original y no duplica auditoría; reutilizar una clave con otra solicitud genera conflicto. Se comprueban permisos e identidad actuales antes del reintento. Repetir una actuación ya registrada no crea otra ni reactiva fundamentos retirados. Un cambio de identidad del autor histórico impide recuperar el resultado mediante esa cuenta reasignada.

Una versión esperada obsoleta genera conflicto; los fallos de infraestructura, timeout o deadlock no se convierten en conflictos satisfactorios. Los errores SQL se propagan y revierten la operación. Los registros de auditoría general solo contienen nombres de campos, sin documentos ni contenido de evidencia privada.

## Verificación y alcance de las pruebas

Antes de PostgreSQL se ejecutaron satisfactoriamente el verificador estático específico y las 24 barreras existentes de aislamiento. El verificador no importa settings del proyecto ni abre conexiones. Comprobó sintaxis de los siete archivos Python, grafo/modelos, checks de los cuatro modelos, acciones cerradas, permisos de lectura y veinte guardias de inmutabilidad ORM.

La única ronda PostgreSQL autorizada se limitó a `cuentas.tests.test_acreditaciones_emisoras`, mediante el ejecutor publicado. Creó un clúster nuevo y evidencia propia fuera del repositorio y de `respaldos/`, con paquetes/binarios explícitos, entorno saneado y sin `.env`. No se reutilizaron clústeres o evidencias anteriores. El cierre revalidó identidad y objeto hijo; no se detuvieron servidores ajenos.

Las fixtures son identidades y expedientes ficticios sin aprobación operativa. Cubren separación entre cuentas, fundamentos B1, referencias obsoletas/retiradas, periodos, cadenas, auditoría, rechazo ORM/SQL, rollback, concurrencia, idempotencia y los bloqueos Python/SQL de `realizada`. También comprueban que las migraciones B1 permanecen instaladas y protegidas. No sustituyen la suite completa de regresión ni representan un despliegue.

Resultados: 24/24 pruebas de barreras aprobadas. PostgreSQL descubrió y ejecutó 28 pruebas B2.1 en una sola ronda: 28 aprobadas, cero fallidas, cero errores y cero omitidas, en 14.802 segundos. Las migraciones `0010` y `0011` se aplicaron correctamente en la base nueva `test_zdb_fase3_e0501b1c2ca6`, junto con las migraciones anteriores. Pasaron identidad/separación, fundamentos B1, secuencia, retiro, inmutabilidad ORM/SQL, referencias, auditoría, rollback, concurrencia e idempotencia. Se verificó que `realizada` sigue bloqueada en Python y SQL y que los expedientes no conceden permisos operativos.

El chequeo posterior modelos/migraciones terminó con `No changes detected`, código 0. Evidencias conservadas en `C:\Users\57310\AppData\Local\Temp\zdb_pg_sndo54q8`. Host 127.0.0.1, puerto 56883, hijo PID 2760. `resultado.json` confirmó `pruebas: 0`, `migraciones_check: 0`, `detenido: true`, identidad revalidada y cierre controlado sin incidentes ni terminación forzada. El log confirmó el apagado y desapareció `postmaster.pid`. No se ejecutaron otras suites ni migraciones operativas. Ante futuros fallos se deberá conservar evidencia y detenerse, sin corregir ni repetir automáticamente.

## Decisiones institucionales pendientes

Autoridad inicial que aprueba mandatos, evidencia de competencia profesional, catálogo funcional, vigencias de facultades reales, suplencias, excepciones y procedimiento de aprobación/revocación de facultades. B2.1 no implementa esos actos. Un retiro aquí retira una propuesta; no representa revocación de una competencia vigente.

Una identidad o fundamento revocado/retirado impide nuevas actuaciones, incluido el retiro de un expediente dependiente; su historia permanece consultable. Cualquier mecanismo adicional de cierre administrativo tras perder el fundamento requerirá autorización específica y no se presupone en este incremento.

## Archivos exclusivos

1. `backend/cuentas/modelos_acreditaciones_emisoras.py`
2. `backend/cuentas/models.py`
3. `backend/cuentas/servicios_competencias_emisoras.py`
4. `backend/cuentas/migrations/0010_mandatos_acreditaciones_b2_1.py`
5. `backend/cuentas/migrations/0011_guardias_mandatos_acreditaciones_b2_1.py`
6. `backend/cuentas/tests/test_acreditaciones_emisoras.py`
7. `scripts/verificar_acreditaciones_emisoras_b2_1_estatico.py`
8. Este documento.

Sin cambios en B1, React, biblioteca, deportistas, sesiones, settings o ejecutor. Sin conexión a `zona_bloque`, migraciones operativas, commit ni push. Publicación y B2.2 pendientes de autorización.
