
import { useEffect, useRef, useState } from 'react';

import { solicitar } from '../api/cliente.js';
import {
  guardar,
  todas,
  fechaBogota,
} from '../api/gestion.js';

import {
  Campo,
  ErrorGestion,
  Paginacion,
} from '../componentes/Gestion.jsx';

import {
  PlanificacionSesion,
} from '../componentes/PlanificacionSesion.jsx';

const SITUACIONES = [
  ['', 'Todas las sesiones'],
  ['programadas', 'Programadas'],
  ['ejecutadas', 'Con ejecución finalizada'],
  ['pendientes', 'Pendientes de ejecución'],
  ['canceladas', 'Canceladas'],
  ['realizadas', 'Realizadas institucionalmente'],
];

function describirEstado(sesion) {
  if (sesion.estado === 'cancelada') {
    return 'Cancelada';
  }

  if (sesion.estado === 'realizada') {
    return 'Realizada institucionalmente';
  }

  if (
    sesion.estado_ejecucion ===
    'registrada_pendiente_validacion'
  ) {
    return 'Ejecución cerrada; validación pendiente';
  }

  if (sesion.estado_ejecucion === 'borrador') {
    return 'Ejecución en borrador';
  }

  return 'Programada';
}

function horaCorta(hora) {
  return hora ? String(hora).slice(0, 5) : '—';
}

function formularioInicial() {
  return {
    grupo: '',
    fecha: fechaBogota(),
    hora_inicio: '10:00',
    hora_fin: '12:00',
  };
}

