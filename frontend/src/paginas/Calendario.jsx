import { useEffect, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { fechaBogota } from '../api/gestion.js';
import { Campo, ErrorGestion } from '../componentes/Gestion.jsx';

export function Calendario() {
  const [desde, cambiarDesde] = useState(fechaBogota);
  const [hasta, cambiarHasta] = useState(() => {
    const fecha = new Date(fechaBogota() + 'T12:00:00Z'); fecha.setUTCDate(fecha.getUTCDate() + 30); return fecha.toISOString().slice(0, 10);
  });
  const [consulta, cambiarConsulta] = useState(null);
  const [eventos, cambiarEventos] = useState([]);
  const [error, cambiarError] = useState(null);
  const [cargando, cambiarCargando] = useState(true);
  useEffect(() => {
    let vigente = true;
    cambiarCargando(true); cambiarError(null);
    const filtros = consulta || { desde, hasta };
    solicitar('/organizacion/calendario/?' + new URLSearchParams(filtros))
      .then((r) => { if (vigente) cambiarEventos(r.eventos); })
      .catch((e) => { if (vigente) { cambiarError(e); cambiarEventos([]); } })
      .finally(() => { if (vigente) cambiarCargando(false); });
    return () => { vigente = false; };
  }, [consulta]);
  return <section className="gestion"><h1>Calendario de entrenamientos</h1>
    <p>Horarios recurrentes en America/Bogota según la vigencia de tus asignaciones. Aún no se crean sesiones de clase.</p>
    <form className="filtros-calendario" onSubmit={(e) => { e.preventDefault(); cambiarConsulta({ desde, hasta }); }}>
      <Campo etiqueta="Desde" nombre="desde" tipo="date" valor={desde} cambiar={cambiarDesde} />
      <Campo etiqueta="Hasta" nombre="hasta" tipo="date" min={desde} valor={hasta} cambiar={cambiarHasta} />
      <button disabled={cargando}>Consultar calendario</button>
    </form><ErrorGestion error={error} />
    {cargando ? <p role="status">Cargando calendario…</p> : !error && !eventos.length && <p>No hay entrenamientos programados en este rango.</p>}
    <div className="tabla-contenedor"><table><thead><tr><th>Fecha</th><th>Grupo</th><th>Horario</th><th>Duración</th></tr></thead><tbody>
      {eventos.map((e) => <tr key={e.id}><td>{e.fecha}</td><td>{e.grupo_nombre}</td><td>{e.hora_inicio}–{e.hora_fin}</td><td>{e.duracion_minutos} minutos</td></tr>)}
    </tbody></table></div>
  </section>;
}
