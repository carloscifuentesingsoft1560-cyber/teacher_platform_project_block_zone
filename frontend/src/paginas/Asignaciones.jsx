import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar, todas, fechaBogota } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, PieListado, BotonesFormulario } from '../componentes/Gestion.jsx';

export function Asignaciones() {
  const { usuario } = usarAutenticacion();
  const administra = ['administrador', 'coordinador'].includes(usuario.rol);
  const [parametros] = useSearchParams();
  const grupoConsulta = parametros.get('grupo');
  const consulta = new URLSearchParams();
  for (const campo of ['grupo', 'estado', 'fecha', 'periodo', 'disciplina', 'nivel']) {
    if (parametros.has(campo)) consulta.set(campo, parametros.get(campo));
  }
  const listado = useListado('/organizacion/asignaciones/' + (consulta.size ? '?' + consulta : ''));
  const [grupos, cambiarGrupos] = useState([]);
  const [usuarios, cambiarUsuarios] = useState([]);
  const [formulario, cambiarFormulario] = useState(null);
  const [finalizar, cambiarFinalizar] = useState(null);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  useEffect(() => {
    if (!administra) return;
    let vigente = true;
    Promise.all([todas('/organizacion/grupos/'), todas(usuario.rol === 'administrador' ? '/usuarios/' : '/organizacion/profesores/')]).then(([g, u]) => {
      if (vigente) { cambiarGrupos(g); cambiarUsuarios(u); }
    }).catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [administra]);
  const campo = (nombre) => (valor) => cambiarFormulario({ ...formulario, [nombre]: valor, ...(nombre === 'tipo' ? { usuario: '' } : {}) });
  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm(finalizar ? '¿Confirmas la finalización de esta asignación?' : '¿Confirmas esta asignación y su vigencia?')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      if (finalizar) await guardar('/organizacion/asignaciones/' + finalizar.id + '/finalizar/', { fecha_fin: finalizar.fecha_fin });
      else await guardar('/organizacion/asignaciones/', { ...formulario, usuario: Number(formulario.usuario), grupo: Number(formulario.grupo), fecha_fin: formulario.fecha_fin || null });
      cambiarFormulario(null); cambiarFinalizar(null); listado.recargar(); cambiarAviso('Asignación guardada. El historial se conserva.');
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }
  const hoy = fechaBogota();
  return <section className="gestion"><h1>Asignaciones</h1><p>{administra ? 'Responsabilidades con fechas de inicio y finalización. Las fechas finales son inclusivas.' : 'Tus asignaciones vigentes.'}</p>
    <ErrorGestion error={error || listado.error} />{aviso && <p className="aviso" role="status">{aviso}</p>}
    {administra && <button onClick={() => { cambiarFinalizar(null); cambiarFormulario({ grupo: grupoConsulta || '', usuario: '', tipo: 'profesor', fecha_inicio: hoy, fecha_fin: '' }); }}>Crear asignación</button>}
    {formulario && <form className="formulario-gestion" onSubmit={enviar} aria-label="Formulario de asignación"><h2>Nueva asignación</h2><div className="rejilla-formulario">
      <Campo etiqueta="Grupo" nombre="grupo" valor={formulario.grupo} cambiar={campo('grupo')} opciones={grupos.filter((g) => g.activo).map((g) => [g.id, g.codigo + ' · ' + g.nombre])} />
      <Campo etiqueta="Responsabilidad" nombre="tipo" valor={formulario.tipo} cambiar={campo('tipo')} opciones={[['profesor', 'Profesor']]} />
      <Campo etiqueta="Persona" nombre="usuario" valor={formulario.usuario} cambiar={campo('usuario')} opciones={usuarios.filter((u) => u.is_active && u.rol === formulario.tipo).map((u) => [u.id, u.nombre || [u.first_name, u.last_name].filter(Boolean).join(' ') || u.username])} />
      <Campo etiqueta="Fecha de inicio" nombre="fecha_inicio" tipo="date" valor={formulario.fecha_inicio} cambiar={campo('fecha_inicio')} />
      <Campo etiqueta="Fecha final (opcional)" nombre="fecha_fin" tipo="date" min={formulario.fecha_inicio} valor={formulario.fecha_fin} cambiar={campo('fecha_fin')} requerido={false} />
    </div><p>Una fecha final vacía limita la asignación al final del periodo. Los cruces de horario de profesores se verifican en servidor.</p>
      <BotonesFormulario enviando={enviando} cancelar={() => cambiarFormulario(null)} /></form>}
    {finalizar && <form className="formulario-gestion" onSubmit={enviar}><h2>Finalizar asignación</h2>
      <p>{finalizar.usuario_nombre} · {finalizar.grupo_nombre}</p>
      <Campo etiqueta="Fecha de finalización" nombre="finalizar-fecha" tipo="date" min={finalizar.fecha_inicio} valor={finalizar.fecha_fin} cambiar={(v) => cambiarFinalizar({ ...finalizar, fecha_fin: v })} />
      <BotonesFormulario texto="Confirmar finalización" enviando={enviando} cancelar={() => cambiarFinalizar(null)} /></form>}
    {listado.cargando && <p role="status">Cargando asignaciones…</p>}
    {!listado.cargando && !listado.datos.count && <p>No hay asignaciones para esta consulta.</p>}
    <div className="tabla-contenedor"><table><thead><tr><th>Persona</th><th>Responsabilidad</th><th>Grupo</th><th>Inicio</th><th>Finalización</th>{administra && <th>Acciones</th>}</tr></thead>
      <tbody>{listado.datos.results.map((a) => <tr key={a.id}><td>{a.usuario_nombre}</td><td>{a.tipo === 'profesor' ? 'Profesor' : 'Coordinador'}</td><td>{a.grupo_nombre}</td><td>{a.fecha_inicio}</td><td>{a.fecha_fin || 'Hasta fin del periodo'}</td>
        {administra && <td><button className="boton-secundario" disabled={!!a.fecha_fin && a.fecha_fin < hoy} onClick={() => { cambiarFormulario(null); cambiarFinalizar({ ...a, fecha_fin: hoy >= a.fecha_inicio ? hoy : a.fecha_inicio }); }}>Finalizar {a.usuario_nombre}</button></td>}</tr>)}</tbody>
    </table></div><PieListado listado={listado} />
  </section>;
}
