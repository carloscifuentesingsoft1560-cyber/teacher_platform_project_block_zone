
import { useRef, useState } from 'react';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';
import { ContextoCurricularSesion } from './ContextoCurricularSesion.jsx';

const FASES = [
  { codigo: 'inicial', nombre: 'Fase inicial' },
  { codigo: 'central', nombre: 'Fase central' },
  { codigo: 'final', nombre: 'Fase final' },
];

const CURRICULO_VACIO = {
  programa_id: null,
  malla_version_id: null,
  fase_curricular_id: null,
  semana_id: null,
  clase_id: null,
  competencias_ids: [],
};

function minutosEntre(inicio, fin) {
  if (!inicio || !fin) return 0;

  const [hi, mi] = inicio.split(':').map(Number);
  const [hf, mf] = fin.split(':').map(Number);

  return hf * 60 + mf - (hi * 60 + mi);
}

function tieneReferencias(plan) {
  if (!plan) return false;

  const campos = [
    'programa',
    'malla_version',
    'fase_curricular',
    'semana',
    'clase',
  ];

  if (campos.some((campo) => plan[campo] != null)) {
    return true;
  }

  if (plan.competencias?.length) return true;

  return (plan.tareas || []).some(
    (tarea) =>
      tarea.ejercicio_version != null ||
      tarea.ejercicio_detalle != null
  );
}

function estructuraCompatible(plan) {
  if (!plan) return true;

  const tareas = plan.tareas || [];

  return (
    tareas.length === 3 &&
    tareas.every(
      (tarea, indice) =>
        tarea.fase === FASES[indice].codigo
    )
  );
}

function tareasIniciales(sesion) {
  const anterior = sesion.planes?.at(-1);

  if (anterior?.tareas?.length) {
    return anterior.tareas.map((tarea) => ({
      fase: tarea.fase,
      minutos: String(tarea.minutos),
      objetivo: tarea.objetivo || '',
      instrucciones: tarea.instrucciones || '',
    }));
  }

  const total = minutosEntre(
    sesion.hora_inicio,
    sesion.hora_fin
  );

  const inicial = Math.max(1, Math.floor(total / 4));
  const final = Math.max(1, Math.floor(total / 4));

  return [
    {
      fase: 'inicial',
      minutos: String(inicial),
      objetivo: '',
      instrucciones: '',
    },
    {
      fase: 'central',
      minutos: String(Math.max(1, total - inicial - final)),
      objetivo: '',
      instrucciones: '',
    },
    {
      fase: 'final',
      minutos: String(final),
      objetivo: '',
      instrucciones: '',
    },
  ];
}

