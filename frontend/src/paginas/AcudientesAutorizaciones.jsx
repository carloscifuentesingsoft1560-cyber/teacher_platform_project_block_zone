import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar, fechaBogota } from '../api/gestion.js';
import { useListado, BarraListado, PieListado } from '../componentes/Gestion.jsx';
import { FormularioRegistro } from '../componentes/FormularioRegistro.jsx';
import { ComprobacionFacultad } from '../componentes/ComprobacionFacultad.jsx';

const persona = [{ nombre: 'nombres', etiqueta: 'Nombres', maxLength: 100 }, { nombre: 'apellidos', etiqueta: 'Apellidos', maxLength: 100 }];
const camposContacto = [...persona, { nombre: 'telefono', etiqueta: 'Teléfono de contacto', requerido: false, maxLength: 30 }, { nombre: 'correo', etiqueta: 'Correo de contacto', tipo: 'email', requerido: false }];
const deportista = { nombre: 'deportista', etiqueta: 'Deportista', ruta: '/deportistas/', numero: true };
const secciones = {
  acudientes: { titulo: 'Acudientes', campos: camposContacto },
  'vinculos-acudientes': { titulo: 'Vínculos con acudientes', inicial: () => ({ fecha_inicio: fechaBogota() }), campos: [deportista, { nombre: 'acudiente', etiqueta: 'Acudiente', ruta: '/acudientes/', numero: true },
    { nombre: 'parentesco', etiqueta: 'Parentesco declarado', requerido: false, maxLength: 60 }, { nombre: 'fecha_inicio', etiqueta: 'Inicio del vínculo', tipo: 'date' },
    { nombre: 'fecha_fin', etiqueta: 'Fin exclusivo del vínculo', tipo: 'date', requerido: false }, { nombre: 'es_contacto_principal', etiqueta: 'Contacto principal', tipo: 'checkbox' }] },
  autorizaciones: { titulo: 'Autorizaciones diferenciadas', campos: [deportista, { nombre: 'tipo', etiqueta: 'Tipo y finalidad aprobada', ruta: '/tipos-autorizacion/', numero: true },
    { nombre: 'otorgante', etiqueta: 'Otorgante', opciones: [['acudiente', 'Acudiente con facultad verificada'], ['deportista', 'Deportista según política aprobada']] },
    { nombre: 'vinculo_acudiente', etiqueta: 'Vínculo acreditado, cuando corresponda', tipo: 'number', numero: true, requerido: false, min: 1 },
    { nombre: 'decision', etiqueta: 'Decisión acreditada', opciones: [['otorgada', 'Otorgada'], ['denegada', 'Denegada']] },
    { nombre: 'declarada_en', etiqueta: 'Fecha y hora de la declaración', tipo: 'datetime-local' },
    { nombre: 'vigente_desde', etiqueta: 'Vigente desde', tipo: 'date' }, { nombre: 'vigente_hasta', etiqueta: 'Vigente hasta', tipo: 'date', requerido: false },
    { nombre: 'referencia_evidencia', etiqueta: 'Referencia privada de la evidencia', requerido: false, maxLength: 240 }] },
  'tipos-autorizacion': { titulo: 'Tipos y versiones de autorización', inicial: () => ({ numero_version: 1 }), campos: [
    { nombre: 'codigo', etiqueta: 'Código de finalidad', maxLength: 50 }, { nombre: 'numero_version', etiqueta: 'Versión del texto', tipo: 'number', numero: true, min: 1 },
    { nombre: 'finalidad', etiqueta: 'Finalidad institucional aprobada', maxLength: 240 }, { nombre: 'referencia_texto_aprobado', etiqueta: 'Referencia del texto aprobado', maxLength: 240 }] },
  'politicas-datos': { titulo: 'Políticas de conservación y supresión', campos: [
    { nombre: 'codigo', etiqueta: 'Código de política', maxLength: 50 }, { nombre: 'finalidad', etiqueta: 'Finalidad', maxLength: 240 },
    { nombre: 'criterio_conservacion', etiqueta: 'Criterio institucional de conservación' }, { nombre: 'procedimiento_supresion', etiqueta: 'Procedimiento autorizado de supresión' },
    { nombre: 'referencia_aprobacion', etiqueta: 'Referencia de aprobación institucional', maxLength: 240 },
    { nombre: 'edad_autonomia', etiqueta: 'Edad de autonomía expresamente aprobada, si aplica', tipo: 'number', numero: true, requerido: false, min: 1 }] },
};

