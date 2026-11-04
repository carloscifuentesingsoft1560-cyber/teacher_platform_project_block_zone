
import { useEffect, useRef, useState } from 'react';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const ESTADOS_VALIDOS = [
  'asistio',
  'no_asistio',
  'tarde',
  'excusa',
  'retiro',
];

function fechaBogota() {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

export function FinalizacionEjecucionSesion({
  sesion,
  onFinalizado,
  onCancelar,
}) {
  const [ejecucion, establecerEjecucion] = useState(null);
  const [asistencia, establecerAsistencia] = useState(null);
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

    establecerEjecucion(null);
    establecerAsistencia(null);
    establecerCargando(true);
    establecerConfirmado(false);
    establecerError(null);
    establecerMensaje('');
    establecerRequiereActualizar(false);

    async function consultarRegistros() {
      try {
        const [respuestaEjecucion, respuestaAsistencia] =
          await Promise.all([
            solicitar(`/sesiones/${sesion.id}/ejecucion/`),
            solicitar(`/sesiones/${sesion.id}/asistencia/`),
          ]);

        if (!vigente) return;

        if (
          respuestaEjecucion.version !== sesion.version ||
          respuestaAsistencia.version !== sesion.version
        ) {
          establecerRequiereActualizar(true);
          establecerMensaje(
            'Los registros consultados no coinciden con ' +
            'la versión de la sesión. Actualiza el detalle.'
          );
          return;
        }

        establecerEjecucion(respuestaEjecucion.ejecucion);
        establecerAsistencia(respuestaAsistencia);
      } catch (fallo) {
        if (!vigente) return;

        establecerError(fallo);
        establecerRequiereActualizar(true);
      } finally {
        if (vigente) establecerCargando(false);
      }
    }

    consultarRegistros();

    return () => {
      vigente = false;
    };
  }, [sesion.id, sesion.version]);

  const participantes = asistencia?.participantes || [];

  const sinRegistrar = participantes.filter(
    (persona) => !ESTADOS_VALIDOS.includes(persona.estado)
  ).length;

  const fechaPermitida =
    Boolean(sesion.fecha) &&
    sesion.fecha <= fechaBogota();

  const ejecucionValida =
    Boolean(ejecucion) &&
    !ejecucion.finalizada_en &&
    Boolean(ejecucion.plan?.id) &&
    Array.isArray(ejecucion.actividades) &&
    ejecucion.actividades.length > 0;

  const puedeFinalizar =
    !cargando &&
    !enviando &&
    !requiereActualizar &&
    sesion.estado === 'planificada' &&
    sesion.estado_ejecucion === 'borrador' &&
    fechaPermitida &&
    ejecucionValida &&
    Boolean(asistencia) &&
    !asistencia.requiere_preparacion &&
    (asistencia.cerrada ||
      (participantes.length > 0 && sinRegistrar === 0));

  async function finalizarEjecucion(evento) {
    evento.preventDefault();

    if (
      !puedeFinalizar ||
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

    try {
      const resultado = await guardar(
        `/sesiones/${sesion.id}/ejecucion/finalizar/`,
        {
          clave: crypto.randomUUID(),
          version: sesion.version,
        }
      );

      establecerRequiereActualizar(true);

      if (
        !resultado?.sesion ||
        resultado.sesion.id !== sesion.id ||
        resultado.sesion.version !== sesion.version + 1 ||
        !resultado.asistencia?.cerrada ||
        !resultado.sesion.asistencia_confirmada ||
        resultado.sesion.estado_ejecucion !==
          'registrada_pendiente_validacion' ||
        resultado.sesion.estado !== 'planificada'
      ) {
        establecerError(
          new Error(
            'El servidor no devolvió una confirmación ' +
            'completa de la finalización.'
          )
        );
        establecerMensaje(
          'Consulta nuevamente la sesión y su ejecución ' +
          'antes de realizar otra operación.'
        );
        return;
      }

      establecerMensaje(
        'Ejecución finalizada y asistencia cerrada. ' +
        'La validación institucional continúa pendiente.'
      );

      onFinalizado?.(resultado);
    } catch (fallo) {
      establecerError(fallo);
      establecerRequiereActualizar(true);
      establecerMensaje(
        fallo.estado === 0
          ? 'No llegó una respuesta confirmada. ' +
            'La finalización podría haberse realizado. ' +
            'Consulta los registros antes de reintentar.'
          : 'La finalización no se confirmó. ' +
            'Actualiza el detalle y verifica los registros.'
      );
    } finally {
      envioActivo.current = false;
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h3>Finalización definitiva de ejecución</h3>

      <p className="aviso">
        Esta operación es definitiva para el profesor.
        Finaliza la ejecución real del entrenamiento y
        también cierra la asistencia si todavía estaba abierta.
        No valida institucionalmente la sesión como realizada.
      </p>

      {cargando && (
        <p role="status">
          Comprobando ejecución y asistencia…
        </p>
      )}

      <ErrorGestion error={error} />

      {mensaje && <p role="status">{mensaje}</p>}

      {requiereActualizar && (
        <p role="alert">
          Es necesario actualizar el detalle de la sesión
          antes de continuar.
        </p>
      )}

      {!cargando && (
        <>
          <h4>Comprobaciones antes de finalizar</h4>

          <dl>
            <dt>Versión de sesión</dt>
            <dd>{sesion.version}</dd>

            <dt>Plan registrado</dt>
            <dd>
              {ejecucion?.plan?.numero
                ? `Revisión ${ejecucion.plan.numero}`
                : 'No disponible'}
            </dd>

            <dt>Inicio real</dt>
            <dd>{ejecucion?.inicio || '—'}</dd>

            <dt>Fin real</dt>
            <dd>{ejecucion?.fin || '—'}</dd>

            <dt>Actividades registradas</dt>
            <dd>{ejecucion?.actividades?.length || 0}</dd>

            <dt>Participantes</dt>
            <dd>{participantes.length}</dd>

            <dt>Sin estado de asistencia</dt>
            <dd>{sinRegistrar}</dd>

            <dt>Asistencia cerrada</dt>
            <dd>{asistencia?.cerrada ? 'Sí' : 'No'}</dd>
          </dl>

          {!fechaPermitida && (
            <p role="alert">
              No es posible finalizar una sesión futura.
            </p>
          )}

          {!ejecucionValida && (
            <p role="alert">
              No existe un borrador de ejecución completo
              que pueda finalizarse.
            </p>
          )}

          {asistencia?.requiere_preparacion && (
            <p role="alert">
              Debes preparar y revisar el padrón antes
              de finalizar la ejecución.
            </p>
          )}

          {asistencia &&
            !asistencia.cerrada &&
            participantes.length === 0 && (
              <p role="alert">
                No hay participantes disponibles
                para cerrar la asistencia.
              </p>
            )}

          {asistencia &&
            !asistencia.cerrada &&
            sinRegistrar > 0 && (
              <p role="alert">
                Hay {sinRegistrar} participantes sin estado
                de asistencia. Completa primero el registro.
              </p>
            )}

          {ejecucion?.finalizada_en && (
            <p role="alert">
              Esta ejecución ya está finalizada.
            </p>
          )}

          <form onSubmit={finalizarEjecucion}>
            <label>
              <input
                type="checkbox"
                checked={confirmado}
                disabled={!puedeFinalizar}
                onChange={(evento) =>
                  establecerConfirmado(evento.target.checked)
                }
              />

              {' '}
              Confirmo que revisé las actividades ejecutadas,
              sus horarios y la asistencia. Comprendo que la
              ejecución quedará finalizada y que la asistencia
              también quedará cerrada definitivamente para
              modificaciones ordinarias.
            </label>

            <div className="acciones">
              <button
                type="submit"
                disabled={!puedeFinalizar || !confirmado}
              >
                {enviando
                  ? 'Finalizando ejecución…'
                  : 'Confirmar finalización definitiva'}
              </button>

              <button
                type="button"
                className="boton-secundario"
                disabled={enviando}
                onClick={onCancelar}
              >
                Cancelar finalización
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}
