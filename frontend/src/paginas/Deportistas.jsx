import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar } from '../api/gestion.js';
import { solicitar } from '../api/cliente.js';
import { ErrorGestion, useListado, BarraListado, PieListado, Campo } from '../componentes/Gestion.jsx';
import { FormularioRegistro } from '../componentes/FormularioRegistro.jsx';
import { CamposDocumento, useTiposDocumento } from '../componentes/DocumentoDeportista.jsx';
import { GestionDocumentoFicha } from '../componentes/GestionDocumentoFicha.jsx';
import { BusquedaDocumento } from '../componentes/BusquedaDocumento.jsx';
import { SelectorCatalogo } from '../componentes/SelectorCatalogo.jsx';

export function Deportistas() {
  const { usuario } = usarAutenticacion();
  const gestor = usuario.rol !== 'profesor';
  const [parametros, cambiarParametros] = useSearchParams();
  const lista = useListado('/deportistas/?' + parametros.toString());
  const catalogo = useTiposDocumento(gestor);
  const [documento, cambiarDocumento] = useState({ tipo_documento: null, numero_documento: '', pais_emisor: '' });
  const [buscador, cambiarBuscador] = useState(false);
  const [resultado, cambiarResultado] = useState(null);
  const [formulario, cambiarFormulario] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [error, cambiarError] = useState(null);
  const campos = [{ nombre: 'nombres', etiqueta: 'Nombres', maxLength: 100 }, { nombre: 'apellidos', etiqueta: 'Apellidos', maxLength: 100 },
    { nombre: 'fecha_nacimiento', etiqueta: 'Fecha de nacimiento', tipo: 'date' }];
  if (formulario?.identificador_publico) campos.push(
    { nombre: 'estado', etiqueta: 'Estado', opciones: [['activo', 'Activo'], ['inactivo', 'Inactivo'], ['archivado', 'Archivado']] },
    { nombre: 'motivo_estado', etiqueta: 'Motivo administrativo', requerido: false, maxLength: 160 });
  async function enviar(datos) {
    const uuid = formulario.identificador_publico;
    const cuerpo = { nombres: datos.nombres, apellidos: datos.apellidos, fecha_nacimiento: datos.fecha_nacimiento };
    if (uuid) Object.assign(cuerpo, { version: formulario.version, estado: datos.estado, motivo_estado: datos.motivo_estado || '' });
    else if (documento.tipo_documento) Object.assign(cuerpo, documento);
    await guardar('/deportistas/' + (uuid ? uuid + '/' : ''), cuerpo, uuid ? 'PATCH' : 'POST');
    cambiarFormulario(null); cambiarResultado(null); lista.recargar(); cambiarAviso('Ficha guardada. La identidad se conserva entre grupos y periodos.');
  }
  function filtrar(campo, valor) {
    cambiarResultado(null);
    lista.cambiarPagina(1);
    const nuevo = new URLSearchParams(parametros);
    if (valor) nuevo.set(campo, valor); else nuevo.delete(campo);
    cambiarParametros(nuevo);
  }
  return <section className="gestion deportistas"><h1>Deportistas</h1>
    <p>{gestor ? 'Identidad permanente y trayectoria deportiva. No crea cuentas de acceso.' : 'Consulta limitada a deportistas de tus grupos vigentes.'}</p>
    <ErrorGestion error={error} /><ErrorGestion error={catalogo.error} />{aviso && <p role="status">{aviso}</p>}
    <BarraListado listado={{ ...lista, buscar: (texto) => { cambiarResultado(null); lista.buscar(texto); } }} etiquetaBusqueda="Buscar por nombre o apellido">{gestor && <><button onClick={() => { cambiarDocumento({ tipo_documento: null, numero_documento: '', pais_emisor: '' }); cambiarFormulario({}); }}>Crear deportista</button><button className="boton-secundario" onClick={() => cambiarBuscador(!buscador)}>Buscar por documento</button></>}</BarraListado>
    {gestor && buscador && <BusquedaDocumento tipos={catalogo.tipos} resultado={cambiarResultado} cancelar={() => cambiarBuscador(false)} />}
    {resultado && <p role="status">{resultado.count} coincidencias documentales. <button className="boton-secundario" onClick={() => cambiarResultado(null)}>Limpiar búsqueda documental</button></p>}
    <div className="rejilla-formulario">
      <Campo etiqueta="Filtrar estado" nombre="filtro-estado" requerido={false} valor={parametros.get('estado') || ''} cambiar={(v) => filtrar('estado', v)} opciones={['activo', 'inactivo', 'archivado'].map((x) => [x, x])} />
      {[['grupo', 'grupos'], ['periodo', 'periodos'], ['disciplina', 'disciplinas'], ['nivel', 'niveles']].map(([campo, catalogo]) =>
        <SelectorCatalogo key={campo} etiqueta={'Filtrar ' + campo} nombre={'filtro-' + campo} ruta={'/organizacion/' + catalogo + '/'} valor={parametros.get(campo) || ''} cambiar={(v) => filtrar(campo, v)} />)}
    </div>
    {formulario && <FormularioRegistro key={formulario.id || 'nuevo'} titulo={formulario.id ? 'Editar ficha de deportista' : 'Crear ficha de deportista'} campos={campos} inicial={formulario} guardar={enviar} cancelar={() => cambiarFormulario(null)}>
      {formulario.id ? <p>Documento: {formulario.documento_presentacion || 'Documento pendiente'}. Los cambios se realizan desde la ficha individual con motivo y versión.</p> : <CamposDocumento datos={documento} cambiar={cambiarDocumento} tipos={catalogo.tipos} prefijo="alta" />}
    </FormularioRegistro>}
    <div className="tabla-contenedor"><table><thead><tr><th>Documento de identidad</th><th>Deportista</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>{(resultado || lista.datos).results.map((p) => <tr key={p.identificador_publico}><td className="documento-celda">{p.documento_presentacion || 'Documento pendiente'}</td><td>{p.nombres} {p.apellidos}</td><td>{p.estado}</td><td className="acciones"><div className="acciones-deportista">
        <Link to={rutaDelRol(usuario.rol) + "/deportistas/" + p.identificador_publico}>Ver ficha individual</Link>
        <Link to={rutaDelRol(usuario.rol) + '/inscripciones?deportista=' + p.id}>Inscripciones e historial</Link>
        {gestor && <><button className="boton-secundario" onClick={() => cambiarFormulario(p)}>Editar ficha de {p.nombres}</button><Link to={rutaDelRol(usuario.rol) + '/autorizaciones?deportista=' + p.id}>Acudientes y autorizaciones</Link></>}
      </div></td></tr>)}</tbody></table></div>{!resultado && <PieListado listado={lista} />}
    {!lista.error && !gestor && <p>No se muestran números completos, fecha de nacimiento ni datos de acudientes.</p>}
  </section>;
}

