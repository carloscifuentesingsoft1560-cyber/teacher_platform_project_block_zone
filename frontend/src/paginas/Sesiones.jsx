
import { useEffect, useRef, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { guardar, fechaBogota } from '../api/gestion.js';
import {
  Campo,
  ErrorGestion,
  Paginacion,
} from '../componentes/Gestion.jsx';

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
  const [mensaje, establecerMensaje] = useState('');

  const [mostrarFormulario, establecerMostrarFormulario] =
    useState(false);

  const [formulario, establecerFormulario] =
    useState(formularioInicial);

  const [enviando, establecerEnviando] = useState(false);

  const [detalle, establecerDetalle] = useState(null);
  const [cargandoDetalle, establecerCargandoDetalle] =
    useState(false);

  const [errorDetalle, establecerErrorDetalle] = useState(null);

  // Conserva el identificador de una creación incierta.
  // No se genera una segunda clave para repetir la misma petición.
  const intentoCreacion = useRef(null);

  useEffect(() => {
    let vigente = true;

    async function cargarGrupos() {
      establecerCargandoGrupos(true);

      try {
        const acumulados = [];
        let siguiente = '/sesiones/grupos/';

        for (let i = 0; siguiente && i < 100; i += 1) {
          const respuesta = await solicitar(siguiente);

          acumulados.push(...(respuesta.results || []));

          if (respuesta.next) {
            const url = new URL(
              respuesta.next,
              window.location.origin
            );

            siguiente =
              url.pathname.replace(/^\/api/, '') +
              url.search;
          } else {
            siguiente = null;
          }
        }

        if (siguiente) {
          throw new Error(
            'Hay demasiados grupos para este selector.'
          );
        }

        if (vigente) establecerGrupos(acumulados);
      } catch (fallo) {
        if (vigente) establecerError(fallo);
      } finally {
        if (vigente) establecerCargandoGrupos(false);
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
        if (vigente) establecerCargando(false);
      }
    }

    cargarSesiones();

    return () => {
      vigente = false;
    };
  }, [pagina, situacion, revision]);

  function cambiarCampo(campo, valor) {
    establecerFormulario((actual) => ({
      ...actual,
      [campo]: valor,
    }));

    intentoCreacion.current = null;
    establecerMensaje('');
  }

  function actualizarListado() {
    establecerRevision((actual) => actual + 1);
  }

  function cambiarSituacion(valor) {
    establecerSituacion(valor);
    establecerPagina(1);
    establecerDetalle(null);
  }

  function alternarFormulario() {
    establecerMostrarFormulario((actual) => !actual);
    establecerError(null);
    establecerMensaje('');
    intentoCreacion.current = null;
  }

  async function consultarDetalle(id) {
    establecerDetalle(null);
    establecerErrorDetalle(null);
    establecerCargandoDetalle(true);

    try {
      const respuesta = await solicitar(`/sesiones/${id}/`);
      establecerDetalle(respuesta);
    } catch (fallo) {
      establecerErrorDetalle(fallo);
    } finally {
      establecerCargandoDetalle(false);
    }
  }

  async function crearSesion(evento) {
    evento.preventDefault();

    if (enviando) return;

    establecerError(null);
    establecerMensaje('');

    const nuevoContenido = {
      grupo: Number(formulario.grupo),
      fecha: formulario.fecha,
      hora_inicio: formulario.hora_inicio,
      hora_fin: formulario.hora_fin,
    };

    if (!nuevoContenido.grupo) {
      establecerError(new Error('Selecciona un grupo.'));
      return;
    }

    if (
      nuevoContenido.hora_fin <= nuevoContenido.hora_inicio
    ) {
      establecerError(
        new Error(
          'La hora de finalización debe ser posterior al inicio.'
        )
      );
      return;
    }

    const firma = JSON.stringify(nuevoContenido);

    if (!intentoCreacion.current) {
      intentoCreacion.current = {
        clave: crypto.randomUUID(),
        firma,
      };
    }

    // El mismo intento conserva la misma clave UUID.
    if (intentoCreacion.current.firma !== firma) {
      establecerError(
        new Error(
          'El formulario cambió. Actualiza antes de crear.'
        )
      );
      return;
    }

    const datos = {
      clave: intentoCreacion.current.clave,
      ...nuevoContenido,
    };

    establecerEnviando(true);

    try {
      await guardar('/sesiones/', datos);

      intentoCreacion.current = null;
      establecerMensaje('Sesión creada correctamente.');

      establecerMostrarFormulario(false);
      establecerFormulario(formularioInicial());
      establecerPagina(1);
      actualizarListado();
    } catch (fallo) {
      establecerError(fallo);

      if (fallo.estado === 0) {
        establecerMensaje(
          'La respuesta del servidor no llegó. ' +
          'Comprueba el listado antes de repetir la operación. ' +
          'El mismo formulario conservará su clave de solicitud.'
        );
      } else if (
        fallo.estado === 401 ||
        fallo.estado === 403 ||
        fallo.estado === 409
      ) {
        intentoCreacion.current = null;
        establecerMensaje(
          'Actualiza los datos y verifica tus permisos ' +
          'antes de volver a intentar.'
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
        Consulta las sesiones de entrenamiento, revisa su
        planificación y crea nuevas sesiones dentro de los
        grupos para los que tienes autorización.
      </p>

      <p className="aviso">
        Un informe de ejecución cerrado no significa que
        la sesión esté validada institucionalmente como
        realizada.
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
            Selecciona el grupo y el horario. El servidor
            verificará los permisos, las asignaciones y
            las restricciones de programación.
          </p>

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
              <th>Situación</th>
              <th>Consulta</th>
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

                <td>{describirEstado(sesion)}</td>

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

          <h3>Historial de planificación</h3>

          {!detalle.planes?.length && (
            <p>
              Todavía no existe una planificación
              registrada para esta sesión.
            </p>
          )}

          {detalle.planes?.map((plan) => (
            <article
              key={plan.id}
              className="formulario-gestion"
            >
              <h3>Plan número {plan.numero}</h3>

              <p>
                <strong>Objetivo:</strong>{' '}
                {plan.objetivo}
              </p>

              {plan.malla_version && (
                <p>
                  Versión curricular: {plan.malla_version}
                </p>
              )}

              <h4>Actividades planificadas</h4>

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

          <button
            type="button"
            className="boton-secundario"
            onClick={() => establecerDetalle(null)}
          >
            Cerrar detalle
          </button>
        </section>
      )}
    </section>
  );
}