export function PlanificacionSesion({
  sesion,
  onGuardado,
  onCancelar,
}) {
  const anterior = sesion.planes?.at(-1);

  const bloqueoReferencias = tieneReferencias(anterior);
  const bloqueoEstructura = !estructuraCompatible(anterior);

  const editable =
    sesion.estado === 'planificada' &&
    sesion.estado_ejecucion !==
      'registrada_pendiente_validacion' &&
    !bloqueoReferencias &&
    !bloqueoEstructura;

  const [objetivo, establecerObjetivo] = useState(
    anterior?.objetivo || ''
  );

  const [tareas, establecerTareas] = useState(
    () => tareasIniciales(sesion)
  );

  const [vincularCurriculo, establecerVincularCurriculo] =
    useState(false);

  const [curriculo, establecerCurriculo] = useState({
    ...CURRICULO_VACIO,
  });

  // Solo se autoriza guardar cuando el catálogo vigente
  // confirma que terminó sin errores.
  const [estadoCatalogos, establecerEstadoCatalogos] =
    useState(null);

  const [enviando, establecerEnviando] = useState(false);
  const [error, establecerError] = useState(null);
  const [aviso, establecerAviso] = useState('');

  const [
    requiereActualizacion,
    establecerRequiereActualizacion,
  ] = useState(false);

  const intento = useRef(null);
  const envioActivo = useRef(false);

  const duracion = minutosEntre(
    sesion.hora_inicio,
    sesion.hora_fin
  );

  const distribuidos = tareas.reduce(
    (total, tarea) =>
      total + (Number(tarea.minutos) || 0),
    0
  );

  const diferencia = duracion - distribuidos;

  const claveCurricular =
    `${sesion.id}:${curriculo.malla_version_id || 0}`;

  const catalogosListos =
    !vincularCurriculo ||
    (
      estadoCatalogos?.clave === claveCurricular &&
      estadoCatalogos?.listo === true
    );

  const bloqueado =
    !editable ||
    enviando ||
    requiereActualizacion;

  const guardadoBloqueado =
    bloqueado ||
    diferencia !== 0 ||
    !catalogosListos;

  function invalidarIntento() {
    intento.current = null;
    establecerAviso('');
    establecerError(null);
  }

  function modificarObjetivo(valor) {
    establecerObjetivo(valor);
    invalidarIntento();
  }

  function modificarTarea(indice, campo, valor) {
    establecerTareas((actuales) =>
      actuales.map((tarea, posicion) =>
        posicion === indice
          ? { ...tarea, [campo]: valor }
          : tarea
      )
    );

    invalidarIntento();
  }

  function cambiarVinculacion(marcado) {
    establecerVincularCurriculo(marcado);
    establecerCurriculo({ ...CURRICULO_VACIO });
    establecerEstadoCatalogos(null);
    invalidarIntento();
  }

  function cambiarCurriculo(nuevo) {
    if (nuevo.malla_version_id !== curriculo.malla_version_id) {
      establecerEstadoCatalogos(null);
    }
    establecerCurriculo(nuevo);
    invalidarIntento();
  }

  function validar() {
    if (!editable) {
      return 'La sesión no permite esta edición.';
    }

    if (!objetivo.trim()) {
      return 'Debes escribir el objetivo general.';
    }

    if (duracion < 3 || tareas.length !== 3) {
      return 'La duración o las fases no son válidas.';
    }

    for (let indice = 0; indice < 3; indice += 1) {
      const tarea = tareas[indice];
      const fase = FASES[indice];

      if (tarea.fase !== fase.codigo) {
        return 'Las fases deben conservar su orden.';
      }

      const minutos = Number(tarea.minutos);

      if (
        !tarea.minutos ||
        !Number.isInteger(minutos) ||
        minutos <= 0
      ) {
        return `Duración inválida en ${fase.nombre}.`;
      }

      if (!tarea.instrucciones.trim()) {
        return `Describe las actividades de ${fase.nombre}.`;
      }
    }

    if (diferencia !== 0) {
      return 'Las fases deben completar la duración programada.';
    }

    if (vincularCurriculo) {
      if (!catalogosListos) {
        return (
          'Espera a que se carguen correctamente ' +
          'los catálogos curriculares.'
        );
      }

      if (
        !curriculo.programa_id ||
        !curriculo.malla_version_id
      ) {
        return (
          'Para vincular currículo, selecciona un ' +
          'programa y una versión de malla.'
        );
      }

      if (
        new Set(curriculo.competencias_ids).size !==
        curriculo.competencias_ids.length
      ) {
        return 'No se permiten competencias repetidas.';
      }
    }

    return null;
  }

  async function guardarPlan(evento) {
    evento.preventDefault();

    if (
      envioActivo.current ||
      requiereActualizacion ||
      !editable ||
      !catalogosListos
    ) {
      return;
    }

    establecerError(null);
    establecerAviso('');

    const problema = validar();

    if (problema) {
      establecerError(new Error(problema));
      return;
    }

    const contenido = {
      version: sesion.version,
      objetivo: objetivo.trim(),
      tareas: tareas.map((tarea) => ({
        fase: tarea.fase,
        minutos: Number(tarea.minutos),
        objetivo: tarea.objetivo.trim(),
        instrucciones: tarea.instrucciones.trim(),
      })),
    };

    if (vincularCurriculo) {
      Object.assign(contenido, {
        programa_id: curriculo.programa_id,
        malla_version_id: curriculo.malla_version_id,
        fase_curricular_id: curriculo.fase_curricular_id,
        semana_id: curriculo.semana_id,
        clase_id: curriculo.clase_id,
        competencias_ids: [...curriculo.competencias_ids],
      });
    }

    const firma = JSON.stringify(contenido);

    if (!intento.current) {
      intento.current = {
        clave: crypto.randomUUID(),
        firma,
      };
    }

    if (intento.current.firma !== firma) {
      establecerError(
        new Error('La solicitud cambió. Actualiza la sesión.')
      );
      return;
    }

    envioActivo.current = true;
    establecerEnviando(true);

    try {
      const resultado = await guardar(
        `/sesiones/${sesion.id}/`,
        {
          clave: intento.current.clave,
          ...contenido,
        },
        'PATCH'
      );

      intento.current = null;
      establecerAviso('Planificación guardada correctamente.');
      onGuardado?.(resultado);
    } catch (fallo) {
      establecerError(fallo);

      if (
        fallo.estado === 0 ||
        [400, 401, 403, 409].includes(fallo.estado)
      ) {
        establecerRequiereActualizacion(true);

        establecerAviso(
          fallo.estado === 0
            ? (
                'No llegó la respuesta del servidor. ' +
                'Consulta la sesión antes de reintentar.'
              )
            : (
                'La operación fue rechazada. ' +
                'Actualiza la sesión y comprueba los datos y permisos ' +
                'antes de volver a intentarlo.'
              )
        );
      }
    } finally {
      envioActivo.current = false;
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h2>Planificación de la sesión</h2>

      <p>
        Define objetivos, actividades y, cuando corresponda,
        su vinculación con una malla curricular aprobada.
      </p>

      <dl>
        <dt>Fecha</dt>
        <dd>{sesion.fecha}</dd>

        <dt>Horario</dt>
        <dd>
          {sesion.hora_inicio?.slice(0, 5)}
          {' – '}
          {sesion.hora_fin?.slice(0, 5)}
        </dd>

        <dt>Duración</dt>
        <dd>{duracion} minutos</dd>

        <dt>Versión de sesión</dt>
        <dd>{sesion.version}</dd>
      </dl>

      {sesion.estado !== 'planificada' && (
        <p className="mensaje-error" role="alert">
          Esta sesión no está en estado planificada.
          No se puede crear otra revisión.
        </p>
      )}

      {sesion.estado_ejecucion ===
        'registrada_pendiente_validacion' && (
        <p className="mensaje-error" role="alert">
          La ejecución está finalizada. Su planificación
          se conserva como historial y no puede modificarse.
        </p>
      )}

      {bloqueoReferencias && (
        <p className="mensaje-error" role="alert">
          Esta sesión tiene referencias curriculares,
          competencias o ejercicios asociados.
          Para protegerlas, la edición básica está
          deshabilitada hasta incorporar el editor
          curricular completo.
        </p>
      )}

      {bloqueoEstructura && !bloqueoReferencias && (
        <p className="mensaje-error" role="alert">
          El plan tiene una estructura distinta a las
          tres fases básicas. Su edición requiere el
          editor completo para conservar las actividades.
        </p>
      )}

      <form onSubmit={guardarPlan}>
        <label
          className="campo-gestion"
          htmlFor="objetivo-general-sesion"
        >
          Objetivo general de la sesión

          <textarea
            id="objetivo-general-sesion"
            rows={3}
            required
            value={objetivo}
            disabled={bloqueado}
            onChange={(evento) =>
              modificarObjetivo(evento.target.value)
            }
            placeholder="Describe el objetivo del entrenamiento."
          />
        </label>

        <h3>Distribución de actividades</h3>

        {FASES.map((fase, indice) => {
          const tarea = tareas[indice];

          if (!tarea) return null;

          return (
            <fieldset
              className="fila-horario"
              key={fase.codigo}
              disabled={bloqueado}
            >
              <legend>{fase.nombre}</legend>

              <label className="campo-gestion">
                Duración en minutos

                <input
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={tarea.minutos}
                  onChange={(evento) =>
                    modificarTarea(
                      indice,
                      'minutos',
                      evento.target.value
                    )
                  }
                />
              </label>

              <label className="campo-gestion">
                Objetivo específico

                <input
                  type="text"
                  value={tarea.objetivo}
                  onChange={(evento) =>
                    modificarTarea(
                      indice,
                      'objetivo',
                      evento.target.value
                    )
                  }
                />
              </label>

              <label className="campo-gestion">
                Actividades e instrucciones

                <textarea
                  rows={4}
                  required
                  value={tarea.instrucciones}
                  onChange={(evento) =>
                    modificarTarea(
                      indice,
                      'instrucciones',
                      evento.target.value
                    )
                  }
                />
              </label>
            </fieldset>
          );
        })}

        <p>
          <strong>Duración total:</strong>{' '}
          {duracion} minutos
        </p>

        <p>
          <strong>Minutos distribuidos:</strong>{' '}
          {distribuidos}
        </p>

        <p>
          <strong>Diferencia:</strong>{' '}
          {diferencia} minutos
        </p>

        {diferencia !== 0 && (
          <p className="mensaje-error">
            Ajusta los minutos de las fases hasta
            completar exactamente la duración programada.
          </p>
        )}

        <fieldset disabled={bloqueado}>
          <legend>Contenido curricular</legend>

          <label className="campo-checkbox">
            <input
              type="checkbox"
              checked={vincularCurriculo}
              onChange={(evento) =>
                cambiarVinculacion(evento.target.checked)
              }
            />

            Vincular esta planificación a una malla curricular
          </label>

          {vincularCurriculo && (
            <ContextoCurricularSesion
              sesionId={sesion.id}
              valor={curriculo}
              cambiar={cambiarCurriculo}
              disabled={bloqueado}
              onEstadoCambio={establecerEstadoCatalogos}
            />
          )}
        </fieldset>

        {vincularCurriculo && (
          <p>
            La malla y las competencias seleccionadas se
            enviarán a Django para verificar su vigencia
            y compatibilidad con el grupo.
          </p>
        )}

        {vincularCurriculo && !catalogosListos && (
          <p role="status">
            El guardado permanecerá bloqueado hasta
            completar correctamente la consulta curricular.
          </p>
        )}

        <ErrorGestion error={error} />

        {aviso && <p role="status">{aviso}</p>}

        <div className="acciones">
          <button
            type="submit"
            disabled={guardadoBloqueado}
          >
            {enviando
              ? 'Guardando planificación…'
              : 'Guardar planificación'}
          </button>

          <button
            type="button"
            className="boton-secundario"
            onClick={onCancelar}
            disabled={enviando}
          >
            Cerrar planificación
          </button>
        </div>
      </form>
    </section>
  );
}
