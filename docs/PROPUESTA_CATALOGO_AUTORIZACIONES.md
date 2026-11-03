# Propuesta de catálogo institucional de autorizaciones

**Zona de Bloque — borrador para revisión jurídica e institucional**
Fecha de elaboración y consulta de fuentes: **29 de octubre de 2026, Colombia**.

**Ninguna finalidad, versión, referencia, autorización individual o texto de este documento se declara aprobado.** No constituye un formulario de consentimiento listo para firmar. Las referencias sugeridas son identificadores reservados: los textos y actas correspondientes todavía deben elaborarse y aprobarse. No deben copiarse al campo «Referencia del texto aprobado» mientras no exista el documento aprobado y localizable.

Única actuación de este encargo: crear este documento. No se consultaron ni modificaron registros de PostgreSQL, ni se modificaron código, permisos, modelos o migraciones. No se repitió `deportistas.0003_comprobacion_facultades`, no se cargó catálogo ni se realizaron commits o push.

## 1. Encaje con la plataforma actual

Se revisaron los modelos, servicios y documentación de Fase 3, especialmente [el plan de deportistas](PLAN_FASE_3_DEPORTISTAS.md), [la implementación de facultades](IMPLEMENTACION_FACULTADES_ACUDIENTES.md) y [su aplicación](APLICACION_COMPROBACION_FACULTADES.md). La sección vacía observada por el usuario es coherente con no haber precargado textos institucionales supuestos. Este análisis no ejecutó una consulta para certificar el contenido actual de la base.

`TipoAutorizacion` dispone de código, número entero de versión, finalidad, referencia del texto y estado activo; la combinación código/version es única. Las autorizaciones individuales apuntan a una versión concreta. Las comprobaciones de facultad del acudiente también tienen alcance por tipo/version, método, resultado, referencia privada, responsable y fechas. Los textos usados en comprobaciones o autorizaciones no deben reescribirse.

Deben distinguirse cuatro actos:

1. La institución aprueba un **texto y una finalidad** del catálogo.
2. El personal autorizado acredita, cuando corresponde, la **facultad del representante** para ese alcance.
3. El titular o representante legitimado manifiesta una **decisión individual**, informada y demostrable.
4. La institución verifica que el tratamiento concreto y su tecnología estén habilitados y sean compatibles con esa decisión.

Ninguno sustituye al siguiente. El permiso administrativo para crear tipos no convierte un borrador en texto jurídicamente suficiente. El parentesco, ser contacto principal, la matrícula, una referencia UUID o la aprobación de una migración tampoco constituyen consentimiento. Los módulos de imágenes, vídeos, IA y biometría siguen fuera del alcance operativo actual.

## 2. Marco jurídico y criterios de interpretación

Las fuentes se citan como soporte del análisis; la propuesta de clasificación, códigos y procedimiento es una recomendación institucional pendiente, no una conclusión de asesoría jurídica definitiva. Debe revisarse la vigencia y aplicabilidad normativa nuevamente antes de activar cada tratamiento.

### 2.1 Régimen general y posibles fundamentos

