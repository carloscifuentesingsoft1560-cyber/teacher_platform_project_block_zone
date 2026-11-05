# F3.6-B2.3 — Expedientes funcionales individuales pendientes

Base: `interfaz-sesiones-react`, `19dddc1faeb3034b1f209f08e8750364c03eb894`.
**Exclusivamente escenario A. Pendiente de revisión; sin aprobación institucional.**

## Límite funcional

Las siete entidades conservan propuestas individuales, revisiones documentales y retiros.
No emiten autorizaciones profesionales, no determinan aptitud ni conceden derechos. No hay
estados de aprobación/vigencia operativa, endpoints, consultas docentes ni integración
con validación institucional. B1/B2.1/B2.2 permanecen antecedentes propuestos.

El consentimiento del acudiente, la matrícula, la evaluación pedagógica, la restricción
funcional propuesta, la autorización profesional y la validación de sesión son conceptos
distintos. No se transforma ni importa `Autorizacion` como autorización funcional.

## Entidades

- `ExpedienteAutorizacionFuncional`: UUID, deportista, Persona, disciplina y snapshot del
  enlace acreditado (FK, versión y evidencia). No copia nombres/documentos ni crea identidades.
- `PropuestaDecisionFuncionalVersion`: número/antecesora, acreditación B2.1 y evento exacto,
  emisión declarada opcional y periodo propuesto finito. No acredita una emisión profesional.
- `AlcanceDecisionFuncional`: perfil versionado y evento exactos; correspondencia versionada
  y evento opcionales, siempre del mismo perfil. Un perfil por versión individual; si hay
  varios destinos del mismo perfil se requiere ampliar este diseño antes de agregarlos.
- `CondicionDecisionFuncional`: referencia a condición del perfil con modalidad propuesta
  condicionar/excluir. No hay diagnósticos ni restricciones individuales en texto libre.
- `AdaptacionDecisionFuncional`: adaptación del catálogo y condición individual explícitas;
  no permite superar una exclusión ni importar adaptaciones de otro perfil.
- `ReferenciaEvidenciaFuncional`: UUID v4 opacos de evidencia y registro de custodia, más
  huella SHA-256 declarada. No almacena el documento, URL, ruta, nombre o diagnóstico.
- `EventoExpedienteFuncional`: secuencia global del expediente, versión, propuesta/revision/
  retiro, actor/persona/enlace históricos, clave idempotente y huella de solicitud.

Las solicitudes completas no se conservan: se calcula su huella canónica sin copiar valores
sensibles al historial. La auditoría general solo registra entidad, identificador, actor,
acción y nombres de campos `accion`/`numero`. No existen motivos de texto libre.

## Custodia documental y privacidad

No se crean permisos genéricos Django, ni siquiera view. No se reutilizan es_gestor ni
permisos del repositorio pedagógico. Los comandos internos exigen rol administrativo vigente,
identidad acreditada y ser exactamente el registrador histórico de la acreditación B2.1
referenciada, con la misma persona. Otro administrador no puede actuar por su mero rol.
Esto limita el registro documental interno; no define una política aprobada de consulta,
descarga o acceso clínico. No hay endpoints ni funciones de listado de este dominio.

La persona destinataria debe ser distinta del registrador, del emisor propuesto B1 y del
titular del mandato. Se compara Persona, no nombres ni roles. Revocar identidad impide
nuevas propuestas/revisiones; el retiro documental sigue permitido al custodio identificado.

La integridad SQL garantiza la existencia de la referencia interna, no la autenticidad ni
la existencia del archivo externo. El registro externo de custodia y su política de acceso
continúan pendientes; no se crea un almacén de evidencia ni se afirma evidencia verificada.

## Integridad e historia

FK PROTECT, índices de identidad/disciplina y relaciones, unicidad de números y claves,
antecesoras uno-a-uno, checks de intervalos y huellas. El expediente no cambia de persona,
deportista ni disciplina. Versiones y eventos son consecutivos, sin bifurcaciones.

Los triggers propios rechazan UPDATE/DELETE en las siete tablas. Las guardias ORM heredadas
rechazan save de existentes, delete, update y bulk_update. El primer evento sella detalles.
Constraint triggers diferidos exigen primera versión, evento de propuesta, alcance,
referencia de evidencia y auditoría mínima antes de confirmar. Toda operación es atómica.

Las nuevas actuaciones comprueban el evento B2.1 más reciente, identidad y fundamentos B1/
mandato exactos, intervalos propuestos, disciplina, perfil actual y correspondencia exacta.
Un fundamento retirado, sustituido u obsoleto no se reutiliza. El retiro del expediente es
terminal y no depende de que el fundamento continúe vigente, para conservar salida segura.

