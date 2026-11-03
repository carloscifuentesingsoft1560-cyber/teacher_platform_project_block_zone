# Contratos compartidos para los módulos futuros

Diseño de Etapa 1, versión propuesta 0.1. No crea modelos, API ni contenido institucional. Los nombres candidatos y ejemplos de payload son contratos a revisar al implementar cada etapa. Se conserva el monolito Django/DRF, PostgreSQL y React/Vite/Sass.

## Identidad, contexto y autorización

Reutilizar Usuario, Deportista, Acudiente, Grupo, Nivel, Disciplina, Periodo, Asignacion e Inscripcion. Una participación en varios grupos no crea otra persona. La identidad transversal y sus enlaces se resolverán en Etapa 2; no usar nombre, correo o rol como identificador de persona. El nivel se interpreta por disciplina e historial, no como un campo global mutable contradictorio con matrícula.

Toda acción evalúa cuenta activa, facultades vigentes, ámbito, objeto y finalidad. Una combinación de roles no habilita por sí sola datos clínicos ni medios de menores. Los filtros de lista y la recuperación por ID deben compartir el mismo ámbito; UUID no sustituye autorización. Revocaciones se revalidan en servidor en la siguiente petición y antes de confirmar una escritura. Las cuentas nuevas no reciben acceso histórico automáticamente.

Reutilizar sesión Django, CSRF y cookies del mismo origen; no introducir JWT como requisito del diseño. Mantener serializers estrictos, datos mínimos por rol y errores del contrato actual. Actor/fecha/versiones se asignan por servidor; no confiar en IDs de autor enviados por cliente. Cambio de rol o vínculo no reasigna autores históricos.

## Identidad estable, versiones y evidencia

Cada entidad con historia distingue identidad estable, versión exacta y estado. Un registro ejecutado referencia la versión utilizada, nunca “la última” mediante consulta dinámica. Actor, fecha de registro, fecha efectiva y fuente tienen significados separados. Timestamps con zona; día operativo en America/Bogota; duraciones con unidad explícita.

Malla original, propuesta revisada y aprobada son estados diferentes. Lo mismo aplica a ejercicio, protocolo, reglamento y montaje. Aprobar contenido institucional no equivale a aprobar de antemano cada sesión. El documento fuente conserva hash, hoja/celda o página, texto original y versión. La corrección genera una revisión que enlaza el original; no reescribe la evidencia fuente.

Reutilizar Registro/version y patrones inmutables existentes donde corresponda. Una cifra de versión no garantiza snapshot de todo el registro: la implementación definirá campos congelados y restricciones por entidad. No usar CambioAdministrativo como almacén de texto clínico o copias completas de datos personales.

## Escritura, concurrencia y errores

Las transiciones sensibles son comandos de dominio, con transacción, lectura actual de permisos y bloqueo de las filas afectadas en un orden documentado. Reutilizar conflictos por versión; no confiar únicamente en validación previa del serializer. Versiones obsoletas producen 409 según el patrón existente. Errores de campos o reglas de entrada mantienen 400; sesión/CSRF y permisos conservan semántica actual. Un objeto fuera del ámbito no revela su existencia ni datos.

Para operaciones reintentables, clave UUID idempotente con alcance definido (actor/operación/objeto o revisión). La misma clave y datos devuelve el resultado confirmado; misma clave con otra operación o datos produce conflicto. Idempotencia no evita revalidar autoridad y visibilidad. Duplicados de sesión/asistencia, votos y exposición requieren además restricciones de dominio en base de datos.

Una escritura deportiva válida y su evento se confirman atómicamente. La entrega de una notificación se realiza después, con estado/reintentos, sin revertir por un fallo ordinario de canal. Acciones con razón de seguridad bloqueante deben definirla expresamente. Mantener los eventos históricos y evitar eventos duplicados durante reintentos.

## Sesión canónica y asistencia

