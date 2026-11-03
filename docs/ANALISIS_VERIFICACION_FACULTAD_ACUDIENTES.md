# Diagnóstico y propuesta: comprobación de facultades de acudientes

Este documento conserva el diagnóstico original. La implementación fue autorizada posteriormente y está descrita en [Implementación de facultades](IMPLEMENTACION_FACULTADES_ACUDIENTES.md). La migración real ya fue autorizada, aplicada y verificada: [informe de aplicación](APLICACION_COMPROBACION_FACULTADES.md).

Fecha del diagnóstico: 28 de octubre de 2026. Estado de aquel encargo: solo análisis, sin implementación ni migraciones.

Se revisó el código y la documentación. No se invocó la acción de verificación, no se consultaron datos personales del vínculo 3 y no se cambió ningún estado real o ficticio. El estado pendiente y parentesco «Madre» son los informados por el usuario; no se deduce de ellos una representación ni la edad del deportista. No se ejecutaron pruebas que escriban datos ni se modificaron código, modelos, pruebas o migraciones. Único archivo creado: este documento.

## 1. Causa de la pantalla vacía y contrato actual

En `frontend/src/paginas/AcudientesAutorizaciones.jsx`, `RegistroPrivado` ejecuta `campos = []` cuando la acción es `verificar`. El formulario genérico muestra el título y los botones, pero no recibe campos ni contenido explicativo. `enviar` añade `version` y publica en `/api/vinculos-acudientes/{id}/verificar/`. Tras la corrección anterior de valores iniciales, el cuerpo efectivo es exclusivamente `{version: <versión actual>}`. No es un fallo de carga de campos ni de la migración documental.

En `backend/deportistas/views.py`, `datos_accion` admite para verificar únicamente `version`. Por tanto, añadir una referencia solo en React haría que la API la rechazara como campo ajeno. `VinculoVista.verificar` llama a `verificar_vinculo` y devuelve el serializer del vínculo.

La confirmación genérica «¿Confirmas esta operación?» del formulario no explica qué facultad se está acreditando ni prueba que se haya realizado una revisión.

## 2. Controles existentes y carencias

`backend/deportistas/servicios.py`, función `verificar_vinculo`, utiliza una transacción y:

1. Bloquea y revalida los usuarios: admite administrador o único coordinador activo, excluyendo profesores y actores desactivados o relevados.
2. Bloquea el vínculo y exige su versión actual; una solicitud obsoleta devuelve conflicto.
3. Comprueba que el acudiente esté activo y que el vínculo esté vigente en la fecha local, con fecha final exclusiva.
4. Asigna directamente `facultad_para_autorizar = verificada`, responsable, fecha del servidor e incremento de versión.
5. Registra auditoría administrativa de la operación y del nombre del campo modificado.

El modelo exige responsable y fecha cuando el estado es verificada. El serializer impide escribir directamente el estado y la fecha mediante el formulario genérico. Estos controles son útiles y deben conservarse.

Sin embargo, **no exige referencia de evidencia, método, resultado motivado, alcance de la facultad ni vigencia propia de la acreditación**. Tampoco conserva un historial específico de comprobaciones: una nueva confirmación con la versión actual puede sobrescribir el último responsable y fecha. No hay una acción específica para registrar un resultado no acreditado o retirar la acreditación, aunque el catálogo de estados incluye `no_acreditada`.

En el alta de `Autorizacion`, el backend comprueba que el vínculo corresponda al deportista, que esté marcado verificado, que el acudiente esté activo y que la vigencia declarada encaje en el vínculo. Para una autorización otorgada exige además `referencia_evidencia`. Comprueba finalidad/version, tipo activo y otras reglas de vigencia. Pero esa referencia es texto: no valida por sí misma la autenticidad o suficiencia de una evidencia. Tampoco acredita retrospectivamente la representación. El código utiliza el estado general del vínculo para todas las finalidades, sin un alcance de facultades diferenciado.

Las pruebas actuales en `backend/deportistas/tests.py` y `test_formularios_privacidad.py` aceptan precisamente una verificación con solo versión y luego una autorización. Confirman el comportamiento existente, pero no exigen acreditación suficiente.

