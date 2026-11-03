import { useEffect, useState, useRef } from 'react';
import { solicitar, prepararCsrf } from '../api/cliente.js';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';

const lista = (d) => d?.results ?? d ?? [];
const roles = (u) => u?.roles ?? [u?.rol];
const custodia = (u) => roles(u).some((r) => ['coordinador', 'administrador'].includes(r));
async function escribir(ruta, datos, method = 'POST') {
  await prepararCsrf();
  return solicitar(ruta, { method, body: datos instanceof FormData ? datos : JSON.stringify(datos) });
}
function Campo({ nombre, valor, cambiar, largo = false, tipo = 'text', obligatorio = true }) {
  return <label>{nombre}{largo ? <textarea value={valor ?? ''} required={obligatorio} onChange={(e) => cambiar(e.target.value)} /> : <input type={tipo} value={valor ?? ''} required={obligatorio} onChange={(e) => cambiar(e.target.value)} />}</label>;
}
function Selector({ nombre, valor, cambiar, opciones, opcional = false }) {
  return <label>{nombre}<select required={!opcional} value={valor ?? ''} onChange={(e) => cambiar(e.target.value)}><option value="">Selecciona…</option>{opciones.map((o) => <option key={o.id} value={o.id}>{o.nombre ?? o.titulo ?? `${o.ordinal ?? o.codigo ?? o.numero} (${o.id})`}</option>)}</select></label>;
}
function useCatalogo(ruta) {
  const [datos, setDatos] = useState([]); const [error, setError] = useState('');
  const [siguiente, setSiguiente] = useState(null);
  async function recargar() { try { const d = await solicitar(ruta); setDatos(lista(d)); setSiguiente(d.next || null); setError(''); } catch (e) { setError(e.message); } }
  async function mas() { try { const u = new URL(siguiente, window.location.origin); if (u.origin !== window.location.origin || !u.pathname.startsWith('/api/')) throw new Error('Página de catálogo no válida.'); const d = await solicitar(u.pathname.slice(4) + u.search); setDatos((v) => [...v, ...lista(d)]); setSiguiente(d.next || null); } catch (e) { setError(e.message); } }
  useEffect(() => { let activo = true; solicitar(ruta).then((d) => { if (activo) { setDatos(lista(d)); setSiguiente(d.next || null); } }).catch((e) => { if (activo) setError(e.message); }); return () => { activo = false; }; }, [ruta]);
  return { datos, recargar, error, siguiente, mas };
}
function Mensaje({ error, aviso }) { return <>{error && <p role="alert" className="mensaje-error">{error}</p>}{aviso && <p role="status">{aviso}</p>}</>; }

function AccionesVersion({ v, base, ejecutar, pendiente }) {
  const { usuario } = usarAutenticacion();
  const coordinador = roles(usuario).includes('coordinador');
  return <div className="contenido-acciones">
    <span>Edición {v.numero} · {v.naturaleza} · {v.estado}{v.vigente ? ' · vigente' : ''}</span>
    <button disabled={pendiente} onClick={() => ejecutar('derivar')}>Crear propuesta derivada</button>
    {v.estado === 'borrador' && v.naturaleza !== 'original_institucional' && <button disabled={pendiente} onClick={() => ejecutar('proponer')}>Enviar a revisión</button>}
    {coordinador && v.estado === 'en_revision' && <button disabled={pendiente} onClick={() => ejecutar('aprobar')}>Aprobar y publicar esta edición</button>}
    {coordinador && v.estado === 'en_revision' && <button disabled={pendiente} onClick={() => ejecutar('devolver')}>Devolver con observación</button>}
    {v.estado !== 'retirado' && <button disabled={pendiente} onClick={() => ejecutar('retirar')}>Retirar con motivo</button>}
  </div>;
}

function useEdicion(base, recargar) {
  const [v, seleccionar] = useState(null); const [error, setError] = useState(''); const [aviso, setAviso] = useState(''); const [pendiente, setPendiente] = useState(false);
  const [motivo, setMotivo] = useState('');
  const claves = useRef(new Map());
  async function actuar(accion) {
    if (['retirar','devolver'].includes(accion) && !motivo.trim()) { setError('Escribe un motivo u observación antes de continuar.'); return; }
    setPendiente(true); setError('');
    try {
      const intento = JSON.stringify([v.uuid, accion, v.revision, motivo]);
      if (!claves.current.has(intento)) claves.current.set(intento, crypto.randomUUID());
      const clave = claves.current.get(intento);
      const n = await escribir(`${base}${v.uuid}/${accion}/`, accion === 'derivar' ? { clave } : { revision: v.revision, clave, motivo });
      seleccionar(n); setAviso('Operación confirmada.'); await recargar();
    } catch (e) { setError(e.estado === 409 ? 'La edición cambió. Actualiza antes de reintentar.' : e.message); }
    finally { setPendiente(false); }
  }
  return { v, seleccionar, error, setError, aviso, setAviso, pendiente, actuar, motivo, setMotivo };
}