function RegistroPrivado({ tipo, consulta }) {
  const { usuario } = usarAutenticacion();
  const config = secciones[tipo];
  const lista = useListado('/' + tipo + '/' + consulta);
  const [formulario, cambiarFormulario] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const puedeCrear = !['tipos-autorizacion', 'politicas-datos'].includes(tipo) || usuario.rol === 'administrador';
  async function enviar(datos) {
    const r = formulario.registro;
    const cuerpo = { ...datos };
    for (const k of ['fecha_fin', 'vigente_hasta', 'edad_autonomia', 'vinculo_acudiente']) if (cuerpo[k] === '') cuerpo[k] = null;
    if (cuerpo.declarada_en) cuerpo.declarada_en = new Date(cuerpo.declarada_en).toISOString();
    if (formulario.accion === 'crear') await guardar('/' + tipo + '/', cuerpo);
    else if (formulario.accion === 'editar') await guardar('/' + tipo + '/' + r.id + '/', { ...cuerpo, version: r.version }, 'PATCH');
    else if (formulario.accion === 'finalizar') await guardar('/' + tipo + '/' + r.id + '/', { fecha_fin: cuerpo.fecha_fin, version: r.version }, 'PATCH');
    else await guardar('/' + tipo + '/' + r.id + '/' + formulario.accion + '/', { ...cuerpo, version: r.version });
    cambiarFormulario(null); lista.recargar(); cambiarAviso('Operación guardada con auditoría.');
  }
  let campos = config.campos;
  if (formulario?.accion === 'revocar') campos = [{ nombre: 'motivo', etiqueta: 'Motivo acreditado de revocación', maxLength: 160 }];
  if (formulario?.accion === 'finalizar') campos = [{ nombre: 'fecha_fin', etiqueta: 'Fin exclusivo del vínculo', tipo: 'date' }];
  return <section><h2>{config.titulo}</h2>{aviso && <p role="status">{aviso}</p>}
    <BarraListado listado={lista}>{puedeCrear && <button onClick={() => cambiarFormulario({ accion: 'crear' })}>Crear registro de {config.titulo.toLowerCase()}</button>}</BarraListado>
    {formulario?.accion === 'verificar' && <ComprobacionFacultad vinculo={formulario.registro} cancelar={() => cambiarFormulario(null)} completada={() => { cambiarFormulario(null); lista.recargar(); cambiarAviso('Comprobación registrada con auditoría.'); }} />}
    {formulario && formulario.accion !== 'verificar' && <FormularioRegistro key={tipo + formulario.accion + (formulario.registro?.id || '')} titulo={formulario.accion + ' · ' + config.titulo} campos={campos} inicial={formulario.accion === 'editar' ? Object.fromEntries(config.campos.map((c) => [c.nombre, formulario.registro[c.nombre]])) : formulario.accion === 'crear' ? config.inicial?.() || {} : {}} guardar={enviar} cancelar={() => cambiarFormulario(null)} />}
    <div className="tabla-contenedor"><table><thead><tr><th>Identificación</th><th>Información autorizada</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>
      {lista.datos.results.map((r) => <tr key={r.id}><td>{r.id} · {r.nombres ? r.nombres + ' ' + r.apellidos : r.codigo || 'Deportista ' + r.deportista}</td>
        <td>{r.telefono} {r.correo}{r.finalidad}{r.parentesco && <p>Parentesco declarado: {r.parentesco}</p>}{tipo === 'vinculos-acudientes' && <p>Contacto principal: {r.es_contacto_principal ? 'Sí' : 'No'}</p>}{r.referencia_evidencia}{r.criterio_conservacion && <p>Conservación: {r.criterio_conservacion}</p>}{r.procedimiento_supresion && <p>Supresión: {r.procedimiento_supresion}</p>}</td>
        <td>{tipo === 'vinculos-acudientes' && r.facultades?.length ? 'Decisiones por finalidad' : r.facultad_para_autorizar || r.decision || (r.activo === false ? 'Inactivo' : 'Registrado')}{r.facultades?.map((f) => <p key={f.id}>{f.alcance} · v{f.numero_version_texto}: {f.estado_efectivo}{f.resultado === 'verificada' && f.estado_efectivo !== 'verificada' && ' (requiere revisión de vigencia o alcance)'} · {f.metodo} · Hasta: {f.vigente_hasta || 'sin vencimiento acreditado'}</p>)}{r.facultad_vigente === false && <p>Facultad no vigente o pendiente de revisión; se conserva la declaración histórica.</p>}{r.revocada_en && ' · Revocada'}{r.fecha_fin && ' · Fin ' + r.fecha_fin}{r.vigente_hasta && ' · Vence ' + r.vigente_hasta}</td>
        <td className="acciones">
          {tipo === 'acudientes' && <button className="boton-secundario" onClick={() => cambiarFormulario({ accion: 'editar', registro: r })}>Editar contacto {r.id}</button>}
          {tipo === 'vinculos-acudientes' && !r.fecha_fin && <><button className="boton-secundario" disabled={r.control_facultades_disponible === false} onClick={() => cambiarFormulario({ accion: 'verificar', registro: r })}>Registrar comprobación de facultad {r.id}</button>{r.control_facultades_disponible === false && <p>Comprobaciones pendientes de migración autorizada.</p>}<button className="boton-secundario" onClick={() => cambiarFormulario({ accion: 'finalizar', registro: r })}>Finalizar vínculo {r.id}</button></>}
          {tipo === 'autorizaciones' && !r.revocada_en && <button className="boton-secundario" onClick={() => cambiarFormulario({ accion: 'revocar', registro: r })}>Revocar autorización {r.id}</button>}
          {tipo === 'politicas-datos' && usuario.rol === 'administrador' && <button className="boton-secundario" onClick={() => cambiarFormulario({ accion: 'editar', registro: r })}>Editar política {r.id}</button>}
        </td></tr>)}
    </tbody></table></div><PieListado listado={lista} />
  </section>;
}

