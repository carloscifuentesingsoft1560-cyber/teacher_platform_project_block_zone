# Aplicación controlada de migración de ascensos B1

Estado: APLICADA Y VERIFICADA.

- Inicio UTC: 2026-10-29T23:41:32.466587+00:00
- Inicio Colombia (UTC-05): 2026-10-29T18:41:32.466587-05:00
- Fin UTC: 2026-10-29T23:41:34.594154+00:00
- Conexión efectiva de `scripts/django_local.py`: `zona_bloque`, `public`, `127.0.0.1:5432`, PostgreSQL 17.11.
- Migración exclusiva: `inscripciones.0002_progresioninstitucional_eventoprogresion_and_more`.
- SHA-256 de la migración auditada: `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`.
- Aplicación confirmada por commit: True. Estado real posterior: True.
- Código/modelos/migraciones auditados sin cambios de archivo: True.

## Respaldo y recuperación

- Respaldo existente: `respaldos/preparacion_b1_20261029T232105Z/zona_bloque_pre_b1_20261029T232105Z.dump`.
- Tamaño: 164565 bytes.
- SHA-256 comprobado: `cf81d354fd0bb9ef1c79c6012e379c92688db9d4b5bcd0a9f731a66d3787acfb`.
- Manifiesto anterior revisado: estado restaurado/verificado; lectura completa, 32 tablas/249 registros, funciones/triggers y migraciones contrastados; 14 GET satisfactorios en clúster aislado eliminado.
- Incidencia histórica de CHECK: las diferencias de representación se comprobaron por reparseo en PostgreSQL. No se reinterpretaron reglas institucionales.
- No se restauró sobre la base real. Revertir B1 elimina sus datos si ya existen; requiere preservación y autorización posterior, nunca una reversión automática.

## Fases 1 y 2: verificaciones y SQL

- Única pendiente antes de aplicar: B1; 29 migraciones previas.
- Respaldo íntegro y evidencia de restauración comprobados antes de escribir.
- Actividad previa: [] sesiones ajenas; sin transacciones prolongadas/preparadas ni bloqueos incompatibles en la ventana validada.
- Definición: 17 operaciones (4 CreateModel, 1 AddIndex, 10 AddConstraint, 2 RunSQL), 4 funciones y 6 triggers; dependencias ya aplicadas.
- SQL generado con `sqlmigrate`, únicamente inspeccionado. SHA-256: `d152bbb6e7b6025ebf6c33e5ab4ebe50a3b81fc9577e5a1c17eb7520621377e1`.
- SQL inverso inspeccionado. SHA-256: `9c8c96260c6bd0e5216769563b6ff1a7fa562a2755d392d68e2f12b854b316d3`.
- Sin DML ni eliminación/renombrado inesperados hacia adelante; nombres públicos sin colisiones. Atomicidad Django conservada.
- Comprobaciones previas: No changes detected; System check identified no issues (0 silenced).

## Fase 3: aplicación

- Ejecutada desde el entorno local con `scripts/django_local.py shell` y `MigrationExecutor.migrate([objetivo], plan=plan_exclusivo)`; no se utilizó migrate sin objetivo.
- No se ejecutaron señales post_migrate: no se crearon content types ni permisos de modelos. La Única modificación a datos anteriores es la fila autorizada en django_migrations.
- Transacción externa atómica; lock_timeout 5 s, statement_timeout 120 s, idle_in_transaction_session_timeout 60 s. Bloqueos SHARE de tablas previas con NOWAIT durante la ventana; no se desconectó ninguna sesión.
- Inventario inmediatamente anterior: 2026-10-29T23:41:33.682018+00:00.
- Commit: 2026-10-29T23:41:34.422476+00:00.

## Fase 4: verificación

- Resultado de objetos: {"tablas": 4, "filas": 0, "funciones": 4, "triggers": 6, "restricciones_dominio": 13, "claves_foraneas": 18, "indice_explicito": "CREATE INDEX ascenso_persona_disciplina ON public.inscripciones_progresioninstitucional USING btree (deportista_id, disciplina_id, estado_decision)"}.
- Cuatro tablas nuevas: `inscripciones_progresioninstitucional`, `inscripciones_eventoprogresion`, `inscripciones_afectacioninscripcion`, `inscripciones_excepcionpedagogica`.
- Funciones en public: `zdb_validar_ascenso_b1`, `zdb_historial_ascenso_inmutable`, `zdb_nivel_ascenso_estable`, `zdb_revocacion_ascenso_auditada`.
- Triggers: `zdb_progresion_coherente`, `zdb_afectacion_coherente`, `zdb_excepcion_coherente`, `zdb_evento_ascenso_inmutable`, `zdb_nivel_ascenso_estable`, `zdb_revocacion_ascenso_auditada`.
- Se verificaron cuerpos de funciones contra la migración, SECURITY INVOKER/search_path, habilitación/tipo/tabla de triggers y diferimiento del historial de revocación.
- Comparación anterior/posterior: True. Se comparan columnas/defaults/restricciones/índices y registros. Solo se excluye de la comparación la nueva fila autorizada de django_migrations.
- Inventario global de funciones y triggers previos conservado, excluyendo únicamente los nuevos objetos B1.
- Estados operativos previos conservados: {"inscripciones_inscripcion": [["activa", 1]], "inscripciones_propuesta": [], "deportistas_deportista": [["activo", 1]], "organizacion_grupo": [[true, 1]]}.
- Comprobaciones posteriores: System check identified no issues (0 silenced).; No changes detected.
- Migraciones pendientes al cierre satisfactorio: ninguna. No se crearon progresiones, afectaciones, excepciones ni eventos B1.