export function Curriculo() {
  const { usuario } = usarAutenticacion();
  const [programa, setPrograma] = useState('');
  const cat = useCatalogo('/curriculo/versiones/' + (programa ? `?programa=${programa}` : ''));
  const pro = useCatalogo('/curriculo/programas/');
  const ed = useEdicion('/curriculo/versiones/', cat.recargar);
  const [arbol, setArbol] = useState(null); const [nuevo, setNuevo] = useState({ codigo: '', nombre: '', derechos: '', programa: '' });
  const [tipo, setTipo] = useState('fase'); const [d, setD] = useState({}); const [texto, setTexto] = useState(''); const [elemento, setElemento] = useState('');
  useEffect(() => { setArbol(null); if (ed.v) solicitar(`/curriculo/versiones/${ed.v.uuid}/estructura/`).then(setArbol).catch((e) => ed.setError(e.message)); }, [ed.v?.uuid, ed.v?.revision]);
  async function crear(e) { e.preventDefault(); try { const v = await escribir('/curriculo/versiones/', { ...nuevo, programa: Number(nuevo.programa) }); ed.seleccionar(v); await cat.recargar(); } catch (x) { ed.setError(x.message); } }
  async function agregar(e) {
    e.preventDefault(); const datos = { ...d };
    for (const k of ['orden','ordinal','fase','semana','clase']) if (datos[k]) datos[k] = Number(datos[k]);
    if (tipo === 'elemento') { datos.tipo = datos.tipo || 'objetivo'; }
    try { await escribir(`/curriculo/versiones/${ed.v.uuid}/agregar/`, { tipo, datos, revision: ed.v.revision }); ed.seleccionar(await solicitar(`/curriculo/versiones/${ed.v.uuid}/`)); setD({}); } catch (x) { ed.setError(x.message); }
  }
  async function editarTexto(e) {
    e.preventDefault(); try { await escribir(`/curriculo/versiones/${ed.v.uuid}/editar-elemento/`, { elemento, texto, revision: ed.v.revision }); ed.seleccionar(await solicitar(`/curriculo/versiones/${ed.v.uuid}/`)); } catch (x) { ed.setError(x.message); }
  }
  const editable = ed.v?.estado === 'borrador' && ed.v.naturaleza !== 'original_institucional';
  return <section className="contenido-deportivo"><h1>Currículo</h1><p>Las clases previstas son referencias curriculares. No registran sesiones realizadas ni asistencia.</p>
    <Mensaje error={cat.error || pro.error || ed.error} aviso={ed.aviso} />
    <Selector nombre="Filtrar por programa" valor={programa} cambiar={setPrograma} opciones={pro.datos} opcional />
    <ul aria-label="Ediciones curriculares">{cat.datos.map((v) => <li key={v.uuid}><button onClick={() => ed.seleccionar(v)}>{v.nombre} · edición {v.numero} · {v.estado}</button></li>)}</ul>
    {cat.siguiente && <button onClick={cat.mas}>Cargar más mallas</button>}
    {!cat.datos.length && <p>No hay mallas visibles para tu ámbito.</p>}
    <details><summary>Crear propuesta curricular</summary><form onSubmit={crear} className="contenido-formulario">{['codigo','nombre','derechos'].map((k) => <Campo key={k} nombre={{ codigo: 'Código de malla', nombre: 'Nombre de malla', derechos: 'Procedencia y derechos de malla' }[k]} valor={nuevo[k]} cambiar={(v) => setNuevo({ ...nuevo, [k]: v })} />)}<Selector nombre="Programa de malla" valor={nuevo.programa} cambiar={(v) => setNuevo({ ...nuevo, programa: v })} opciones={pro.datos} /><button>Crear borrador de malla</button></form></details>
    {custodia(usuario) && <><ConfiguracionProgramas recargar={pro.recargar} />{pro.datos.filter((p) => !p.formalizado).map((p) => <p key={p.id}>{p.nombre}: pendiente de formalización <button onClick={async () => { try { await escribir(`/curriculo/programas/${p.id}/`, { formalizado: true }, 'PATCH'); await pro.recargar(); } catch (e) { ed.setError(e.message); } }}>Confirmar formalización del programa {p.nombre}</button></p>)}</>}
    {ed.v && <article><h2>{ed.v.nombre}</h2><AccionesVersion v={ed.v} ejecutar={ed.actuar} pendiente={ed.pendiente} /><Campo nombre="Motivo u observación curricular" valor={ed.motivo} cambiar={ed.setMotivo} obligatorio={false} />
      {arbol && <><h3>Fases y semanas</h3>{arbol.fases.map((f) => <section key={f.uuid}><h4>{f.nombre}</h4><p>Semanas: {arbol.semanas.filter((s) => s.fase === f.id).map((s) => s.ordinal).join(', ')}</p></section>)}<p>{arbol.clases.length} clases previstas.</p><h3>Objetivos, contenidos y desempeños</h3><ul>{arbol.elementos.map((e) => <li key={e.uuid}><strong>{e.tipo}</strong> · {e.dimension} {e.subdimension}<p>{e.texto}</p>{e.procedencia.map((p, i) => <small key={i}>Fuente: {p.fragmento__hoja}!{p.fragmento__rango || p.fragmento__celda} · {p.transformacion}</small>)}</li>)}</ul></>}
      {editable && arbol && <><form onSubmit={agregar} className="contenido-formulario"><h3>Completar estructura del borrador</h3><Selector nombre="Tipo de componente curricular" valor={tipo} cambiar={(v) => { setTipo(v); setD({}); }} opciones={['fase','semana','clase','elemento'].map((x) => ({ id: x, nombre: x }))} />
        {tipo === 'fase' && <>{['codigo','nombre','orden'].map((k) => <Campo key={k} nombre={`Fase: ${k}`} tipo={k === 'orden' ? 'number' : 'text'} valor={d[k]} cambiar={(v) => setD({ ...d, [k]: v })} />)}</>}
        {tipo === 'semana' && <><Selector nombre="Fase de semana" valor={d.fase} cambiar={(v) => setD({ ...d, fase: v })} opciones={arbol.fases} /><Campo nombre="Número global de semana" tipo="number" valor={d.ordinal} cambiar={(v) => setD({ ...d, ordinal: v })} /></>}
        {tipo === 'clase' && <><Selector nombre="Semana de clase" valor={d.semana} cambiar={(v) => setD({ ...d, semana: v })} opciones={arbol.semanas} /><Campo nombre="Número global de clase prevista" tipo="number" valor={d.ordinal} cambiar={(v) => setD({ ...d, ordinal: v })} /></>}
        {tipo === 'elemento' && <><Selector nombre="Tipo de contenido curricular" valor={d.tipo || 'objetivo'} cambiar={(v) => setD({ ...d, tipo: v })} opciones={['objetivo','competencia','contenido','desempeno'].map((x) => ({ id: x, nombre: x }))} /><Campo nombre="Texto curricular" largo valor={d.texto} cambiar={(v) => setD({ ...d, texto: v })} /><Campo nombre="Dimensión" valor={d.dimension} obligatorio={false} cambiar={(v) => setD({ ...d, dimension: v })} /><Selector nombre="Clase de contenido (opcional)" valor={d.clase} cambiar={(v) => { const n = { ...d }; if (v) n.clase = v; else delete n.clase; setD(n); }} opciones={arbol.clases} opcional /></>}
        <button>Agregar componente curricular</button></form>
        <form onSubmit={editarTexto} className="contenido-formulario"><h3>Revisar un texto</h3><Selector nombre="Elemento a revisar" valor={elemento} cambiar={(v) => { setElemento(v); setTexto(arbol.elementos.find((x) => x.uuid === v)?.texto || ''); }} opciones={arbol.elementos.map((x) => ({ id: x.uuid, nombre: x.texto.slice(0,90) }))} /><Campo nombre="Texto revisado" valor={texto} cambiar={setTexto} largo /><button>Guardar texto revisado</button></form></>}
      {editable && arbol && <ActividadDeMalla version={ed.v} elementos={arbol.elementos} actualizado={async()=>ed.seleccionar(await solicitar(`/curriculo/versiones/${ed.v.uuid}/`))} onError={ed.setError} />}
    </article>}
  </section>;
}

