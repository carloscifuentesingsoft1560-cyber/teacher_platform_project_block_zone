import { useState } from 'react';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, PieListado } from '../componentes/Gestion.jsx';
import { SelectorCatalogo } from '../componentes/SelectorCatalogo.jsx';

export function Identidades() {
  const lista = useListado('/identidad/', { permitirBusqueda: false });
  const [tipo, elegirTipo] = useState('usuario');
  const [perfil, elegirPerfil] = useState('');
  const [persona, elegirPersona] = useState('');
  const [modo, elegirModo] = useState('nueva');
  const [version, elegirVersion] = useState('');
  const [evidencia, indicar] = useState('');
  const [contrastada, contrastar] = useState(false);
  const [error, fallar] = useState(null);
  const [aviso, avisar] = useState('');
  const [ocupado, ocupar] = useState(false);
  async function enviar(e) {
    e.preventDefault(); if (ocupado || !contrastada) return;
    ocupar(true); fallar(null); avisar('');
    try { await guardar('/identidad/', { persona: persona ? Number(persona) : null, ...(persona ? { version_persona: Number(version) } : {}), tipo, perfil: Number(perfil), evidencia, identidad_contrastada: true }); lista.recargar(); avisar('Enlace acreditado. Los registros originales conservan su identidad e historial.'); elegirPerfil(''); indicar(''); contrastar(false); }
    catch (err) { fallar(err); } finally { ocupar(false); }
  }
  async function revocar(enlace) {
    if (ocupado || !window.confirm('¿Confirmas revocar este enlace? Se conservará su historial.')) return;
    ocupar(true); fallar(null);
    try { await guardar(`/identidad/${enlace.id}/revocar/`, { version: enlace.version }); lista.recargar(); }
    catch (err) { fallar(err); } finally { ocupar(false); }
  }
  return <section className="gestion"><h1>Identidad institucional</h1>
    <p>Acredita que registros existentes corresponden a una misma persona. No se fusionan por nombre o correo. Este enlace no habilita consultas de menores ni autorizaciones audiovisuales.</p>
    <ErrorGestion error={error || lista.error} />{aviso && <p role="status">{aviso}</p>}
    <form onSubmit={enviar} className="formulario-gestion"><fieldset disabled={ocupado}>
      <legend>Acreditar enlace de identidad</legend>
      <Campo etiqueta="Tipo de registro" nombre="tipo-identidad" valor={tipo} cambiar={(v) => { elegirTipo(v); elegirPerfil(''); }} opciones={[['usuario', 'Cuenta'], ['deportista', 'Deportista'], ['acudiente', 'Acudiente']]} />
      <SelectorCatalogo key={tipo} etiqueta="Registro existente" nombre="perfil-identidad" valor={perfil} cambiar={elegirPerfil} etiquetaRegistro={(r) => r.username || [r.nombres,r.apellidos].filter(Boolean).join(" ")} ruta={tipo === 'usuario' ? '/usuarios/' : tipo === 'deportista' ? '/deportistas/' : '/acudientes/'} />
      <Campo etiqueta="Identidad institucional" nombre="modo-identidad" valor={modo} cambiar={(v) => { elegirModo(v); elegirPersona(''); elegirVersion(''); }} opciones={[["nueva","Crear identidad acreditada"],["existente","Enlazar con persona existente"]]} />
      {modo === 'existente' && <SelectorCatalogo etiqueta="Persona institucional existente" nombre="persona-identidad" ruta="/personas-institucionales/" valor={persona} cambiar={(id,r) => { elegirPersona(id); elegirVersion(r?.version || ''); }} />}
      <Campo etiqueta="Referencia privada de verificación" nombre="evidencia-identidad" valor={evidencia} cambiar={indicar} maxLength={36} />
      <label><input type="checkbox" checked={contrastada} onChange={(e) => contrastar(e.target.checked)} />He contrastado la identidad y la evidencia que respalda este enlace</label>
      <button disabled={!contrastada || !perfil || !evidencia || ocupado || (modo === 'existente' && !persona)}>Acreditar enlace</button>
    </fieldset></form>
    <ul>{lista.datos.results.map((e) => <li key={e.id}>Persona {e.persona} · versión {e.version_persona} · enlace {e.id}: {e.usuario ? 'cuenta' : e.deportista ? 'deportista' : 'acudiente'} · {e.vigente ? 'Vigente' : 'Revocado'} {e.vigente && <button disabled={ocupado} onClick={() => revocar(e)}>Revocar enlace {e.id}</button>}</li>)}</ul><PieListado listado={lista} />
  </section>;
}
