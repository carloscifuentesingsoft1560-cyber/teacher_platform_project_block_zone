import { useEffect, useRef, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { SelectorCatalogo } from './SelectorCatalogo.jsx';
import { ErrorGestion, BotonesFormulario } from './Gestion.jsx';

export function FormularioAscenso({ modalidad, completada, cancelar }) {
  const [persona, cambiarPersona] = useState('');
  const [disciplina, cambiarDisciplina] = useState('');
  const [referencia, cambiarReferencia] = useState('');
  const [detalle, cambiarDetalle] = useState(null);
  const [nivel, cambiarNivel] = useState(null);
  const [justificacion, cambiarJustificacion] = useState('');
  const [error, cambiarError] = useState(null);
  const [errorNivel, cambiarErrorNivel] = useState(null);
  const [cargando, cambiarCargando] = useState(false);
  const [enviando, cambiarEnviando] = useState(false);
  const [revision, cambiarRevision] = useState(0);
  const bloqueo = useRef(false);
  const listo = Boolean(persona && disciplina && referencia && detalle);
  const clave = [persona, disciplina, referencia].join(':');
  const nivelActual = nivel?.clave === clave ? nivel.valor : null;

  useEffect(() => {
    let vigente = true;
    cambiarNivel(null); cambiarErrorNivel(null); cambiarCargando(listo);
    if (!listo) return;
    const parametros = new URLSearchParams({ deportista: persona, disciplina, inscripcion_referencia: referencia });
    solicitar('/ascensos/niveles/?' + parametros).then((r) => {
      if (!vigente) return;
      if (!Array.isArray(r.results) || r.results.length > 1 || r.next) throw new Error('La respuesta de niveles no permite confirmar un ascenso consecutivo. Actualiza la consulta.');
      const siguiente = r.results[0] || null;
      if (siguiente && (Number(siguiente.disciplina) !== Number(disciplina) ||
          Number(siguiente.orden) !== Number(detalle.nivel_origen.orden) + 1 ||
          Number(siguiente.id) === Number(detalle.nivel_origen.id))) {
        throw new Error('El nivel recibido no es consecutivo dentro de la disciplina seleccionada.');
      }
      cambiarNivel({ clave, valor: siguiente });
    }).catch((e) => { if (vigente) cambiarErrorNivel(e); })
      .finally(() => { if (vigente) cambiarCargando(false); });
    return () => { vigente = false; };
  }, [persona, disciplina, referencia, detalle, clave, listo, revision]);

  function limpiarReferencia() {
    cambiarReferencia(''); cambiarDetalle(null); cambiarNivel(null); cambiarError(null);
  }
  async function enviar(e) {
    e.preventDefault();
    if (bloqueo.current) return;
    if (!listo || !nivelActual || cargando || errorNivel || !justificacion.trim() || justificacion.trim().length > 500) {
      cambiarError(new Error('Selecciona deportista, disciplina, referencia activa y nivel consecutivo disponible; escribe una justificación de hasta 500 caracteres.'));
      return;
    }
    if (!window.confirm('¿Registrar el ascenso para revisión pedagógica? No aprueba, no traslada ni reserva cupos.')) return;
    bloqueo.current = true; cambiarEnviando(true); cambiarError(null);
    try {
      const resultado = await guardar('/ascensos/', { deportista: Number(persona), disciplina: Number(disciplina),
        inscripcion_referencia: Number(referencia), nivel_destino: Number(nivelActual.id),
        justificacion: justificacion.trim() });
      if (!resultado.id || resultado.estado_decision !== 'pendiente' || resultado.estado_plan !== 'pendiente') {
        throw new Error('No se pudo confirmar la respuesta. Consulta el listado antes de intentar otra propuesta.');
      }
      completada(resultado);
    } catch (e) {
      cambiarError(e.estado === 0 ? new Error(e.message + ' La solicitud podría haberse procesado; consulta el listado antes de reenviar.') : e);
    } finally { bloqueo.current = false; cambiarEnviando(false); }
  }

  return <form className="formulario-gestion" aria-label="Nueva propuesta de ascenso institucional" onSubmit={enviar}>
    <h2>Proponer ascenso institucional</h2>
    <p id="aviso-ascenso">Solo registra la intención docente. No aprueba, no cambia grupos ni niveles efectivos, no ejecuta traslados y no modifica cupos o reservas.</p>
    <ErrorGestion error={error} />
    <fieldset className="datos-ascenso" disabled={enviando} aria-describedby="aviso-ascenso">
      <legend>Datos de la propuesta</legend>
      {modalidad}
      <div className="rejilla-formulario">
        <SelectorCatalogo etiqueta="Deportista de mis grupos" nombre="ascenso-deportista" ruta="/deportistas/" valor={persona}
          etiquetaRegistro={(r) => (r.documento_presentacion || 'Documento pendiente') + ' · ' + r.nombres + ' ' + r.apellidos}
          cambiar={(id, r) => { cambiarPersona(r ? id : ''); cambiarDisciplina(''); limpiarReferencia(); }} />
        {persona && <SelectorCatalogo key={'disciplina-' + persona} etiqueta="Disciplina disponible" nombre="ascenso-disciplina"
          ruta={'/ascensos/contexto/?' + new URLSearchParams({ deportista: persona, vista: 'disciplinas' })}
          valor={disciplina} cambiar={(id, r) => { cambiarDisciplina(r ? id : ''); limpiarReferencia(); }} />}
        {persona && disciplina && <SelectorCatalogo key={'referencia-' + persona + '-' + disciplina} etiqueta="Inscripción activa de referencia" nombre="ascenso-referencia"
          ruta={'/ascensos/contexto/?' + new URLSearchParams({ deportista: persona, disciplina, vista: 'referencias' })}
          etiquetaRegistro={(r) => [r.grupo_codigo, r.grupo_nombre, r.nivel_origen?.nombre, r.periodo_nombre].filter(Boolean).join(' · ')}
          valor={referencia} cambiar={(id, r) => { cambiarReferencia(r ? id : ''); cambiarDetalle(r || null); cambiarNivel(null); cambiarError(null); }} />}
        {detalle && <div className="campo-gestion"><span id="etiqueta-origen-ascenso">Nivel de origen de la referencia</span>
          <output aria-labelledby="etiqueta-origen-ascenso">{detalle.nivel_origen.nombre}</output></div>}
        {listo && <div className="campo-gestion"><span id="etiqueta-destino-ascenso">Nivel propuesto</span>
          <output aria-labelledby="etiqueta-destino-ascenso" aria-live="polite">{nivelActual?.nombre || (cargando ? 'Consultando nivel…' : 'No disponible')}</output></div>}
      </div>
      {listo && <>
        {cargando && <p role="status">Consultando el nivel inmediatamente superior…</p>}
        <ErrorGestion error={errorNivel} />
        {!cargando && !errorNivel && !nivelActual && <p role="status">No hay un nivel inmediatamente superior activo disponible. No se omiten niveles ni se seleccionan destinos incompatibles.</p>}
        <button type="button" className="boton-secundario" disabled={cargando} onClick={() => cambiarRevision((v) => v + 1)}>Actualizar nivel disponible</button>
      </>}
      <p>La referencia acredita tu ámbito; no limita la revisión institucional a ese grupo. La coordinación revisará todas las inscripciones pertinentes, incluidas suspendidas y futuras. Aquí solo se muestra información de tus grupos autorizados.</p>
      <label className="campo-gestion" htmlFor="justificacion-ascenso">Justificación pedagógica y deportiva
        <textarea id="justificacion-ascenso" rows={4} required maxLength={500} aria-describedby="limite-justificacion-ascenso"
          value={justificacion} onChange={(e) => cambiarJustificacion(e.target.value)} />
      </label>
      <p id="limite-justificacion-ascenso">Hasta 500 caracteres. {justificacion.length}/500.</p>
    </fieldset>
    <BotonesFormulario enviando={enviando} cancelar={cancelar} texto="Registrar propuesta de ascenso" />
  </form>;
}