function ActividadDeMalla({version,elementos,actualizado,onError}) {
  const ejercicios = useCatalogo('/biblioteca/versiones/?estado=aprobado&vigente=true'); const [elemento,setElemento]=useState(''); const [ejercicio,setEjercicio]=useState(''); const [finalidad,setFinalidad]=useState('');
  return <form className="contenido-formulario" onSubmit={async(e)=>{e.preventDefault();try{await escribir(`/curriculo/versiones/${version.uuid}/actividad/`,{elemento,ejercicio_version:ejercicio,finalidad,revision:version.revision});await actualizado();}catch(x){onError(x.message);}}}><h3>Relacionar actividad aprobada</h3><Selector nombre="Objetivo o desempeño de actividad" valor={elemento} cambiar={setElemento} opciones={elementos.map((x)=>({id:x.uuid,nombre:x.texto.slice(0,100)}))} /><Selector nombre="Edición de ejercicio aprobada" valor={ejercicio} cambiar={setEjercicio} opciones={ejercicios.datos.map((x)=>({id:x.uuid,nombre:x.nombre}))} /><Campo nombre="Finalidad curricular de actividad" valor={finalidad} cambiar={setFinalidad} /><button>Relacionar actividad curricular</button></form>;
}

function ConfiguracionProgramas({ recargar }) {
  const niveles = useCatalogo('/organizacion/niveles/'); const [nivel, setNivel] = useState(''); const [modalidad, setModalidad] = useState('curricular'); const [error, setError] = useState('');
  return <details><summary>Vincular programa a nivel existente</summary><form className="contenido-formulario" onSubmit={async (e) => { e.preventDefault(); try { await escribir('/curriculo/programas/', { nivel: Number(nivel), modalidad, formalizado: false }); await recargar(); setError('Programa creado como pendiente de formalización.'); } catch (x) { setError(x.message); } }}><Selector nombre="Nivel existente" valor={nivel} cambiar={setNivel} opciones={niveles.datos} /><Selector nombre="Modalidad de programa" valor={modalidad} cambiar={setModalidad} opciones={['curricular','mixta','individual'].map((x) => ({ id: x, nombre: x }))} /><button>Crear programa pendiente</button><p role="status">{error}</p></form></details>;
}

