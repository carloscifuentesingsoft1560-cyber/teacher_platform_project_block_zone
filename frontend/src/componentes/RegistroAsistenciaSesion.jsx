
import { useEffect, useRef, useState } from 'react';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const ESTADOS = [
  ['', 'Sin registrar'],
  ['asistio', 'Asistió'],
  ['no_asistio', 'No asistió'],
  ['tarde', 'Llegó tarde'],
  ['excusa', 'Excusa'],
  ['retiro', 'Retiro'],
];

function nombreCompleto(persona) {
  return [persona.nombres, persona.apellidos]
    .filter(Boolean)
    .join(' ') || `Deportista ${persona.deportista}`;
}

function obtenerRegistros(participantes) {
  return Object.fromEntries(
    participantes.map((persona) => [
      String(persona.inscripcion),
      persona.estado || '',
    ])
  );
}

export function RegistroAsistenciaSesion({
  sesion,
  onGuardado,
  onCancelar,
}) {
  const [padron, establecerPadron] = useState(null);
  const [registros, establecerRegistros] = useState({});

  const [cargando, establecerCargando] = useState(true);
  const [enviando, establecerEnviando] = useState(false);

  const [error, establecerError] = useState(null);
  const [mensaje, establecerMensaje] = useState('');

  const [requiereActualizar, establecerRequiereActualizar] =
    useState(false);

  const envioActivo = useRef(false);
  const intento = useRef(null);

  useEffect(() => {
    let vigente = true;

    establecerCargando(true);
    establecerError(null);
    establecerMensaje('');
    establecerPadron(null);
    establecerRegistros({});
    establecerRequiereActualizar(false);
    intento.current = null;

    async function consultar() {
      try {
        const respuesta = await solicitar(
          `/sesiones/${sesion.id}/asistencia/`
        );

        if (!vigente) return;

        establecerPadron(respuesta);

        establecerRegistros(
          obtenerRegistros(respuesta.participantes || [])
        );
      } catch (fallo) {
        if (vigente) establecerError(fallo);
      } finally {
        if (vigente) establecerCargando(false);
      }
    }

    consultar();

    return () => {
      vigente = false;
    };
  }, [sesion.id, sesion.version]);

  const versionCoincide =
    padron?.version === sesion.version;

  const editable =
    !cargando &&
    !enviando &&
    !requiereActualizar &&
    !!padron &&
    !padron.cerrada &&
    !padron.requiere_preparacion &&
    versionCoincide &&
    sesion.estado === 'planificada';

  function cambiarEstado(inscripcion, estado) {
    if (!editable) return;

    establecerRegistros((actuales) => ({
      ...actuales,
      [String(inscripcion)]: estado,
    }));

    intento.current = null;
    establecerError(null);
    establecerMensaje('');
  }

  async function guardarAsistencia(evento) {
    evento.preventDefault();

    if (!editable || envioActivo.current) return;

    const participantes = padron.participantes || [];

    const clavesEsperadas = participantes
      .map((persona) => String(persona.inscripcion))
      .sort();

    const clavesRegistradas =
      Object.keys(registros).sort();

    const estadosValidos = ESTADOS.map(
      ([estado]) => estado
    );

    const padronCompleto =
      JSON.stringify(clavesEsperadas) ===
      JSON.stringify(clavesRegistradas);

    const valoresValidos = Object.values(registros)
      .every((estado) => estadosValidos.includes(estado));

    if (!padronCompleto || !valoresValidos) {
      establecerError(
        new Error(
          'El padrón contiene registros incompletos o inválidos.'
        )
      );
      return;
    }

    const contenido = {
      version: padron.version,
      registros: { ...registros },
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
        new Error(
          'La solicitud cambió. Actualiza la asistencia.'
        )
      );
      return;
    }

    envioActivo.current = true;
    establecerEnviando(true);
    establecerError(null);
    establecerMensaje('');

    try {
      const resultado = await guardar(
        `/sesiones/${sesion.id}/asistencia/`,
        {
          clave: intento.current.clave,
          ...contenido,
        }
      );

      intento.current = null;

      establecerMensaje(
        'Asistencia guardada. Todavía no está cerrada.'
      );

      establecerRequiereActualizar(true);

      onGuardado?.(resultado);
    } catch (fallo) {
      establecerError(fallo);
      establecerRequiereActualizar(true);

      establecerMensaje(
        fallo.estado === 0
          ? (
              'No llegó una respuesta confirmada. ' +
              'Consulta la sesión antes de reintentar.'
            )
          : (
              'No se confirmó el guardado. ' +
              'Actualiza la sesión y comprueba los permisos.'
            )
      );
    } finally {
      envioActivo.current = false;
      establecerEnviando(false);
    }
  }

  return (
    <section className="formulario-gestion">
      <h3>Registrar asistencia de la sesión</h3>

      <p>
        Selecciona el estado de cada participante.
        El guardado no cierra la asistencia.
      </p>

      {cargando && (
        <p role="status">
          Consultando el padrón autorizado…
        </p>
      )}

      <ErrorGestion error={error} />

      {padron && (
        <>
          <dl>
            <dt>Versión del padrón</dt>
            <dd>{padron.version}</dd>

            <dt>Participantes</dt>
            <dd>{padron.participantes?.length || 0}</dd>

            <dt>Asistencia cerrada</dt>
            <dd>{padron.cerrada ? 'Sí' : 'No'}</dd>
          </dl>

          {padron.cerrada && (
            <p role="alert">
              Esta asistencia está cerrada y no admite
              modificaciones docentes.
            </p>
          )}

          {padron.requiere_preparacion && (
            <p role="alert">
              El padrón ha cambiado. Requiere preparación
              autorizada antes de guardar la asistencia.
            </p>
          )}

          {!versionCoincide && (
            <p role="alert">
              La versión consultada no coincide con la
              sesión. Actualiza el detalle antes de guardar.
            </p>
          )}

          <form onSubmit={guardarAsistencia}>
            <div className="tabla-contenedor">
              <table>
                <thead>
                  <tr>
                    <th>Participante</th>
                    <th>Estado de asistencia</th>
                  </tr>
                </thead>

                <tbody>
                  {(padron.participantes || []).map(
                    (persona) => (
                      <tr key={persona.inscripcion}>
                        <td>{nombreCompleto(persona)}</td>

                        <td>
                          <label>
                            <span className="sr-only">
                              Asistencia de{' '}
                              {nombreCompleto(persona)}
                            </span>

                            <select
                              aria-label={
                                `Asistencia de ${nombreCompleto(persona)}`
                              }
                              value={
                                registros[
                                  String(persona.inscripcion)
                                ] ?? ''
                              }
                              disabled={!editable}
                              onChange={(evento) =>
                                cambiarEstado(
                                  persona.inscripcion,
                                  evento.target.value
                                )
                              }
                            >
                              {ESTADOS.map(([valor, texto]) => (
                                <option
                                  key={valor}
                                  value={valor}
                                >
                                  {texto}
                                </option>
                              ))}
                            </select>
                          </label>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>

            {requiereActualizar && (
              <p role="status">
                Actualiza el detalle de la sesión antes
                de realizar otra operación.
              </p>
            )}

            {mensaje && <p role="status">{mensaje}</p>}

            <div className="acciones">
              <button
                type="submit"
                disabled={!editable}
              >
                {enviando
                  ? 'Guardando asistencia…'
                  : 'Guardar asistencia'}
              </button>

              <button
                type="button"
                className="boton-secundario"
                disabled={enviando}
                onClick={onCancelar}
              >
                Cerrar formulario
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