export function AcudientesAutorizaciones() {
  const { usuario } = usarAutenticacion();
  const [parametros] = useSearchParams();
  const [tipo, cambiarTipo] = useState('acudientes');
  if (usuario.rol === 'profesor') return <section><h1>Acceso restringido</h1><p>Los datos de acudientes y autorizaciones corresponden a gestión institucional y operativa.</p></section>;
  const consulta = parametros.has('deportista') && ['vinculos-acudientes', 'autorizaciones'].includes(tipo) ? '?deportista=' + parametros.get('deportista') : '';
  return <section className="gestion"><h1>Acudientes y autorizaciones</h1>
    <p>El contacto no acredita representación. Cada autorización requiere finalidad, vigencia y evidencia cuando corresponda. Estos registros no habilitan acceso digital, publicación de imágenes, vídeos, biometría ni IA.</p>
    <p>Las políticas se definen con aprobación institucional; no hay plazos universales ni supresión automática.</p>
    <nav aria-label="Secciones de privacidad" className="acciones">{Object.entries(secciones).filter(([k]) => k !== 'politicas-datos' || usuario.rol === 'administrador').map(([k, c]) => <button key={k} className="boton-secundario" aria-pressed={tipo === k} onClick={() => cambiarTipo(k)}>{c.titulo}</button>)}</nav>
    <RegistroPrivado key={tipo + consulta} tipo={tipo} consulta={consulta} />
  </section>;
}
