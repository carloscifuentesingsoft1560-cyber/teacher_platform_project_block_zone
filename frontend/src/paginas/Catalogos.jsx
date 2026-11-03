import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { guardar, todas } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, BarraListado, PieListado, BotonesFormulario } from '../componentes/Gestion.jsx';

const nombres = { disciplinas: 'Disciplinas', niveles: 'Niveles', periodos: 'Periodos' };
export function Catalogos() {
  const [parametros] = useSearchParams();
  const [tipo, cambiarTipo] = useState(() => Object.hasOwn(nombres, parametros.get('tipo')) ? parametros.get('tipo') : 'disciplinas');
  const [formulario, cambiarFormulario] = useState(null);
  const [disciplinas, cambiarDisciplinas] = useState([]);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  const listado = useListado('/organizacion/' + tipo + '/' + (tipo === 'periodos' && parametros.get('periodo') ? '?id=' + encodeURIComponent(parametros.get('periodo')) : ''));
  useEffect(() => {
    let vigente = true;
    todas('/organizacion/disciplinas/').then((r) => { if (vigente) cambiarDisciplinas(r); }).catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [tipo, aviso]);
  const campo = (nombre) => (valor) => cambiarFormulario({ ...formulario, [nombre]: valor });
  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm('¿Confirmas los cambios del catálogo?')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      const datos = { ...formulario };
      delete datos.id; delete datos.disciplina_nombre;
      if (tipo === 'niveles') { datos.disciplina = Number(datos.disciplina); datos.orden = Number(datos.orden); }
      await guardar('/organizacion/' + tipo + '/' + (formulario.id ? formulario.id + '/' : ''), datos, formulario.id ? 'PATCH' : 'POST');
      cambiarFormulario(null); listado.recargar(); cambiarAviso('Catálogo guardado correctamente.');
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }

  return <section className="gestion"><h1>Catálogos deportivos</h1><p>Disciplinas, niveles y ciclos de formación configurables.</p>
    <div className="pestanas" role="group" aria-label="Tipo de catálogo">{Object.entries(nombres).map(([id, texto]) =>
      <button key={id} className={id === tipo ? '' : 'boton-secundario'} aria-pressed={id === tipo} onClick={() => { cambiarTipo(id); cambiarFormulario(null); cambiarError(null); listado.cambiarPagina(1); }}>{texto}</button>)}</div>
    <h2>{nombres[tipo]}</h2><ErrorGestion error={error} />{aviso && <p className="aviso" role="status">{aviso}</p>}
    <BarraListado listado={listado}><button onClick={() => cambiarFormulario({ codigo: '', nombre: '', activo: true, ...(tipo === 'niveles' ? { disciplina: '', orden: 0 } : {}), ...(tipo === 'periodos' ? { fecha_inicio: '', fecha_fin: '' } : {}) })}>Crear registro</button></BarraListado>
    {formulario && <form className="formulario-gestion" onSubmit={enviar} aria-label="Formulario de catálogo"><h2>{formulario.id ? 'Editar registro' : 'Nuevo registro'}</h2>
      <div className="rejilla-formulario">
        <Campo etiqueta="Código" nombre="codigo" valor={formulario.codigo} cambiar={campo('codigo')} maxLength={40} pattern="[a-zA-Z0-9_-]+" />
        <Campo etiqueta="Nombre" nombre="nombre" valor={formulario.nombre} cambiar={campo('nombre')} maxLength={tipo === 'niveles' ? 140 : 100} />
        {tipo === 'niveles' && <><Campo etiqueta="Disciplina" nombre="disciplina" valor={formulario.disciplina} cambiar={campo('disciplina')} opciones={disciplinas.map((d) => [d.id, d.nombre + (d.activo ? '' : ' (inactiva)')])} />
          <Campo etiqueta="Orden" nombre="orden" tipo="number" min="0" max="32767" valor={formulario.orden} cambiar={campo('orden')} /></>}
        {tipo === 'periodos' && <><Campo etiqueta="Fecha de inicio" nombre="fecha_inicio" tipo="date" valor={formulario.fecha_inicio} cambiar={campo('fecha_inicio')} />
          <Campo etiqueta="Fecha de finalización" nombre="fecha_fin" tipo="date" min={formulario.fecha_inicio} valor={formulario.fecha_fin} cambiar={campo('fecha_fin')} /></>}
        <label className="campo-checkbox"><input type="checkbox" checked={formulario.activo} onChange={(e) => cambiarFormulario({ ...formulario, activo: e.target.checked })} />Registro activo</label>
      </div><BotonesFormulario enviando={enviando} cancelar={() => cambiarFormulario(null)} />
    </form>}
    <div className="tabla-contenedor"><table><thead><tr><th>Código</th><th>Nombre</th>{tipo === 'niveles' && <th>Disciplina</th>}{tipo === 'periodos' && <th>Vigencia</th>}<th>Estado</th><th>Acciones</th></tr></thead><tbody>
      {listado.datos.results.map((r) => <tr key={r.id}><td>{r.codigo}</td><td>{r.nombre}</td>{tipo === 'niveles' && <td>{r.disciplina_nombre}</td>}{tipo === 'periodos' && <td>{r.fecha_inicio} — {r.fecha_fin}</td>}<td>{r.activo ? 'Activo' : 'Inactivo'}</td><td><button className="boton-secundario" onClick={() => cambiarFormulario({ ...r })}>Editar {r.codigo}</button></td></tr>)}
    </tbody></table></div><PieListado listado={listado} />
  </section>;
}
