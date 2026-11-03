import { useState } from 'react';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar } from '../api/gestion.js';
import { useListado, BarraListado, PieListado, Campo } from '../componentes/Gestion.jsx';
import { FormularioRegistro } from '../componentes/FormularioRegistro.jsx';
import { FormularioPropuesta } from '../componentes/FormularioPropuesta.jsx';
import { ListadoAscensos } from '../componentes/ListadoAscensos.jsx';

export function Propuestas() {
  const { usuario } = usarAutenticacion();
  const profesor = usuario.rol === 'profesor';
  const [estado, cambiarEstado] = useState('');
  const lista = useListado('/propuestas/?' + new URLSearchParams(estado ? { estado } : {}));
  const [formulario, cambiarFormulario] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [revisionAscensos, cambiarRevisionAscensos] = useState(0);
  async function enviar(datos) {
    await guardar('/propuestas/' + formulario.registro.id + '/' + formulario.accion + '/', { version: formulario.registro.version, resolucion: datos.resolucion });
    cambiarFormulario(null); lista.recargar(); cambiarAviso('Propuesta registrada. Las decisiones quedan auditadas.');
  }
  return <section className="gestion"><h1>Propuestas y decisiones</h1>
    <p>{profesor ? 'Puedes proponer inscripciones adicionales, traslados al mismo nivel y ascensos institucionales para deportistas de tu ámbito. Proponer no ejecuta cambios.' : 'Las propuestas administrativas de inscripción y traslado mantienen sus controles. El mecanismo anterior de cambio de nivel está deshabilitado. El coordinador activo puede revisar ascensos institucionales y decidir pedagógicamente sin ejecutar traslados.'}</p>
    {aviso && <p role="status">{aviso}</p>}<BarraListado listado={lista}>{profesor && <button onClick={() => cambiarFormulario({ accion: 'crear' })}>Crear propuesta</button>}</BarraListado>
    <Campo etiqueta="Filtrar propuestas por estado" nombre="estado-propuesta" requerido={false} valor={estado} cambiar={cambiarEstado} opciones={['pendiente', 'aplicada', 'rechazada', 'cancelada'].map((e) => [e, e])} />
    {formulario?.accion === 'crear' && <FormularioPropuesta cancelar={() => cambiarFormulario(null)} completada={(resultado) => {
      cambiarFormulario(null);
      if (resultado?.modalidad === 'ascenso') {
        cambiarRevisionAscensos((v) => v + 1);
        cambiarAviso('Ascenso institucional propuesto, pendiente de decisión pedagógica. No se modificaron inscripciones ni cupos.');
      } else { lista.recargar(); cambiarAviso('Propuesta registrada sin modificar inscripciones.'); }
    }} />}
    {formulario && formulario.accion !== 'crear' && <FormularioRegistro key={formulario.accion + formulario.registro.id} titulo={'Confirmar ' + formulario.accion} campos={[{ nombre: 'resolucion', etiqueta: 'Resolución motivada', maxLength: 240 }]} guardar={enviar} cancelar={() => cambiarFormulario(null)} />}
    <h2>Inscripciones, traslados e historial anterior</h2>
    <div className="tabla-contenedor"><table aria-label="Propuestas anteriores y administrativas"><thead><tr><th>Propuesta</th><th>Fecha</th><th>Destino / niveles</th><th>Estado y resolución</th><th>Acciones</th></tr></thead><tbody>{lista.datos.results.map((p) => <tr key={'propuesta:' + p.id}>
      <td>{p.tipo} · {p.justificacion}</td><td>{p.fecha_efectiva}<br />Autor: {p.creado_por}</td><td>{p.codigo_destino} · {p.nombre_destino || 'Grupo ' + p.grupo_destino}<br />{p.periodo_destino}<br />{p.nivel_anterior || 'Ubicación inicial'} → {p.nivel_nuevo}</td><td>{p.estado}<br />{p.resolucion}</td>
      <td className="acciones">{(p.tipo === 'nivel' || p.mecanismo_deshabilitado) &&
        <p>{p.aviso_procedimiento || 'Mecanismo anterior de cambio de nivel deshabilitado. Se conserva para revisión administrativa, sin conversión automática.'}</p>}
        {!profesor && p.estado === 'pendiente' && ['aprobar', 'rechazar'].filter((accion) =>
          !(p.tipo === 'nivel' || p.mecanismo_deshabilitado) || (accion === 'rechazar' && usuario.rol === 'coordinador')
        ).map((accion) => <button key={accion} className="boton-secundario" onClick={() => cambiarFormulario({ accion, registro: p })}>{accion} propuesta {p.id}</button>)}
        {p.estado === 'pendiente' && <button className="boton-secundario" onClick={() => cambiarFormulario({ accion: 'cancelar', registro: p })}>Cancelar propuesta {p.id}</button>}
      </td>
    </tr>)}</tbody></table></div><PieListado listado={lista} />
    <ListadoAscensos key={revisionAscensos} coordinacion={usuario.rol === 'coordinador'} administracion={usuario.rol === 'administrador'} />
  </section>;
}
