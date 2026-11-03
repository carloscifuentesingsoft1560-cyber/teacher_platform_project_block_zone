import { useEffect, useState } from 'react';
import { Campo, ErrorGestion } from './Gestion.jsx';
import { todas } from '../api/gestion.js';

export const motivosDocumento = [
  ['completar_pendiente', 'Completar documento pendiente'],
  ['correccion', 'Corregir un dato documental'],
  ['nuevo_documento', 'Registrar un nuevo documento'],
  ['anulacion_por_error', 'Anular una identificación registrada por error'],
];
const tiposColombianos = new Set(['RC', 'TI', 'CC', 'CE', 'PPT']);

export function useTiposDocumento(habilitado) {
  const [tipos, cambiarTipos] = useState([]);
  const [error, cambiarError] = useState(null);
  useEffect(() => {
    let vigente = true;
    if (!habilitado) return;
    todas('/tipos-documento/').then((r) => { if (vigente) cambiarTipos(r); }).catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [habilitado]);
  return { tipos, error };
}

export function CamposDocumento({ datos, cambiar, tipos, prefijo, pendiente = true }) {
  const tipo = datos.tipo_documento || '';
  const fijo = tiposColombianos.has(tipo);
  return <fieldset><legend>Documento de identidad</legend>
    <div className="rejilla-formulario">
      <Campo etiqueta="Tipo de documento" aria-label="Tipo de documento" nombre={prefijo + '-tipo'} requerido={!pendiente} valor={tipo}
        opciones={tipos.filter((t) => t.activo !== false || t.codigo === tipo).map((t) => [t.codigo, t.nombre])}
        cambiar={(v) => cambiar({ tipo_documento: v || null, numero_documento: '', pais_emisor: tiposColombianos.has(v) ? 'CO' : '' })} />
      {tipo && <><Campo etiqueta="Número de documento" aria-label="Número de documento" nombre={prefijo + '-numero'} valor={datos.numero_documento || ''}
        tipo="text" autoComplete="off" spellCheck={false} maxLength={120}
        cambiar={(v) => cambiar({ ...datos, numero_documento: v })} />
        <Campo etiqueta="País emisor (código ISO)" aria-label="País emisor (código ISO)" nombre={prefijo + '-pais'} valor={fijo ? 'CO' : datos.pais_emisor || ''}
          readOnly={fijo} maxLength={2} pattern="[A-Za-z]{2}" autoComplete="off"
          cambiar={(v) => cambiar({ ...datos, pais_emisor: v.toUpperCase() })} /></>}
    </div>
    {!tipo && pendiente && <p>Documento pendiente. No se genera un número provisional.</p>}
    {tipo && <p>Conserva letras y ceros iniciales. País emisor: por ejemplo CO, VE, EC o US. En registro civil indica NUIP/NIP, no el serial.</p>}
  </fieldset>;
}

export function ErrorTiposDocumento({ catalogo }) {
  return <ErrorGestion error={catalogo.error} />;
}
