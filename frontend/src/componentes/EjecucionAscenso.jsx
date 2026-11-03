import { useEffect, useRef, useState } from 'react';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion, PieListado, useListado } from './Gestion.jsx';
import { SelectorCatalogo } from './SelectorCatalogo.jsx';

const dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
function Grupo({ grupo, historico }) {
  if (!grupo) return <p>Destino {historico || 'no definido'}: no disponible. No se seleccionará otro automáticamente.</p>;
  return <div><p>{grupo.codigo} · {grupo.nombre} · {grupo.nivel} · {grupo.periodo}</p>
    <p>{grupo.horarios.map((h) => `${dias[h.dia]} ${h.hora_inicio}–${h.hora_fin}`).join(', ') || 'Sin horarios activos'}</p>
    <p>Capacidad: {grupo.capacidad}. Ocupación máxima restante del periodo: {grupo.ocupacion_maxima}. Reservas vigentes: {grupo.reservas_vigentes}. Disponibles: {grupo.disponibles}.</p>
    <p>Consulta informativa: no garantiza una plaza. Se revalida al ejecutar.</p></div>;
}

function Historial({ id, tipo }) {
  const lista = useListado(`/ascensos/${id}/${tipo}/`, { permitirBusqueda: false });
  return <section aria-label={`Historial de ${tipo}`}><h3>{tipo === 'revisiones' ? 'Revisiones administrativas' : 'Resultados históricos'}</h3>
    <ErrorGestion error={lista.error} />{lista.cargando && <p role="status">Consultando historial…</p>}
    {!lista.cargando && !lista.datos.count && <p>Sin registros históricos.</p>}
    <ul>{lista.datos.results.map((r) => <li key={r.id}>{tipo === 'revisiones'
      ? <>Revisión {r.numero} · {r.registrada_en} · Responsable {r.actor_id} · {r.motivo}<ul>{r.disposiciones.map((f) => <li key={f.afectacion}>Inscripción {f.origen}: {f.disposicion} · destino {f.destino || 'pendiente'} · {f.motivo}</li>)}</ul></>
      : <>Resultado {r.id} · {r.estado} · origen {r.origen_id} → inscripción destino {r.destino_id || 'sin movimiento'} · {r.fecha_efectiva} · Responsable {r.actor_id} · {r.motivo}</>}</li>)}</ul>
    <PieListado listado={lista} />
  </section>;
}

function RevisionAdministrativa({ datos, enviar, cancelar, ocupado }) {
  const [filas, cambiar] = useState(datos.afectaciones.map((f) => ({ afectacion: f.afectacion,
    disposicion: f.disposicion, destino: f.destino_id, motivo: f.motivo || '' })));
  const [motivo, motivar] = useState('');
  function editar(id, campo, valor) { cambiar((actual) => actual.map((f) => f.afectacion === id ? { ...f, [campo]: valor } : f)); }
  return <form aria-label="Nueva revisión administrativa" className="formulario-gestion" onSubmit={(e) => {
    e.preventDefault(); if (!motivo.trim()) return;
    enviar({ version: datos.version, motivo: motivo.trim(), disposiciones: filas.map((f) => ({ ...f,
      destino: f.disposicion === 'reubicar' ? Number(f.destino) : null, motivo: f.motivo.trim() })) });
  }}><fieldset disabled={ocupado}><legend>Revisión completa y versionada</legend>
    <p>No cambia la aprobación pedagógica, no mueve deportistas y no reserva plazas. Incluye expresamente todas las inscripciones.</p>
    {filas.map((f) => {
      const original = datos.afectaciones.find((a) => a.afectacion === f.afectacion);
      const vigente = datos.excepciones.some((e) => e.afectacion === f.afectacion && e.situacion === 'vigente');
      const opciones = [...new Set(['revisar', 'reubicar', 'pendiente', ...(vigente ? ['continuidad'] : []),
        ...(original.situacion === 'reserva' ? ['reserva'] : []),
        ...(original.situacion === 'futura' ? ['futura'] : []),
        ...(original.ejecutada ? [f.disposicion] : [])])];
      return <fieldset key={f.afectacion} disabled={original.ejecutada}><legend>Inscripción {original.inscripcion}{original.ejecutada ? ' · movimiento histórico protegido' : ''}</legend>
        <Campo etiqueta={`Disposición de inscripción ${original.inscripcion}`} nombre={`plan-${f.afectacion}`} opciones={opciones.map((v) => [v, v])} valor={f.disposicion}
          cambiar={(v) => { editar(f.afectacion, 'disposicion', v); editar(f.afectacion, 'destino', null); }} />
        {f.disposicion === 'reubicar' && <SelectorCatalogo etiqueta={`Destino de inscripción ${original.inscripcion}`} nombre={`grupo-plan-${f.afectacion}`}
          valor={f.destino || ''} cambiar={(v) => editar(f.afectacion, 'destino', Number(v))}
          ruta={`/organizacion/grupos/?${new URLSearchParams({ disciplina: datos.disciplina_id, nivel: datos.nivel_destino_id, activo: 'true' })}`} />}
        <label className="campo-gestion">Motivo para inscripción {original.inscripcion}<textarea required maxLength={500} value={f.motivo} onChange={(e) => editar(f.afectacion, 'motivo', e.target.value)} /></label>
      </fieldset>;
    })}
    <label className="campo-gestion">Motivo de la revisión administrativa<textarea required maxLength={500} value={motivo} onChange={(e) => motivar(e.target.value)} /></label>
    <button type="submit" disabled={!motivo.trim() || filas.some((f) => !f.motivo.trim() || (f.disposicion === 'reubicar' && !f.destino))}>Registrar revisión completa</button>
    <button type="button" onClick={cancelar}>Cancelar revisión administrativa</button>
  </fieldset></form>;
}

