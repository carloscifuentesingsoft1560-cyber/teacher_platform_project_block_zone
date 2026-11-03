import { useEffect, useState } from 'react';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar, todas } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, PieListado } from '../componentes/Gestion.jsx';

export function Coordinacion() {
  const { usuario } = usarAutenticacion();
  const listado = useListado('/organizacion/coordinacion/');
  const [cuentas, cambiarCuentas] = useState([]);
  const [seleccion, cambiarSeleccion] = useState('');
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  useEffect(() => {
    let vigente = true;
    todas('/usuarios/').then((r) => { if (vigente) cambiarCuentas(r); }).catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [aviso]);
  const actual = listado.datos.actual;
  async function relevar(e) {
    e.preventDefault();
    if (enviando || !window.confirm(actual ? '¿Confirmas el relevo? Se retirará el cargo al saliente y se conservarán sus otras facultades e historial.' : '¿Confirmas la designación del coordinador?')) return;
    cambiarEnviando(true); cambiarError(null); cambiarAviso('');
    try {
      await guardar('/organizacion/coordinacion/relevar/', { usuario: Number(seleccion), coordinador_actual: actual?.id || null });
      cambiarAviso('Coordinación actualizada. Se conservó el historial.'); cambiarSeleccion(''); listado.recargar();
    } catch (fallo) { cambiarError(fallo); if (fallo.estado === 409) listado.recargar(); }
    finally { cambiarEnviando(false); }
  }
  return <section className="gestion"><h1>Coordinación: cargo e historial</h1><p>Un único coordinador activo para toda la escuela. Solo administración autoriza el relevo.</p>
    <ErrorGestion error={error || listado.error} />{aviso && <p className="aviso" role="status">{aviso}</p>}
    <h2>Coordinador actual</h2><p>{listado.cargando ? 'Consultando…' : actual?.nombre || 'Vacante'}</p>
    <form className="formulario-gestion" onSubmit={relevar}>
      <Campo etiqueta="Persona entrante" nombre="coordinador-entrante" valor={seleccion} cambiar={cambiarSeleccion}
        opciones={cuentas.filter((c) => c.id !== usuario.id && c.id !== actual?.id && c.is_active).map((c) => [c.id, [c.first_name, c.last_name].filter(Boolean).join(' ') || c.username])} />
      <p>El relevo conserva la docencia y otras facultades vigentes. Si el saliente no conserva ninguna facultad, su cuenta quedará inactiva.</p>
      <button disabled={enviando || listado.cargando || !!listado.error}>{enviando ? 'Guardando…' : actual ? 'Confirmar relevo' : 'Designar coordinador'}</button>
    </form>
    <h2>Historial del cargo</h2>
    <p>Se conserva la persona y el administrador que autorizó cada inicio o finalización. Si no existe un evento inicial, no se inventa una fecha.</p>
    <div className="tabla-contenedor"><table><thead><tr><th>Fecha (Bogotá)</th><th>Evento</th><th>Persona</th><th>Autorizado por</th></tr></thead><tbody>
      {listado.datos.results.map((e) => <tr key={e.id}><td>{new Date(e.fecha).toLocaleString('es-CO', { timeZone: 'America/Bogota' })}</td><td>{e.accion === 'coordinacion_inicio' ? 'Inicio' : 'Finalización'}</td><td>{e.nombre}</td><td>{e.autorizado_por}</td></tr>)}
    </tbody></table></div><PieListado listado={listado} />
  </section>;
}