export function Sesiones() {
  const [sesiones, establecerSesiones] = useState({
    results: [],
    count: 0,
    next: null,
  });

  const [grupos, establecerGrupos] = useState([]);

  const [situacion, establecerSituacion] = useState('');
  const [pagina, establecerPagina] = useState(1);
  const [revision, establecerRevision] = useState(0);

  const [cargando, establecerCargando] = useState(true);
  const [cargandoGrupos, establecerCargandoGrupos] =
    useState(true);

  const [error, establecerError] = useState(null);
  const [errorGrupos, establecerErrorGrupos] =
    useState(null);

  const [mensaje, establecerMensaje] = useState('');

  const [mostrarFormulario, establecerMostrarFormulario] =
    useState(false);

  const [formulario, establecerFormulario] =
    useState(formularioInicial);

  const [enviando, establecerEnviando] = useState(false);

  const [detalle, establecerDetalle] = useState(null);
  const [cargandoDetalle, establecerCargandoDetalle] =
    useState(false);

  const [errorDetalle, establecerErrorDetalle] =
    useState(null);

  const [planificando, establecerPlanificando] =
    useState(false);

  const intentoCreacion = useRef(null);
  const consultaDetalle = useRef(0);

  useEffect(() => {
    let vigente = true;

    async function cargarGrupos() {
      establecerCargandoGrupos(true);
      establecerErrorGrupos(null);

      try {
        const respuesta = await todas(
          '/sesiones/grupos/'
        );

        if (vigente) {
          establecerGrupos(respuesta);
        }
      } catch (fallo) {
        if (vigente) {
          establecerErrorGrupos(fallo);
          establecerGrupos([]);
        }
      } finally {
        if (vigente) {
          establecerCargandoGrupos(false);
        }
      }
    }

    cargarGrupos();

    return () => {
      vigente = false;
    };
  }, []);

  useEffect(() => {
    let vigente = true;

    async function cargarSesiones() {
      establecerCargando(true);
      establecerError(null);

      const parametros = new URLSearchParams({
        page: String(pagina),
      });

      if (situacion) {
        parametros.set('situacion', situacion);
      }

      try {
        const respuesta = await solicitar(
          '/sesiones/?' + parametros.toString()
        );

        if (vigente) {
          establecerSesiones(respuesta);
        }
      } catch (fallo) {
        if (vigente) {
          establecerError(fallo);

          establecerSesiones({
            results: [],
            count: 0,
            next: null,
          });
        }
      } finally {
        if (vigente) {
          establecerCargando(false);
        }
      }
    }

    cargarSesiones();

    return () => {
      vigente = false;
    };
  }, [pagina, situacion, revision]);

  function actualizarListado() {
    establecerRevision((actual) => actual + 1);
  }

  function cambiarSituacion(valor) {
    establecerSituacion(valor);
    establecerPagina(1);
    cerrarDetalle();
  }

  function cambiarCampo(campo, valor) {
    establecerFormulario((actual) => ({
      ...actual,
      [campo]: valor,
    }));

    intentoCreacion.current = null;
    establecerMensaje('');
  }

  function alternarFormulario() {
    establecerMostrarFormulario((actual) => !actual);
    establecerError(null);
    establecerMensaje('');
    intentoCreacion.current = null;
  }

  function cerrarDetalle() {
    consultaDetalle.current += 1;
    establecerDetalle(null);
    establecerPlanificando(false);
    establecerErrorDetalle(null);
    establecerCargandoDetalle(false);
  }

  async function consultarDetalle(id) {
    const consultaActual = ++consultaDetalle.current;

    establecerDetalle(null);
    establecerPlanificando(false);
    establecerErrorDetalle(null);
    establecerCargandoDetalle(true);

    try {
      const respuesta = await solicitar(
        `/sesiones/${id}/`
      );

      if (consultaActual === consultaDetalle.current) {
        establecerDetalle(respuesta);
      }
    } catch (fallo) {
      if (consultaActual === consultaDetalle.current) {
        establecerErrorDetalle(fallo);
      }
    } finally {
      if (consultaActual === consultaDetalle.current) {
        establecerCargandoDetalle(false);
      }
    }
  }

  function iniciarPlanificacion() {
    establecerPlanificando(true);
    establecerErrorDetalle(null);
  }

  function cerrarPlanificacion() {
    establecerPlanificando(false);
  }

  function planGuardado(sesionActualizada) {
    // Django devuelve la nueva versión y el historial.
    establecerDetalle(sesionActualizada);
    establecerPlanificando(false);
    establecerErrorDetalle(null);

    // Actualizar también la tabla.
    actualizarListado();

    establecerMensaje(
      'La nueva revisión de planificación quedó registrada.'
    );
  }

  async function crearSesion(evento) {
    evento.preventDefault();

    if (enviando) return;

    establecerError(null);
    establecerMensaje('');

    const contenido = {
      grupo: Number(formulario.grupo),
      fecha: formulario.fecha,
      hora_inicio: formulario.hora_inicio,
      hora_fin: formulario.hora_fin,
    };

    if (!contenido.grupo) {
      establecerError(
        new Error('Selecciona un grupo.')
      );
      return;
    }

    if (
      contenido.hora_fin <= contenido.hora_inicio
    ) {
      establecerError(
        new Error(
          'La hora final debe ser posterior a la hora inicial.'
        )
      );
      return;
    }

    const firma = JSON.stringify(contenido);

    if (!intentoCreacion.current) {
      intentoCreacion.current = {
        clave: crypto.randomUUID(),
        firma,
      };
    }

    if (intentoCreacion.current.firma !== firma) {
      establecerError(
        new Error(
          'Los datos cambiaron. Actualiza antes de crear.'
        )
      );
      return;
    }

    const datos = {
      clave: intentoCreacion.current.clave,
      ...contenido,
    };

    establecerEnviando(true);

    try {
      await guardar('/sesiones/', datos);

      intentoCreacion.current = null;

      establecerMensaje(
        'Sesión creada correctamente.'
      );

      establecerMostrarFormulario(false);
      establecerFormulario(formularioInicial());
      establecerPagina(1);
      actualizarListado();
    } catch (fallo) {
      establecerError(fallo);

      if (fallo.estado === 0) {
        establecerMensaje(
          'No llegó la respuesta del servidor. ' +
          'Comprueba el listado antes de repetir la operación.'
        );
      } else if (
        [400, 403, 409].includes(fallo.estado)
      ) {
        intentoCreacion.current = null;

        establecerMensaje(
          'Actualiza los datos y verifica los permisos antes de reintentar.'
        );
      }
    } finally {
      establecerEnviando(false);
    }
  }

  return (
    <section className="gestion">
      <h1>Mis sesiones</h1>

      <p>
        Consulta tus sesiones, crea nuevas sesiones y
        registra las revisiones de su planificación.
      </p>

      <p className="aviso">
        Una ejecución cerrada no significa que la
        sesión esté validada institucionalmente
        como realizada.
      </p>

      <div className="barra-gestion">
        <Campo
          etiqueta="Situación"
          nombre="situacion-sesiones"
          valor={situacion}
          cambiar={cambiarSituacion}
          opciones={SITUACIONES}
          requerido={false}
        />

        <div className="acciones">
          <button
            type="button"
            className="boton-secundario"
            onClick={actualizarListado}
            disabled={cargando}
          >
            Actualizar listado
          </button>

          <button
            type="button"
            onClick={alternarFormulario}
            disabled={enviando}
          >
            {mostrarFormulario
              ? 'Cerrar formulario'
              : 'Nueva sesión'}
          </button>
        </div>
      </div>

      {mostrarFormulario && (
        <form
          className="formulario-gestion"
          onSubmit={crearSesion}
        >
          <h2>Crear sesión de entrenamiento</h2>

          <p>
            Selecciona el grupo, la fecha y el horario.
            Django comprobará las asignaciones y permisos.
          </p>

          <ErrorGestion error={errorGrupos} />

          <div className="rejilla-formulario">
            <Campo
              etiqueta="Grupo"
              nombre="sesion-grupo"
              valor={formulario.grupo}
              cambiar={(valor) =>
                cambiarCampo('grupo', valor)
              }
              opciones={grupos.map((grupo) => [
                grupo.id,
                grupo.nombre,
              ])}
              disabled={cargandoGrupos || enviando}
            />

            <Campo
              etiqueta="Fecha"
              nombre="sesion-fecha"
              tipo="date"
              valor={formulario.fecha}
              cambiar={(valor) =>
                cambiarCampo('fecha', valor)
              }
              disabled={enviando}
            />

            <Campo
              etiqueta="Hora de inicio"
              nombre="sesion-inicio"
              tipo="time"
              valor={formulario.hora_inicio}
              cambiar={(valor) =>
                cambiarCampo('hora_inicio', valor)
              }
              disabled={enviando}
            />

            <Campo
              etiqueta="Hora de finalización"
              nombre="sesion-fin"
              tipo="time"
              valor={formulario.hora_fin}
              cambiar={(valor) =>
                cambiarCampo('hora_fin', valor)
              }
              disabled={enviando}
            />
          </div>

          {!cargandoGrupos && grupos.length === 0 && (
            <p>
              No hay grupos disponibles para crear sesiones.
            </p>
          )}

          <div className="acciones">
            <button
              type="submit"
              disabled={
                enviando ||
                cargandoGrupos ||
                !grupos.length
              }
            >
              {enviando
                ? 'Guardando…'
                : 'Crear sesión'}
            </button>

            <button
              type="button"
              className="boton-secundario"
              onClick={alternarFormulario}
              disabled={enviando}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      <ErrorGestion error={error} />

      {mensaje && <p role="status">{mensaje}</p>}

      {cargando && (
        <p role="status">Cargando sesiones…</p>
      )}

      {!cargando &&
        !error &&
        sesiones.count === 0 && (
          <p>
            No hay sesiones registradas para esta consulta.
          </p>
        )}

      <div className="tabla-contenedor">
        <table>
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Grupo</th>
              <th>Horario</th>
              <th>Estado</th>
              <th>Detalle</th>
            </tr>
          </thead>

          <tbody>
            {sesiones.results.map((sesion) => (
              <tr key={sesion.id}>
                <td>{sesion.fecha}</td>

                <td>{sesion.grupo}</td>

                <td>
                  {horaCorta(sesion.hora_inicio)}
                  {' – '}
                  {horaCorta(sesion.hora_fin)}
                </td>

                <td>
                  {describirEstado(sesion)}
                </td>

                <td>
                  <button
                    type="button"
                    className="boton-secundario"
                    onClick={() =>
                      consultarDetalle(sesion.id)
                    }
                  >
                    Ver detalle
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Paginacion
        pagina={pagina}
        cambiar={establecerPagina}
        siguiente={sesiones.next}
        total={sesiones.count}
      />

      {cargandoDetalle && (
        <p role="status">
          Consultando el detalle de la sesión…
        </p>
      )}

      <ErrorGestion error={errorDetalle} />

      {detalle && (
        <section className="detalle-grupo">
          <h2>Detalle de la sesión</h2>

          <dl>
            <dt>Fecha</dt>
            <dd>{detalle.fecha}</dd>

            <dt>Grupo</dt>
            <dd>{detalle.grupo}</dd>

            <dt>Profesor</dt>
            <dd>{detalle.profesor}</dd>

            <dt>Horario</dt>
            <dd>
              {horaCorta(detalle.hora_inicio)}
              {' – '}
              {horaCorta(detalle.hora_fin)}
            </dd>

            <dt>Estado</dt>
            <dd>{describirEstado(detalle)}</dd>

            <dt>Asistencia confirmada</dt>
            <dd>
              {detalle.asistencia_confirmada
                ? 'Sí'
                : 'No'}
            </dd>

            <dt>Versión de sesión</dt>
            <dd>{detalle.version}</dd>
          </dl>

          <div className="acciones">
            {!planificando &&
              detalle.estado === 'planificada' && (
                <button
                  type="button"
                  onClick={iniciarPlanificacion}
                >
                  Planificar sesión
                </button>
              )}

            <button
              type="button"
              className="boton-secundario"
              onClick={() =>
                consultarDetalle(detalle.id)
              }
            >
              Actualizar detalle
            </button>

            <button
              type="button"
              className="boton-secundario"
              onClick={cerrarDetalle}
            >
              Cerrar detalle
            </button>
          </div>

          {planificando && (
            <PlanificacionSesion
              key={`${detalle.id}-${detalle.version}`}
              sesion={detalle}
              onGuardado={planGuardado}
              onCancelar={cerrarPlanificacion}
            />
          )}

          <h3>Historial de planificación</h3>

          {!detalle.planes?.length && (
            <p>
              Esta sesión todavía no tiene planificación
              registrada.
            </p>
          )}

          {detalle.planes?.map((plan) => (
            <article
              key={plan.id}
              className="formulario-gestion"
            >
              <h4>
                Revisión número {plan.numero}
              </h4>

              <p>
                <strong>Objetivo:</strong>{' '}
                {plan.objetivo}
              </p>

              <p>
                <strong>Autor:</strong>{' '}
                {plan.autor}
              </p>

              <p>
                <strong>Fecha de registro:</strong>{' '}
                {plan.creado_en}
              </p>

              <h4>Actividades</h4>

              <ul>
                {plan.tareas?.map((tarea) => (
                  <li key={tarea.orden}>
                    <strong>{tarea.fase}</strong>
                    {' — '}
                    {tarea.minutos} minutos.
                    {' '}
                    {tarea.instrucciones}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
