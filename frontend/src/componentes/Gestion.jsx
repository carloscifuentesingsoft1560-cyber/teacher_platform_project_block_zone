import { useEffect, useState } from 'react';
import { solicitar } from '../api/cliente.js';

export function ErrorGestion({ error }) {
  if (!error) return null;
  return <div className="mensaje-error" role="alert"><p>{error.message || String(error)}</p>
    {error.errores && <ul>{Object.entries(error.errores).map(([campo, mensajes]) =>
      <li key={campo}>{campo}: {Array.isArray(mensajes) ? mensajes.join(' ') : String(mensajes)}</li>)}</ul>}
  </div>;
}
export function Campo({ etiqueta, nombre, valor, cambiar, tipo = 'text', opciones, requerido = true, ...resto }) {
  const id = 'campo-' + nombre;
  return <label className="campo-gestion" htmlFor={id}>{etiqueta}
    {opciones ? <select id={id} value={valor ?? ''} onChange={(e) => cambiar(e.target.value)} required={requerido} {...resto}>
      <option value="">Seleccionar…</option>{opciones.map(([idOpcion, texto]) => <option key={idOpcion} value={idOpcion}>{texto}</option>)}
    </select> : <input id={id} type={tipo} value={valor ?? ''} onChange={(e) => cambiar(e.target.value)} required={requerido} {...resto} />}
  </label>;
}
export function Paginacion({ pagina, cambiar, siguiente, total }) {
  return <div className="paginacion"><span>{total} registros · Página {pagina}</span>
    <button className="boton-secundario" disabled={pagina === 1} onClick={() => cambiar(pagina - 1)}>Anterior</button>
    <button className="boton-secundario" disabled={!siguiente} onClick={() => cambiar(pagina + 1)}>Siguiente</button>
  </div>;
}
export function useListado(ruta, { permitirBusqueda = true } = {}) {
  const [pagina, cambiarPagina] = useState(1);
  const [busqueda, cambiarBusqueda] = useState('');
  const [version, cambiarVersion] = useState(0);
  const [datos, establecerDatos] = useState({ results: [], count: 0 });
  const [error, establecerError] = useState(null);
  const [cargando, establecerCargando] = useState(true);
  useEffect(() => {
    let vigente = true;
    establecerCargando(true); establecerError(null); establecerDatos({ results: [], count: 0 });
    solicitar(ruta + (ruta.includes('?') ? '&' : '?') + new URLSearchParams({ page: pagina, ...(permitirBusqueda ? { search: busqueda } : {}) }))
      .then((r) => { if (vigente) establecerDatos(r); })
      .catch((e) => { if (vigente) { establecerError(e); establecerDatos({ results: [], count: 0 }); } })
      .finally(() => { if (vigente) establecerCargando(false); });
    return () => { vigente = false; };
  }, [ruta, pagina, busqueda, version, permitirBusqueda]);
  return { datos, error, cargando, pagina, cambiarPagina, busqueda,
    buscar: (texto) => { cambiarBusqueda(texto); cambiarPagina(1); },
    recargar: () => cambiarVersion((v) => v + 1) };
}
export function BarraListado({ listado, children, etiquetaBusqueda = 'Buscar' }) {
  return <><div className="barra-gestion">
    <Campo etiqueta={etiquetaBusqueda} nombre="buscar" valor={listado.busqueda} cambiar={listado.buscar} requerido={false} tipo="search" />
    {children}
  </div><ErrorGestion error={listado.error} />{listado.cargando && <p role="status">Cargando registros…</p>}
  {!listado.cargando && !listado.error && !listado.datos.count && <p>No hay registros para esta consulta.</p>}</>;
}
export function PieListado({ listado }) {
  return <Paginacion pagina={listado.pagina} cambiar={listado.cambiarPagina} siguiente={listado.datos.next} total={listado.datos.count} />;
}
export function BotonesFormulario({ enviando, cancelar, texto = 'Guardar cambios' }) {
  return <div className="acciones"><button type="submit" disabled={enviando}>{enviando ? 'Guardando…' : texto}</button>
    <button type="button" className="boton-secundario" disabled={enviando} onClick={cancelar}>Cancelar</button></div>;
}