## Inventario de tablas anteriores

Las huellas se calculan sobre filas completas serializadas por PostgreSQL y ordenadas. No se incluyen datos personales en este informe. La huella de estructura cubre columnas, defaults, restricciones e índices. Django_migrations pasa de 29 a 30 filas; su comparación conserva las 29 originales excluyendo solo B1.

| Tabla | Filas antes | Filas comparadas después | SHA-256 registros originales | SHA-256 estructura | Coincide |
| --- | ---: | ---: | --- | --- | --- |
| auditoria_cambioadministrativo | 14 | 14 | `5bc5e4d1f4c208ee98597616595e4189e9089fff8f335db78a136f602337c11b` | `b75fa290cede98a00ea88957dd571dc853fa5093289979c8317ee93d3528b627` | True |
| auth_group | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `a39fd8b6acc31404fbb541b4ffd57c49b7197a5b4ad4803f667ae8b7a86ee262` | True |
| auth_group_permissions | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `45d28c9012a0d9ad082950189cf7e474ee6a0653539de8aa50dd5b5c08f73d10` | True |
| auth_permission | 109 | 109 | `a63d39a827835ca03c0ec8260ded71c9aa78ec6707a49945a33ff61509d7a57b` | `7e4e1be913017ab1aa0aa0104a8be1a3c18663ff4884a5a0c3f909a5b69a427e` | True |
| cuentas_eventoacceso | 29 | 29 | `76a3c74c6187082a4103ed705c1c8e2ba4d0cdb0276ab02525cf9cf250705cd1` | `54ee78f8cbb6c54f58cb0418ca588debfe4b14296a30af8e86cfc6abe3320a1c` | True |
| cuentas_solicitudrestablecimiento | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `899a941bf2912b7b5d88ecc6d78669bf9faf95c3beb424f9eedd9659c437fe5e` | True |
| cuentas_usuario | 3 | 3 | `af79fb5624bbbdd30dbcca65bb580b66b58e3eddb1c0ace48480dbf8a8ca10c3` | `0f0af7cbd7b7782f1c41a0c37ec8b57dba259076a58d204fcf8b6abadb76b273` | True |
| cuentas_usuario_groups | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `da3876deb255cfcd89a66f0a39d34092b4d15013a171448dd07c63b52af6adda` | True |
| cuentas_usuario_user_permissions | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `0c08aa9a4eabfe4bcdd0be942f3839f5ed911fa88ea45fc7a8e03c8c1ae353e9` | True |
| deportistas_acudiente | 1 | 1 | `57a2601fb378e1fb490b2382262e8d9209225c00ff03e70f55f27b1bb4690008` | `e2a95df8317894b47530d02dbf9646c566936a34184e6dfdd7aeba6a4b1c60fa` | True |
| deportistas_autorizacion | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `f5fadf4f1f9339fbd56362d1f6c4fc2d8a2c674d6a381704bb07464ba02188f7` | True |
| deportistas_cambiodocumentodeportista | 1 | 1 | `6eed2c0370d8247bdac09a65a8ef46bdbe17871bc4c83711e74964ab00c5212e` | `35a97236dadd9a3f7b91a543e20f6215b68c10d1a16a70aa1ef8c4d98874bfe2` | True |
| deportistas_comprobacionfacultad | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `68c86f3e39cded9a49329fa0cd9a8eac6ba71d25a9cfe45a0de0bd80f584c6e0` | True |
| deportistas_deportista | 1 | 1 | `953b146602f87eccf63f1f6fb6542bc3b1477f671160d5cbe2bf38f66e8ac5c0` | `02d9a667fce0f5e7bb18c7196d92bdbd8ff3c83504fd4ba45266ea2ae9a22ef1` | True |
| deportistas_politicadatos | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `77879d5cfcee8cf068d142384050420aeb47a298266f50740a72640828803c56` | True |
| deportistas_tipoautorizacion | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `90adb256f049c76f3d12ad804dfd3957bc9841984505b930d0491c48f5ff9154` | True |
| deportistas_tipodocumento | 7 | 7 | `625045fa20e22eac07ba6cab4330dbc0d902bb5398ded87c3a5049ed915419ea` | `612dc809d2b3693f40b5b6ad1a05d07e166a18aa29cd7925b40d86a329065097` | True |
| deportistas_vinculoacudiente | 1 | 1 | `2ed8625966bd20e5cfded69582ab1b1e5c86922f08439158b2d7bbbc09652ce1` | `111e51e6885cb5191a1a6f37b0c431cf195bc5d1c7eb6bce5ec8597dbcc2f719` | True |
| django_admin_log | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `bdcfaaa5c8111e43bcc99780612c7049f6ec3e2b15c885da365a90ac498111ef` | True |
| django_content_type | 28 | 28 | `0395902b3380a03fb672e01a2eac4a291a6d11afa8fe52008915978ca22de9b1` | `f34f9b9ccf08f0d0729ef2a81ca7b86eb6e1d9771fc5f06958a6f8e7eeb2817d` | True |
| django_migrations | 29 | 29 | `0cf1b7b843c1cf05cbf7534e86a816648334155f8e0f83f5784a87dc4884bf18` | `3f04b31577dcd3110d266b3df933d63e1d05bc834fb1964f775b10be939540af` | True |
| django_session | 8 | 8 | `ac588a968ca8f1cb23f539f64fe56dacfdd52ef1869b0b2fdf46f70e829dce43` | `58e986a4bd769e508db378ffc70a04e3cf70d9564dfbe62c8539528426dfbc12` | True |
| inscripciones_eventoinscripcion | 3 | 3 | `12738fbf3e5b40938773ec31ed6ea519ea2c1001f31411bae2afc4d00ccc40bc` | `bc5f97a77979455684a8e22f65519ae6bda1f219f2d2caa60a57197951b9747e` | True |
| inscripciones_inscripcion | 1 | 1 | `64805fdac13d8674763109135d7b05b72075fdb2a17a6a8a04c2b9c13b3868a3` | `6f6ca701c69b8396bcebe02c39447a5d42d9ff70bfd54554035ef8c6eeab1dda` | True |
| inscripciones_propuesta | 0 | 0 | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `581de7a72ee2c13fd36d5b328f89aed3bd254c8d23211f39da8c28dee0cc4062` | True |
| inscripciones_reservacupo | 1 | 1 | `9108593a5d22297c71d80df1c20f114a9ecce52779e535d6bf196d7fc0774443` | `972df07503933c2e864854f34ad9c45b6527c41513e35bc99d98f0ffa1b006c5` | True |
| organizacion_asignacion | 2 | 2 | `01a8666c2ba7be3962da9f92611a17bfdfb70d69bd2615dbfb4f71d28757d94c` | `407d473c8493c02d31310a2b2a3598cb7a57aafe45d6b6553c4bbeea920308bd` | True |
| organizacion_disciplina | 1 | 1 | `44636271feef092eb09e39056872e8422bd639c4f41e1644e69f4a0106d6d26c` | `1af9db2bc8dfedffd9a2e2db06fc2a9e3fd3fee57395995204774e4b476b090c` | True |
| organizacion_grupo | 1 | 1 | `5061787afb2e9f57349ea106eb46119566adb111b38e23bd57cc91a45e7507f4` | `bd736dc8cba9df35c396083354e320b8835af0ba9c60d3b3a70759f083c9eae3` | True |
| organizacion_horario | 3 | 3 | `976ef1ee5d7f4ed3b1534e3681675141711e83e97413bdc90b7d1ccbcb476255` | `4aa193e033e11740f91508931f2aeb644a3cbd9c2f2705555a8dc91e7a4fd5aa` | True |
| organizacion_nivel | 5 | 5 | `caf2215e753b81b0f0f9b12cd82d39b926dc40bf33deb4dd973b99fa19982155` | `3b84f09cea09294732fea3e2edd0c8326a93c280dab52582888b0711a38b4505` | True |
| organizacion_periodo | 1 | 1 | `06ac7bd9a24da8813bea4b9d242086e3dd8aae2c908207ce9b1772a403759e43` | `08785cdc76f738d29a64c42801c8b6727b386bd234c16e56212cb820cc1fab55` | True |

## Incidencias y límites

- Sin incidencias durante la aplicación. No se ejecutaron pruebas con escrituras en producción. Se usaron inventarios de solo lectura antes/después; la regresión aislada previa de 319 pruebas permanece documentada, no se afirma una nueva ejecución de esa suite en esta aplicación.
- No se modificaron roles, credenciales, usuarios, permisos, inscripciones, cupos, reservas o propuestas; no se crearon ascensos.
- No se realizaron commits/push ni se iniciaron B2/B3. Único archivo creado en este encargo: este informe.