export function Biblioteca() {
  const { usuario } = usarAutenticacion();
  const [buscar, setBuscar] = useState(''); const [filtro, setFiltro] = useState('');
  const [filtros, setFiltros] = useState({});
  const query = new URLSearchParams({ buscar: filtro, ...Object.fromEntries(Object.entries(filtros).filter(([, v]) => v)) });
  const cat = useCatalogo('/biblioteca/versiones/?' + query.toString().replaceAll('+','%20')); const pro = useCatalogo('/curriculo/programas/');
  const terminos = useCatalogo('/biblioteca/terminos/');
  const ed = useEdicion('/biblioteca/versiones/', cat.recargar); const [crear, setCrear] = useState(false);
  const [paso, setPaso] = useState(''); const [condicion, setCondicion] = useState(''); const [alternativa, setAlternativa] = useState(''); const [limites, setLimites] = useState('');
  async function agregar(tipo, datos) { try { await escribir(`/biblioteca/versiones/${ed.v.uuid}/agregar/`, { tipo, datos, revision: ed.v.revision }); ed.seleccionar(await solicitar(`/biblioteca/versiones/${ed.v.uuid}/`)); } catch (x) { ed.setError(x.message); } }
  const editable = ed.v?.estado === 'borrador';
  return <section className="contenido-deportivo"><h1>Biblioteca de ejercicios</h1><p>Una ficha aprobada no sustituye la adaptación docente ni las restricciones individuales. Los candidatos históricos no se publican automáticamente.</p><Mensaje error={cat.error || ed.error} aviso={ed.aviso} />
    <form onSubmit={(e) => { e.preventDefault(); setFiltro(buscar); }}><Campo nombre="Buscar ejercicio" valor={buscar} cambiar={setBuscar} obligatorio={false} /><button>Buscar</button></form>
    <div className="contenido-formulario"><Selector nombre="Programa del filtro de ejercicios" valor={filtros.programa} cambiar={(v) => setFiltros({ ...filtros, programa:v })} opciones={pro.datos} opcional />
      {[['capacidad','capacidad'],['estilo','estilo'],['material','implemento'],['instalacion','instalacion']].map(([k,n]) => <Selector key={k} nombre={`Filtrar ejercicios por ${k}`} valor={filtros[k]} cambiar={(v) => setFiltros({ ...filtros, [k]:v })} opciones={terminos.datos.filter((t) => t.namespace === n).map((t) => ({ id:t.codigo, nombre:t.nombre }))} opcional />)}
      <Campo nombre="Duración máxima del filtro (min)" tipo="number" valor={filtros.duracion_max} cambiar={(v) => setFiltros({ ...filtros,duracion_max:v })} obligatorio={false} /></div>
    {custodia(usuario) && <CrearTermino recargar={terminos.recargar} />}
    <button onClick={() => { setCrear(!crear); ed.seleccionar(null); }}>Preparar ejercicio propio</button>
    {crear && <FormularioEjercicio programas={pro.datos} guardar={async (codigo, contenido) => { const v = await escribir('/biblioteca/versiones/', { codigo, contenido }); ed.seleccionar(v); setCrear(false); await cat.recargar(); }} onError={ed.setError} />}
    <ul aria-label="Ejercicios visibles">{cat.datos.map((v) => <li key={v.uuid}><button onClick={() => { ed.seleccionar(v); setCrear(false); }}>{v.nombre} · edición {v.numero} · {v.estado}</button></li>)}</ul>{!cat.datos.length && <p>No hay ejercicios visibles.</p>}
    {cat.siguiente && <button onClick={cat.mas}>Cargar más ejercicios</button>}
    {ed.v && <article><h2>{ed.v.nombre}</h2><AccionesVersion v={ed.v} ejecutar={ed.actuar} pendiente={ed.pendiente} /><Campo nombre="Motivo u observación de ejercicio" valor={ed.motivo} cambiar={ed.setMotivo} obligatorio={false} />
      {['objetivo','poblacion','metodologia','descripcion','prerrequisitos','riesgos','controles','derechos'].map((k) => <p key={k}><strong>{k}:</strong> {ed.v[k] || 'No documentado'}</p>)}<p>Duración orientativa: {ed.v.duracion_min ?? 'sin dato'}–{ed.v.duracion_max ?? 'sin dato'} min</p>
      <h3>Pasos</h3><ol>{ed.v.pasos.map((p) => <li key={p.id}>{p.instrucciones}</li>)}</ol><h3>Adaptaciones</h3><ul>{ed.v.adaptaciones.map((a) => <li key={a.id}>{a.condicion}: {a.alternativa}. Límites: {a.limites}</li>)}</ul><h3>Materiales autorizados</h3>{ed.v.materiales.map((m) => <p key={m.material__uuid}><a href={`/api/biblioteca/materiales/${m.material__uuid}/descarga/`}>Descargar material: {m.finalidad}</a></p>)}
      {editable && <><FormularioEjercicio inicial={ed.v} programas={pro.datos} guardar={async (_, contenido) => { const v = await escribir(`/biblioteca/versiones/${ed.v.uuid}/`, { ...contenido, revision: ed.v.revision }, 'PATCH'); ed.seleccionar(v); await cat.recargar(); }} onError={ed.setError} />
        <form onSubmit={(e) => { e.preventDefault(); agregar('paso', { orden: ed.v.pasos.length + 1, instrucciones: paso }); }}><Campo nombre="Nuevo paso de ejecución" largo valor={paso} cambiar={setPaso} /><button>Agregar paso</button></form>
        <form onSubmit={(e) => { e.preventDefault(); agregar('adaptacion', { condicion, alternativa, limites }); }} className="contenido-formulario"><Campo nombre="Población o condición de adaptación" valor={condicion} cambiar={setCondicion} /><Campo nombre="Alternativa" valor={alternativa} cambiar={setAlternativa} /><Campo nombre="Límites de adaptación" valor={limites} cambiar={setLimites} /><button>Agregar adaptación</button></form></>}
      {editable && <CompletarEjercicio version={ed.v} terminos={terminos.datos} agregar={agregar} />}
    </article>}
  </section>;
}