## 3. Riesgo funcional identificado

**Sí existe un riesgo de registrar una facultad sin comprobación suficiente.** Un operador con permiso puede confirmar el formulario vacío y convertir un contacto vigente en otorgante admitido por la API. No es un acceso anónimo ni una elevación de rol del profesor; es una insuficiencia del flujo autorizado y de su trazabilidad. Resulta especialmente relevante al tratar datos de menores.

El parentesco declarado «Madre» es información administrativa aportada; no es una acreditación automática. La marca contacto principal indica a quién contactar primero; tampoco prueba representación. Incluso una facultad acreditada debe limitarse a su alcance y vigencia: no equivale a consentimiento para cualquier finalidad.

Hasta aprobar e implementar los controles, se recomienda **no usar esta acción vacía como mecanismo de acreditación**. No se deshabilitó la función en este encargo y no se marcaron ni desmarcaron vínculos. Tampoco se declara que una autorización histórica sea inválida sin revisión de su evidencia externa.

## 4. Propuesta funcional segura

Mostrar por separado:

| Concepto | Significado | Efecto permitido |
| --- | --- | --- |
| Parentesco declarado | Relación informada, sin presunción probatoria | Información de contexto |
| Contacto principal | Prioridad operativa de contacto | Contactar; sin facultades implícitas |
| Facultad acreditada | Resultado documentado de una revisión institucional competente | Solo alcance y vigencia acreditados |
| Autorización por finalidad y versión | Decisión del otorgante legitimado, registrada con evidencia propia | Exclusivamente la finalidad aprobada; sin activar módulos futuros |

Renombrar el botón a «Registrar comprobación de facultad». El formulario debe mostrar deportista y contacto mínimos, parentesco como declarado, contacto principal, vigencia del vínculo y estado de comprobación. Evitar números completos de identificación o copias de documentos en este resumen.

Solicitar resultado (`acreditada` / `no_acreditada`), método institucional aprobado, referencia privada localizable, alcance concreto, fecha de comprobación y, cuando proceda según la evidencia, vigencia. Mostrar claramente que parentesco y contacto no acreditan representación y que la operación no registra una autorización de tratamiento o imagen. Antes de confirmar, presentar un resumen de la decisión y de su alcance. Responsable y fecha de registro se obtienen de sesión y servidor, nunca del cuerpo enviado.

Para un resultado no acreditado, registrar motivo codificado y referencia de la gestión realizada, sin exigir un documento que no existe. No marcarlo verificado. Si aún no se ha realizado ninguna revisión, conservar pendiente y no simular una decisión. Una casilla de declaración del operador puede reforzar la responsabilidad, pero **no sustituye una revisión ni una referencia verificable**.

No incorporar cargas de archivos, OCR, vídeos, firmas, biometría, imágenes de documentos ni cuentas de familiares. Una referencia debe apuntar a un registro institucional controlado, no a una URL pública o un número de identidad pegado en texto libre. El software puede comprobar formato, existencia y acceso cuando haya un registro integrado; no puede determinar por sí solo la suficiencia jurídica de un documento externo.

## 5. Cambios técnicos recomendados, sujetos a aprobación

### Registro de comprobación separado e histórico

Añadir un modelo `ComprobacionFacultad` vinculado por FK PROTECT a `VinculoAcudiente`, sin duplicar identidades. Recomendación de campos:

- Vínculo y secuencia/versión resultante únicos; registro inmutable.
- Resultado acreditada/no_acreditada y motivo codificado según procedimiento institucional aprobado.
- Método y versión del procedimiento institucional aplicable.
- Referencia privada opaca de evidencia o gestión; nunca el contenido del documento. Para acreditada, una referencia de evidencia revisada es obligatoria.
- Alcance concreto aprobado. Para facultad de registrar una autorización, referencia a `TipoAutorizacion` y su versión; no reutilizarlo para retiro del menor, acceso digital o poderes distintos. No crear tipos ni finalidades de oficio.
- Fecha/hora de comprobación declarada (no futura), fecha/hora de registro del servidor y usuario responsable validado.
- Inicio y final de vigencia cuando corresponda al caso, y referencia a la comprobación sustituida, si existe. Ausencia de vencimiento no significa facultad universal ni exención de revisión.

