
import { useEffect, useRef, useState } from 'react';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const ESTADOS = [
  ['asistio', 'Asistió'],
  ['no_asistio', 'No asistió'],
  ['tarde', 'Llegó tarde'],
  ['excusa', 'Excusa'],
  ['retiro', 'Retiro'],
];

const ESTADOS_VALIDOS = ESTADOS.map(([valor]) => valor);

function fechaActualBogota() {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

function nombreParticipante(persona) {
  return [persona.nombres, persona.apellidos]
    .filter(Boolean)
    .join(' ') || `Deportista ${persona.deportista}`;
}

function resumir(participantes) {
  return ESTADOS.map(([valor, etiqueta]) => ({
    valor,
    etiqueta,
    total: participantes.filter(
      (persona) => persona.estado === valor
    ).length,
  }));
}

export function CierreAsistenciaSesion({
  sesion,
  onCerrado,
  onCancelar,
}) {
  const [padron, establecerPadron] = useState(null);
  const [cargando, establecerCargando] = useState(true);

  const [confirmado, establecerConfirmado] = useState(false);
  const [enviando, establecerEnviando] = useState(false);

  const [error, establecerError] = useState(null);
  const [mensaje, establecerMensaje] = useState('');

  const [requiereActualizar, establecerRequiereActualizar] =
    useState(false);

  const envioActivo = useRef(false);

  useEffect(() => {
    let vigente = true;

    establecerPadron(null);
    establecerCargando(true);
    establecerConfirmado(false);
    establecerError(null);
    establecerMensaje('');
    establecerRequiereActualizar(false);

    async function consultarPadron() {
      try {
        const respuesta = await solicitar(
          `/sesiones/${sesion.id}/asistencia/`
        );

        if (!vigente) return;

        establecerPadron(respuesta);
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

    consultarPadron();

    return () => {
      vigente = false;
    };
  }, [sesion.id, sesion.version]);

  const participantes = padron?.participantes || [];

  const sinRegistrar = participantes.filter(
    (persona) =>
      !ESTADOS_VALIDOS.includes(persona.estado)
  ).length;

  const versionCorrecta =
    padron?.version === sesion.version;

  const fechaValida =
    Boolean(sesion.fecha) &&
    sesion.fecha <= fechaActualBogota();

  const puedeCerrar =
    !cargando &&
    !enviando &&
    !requiereActualizar &&
    Boolean(padron) &&
    !padron.cerrada &&
    !padron.requiere_preparacion &&
    !sesion.asistencia_confirmada &&
    sesion.estado === 'planificada' &&
    versionCorrecta &&
    fechaValida &&
    participantes.length > 0 &&
    sinRegistrar === 0;

  async function cerrarAsistencia(evento) {
    evento.preventDefault();

    if (
      !puedeCerrar ||
      !confirmado ||
      envioActivo.current
    ) {
      return;
    }

    envioActivo.current = true;

    establecerEnviando(true);
    establecerConfirmado(false);
    establecerError(null);
    establecerMensaje('');

    const datos = {
      version: padron.version,
      clave: crypto.randomUUID(),
    };

    try {
      const resultado = await guardar(
        `/sesiones/${sesion.id}/asistencia/cerrar/`,
        datos
      );

      establecerRequiereActualizar(true);

      if (
        !resultado?.sesion ||
        !resultado?.asistencia?.cerrada
      ) {
        establecerError(
          new Error(
            'El servidor no devolvió una confirmación ' +
            'completa del cierre.'
          )
        );

        establecerMensaje(
          'Consulta nuevamente la sesión para verificar ' +
          'si la asistencia quedó cerrada.'
        );

        return;
      }

      establecerMensaje(
        'La asistencia quedó cerrada correctamente.'
      );

      onCerrado?.(resultado);
    } catch (fallo) {
      establecerError(fallo);
      establecerRequiereActualizar(true);

      if (fallo.estado === 0) {
        establecerMensaje(
          'No llegó una respuesta confirmada. ' +
          'El cierre podría haberse realizado. ' +
          'Consulta la sesión antes de realizar otra operación.'
        );
      } else {
        establecerMensaje(
          'No se confirmó el cierre. ' +
          'Actualiza la sesión y comprueba su estado.'
        );
      }
    } finally {
      envioActivo.current = false;
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h3>Cierre definitivo de asistencia</h3>

      <p className="aviso">
        Esta operación cierra la asistencia de la sesión.
        Después del cierre, el profesor no podrá modificar
        los estados mediante el registro ordinario.
      </p>

      {cargando && (
        <p role="status">
          Verificando la asistencia antes del cierre…
        </p>
      )}

      <ErrorGestion error={error} />

      {padron && (
        <>
          <h4>Comprobaciones previas</h4>

          <dl>
            <dt>Versión de sesión</dt>
            <dd>{sesion.version}</dd>

            <dt>Versión del padrón</dt>
            <dd>{padron.version}</dd>

            <dt>Participantes</dt>
            <dd>{participantes.length}</dd>

            <dt>Sin registrar</dt>
            <dd>{sinRegistrar}</dd>

            <dt>Asistencia cerrada</dt>
            <dd>{padron.cerrada ? 'Sí' : 'No'}</dd>
          </dl>

          {padron.cerrada && (
            <p role="alert">
              Esta asistencia ya está cerrada.
            </p>
          )}

          {padron.requiere_preparacion && (
            <p role="alert">
              El padrón requiere preparación antes
              de cerrar la asistencia.
            </p>
          )}

          {!versionCorrecta && (
            <p role="alert">
              La versión del padrón no coincide
              con la sesión. Actualiza el detalle.
            </p>
          )}

          {!fechaValida && (
            <p role="alert">
              No se puede cerrar la asistencia
              de una sesión futura.
            </p>
          )}

          {participantes.length === 0 && (
            <p role="alert">
              No hay participantes disponibles
              para confirmar el cierre.
            </p>
          )}

          {sinRegistrar > 0 && (
            <p role="alert">
              Hay {sinRegistrar} participantes
              sin un estado válido registrado.
              Completa la asistencia antes del cierre.
            </p>
          )}

          <h4>Resumen de asistencia</h4>

          <div className="tabla-contenedor">
            <table>
              <thead>
                <tr>
                  <th>Estado</th>
                  <th>Total</th>
                </tr>
              </thead>

              <tbody>
                {resumir(participantes).map((fila) => (
                  <tr key={fila.valor}>
                    <td>{fila.etiqueta}</td>
                    <td>{fila.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h4>Participantes registrados</h4>

          <div className="tabla-contenedor">
            <table>
              <thead>
                <tr>
                  <th>Participante</th>
                  <th>Estado</th>
                </tr>
              </thead>

              <tbody>
                {participantes.map((persona) => (
                  <tr key={persona.inscripcion}>
                    <td>{nombreParticipante(persona)}</td>
                    <td>
                      {ESTADOS.find(
                        ([valor]) =>
                          valor === persona.estado
                      )?.[1] || 'Sin registrar'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <form onSubmit={cerrarAsistencia}>
            <label>
              <input
                type="checkbox"
                checked={confirmado}
                disabled={!puedeCerrar}
                onChange={(evento) =>
                  establecerConfirmado(
                    evento.target.checked
                  )
                }
              />

              {' '}
              Confirmo que revisé todos los estados
              y comprendo que el cierre de asistencia
              es definitivo para el profesor.
            </label>

            {requiereActualizar && (
              <p role="status">
                Actualiza el detalle de la sesión
                antes de realizar otra operación.
              </p>
            )}

            {mensaje && (
              <p role="status">{mensaje}</p>
            )}

            <div className="acciones">
              <button
                type="submit"
                disabled={
                  !puedeCerrar || !confirmado
                }
              >
                {enviando
                  ? 'Cerrando asistencia…'
                  : 'Confirmar cierre definitivo'}
              </button>

              <button
                type="button"
                className="boton-secundario"
                disabled={enviando}
                onClick={onCancelar}
              >
                Cancelar cierre
              </button>
            </div>
          </form>
        </>
      )}

      {!padron && !cargando && (
        <button
          type="button"
          className="boton-secundario"
          onClick={onCancelar}
        >
          Volver al detalle
        </button>
      )}
    </section>
  );
}
