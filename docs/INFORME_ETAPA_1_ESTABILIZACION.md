# Informe de Etapa 1 — estabilización y reutilización

Fecha: 2 de noviembre de 2026. Alcance autorizado: documentación, pruebas e infraestructura de desarrollo reversibles. Se completó esta entrega sin implementar módulos deportivos ni cambiar facultades de negocio, modelos o migraciones. La aplicación conserva tres roles exclusivos y ejecución de ascensos compartida entre coordinador y administrador hasta una entrega posterior autorizada.

## Resultado y archivos de entrega

| Archivo | Cambio y motivo |
|---|---|
| scripts/pruebas_postgresql_aisladas.py | Argumentos permitidos explícitos; retirada de generación opcional de migraciones; entorno libpq saneado, credenciales ficticias, verificación de clúster/PID, registros completos y resultado JSON; apagado en finally |
| backend/configuracion/settings_pruebas_postgresql.py | Barrera previa a .env que rechaza ejecución sin directorio/puerto/base temporal identificados; no modifica settings operativos |
| scripts/django_local.py | Docstring remite al procedimiento vigente; lógica operativa intacta |
| scripts/test_infraestructura_aislada.py — nuevo | Cinco pruebas de barreras sin abrir PostgreSQL ni consultar datos reales |
| docs/PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md — nuevo | Comandos reproducibles con Python existente, requisitos, diagnóstico, evidencia y límites |
| docs/RECONCILIACION_VIGENTE_2026_11.md — nuevo | Diferencias históricas, precedencia de decisiones, snapshot previo y propuesta segura de Git |
| docs/CONTRATOS_COMPARTIDOS_FUTUROS.md — nuevo | Identidad/ámbito, versiones, transacciones, sesión única, asistencia, evaluación, planificación, restricciones, carga, bloques, medios y anotación humana; propuestas sin implementación |
| docs/PROPUESTA_ETAPA_2_NUCLEO_INSTITUCIONAL.md — nuevo | Dependencias por capa, identidad/roles, cargo único, matriz de ascensos, incrementos, pruebas y decisiones pendientes |
| README.md | Aviso vigente, resultados actuales y enlaces; cuerpo histórico conservado |
| docs/DECISIONES.md | Aviso de vigencia y alcance más reciente de Etapa 1 |
| docs/ARQUITECTURA.md | Enlace a arquitectura auditada y contratos propuestos, diferenciados de implementación |
| docs/MATRIZ_PERMISOS.md | Distingue permisos actuales de objetivo futuro multirrol/ascensos |
| docs/IMPORTACION_EXCEL.md | Advertencias de auditoría y contrato de procedencia sin importar datos |
| docs/REPOSITORIO_REMOTO.md | Distingue inspección histórica de estado actual desconocido del remoto |
| Este informe — nuevo | Resultados, límites, continuidad y siguiente etapa |

No se modificaron fuentes funcionales de frontend, modelos, serializers, vistas, permisos, servicios de negocio, dependencias, package-lock, .env, referencias Excel o migraciones históricas. Los artefactos dist de build y evidencia de pruebas son locales. La auditoría de Fase 0 se conserva sin reescribir sus conclusiones o su punto de parada histórico.

## Control de versiones y conservación

Antes de cambiar código se verificó ausencia de Git y se creó snapshot de 281 archivos con manifiesto SHA-256 en `respaldos/linea_base_etapa1_20261102T170826Z/`. El ZIP excluye secretos, bases, medios y documentos privados; no equivale a respaldo operativo. El [registro de reconciliación](RECONCILIACION_VIGENTE_2026_11.md) identifica el hash y el plan de integración futura en carpeta separada.

No se inicializó Git ni se consultó/sincronizó el remoto. El delta se determina por hashes contra el snapshot, no por git diff. La restauración debe ser por archivo revisado; no sobrescribir cambios posteriores. Las migraciones y fuentes funcionales deben conservar su hash previo; el settings de prueba es la única modificación dentro de backend.

Verificación final de conservación ejecutada: nueve archivos previos modificados, ninguno eliminado; todas las migraciones históricas y fuentes de frontend conservan su hash. Se verificó integridad de las 281 entradas del ZIP contra el manifiesto, sintaxis Python de la infraestructura y enlaces de los nuevos documentos/README. Se añadieron seis archivos de entrega (cinco documentos y la prueba de infraestructura). Delta privado de archivos previos en `respaldos/linea_base_etapa1_20261102T170826Z/delta_etapa1.json`.

