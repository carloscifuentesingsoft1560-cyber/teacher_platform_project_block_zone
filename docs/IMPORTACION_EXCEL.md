# Referencias e importación futura

> Revisión de noviembre: la [auditoría integral](AUDITORIA_INTEGRAL_FASE_0_2026_11_02.md) confirma las cuatro mallas, 42 hojas y 1.548 fórmulas, y documenta ejemplos de referencias desplazadas y ausencia confundida con puntuación. No hay importador implementado ni fórmulas aprobadas. Mantener originales, fuente/celda y estados de revisión conforme a los [contratos futuros](CONTRATOS_COMPARTIDOS_FUTUROS.md).

No existe importador en Fase 1. Los originales permanecen en docs/referencias sin modificaciones y excluidos del control de versiones.

## Inventario de Fase 0

- Mallas: cuatro hojas — LUDICO, NIVEL 1, NIVEL 2 y ESPECIALIZACION SEMICOMPETITIVA.
- Cada una tiene 40 entradas numéricas de semana y 80 de clase; la importación deberá reconstruir agrupaciones y revisar textos.
- Las celdas combinadas y los desempeños en filas contiguas no equivalen a registros independientes.
- No hay contenido curricular de Alto Rendimiento.
- Valoraciones: 42 hojas; dos de indicadores/baremos, tres plantillas identificadas por nombre exacto y 37 hojas restringidas o variantes.
- Se identificaron 1.548 celdas con fórmulas, incluyendo fórmulas compartidas: búsquedas, sumatorias, porcentajes y diferencias.
- Hay formatos de fecha en indicadores nivel 2, celdas B12, B19, B20 y B21, que requieren revisión humana.
- No se recalcularon los libros ni se aprobaron reglas de promoción.

## Proceso previsto para Fase 4

1. Separar catálogos/plantillas de hojas individuales usando una lista explícita de hojas permitidas. No usar coincidencias por prefijo: algunas hojas individuales imitan nombres de plantillas.
2. Conservar libro, hoja, celda, texto original y versión.
3. Reconstruir combinaciones y orden, sin descartar desempeños contiguos.
4. Presentar vista previa y advertencias.
5. Resolver baremos, errores y equivalencias con el propietario.
6. Importar catálogos únicamente después de confirmación.
7. Tratar cualquier importación personal como proceso separado y expresamente autorizado.

Las plantillas pueden contener puntajes y anotaciones de ejemplo: no se convertirán automáticamente en resultados de estudiantes. La importación no podrá generar promociones ni decidir ponderaciones ausentes.