Las escrituras siguen el bloqueo global de usuarios compartido con B1/B2.1/B2.2, luego
identidades y cabeceras. Esto serializa carreras con cambios de roles e identidad, con
contención conocida. Versión esperada y clave/huella idempotente rechazan cambios obsoletos
y claves reutilizadas con otro contenido. No se interpretan timeouts/deadlocks como éxito.

## Temporalidad

Se usan DateTime con zona e intervalos propuestos `[desde, hasta)`, fin mayor que inicio.
La emisión declarada no puede ser futura ni posterior al comienzo propuesto. El periodo
debe quedar dentro de los antecedentes propuestos. Registro/creación son tiempos fijados
por PostgreSQL. Puede documentarse un antecedente histórico; nunca resulta cobertura real,
retroactiva o presente. La sustitución es una nueva versión completa; el retiro no borra
antecedentes. Revocaciones profesionales y resolución operativa de conflictos no existen
en A y requieren escenario B aprobado. Propuestas concurrentes no conceden permisos.

## Migraciones

`0004_expedientes_funcionales_b2_3` añade las siete entidades y restricciones. Depende de
deportistas 0003, cuentas 0011 y biblioteca 0005, además de organización/usuario. No altera
tablas anteriores ni migra consentimientos. El grafo se valida sin conexiones antes de SQL.
`0005_guardias_expedientes_funcionales_b2_3` añade exclusivamente funciones/triggers B2.3.
Es deliberadamente irreversible: no se permite retirar guardias dejando historial existente.
No habilitar una instalación parcial hasta 0004. No se modifican migraciones históricas.

## Verificación

Suite específica preparada: 32 pruebas de fixtures ficticias. Reutiliza helpers de B2.1/B2.2,
sin heredar sus clases de pruebas ni ejecutar suites ajenas. Cubre identidad/separación,
custodia específica, referencias, historial, auditoría, fechas, retiro, rollback, concurrencia
real, idempotencia y bloqueo de realizada, así como guardias anteriores. No es regresión completa.
Resultados de la primera ronda autorizada:

- 0004 generada sin SQL ni settings del proyecto. Verificador estático satisfactorio:
  siete archivos Python, siete modelos, 35 guardias ORM, ausencia de permisos genéricos,
  grafo acíclico y `No changes detected` con backend dummy y conexión prohibida.
- Barreras de aislamiento: 24/24 satisfactorias, una ejecución, 0.913 segundos.
- Única ronda PostgreSQL: 32 pruebas descubiertas; una ejecutada con error, cero aprobadas,
  cero fallos de aserción y 31 sin ejecutar. Django informó `Ran 1 test in 2.662s`,
  `FAILED (errors=1)`. No hubo omisiones declaradas; las restantes no llegaron a ejecutarse
  por failfast. No se repitió la ronda ni se corrigió código tras el fallo.
- Las migraciones anteriores y deportistas 0004/0005 se aplicaron correctamente en la base
  nueva `test_zdb_fase3_955fda9f3a3f`. Esto no acredita el funcionamiento de los triggers:
  la primera propuesta falló al insertar su condición individual.
- Defecto de implementación: en `zdb_b23_guardia`, la variable PL/pgSQL `a` tiene tipo
  `cuentas_acreditacionemisora`, pero una subconsulta utiliza también `a` como alias de
  `deportistas_alcancedecisionfuncional`. Al evaluar `a.perfil_version_id`, PostgreSQL
  resuelve el registro PL/pgSQL y produce `UndefinedColumn` (SQLSTATE 42703), propagado como
  `django.db.utils.ProgrammingError`. No es un rechazo esperado de integridad ni un éxito.
  Requiere revisión/autorización antes de corregir la nueva guardia SQL.
- El chequeo posterior con PostgreSQL de modelos/migraciones no se ejecutó por el error.
  El `No changes detected` anterior corresponde exclusivamente al análisis estático.
- Evidencias conservadas: `C:\Users\57310\AppData\Local\Temp\zdb_pg_ajolezzl`.
  Host 127.0.0.1, puerto 55455, PID hijo 7252. `resultado.json` registra pruebas=1,
  migraciones_check=null, detenido=true, identidad revalidada, pg_ctl solicitado,
  sin terminación forzada ni incidentes. La base de prueba se destruyó; el directorio
  temporal y sus logs se conservaron, sin reutilizar ni alterar evidencias previas.

La primera ronda no validó la implementación: inmutabilidad SQL, rollback, concurrencia,
compatibilidad y bloqueo de realizada quedaron pendientes al detenerse en la primera prueba.
Las protecciones anteriores permanecieron sin modificar. No se accedió a zona_bloque ni se
habilitó ningún permiso operativo.

