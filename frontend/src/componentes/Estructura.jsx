import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { Marca } from './Marca.jsx';

const nombres = { profesor: 'Profesor', coordinador: 'Coordinador', administrador: 'Administrador', routesetter: 'Routesetter', deportista: 'Deportista', acudiente: 'Acudiente' };
export function Estructura() {
  const { usuario, salir, invalidarSesion } = usarAutenticacion();
  const [abierto, establecerAbierto] = useState(false);
  const [cerrando, establecerCerrando] = useState(false);
  const [error, establecerError] = useState('');
  const base = rutaDelRol(usuario.rol);
  const navegar = useNavigate();
  const operativo = ["administrador","coordinador","profesor"].includes(usuario.rol);

  async function cerrar() {
    establecerCerrando(true);
    establecerError('');
    try { await salir(); }
    catch (fallo) {
      if (fallo.estado === 401 || fallo.estado === 403) invalidarSesion();
      else establecerError(fallo.message);
    } finally { establecerCerrando(false); }
  }

  return <div className="estructura">
    <a className="saltar" href="#contenido">Saltar al contenido</a>
    <aside className="lateral">
      <Marca />
      <button className="alternar-menu" aria-expanded={abierto} aria-controls="navegacion" onClick={() => establecerAbierto(!abierto)}>Menú</button>
      <nav id="navegacion" className={abierto ? 'navegacion navegacion--abierta' : 'navegacion'} aria-label="Navegación principal">
        <span className="etiqueta">ESPACIO {nombres[usuario.rol].toUpperCase()}</span>
        <NavLink to={base} end onClick={() => establecerAbierto(false)}>Mi panel</NavLink>
        <NavLink to={base + '/perfil'} onClick={() => establecerAbierto(false)}>Mi cuenta</NavLink>
        {operativo && <NavLink to={base + '/curriculo'} onClick={() => establecerAbierto(false)}>Currículo</NavLink>}
        {(operativo || usuario.rol === 'routesetter') && <><NavLink to={base + '/biblioteca'} onClick={() => establecerAbierto(false)}>Biblioteca de ejercicios</NavLink><NavLink to={base + '/materiales'} onClick={() => establecerAbierto(false)}>Materiales docentes</NavLink></>}
        {['administrador','coordinador'].includes(usuario.rol) && <NavLink to={base + '/fuentes'} onClick={() => establecerAbierto(false)}>Fuentes e importación</NavLink>}
        {(usuario.rol === 'administrador' ? [['usuarios', 'Usuarios'], ['identidad', 'Identidad institucional'], ['coordinacion', 'Cargo de coordinador'], ['catalogos', 'Catálogos'], ['grupos', 'Grupos'], ['asignaciones', 'Asignaciones'], ['calendario', 'Calendario']] :
          usuario.rol === 'coordinador' ? [['grupos', 'Grupos de la escuela'], ['profesores', 'Profesores'], ['asignaciones', 'Asignaciones'], ['calendario', 'Calendario']] :
          operativo ? [['grupos', 'Mis grupos'], ['asignaciones', 'Mis asignaciones'], ['calendario', 'Calendario']] : []).map(([ruta, titulo]) =>
          <NavLink key={ruta} to={base + '/' + ruta} onClick={() => establecerAbierto(false)}>{titulo}</NavLink>)}
        {operativo && <><NavLink to={base + "/deportistas"} onClick={() => establecerAbierto(false)}>Deportistas</NavLink>
        <NavLink to={base + "/inscripciones"} onClick={() => establecerAbierto(false)}>Inscripciones</NavLink>
        <NavLink to={base + "/propuestas"} onClick={() => establecerAbierto(false)}>Propuestas</NavLink>
        {usuario.rol !== "profesor" && <NavLink to={base + "/autorizaciones"} onClick={() => establecerAbierto(false)}>Acudientes y autorizaciones</NavLink>}</>}
        <div className="lateral__nota">Entrenamos capacidades.<br />Acompañamos procesos.</div>
      </nav>
    </aside>
    <div className="area-principal">
      <header className="cabecera">
        <span>Escuela de escalada <span className="cabecera__punto">/</span> {nombres[usuario.rol]}</span>
        <div className="cabecera__cuenta">{usuario.roles?.length > 1 && <label>Espacio de trabajo<select aria-label="Espacio de trabajo" value={usuario.rol} onChange={(e) => navegar(rutaDelRol(e.target.value))}>{usuario.roles.map((r) => <option key={r} value={r}>{nombres[r]}</option>)}</select></label>}<span>{usuario.nombre}</span>
          <button className="boton-secundario" onClick={cerrar} disabled={cerrando}>{cerrando ? 'Cerrando…' : 'Cerrar sesión'}</button>
        </div>
      </header>
      {error && <p className="mensaje-error" role="alert">{error}</p>}
      <main id="contenido" tabIndex="-1"><Outlet /></main>
      <footer>Zona de Bloque · Gestión Deportiva y Pedagógica</footer>
    </div>
  </div>;
}