Una Sesion candidata representa una exposición de grupo y profesor en fecha y franja; puede enlazar objetivos curriculares y ciclos deportivos simultáneamente. Especialización no crea una sesión curricular y otra deportiva. El calendario organizativo existente es una fuente de propuesta horaria, no evidencia de ejecución.

Separar versión planificada, ejecución real y corrección posterior. Fases inicial/central/final y tareas se ordenan; guardan duración planificada y realizada por separado. El total planificado debe ser coherente con fases/tareas sin sumar actividades simultáneas como si fueran secuenciales. Referenciar versiones de ejercicios, protocolos y montajes; una actividad propia conserva autor y contenido.

Contrato mínimo candidato de una tarea:

```json
{
  "sesion_version": "referencia a versión exacta",
  "orden": 1,
  "ejercicio_version": null,
  "instrucciones_propias": "contenido docente",
  "duracion_planificada": {"valor": 10, "unidad": "min"},
  "montaje_version": null,
  "exigencias_funcionales": [],
  "adaptaciones": []
}
```

Nombres y tipos finales se fijarán en su etapa; no publicar esas referencias textuales como esquema API definitivo. Dos sesiones diarias por profesor se controlan dentro de la transacción, también al reprogramar. Definir qué estados computan y cómo afectan cancelaciones antes de codificar; no convertir esta regla en dos copias o dos inscripciones. La duración depende de programa/población, con Babys aproximadamente 40–45 y Lúdico aproximadamente 60 minutos; no imponer 120 a todo grupo.

Asistencia por sesión e inscripción: asistió/no asistió/tarde/excusa/retiro. Confirmación del lote debe ser atómica y no permitir edición ordinaria posterior. Cierre de sesión y cierre de asistencia tienen una tabla de transiciones conjunta, sin inferir que “sesión realizada” significa “asistencia confirmada”. Corrección extraordinaria mediante comando autorizado y evento con vínculo al registro anterior. Conservar el padrón de referencia ante cambios de matrícula; no atribuir retroactivamente asistencia a otra inscripción.

## Evaluación, progresión y publicación

ProtocoloVersion define población, instrumento, estaciones, criterio, escala, condiciones, seguridad y aprobación. Aplicacion referencia deportista/inscripción, sesión cuando corresponda, protocolo exacto, evaluador y condiciones. Observación, resultado, interpretación, revisión y publicación son conceptos separados.

Estado de dato: no evaluado, no aplicable, interrumpido, ausente o observado. Un valor vacío no es cero ni descriptor mínimo. La escala ordinal exploración/en desarrollo/consolidado/transferencia no es porcentaje ni admite promedio por defecto. La implementación debe distinguir estado de dato y descriptor para evitar usar “no evaluado” como puntuación. No incorporar umbrales heredados ni baremos no aprobados.

Una estación puede designar un bloque del catálogo oficial con versión de montaje exacta; no duplicar el bloque en otro banco. Montaje desmontado bloquea aplicaciones futuras salvo equivalente explícitamente aprobado, pero conserva aplicaciones históricas. ProgresionInstitucional existente enlazará evidencias versionadas; una evaluación no dispara cambio de nivel. Flujo objetivo docente propone → coordinador revisa → administrador formaliza; actualmente la ejecución sigue compartida hasta su cambio autorizado en Etapa 2.

Publicar un resultado es una acción explícita con destinatarios/finalidad. Revisión interna no hace visible automáticamente contenido a deportista/acudiente. Una solicitud de revisión no sobrescribe evaluación oficial.

## Planificación, restricciones y cargas

Temporada/ciclos y modelo metodológico enlazan sesiones existentes. Modelo/plantilla documenta población, fuente, límites, secuencia candidata, evidencia y estado institucional. La frecuencia real de dos sesiones semanales no se rellena copiando programas de alta frecuencia. ATR no comprime ciclos para encajar fechas. Cambios de competición A/B/C generan propuestas versionadas; el entrenador confirma, sin alterar pasado ejecutado.

