import { useState } from 'react';
import { Campo, ErrorGestion, useListado, BarraListado, PieListado, BotonesFormulario } from './Gestion.jsx';
import { CamposDocumento, motivosDocumento, useTiposDocumento } from './DocumentoDeportista.jsx';
import { guardar } from '../api/gestion.js';

function Historia({ uuid }) {
  const lista = useListado('/deportistas/' + uuid + '/historial-documental/');
  return <section><h2>Historial documental</h2><p>Solo conserva referencias enmascaradas, no números anteriores completos.</p>
    <BarraListado listado={lista} /><ul>{lista.datos.results.map((c) => <li key={c.id}>{c.fecha} · {c.motivo} · {c.tipo_anterior || 'Pendiente'} {c.documento_anterior_enmascarado} → {c.tipo_nuevo || 'Pendiente'} {c.documento_nuevo_enmascarado} · Responsable {c.actor}</li>)}</ul>
    <PieListado listado={lista} />
  </section>;
}

export function GestionDocumentoFicha({ ficha, actualizar }) {
  const catalogo = useTiposDocumento(true);
  const [abierto, cambiarAbierto] = useState(false);
  const [datos, cambiarDatos] = useState({});
  const [motivo, cambiarMotivo] = useState('completar_pendiente');
  const [enviando, cambiarEnviando] = useState(false);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  function abrir() {
    cambiarDatos({ tipo_documento: ficha.tipo_documento || null, numero_documento: ficha.numero_documento || '', pais_emisor: ficha.pais_emisor || '' });
    cambiarMotivo(ficha.tipo_documento ? 'nuevo_documento' : 'completar_pendiente'); cambiarAbierto(true);
  }
  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm('¿Confirmas el cambio documental en esta misma ficha?')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      actualizar(await guardar('/deportistas/' + ficha.identificador_publico + '/cambiar-documento/', { ...datos, version: ficha.version, motivo }));
      cambiarAbierto(false); cambiarDatos({}); cambiarAviso('Documento actualizado sin cambiar la identidad ni sus relaciones.');
    } catch (e) { cambiarError(e); }
    finally { cambiarEnviando(false); }
  }
  return <section><ErrorGestion error={error} /><ErrorGestion error={catalogo.error} />{aviso && <p role="status">{aviso}</p>}
    <button className="boton-secundario" onClick={abrir}>Cambiar documento</button>
    {abierto && <form className="formulario-gestion" aria-label="Cambio documental" onSubmit={enviar}><h2>Cambio documental</h2>
      <CamposDocumento datos={datos} cambiar={cambiarDatos} tipos={catalogo.tipos} prefijo="cambio" />
      <Campo etiqueta="Motivo del cambio documental" nombre="motivo-documento" valor={motivo} cambiar={cambiarMotivo} opciones={motivosDocumento} />
      <p>Los motivos están codificados para no almacenar números completos en el historial. La anulación solo corresponde a un dato registrado por error.</p>
      <BotonesFormulario enviando={enviando} cancelar={() => { cambiarAbierto(false); cambiarDatos({}); }} />
    </form>}
    <Historia key={ficha.version} uuid={ficha.identificador_publico} />
  </section>;
}
