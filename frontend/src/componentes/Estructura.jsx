
import { useState } from 'react';

import {
  NavLink,
  Outlet,
  useNavigate,
} from 'react-router-dom';

import {
  usarAutenticacion,
  rutaDelRol,
} from '../autenticacion/ContextoAutenticacion.jsx';

import { Marca } from './Marca.jsx';

const nombres = {
  profesor: 'Profesor',
  coordinador: 'Coordinador',
  administrador: 'Administrador',
  routesetter: 'Routesetter',
  deportista: 'Deportista',
  acudiente: 'Acudiente',
};

export function Estructura() {
  const {
    usuario,
    salir,
    invalidarSesion,
  } = usarAutenticacion();

  const [abierto, establecerAbierto] = useState(false);
  const [cerrando, establecerCerrando] = useState(false);
  const [error, establecerError] = useState('');

  const navegar = useNavigate();
  const base = rutaDelRol(usuario.rol);

  const operativo = [
    'administrador',
    'coordinador',
    'profesor',
  ].includes(usuario.rol);

  const gestor = [
    'administrador',
    'coordinador',
  ].includes(usuario.rol);

  const accesoBiblioteca =
    operativo || usuario.rol === 'routesetter';

  const opcionesOrganizacion =
    usuario.rol === 'administrador'
      ? [
          ['usuarios', 'Usuarios'],
          ['identidad', 'Identidad institucional'],
          ['coordinacion', 'Cargo de coordinador'],
          ['catalogos', 'Catálogos'],
          ['grupos', 'Grupos'],
          ['asignaciones', 'Asignaciones'],
          ['calendario', 'Calendario'],
        ]
      : usuario.rol === 'coordinador'
        ? [
            ['grupos', 'Grupos de la escuela'],
            ['profesores', 'Profesores'],
            ['asignaciones', 'Asignaciones'],
            ['calendario', 'Calendario'],
          ]
        : operativo
          ? [
              ['grupos', 'Mis grupos'],
              ['asignaciones', 'Mis asignaciones'],
              ['calendario', 'Calendario'],
            ]
          : [];

  function cerrarMenu() {
    establecerAbierto(false);
  }

  async function cerrarSesion() {
    establecerCerrando(true);
    establecerError('');

    try {
      await salir();
    } catch (fallo) {
      if (
        fallo.estado === 401 ||
        fallo.estado === 403
      ) {
        invalidarSesion();
      } else {
        establecerError(fallo.message);
      }
    } finally {
      establecerCerrando(false);
    }
  }

  return (
    <div className="estructura">
      <a
        className="saltar"
        href="#contenido"
      >
        Saltar al contenido
      </a>

      <aside className="lateral">
        <Marca />

        <button
          className="alternar-menu"
          aria-expanded={abierto}
          aria-controls="navegacion"
          onClick={() => establecerAbierto(!abierto)}
        >
          Menú
        </button>

        <nav
          id="navegacion"
          className={
            abierto
              ? 'navegacion navegacion--abierta'
              : 'navegacion'
          }
          aria-label="Navegación principal"
        >
          <span className="etiqueta">
            ESPACIO {nombres[usuario.rol].toUpperCase()}
          </span>

          <NavLink
            to={base}
            end
            onClick={cerrarMenu}
          >
            Mi panel
          </NavLink>

          <NavLink
            to={base + '/perfil'}
            onClick={cerrarMenu}
          >
            Mi cuenta
          </NavLink>

          {operativo && (
            <>
              <NavLink
                to={base + '/sesiones'}
                onClick={cerrarMenu}
              >
                Sesiones
              </NavLink>

              <NavLink
                to={base + '/curriculo'}
                onClick={cerrarMenu}
              >
                Currículo
              </NavLink>
            </>
          )}

          {accesoBiblioteca && (
            <>
              <NavLink
                to={base + '/biblioteca'}
                onClick={cerrarMenu}
              >
                Biblioteca de ejercicios
              </NavLink>

              <NavLink
                to={base + '/materiales'}
                onClick={cerrarMenu}
              >
                Materiales docentes
              </NavLink>
            </>
          )}

          {gestor && (
            <NavLink
              to={base + '/fuentes'}
              onClick={cerrarMenu}
            >
              Fuentes e importación
            </NavLink>
          )}

          {opcionesOrganizacion.map(
            ([ruta, titulo]) => (
              <NavLink
                key={ruta}
                to={base + '/' + ruta}
                onClick={cerrarMenu}
              >
                {titulo}
              </NavLink>
            )
          )}

          {operativo && (
            <>
              <NavLink
                to={base + '/deportistas'}
                onClick={cerrarMenu}
              >
                Deportistas
              </NavLink>

              <NavLink
                to={base + '/inscripciones'}
                onClick={cerrarMenu}
              >
                Inscripciones
              </NavLink>

              <NavLink
                to={base + '/propuestas'}
                onClick={cerrarMenu}
              >
                Propuestas
              </NavLink>

              {usuario.rol !== 'profesor' && (
                <NavLink
                  to={base + '/autorizaciones'}
                  onClick={cerrarMenu}
                >
                  Acudientes y autorizaciones
                </NavLink>
              )}
            </>
          )}

          <div className="lateral__nota">
            Entrenamos capacidades.
            <br />
            Acompañamos procesos.
          </div>
        </nav>
      </aside>

      <div className="area-principal">
        <header className="cabecera">
          <span>
            Escuela de escalada
            <span className="cabecera__punto">
              /
            </span>
            {nombres[usuario.rol]}
          </span>

          <div className="cabecera__cuenta">
            {usuario.roles?.length > 1 && (
              <label>
                Espacio de trabajo

                <select
                  aria-label="Espacio de trabajo"
                  value={usuario.rol}
                  onChange={(evento) =>
                    navegar(
                      rutaDelRol(evento.target.value)
                    )
                  }
                >
                  {usuario.roles.map((rol) => (
                    <option
                      key={rol}
                      value={rol}
                    >
                      {nombres[rol]}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <span>{usuario.nombre}</span>

            <button
              className="boton-secundario"
              onClick={cerrarSesion}
              disabled={cerrando}
            >
              {cerrando
                ? 'Cerrando…'
                : 'Cerrar sesión'}
            </button>
          </div>
        </header>

        {error && (
          <p
            className="mensaje-error"
            role="alert"
          >
            {error}
          </p>
        )}

        <main
          id="contenido"
          tabIndex="-1"
        >
          <Outlet />
        </main>

        <footer>
          Zona de Bloque · Gestión Deportiva y Pedagógica
        </footer>
      </div>
    </div>
  );
}