Antes de habilitar tareas, se requiere un contrato de autorización funcional: procedencia competente, vigencia, actividades permitidas, restricciones estructuradas y condiciones incompatibles, con detalle clínico segregado. Una restricción vigente prevalece sobre el plan, incluso si cambia entre planificación y ejecución. Resultado de compatibilidad: permitido, incompatible o requiere revisión; falta de información relevante no se convierte en permitido. Este control debe existir antes de abrir el planificador a ejecución, aunque RSD longitudinal se complete después.

La adaptación individual referencia plan original y versión; no cambia el grupo por un solo deportista. Profesor adapta dentro de autorización funcional y no emite alta clínica. Participación/deporte/rendimiento son categorías de seguimiento deportivo, no fases clínicas automáticas.

Una Exposicion candidata identifica sesión/deportista/ejecución para agregación única. Intentos, tareas y vídeos son detalles de esa exposición y no nuevas sesiones sumables. Carga externa registra cada magnitud por separado; sRPE = duración de sesión en minutos × RPE de sesión según protocolo aplicable; unidad UA. Tiempo activo separado. Guardar escala, momento, fuente, faltantes, plan/real y versión. V/color/RIC no se convierten en intensidad fisiológica. No diagnosticar lesión o recuperación ni prescribir máximos a menores a partir de estos datos.

## Route Setting y captura audiovisual

Separar presa física, ubicación/contorno sobre mapa versionado, pertenencia a bloque y función inicio/zona/top/intermedia. La misma presa puede integrar varios bloques y tener funciones distintas en cada uno. Geometría/forma, orientación, usos posibles y uso observado son campos diferentes. Foto no mide por sí misma profundidad, fricción ni fuerza. Grado V exacto independiente de color; estilos multietiqueta del catálogo institucional.

RIC/RICO es valoración deportiva candidata por persona y versión; una persona con dos roles tiene un voto, no dos. Mostrar tamaño/distribución/dispersión y desacuerdo; no sustituye revisión física de seguridad. Routesetter prepara; administración publica ficha oficial. Desmontaje termina vigencia física sin borrar resultados o vídeos históricos.

ArchivoPrivado será servicio común de fotos/vídeos/materiales. Metadatos mínimos: identificador opaco, ubicación privada, propietario/contexto, tipo verificado, tamaño, hash, fecha/autor, finalidad/autorización, versión y política de retención. Backend valida tamaño, extensión, firma y tipo; nombre original nunca define ruta de disco. Descargas y rangos de vídeo revalidan acceso. No emitir URL pública permanente ni almacenar secretos de acceso en React. Revocación impide nuevas lecturas aunque exista un enlace copiado; documentar límites de copias ya descargadas.

Captura básica desde un teléfono: cargar/capturar foto y vídeo; asociar montaje exacto, bloque, deportista, intento y sesión cuando corresponda. Subida reintentable no duplica intento ni archivo; estado de transferencia separado de resultado deportivo. No imponer dos teléfonos. Compatibilidad y formatos Android/iPhone se prueban en dispositivo real durante su etapa.

AnotacionVersion humana: intervalo temporal y unidad, extremidad, presa, evento, visibilidad, incertidumbre, autor y revisión. Conservar original y correcciones. Contacto observado no es por sí mismo zona/top conseguido: resultado usa criterio/reglamento. Predicción algorítmica futura es otro origen y no sustituye anotación humana o decisión profesional. Grabación autorizada no habilita entrenamiento IA; finalidad de investigación/IA requiere autorización aplicable y calidad independiente. No se implementa IA en estas etapas.

## Criterios compartidos de aceptación

Cada módulo añadirá pruebas de API directa, objeto ajeno, revocación, roles combinados, reintento, concurrencia, versión obsoleta, ausencias y preservación histórica. Probar relación con matrícula vigente y fechas reales; usar datos ficticios. Gráficas muestran unidades/leyendas/faltantes y versión del indicador. Exportación respeta el mismo ámbito y registra acceso sensible. No aprobar contenido metodológico mediante un test de software ni declarar contratos implementados por existir este documento.