function CompletarEjercicio({ version, terminos, agregar }) {
  const materiales = useCatalogo('/biblioteca/materiales/?estado=aprobado&vigente=true');
  const [termino,setTermino]=useState(''); const [descripcion,setDescripcion]=useState(''); const [estado,setEstado]=useState('requiere_revision'); const [material,setMaterial]=useState(''); const [finalidad,setFinalidad]=useState('');
  return <details><summary>Exigencias funcionales y recursos relacionados</summary><p>Registrar exigencias no concede autorización clínica ni garantiza compatibilidad individual.</p>
    <form className="contenido-formulario" onSubmit={(e)=>{e.preventDefault();agregar('exigencia',{termino:Number(termino),descripcion,estado_dato:estado});}}><Selector nombre="Exigencia funcional" valor={termino} cambiar={setTermino} opciones={terminos.filter((t)=>t.namespace==='exigencia_funcional')} /><Campo nombre="Descripción de exigencia" valor={descripcion} cambiar={setDescripcion} /><Selector nombre="Estado de información funcional" valor={estado} cambiar={setEstado} opciones={['conocido','desconocido','requiere_revision'].map((x)=>({id:x,nombre:x}))} /><button>Registrar exigencia</button></form>
    <form className="contenido-formulario" onSubmit={(e)=>{e.preventDefault();agregar('material',{material:Number(material),finalidad});}}><Selector nombre="Material aprobado relacionado" valor={material} cambiar={setMaterial} opciones={materiales.datos} /><Campo nombre="Finalidad del recurso" valor={finalidad} cambiar={setFinalidad} /><button>Relacionar material docente</button></form>
    <ul>{version.exigencias.map((e)=><li key={e.id}>{e.descripcion} · {e.estado_dato}</li>)}</ul>
  </details>;
}