### Corrección mínima y segunda ronda autorizada

La revisión completa de 0005 confirmó la colisión dentro de `zdb_b23_guardia`. Se cambiaron
solo cinco líneas: declaración y dos usos de la variable de acreditación `a` pasan a
`v_acreditacion`; el alias de alcance `a` y sus dos referencias pasan a `alcance`. Los usos
de `a` en las otras funciones son independientes y se conservaron. No se alteraron condiciones,
referencias, errores, bloqueos, triggers ni política de reversión. No se modificaron modelos,
servicios ni pruebas; la corrección y este historial afectan únicamente 0005 y este documento.

Resultados de la nueva autorización, sin repetir automáticamente ninguna ronda:

- Verificador estático satisfactorio: siete archivos Python, siete modelos, 35 guardias ORM,
  sin permisos genéricos, grafo acíclico y `No changes detected` sin conexión. Diff revisado:
  exclusivamente los identificadores indicados; sin cambios de significado.
- Barreras: 24/24 aprobadas en una ejecución, 1.243 segundos.
- PostgreSQL temporal nuevo: 32 pruebas descubiertas y ejecutadas, 32 aprobadas, cero fallidas,
  cero errores y cero omitidas, en 77.215 segundos. Base `test_zdb_fase3_c90db95c4257`.
  Se aplicaron las migraciones anteriores y deportistas 0004/0005. Pasaron identidad y
  separación, custodia específica, referencias B1/B2.1/B2.2, condiciones/adaptaciones,
  temporalidad, inmutabilidad ORM/SQL, eventos y auditoría obligatorios, retiro terminal,
  rollback, idempotencia y concurrencia real. Las pruebas 28/29 comprobaron el bloqueo
  Python/SQL de `realizada` y las guardias de los incrementos anteriores. No hubo regresión
  completa ni se habilitó una autorización profesional o institucional operativa.
- Chequeo posterior en el entorno aislado: `No changes detected`, código 0.
- Evidencias nuevas: `C:\Users\57310\AppData\Local\Temp\zdb_pg_e9s3e5ja`.
  Host 127.0.0.1, puerto 61299, PID hijo 14712. `resultado.json`: pruebas=0,
  migraciones_check=0, detenido=true, identidad revalidada, cierre solicitado mediante
  pg_ctl, sin terminación forzada ni incidentes. La base se destruyó y el clúster hijo
  quedó detenido. Se conservaron las evidencias de ambas rondas, sin reutilizarlas.

Se utilizó `-X utf8 -I -B` para el ejecutor y variables PYTHONIOENCODING/PYTHONUTF8;
las barreras se invocaron con `-B`, sin `-I`. No se cambió el ejecutor ni su aislamiento.
La publicación permanece pendiente de revisión y autorización. Sin commit/push ni B2.4.

Solo después de estática, correspondencia modelos/migraciones y 24 barreras satisfactorias:

```powershell
$pythonPruebas = 'C:/Users/57310/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:ZDB_PAQUETES_PYTHON = 'C:/Users/57310/Desktop/Proyectos_Carlos/teacher_platform_project_block_zone/.venv-local/Lib/site-packages'
$env:ZDB_LIBPQ_DIR = 'C:/Program Files/PostgreSQL/17/bin'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
& $pythonPruebas -X utf8 -I -B scripts/pruebas_postgresql_aisladas.py --etiqueta deportistas.test_autorizaciones_funcionales --failfast --verbosity 2
```

El ejecutor existente crea clúster, base y evidencias nuevos fuera del repositorio y respaldos,
sin .env ni credenciales heredadas. Verifica manifiesto/PID/directorio/host/puerto y su propio
Popen; solo detiene el hijo confirmado y conserva evidencia. No utiliza zona_bloque.

## Archivos y pendientes

Únicamente modelos_autorizaciones_funcionales.py, models.py, servicios_autorizaciones_funcionales.py,
migraciones 0004/0005 y test_autorizaciones_funcionales.py dentro de backend/deportistas;
scripts/verificar_autorizaciones_funcionales_b2_3_estatico.py y este documento.

Pendientes: autoridad aprobadora, competencia profesional operativa, catálogo aprobado,
custodia sensible y política de acceso, representación de restricciones individuales no
expresables por el catálogo, varios destinos por perfil, revocaciones profesionales y
conflictos entre decisiones reales. Ninguno se resuelve activando propuestas ni por rol.
Se mantienen intactos verificar_autorizacion_funcional(), los triggers de realizada, planes
sellados y ejecuciones finalizadas. Sin commit/push; no se avanza a B2.4.