La Ley 1581 exige, por regla general, autorización previa e informada, consultable posteriormente; contempla excepciones delimitadas y reglas especiales para datos sensibles. También regula información al titular, derechos, deberes y circulación internacional. La necesidad operativa **no crea una excepción**. Un contrato deportivo no habilita por sí solo cualquier uso, ni debe importarse una base genérica de «interés legítimo» como si fuera una excepción colombiana. Para cada excepción invocada debe identificarse la norma y el tratamiento exactos. [Ley 1581 de 2012, arts. 4–12, 17–18 y 26](https://www.cancilleria.gov.co/normograma/compilacion/docs/ley_1581_2012.htm).

El Decreto 1074 desarrolla autorización, prueba, revocación, temporalidad y tratamiento de menores. La autorización de datos sensibles debe advertir su carácter facultativo; no se puede condicionar una actividad a suministrarlos. La conservación exige justificación por finalidad y obligaciones aplicables, no plazos universales inventados. [Decreto 1074, capítulo 25, en el texto oficial publicado por Supersociedades](https://www.supersociedades.gov.co/documents/107391/832636/Decreto-1074-del-26-de-mayo-de-2015.pdf); [concordancias de los artículos compilados del Decreto 1377 en CREG](https://gestornormativo.creg.gov.co/gestor/entorno/docs/decreto_1377_2013.htm).

La evaluación jurídica deberá distinguir: autorización como fundamento general; una obligación legal específica, si existe; y una excepción legal aplicable a una operación delimitada. Las necesidades contractuales de conservación no autorizan publicidad, IA o biometría adicionales. No se presume que la excepción sobre registro civil convierta las copias, números de identidad y fichas completas de la escuela en información de libre uso.

### 2.2 Menores, imagen, IA y biometría

El artículo 7 no debe leerse como prohibición absoluta de tratar cualquier dato no público de menores: la Corte condicionó su interpretación a su interés superior y a la prevalencia de sus derechos. Esto exige evaluación del caso, no una autorización genérica de toda la actividad deportiva. [Sentencia C-748 de 2011, apartado 2.9.3](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?0=&i=50042).

Deben acreditarse representación y autorización correspondiente, escuchando al menor y valorando comprensión y madurez. La intimidad y su opinión requieren protección propia; una firma adulta no elimina esa evaluación. [SIC, concepto sobre tratamiento excepcional de datos de menores, diciembre de 2025](https://sedeelectronica.sic.gov.co/publicaciones/boletin-juridico/concepto/tratamiento-excepcional-y-autorizacion-del-representante-legal-con-interes-superior); [Ley 1098 de 2006, arts. 26 y 33](https://www1.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=22106).

La revisión de fotografías debe considerar su contenido: no presumir que un vídeo técnico es inocuo o que no puede contener datos sensibles. La Corte distingue contenido identificable y no personal, y aborda el rostro como información biométrica sensible. La clasificación concreta requiere revisión reforzada. [Sentencia C-468 de 2025, párrs. 316–318](https://www.corteconstitucional.gov.co/relatoria/2025/C-468-25.htm). La publicación añade cuestiones de imagen y derechos del autor de la obra; revisar el artículo 87 y sus límites, sin trasladar excepciones automáticamente a promoción empresarial. [Ley 23 de 1982](https://www1.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=3431).

Para IA, la Circular SIC 002 de 2024 exige ponderar idoneidad, necesidad, razonabilidad y proporcionalidad, gestionar riesgos y documentar un estudio de impacto cuando sea probable un alto riesgo. Incorporar sus instrucciones de precaución y protección desde el diseño al proyecto futuro, no limitarse a obtener una firma. [Circular Externa 002 de 2024, apartados I–IV y X](https://cancilleria.gov.co/normograma/compilacion/docs/circular_superindustria_0002_2024.htm).

Como antecedente específico, la SIC ordenó alternativas al reconocimiento facial y supresión de datos en un caso de copropiedad. Sirve para revisar alternativas menos invasivas; no es una autorización ni una regulación sectorial deportiva. [SIC, Resolución 52185 de 2025, comunicado oficial](https://sedeelectronica.sic.gov.co/comunicado/la-superintendencia-de-industria-y-comercio-ordena-un-conjunto-residencial-habilitar-mecanismos-de-ingreso-que-no-impliquen-el-tratamiento).

## 3. Catálogo propuesto: seis familias y siete entradas candidatas

Se recomienda **separar comunicaciones ordinarias y contactos de emergencia** dentro de la segunda familia: tienen sujetos, destinatarios y condiciones diferentes. Resultan siete códigos candidatos para las seis familias solicitadas. Esta división también queda pendiente de decisión institucional.

En todas las filas, «1 propuesta» significa primera versión entera futura del texto, no aprobación ni vigencia. El borrador de trabajo puede llevar una revisión editorial 0.1 fuera de PostgreSQL. Ninguna referencia de la tabla corresponde a un archivo creado o aprobado en este encargo.

| Familia | Código propuesto, compatible con el campo actual | Versión propuesta | Referencia documental reservada | Clasificación propuesta |
| --- | --- | --- | --- | --- |
| 1. Inscripción y gestión deportiva | `inscripcion_gestion_deportiva` | 1, pendiente | `ZDB-AUT-001-V1` | Núcleo operativo, limitado a datos necesarios |
| 2A. Comunicaciones operativas | `comunicaciones_operativas` | 1, pendiente | `ZDB-AUT-002A-V1` | Operativa; canales y destinatarios delimitados |
| 2B. Contactos de emergencia | `contactos_emergencia` | 1, pendiente | `ZDB-AUT-002B-V1` | Seguridad operativa mínima; excepción de urgencia solo caso a caso |
| 3. Seguimiento técnico interno con imágenes | `seguimiento_tecnico_interno` | 1, pendiente | `ZDB-AUT-003-V1` | Opcional y futura |
| 4. Publicación institucional de imágenes | `publicacion_institucional` | 1, pendiente | `ZDB-AUT-004-V1` | Opcional y futura, separada del seguimiento |
| 5. Análisis mediante ClimbVision-AI | `climbvision_analisis_deportivo` | 1, pendiente | `ZDB-AUT-005-V1` | Opcional y futura, revisión de alto riesgo |
| 6. Biometría futura | `biometria_revision_especial` | 1 solo como reserva | `ZDB-AUT-006-REVISION` | **Reserva documental; no es una finalidad suficientemente concreta para cargar o autorizar** |

La familia biométrica deberá convertirse, si llega a justificarse, en finalidades concretas con códigos y textos específicos; por ejemplo, un uso de autenticación no equivale a análisis deportivo. La fila reservada no es una autorización para «cualquier tratamiento biométrico».

### 3.1 Inscripción y gestión deportiva

Propuesta de alcance: identificar la ficha permanente, vincular deportista a grupos y periodos, administrar cambios e historial y contactar por la prestación del servicio. Delimitar destinatarios por función y recopilar únicamente datos necesarios. No extender el texto a medios, diagnósticos de salud, campañas comerciales ni tecnologías futuras. Una exoneración de responsabilidad o aceptación del reglamento deportivo es otro acto, no una autorización de datos implícita.

Fundamento candidato: autorización general conforme al régimen aplicable, con garantías de menores; documentar separadamente las obligaciones legales concretas que puedan afectar determinados registros. Las necesidades del contrato explican la operación, no una dispensa general de autorización. Si se rechaza un dato realmente indispensable, explicar su efecto concreto y buscar una alternativa; la negativa a finalidades opcionales no debe impedir inscripción o degradar la enseñanza. La institución debe justificar qué datos considera indispensables antes de decidir sobre el servicio.

Aprobación propuesta: representante legal o persona con facultad institucional suficiente, con concepto jurídico y validación operativa del coordinador. Antes de usar el formulario: aprobar inventario mínimo, destinatarios, conservación y canal de derechos.

### 3.2 Comunicaciones operativas y contactos de emergencia

**Comunicaciones:** limitar a información de grupos, horarios, cambios y gestión administrativa de la prestación. Identificar canales concretos y preferencias; no incluir publicidad, patrocinadores, venta cruzada ni grupos masivos donde se revelen teléfonos. Si se desea marketing posteriormente, necesitará otra finalidad y revisión de sus reglas específicas. No confundir aceptar un contacto operativo con autorizar cualquier mensajería o cualquier proveedor.

**Emergencias:** identificar y localizar al contacto designado, comunicándole solo lo pertinente para actuar. No solicitar por defecto historias clínicas o datos sensibles de terceros. El contacto de emergencia puede ser una persona distinta del representante. Recibir su teléfono del acudiente no demuestra que aquel haya autorizado todos los usos de sus propios datos: definir información al contacto y fundamento de su tratamiento. La autorización del menor no sustituye la del adulto respecto de sus datos propios.

Fundamento candidato ordinario: información/autorización pertinente a cada titular según revisión jurídica. Una urgencia médica o sanitaria puede requerir valorar la excepción del artículo 10 de la Ley 1581 en sus condiciones concretas; no permite una recopilación rutinaria ilimitada ni divulgar a cualquier persona. Los tratamientos sensibles tienen reglas adicionales. Documentar la situación y sus límites sin fabricar consentimientos retrospectivos.

Aprobación propuesta: representante legal, revisión jurídica y coordinador como responsable del protocolo operativo. Pendientes: canales/proveedores, destinatarios habilitados, sustitución de contactos y mecanismo para gestionar los datos propios de acudientes y contactos adultos.

### 3.3 Fotografías y vídeos para seguimiento técnico interno

Propuesta futura y opcional: captura y consulta restringida para una revisión técnica humana determinada. Definir qué se graba, en qué espacios, quién accede, periodo de uso y forma de entrega del resultado. Prever una alternativa razonable sin grabación. No incluir rostros o terceros si no son necesarios, y proteger a quienes no autoricen, también en grabaciones de grupo.

Fundamento candidato: autorización específica, con advertencias y consentimiento explícito si hay datos sensibles; garantías reforzadas de menores. Revisión jurídica del contenido y de necesidad/proporcionalidad antes de ofrecerla. No se asume que una captura sin nombre esté anonimizada.

Excluir expresamente publicación, difusión a otros acudientes, análisis automático, reconocimiento facial y entrenamiento de modelos. No reutilizar estas grabaciones para ClimbVision-AI mediante una versión del mismo alcance que silenciosamente amplíe su finalidad.

Aprobación propuesta: representante legal, revisión jurídica y de seguridad, validación pedagógica del coordinador. Pendientes: plataforma, acceso, dispositivos de captura, conservación y retirada de copias. No hay autorización para desarrollar el módulo de medios en este encargo.

### 3.4 Publicación de fotografías y vídeos institucionales

Propuesta futura y opcional, independiente de la anterior. Definir piezas, contexto, audiencia, medios concretos —sitio institucional, redes, impresos, por ejemplo— y vigencia. No autorizar en bloque plataformas, publicidad pagada, cesión a patrocinadores o usos comerciales de terceros no identificados. Si las opciones son independientes, resolverlas con decisiones separadas o subdividir el código antes de cargarlo; el modelo actual no contiene preferencias granulares de canal por autorización.

Fundamento candidato: autorización específica de datos y revisión del derecho a la imagen y de las licencias del fotógrafo/productor. La institución no obtiene propiedad sobre la identidad del deportista. Un evento abierto al público o la presencia del acudiente no equivalen a permiso promocional. Para menores, evaluar seguridad, dignidad y riesgo de localización; no asociar innecesariamente nombres completos, horarios habituales o ubicación precisa.

Ante negativa, proponer exclusión de encuadre, sustitución de la pieza o edición que evite identificación antes de publicar. No penalizar al deportista. La eliminación de una pieza institucional no garantiza desaparición de copias hechas por terceros: explicar ese riesgo antes de decidir, sin convertirlo en renuncia a derechos.

Aprobación propuesta: representante legal y revisión jurídica, con coordinador y persona encargada de comunicaciones si se designa. Pendientes: medios autorizables por separado, responsables de publicación, licencias, plazos y protocolo de retirada.

### 3.5 Análisis deportivo mediante ClimbVision-AI

Propuesta futura y opcional para una función de análisis **todavía por especificar**. Precisar entradas, resultados, límites, intervención humana, proveedores, ubicación del tratamiento, errores esperables y destinatarios. No afirmar que la herramienta existe o que sus resultados están validados. La alternativa propuesta es seguimiento docente sin IA, sin ascensos automáticos ni exclusión del servicio por negativa.

Fundamento candidato: autorización específica para el tratamiento descrito, régimen reforzado si las entradas o inferencias son sensibles y evaluación previa de riesgos. Acordar condiciones de proveedores y circulación de datos antes de un piloto real. No invocar investigación, innovación o datos accesibles en internet como habilitación genérica.

**Separación necesaria:** inferencia para el deportista no incluye entrenamiento, ajuste, evaluación de modelos o creación de conjuntos de datos reutilizables. Esos usos no quedan propuestos como autorizados: exigirían una finalidad y revisión adicionales, o demostrar anonimización efectiva y evaluar riesgos residuales. Tampoco incluye identificación biométrica; si el diseño la necesita, deberá pasar por la familia 6.

Aprobación propuesta: representante legal, concepto jurídico, revisión técnica/de seguridad e informe pedagógico del coordinador. Pendientes: diseño concreto, estudio de impacto, condiciones de proveedores, tratamiento de inferencias y mecanismo real de revocación. Sin esa definición no procede preparar un texto final ni cargar un tipo genérico de IA.

### 3.6 Tratamientos biométricos futuros

No se propone un consentimiento abierto. Primero definir si existe un objetivo institucional legítimo que no pueda alcanzarse adecuadamente con alternativas menos invasivas, qué característica se trataría y qué datos/resultados se generarían. Sería opcional, sujeto al régimen de datos sensibles y a examen especialmente riguroso de menores. El consentimiento no subsana un tratamiento desproporcionado.

Excluir cualquier obligación de entregar huella, rostro, voz u otra característica para poder inscribirse o recibir enseñanza. Una solución de acceso, si alguna vez se estudia, deberá contemplar alternativas reales. No crear plantillas, perfiles, repositorios biométricos ni pruebas con menores a partir de esta reserva documental.

Aprobación propuesta: representante legal tras revisión jurídica especial, seguridad e impacto documentados. La decisión admisible puede ser **no implementar**. Si se justifica un caso concreto, sustituir la reserva por códigos precisos y textos nuevos, sin activar por extensión los de imagen o IA.

## 4. Garantías comunes de menores y de terceros

Propuestas para los expedientes y textos futuros, sujetas a validación:

- Acreditar quién puede representar al menor para la finalidad y versión concretas; no deducirlo de «Madre», parentesco, contacto principal o un documento de identidad aislado. Resolver con asesoría competente casos de custodia, restricciones, desacuerdos o protección administrativa.
- Explicar cada finalidad en lenguaje comprensible, escuchar al menor según madurez y dejar evidencia mínima de esa actuación. Proponer que una oposición o señal de malestar ante medios, IA o biometría suspenda el uso opcional mientras se revisa el caso; no tratar una firma adulta como permiso para ignorarla.
- Distinguir la autorización del representante de la participación/opinión del menor; no hacerle firmar como si tuviera automáticamente facultad contractual plena. La configuración institucional `edad_autonomia` no reemplaza los requisitos legales ni resuelve por sí sola todos los tratamientos.
- Revisar cambios de representación y la transición a la mayoría de edad; no prolongar por defecto permisos del acudiente ni fabricar decisiones del deportista.
- Minimizar información en grupos, terceros y dispositivos personales. No publicar contactos de emergencia, documentos o evidencias de representación.
- Mantener el expediente de facultad separado de la prueba del consentimiento individual. Conservar referencias privadas; no copiar números documentales completos a historiales, actas de aprobación de textos o registros de auditoría.

Estas garantías son requisitos de diseño propuestos, no evidencia de que se hayan cumplido en un deportista concreto.

## 5. Textos, referencias y aprobación institucional

### Contenido que deberá tener cada texto, sin redactar aquí un consentimiento

Identidad y datos de contacto del responsable real de tratamiento; finalidad delimitada; titulares/categorías de datos; operaciones; destinatarios y proveedores relevantes; canales/países de tratamiento cuando corresponda; carácter necesario u opcional; alternativas y consecuencias concretas de negar; vigencia y criterios de conservación; derechos/canal de ejercicio; revocación; garantías de menores y datos sensibles; identificación de versión y fecha de entrada en uso. No usar «cualquier fin», «irrevocable», «a perpetuidad» o exenciones generales de responsabilidad como atajos.

La política de tratamiento, el aviso de privacidad, el reglamento de servicio, el texto de autorización y la constancia individual cumplen funciones diferentes. Una remisión a la política no sustituye informar la finalidad precisa ni conservar la decisión correspondiente.

### Roles propuestos, sin crear una jerarquía nueva

| Participante | Responsabilidad propuesta |
| --- | --- |
| Representante legal de la empresa o delegado con facultad suficiente | Aprobación institucional formal; confirmar quién es jurídicamente el responsable del tratamiento |
| Asesoría jurídica competente, que puede ser externa | Validación del fundamento, menores, sensibles, imagen, proveedores, excepciones y conservación |
| Coordinador activo | Elaboración del alcance operativo/pedagógico, minimización y procedimiento de atención/revocación |
| Administrador principal de la plataforma | Custodia del catálogo y carga fiel solo después de aprobación documentada; rol técnico no sustituye representación legal |
| Responsable técnico/de seguridad designado | Revisar accesos, proveedores, controles y viabilidad de retiro, supresión y conservación |
| Profesores | Aportar necesidades y aplicar límites operativos; no aprobar textos legales ni otorgar permisos por la familia |

Una persona puede acumular funciones si tiene atribuciones válidas, pero el expediente debe distinguir qué revisión realizó. No se presume que ya existan asesores contratados o responsables formalmente designados.

### Procedimiento de conservación y versionado propuesto

1. Crear un expediente documental por código fuera del catálogo activo, marcado BORRADOR. Incorporar mapa de datos, necesidad/alternativas, riesgos y responsables. No crear aún otros archivos por este encargo.
2. Elaborar el texto y someterlo a revisión jurídica e institucional; registrar observaciones y decisión. Para medios/IA/biometría, añadir las revisiones especiales pertinentes antes de decidir su viabilidad.
3. Si se aprueba posteriormente, asignar la referencia reservada definitiva y acta de aprobación con identidad/cargo del aprobador, fecha y alcance. Un hash o un nombre de archivo **no acreditan por sí solos** esa aprobación.
4. Conservar una copia exacta e inmutable del texto aprobado —por ejemplo PDF firmado o evidencia equivalente jurídicamente revisada—, su SHA-256, versión, fecha de uso y acta. Mantenerla en repositorio institucional protegido, con permisos, respaldo, registro de acceso y localización estable. El presente repositorio de código no debe alojar consentimientos firmados ni expedientes personales.
5. Solo entonces, y mediante instrucción de carga separada, registrar código, versión entera, finalidad precisa y referencia resoluble en el catálogo. Verificar coincidencia entre pantalla y texto, acceso a la versión histórica y ausencia de ámbitos adicionales implícitos. No usar «pendiente» como referencia de un texto supuestamente aprobado.
6. Al recabar cada decisión, conservar la prueba de qué texto/versión se presentó, cuándo, a quién, con qué representación y qué se decidió. No bastan la fecha del acta institucional o una marca del operador. Para menores añadir las constancias pertinentes sin recopilación excesiva.
7. Modificación sustancial de finalidad, destinatarios, tecnología o condiciones: nueva revisión y versión; si nace otro propósito, otro código. Evaluar nueva autorización y nueva comprobación de facultad; nunca migrar decisiones de v1 a v2 automáticamente. Mantener la versión utilizada y la evidencia anterior sin reescribirlas.
8. Retirar versiones para nuevas captaciones mediante un procedimiento aprobado y conservar su trazabilidad. Revisar previamente cómo `activo` afecta a autorizaciones/comprobaciones existentes: el sistema actual considera ese estado al evaluar vigencia, por lo que desactivar un tipo no equivale simplemente a ocultarlo del formulario.

Definir conservación por clase de expediente y obligación concreta, con minimización y eliminación/restricción cuando corresponda; no fijar aquí un plazo único ni justificar retención ilimitada de todos los vídeos o datos por conservar una prueba mínima de consentimiento.

## 6. Revocación, negativa y supresión

Debe existir un canal gratuito y accesible, sin exigir portal o cuenta de menor. La institución debe definirlo y comunicarlo; aquí no se inventan correo, dirección o teléfono. La revocación/supresión se tramita considerando las obligaciones legales o contractuales concretas y conservando solo lo justificable. No exigir una previa decisión de la SIC como condición para recibir una solicitud. [Decreto 1074, art. 2.2.2.25.2.6, recogido en una decisión oficial de la SIC](https://sedeelectronica.sic.gov.co/sites/default/files/normativa/RE22390-2024.pdf).

Procedimiento operativo propuesto:

1. Recibir y radicar la solicitud; verificar identidad y legitimación de manera proporcional, sin pedir otra copia completa de documento por defecto. Identificar finalidad/version y alcance de la solicitud.
2. Distinguir revocación de una autorización concreta, retirada de facultad del representante, rectificación y supresión de datos. Una no debe registrarse falsamente como otra ni borrar la evidencia histórica.
3. Evaluar restricciones/obligaciones aplicables con motivación y plazo específico. Atender consultas y reclamos conforme a los términos legales de los artículos 14 y 15 de la Ley 1581; aprobar un procedimiento y seguimiento de plazos, sin inventar términos uniformes para todo trámite.
4. Bloquear nuevos usos afectados y comunicar la decisión y las medidas. Mantener el servicio deportivo si solo se negó o revocó un tratamiento opcional; una conservación obligatoria residual no permite mantener publicidad o análisis opcional.
5. Comunicar instrucciones a encargados/proveedores y documentar su cumplimiento. Para publicaciones, retirar de medios controlados y gestionar retiradas de terceros; explicar límites reales sin prometer desaparición total de internet ni desatender el reclamo.
6. Para vídeos internos, IA y biometría futuros, disponer de un inventario que localice originales, derivados, copias y destinatarios. Detener nuevos análisis y tratar la supresión o restricción que proceda. No prometer «desentrenar» un modelo si no existe capacidad demostrada; ese riesgo debe resolverse antes de autorizar cualquier entrenamiento.
7. Conservar evidencia mínima de recepción, fundamento, responsable, fecha y actuaciones; tratar copias de respaldo con reglas que impidan reactivar datos retirados al restaurar. Definir jurídicamente las excepciones y la conservación residual, sin eliminar ni retener todo por defecto.

Una negativa o el silencio no se convierten en otorgamiento. Revocar no crea autorización para otro alcance ni implica consentimiento para una versión futura.

## 7. Brechas que el catálogo por sí solo no resuelve

La propuesta encaja en los campos de `TipoAutorizacion` únicamente después de aprobar textos, pero no debe atribuir al software capacidades que no tiene:

- El catálogo no incorpora un flujo jurídico de aprobación, verificación de firmas, cálculo/custodia de hashes de textos ni gestor documental. Debe existir el expediente institucional externo antes de una carga.
- `Autorizacion` está vinculada obligatoriamente a un deportista y su esquema de otorgantes no es un registro general de decisiones propias de cualquier adulto contacto. No usar la ficha del menor para fingir consentimiento del acudiente/contacto sobre sus propios datos. Resolver procedimiento externo válido y evaluar después una adaptación explícita si se necesita.
- No hay decisiones granulares por canal, proveedor o pieza de publicación, ni registro específico del ejercicio de escucha del menor. Las condiciones o negativas parciales no deben representarse como un otorgamiento global; subdividir textos/códigos o aprobar una evolución futura antes de depender de esas funciones.
- El estado `activo` del tipo y la referencia a una comprobación exacta tienen efectos operativos. Revisar cómo retirar una versión sin invalidar indiscriminadamente historia o interpretar una nueva como consentimiento adquirido.
- La fase actual no ejecuta bajas en proveedores, retiro de publicaciones, supresión de medios ni procesos de IA/biometría. Documentarlos no los implementa. Si una finalidad requiere controles inexistentes, no debe ponerse en operación.

No se propone modificar ninguno de estos contratos durante este encargo ni incorporar excepciones jurídicas a fuerza de crear autorizaciones ficticias. Un fundamento distinto del consentimiento, cuando sea válido, deberá documentarse como tal; no registrarse como una decisión «otorgada» que nadie emitió.

## 8. Decisiones pendientes y criterio para una aprobación posterior

| Decisión | Quién debe validarla antes de una carga/uso |
| --- | --- |
| Identidad jurídica del responsable y facultad del aprobador; datos reales del canal de derechos | Representante legal y asesoría jurídica |
| Datos estrictamente necesarios y posibles excepciones legales por operación | Jurídica y coordinador |
| División de comunicaciones/emergencias, datos propios de contactos adultos y canales concretos | Jurídica, coordinador y administración |
| Requisitos de representación, escucha del menor, desacuerdos y cambio de edad/representación | Jurídica y responsable institucional competente |
| Finalidades/textos exactos, vigencia y criterios de conservación por categoría | Aprobador institucional con revisión jurídica |
| Medios y opciones separadas de publicación, licencias y retirada de piezas | Jurídica y responsable de comunicaciones designado |
| Diseño de ClimbVision-AI, riesgos, proveedores, inferencias y alternativas | Jurídica, seguridad/técnica y coordinador |
| Transferencias frente a transmisiones, países, contratos y eventuales transferencias de tecnología | Jurídica; revisar art. 26, reglamentación y disposiciones aplicables al proveedor concreto |
| Necesidad real de biometría y alternativas, o decisión de descartarla | Representante legal tras revisión especial documentada |
| Repositorio, actas, SHA-256, responsables de custodia y procedimiento de retiro de versiones | Administración institucional y seguridad |
| Brechas del modelo actual y permiso separado para cualquier evolución necesaria | Usuario responsable del proyecto, tras definir requisitos |

Para IA/proveedores, revisar además si una operación específica entra en las instrucciones de transferencia de tecnología de la SIC de 2025; no confundirlas con una licencia genérica para mover datos. [Circular Externa 002 del 7 de octubre de 2025](https://sedeelectronica.sic.gov.co/transparencia/normativa/circular-externa-no-002-del-07-de-octubre-de-2025).

Una aprobación posterior deberá identificar **código, versión, texto final, referencia localizable, acta, aprobador y fecha**, junto con alcance, alternativa, destinatarios y controles efectivos. Revisar primero el núcleo operativo; mantener medios, IA y biometría como propuestas futuras hasta sus aprobaciones y habilitaciones independientes. Aprobar este análisis no equivale a aprobar textos definitivos, convertir la reserva biométrica en una finalidad autorizable ni conceder autorizaciones individuales.

**Punto de parada:** documento entregado para revisión. Catálogo sin cargar, consentimientos sin declarar aprobados y plataforma sin cambios. Se espera la decisión jurídica e institucional antes de redactar textos finales o solicitar una actuación posterior sobre el sistema.
