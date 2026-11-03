import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar, todas } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, BarraListado, PieListado, BotonesFormulario } from '../componentes/Gestion.jsx';

export const dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
export function Grupos() {
  const { usuario } = usarAutenticacion();
  const administra = ['administrador', 'coordinador'].includes(usuario.rol);
  const [parametros] = useSearchParams();
  const consulta = new URLSearchParams();
  for (const campo of ['profesor', 'activo', 'periodo', 'disciplina', 'nivel']) {
    if (parametros.has(campo)) consulta.set(campo, parametros.get(campo));
  }
  const listado = useListado('/organizacion/grupos/' + (consulta.size ? '?' + consulta : ''));
  const [catalogos, cambiarCatalogos] = useState({ disciplinas: [], niveles: [], periodos: [] });
  const [formulario, cambiarFormulario] = useState(null);
  const [detalle, cambiarDetalle] = useState(null);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  useEffect(() => {
    if (!administra) return;
    let vigente = true;
    Promise.all(['disciplinas', 'niveles', 'periodos'].map((ruta) => todas('/organizacion/' + ruta + '/')))
      .then(([disciplinas, niveles, periodos]) => { if (vigente) cambiarCatalogos({ disciplinas, niveles, periodos }); })
      .catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [administra]);
  const campo = (nombre) => (valor) => cambiarFormulario({ ...formulario, [nombre]: valor, ...(nombre === 'disciplina' ? { nivel: '' } : {}) });
  function horario(indice, nombre, valor) {
    cambiarFormulario({ ...formulario, horarios: formulario.horarios.map((h, i) => i === indice ? { ...h, [nombre]: valor } : h) });
  }
  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm('¿Confirmas los datos y horarios de este grupo?')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      const datos = { codigo: formulario.codigo, nombre: formulario.nombre, disciplina: Number(formulario.disciplina), nivel: Number(formulario.nivel),
        periodo: Number(formulario.periodo), cupo_maximo: Number(formulario.cupo_maximo), activo: formulario.activo,
        horarios: formulario.horarios.map((h) => ({ dia: Number(h.dia), hora_inicio: h.hora_inicio, hora_fin: h.hora_fin })) };
      await guardar('/organizacion/grupos/' + (formulario.id ? formulario.id + '/' : ''), datos, formulario.id ? 'PATCH' : 'POST');
      cambiarFormulario(null); cambiarDetalle(null); listado.recargar(); cambiarAviso('Grupo guardado correctamente.');
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }

  return <section className="gestion"><h1>{administra ? 'Grupos deportivos' : 'Mis grupos'}</h1>
    <p>{administra ? 'Organiza los grupos, cupos y horarios de entrenamiento.' : 'Consulta los grupos correspondientes a tus asignaciones vigentes.'}</p>
    <ErrorGestion error={error} />{aviso && <p className="aviso" role="status">{aviso}</p>}
    <BarraListado listado={listado}>{administra && <button onClick={() => cambiarFormulario({ codigo: '', nombre: '', disciplina: '', nivel: '', periodo: '', cupo_maximo: 12, activo: true, horarios: [{ dia: 0, hora_inicio: '', hora_fin: '' }] })}>Crear grupo</button>}</BarraListado>
    {formulario && <form className="formulario-gestion" onSubmit={enviar} aria-label="Formulario de grupo"><h2>{formulario.id ? 'Editar grupo' : 'Nuevo grupo'}</h2>
      <div className="rejilla-formulario">
        <Campo etiqueta="Código del grupo" nombre="codigo" valor={formulario.codigo} cambiar={campo('codigo')} maxLength={40} pattern="[a-zA-Z0-9_-]+" />
        <Campo etiqueta="Nombre del grupo" nombre="nombre" valor={formulario.nombre} cambiar={campo('nombre')} maxLength={120} />
        <Campo etiqueta="Disciplina" nombre="disciplina" valor={formulario.disciplina} cambiar={campo('disciplina')} opciones={catalogos.disciplinas.map((d) => [d.id, d.nombre + (d.activo ? '' : ' (inactiva)')])} />
        <Campo etiqueta="Nivel" nombre="nivel" valor={formulario.nivel} cambiar={campo('nivel')} opciones={catalogos.niveles.filter((n) => n.disciplina === Number(formulario.disciplina)).map((n) => [n.id, n.nombre + (n.activo ? '' : ' (inactivo)')])} />
        <Campo etiqueta="Periodo" nombre="periodo" valor={formulario.periodo} cambiar={campo('periodo')} opciones={catalogos.periodos.map((p) => [p.id, p.nombre + (p.activo ? '' : ' (inactivo)')])} />
        <Campo etiqueta="Cupo máximo" nombre="cupo_maximo" tipo="number" min="1" max="32767" valor={formulario.cupo_maximo} cambiar={campo('cupo_maximo')} />
        <label className="campo-checkbox"><input type="checkbox" checked={formulario.activo} onChange={(e) => cambiarFormulario({ ...formulario, activo: e.target.checked })} />Grupo activo</label>
      </div><h3>Horarios de entrenamiento</h3><p>La duración se calcula a partir de las horas. Las franjas deben terminar el mismo día.</p>
      {formulario.horarios.map((h, i) => <fieldset className="fila-horario" key={i}><legend>Horario {i + 1}</legend>
        <Campo etiqueta="Día" nombre={'dia-' + i} valor={h.dia} cambiar={(v) => horario(i, 'dia', v)} opciones={dias.map((d, n) => [n, d])} />
        <Campo etiqueta="Hora de inicio" nombre={'inicio-' + i} tipo="time" step="60" valor={h.hora_inicio} cambiar={(v) => horario(i, 'hora_inicio', v)} />
        <Campo etiqueta="Hora de finalización" nombre={'fin-' + i} tipo="time" step="60" valor={h.hora_fin} cambiar={(v) => horario(i, 'hora_fin', v)} />
        <button type="button" className="boton-secundario" disabled={formulario.horarios.length <= 1} onClick={() => cambiarFormulario({ ...formulario, horarios: formulario.horarios.filter((_, n) => n !== i) })}>Quitar horario {i + 1}</button>
      </fieldset>)}
      <button type="button" className="boton-secundario" onClick={() => cambiarFormulario({ ...formulario, horarios: [...formulario.horarios, { dia: 0, hora_inicio: '', hora_fin: '' }] })}>Agregar horario</button>
      <BotonesFormulario enviando={enviando} cancelar={() => cambiarFormulario(null)} />
    </form>}
    {detalle && <section className="detalle-grupo"><h2>{detalle.nombre}</h2>
      <dl><dt>Código</dt><dd>{detalle.codigo}</dd><dt>Disciplina / nivel</dt><dd>{detalle.disciplina_nombre} / {detalle.nivel_nombre}</dd>
        <dt>Periodo</dt><dd>{detalle.periodo_nombre}</dd><dt>Cupo máximo</dt><dd>{detalle.cupo_maximo}</dd><dt>Estado</dt><dd>{detalle.activo ? 'Activo' : 'Inactivo'}</dd></dl>
      <h3>Horarios</h3><ul>{detalle.horarios.map((h, i) => <li key={h.id || i}>{dias[h.dia]} · {h.hora_inicio.slice(0, 5)}–{h.hora_fin.slice(0, 5)} · {h.duracion_minutos} minutos</li>)}</ul>
      <Link to={rutaDelRol(usuario.rol) + '/asignaciones?grupo=' + detalle.id}>Ver asignaciones autorizadas</Link>
      <button className="boton-secundario" onClick={() => cambiarDetalle(null)}>Cerrar detalle</button>
    </section>}
    <div className="tabla-contenedor"><table><thead><tr><th>Código</th><th>Grupo</th><th>Nivel / periodo</th><th>Cupo</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>{listado.datos.results.map((grupo) => <tr key={grupo.id}><td>{grupo.codigo}</td><td>{grupo.nombre}</td><td>{grupo.nivel_nombre}<br />{grupo.periodo_nombre}</td><td>{grupo.cupo_maximo}</td><td>{grupo.activo ? 'Activo' : 'Inactivo'}</td>
        <td className="acciones"><button className="boton-secundario" onClick={() => cambiarDetalle(grupo)}>Ver {grupo.codigo}</button>
          {administra && <button className="boton-secundario" onClick={() => cambiarFormulario({ ...grupo, horarios: grupo.horarios.map((h) => ({ ...h })) })}>Editar {grupo.codigo}</button>}</td></tr>)}</tbody>
    </table></div><PieListado listado={listado} />
  </section>;
}
