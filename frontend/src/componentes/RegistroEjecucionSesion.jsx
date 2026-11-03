
import { useEffect, useRef, useState } from 'react';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const RESULTADOS = [
  ['realizada', 'Realizada'],
  ['modificada', 'Modificada'],
  ['omitida', 'Omitida'],
];

const FASES = {
  inicial: 'Fase inicial',
  central: 'Fase central',
  final: 'Fase final',
};

function fechaLocalBogota(valor) {
  if (!valor) return '';

  const fecha = new Date(valor);

  if (Number.isNaN(fecha.getTime())) return '';

  const partes = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(fecha);

  const obtener = (tipo) =>
    partes.find((parte) => parte.type === tipo)?.value || '';

  return (
    `${obtener('year')}-${obtener('month')}-${obtener('day')}` +
    `T${obtener('hour')}:${obtener('minute')}`
  );
}

function actividadInicial(tarea) {
  return {
    tarea: tarea.id,
    resultado: 'realizada',
    minutos: String(tarea.minutos),
    descripcion: '',
    adaptacion_metodologica: '',
    motivo_omision: '',
  };
}

function actividadesIniciales(plan) {
  return (plan?.tareas || []).map(actividadInicial);
}

function fechaISO(valor) {
  if (!valor) return null;

  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(valor)) {
    return null;
  }

  const fecha = new Date(`${valor}:00-05:00`);

  if (Number.isNaN(fecha.getTime())) return null;

  if (fechaLocalBogota(fecha.toISOString()) !== valor) {
    return null;
  }

  return `${valor}:00-05:00`;
}

function validarActividades(plan, actividades) {
  const tareas = plan?.tareas || [];

  if (
    !tareas.length ||
    tareas.some((tarea) => !Number.isInteger(tarea.id)) ||
    new Set(tareas.map((tarea) => tarea.id)).size !== tareas.length ||
    actividades.length !== tareas.length
  ) {
    return 'El plan no contiene identificadores de tareas válidos.';
  }

  for (let indice = 0; indice < tareas.length; indice += 1) {
    const actividad = actividades[indice];

    if (actividad.tarea !== tareas[indice].id) {
      return 'Las actividades no coinciden con las tareas del plan.';
    }

    const minutos = Number(actividad.minutos);

    if (
      !Number.isInteger(minutos) ||
      minutos < 0 ||
      minutos > 32767
    ) {
      return 'Los minutos de las actividades deben ser enteros válidos.';
    }

    if (actividad.resultado === 'omitida') {
      if (
        minutos !== 0 ||
        !actividad.motivo_omision.trim() ||
        actividad.adaptacion_metodologica.trim()
      ) {
        return (
          'Una actividad omitida requiere cero minutos, ' +
          'un motivo y ninguna adaptación metodológica.'
        );
      }
    } else if (
      actividad.resultado === 'realizada' ||
      actividad.resultado === 'modificada'
    ) {
      if (minutos < 1 || !actividad.descripcion.trim()) {
        return (
          'Cada actividad ejecutada requiere minutos positivos ' +
          'y una descripción.'
        );
      }

      if (actividad.motivo_omision.trim()) {
        return 'Las actividades ejecutadas no admiten motivo de omisión.';
      }

      const adaptada = Boolean(
        actividad.adaptacion_metodologica.trim()
      );

      if (
        (actividad.resultado === 'modificada') !== adaptada
      ) {
        return (
          'Las actividades modificadas requieren describir la ' +
          'adaptación; las realizadas no deben tener adaptación.'
        );
      }
    } else {
      return 'El resultado de una actividad no es válido.';
    }
  }

  return null;
}