Retirar o sustituir una acreditación mediante un evento separado con responsable, motivo y fecha; no reescribir el registro previo. El estado actual puede derivarse de eventos vigentes. Los campos actuales del vínculo pueden mantenerse como resumen compatible, pero no deben seguir siendo la fuente suficiente para conceder facultades de cualquier finalidad.

Definir restricciones: resultado válido; acreditada exige referencia, alcance y responsable; fechas coherentes; unicidad de versión por vínculo; campos de auditoría de solo lectura. Las reglas entre entidades y vigencias se validan transaccionalmente en servicios. No se proponen índices con nombres definitivos ni número de migración hasta revisar la implementación aprobada.

Registrar la auditoría general con identificador del evento, resultado y nombres de campos; evitar copiar referencias privadas y datos personales en logs, errores, analítica o listados docentes. La consulta de evidencia queda restringida a administrador y coordinador activo por finalidad operativa. No almacenar originales por defecto; establecer conservación y supresión según política institucional aplicable, sin inventar plazos universales.

### API y control efectivo

Evolucionar explícitamente el POST actual para exigir el contrato de comprobación. No conservar una ruta alternativa que acepte únicamente versión y marque verificado. Documentar el cambio para React y consumidores internos. Añadir consulta de historial restringida y acciones de sustitución/retirada solo si se aprueban sus reglas.

El backend debe:

1. Validar sesión/CSRF, rol vigente y titularidad activa de coordinación antes de procesar datos privados.
2. Usar un serializer específico de la acción, rechazar actor/fecha de registro/estado final falsificados y no permitir atajos por PATCH genérico.
3. Validar método, referencia, resultado, alcance, versión del texto y vigencia. Si no existe proceso institucional aprobado o no se puede acreditar la referencia, rechazar la transición a acreditada; una cadena no vacía no es evidencia suficiente.
4. Mantener bloqueo transaccional y un orden consistente de usuarios, deportista, acudiente y vínculo frente a finalización, desactivación y decisiones concurrentes. Revisar ese orden con los servicios existentes para evitar interbloqueos.
5. Guardar evento, resumen y auditoría en la misma transacción. Dos decisiones sobre la misma versión deben producir como máximo una transición; no duplicar revisiones por doble clic o reenvío. Una revisión nueva debe ser explícita y no sobrescribir historial.
6. Al registrar o utilizar una autorización, comprobar una acreditación concreta vigente del otorgante para esa finalidad/version, además de la evidencia propia de su decisión. Proponer una FK desde Autorizacion a la comprobación utilizada para conservar trazabilidad. No cambiar retroactivamente esa referencia al revisar la facultad.
7. Ante retirada, fin de vínculo, contacto inactivo o evidencia cuestionada, impedir nuevos usos incompatibles y presentar revisión pendiente. La política sobre efectos en autorizaciones previas debe aprobarse; no borrar ni revocar masivamente registros históricos de forma implícita.

Para menores, no permitir una declaración personal basándose únicamente en una edad de configuración: conservar la revisión institucional aplicable y separar condiciones de representación, finalidad y protección del menor. Este análisis técnico no determina qué documentos acreditan legalmente cada facultad; esa suficiencia debe quedar definida en el procedimiento institucional competente.

### Interfaz

Renderizar campos y explicaciones para la comprobación; eliminar el formulario vacío. Obtener opciones aprobadas del backend, presentar errores por campo, mantener el formulario ante conflicto y recargar la versión antes de reintentar. Mostrar únicamente acciones válidas por estado; «verificada» debe visualizar su alcance y vigencia, sin sugerir facultad universal. El frontend ayuda a prevenir errores, pero toda escritura exige las mismas reglas en Django.

## 6. Transición y migraciones propuestas

La solución completa requiere una migración aditiva para el historial y, si se aprueba, la referencia desde autorizaciones. No se genera ni aplica en este encargo. Conservar PK, UUID y vínculos actuales.

