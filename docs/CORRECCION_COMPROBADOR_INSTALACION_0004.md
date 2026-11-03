# Corrección del comprobador de instalación 0004

Fecha: 30 de octubre de 2026, Bogotá; ejecución UTC del 31 de octubre. **Solo corrección y pruebas del comprobador. No se reintentó la instalación real.**

## Causa verificada

El primer intento comparaba por igualdad literal los diccionarios de restricciones, índices, funciones y triggers del origen con los de una copia restaurada. PostgreSQL había normalizado casts al restaurar expresiones antiguas. Por eso 21 restricciones CHECK semánticamente equivalentes producían una diferencia textual. La preparación también había identificado un índice parcial con el mismo fenómeno.

El manifiesto del intento original conserva el error y confirma que la migración no quedó registrada. La transacción se revirtió íntegramente. El script anterior se preservó como `respaldos/aplicacion_0004_20261031T011121Z/aplicar_antes_correccion.py`, SHA-256 `1ac8a4fbbe0ee10e0fc3cd81c1e138195b15c8914e12af5284775ec1341046d4`. No se alteró ese manifiesto ni se volvió a ejecutar `ejecutar()` del instalador.

## Criterio corregido

El instalador usa `scripts/comparador_esquema_0004.py` y un certificado de pares SQL exactos. No se eliminan casts mediante expresiones regulares, no se aceptan restricciones únicamente por su nombre y no se ignoran objetos.

1. Los inventarios de restricciones, índices, funciones y triggers deben contener exactamente los objetos esperados: faltantes o adicionales bloquean la comparación.
2. Funciones y triggers siguen comparándose literalmente, incluidos sus atributos inventariados.
3. Restricciones e índices idénticos se aceptan. Una diferencia de definición solo se admite si corresponde exactamente al par origen/restaurado de ese objeto, previamente comprobado en PostgreSQL aislado. Los demás atributos deben ser idénticos.
4. Se siguen exigiendo CHECK validados, índices válidos/listos y triggers habilitados en modo ordinario.
5. Se comprueban tablas y una huella completa de metadatos de columnas: orden, nombre, tipo y longitud, nulabilidad, identidad, generación, collation y expresión de valor predeterminado.
6. El certificado está vinculado mediante huellas a los dos inventarios de esquema y a los metadatos esperados tras `0004`. Su contenido completo tiene SHA-256 fijado en el módulo: un archivo modificado se rechaza.
7. El comparador no ejecuta DDL ni DML. Puede usarse dentro de una transacción PostgreSQL `READ ONLY`. Las comprobaciones originales de conteos/huellas de registros y permisos del instalador permanecen intactas.

No es un motor de demostración de equivalencias arbitrarias. Incluso una variante aparentemente inocua pero no certificada se rechaza. Cambiar cualquier condición, tabla, atributo o definición fuera del par acreditado bloquea la instalación y requiere revisión.

## Cómo se acreditaron las equivalencias

Se creó un clúster PostgreSQL 17.11 nuevo, exclusivo, con el mismo locale `Spanish_Colombia.1252` y una base `comparador_0004_20261031t011935z`. Antes de restaurar y antes de aplicar DDL se verificaron nombre de base, puerto distinto de 5432, directorio de datos y PID del proceso hijo. No se restauró sobre `zona_bloque` ni sobre una base compartida.

Se restauró el respaldo aprobado, comprobando su SHA-256. La copia reprodujo tablas, datos, funciones, triggers y migraciones. Los metadatos de tipos de columnas se compararon con los obtenidos del origen en lectura. Se aplicó `0004` exclusivamente en la copia aislada; el esquema resultante se contrastó con la referencia aislada anterior.

Para cada diferencia de CHECK se creó una tabla temporal vacía con los mismos tipos y collations. PostgreSQL reanalizó la expresión original y la restaurada en ese mismo contexto tipado; sus definiciones canónicas obtenidas mediante `pg_get_constraintdef` coincidieron. Para el índice parcial se exigió además el mismo prefijo estructural de índice y se reanalizaron sus dos predicados como expresiones booleanas CHECK. Se comprobó que sustituir la condición por `CHECK (true)` produce un canon distinto y no se certifica.

Resultado: **21 pares CHECK y un par de predicados de índice**, sin equivalencias adicionales. El certificado contiene los dos textos exactos y sus resultados canónicos; no contiene filas personales.

Archivo: `scripts/evidencias_0004/equivalencias.json`.

