import { useEffect, useRef, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { Campo, ErrorGestion } from './Gestion.jsx';

export function etiquetaCatalogo(registro) {
  return [registro.codigo, registro.nombre, registro.periodo_nombre,
    registro.disciplina_nombre && !registro.periodo_nombre ? registro.disciplina_nombre : null]
    .filter(Boolean).join(' · ');
}

// Caché local a esta instancia: no comparte catálogos ni permisos entre sesiones.
export function SelectorCatalogo({ etiqueta, nombre, ruta, valor, cambiar, etiquetaRegistro = etiquetaCatalogo }) {
  const [texto, cambiarTexto] = useState('');
  const [busqueda, cambiarBusqueda] = useState('');
  const [opciones, cambiarOpciones] = useState([]);
  const [siguiente, cambiarSiguiente] = useState(null);
  const [seleccionado, cambiarSeleccionado] = useState(null);
  const [error, cambiarError] = useState(null);
  const [cargando, cambiarCargando] = useState(false);
  const [consultado, cambiarConsultado] = useState(false);
  const [revision, cambiarRevision] = useState(0);
  const cache = useRef(new Map());
  const registros = useRef(new Map());
  const generacion = useRef(0);
  const cargandoMas = useRef(false);
  useEffect(() => {
    const reloj = setTimeout(() => cambiarBusqueda(texto.trim()), 300);
    return () => clearTimeout(reloj);
  }, [texto]);
  useEffect(() => {
    const turno = ++generacion.current;
    let vigente = true;
    cambiarError(null); cambiarOpciones([]); cambiarSiguiente(null); cambiarCargando(true); cambiarConsultado(false);
    cargandoMas.current = false;
    const url = ruta + (ruta.includes('?') ? '&' : '?') + new URLSearchParams({ search: busqueda });
    const promesa = cache.current.has(url) ? Promise.resolve(cache.current.get(url)) : solicitar(url);
    promesa.then((r) => {
      if (!vigente || turno !== generacion.current) return;
      cache.current.set(url, r);
      r.results.forEach((x) => registros.current.set(String(x.id), x));
      cambiarOpciones(r.results); cambiarSiguiente(r.next);
    }).catch((e) => { if (vigente) cambiarError(e); })
      .finally(() => { if (vigente) { cambiarCargando(false); cambiarConsultado(true); } });
    return () => { vigente = false; };
  }, [ruta, busqueda, revision]);
  useEffect(() => {
    let vigente = true;
    if (!valor) { cambiarSeleccionado(null); return; }
    const conocido = registros.current.get(String(valor));
    if (conocido) { cambiarSeleccionado(conocido); return; }
    // Resolver filtros recibidos por URL sin pedir al usuario que conozca su ID.
    if (cargando || !consultado || error) return;
    if (!/^\d+$/.test(String(valor))) {
      cambiarSeleccionado(null); cambiarError(new Error('La selección de catálogo no es válida. Puedes elegir otra opción.')); return;
    }
    solicitar(ruta.split('?')[0] + valor + '/').then((r) => {
      if (vigente) { registros.current.set(String(r.id), r); cambiarSeleccionado(r); }
    }).catch((e) => { if (vigente) { cambiarSeleccionado(null); cambiarError(e); } });
    return () => { vigente = false; };
  }, [valor, ruta, opciones, cargando, consultado, error]);
  async function mas() {
    if (!siguiente || cargandoMas.current) return;
    const turno = generacion.current;
    cargandoMas.current = true; cambiarCargando(true); cambiarError(null);
    const u = new URL(siguiente, window.location.origin);
    const url = u.pathname.replace(/^\/api/, '') + u.search;
    try {
      const r = cache.current.has(url) ? cache.current.get(url) : await solicitar(url);
      if (turno !== generacion.current) return;
      cache.current.set(url, r);
      r.results.forEach((x) => registros.current.set(String(x.id), x));
      cambiarOpciones((anteriores) => [...new Map([...anteriores, ...r.results].map((x) => [x.id, x])).values()]);
      cambiarSiguiente(r.next);
    } catch (e) { if (turno === generacion.current) cambiarError(e); }
    finally { if (turno === generacion.current) { cargandoMas.current = false; cambiarCargando(false); } }
  }
  const visibles = seleccionado && !opciones.some((r) => String(r.id) === String(seleccionado.id)) ? [seleccionado, ...opciones] : opciones;
  return <fieldset className="selector-catalogo"><legend>{etiqueta}</legend>
    <Campo etiqueta={'Buscar ' + etiqueta.toLowerCase().replace(/^filtrar /, '')} nombre={'buscar-' + nombre} tipo="search" requerido={false} valor={texto} cambiar={cambiarTexto} />
    <ErrorGestion error={error} />
    <Campo etiqueta={etiqueta} aria-label={etiqueta} nombre={nombre} requerido={false} valor={valor || ''}
      cambiar={(id) => { const r = registros.current.get(String(id)); cambiarSeleccionado(r || null); cambiar(id, r); }}
      opciones={[
        ...(valor && !visibles.some((r) => String(r.id) === String(valor)) ? [[valor, 'Selección no disponible en esta consulta']] : []),
        ...visibles.map((r) => [r.id, etiquetaRegistro(r)]),
      ]} />
    {cargando && <p role="status">Cargando opciones de {etiqueta.toLowerCase()}…</p>}
    {!cargando && !error && !opciones.length && <p>No hay opciones para esta búsqueda.</p>}
    {siguiente && <button type="button" className="boton-secundario" disabled={cargando} onClick={mas}>Más opciones de {etiqueta.toLowerCase()}</button>}
    {error && <button type="button" className="boton-secundario" onClick={() => { cache.current.clear(); cambiarRevision((v) => v + 1); }}>Reintentar {etiqueta.toLowerCase()}</button>}
  </fieldset>;
}