function FormularioEjercicio({ inicial, programas, guardar, onError }) {
  const { usuario } = usarAutenticacion();
  const terminos = useCatalogo('/biblioteca/terminos/');
  const disciplinas = useCatalogo('/organizacion/disciplinas/'); const [d, setD] = useState(inicial || { codigo: '', nombre: '', disciplina: '', programas: [], objetivo: '', poblacion: '', metodologia: '', descripcion: '', riesgos: '', controles: '', derechos: '', prerrequisitos: '', duracion_min: '', duracion_max: '' });
  useEffect(() => { if (inicial) setD(inicial); }, [inicial?.uuid, inicial?.revision]);
  async function enviar(e) { e.preventDefault(); const campos = ['nombre','disciplina','objetivo','poblacion','metodologia','descripcion','riesgos','controles','derechos','prerrequisitos']; const contenido = Object.fromEntries(campos.map((k) => [k, d[k] ?? ''])); contenido.disciplina = Number(d.disciplina); contenido.programas = (d.programas || []).map(Number); contenido.etiquetas = (d.etiquetas || []).map(Number); contenido.acceso_tecnico = !!d.acceso_tecnico; for (const k of ['duracion_min','duracion_max']) contenido[k] = d[k] === '' || d[k] == null ? null : Number(d[k]); try { await guardar(d.codigo, contenido); } catch (x) { onError(x.message); } }
  return <form onSubmit={enviar} className="contenido-formulario"><h3>{inicial ? 'Editar borrador' : 'Nuevo ejercicio'}</h3>{!inicial && <Campo nombre="Código del ejercicio" valor={d.codigo} cambiar={(v) => setD({ ...d, codigo: v })} />}
    {['nombre','objetivo','poblacion','metodologia','descripcion','prerrequisitos','riesgos','controles','derechos'].map((k) => <Campo key={k} nombre={{nombre:'Nombre del ejercicio',objetivo:'Objetivo del ejercicio',poblacion:'Población',metodologia:'Metodología',descripcion:'Descripción',prerrequisitos:'Prerrequisitos',riesgos:'Riesgos',controles:'Controles de seguridad',derechos:'Fuentes y derechos de uso'}[k]} valor={d[k]} obligatorio={k !== 'prerrequisitos'} largo={k !== 'nombre'} cambiar={(v) => setD({ ...d, [k]: v })} />)}
    <Selector nombre="Disciplina del ejercicio" valor={d.disciplina} cambiar={(v) => setD({ ...d, disciplina: v })} opciones={disciplinas.datos} /><label>Programas pertinentes<select multiple value={(d.programas || []).map(String)} onChange={(e) => setD({ ...d, programas: Array.from(e.target.selectedOptions, (o) => Number(o.value)) })}>{programas.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</select></label>
    <label>Capacidades, materiales e instalaciones<select multiple value={(d.etiquetas || []).map(String)} onChange={(e) => setD({ ...d, etiquetas:Array.from(e.target.selectedOptions,(o) => Number(o.value)) })}>{terminos.datos.map((t) => <option key={t.id} value={t.id}>{t.namespace}: {t.nombre}</option>)}</select></label>
    {(custodia(usuario) || roles(usuario).includes('routesetter')) && <label><input type="checkbox" checked={!!d.acceso_tecnico} onChange={(e) => setD({ ...d, acceso_tecnico:e.target.checked })} />Pertinente para catálogo técnico de Route Setting</label>}
    {['duracion_min','duracion_max'].map((k) => <Campo key={k} nombre={k === 'duracion_min' ? 'Duración mínima orientativa (min)' : 'Duración máxima orientativa (min)'} valor={d[k]} tipo="number" obligatorio={false} cambiar={(v) => setD({ ...d, [k]: v })} />)}<button>Guardar ficha de ejercicio</button></form>;
}

function CrearTermino({ recargar }) {
  const [d,setD] = useState({namespace:'capacidad',codigo:'',nombre:''}); const [error,setError] = useState('');
  return <details><summary>Registrar término de actividad</summary><form className="contenido-formulario" onSubmit={async(e) => { e.preventDefault(); try { await escribir('/biblioteca/terminos/',d); await recargar(); setError('Término registrado.'); } catch(x) { setError(x.message); } }}><Selector nombre="Tipo de término" valor={d.namespace} cambiar={(v) => setD({...d,namespace:v})} opciones={['capacidad','estilo','movimiento','geometria','implemento','instalacion','exigencia_funcional'].map((v) => ({id:v,nombre:v}))} /><Campo nombre="Código del término" valor={d.codigo} cambiar={(v) => setD({...d,codigo:v})} /><Campo nombre="Nombre del término" valor={d.nombre} cambiar={(v) => setD({...d,nombre:v})} /><button>Registrar término</button><p role="status">{error}</p></form></details>;
}

async function cargarArchivo(f, finalidad) {
  const d = new FormData(); d.append('archivo', f); d.append('finalidad', finalidad); d.append('declaracion', 'true');
  return escribir('/recursos/archivos/', d);
}

export function MaterialesDocentes() {
  const cat = useCatalogo('/biblioteca/materiales/'); const pro = useCatalogo('/curriculo/programas/'); const ed = useEdicion('/biblioteca/materiales/', cat.recargar);
  const [d, setD] = useState({ codigo: '', titulo: '', resumen: '', derechos: '', programa: '', referencia_externa: '' });
  const [f, setF] = useState(null); const [confirmo, setConfirmo] = useState(false);
  async function crear(e) {
    e.preventDefault(); if (!confirmo) { ed.setError('Confirma derechos y ausencia de datos personales privados.'); return; }
    try {
      const a = f ? await cargarArchivo(f, 'material_docente') : null;
      const contenido = { titulo: d.titulo, resumen: d.resumen, derechos: d.derechos, programas: d.programa ? [Number(d.programa)] : [], ...(a ? { archivo: a.id } : { referencia_externa: d.referencia_externa }) };
      ed.seleccionar(await escribir('/biblioteca/materiales/', { codigo: d.codigo, contenido })); await cat.recargar();
    } catch (x) { ed.setError(x.message); }
  }
  return <section className="contenido-deportivo"><h1>Materiales docentes</h1><p>Repositorio privado versionado. No adjuntes datos de deportistas ni grabaciones privadas.</p><Mensaje error={cat.error || ed.error} aviso={ed.aviso} />
    <ul aria-label="Materiales visibles">{cat.datos.map((v) => <li key={v.uuid}><button onClick={() => ed.seleccionar(v)}>{v.titulo} · edición {v.numero} · {v.estado}</button></li>)}</ul>
    {cat.siguiente && <button onClick={cat.mas}>Cargar más materiales</button>}
    <details><summary>Preparar material docente</summary><form onSubmit={crear} className="contenido-formulario">
      {['codigo','titulo','resumen','derechos','referencia_externa'].map((k) => <Campo key={k} nombre={{ codigo:'Código del material',titulo:'Título del material',resumen:'Resumen del material',derechos:'Licencia y procedencia',referencia_externa:'Enlace HTTPS (si no adjuntas archivo)' }[k]} valor={d[k]} cambiar={(v) => setD({ ...d, [k]: v })} obligatorio={k !== 'referencia_externa'} />)}
      <Selector nombre="Programa destinatario" valor={d.programa} cambiar={(v) => setD({ ...d, programa: v })} opciones={pro.datos} /><label>Archivo docente (máximo 25 MiB)<input type="file" accept=".pdf,.txt,.docx,.xlsx,.png,.jpg,.mp4,.mov" onChange={(e) => setF(e.target.files[0] || null)} /></label>
      <label><input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} required />Tengo derechos de uso y el material no contiene datos personales ni grabaciones privadas.</label><button>Crear edición de material</button>
    </form></details>
    {ed.v && <article><h2>{ed.v.titulo}</h2><p>{ed.v.resumen}</p><p>Derechos: {ed.v.derechos}</p><AccionesVersion v={ed.v} ejecutar={ed.actuar} pendiente={ed.pendiente} /><Campo nombre="Motivo u observación de material" valor={ed.motivo} cambiar={ed.setMotivo} obligatorio={false} />
      {ed.v.archivo ? <a href={`/api/biblioteca/materiales/${ed.v.uuid}/descarga/`}>Descargar edición autorizada</a> : <a href={ed.v.referencia_externa} target="_blank" rel="noopener noreferrer">Consultar referencia externa</a>}
      {ed.v.estado === 'borrador' && <EditarMaterial version={ed.v} guardar={async(datos)=>{try{ed.seleccionar(await escribir(`/biblioteca/materiales/${ed.v.uuid}/`,{...datos,revision:ed.v.revision},'PATCH'));await cat.recargar();}catch(e){ed.setError(e.message);}}} />}
    </article>}
  </section>;
}