export function FichaDeportista() {
  const { uuid } = useParams();
  const { usuario } = usarAutenticacion();
  const [ficha, cambiarFicha] = useState(null);
  const [error, cambiarError] = useState(null);
  const trayectoria = useListado('/deportistas/' + uuid + '/trayectoria/');
  useEffect(() => {
    let vigente = true;
    cambiarFicha(null); cambiarError(null);
    solicitar('/deportistas/' + uuid + '/').then((r) => { if (vigente) cambiarFicha(r); }).catch((e) => { if (vigente) cambiarError(e); });
    return () => { vigente = false; };
  }, [uuid]);
  return <section className="gestion"><h1>Ficha individual del deportista</h1><ErrorGestion error={error} />
    {!ficha && !error && <p role="status">Cargando ficha…</p>}
    {ficha && <><h2>{ficha.nombres} {ficha.apellidos}</h2><dl><dt>Documento de identidad</dt><dd>{ficha.documento_presentacion || 'Documento pendiente'}</dd><dt>Estado</dt><dd>{ficha.estado}</dd>
      {ficha.fecha_nacimiento && <><dt>Fecha de nacimiento</dt><dd>{ficha.fecha_nacimiento}</dd></>}</dl>
      {usuario.rol !== 'profesor' && <GestionDocumentoFicha ficha={ficha} actualizar={cambiarFicha} />}
      <Link to={rutaDelRol(usuario.rol) + '/inscripciones?deportista=' + ficha.id}>Gestionar o consultar inscripciones autorizadas</Link>
      <h2>Trayectoria autorizada</h2><BarraListado listado={trayectoria} />
      <ul>{trayectoria.datos.results.map((i) => <li key={i.id}>{i.nombre_grupo} · {i.nivel} · {i.periodo} · {i.fecha_ingreso} — {i.fecha_salida || 'Fin del periodo'} · {i.estado}</li>)}</ul><PieListado listado={trayectoria} />
    </>}
  </section>;
}