No fabricar evidencias para estados verificados anteriores. Preservar su estado histórico y distinguir «verificación anterior sin comprobación estructurada»; proponer que no habilite **nuevos** otorgamientos hasta revisión. El criterio de compatibilidad y sus efectos operativos requieren aprobación expresa. Los pendientes, incluido el caso reportado, deben seguir pendientes. La corrección no debe acreditar automáticamente ningún parentesco ni contacto principal.

Antes de una aplicación real futura: inventario exacto de operaciones/dependencias, SQL y restricciones; respaldo y recuperación verificados; pruebas de conservación y concurrencia en base aislada; autorización específica de migración. El contrato antiguo debe quedar bloqueado antes de permitir que el nuevo flujo conceda facultades.

## 7. Pruebas recomendadas y aceptación

No se añadieron ni ejecutaron estas pruebas en el encargo de análisis. Deben implementarse con datos ficticios en entornos aislados tras aprobación:

1. React: formulario explicado y con contexto; no admite confirmar acreditada sin referencia revisable, método y alcance; muestra no acreditada sin dar permisos; no mezcla campos de contacto, vínculo y autorización.
2. API: `{version}` por sí solo no verifica; referencia vacía, espacios, referencia no localizable o inaccesible, método no aprobado, resultado inválido, fecha futura y alcance incompatible son rechazados sin cambiar estado/auditoría.
3. Parentesco «Madre», apellidos coincidentes o contacto principal, por separado o combinados, no acreditan facultad. Incluye deportistas menores con documento pendiente y con documento registrado.
4. Un menor no obtiene autorización por un contacto no acreditado, por acreditación de otro deportista, por otro alcance/version o por una comprobación vencida/retirada. No se activan medios, acceso familiar ni IA por ningún resultado.
5. Administrador y coordinador activo registran comprobaciones válidas; profesor, visitante, cuentas inactivas y coordinador relevado reciben rechazo, incluso por API directa y con referencias válidas. CSRF sigue siendo obligatorio.
6. No se puede falsificar responsable/fecha de servidor ni escribir el estado por PATCH. Las referencias no se filtran en respuesta docente, errores, auditoría genérica o URLs.
7. Dos decisiones simultáneas, reenvío de la misma versión y finalización/desactivación concurrente no generan estados incompatibles. Evento, resumen y auditoría se revierten juntos ante error.
8. La evidencia de facultad no sustituye la evidencia propia de una autorización. Un resultado positivo para una finalidad no habilita otra; retirar o revisar conserva historial y no reescribe decisiones previas.
9. Migración aditiva conserva identidades, relaciones y datos históricos, sin evidencias inventadas; casos anteriores quedan identificados para revisión según política aprobada.
10. Regresión de autenticación, ámbitos, formularios privados, identificación documental y fases anteriores.

Aceptación mínima: no existe una vía frontend/API que marque facultad acreditada con una mera confirmación, un parentesco o una referencia arbitraria; cada acreditación nueva tiene responsable, fecha, método, alcance y evidencia revisada trazables. El profesor no gana facultades y ningún registro existente se transforma sin revisión autorizada.

## 8. Decisiones necesarias y secuencia propuesta

Se requiere aprobar: quién y mediante qué procedimiento comprueba la suficiencia de la evidencia; métodos y referencias admitidos; alcances/finalidades autorizados y su relación con versiones; reglas de vigencia/revisión; tratamiento operativo de acreditaciones anteriores; política sobre retirada y autorizaciones ya registradas. No se propone exigir un segundo aprobador por defecto en esta empresa pequeña; si se desea, debe definirse expresamente.

Incrementos recomendados: (1) contrato y bloqueo del flujo sin evidencia, con formulario explicado y pruebas de rechazo; (2) historial de comprobaciones y alcance, con migración revisada; (3) integración de autorización con la comprobación concreta y revisión de casos anteriores. Los incrementos deben entregarse sin una ventana en que el formulario nuevo aparente seguridad pero el contrato anterior siga concediendo facultades. No basta con añadir un campo de texto en React.

**Punto de parada:** análisis terminado. Solicitar aprobación de esta propuesta y de las decisiones institucionales antes de implementar. Una aprobación de implementación no autoriza por sí sola aplicar migraciones en zona_bloque ni marcar el vínculo 3 como verificado.
