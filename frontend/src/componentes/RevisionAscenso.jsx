import { useEffect, useRef, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion } from './Gestion.jsx';
import { SelectorCatalogo, etiquetaCatalogo } from './SelectorCatalogo.jsx';

const dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
function HorarioGrupo({ id }) {
  const [grupo, establecer] = useState(null);
  const [error, fallar] = useState(null);
  useEffect(() => {
    let vigente = true;
    solicitar(`/organizacion/grupos/${id}/`).then((r) => { if (vigente) establecer(r); })
      .catch((e) => { if (vigente) fallar(e); });
    return () => { vigente = false; };
  }, [id]);
  return <><ErrorGestion error={error} />{grupo ? <p>{etiquetaCatalogo(grupo)}: {grupo.horarios.map((h) => `${dias[h.dia]} ${h.hora_inicio}–${h.hora_fin}`).join(', ') || 'Sin horarios activos'}</p> : !error && <p role="status">Consultando grupo…</p>}</>;
}

function Disposicion({ fila, datos, enviar, bloqueado }) {
  const [opcion, elegir] = useState('');
  const [motivo, motivar] = useState('');
  const [destino, destinar] = useState('');
  const vigente = datos.excepciones.some((e) => e.afectacion === fila.afectacion && e.situacion === 'vigente');
  const opciones = ['revisar', 'reubicar', 'pendiente',
    ...(vigente ? ['continuidad'] : []), ...(fila.situacion_observada === 'reserva' ? ['reserva'] : []),
    ...(fila.situacion_observada === 'futura' ? ['futura'] : [])];
  return <form aria-label={`Disposición de inscripción ${fila.inscripcion}`} className="formulario-gestion" onSubmit={(e) => {
    e.preventDefault();
    if (!opciones.includes(opcion) || !motivo.trim() || (opcion === 'reubicar' && !destino)) return;
    enviar('disponer', { afectacion: fila.afectacion, disposicion: opcion, motivo: motivo.trim(), destino: opcion === 'reubicar' ? Number(destino) : null });
  }}><fieldset disabled={bloqueado}><legend>Preparar inscripción {fila.inscripcion}</legend>
    <Campo etiqueta="Disposición" nombre={`disposicion-${fila.inscripcion}`} valor={opcion} cambiar={(v) => { elegir(v); destinar(''); }} opciones={opciones.map((v) => [v, v])} />
    {!vigente && <p>Continuidad requiere una excepción institucional vigente. Este formulario no autoriza excepciones.</p>}
    {opcion === 'reubicar' && <SelectorCatalogo etiqueta="Destino propuesto" nombre={`destino-${fila.inscripcion}`} valor={destino} cambiar={destinar}
      ruta={`/organizacion/grupos/?${new URLSearchParams({ disciplina: datos.disciplina, nivel: datos.nivel_destino, activo: 'true' })}`} />}
    <label className="campo-gestion">Motivo de la disposición<textarea required maxLength={500} value={motivo} onChange={(e) => motivar(e.target.value)} /></label>
    <p>El destino es propuesto: no reserva cupos ni ejecuta traslados.</p>
    <button type="submit" disabled={!opcion || !motivo.trim() || (opcion === 'reubicar' && !destino)}>Registrar disposición</button>
  </fieldset></form>;
}

