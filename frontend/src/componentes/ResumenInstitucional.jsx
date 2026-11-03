import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { solicitar } from '../api/cliente.js';
import { todas, fechaBogota } from '../api/gestion.js';
import { Campo, ErrorGestion } from './Gestion.jsx';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';

export function ResumenInstitucional() {
  const { usuario } = usarAutenticacion();
  const base = rutaDelRol(usuario.rol);
  const [catalogos, establecerCatalogos] = useState({ periodos: [], disciplinas: [], niveles: [] });
  const [filtros, cambiarFiltros] = useState({ fecha: fechaBogota(), periodo: '', disciplina: '', nivel: '' });
  const [consulta, cambiarConsulta] = useState({});
  const [datos, establecerDatos] = useState(null);
  const [error, establecerError] = useState(null);
  const [errorCatalogos, establecerErrorCatalogos] = useState(null);
  const [cargando, establecerCargando] = useState(true);
  useEffect(() => {
    let vigente = true;
    Promise.all(['periodos', 'disciplinas', 'niveles'].map((tipo) => todas('/organizacion/' + tipo + '/')))
      .then(([periodos, disciplinas, niveles]) => { if (vigente) establecerCatalogos({ periodos, disciplinas, niveles }); })
      .catch((e) => { if (vigente) establecerErrorCatalogos(e); });
    return () => { vigente = false; };
  }, []);
  useEffect(() => {
    let vigente = true;
    establecerCargando(true); establecerError(null);
    const parametros = new URLSearchParams(consulta);
    solicitar('/paneles/' + usuario.rol + '/resumen/?' + parametros)
      .then((r) => { if (vigente) establecerDatos(r); })
      .catch((e) => { if (vigente) { establecerError(e); establecerDatos(null); } })
      .finally(() => { if (vigente) establecerCargando(false); });
    return () => { vigente = false; };
  }, [usuario.rol, consulta]);
  const campo = (nombre) => (valor) => cambiarFiltros({ ...filtros, [nombre]: valor, ...(nombre === 'disciplina' ? { nivel: '' } : {}) });
  const listaProfesores = usuario.rol === 'administrador' ? base + '/usuarios?rol=profesor' : base + '/profesores';
  function enlace(ruta, extras = {}, incluirFiltros = false) {
    const parametros = { ...(incluirFiltros && datos ? { ...datos.filtros, fecha: datos.fecha_corte } : {}), ...extras };
    const texto = new URLSearchParams(Object.fromEntries(Object.entries(parametros).filter(([, valor]) => valor !== null && valor !== undefined)));
    return ruta + (ruta.includes('?') ? '&' : '?') + texto;
  }
  return <section className="gestion" aria-label="Resumen institucional">
    <h2>{usuario.rol === 'administrador' ? 'Tablero general de la empresa' : 'Resumen operativo de la escuela'}</h2>
    <form className="formulario-gestion" onSubmit={(e) => { e.preventDefault(); cambiarConsulta(Object.fromEntries(Object.entries(filtros).filter(([, valor]) => valor !== ''))); }}>
      <div className="rejilla-formulario">
        <Campo etiqueta="Fecha de corte" nombre="resumen-fecha" tipo="date" valor={filtros.fecha} cambiar={campo('fecha')} />
        <Campo etiqueta="Periodo" nombre="resumen-periodo" valor={filtros.periodo} cambiar={campo('periodo')} requerido={false} opciones={catalogos.periodos.map((p) => [p.id, p.nombre])} />
        <Campo etiqueta="Disciplina" nombre="resumen-disciplina" valor={filtros.disciplina} cambiar={campo('disciplina')} requerido={false} opciones={catalogos.disciplinas.map((p) => [p.id, p.nombre])} />
        <Campo etiqueta="Nivel" nombre="resumen-nivel" valor={filtros.nivel} cambiar={campo('nivel')} requerido={false} opciones={catalogos.niveles.filter((n) => !filtros.disciplina || n.disciplina === Number(filtros.disciplina)).map((n) => [n.id, n.nombre])} />
      </div><button disabled={cargando}>Aplicar filtros</button>
    </form>
    <ErrorGestion error={error || errorCatalogos} />
    {cargando && <p role="status">Cargando estadísticas reales…</p>}
    {datos && !cargando && <>
      <p>Corte: {datos.fecha_corte} · Estado actual de cuentas y grupos. Los filtros se aplican a grupos y asignaciones; los profesores activos/inactivos representan toda la institución.</p>
      <div className="tarjetas">
        {[
          ['Profesores activos', datos.profesores.activos, enlace(listaProfesores, { activo: 'true' })],
          ['Profesores inactivos', datos.profesores.inactivos, enlace(listaProfesores, { activo: 'false' })],
          ['Profesores sin grupo operativo (filtros)', datos.profesores.sin_grupo, enlace(base + '/profesores', { activo: 'true', sin_grupo: 'true' }, true)],
          ['Grupos activos (filtros)', datos.grupos.activos, enlace(base + '/grupos', { activo: 'true' }, true)],
          ['Grupos inactivos (filtros)', datos.grupos.inactivos, enlace(base + '/grupos', { activo: 'false' }, true)],
          ['Periodos (filtro de periodo)', datos.periodos.total, usuario.rol === 'administrador' ? enlace(base + '/catalogos', { tipo: 'periodos', periodo: datos.filtros.periodo }) : base + '/calendario'],
          ['Asignaciones vigentes (filtros)', datos.asignaciones.vigentes, enlace(base + '/asignaciones', { estado: 'vigentes' }, true)],
          ['Asignaciones operativas (filtros)', datos.asignaciones.operativas, enlace(base + '/asignaciones', { estado: 'operativas' }, true)],
        ].map(([titulo, valor, ruta]) => <article className="tarjeta" key={titulo}><h3>{titulo}</h3><p><strong>{valor}</strong></p><Link to={ruta}>Consultar módulo</Link></article>)}
        <article className="tarjeta"><h3>Coordinación activa</h3><p>{datos.coordinacion.actual?.nombre || (datos.coordinacion.estado === 'inconsistente' ? 'Configuración que requiere revisión' : 'Vacante')}</p>
          {usuario.rol === 'administrador' && <Link to="/administracion/coordinacion">Historial y relevo</Link>}
        </article>
      </div>
      <h3>Resumen por disciplina y nivel</h3>
      <div className="tabla-contenedor"><table><thead><tr><th>Catálogo</th><th>Nombre</th><th>Grupos (filtros)</th><th>Activos</th></tr></thead><tbody>
        {[...datos.disciplinas.map((d) => ({ ...d, tipo: 'Disciplina' })), ...datos.niveles.map((n) => ({ ...n, tipo: 'Nivel' }))].map((r) =>
          <tr key={r.tipo + r.id}><td>{r.tipo}</td><td>{r.nombre}</td><td>{r.total}</td><td>{r.activos}</td></tr>)}
      </tbody></table></div>
      <p>Los indicadores de sesiones, asistencia, cumplimiento y valoraciones se incorporarán cuando existan esos módulos y sus reglas aprobadas.</p>
    </>}
  </section>;
}
