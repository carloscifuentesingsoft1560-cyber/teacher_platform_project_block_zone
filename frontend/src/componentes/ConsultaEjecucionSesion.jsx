
import { useEffect, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { ErrorGestion } from './Gestion.jsx';

const ESTADOS = {
  asistio: 'Asistió',
  no_asistio: 'No asistió',
  tarde: 'Llegó tarde',
  excusa: 'Excusa',
  retiro: 'Retiro',
};

function nombreParticipante(persona) {
  return [persona.nombres, persona.apellidos]
    .filter(Boolean)
    .join(' ') || `Deportista ${persona.deportista}`;
}

function estadoAsistencia(estado) {
  return ESTADOS[estado] || 'Sin registrar';
}

export function ConsultaEjecucionSesion({ sesion }) {
  const [datos, establecerDatos] = useState(null);
  const [ejecucion, establecerEjecucion] = useState(null);
  const [cargando, establecerCargando] = useState(true);
  const [error, establecerError] = useState(null);
  const [revision, establecerRevision] = useState(0);

  useEffect(() => {
    let vigente = true;

    establecerCargando(true);
    establecerError(null);
    establecerDatos(null);
    establecerEjecucion(null);

    async function consultar() {
      try {
        const asistencia = await solicitar(
          `/sesiones/${sesion.id}/asistencia/`
        );

        if (!vigente) return;

        establecerDatos(asistencia);

        // Sin registro de ejecución, no existe detalle
        // que consultar. Evitamos un GET innecesario.
        if (sesion.estado_ejecucion === 'sin_registro') {
          return;
        }

        try {
          const respuesta = await solicitar(
            `/sesiones/${sesion.id}/ejecucion/`
          );

          if (vigente) {
            establecerEjecucion(respuesta.ejecucion);
          }
        } catch (fallo) {
          if (vigente) {
            establecerError(fallo);
          }
        }
      } catch (fallo) {
        if (vigente) {
          establecerError(fallo);
        }
      } finally {
        if (vigente) {
          establecerCargando(false);
        }
      }
    }

    consultar();

    return () => {
      vigente = false;
    };
  }, [sesion.id, sesion.estado_ejecucion, revision]);

  return (
    <section className="formulario-gestion">
      <h3>Ejecución y asistencia</h3>

      <p>
        Consulta de registros institucionales.
        En esta primera entrega no se modifica
        ninguna asistencia ni ejecución.
      </p>

      <button
        type="button"
        className="boton-secundario"
        disabled={cargando}
        onClick={() =>
          establecerRevision((actual) => actual + 1)
        }
      >
        Actualizar ejecución y asistencia
      </button>

      {cargando && (
        <p role="status">
          Consultando ejecución y participantes…
        </p>
      )}

      <ErrorGestion error={error} />

      {!cargando && datos && (
        <>
          <h4>Estado de la asistencia</h4>

          <dl>
            <dt>Asistencia cerrada</dt>
            <dd>{datos.cerrada ? 'Sí' : 'No'}</dd>

            <dt>Versión consultada</dt>
            <dd>{datos.version}</dd>

            <dt>Participantes</dt>
            <dd>{datos.participantes?.length || 0}</dd>

            <dt>Preparación de padrón requerida</dt>
            <dd>
              {datos.requiere_preparacion ? 'Sí' : 'No'}
            </dd>
          </dl>

          {datos.requiere_preparacion && (
            <p role="alert">
              El padrón de la sesión requiere preparación
              antes de guardar o cerrar la asistencia.
            </p>
          )}

          <h4>Asistencia por participante</h4>

          {!datos.participantes?.length ? (
            <p>No hay participantes en el padrón consultado.</p>
          ) : (
            <div className="tabla-contenedor">
              <table>
                <thead>
                  <tr>
                    <th>Participante</th>
                    <th>Estado registrado</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.participantes.map((persona) => (
                    <tr key={persona.inscripcion}>
                      <td>{nombreParticipante(persona)}</td>
                      <td>
                        {estadoAsistencia(persona.estado)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {!cargando && !error && (
        <>
          <h4>Ejecución de la sesión</h4>

          {!ejecucion ? (
            <p>
              No hay un registro de ejecución disponible
              para esta sesión.
            </p>
          ) : (
            <>
              <dl>
                <dt>Plan ejecutado</dt>
                <dd>
                  Revisión {ejecucion.plan?.numero ?? '—'}
                </dd>

                <dt>Inicio real</dt>
                <dd>{ejecucion.inicio}</dd>

                <dt>Fin real</dt>
                <dd>{ejecucion.fin}</dd>

                <dt>Duración real</dt>
                <dd>
                  {ejecucion.duracion_real_minutos}
                  {' minutos'}
                </dd>

                <dt>Tiempo no distribuido</dt>
                <dd>
                  {ejecucion.tiempo_no_distribuido_minutos}
                  {' minutos'}
                </dd>

                <dt>Finalizada</dt>
                <dd>
                  {ejecucion.finalizada_en ? 'Sí' : 'No'}
                </dd>
              </dl>

              <p>
                <strong>Observaciones:</strong>{' '}
                {ejecucion.observaciones || 'Sin observaciones'}
              </p>

              <p>
                <strong>Incidencias pedagógicas:</strong>{' '}
                {ejecucion.incidencias_pedagogicas ||
                  'Sin incidencias registradas'}
              </p>

              <h4>Actividades ejecutadas</h4>

              {!ejecucion.actividades?.length ? (
                <p>No hay actividades registradas.</p>
              ) : (
                <ul>
                  {ejecucion.actividades.map((actividad) => (
                    <li key={actividad.tarea}>
                      <strong>
                        Tarea {actividad.tarea}:
                      </strong>{' '}
                      {actividad.resultado} ·{' '}
                      {actividad.minutos} minutos.
                      {' '}
                      {actividad.descripcion}
                    </li>
                  ))}
                </ul>
              )}

              {ejecucion.finalizada_en && (
                <p className="aviso">
                  La ejecución está finalizada.
                  Esto no implica que la sesión haya sido
                  validada institucionalmente como realizada.
                </p>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