export function EjecucionAscenso({ id, cerrar, actualizada = () => {}, formalizar = false }) {
  const [datos, establecer] = useState(null);
  const [error, fallar] = useState(null);
  const [cargando, cargar] = useState(true);
  const [ocupado, ocupar] = useState(false);
  const [revision, revisar] = useState(false);
  const [seleccion, seleccionar] = useState(null);
  const [motivo, motivar] = useState('');
  const [aviso, avisar] = useState('');
  const [historial, actualizarHistorial] = useState(0);
  const [reintentable, permitirReintento] = useState(false);
  const bloqueo = useRef(false);
  const intento = useRef(null);
  const vivo = useRef(false);
  async function consultar() {
    cargar(true); fallar(null); establecer(null);
    try { const r = await solicitar(`/ascensos/${id}/ejecucion/`); if (vivo.current) establecer(r); }
    catch (e) { if (vivo.current) fallar(e); }
    finally { if (vivo.current) cargar(false); }
  }
  useEffect(() => { vivo.current = true; consultar(); return () => { vivo.current = false; }; }, [id]);
  async function operar(tipo, payload) {
    if (!formalizar || bloqueo.current || !datos?.ejecucion_habilitada || (error && !(tipo === 'ejecutar' && reintentable))) return;
    if (!window.confirm(tipo === 'ejecutar'
      ? '¿Confirmas ejecutar únicamente esta reubicación? Se cerrará su inscripción de origen y se creará la de destino. Las demás no se trasladarán.'
      : '¿Confirmas registrar una nueva revisión completa? No se ejecutarán traslados ni cambiará la decisión pedagógica.')) return;
    bloqueo.current = true; ocupar(true); fallar(null); avisar('');
    try {
      await guardar(`/ascensos/${id}/${tipo}/`, payload);
      if (vivo.current) {
        intento.current = null; seleccionar(null); motivar(''); revisar(false);
        avisar(tipo === 'ejecutar' ? 'Reubicación confirmada. Consulta su resultado histórico.' : 'Revisión administrativa registrada sin cambiar la aprobación pedagógica.');
        actualizarHistorial((v) => v + 1); actualizada(); await consultar();
      }
    } catch (e) { if (vivo.current) { fallar(e); permitirReintento(e.estado === 0 || e.estado >= 500); } }
    finally { bloqueo.current = false; if (vivo.current) ocupar(false); }
  }
  function ejecutar(e) {
    e.preventDefault();
    const fila = datos.afectaciones.find((f) => f.afectacion === seleccion);
    if (!fila?.puede_ejecutar || !motivo.trim() || !datos.plan_completo || datos.estado_decision !== 'aprobada'
        || datos.discrepancias.length || datos.inscripciones_nuevas.length) return;
    // Ante respuesta perdida se conserva exactamente la misma clave y payload.
    if (!intento.current) intento.current = { revision: datos.revision, version: datos.version,
      afectacion: seleccion, clave: crypto.randomUUID(), motivo: motivo.trim() };
    operar('ejecutar', intento.current);
  }
  return <section className="gestion" aria-label={`Administración de ascenso ${id}`}>
    <h2>Reubicaciones administrativas · ascenso {id}</h2>
    <button type="button" disabled={ocupado || cargando} onClick={() => { seleccionar(null); intento.current = null; revisar(false); consultar(); actualizarHistorial((v) => v + 1); }}>Actualizar ejecución</button>{' '}
    <button type="button" disabled={ocupado} onClick={cerrar}>Cerrar administración</button>
    <ErrorGestion error={error} />{error && <p>Actualiza para revisar permisos, cupos y versiones. Si perdiste la respuesta, puedes reintentar la misma operación antes de actualizar; se conserva su clave.</p>}
    {cargando && <p role="status">Consultando ejecución…</p>}{aviso && <p role="status">{aviso}</p>}
    {datos && <>
      <h3>{datos.deportista} · {datos.disciplina}</h3><p>{datos.nivel_origen} → {datos.nivel_destino}</p>
      <p>Decisión pedagógica: {datos.estado_decision}. Ejecución: {datos.estado_ejecucion}. Revisión: {datos.revision_numero || 'sin registrar'}. Versión: {datos.version}.</p>
      <p>Esta pantalla no aprueba ascensos ni cierra progresiones automáticamente.</p>
      {!datos.ejecucion_habilitada && <p role="status">{datos.aviso_instalacion}</p>}
      {!datos.plan_completo && <p>Plan incompleto o desactualizado: requiere revisión expresa.</p>}
      {!!datos.discrepancias.length && <p>Discrepancias en afectaciones: {datos.discrepancias.join(', ')}.</p>}
      {!!datos.inscripciones_nuevas.length && <p>Hay inscripciones nuevas que requieren revisión institucional.</p>}
      <ul>{datos.advertencias_destinos.map((a, n) => <li key={n}>{a.codigo}: {a.mensaje}</li>)}</ul>
      {!formalizar && <p>Consulta coordinadora. La formalización corresponde exclusivamente a administración.</p>}
      {datos.afectaciones.map((f) => <article key={f.afectacion} aria-label={`Reubicación de inscripción ${f.inscripcion}`}>
        <h3>Inscripción {f.inscripcion} · {f.estado}{f.ejecutada ? ' · ejecutada' : ''}</h3>
        <p>Situación: {f.situacion}. Ingreso: {f.fecha_ingreso}. Salida: {f.fecha_salida || 'abierta'}. Disposición: {f.disposicion}. {f.motivo}</p>
        <h4>Origen</h4><Grupo grupo={f.origen} /><h4>Destino previsto</h4><Grupo grupo={f.destino} historico={f.destino_id} />
        <ul>{f.bloqueos.map((m, n) => <li key={n}>{m}</li>)}</ul>
        <button type="button" disabled={!formalizar || ocupado || !!error || !datos.ejecucion_habilitada || !f.puede_ejecutar || seleccion !== null
            || !datos.plan_completo || datos.estado_decision !== 'aprobada' || !!datos.discrepancias.length || !!datos.inscripciones_nuevas.length}
          onClick={() => { seleccionar(f.afectacion); motivar(''); intento.current = null; }}>Preparar ejecución de inscripción {f.inscripcion}</button>
      </article>)}
      {seleccion !== null && <form aria-label="Confirmar reubicación individual" onSubmit={ejecutar}><fieldset disabled={ocupado}>
        <legend>Ejecutar solo la afectación {seleccion}</legend>
        <label className="campo-gestion">Motivo de la reubicación<textarea required maxLength={240} disabled={!!intento.current} value={motivo} onChange={(e) => motivar(e.target.value)} /></label>
        <button type="submit" disabled={!motivo.trim() || !datos.ejecucion_habilitada || (!!error && !reintentable)}>{intento.current ? 'Reintentar misma reubicación' : 'Confirmar reubicación individual'}</button>
        <button type="button" onClick={() => { seleccionar(null); intento.current = null; }}>Cancelar ejecución</button>
      </fieldset></form>}
      <h3>Excepciones pedagógicas</h3><ul>{datos.excepciones.map((e, n) => <li key={n}>Afectación {e.afectacion}: {e.situacion}, {e.inicio}–{e.limite}. {e.motivo}</li>)}</ul>
      <button type="button" disabled={!formalizar || ocupado || !!error || !datos.ejecucion_habilitada || datos.estado_decision !== 'aprobada'} onClick={() => revisar(true)}>Preparar nueva revisión administrativa</button>
      {revision && <RevisionAdministrativa key={datos.version} datos={datos} ocupado={ocupado} cancelar={() => revisar(false)} enviar={(d) => operar('revisiones', d)} />}
      <Historial key={`r-${historial}`} id={id} tipo="revisiones" version={historial} />
      <Historial key={`e-${historial}`} id={id} tipo="resultados" version={historial} />
    </>}
  </section>;
}