export function RevisionAscenso({ id, cerrar, actualizada }) {
  const [datos, establecer] = useState(null);
  const [error, fallar] = useState(null);
  const [cargando, cargar] = useState(true);
  const [ocupado, ocupar] = useState(false);
  const [aviso, avisar] = useState('');
  const [motivo, motivar] = useState('');
  const bloqueo = useRef(false);
  const vivo = useRef(false);
  async function consultar() {
    if (bloqueo.current) return;
    cargar(true); fallar(null); establecer(null);
    try { const r = await solicitar(`/ascensos/${id}/`); if (vivo.current) establecer(r); }
    catch (e) { if (vivo.current) fallar(e); }
    finally { if (vivo.current) cargar(false); }
  }
  useEffect(() => { vivo.current = true; consultar(); return () => { vivo.current = false; }; }, [id]);
  async function enviar(accion, payload) {
    if (bloqueo.current || !datos || error || cargando) return;
    if (accion !== 'disponer' && (!motivo.trim() || !datos.revision?.[accion === 'aprobar' ? 'puede_aprobar' : 'puede_rechazar'])) return;
    if (!window.confirm(`¿Confirmas ${accion === 'disponer' ? 'la disposición' : accion + ' la progresión pedagógica'}? No se ejecutarán traslados.`)) return;
    bloqueo.current = true; ocupar(true); fallar(null); avisar('');
    try {
      const r = await guardar(`/ascensos/${id}/${accion}/`, { version: datos.version, ...payload });
      if (vivo.current) { establecer(r); motivar(''); avisar('Registro confirmado. No se modificaron inscripciones ni cupos.'); actualizada(); }
    } catch (e) { if (vivo.current) fallar(e); }
    finally { bloqueo.current = false; if (vivo.current) ocupar(false); }
  }
  return <section aria-label={`Revisión de ascenso ${id}`} className="gestion">
    <h2>Revisión institucional de ascenso {id}</h2>
    <button type="button" disabled={ocupado || cargando} onClick={consultar}>Actualizar revisión</button>{' '}
    <button type="button" disabled={ocupado} onClick={cerrar}>Cerrar revisión</button>
    <ErrorGestion error={error} />{error && <p>Actualiza la revisión antes de continuar. Las condiciones pueden haber cambiado o tu acceso haber vencido.</p>}
    {cargando && <p role="status">Cargando revisión…</p>}{aviso && <p role="status">{aviso}</p>}
    {datos && <>
      <h3>{datos.nombre_deportista} · {datos.disciplina_nombre}</h3>
      <p>{datos.nivel_origen_nombre} → {datos.nivel_destino_nombre}</p>
      <p>Profesor: {datos.profesor_proponente?.nombre} · Fecha: {datos.creado_en}</p><p>{datos.justificacion}</p>
      <p>Decisión pedagógica: {datos.estado_decision}. Plan administrativo: {datos.estado_plan}. Versión: {datos.version}.</p>
      <p>Preparar no aprueba. Aprobar no ejecuta traslados ni garantiza plazas.</p>
      <h3>Advertencias</h3>{datos.revision.advertencias.length ? <ul>{datos.revision.advertencias.map((a, n) => <li key={n}>{a.mensaje}</li>)}</ul> : <p>Sin advertencias registradas en esta consulta.</p>}
      <h3>Inscripciones afectadas</h3>{datos.inscripciones.map((fila) => <article key={fila.inscripcion}>
        <h4>Inscripción {fila.inscripcion} · {fila.grupo.codigo} · {fila.grupo.nombre}</h4>
        <p>{fila.nivel.nombre} · {fila.periodo.nombre} ({fila.periodo.inicio} – {fila.periodo.fin})</p>
        <HorarioGrupo id={fila.grupo.id} />
        <p>Estado: {fila.estado}. Situación: {fila.situacion_actual}. Ingreso: {fila.fecha_ingreso}. Salida: {fila.fecha_salida || 'Sin cierre'}.</p>
        <p>Disposición: {fila.disposicion}. {fila.motivo}</p>
        {fila.destino_propuesto && <><p>Destino propuesto:</p><HorarioGrupo key={fila.destino_propuesto} id={fila.destino_propuesto} /></>}
        {fila.reservas_vigentes.map((r) => <p key={r.id}>Reserva vigente: {r.inicio} – {r.vencimiento}</p>)}
        {fila.afectacion && datos.estado_decision === 'pendiente' && <Disposicion key={`${fila.afectacion}:${datos.version}`} fila={fila} datos={datos} enviar={enviar}
          bloqueado={ocupado || cargando || Boolean(error) || !datos.revision.puede_preparar} />}
      </article>)}
      <h3>Excepciones pedagógicas</h3>{!datos.excepciones.length && <p>No hay excepciones registradas.</p>}
      {datos.excepciones.map((e) => <p key={e.id}>Afectación {e.afectacion}: {e.situacion}, {e.inicio} – {e.limite}. {e.motivo} · Responsable: {e.responsable?.nombre}</p>)}
      <h3>Historial de eventos</h3><ul>{datos.eventos.map((e) => <li key={e.id}>{e.fecha} · {e.tipo} · {e.responsable?.nombre} · {e.motivo}</li>)}</ul>
      {datos.decision && <p>Resolución: {datos.decision.resolucion || 'Pendiente'} · {datos.decision.responsable?.nombre} {datos.decision.fecha}</p>}
      {datos.estado_decision === 'pendiente' && <fieldset disabled={ocupado || Boolean(error)}><legend>Decisión pedagógica</legend>
        <label className="campo-gestion">Motivo de la resolución<textarea required maxLength={500} value={motivo} onChange={(e) => motivar(e.target.value)} /></label>
        {['aprobar', 'rechazar'].map((accion) => <button key={accion} type="button" disabled={!motivo.trim() || !datos.revision[accion === 'aprobar' ? 'puede_aprobar' : 'puede_rechazar']}
          onClick={() => enviar(accion, { decision: accion, resolucion: motivo.trim() })}>{accion === 'aprobar' ? 'Aprobar progresión pedagógica' : 'Rechazar progresión pedagógica'}</button>)}
      </fieldset>}
    </>}
  </section>;
}
