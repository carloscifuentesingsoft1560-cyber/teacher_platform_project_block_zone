import { useEffect, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion } from './Gestion.jsx';

export const opcionesRoles = ['profesor', 'coordinador', 'administrador', 'routesetter', 'deportista', 'acudiente'].map((r) => [r, r[0].toUpperCase() + r.slice(1)]);

export function RolesCuenta({ cuenta, cerrar, actualizada }) {
  const [roles, cambiar] = useState([]);
  const [rol, elegir] = useState('');
  const [motivo, motivar] = useState('');
  const [error, fallar] = useState(null);
  const [ocupado, ocupar] = useState(false);
  async function cargar() { cambiar(await solicitar(`/usuarios/${cuenta.id}/roles/`)); }
  useEffect(() => { let vivo = true; solicitar(`/usuarios/${cuenta.id}/roles/`).then((r) => { if (vivo) cambiar(r); }).catch((e) => { if (vivo) fallar(e); }); return () => { vivo = false; }; }, [cuenta.id]);
  async function operar(datos, revocacion = false) {
    if (ocupado || !motivo.trim()) return;
    if (!window.confirm(revocacion ? '¿Confirmas revocar esta facultad? El historial se conservará.' : '¿Confirmas otorgar esta facultad institucional?')) return;
    ocupar(true); fallar(null);
    try { await guardar(`/usuarios/${cuenta.id}/${revocacion ? 'revocar-rol' : 'roles'}/`, { ...datos, motivo: motivo.trim() }); await cargar(); actualizada(); elegir(''); motivar(''); }
    catch (e) { fallar(e); }
    finally { ocupar(false); }
  }
  return <section className="formulario-gestion" aria-label="Facultades de la cuenta">
    <h2>Facultades de {cuenta.username}</h2><ErrorGestion error={error} />
    <p>La revocación conserva el historial. El cargo de coordinador se cambia mediante el relevo institucional.</p>
    <p>Una cuenta sin facultades queda inactiva. Para reactivarla, asigna primero una facultad explícita; sus permisos revocados no se restauran automáticamente.</p>
    <label>Motivo del cambio<textarea maxLength={240} value={motivo} onChange={(e) => motivar(e.target.value)} disabled={ocupado} /></label>
    <ul>{roles.map((r) => <li key={r.id}>{r.rol} · {r.vigente ? 'Vigente' : 'Revocado'} · versión {r.version} {r.vigente && <button disabled={ocupado || !motivo.trim()} onClick={() => operar({ pertenencia: r.id, version: r.version }, true)}>Revocar {r.rol}</button>}</li>)}</ul>
    <form onSubmit={(e) => { e.preventDefault(); operar({ rol }); }}>
      <Campo etiqueta="Facultad adicional" nombre="rol-adicional" valor={rol} cambiar={elegir} opciones={opcionesRoles.filter(([r]) => r !== 'coordinador' && !roles.some((x) => x.rol === r && x.vigente))} disabled={ocupado} />
      <button disabled={ocupado || !rol || !motivo.trim()}>Otorgar facultad</button>
    </form><button onClick={cerrar} disabled={ocupado}>Cerrar facultades</button>
  </section>;
}
