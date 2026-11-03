import { useState } from 'react';
import { Campo, ErrorGestion, useListado, BotonesFormulario } from './Gestion.jsx';

export function SelectorRegistro({ campo, valor, cambiar }) {
  const lista = useListado(campo.ruta);
  const nombre = (r) => (r.documento_presentacion || r.codigo_interno) ? (r.documento_presentacion || 'Documento pendiente') + ' · ' + r.nombres + ' ' + r.apellidos :
    r.nombres ? r.nombres + ' ' + r.apellidos : r.nombre_deportista ? r.nombre_deportista + ' · ' + r.nombre_grupo : r.nombre || (r.finalidad ? r.finalidad + (r.numero_version ? ' · v' + r.numero_version : '') : r.codigo);
  return <fieldset><legend>{campo.etiqueta}</legend>
    <Campo etiqueta={'Buscar ' + campo.etiqueta.toLowerCase()} nombre={'buscar-' + campo.nombre} tipo="search" requerido={false} valor={lista.busqueda} cambiar={lista.buscar} />
    <ErrorGestion error={lista.error} />
    <Campo etiqueta={campo.etiqueta} nombre={campo.nombre} valor={valor} cambiar={cambiar}
      requerido={campo.requerido !== false} opciones={lista.datos.results.map((r) => [r.id, nombre(r)])} />
    {lista.datos.next && <button type="button" className="boton-secundario" onClick={() => lista.cambiarPagina(lista.pagina + 1)}>Más opciones de {campo.etiqueta.toLowerCase()}</button>}
  </fieldset>;
}

export function FormularioRegistro({ titulo, campos, inicial = {}, guardar, cancelar, children }) {
  const [datos, cambiarDatos] = useState(inicial);
  const [error, cambiarError] = useState(null);
  const [enviando, cambiarEnviando] = useState(false);
  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm('¿Confirmas esta operación?')) return;
    cambiarEnviando(true); cambiarError(null);
    try { await guardar(datos); }
    catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }
  return <form className="formulario-gestion" aria-label={titulo} onSubmit={enviar}>
    <h2>{titulo}</h2><ErrorGestion error={error} />
    {children}
    <div className="rejilla-formulario">{campos.map((campo) => {
      const cambiar = (v) => cambiarDatos((antes) => ({ ...antes, [campo.nombre]: campo.numero && v !== '' ? Number(v) : v }));
      if (campo.ruta) return <SelectorRegistro key={campo.nombre} campo={campo} valor={datos[campo.nombre]} cambiar={cambiar} />;
      if (campo.tipo === 'checkbox') return <label key={campo.nombre} className="campo-checkbox"><input type="checkbox" checked={Boolean(datos[campo.nombre])} onChange={(e) => cambiar(e.target.checked)} />{campo.etiqueta}</label>;
      return <Campo key={campo.nombre} {...Object.fromEntries(Object.entries(campo).filter(([k]) => !["ruta", "numero", "requerido"].includes(k)))} valor={datos[campo.nombre]} cambiar={cambiar} requerido={campo.requerido !== false} />;
    })}</div><BotonesFormulario enviando={enviando} cancelar={cancelar} />
  </form>;
}
