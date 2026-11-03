# Etapa 4 — Incremento E: seguimiento pedagógico e informes

## Estado

Implementación técnica sobre el commit 75a1726.
Rama: funcionalidad-sesiones-asistencia.

## Funcionalidades

- Seguimiento pedagógico con comentarios y recomendaciones.
- Historial de seguimiento y referencias de auditoría.
- Protección de registros históricos en PostgreSQL.
- Informes agrupados por profesor, grupo, nivel y periodo.
- Filtros de fechas y situación de las sesiones.
- Indicadores de ejecución, asistencia y actividades.
- Restricciones de acceso mediante roles y asignaciones.
- Separación entre informe de ejecución cerrado y estado institucional realizada.

## Pruebas

Ejecutadas el 3 de noviembre de 2026 mediante
scripts/pruebas_postgresql_aisladas.py.

Suite especifica de sesiones: 76 pruebas aprobadas.
Suite general del backend: 668 pruebas aprobadas.

Resultado: OK.
System check: sin incidencias.
Diferencias de migraciones detectadas: ninguna.
Base de datos: PostgreSQL temporal.
Base operativa zona_bloque: no utilizada.
Cluster temporal: detenido al finalizar.

Evidencia privada:
respaldos/pruebas_etapa1_p9uv7x65

## Indicadores y consideraciones

El porcentaje de presencia implementado considera los estados
asistio y tarde sobre todos los registros con estado de asistencia
cerrado. Las excusas y retiros forman parte del denominador.

El porcentaje de cumplimiento curricular declarado mide tareas
curriculares abordadas frente a tareas curriculares registradas
en ejecuciones cerradas. No certifica aprendizaje, competencias
adquiridas ni cumplimiento del total de clases de una malla.

Los porcentajes sin denominador disponible se devuelven como null.

Estas definiciones deben validarse institucionalmente antes
de presentar informes como indicadores oficiales.

## Restricciones pendientes

La transicion institucional a realizada permanece bloqueada
hasta contar con el contrato de autorizacion funcional por
deportista y actividad.

No se han aplicado migraciones a la base operativa.
No se ha realizado un despliegue en produccion.
El frontend completo de sesiones e informes sigue pendiente.

## Continuidad

Etapa 4F:
Implementar interfaz React para profesores, coordinadores y
administradores utilizando las APIs existentes.

Mantener permisos efectivos, trazabilidad, estados separados
y las restricciones funcionales pendientes.
