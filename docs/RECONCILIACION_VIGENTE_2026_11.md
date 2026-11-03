# Estado vigente y reconciliación — noviembre de 2026

Registro de Etapa 1. Se conserva la documentación original como evidencia histórica. Este documento resuelve su lectura; no reescribe resultados ni autorizaciones pasadas.

Orden de interpretación: instrucción explícita más reciente del propietario → decisiones institucionales posteriores documentadas → contratos implementados y comprobados para describir el comportamiento actual → planes y propuestas históricas. Un requisito aprobado para desarrollo no implica que esté implementado ni aprobado científicamente.

| Tema y fuente histórica | Estado vigente | Tratamiento |
|---|---|---|
| Auditoría Fase 0, Etapa 1 proponía corregir autoridad de ascensos | La autorización de esta sesión exige solo identificar/documentar ese cambio | No modificar autoridad, roles, servicios ni SQL de ascensos en Etapa 1 |
| Prompt maestro antiguo: tres roles y sin portales | Nuevo maestro prevé seis roles y roles múltiples | Objetivo futuro; actualmente se mantienen tres roles exclusivos y ningún portal |
| DECISIONES/ARQUITECTURA/MIGRACION_COORDINADOR_UNICO: referencias a índice pendiente | Informe de aplicación posterior y lectura Fase 0 acreditan cuentas.0004 aplicada | No volver a aplicar ni falsear migraciones. Etapa 1 no consulta ni altera base real |
| Supervisión por parejas o grupos delegados | Decisión posterior: coordinador único activo para toda la institución | Conservar cargo único; no crear jerarquía paralela |
| README: 271 backend/88 frontend y “sin ascensos” en entregas antiguas | Fase 0 ejecutó 505 backend/150 frontend/6 HTTP; B1–B3 implementaron ascensos | Cifras antiguas son históricas; resultados de Etapa 1 están en su informe fechado |
| README: SQLite como prueba completa | SQL/triggers de ascensos exigen PostgreSQL | Procedimiento vigente en PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md; conservar settings SQLite para usos compatibles |
| Comandos con ZDB_GENERAR_ASCENSOS | Vía retirada del ejecutor temporal | Rechazar variable; no generar migraciones en una prueba de regresión |
| Ejecutable .venv-local Python313 | Lanzador inaccesible en esta máquina | Runtime compatible existente y paquetes reutilizados; documentado, sin reinstalación |
| Coordinador/administrador ejecutan reubicaciones en B3 | Sigue siendo comportamiento actual; maestro nuevo reserva formalización a admin | Diferencia pendiente de Etapa 2, con permisos y SQL coordinados; no atribuir ya el cambio |
| Manual técnico de juegos y revisión piloto | Manual tiene 12 fichas; revisión/CSV contienen 16 títulos | Artefactos distintos; no homologar automáticamente ni publicar |
| Nombre de CSV “25 entradas” | Contiene 31 registros; catálogo unificado 224=193+31 | Conservar nombre y procedencia; fila candidata no equivale a ejercicio válido |
| F03/F05: 120 minutos por defecto | Nuevo maestro distingue Babys 40–45 y Lúdico aproximadamente 60, otros según grupo | Contrato futuro por programa; no cambiar horarios reales ni inventar malla Babys |
| F05: tiempo activo o sesión para carga | Nuevo maestro define sRPE con duración de sesión | Mantener tiempo activo separado; otra fórmula necesita otro indicador/protocolo |
| Excel con 80%, denominadores y descriptores por defecto | Originales preservados; fórmulas no aprobadas para calificar/ascender | No automatizar. Estados de ausencia, NA, interrupción y desempeño separados |
| F03: justificación de edición y revisión coordinadora | Autonomía ordinaria del profesor en nuevo maestro | Versionado automático, motivo proporcional cuando corresponde; sin aprobación previa universal |
| Calendario/grupos existentes | Calendario organizativo, sin entidades Sesion/Asistencia | No declararlo motor de planificación ni captura de sesiones |
| ExcepcionPedagogica | Permanencia temporal por progresión | No es restricción clínica, alta sanitaria ni adaptación RSD |
| UUID de evidencia en facultades | Referencia a custodia externa/institucional | No es sistema de subida/descarga ni autorización audiovisual o de IA |
| Notebooks ClimbVision-AI | Experimentos existentes, sin validación acreditada | IA operativa pausada; no ejecutar, descargar pesos ni añadir dependencias |
| Límites antiguos ambiguos de copias/semáforo/plazos | Sin decisión suficientemente precisa para programarlos | Pendientes por su etapa; no bloquear sesiones ordinarias con aprobaciones inventadas |

## Línea base y control de versiones

`git status --short` confirmó de nuevo que no existe repositorio Git local. No se conoce el diff contra un commit ni se ha verificado el remoto en esta etapa. Antes de editar código se creó `respaldos/linea_base_etapa1_20261102T170826Z/fuentes.zip` y `manifest.json`: 281 archivos fuente/documentales permitidos, con ruta, tamaño y SHA-256. SHA-256 del ZIP: `6cfe6f45c03e2d91af310574f5cd687964751b49d744b1f15f7d027fa6b963f6`.

Se excluyeron .env, credenciales, bases, medios, respaldos previos, entornos, dependencias, compilados y referencias privadas. El ZIP no es respaldo de base de datos ni prueba de completitud del remoto. Permite comparar y restaurar archivos puntuales de esta entrega; no descomprimirlo encima de cambios posteriores sin revisión.

Propuesta segura de Git, pendiente de ejecución: inspeccionar el remoto en una carpeta separada; comparar árbol e historial con manifiesto local; revisar .gitignore y archivos candidatos con atención a datos privados; escoger si el árbol local se integra en una rama del historial remoto o como línea base independiente documentada. Presentar diff y primer commit propuestos antes de sincronizar. No realizar clone sobre la carpeta actual, push forzado, git clean o sustitución de historial. No se necesita Git para ejecutar las pruebas de esta etapa.

## Continuidad

La documentación antigua se conserva; se añade aviso de vigencia a los puntos de entrada más usados. El informe original de auditoría permanece como foto de Fase 0. Las decisiones pendientes, resultados de pruebas y lista exacta de cambios de esta entrega se registran en INFORME_ETAPA_1_ESTABILIZACION.md. Los contratos futuros son propuestas de diseño, no endpoints existentes.