SHA-256: `234059d583bb438f53c58a0da3884abf27993b0ecd0afb2e7a9094ca9c21e109`.

La primera ejecución generó correctamente las pruebas de equivalencia, pero un test de metadatos utilizó la posición 9 de una tupla de nueve elementos. Se corrigió a la posición 8, correspondiente al valor predeterminado. Se conservó el log inicial y se repitió la batería en el mismo clúster exclusivo ya detenido, verificando nuevamente directorio y PID antes de usarlo.

## Pruebas y resultados

**24 pruebas automatizadas aprobadas en 0,997 segundos**, sin errores ni fallos en la ejecución final.

Positivos:

- Catálogo real instalado en PostgreSQL aislado.
- Los 22 pares en su formato original, simultáneamente.
- Certificado válido con SHA-256 correcto.
- Comparación completa dentro de transacción de solo lectura.

Negativos:

- Restricciones ausentes, adicionales o cambiadas de tabla.
- Condición certificada sustituida por `CHECK (true)`.
- Variante textual no certificada, aunque solo agregue un espacio.
- CHECK no validado.
- Índice ausente, inválido o con predicado alterado.
- Función modificada y trigger deshabilitado.
- Tabla ausente o adicional.
- Columna, tipo, nulabilidad y valor predeterminado alterados.
- Referencia manipulada y SHA-256 incorrecto del certificado.

Cinco casos se ejecutaron realmente con SQL en la copia aislada: eliminación de CHECK; sustitución de su condición; deshabilitación de trigger; incorporación de una columna; cambio de un DEFAULT. Todos fueron rechazados y sus transacciones se revirtieron. El inventario completo y las huellas del clon antes/después quedaron idénticos.

Además de la batería, se importó el instalador corregido **sin ejecutar su función de instalación** y se llamó exactamente a `esquema_verificado()` en la base aislada, dentro de una transacción READ ONLY. La integración pasó con el certificado fijado por SHA-256. La ubicación de salida se redirigió a la carpeta de esta corrección para conservar la evidencia del primer intento.

No se repitieron las regresiones deportivas ni frontend: estos componentes no fueron modificados. No se generaron migraciones.

## Estado final de la base real

Verificación exclusivamente en lectura, tras finalizar las pruebas:

| Comprobación | Resultado |
|---|---|
| Conexión | PostgreSQL 17.11, `127.0.0.1:5432`, `zona_bloque`, `public` |
| Tablas | **38** |
| Registros | **267** |
| Esquema y huellas de registros | Idénticos a la referencia anterior |
| `0003` | Aplicada |
| `0004` | **No aplicada; única pendiente** |
| Operaciones deportivas reales | **0** |

SHA-256 de las migraciones, sin modificaciones:

- `0002`: `eb8c72570b8e475f8c38e4986544ced3948b589f971c217e17d49eedf3b73d2f`.
- `0003`: `5f6fdd0fe87f1bcb37ab5273110f652ca6dc32c3590ee3b8b107a140706c8658`.
- `0004`: `115e827fbc4d84e13db8006bbee71b6882ffda4944bcba69345636b1dc7082c6`.

No se modificaron inscripciones, usuarios, roles, permisos, credenciales, servicios deportivos ni frontend. No hubo commits ni push. El clúster aislado terminó detenido y se conserva como evidencia temporal; no se intentó eliminar ninguna base real.

## Archivos y evidencia

- Nuevo: `scripts/comparador_esquema_0004.py`.
- Nuevo: `scripts/test_comparador_0004.py`.
- Nuevo: `scripts/evidencias_0004/equivalencias.json`.
- Modificado únicamente en su integración de comparación: `respaldos/aplicacion_0004_20261031T011121Z/aplicar.py`.
- Copia histórica preservada: `aplicar_antes_correccion.py` en esa carpeta.
- Evidencia aislada, scripts de ejecución y logs: `respaldos/correccion_comparador_0004_20261031T011935Z/`.
- Informe: este documento.

La evidencia incluye `pruebas_corregidas.log`, `resultado_aislado.json`, `comparacion_esquema.json`, `estado_real_final.json` e `inventario_origen_final.json`. Los archivos en `respaldos/` continúan excluidos de Git.

## Punto de parada

**Comparador corregido y verificado; no se reintentó la instalación real.** Un nuevo intento requiere instrucciones expresas, reconfirmar conexión, respaldo y huellas vigentes y conservar la evidencia en una carpeta nueva. Si aparece una variante no acreditada, se detendrá; no se ampliará automáticamente el certificado ni se relajarán las comprobaciones.