function EditarMaterial({version,guardar}) {
  const [d,setD]=useState({titulo:version.titulo,resumen:version.resumen,derechos:version.derechos});
  useEffect(()=>{setD({titulo:version.titulo,resumen:version.resumen,derechos:version.derechos});},[version.uuid,version.revision]);
  return <form className="contenido-formulario" onSubmit={(e)=>{e.preventDefault();guardar(d);}}><h3>Editar material en borrador</h3>{['titulo','resumen','derechos'].map((k)=><Campo key={k} nombre={`Material revisado: ${k}`} valor={d[k]} cambiar={(v)=>setD({...d,[k]:v})} />)}<button>Guardar revisión de material</button></form>;
}

export function FuentesCurriculares() {
  const fuentes = useCatalogo('/recursos/fuentes/'); const versiones = useCatalogo('/recursos/fuentes-version/'); const lotes = useCatalogo('/curriculo/importaciones/'); const programas = useCatalogo('/curriculo/programas/');
  const [titulo, setTitulo] = useState(''); const [fuente, setFuente] = useState(''); const [numero, setNumero] = useState('1'); const [licencia, setLicencia] = useState(''); const [f, setF] = useState(null); const [declaracion, setDeclaracion] = useState(false); const [version, setVersion] = useState(''); const [lote, setLote] = useState(null); const [mapa, setMapa] = useState({}); const [error, setError] = useState(''); const [aviso, setAviso] = useState('');
  async function ejecutar(fn) { try { setError(''); await fn(); setAviso('Operación confirmada sin publicación automática.'); } catch (e) { setError(e.message); } }
  return <section className="contenido-deportivo"><h1>Fuentes e importación curricular</h1><p>Custodia institucional. El original se conserva sin corregir; la confirmación no publica una malla. No se importan candidatos de ejercicios.</p><Mensaje error={error || fuentes.error || versiones.error || lotes.error} aviso={aviso} />
    <form className="contenido-formulario" onSubmit={(e) => { e.preventDefault(); ejecutar(async () => { await escribir('/recursos/fuentes/', { titulo, referencia: 'Documento institucional bajo custodia' }); await fuentes.recargar(); }); }}><Campo nombre="Título de fuente documental" valor={titulo} cambiar={setTitulo} /><button>Registrar fuente</button></form>
    <form className="contenido-formulario" onSubmit={(e) => { e.preventDefault(); ejecutar(async () => { if (!f || !declaracion) throw new Error('Adjunta el archivo autorizado y confirma su custodia.'); const a = await cargarArchivo(f, 'fuente_curricular'); await escribir('/recursos/fuentes-version/', { fuente: Number(fuente), numero: Number(numero), archivo: a.id, licencia }); await versiones.recargar(); }); }}><Selector nombre="Fuente del archivo original" valor={fuente} cambiar={setFuente} opciones={fuentes.datos} /><Campo nombre="Número de edición de fuente" tipo="number" valor={numero} cambiar={setNumero} /><Campo nombre="Licencia o custodia del original" valor={licencia} cambiar={setLicencia} largo /><label>Excel original<input type="file" accept=".xlsx" onChange={(e) => setF(e.target.files[0] || null)} required /></label><label><input type="checkbox" required checked={declaracion} onChange={(e) => setDeclaracion(e.target.checked)} />Autorizo su custodia privada y tengo derechos para este uso; no contiene datos personales de deportistas.</label><button>Conservar edición original</button></form>
    <form onSubmit={(e) => { e.preventDefault(); ejecutar(async () => { setLote(await escribir('/curriculo/importaciones/', { fuente: Number(version), clave: crypto.randomUUID() })); await lotes.recargar(); }); }}><Selector nombre="Edición de fuente para vista previa" valor={version} cambiar={setVersion} opciones={versiones.datos.map((v) => ({ id:v.id,nombre:`Fuente ${v.fuente}, edición ${v.numero} · ${v.sha256.slice(0,12)}` }))} /><button>Extraer vista previa</button></form>
    <ul>{versiones.datos.filter((v)=>v.archivo).map((v)=><li key={v.uuid}><a href={`/api/recursos/fuentes-version/${v.id}/descarga/`}>Descargar original bajo custodia: fuente {v.fuente}, edición {v.numero}</a></li>)}</ul>
    <ul>{lotes.datos.map((l) => <li key={l.uuid}><button onClick={() => setLote(l)}>Importación {l.uuid.slice(0,8)} · {l.estado}</button></li>)}</ul>
    {lote && <section><h2>Vista previa de importación</h2>{lote.vista_previa.hojas.map((h) => <div key={h.nombre}><h3>{h.nombre}</h3><p>{h.semanas} semanas, {h.clases} clases. Fases: {h.fases.join(' / ')}. {h.combinadas.length} rangos combinados preservados.</p><p>{h.incidencias.join(' ')}</p><Selector nombre={`Programa para ${h.nombre}`} valor={mapa[h.nombre]} cambiar={(v) => setMapa({ ...mapa, [h.nombre]: Number(v) })} opciones={programas.datos} /></div>)}<button disabled={lote.estado === 'confirmado'} onClick={() => ejecutar(async () => { setLote(await escribir(`/curriculo/importaciones/${lote.uuid}/confirmar/`, { programas: mapa })); await lotes.recargar(); })}>Confirmar archivo curricular sin publicar</button><p>Después crea una propuesta derivada y revisa las incidencias antes de enviarla a aprobación.</p></section>}
  </section>;
}
