import { useState } from 'react';
import { CamposDocumento } from './DocumentoDeportista.jsx';
import { ErrorGestion, BotonesFormulario } from './Gestion.jsx';
import { guardar } from '../api/gestion.js';

export function BusquedaDocumento({ tipos, resultado, cancelar }) {
  const [datos, cambiarDatos] = useState({ tipo_documento: null, numero_documento: '', pais_emisor: '' });
  const [error, cambiarError] = useState(null);
  const [enviando, cambiarEnviando] = useState(false);
  async function enviar(e) {
    e.preventDefault();
    if (enviando) return;
    cambiarEnviando(true); cambiarError(null);
    try { resultado(await guardar('/deportistas/buscar-documento/', datos)); }
    catch (e) { cambiarError(e); }
    finally { cambiarEnviando(false); }
  }
  return <form className="formulario-gestion" aria-label="Buscar por documento" onSubmit={enviar}>
    <h2>Búsqueda documental exacta</h2><ErrorGestion error={error} />
    <CamposDocumento datos={datos} cambiar={cambiarDatos} tipos={tipos} prefijo="buscar-documento" pendiente={false} />
    <BotonesFormulario enviando={enviando} texto="Consultar documento" cancelar={cancelar} />
  </form>;
}