export function RegistroEjecucionSesion({
  sesion,
  onGuardado,
  onCancelar,
}) {
  const [planId, establecerPlanId] = useState('');
  const [inicio, establecerInicio] = useState('');
  const [fin, establecerFin] = useState('');

  const [actividades, establecerActividades] = useState([]);
  const [observaciones, establecerObservaciones] = useState('');
  const [
    incidenciasPedagogicas,
    establecerIncidenciasPedagogicas,
  ] = useState('');

  const [cargando, establecerCargando] = useState(true);
  const [enviando, establecerEnviando] = useState(false);

  const [error, establecerError] = useState(null);
  const [mensaje, establecerMensaje] = useState('');
  const [finalizada, establecerFinalizada] = useState(false);

  const [requiereActualizar, establecerRequiereActualizar] =
    useState(false);

  const envioActivo = useRef(false);
  const intento = useRef(null);

  const planes = sesion.planes || [];

  const plan = planes.find(
    (elemento) => String(elemento.id) === planId
  );

  useEffect(() => {
    let vigente = true;

    establecerPlanId('');
    establecerInicio('');
    establecerFin('');
    establecerActividades([]);
    establecerObservaciones('');
    establecerIncidenciasPedagogicas('');
    establecerCargando(true);
    establecerError(null);
    establecerMensaje('');
    establecerFinalizada(false);
    establecerRequiereActualizar(false);

    intento.current = null;

    async function consultarEjecucion() {
      try {
        const respuesta = await solicitar(
          `/sesiones/${sesion.id}/ejecucion/`
        );

        if (!vigente) return;

        if (respuesta.version !== sesion.version) {
          establecerRequiereActualizar(true);
          establecerMensaje(
            'La versión consultada no coincide con la sesión. ' +
            'Actualiza el detalle.'
          );
          return;
        }

        const ejecucion = respuesta.ejecucion;

        establecerFinalizada(Boolean(ejecucion.finalizada_en));

        const planExistente = planes.find(
          (elemento) => elemento.id === ejecucion.plan?.id
        );

        if (!planExistente) {
          establecerRequiereActualizar(true);
          establecerMensaje(
            'El plan de la ejecución no está disponible ' +
            'en el detalle actual de la sesión.'
          );
          return;
        }

        establecerPlanId(String(planExistente.id));
        establecerInicio(fechaLocalBogota(ejecucion.inicio));
        establecerFin(fechaLocalBogota(ejecucion.fin));

        establecerActividades(
          (planExistente.tareas || []).map((tarea) => {
            const registrada = (ejecucion.actividades || [])
              .find((item) => item.tarea === tarea.id);

            return registrada
              ? {
                  tarea: tarea.id,
                  resultado: registrada.resultado,
                  minutos: String(registrada.minutos),
                  descripcion: registrada.descripcion || '',
                  adaptacion_metodologica:
                    registrada.adaptacion_metodologica || '',
                  motivo_omision: registrada.motivo_omision || '',
                }
              : actividadInicial(tarea);
          })
        );

        establecerObservaciones(ejecucion.observaciones || '');
        establecerIncidenciasPedagogicas(
          ejecucion.incidencias_pedagogicas || ''
        );
      } catch (fallo) {
        if (!vigente) return;

        if (fallo.estado !== 404) {
          establecerError(fallo);
          establecerRequiereActualizar(true);
        }
      } finally {
        if (vigente) establecerCargando(false);
      }
    }

    consultarEjecucion();

    return () => {
      vigente = false;
    };
  }, [sesion.id, sesion.version]);

  function cambiarPlan(valor) {
    if (enviando || requiereActualizar) return;

    const seleccionado = planes.find(
      (elemento) => String(elemento.id) === valor
    );

    establecerPlanId(valor);
    establecerActividades(actividadesIniciales(seleccionado));
    establecerError(null);
    establecerMensaje('');
    intento.current = null;
  }

  function cambiarActividad(indice, campo, valor) {
    if (enviando || requiereActualizar) return;

    establecerActividades((anteriores) =>
      anteriores.map((actividad, posicion) => {
        if (posicion !== indice) return actividad;

        const actualizada = {
          ...actividad,
          [campo]: valor,
        };

        if (campo === 'resultado') {
          if (valor === 'omitida') {
            actualizada.minutos = '0';
            actualizada.descripcion = '';
            actualizada.adaptacion_metodologica = '';
          } else {
            actualizada.motivo_omision = '';

            if (Number(actualizada.minutos) === 0) {
              actualizada.minutos = '1';
            }

            if (valor === 'realizada') {
              actualizada.adaptacion_metodologica = '';
            }
          }
        }

        return actualizada;
      })
    );

    intento.current = null;
    establecerError(null);
    establecerMensaje('');
  }

  const editable =
    !cargando &&
    !enviando &&
    !requiereActualizar &&
    !finalizada &&
    sesion.estado === 'planificada' &&
    sesion.estado_ejecucion !==
      'registrada_pendiente_validacion';

  const inicioISO = fechaISO(inicio);
  const finISO = fechaISO(fin);

  const inicioFecha = inicioISO ? new Date(inicioISO) : null;
  const finFecha = finISO ? new Date(finISO) : null;

  const duracion =
    inicioFecha && finFecha
      ? (finFecha - inicioFecha) / 60000
      : 0;

  const distribuidos = actividades.reduce(
    (total, actividad) =>
      total + (Number(actividad.minutos) || 0),
    0
  );

  function validarFormulario() {
    if (!plan) {
      return 'Selecciona una revisión de planificación.';
    }

    if (!inicioISO || !finISO) {
      return 'Introduce fechas y horas reales válidas.';
    }

    if (inicio.slice(0, 10) !== sesion.fecha) {
      return (
        'El inicio de la ejecución debe corresponder ' +
        'a la fecha de la sesión.'
      );
    }

    if (
      duracion <= 0 ||
      duracion > 1440 ||
      finFecha.getTime() > Date.now()
    ) {
      return (
        'El horario real debe estar terminado, ser posterior ' +
        'al inicio y no superar 24 horas.'
      );
    }

    const errorActividades = validarActividades(
      plan,
      actividades
    );

    if (errorActividades) return errorActividades;

    if (distribuidos > duracion) {
      return (
        'Los minutos de las actividades superan ' +
        'la duración real del entrenamiento.'
      );
    }

    if (
      observaciones.length > 8000 ||
      incidenciasPedagogicas.length > 8000
    ) {
      return 'Las observaciones superan la longitud permitida.';
    }

    return null;
  }

  async function guardarEjecucion(evento) {
    evento.preventDefault();

    if (!editable || envioActivo.current) return;

    const validacion = validarFormulario();

    if (validacion) {
      establecerError(new Error(validacion));
      return;
    }

    const contenido = {
      version: sesion.version,
      plan: Number(planId),
      inicio: inicioISO,
      fin: finISO,
      actividades: actividades.map((actividad) => ({
        tarea: actividad.tarea,
        resultado: actividad.resultado,
        minutos: Number(actividad.minutos),
        descripcion: actividad.descripcion.trim(),
        adaptacion_metodologica:
          actividad.adaptacion_metodologica.trim(),
        motivo_omision: actividad.motivo_omision.trim(),
      })),
      observaciones: observaciones.trim(),
      incidencias_pedagogicas:
        incidenciasPedagogicas.trim(),
    };

    const firma = JSON.stringify(contenido);

    if (!intento.current) {
      intento.current = {
        clave: crypto.randomUUID(),
        firma,
      };
    }

    if (intento.current.firma !== firma) {
      establecerError(
        new Error('Los datos cambiaron. Actualiza la ejecución.')
      );
      return;
    }

    envioActivo.current = true;
    establecerEnviando(true);
    establecerError(null);
    establecerMensaje('');

    try {
      const resultado = await guardar(
        `/sesiones/${sesion.id}/ejecucion/`,
        {
          clave: intento.current.clave,
          ...contenido,
        }
      );

      establecerRequiereActualizar(true);

      if (
        !resultado?.sesion ||
        resultado.sesion.id !== sesion.id ||
        resultado.sesion.version !== sesion.version + 1
      ) {
        establecerMensaje(
          'La respuesta no permitió verificar la nueva versión. ' +
          'Actualiza el detalle antes de continuar.'
        );
        return;
      }

      establecerMensaje(
        'Ejecución guardada como borrador. ' +
        'Todavía no está finalizada.'
      );

      onGuardado?.(resultado);
    } catch (fallo) {
      establecerRequiereActualizar(true);
      establecerError(fallo);

      establecerMensaje(
        fallo.estado === 0
          ? 'No llegó una respuesta confirmada. ' +
            'La operación podría haberse guardado. ' +
            'Consulta la sesión antes de reintentar.'
          : 'No se confirmó el guardado. ' +
            'Actualiza el detalle y verifica los permisos.'
      );
    } finally {
      envioActivo.current = false;
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h3>Registro de ejecución real</h3>

      <p>
        Documenta lo ocurrido durante el entrenamiento.
        Guardar este formulario no finaliza la ejecución,
        no cierra la asistencia y no valida institucionalmente
        la sesión como realizada.
      </p>

      {cargando && (
        <p role="status">
          Consultando la ejecución registrada…
        </p>
      )}

      <ErrorGestion error={error} />

      {finalizada && (
        <p role="alert">
          Esta ejecución ya está finalizada y no admite
          modificaciones ordinarias.
        </p>
      )}

      {requiereActualizar && (
        <p role="status">
          Actualiza el detalle de la sesión antes de realizar
          otra operación.
        </p>
      )}

      {mensaje && <p role="status">{mensaje}</p>}

      {!cargando && (
        <form onSubmit={guardarEjecucion}>
          <div className="rejilla-formulario">
            <label className="campo-gestion">
              Revisión del plan
              <select
                aria-label="Revisión del plan"
                value={planId}
                disabled={!editable}
                onChange={(evento) =>
                  cambiarPlan(evento.target.value)
                }
                required
              >
                <option value="">Seleccionar…</option>
                {planes.map((elemento) => (
                  <option
                    key={elemento.id}
                    value={elemento.id}
                  >
                    Revisión {elemento.numero} — {elemento.objetivo}
                  </option>
                ))}
              </select>
            </label>

            <label className="campo-gestion">
              Inicio real
              <input
                aria-label="Inicio real"
                type="datetime-local"
                value={inicio}
                disabled={!editable}
                onChange={(evento) => {
                  establecerInicio(evento.target.value);
                  intento.current = null;
                }}
                required
              />
            </label>

            <label className="campo-gestion">
              Finalización real
              <input
                aria-label="Finalización real"
                type="datetime-local"
                value={fin}
                disabled={!editable}
                onChange={(evento) => {
                  establecerFin(evento.target.value);
                  intento.current = null;
                }}
                required
              />
            </label>
          </div>

          {plan && (
            <>
              <h4>Actividades ejecutadas</h4>

              {plan.tareas.map((tarea, indice) => {
                const actividad = actividades[indice];

                if (!actividad) return null;

                return (
                  <fieldset
                    key={tarea.id}
                    disabled={!editable}
                  >
                    <legend>
                      {FASES[tarea.fase] || tarea.fase}
                      {' — '}
                      Actividad {tarea.orden}
                    </legend>

                    <p>
                      <strong>Planificado:</strong>{' '}
                      {tarea.instrucciones}
                    </p>

                    <p>
                      Tiempo previsto: {tarea.minutos} minutos
                    </p>

                    <label className="campo-gestion">
                      Resultado de actividad {tarea.orden}
                      <select
                        value={actividad.resultado}
                        onChange={(evento) =>
                          cambiarActividad(
                            indice,
                            'resultado',
                            evento.target.value
                          )
                        }
                      >
                        {RESULTADOS.map(([valor, texto]) => (
                          <option key={valor} value={valor}>
                            {texto}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="campo-gestion">
                      Minutos reales de actividad {tarea.orden}
                      <input
                        type="number"
                        min="0"
                        max="32767"
                        step="1"
                        value={actividad.minutos}
                        onChange={(evento) =>
                          cambiarActividad(
                            indice,
                            'minutos',
                            evento.target.value
                          )
                        }
                      />
                    </label>

                    {actividad.resultado !== 'omitida' && (
                      <label className="campo-gestion">
                        Descripción ejecutada de actividad {tarea.orden}
                        <textarea
                          maxLength={8000}
                          value={actividad.descripcion}
                          onChange={(evento) =>
                            cambiarActividad(
                              indice,
                              'descripcion',
                              evento.target.value
                            )
                          }
                        />
                      </label>
                    )}

                    {actividad.resultado === 'modificada' && (
                      <label className="campo-gestion">
                        Adaptación metodológica de actividad {tarea.orden}
                        <textarea
                          maxLength={8000}
                          value={
                            actividad.adaptacion_metodologica
                          }
                          onChange={(evento) =>
                            cambiarActividad(
                              indice,
                              'adaptacion_metodologica',
                              evento.target.value
                            )
                          }
                        />
                      </label>
                    )}

                    {actividad.resultado === 'omitida' && (
                      <label className="campo-gestion">
                        Motivo de omisión de actividad {tarea.orden}
                        <textarea
                          maxLength={1000}
                          value={actividad.motivo_omision}
                          onChange={(evento) =>
                            cambiarActividad(
                              indice,
                              'motivo_omision',
                              evento.target.value
                            )
                          }
                        />
                      </label>
                    )}
                  </fieldset>
                );
              })}

              <dl>
                <dt>Duración real</dt>
                <dd>{duracion} minutos</dd>

                <dt>Minutos distribuidos</dt>
                <dd>{distribuidos} minutos</dd>

                <dt>Minutos sin distribuir</dt>
                <dd>{duracion - distribuidos} minutos</dd>
              </dl>
            </>
          )}

          <label className="campo-gestion">
            Observaciones del entrenamiento
            <textarea
              maxLength={8000}
              value={observaciones}
              disabled={!editable}
              onChange={(evento) => {
                establecerObservaciones(evento.target.value);
                intento.current = null;
              }}
            />
          </label>

          <label className="campo-gestion">
            Incidencias pedagógicas
            <textarea
              maxLength={8000}
              value={incidenciasPedagogicas}
              disabled={!editable}
              onChange={(evento) => {
                establecerIncidenciasPedagogicas(
                  evento.target.value
                );
                intento.current = null;
              }}
            />
          </label>

          <div className="acciones">
            <button
              type="submit"
              disabled={!editable || !plan}
            >
              {enviando
                ? 'Guardando ejecución…'
                : 'Guardar ejecución como borrador'}
            </button>

            <button
              type="button"
              className="boton-secundario"
              disabled={enviando}
              onClick={onCancelar}
            >
              Volver al detalle
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