## Pruebas ejecutadas en esta entrega

| Prueba | Resultado comprobado |
|---|---|
| scripts/test_infraestructura_aislada.py | 5 pruebas aprobadas: argumentos permitidos; overrides rechazados; generación rechazada antes de crear clúster; entorno libpq saneado; settings directos rechazados |
| Suite backend en PostgreSQL temporal | 505 pruebas aprobadas en 182,918 segundos; system check sin incidencias |
| makemigrations --check --dry-run en clúster temporal | No changes detected; sin generación de migraciones |
| Limpieza del clúster | Base de prueba destruida por Django; proceso PostgreSQL temporal detenido, `detenido: true` |
| Frontend Vitest | 12 archivos, 150 pruebas aprobadas |
| Cliente HTTP node:test | 6 pruebas aprobadas |
| Build Vite | Aprobado, 74 módulos; mismos nombres/hash de bundles que en Fase 0 |

Evidencia backend: `respaldos/pruebas_etapa1_rj57_f4j/`, con initdb.log, servidor.log, pruebas.log, migraciones_check.log y resultado.json. Resultado de pruebas y chequeo: código 0. Python 3.12.14; puerto efímero 49780. Los logs son privados, no se adjuntan a un remoto automáticamente. La última revisión de textos/encoding y PYTHONIOENCODING para futuras ejecuciones no cambia reglas de negocio; se verifica de nuevo con las pruebas de barreras.

El comando PowerShell `.ps1` de conveniencia ensayado inicialmente fue bloqueado por ExecutionPolicy; se retiró el archivo nuevo y se dejó el procedimiento de invocación directa de Python. No se alteró la política del sistema. No hay un wrapper pendiente que el usuario deba habilitar.

No se ejecutaron pruebas sobre la base operativa, login real, migraciones operativas, pentest, auditoría externa de dependencias, validación de contenido científico, dispositivos móviles ni nueva revisión visual. Las cifras aprobadas no acreditan módulos aún inexistentes. Se conservan como pendientes las advertencias de despliegue de Fase 0; no se cambió configuración local de HTTPS o DEBUG.

## Requisitos abordados y reutilización

Se cubren las seis prioridades de esta autorización: línea base segura propuesta y preservada; prueba PostgreSQL reproducible; reconciliación documental sin borrar historia; contratos futuros comunes; inventario de roles/ascensos sin ejecutarlo; regresión del núcleo existente.

Se reutilizan django_local.py, binarios y paquetes locales, suite existente, clúster temporal y patrones de evidencia en respaldos. Los contratos conservan Usuario/Deportista/Acudiente/Inscripcion/Grupo y ProgresionInstitucional; no proponen catálogo paralelo de bloques ni sesiones duplicadas. La dependencia de restricciones funcionales antes del planificador queda explícita.

## Decisiones pendientes y Etapa 2

La [propuesta detallada](PROPUESTA_ETAPA_2_NUCLEO_INSTITUCIONAL.md) divide el trabajo en matriz de facultades, identidad/roles aditivos, separación de ascensos y auditoría/autorizaciones. Antes de modificar estructura deben concretarse:

- Identidad transversal y acreditación de enlaces entre cuentas, deportistas y acudientes, sin fusiones automáticas.
- Pertenencias de rol y transición del campo rol, cargo coordinador único y relevo que no desactive otras facultades por accidente.
- Preparación de revisión administrativa y formalización exclusiva administrativa de ascensos, incluyendo SQL/triggers y todos los consumidores del helper autorizado.
- Tratamiento de una persona que tenga roles coordinador y administrador: separación por facultad o exigencia expresa de dos personas. No se ha inventado una prohibición.
- Finalidades, retención y permisos de consulta/publicación; los tipos y consentimientos no se rellenan automáticamente.
- Reconciliación del remoto y estrategia de historial Git antes de primer commit/sincronización.

Etapa 2 requerirá diseño concreto revisable, migraciones nuevas probadas solo en destino aislado, pruebas multirrol/IDOR/revocación/concurrencia y conservación de IDs e históricos. La aplicación a base operativa y cualquier despliegue quedan fuera de esta autorización.

**Punto de continuidad:** entrega de Etapa 1 completada dentro del alcance autorizado; Etapa 2 únicamente propuesta. No se han iniciado cambios estructurales ni módulos deportivos. Para repetir las verificaciones usar la [guía PostgreSQL aislado](PRUEBAS_BACKEND_POSTGRESQL_AISLADO.md), sin ejecutar scripts aplicar_*.py.
