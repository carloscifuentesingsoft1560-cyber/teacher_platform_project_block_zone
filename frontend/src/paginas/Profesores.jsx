import { Link, useSearchParams } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { useListado, BarraListado, PieListado } from '../componentes/Gestion.jsx';
import { dias } from './Grupos.jsx';

export function Profesores() {
  const { usuario } = usarAutenticacion();
  const [parametros] = useSearchParams();
  const consulta = new URLSearchParams();
  for (const campo of ['activo', 'sin_grupo', 'fecha', 'periodo', 'disciplina', 'nivel']) {
    if (parametros.has(campo)) consulta.set(campo, parametros.get(campo));
  }
  const listado = useListado('/organizacion/profesores/' + (consulta.size ? '?' + consulta : ''));
  const base = rutaDelRol(usuario.rol);
  return <section className="gestion"><h1>Profesores de la escuela</h1>
    <p>Toda la plantilla docente, incluidos profesores sin grupo e inactivos. Los grupos y horarios mostrados corresponden a sus asignaciones vigentes actuales.</p>
    <BarraListado listado={listado} />
    <div className="tabla-contenedor"><table><thead><tr><th>Nombre</th><th>Usuario</th><th>Estado</th><th>Grupos y horarios</th><th>Consulta</th></tr></thead><tbody>
      {listado.datos.results.map((p) => <tr key={p.id}><td>{p.nombre}</td><td>{p.username}</td><td>{p.is_active === false ? 'Inactivo' : 'Activo'}</td>
        <td>{p.grupos?.length ? p.grupos.map((g) => <div key={g.id}><strong>{g.nombre}</strong>
          <ul>{g.horarios.map((h) => <li key={h.id}>{dias[h.dia]} · {h.hora_inicio.slice(0, 5)}–{h.hora_fin.slice(0, 5)}</li>)}</ul>
        </div>) : 'Sin grupos vigentes'}</td>
        <td><Link to={base + '/grupos?profesor=' + p.id}>Consultar grupos</Link></td>
      </tr>)}
    </tbody></table></div><PieListado listado={listado} />
  </section>;
}
