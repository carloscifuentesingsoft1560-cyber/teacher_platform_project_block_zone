import { useState } from 'react';
import { SelectorCatalogo } from './SelectorCatalogo.jsx';
import { Campo, ErrorGestion, BotonesFormulario } from './Gestion.jsx';
import { guardar, fechaBogota } from '../api/gestion.js';
import { FormularioAscenso } from './FormularioAscenso.jsx';

export function FormularioPropuesta({ completada, cancelar }) {
  const [tipo, cambiarTipo] = useState('inscripcion');
  const [persona, cambiarPersona] = useState('');
  const [origen, cambiarOrigen] = useState('');
  const [destino, cambiarDestino] = useState('');
  const [detalle, cambiarDetalle] = useState(null);
  const [justificacion, cambiarJustificacion] = useState('');
  const [fecha] = useState(fechaBogota);
  const [error, cambiarError] = useState(null);
  const [enviando, cambiarEnviando] = useState(false);
  const [revision, cambiarRevision] = useState(0);
  const parametros = new URLSearchParams({ tipo, deportista: persona, fecha_efectiva: fecha });
  if (origen && tipo !== 'inscripcion') parametros.set('inscripcion_origen', origen);
  const listo = persona && (tipo === 'inscripcion' || origen);
  function limpiarDestino() { cambiarDestino(''); cambiarDetalle(null); cambiarError(null); }
  async function enviar(e) {
    e.preventDefault();
    if (enviando) return;
    if (!listo || !destino || !justificacion.trim()) {
      cambiarError(new Error('Selecciona deportista, origen cuando corresponda, destino compatible y justificación.'));return;
    }
    if (!window.confirm('¿Registrar esta propuesta para revisión? No ejecuta el traslado ni reserva cupo.')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      await guardar('/propuestas/', { tipo, deportista: Number(persona),
        ...(tipo !== 'inscripcion' ? { inscripcion_origen: Number(origen) } : {}),
        grupo_destino: Number(destino), fecha_efectiva: fecha, justificacion: justificacion.trim() });
      completada();
    } catch (e) { cambiarError(e); }
    finally { cambiarEnviando(false); }
  }
  const modalidad = <Campo etiqueta="Tipo de propuesta" aria-label="Tipo de propuesta" nombre="tipo-propuesta" valor={tipo}
    cambiar={(v) => { cambiarTipo(v); cambiarOrigen(''); limpiarDestino(); }}
    opciones={[["inscripcion","Inscripción adicional"],["traslado","Traslado al mismo nivel"],["ascenso","Ascenso institucional"]]} />;
  if (tipo === 'ascenso') return <FormularioAscenso modalidad={modalidad} cancelar={cancelar}
    completada={(registro) => completada({ modalidad: 'ascenso', registro })} />;
  return <form className="formulario-gestion" aria-label="Nueva propuesta docente" onSubmit={enviar}>
    <h2>Nueva propuesta docente</h2>
    <p>Fecha operativa: {fecha}. Proponer no inscribe, no traslada y no reserva plazas. La decisión vuelve a comprobar disponibilidad y permisos.</p>
    <ErrorGestion error={error} />
    <div className="rejilla-formulario">
      {modalidad}
      <SelectorCatalogo etiqueta="Deportista de mis grupos" nombre="propuesta-deportista" ruta="/deportistas/" valor={persona}
        etiquetaRegistro={(r) => (r.documento_presentacion || 'Documento pendiente') + ' · ' + r.nombres + ' ' + r.apellidos}
        cambiar={(id) => { cambiarPersona(id); cambiarOrigen(''); limpiarDestino(); }} />
      {persona && tipo !== 'inscripcion' && <SelectorCatalogo key={'origen-' + persona} etiqueta="Inscripción de origen" nombre="propuesta-origen"
        ruta={'/inscripciones/?' + new URLSearchParams({ estado: 'activa', deportista: persona })} valor={origen}
        etiquetaRegistro={(r) => r.nombre_grupo + ' · ' + r.nivel + ' · ' + r.periodo}
        cambiar={(id) => { cambiarOrigen(id); limpiarDestino(); }} />}
      {listo && <SelectorCatalogo key={parametros.toString() + '|' + revision} etiqueta="Grupo destino autorizado" nombre="propuesta-destino"
        ruta={'/propuestas/destinos/?' + parametros} valor={destino}
        etiquetaRegistro={(r) => [r.codigo, r.nombre, r.nivel_nombre, r.jornada, r.periodo_nombre].filter(Boolean).join(' · ')}
        cambiar={(id, r) => { cambiarDestino(id); cambiarDetalle(r || null); }} />}
    </div>
    {listo && <button type="button" className="boton-secundario" onClick={() => { limpiarDestino(); cambiarRevision((r) => r + 1); }}>Actualizar destinos compatibles</button>}
    {detalle && <section aria-label="Información mínima del destino" className="detalle-grupo">
      <h3>{detalle.codigo} · {detalle.nombre}</h3><p>{detalle.nivel_nombre} · {detalle.jornada} · {detalle.periodo_nombre}</p>
      <p>Periodo: {detalle.fecha_inicio_periodo} a {detalle.fecha_fin_periodo}. Disponibilidad consultada: {detalle.disponibilidad?.disponibles} plazas, del {detalle.disponibilidad?.desde} al {detalle.disponibilidad?.hasta}.</p>
      <ul>{detalle.horarios?.map((h, i) => <li key={i}>{['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'][h.dia]}: {h.hora_inicio} a {h.hora_fin}</li>)}</ul>
      <p>Esta información no habilita acceso a deportistas ni expedientes del grupo de destino.</p>
    </section>}
    <Campo etiqueta="Justificación de la propuesta" nombre="justificacion-propuesta" valor={justificacion} cambiar={cambiarJustificacion} maxLength={240} />
    <BotonesFormulario enviando={enviando} cancelar={cancelar} />
  </form>;
}
