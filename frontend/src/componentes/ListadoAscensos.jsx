import { useState } from 'react';
import { Campo, ErrorGestion, PieListado, useListado } from './Gestion.jsx';
import { RevisionAscenso } from './RevisionAscenso.jsx';
import { EjecucionAscenso } from './EjecucionAscenso.jsx';

export function ListadoAscensos({ coordinacion = false, administracion = false }) {
  const [seleccion, seleccionar] = useState(null);
  const [ejecucion, ejecutar] = useState(null);
  const [estado, cambiarEstado] = useState('');
  const lista = useListado('/ascensos/?' + new URLSearchParams(estado ? { estado_decision: estado } : {}), { permitirBusqueda: false });
  return <section aria-label="Ascensos institucionales">
    <h2>Ascensos institucionales</h2>
    <p>{coordinacion ? 'Revisión institucional del coordinador.' : administracion ? 'Consulta y ejecución administrativa autorizada.' : 'Propuestas pedagógicas propias.'} Una aprobación no equivale a un traslado; cada reubicación exige revisión administrativa y comprobación de instalación.</p>
    {coordinacion && seleccion !== null && <RevisionAscenso key={seleccion} id={seleccion} cerrar={() => seleccionar(null)} actualizada={lista.recargar} />}
    {(coordinacion || administracion) && ejecucion !== null && <EjecucionAscenso formalizar={administracion} key={ejecucion} id={ejecucion} cerrar={() => ejecutar(null)} actualizada={lista.recargar} />}
    <Campo etiqueta="Filtrar decisión de ascenso" nombre="estado-ascenso" requerido={false} valor={estado}
      cambiar={(v) => { cambiarEstado(v); lista.cambiarPagina(1); }}
      opciones={['pendiente', 'aprobada', 'rechazada'].map((v) => [v, v])} />
    <button type="button" className="boton-secundario" disabled={lista.cargando} onClick={lista.recargar}>Actualizar ascensos institucionales</button>
    <ErrorGestion error={lista.error} />
    {lista.cargando && <p role="status">Cargando ascensos institucionales…</p>}
    {!lista.cargando && !lista.error && !lista.datos.count && <p>No hay propuestas institucionales para esta consulta.</p>}
    <div className="tabla-contenedor"><table aria-label="Propuestas de ascenso institucional"><thead><tr>
      <th>Deportista y disciplina</th><th>Niveles y referencia</th><th>Justificación</th><th>Decisión pedagógica</th><th>Plan administrativo</th>{coordinacion && <th>Revisión</th>}{(coordinacion || administracion) && <th>Administración</th>}
    </tr></thead><tbody>{lista.datos.results.map((p) => <tr key={'ascenso:' + p.id}>
      <td>{p.nombre_deportista}<br />{p.disciplina_nombre}</td>
      <td>{p.nivel_origen_nombre} → {p.nivel_destino_nombre}<br />{p.periodo_nombre}</td>
      <td>{p.justificacion}</td><td>{p.estado_decision}</td><td>{p.estado_plan}</td>
      {coordinacion && <td>Profesor: {p.profesor_proponente?.nombre || 'No disponible'}<br />{p.creado_en}<br /><button type="button" onClick={() => seleccionar(p.id)}>Revisar ascenso {p.id}</button></td>}
      {(coordinacion || administracion) && <td><button type="button" onClick={() => ejecutar(p.id)}>Reubicaciones del ascenso {p.id}</button></td>}
    </tr>)}</tbody></table></div>
    <nav aria-label="Paginación de ascensos institucionales"><PieListado listado={lista} /></nav>
  </section>;
}
