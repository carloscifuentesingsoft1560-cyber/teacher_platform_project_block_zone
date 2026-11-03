import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar, fechaBogota } from '../api/gestion.js';
import { solicitar } from '../api/cliente.js';
import { ErrorGestion, useListado, BarraListado, PieListado, Campo } from '../componentes/Gestion.jsx';
import { FormularioRegistro } from '../componentes/FormularioRegistro.jsx';
import { SelectorCatalogo } from '../componentes/SelectorCatalogo.jsx';

export function Inscripciones() {
  const { usuario } = usarAutenticacion();
  const gestor = usuario.rol !== 'profesor';
  const [parametros, cambiarParametros] = useSearchParams();
  const lista = useListado('/inscripciones/?' + parametros.toString());
  const [formulario, cambiarFormulario] = useState(null);
  const [historial, cambiarHistorial] = useState(null);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [grupoCupo, cambiarGrupoCupo] = useState('');
  const [cupos, cambiarCupos] = useState(null);
  const [cargandoCupos, cambiarCargandoCupos] = useState(false);
  const [errorCupos, cambiarErrorCupos] = useState(null);
  const [revisionCupos, cambiarRevisionCupos] = useState(0);
  useEffect(() => {
    let vigente = true;
    cambiarCupos(null); cambiarErrorCupos(null); cambiarCargandoCupos(false);
    if (!grupoCupo) return;
    cambiarCargandoCupos(true);
    solicitar('/inscripciones/cupos/?grupo=' + grupoCupo).then((r) => { if (vigente) cambiarCupos(r); })
      .catch((e) => { if (vigente) cambiarErrorCupos(e); }).finally(() => { if (vigente) cambiarCargandoCupos(false); });
    return () => { vigente = false; };
  }, [grupoCupo, revisionCupos]);
  const motivo = { nombre: 'motivo', etiqueta: 'Motivo administrativo', maxLength: 240 };
  let campos = formulario?.accion === 'crear' ? [
    { nombre: 'deportista', etiqueta: 'Deportista', ruta: '/deportistas/', numero: true },
    { nombre: 'grupo', etiqueta: 'Grupo', ruta: '/organizacion/grupos/', numero: true },
    { nombre: 'fecha_ingreso', etiqueta: 'Fecha de ingreso', tipo: 'date' }, motivo] : [motivo];
  if (formulario?.accion === 'suspender') campos.push({ nombre: 'fecha_vencimiento', etiqueta: 'Último día autorizado de reserva', tipo: 'date' });
  if (formulario?.accion === 'trasladar') campos.push({ nombre: 'grupo_destino', etiqueta: 'Grupo destino del mismo nivel', ruta: '/organizacion/grupos/', numero: true });
  async function enviar(datos) {
    const crear = formulario.accion === 'crear';
    await guardar('/inscripciones/' + (crear ? '' : formulario.registro.id + '/' + formulario.accion + '/'),
      crear ? datos : { ...datos, version: formulario.registro.version });
    cambiarFormulario(null); cambiarHistorial(null); lista.recargar(); cambiarRevisionCupos((v) => v + 1); cambiarAviso('Operación registrada con historial.');
  }
  async function verHistorial(i) {
    try { cambiarError(null); cambiarHistorial(await solicitar('/inscripciones/' + i.id + '/historial/')); }
    catch (e) { cambiarError(e); }
  }
  async function liberar() {
    if (!window.confirm('¿Procesar las reservas cuyo plazo ya venció?')) return;
    try { const r = await guardar('/inscripciones/liberar-reservas/', {}); lista.recargar(); cambiarRevisionCupos((v) => v + 1); cambiarAviso(r.liberadas + ' reservas liberadas con auditoría.'); }
    catch (e) { cambiarError(e); }
  }
  return <section className="gestion"><h1>Inscripciones e historial</h1><p>Una persona puede participar en varios grupos compatibles. Las reservas vigentes cuentan como ocupación.</p>
    <ErrorGestion error={error} />{aviso && <p role="status">{aviso}</p>}
    <BarraListado listado={lista}>{gestor ? <><button onClick={() => cambiarFormulario({ accion: 'crear' })}>Inscribir deportista</button><button className="boton-secundario" onClick={liberar}>Procesar reservas vencidas</button></> : <Link to={rutaDelRol(usuario.rol) + '/propuestas'}>Proponer inscripción o traslado</Link>}</BarraListado>
    <Campo etiqueta="Filtrar estado de inscripción" nombre="estado-inscripcion" requerido={false} valor={parametros.get('estado') || ''} opciones={['activa', 'suspendida', 'finalizada'].map((e) => [e, e])} cambiar={(v) => { const n = new URLSearchParams(parametros); if (v) n.set('estado', v); else n.delete('estado'); cambiarParametros(n); }} />
    <SelectorCatalogo etiqueta="Grupo para consultar cupos" nombre="grupo-cupo" ruta="/organizacion/grupos/" valor={grupoCupo} cambiar={(v) => cambiarGrupoCupo(v)} />
    <ErrorGestion error={errorCupos} />
    {grupoCupo && <button type="button" className="boton-secundario" disabled={cargandoCupos} onClick={() => cambiarRevisionCupos((v) => v + 1)}>Actualizar cupos</button>}
    {cargandoCupos && <p role="status">Consultando cupos…</p>}
    {cupos && <section aria-label="Cupos del grupo" className="detalle-grupo"><h2>Disponibilidad del grupo</h2>
      <p>Capacidad: {cupos.cupo_maximo}. Corte: {cupos.fecha_corte}.</p>
      <p>Inscripciones activas: {cupos.inscripciones_activas}. Reservas vigentes: {cupos.reservas_vigentes}. Ocupación actual: {cupos.ocupacion_actual}. Disponibles actualmente: {cupos.disponibles_actuales}.</p>
      <p>Del {cupos.desde} al {cupos.hasta}: ocupación máxima {cupos.ocupacion_maxima}; disponibles durante todo ese intervalo: {cupos.disponibles}.</p>
      <p>Las reservas vigentes cuentan como ocupación. Una consulta no reserva plazas; cada inscripción vuelve a validar el cupo.</p>
    </section>}
    {formulario && <FormularioRegistro key={formulario.accion + (formulario.registro?.id || '')} titulo={formulario.accion === 'crear' ? 'Nueva inscripción' : 'Confirmar ' + formulario.accion} campos={campos} inicial={formulario.accion === 'crear' ? { fecha_ingreso: fechaBogota() } : {}} guardar={enviar} cancelar={() => cambiarFormulario(null)} />}
    <div className="tabla-contenedor"><table><thead><tr><th>Deportista</th><th>Grupo / nivel / periodo</th><th>Fechas</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
      {lista.datos.results.map((i) => <tr key={i.id}><td>{i.nombre_deportista}</td><td>{i.nombre_grupo}<br />{i.nivel} · {i.periodo}</td><td>{i.fecha_ingreso} — {i.fecha_salida || 'Fin del periodo'}</td><td>{i.situacion_temporal || i.estado}</td><td className="acciones"><button className="boton-secundario" onClick={() => verHistorial(i)}>Historial de inscripción {i.id}</button>
        {gestor && !['finalizada', 'periodo_finalizado', 'reserva_vencida', 'programada'].includes(i.situacion_temporal || i.estado) && [i.estado === 'activa' ? 'suspender' : 'reanudar', 'retirar', ...(i.estado === 'activa' ? ['trasladar'] : [])].map((accion) => <button key={accion} className="boton-secundario" onClick={() => cambiarFormulario({ accion, registro: i })}>{accion} inscripción {i.id}</button>)}</td></tr>)}
    </tbody></table></div><PieListado listado={lista} />
    {historial && <section className="detalle-grupo"><h2>Eventos y reservas</h2><ul>{historial.eventos.map((e) => <li key={e.id}>{e.fecha_efectiva} · {e.tipo} · {e.estado_resultante}{e.motivo ? ' · ' + e.motivo : ''}</li>)}</ul>
      <ul>{historial.reservas.map((r) => <li key={r.id}>Reserva: {r.fecha_inicio} a {r.fecha_vencimiento} · {r.liberada_en ? 'Liberada' : 'El cupo se reserva solo hasta el vencimiento autorizado'}</li>)}</ul><button className="boton-secundario" onClick={() => cambiarHistorial(null)}>Cerrar historial</button></section>}
  </section>;
}
