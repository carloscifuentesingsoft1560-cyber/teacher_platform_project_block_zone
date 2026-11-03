
import { useRef, useState } from 'react';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const FASES = [
  { codigo: 'inicial', nombre: 'Fase inicial' },
  { codigo: 'central', nombre: 'Fase central' },
  { codigo: 'final', nombre: 'Fase final' },
];

function minutosEntre(inicio, fin) {
  if (!inicio || !fin) return 0;

  const [hi, mi] = inicio.split(':').map(Number);
  const [hf, mf] = fin.split(':').map(Number);

  return hf * 60 + mf - (hi * 60 + mi);
}

function planVinculado(plan) {
  if (!plan) return false;

  const referencias = [
    'programa',
    'malla_version',
    'fase_curricular',
    'semana',
    'clase',
  ];

  if (referencias.some(
    (campo) => plan[campo] != null
  )) {
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

  if (tareas.length !== FASES.length) return false;

  return tareas.every(
    (tarea, indice) =>
      tarea.fase === FASES[indice].codigo
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
  const central = Math.max(
    1,
    total - inicial - final
  );

  return [
    {
      fase: 'inicial',
      minutos: String(inicial),
      objetivo: '',
      instrucciones: '',
    },
    {
      fase: 'central',
      minutos: String(central),
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

  const bloqueoCurricular = planVinculado(anterior);
  const bloqueoEstructura = !estructuraCompatible(anterior);

  const editable =
    sesion.estado === 'planificada' &&
    !bloqueoCurricular &&
    !bloqueoEstructura;

  const [objetivo, establecerObjetivo] = useState(
    anterior?.objetivo || ''
  );

  const [tareas, establecerTareas] = useState(
    () => tareasIniciales(sesion)
  );

  const [enviando, establecerEnviando] =
    useState(false);

  const [error, establecerError] =
    useState(null);

  const [aviso, establecerAviso] =
    useState('');

  const [requiereActualizacion, establecerRequiereActualizacion] =
    useState(false);

  const intento = useRef(null);

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

  const bloqueado =
    !editable ||
    enviando ||
    requiereActualizacion;

  function modificarObjetivo(valor) {
    establecerObjetivo(valor);
    intento.current = null;
    establecerAviso('');
    establecerError(null);
  }

  function modificarTarea(indice, campo, valor) {
    establecerTareas((actuales) =>
      actuales.map((tarea, posicion) =>
        posicion === indice
          ? { ...tarea, [campo]: valor }
          : tarea
      )
    );

    intento.current = null;
    establecerAviso('');
    establecerError(null);
  }

  function validar() {
    if (sesion.estado !== 'planificada') {
      return 'La sesión no admite una nueva planificación.';
    }

    if (bloqueoCurricular) {
      return (
        'Esta sesión contiene referencias curriculares ' +
        'o ejercicios vinculados. La edición básica ' +
        'no puede conservar esas relaciones.'
      );
    }

    if (bloqueoEstructura) {
      return (
        'El plan existente tiene una estructura de ' +
        'actividades que requiere el editor completo.'
      );
    }

    if (!objetivo.trim()) {
      return 'Debes escribir el objetivo general de la sesión.';
    }

    if (duracion < 3) {
      return 'La sesión no tiene duración suficiente.';
    }

    if (tareas.length !== FASES.length) {
      return 'Debes registrar las tres fases.';
    }

    for (let i = 0; i < FASES.length; i += 1) {
      const fase = FASES[i];
      const tarea = tareas[i];

      if (tarea.fase !== fase.codigo) {
        return 'El orden de las fases no es válido.';
      }

      const minutos = Number(tarea.minutos);

      if (
        !tarea.minutos ||
        !Number.isInteger(minutos) ||
        minutos < 1
      ) {
        return (
          `La ${fase.nombre.toLowerCase()} ` +
          'necesita una duración válida.'
        );
      }

      if (!tarea.instrucciones.trim()) {
        return (
          'Describe las actividades de la ' +
          fase.nombre.toLowerCase() + '.'
        );
      }
    }

    if (diferencia !== 0) {
      return (
        'Los minutos deben coincidir con ' +
        'la duración de la sesión.'
      );
    }

    return null;
  }

  async function guardarPlan(evento) {
    evento.preventDefault();

    if (
      enviando ||
      requiereActualizacion ||
      !editable
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

    const firma = JSON.stringify(contenido);

    if (!intento.current) {
      intento.current = {
        firma,
        clave: crypto.randomUUID(),
      };
    }

    if (intento.current.firma !== firma) {
      establecerError(
        new Error(
          'El formulario cambió. Consulta la sesión nuevamente.'
        )
      );
      return;
    }

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

      establecerAviso(
        'La revisión se guardó correctamente.'
      );

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
                'No se recibió respuesta del servidor. ' +
                'Consulta el detalle antes de intentar ' +
                'otra modificación.'
              )
            : (
                'La operación fue rechazada. Actualiza ' +
                'la sesión y comprueba sus permisos ' +
                'y su versión.'
              )
        );
      }
    } finally {
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h2>Planificación de la sesión</h2>

      <p>
        Organiza las fases inicial, central y final.
        Cada guardado crea una nueva revisión.
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

        <dt>Versión</dt>
        <dd>{sesion.version}</dd>
      </dl>

      {sesion.estado !== 'planificada' && (
        <p className="mensaje-error" role="alert">
          Esta sesión no está en estado planificada.
          No se puede crear otra revisión.
        </p>
      )}

      {bloqueoCurricular && (
        <p className="mensaje-error" role="alert">
          Esta sesión tiene referencias curriculares,
          competencias o ejercicios asociados.
          Para protegerlas, la edición básica está
          deshabilitada hasta incorporar el editor
          curricular completo.
        </p>
      )}

      {bloqueoEstructura && !bloqueoCurricular && (
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

        <ErrorGestion error={error} />

        {aviso && (
          <p role="status">{aviso}</p>
        )}

        <div className="acciones">
          <button
            type="submit"
            disabled={
              bloqueado ||
              diferencia !== 0
            }
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
