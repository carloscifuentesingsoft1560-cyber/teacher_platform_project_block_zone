import { Identidades } from './paginas/Identidades.jsx';
import { Curriculo, Biblioteca, MaterialesDocentes, FuentesCurriculares } from './paginas/ContenidoDeportivo.jsx';
import { Deportistas, FichaDeportista } from './paginas/Deportistas.jsx';
import { Inscripciones } from './paginas/Inscripciones.jsx';
import { Propuestas } from './paginas/Propuestas.jsx';
import { AcudientesAutorizaciones } from './paginas/AcudientesAutorizaciones.jsx';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from './autenticacion/ContextoAutenticacion.jsx';
import { Estructura } from './componentes/Estructura.jsx';
import { Estado } from './componentes/Estado.jsx';
import { Ingreso } from './paginas/Ingreso.jsx';
import { Panel, Perfil } from './paginas/Panel.jsx';
import { Usuarios } from './paginas/Usuarios.jsx';
import { Coordinacion } from './paginas/Coordinacion.jsx';
import { Catalogos } from './paginas/Catalogos.jsx';
import { Grupos } from './paginas/Grupos.jsx';
import { Asignaciones } from './paginas/Asignaciones.jsx';
import { Calendario } from './paginas/Calendario.jsx';
import { Profesores } from './paginas/Profesores.jsx';
import { RestablecerAcceso } from './paginas/RestablecerAcceso.jsx';

function RutaPrivada({ rol }) {
  const { usuario } = usarAutenticacion();
  if (!usuario) return <Navigate to="/ingresar" replace />;
  if (!(usuario.roles ?? [usuario.rol]).includes(rol)) return <Estado titulo="Acceso restringido">Tu cuenta no tiene permiso para abrir este espacio.</Estado>;
  return <Outlet />;
}

function Inicio() {
  const { usuario } = usarAutenticacion();
  return <Navigate to={usuario ? rutaDelRol(usuario.rol) : '/ingresar'} replace />;
}

export function Aplicacion() {
  const { cargando, error, restaurar } = usarAutenticacion();
  if (cargando) return <Estado titulo="Comprobando tu sesión…" />;
  if (error) return <Estado titulo="Servidor no disponible" accion={restaurar}>{error}</Estado>;
  return <Routes>
    <Route path="/ingresar" element={<Ingreso />} />
    <Route path="/restablecer-acceso" element={<RestablecerAcceso />} />
    {[['profesor', 'profesor'], ['coordinacion', 'coordinador'], ['administracion', 'administrador']].map(([ruta, rol]) =>
      <Route key={rol} element={<RutaPrivada rol={rol} />}>
        <Route path={'/' + ruta} element={<Estructura />}>
          <Route path="curriculo" element={<Curriculo />} /><Route path="biblioteca" element={<Biblioteca />} /><Route path="materiales" element={<MaterialesDocentes />} />
          {rol !== 'profesor' && <Route path="fuentes" element={<FuentesCurriculares />} />}
          <Route path="deportistas" element={<Deportistas />} /><Route path="deportistas/:uuid" element={<FichaDeportista />} /><Route path="inscripciones" element={<Inscripciones />} /><Route path="propuestas" element={<Propuestas />} />
          {rol !== "profesor" && <Route path="autorizaciones" element={<AcudientesAutorizaciones />} />}
          <Route index element={<Panel />} /><Route path="perfil" element={<Perfil />} />
          <Route path="grupos" element={<Grupos />} />
          <Route path="asignaciones" element={<Asignaciones />} />
          <Route path="calendario" element={<Calendario />} />
          {rol === 'administrador' && <><Route path="usuarios" element={<Usuarios />} /><Route path="identidad" element={<Identidades />} /><Route path="catalogos" element={<Catalogos />} /><Route path="coordinacion" element={<Coordinacion />} /><Route path="profesores" element={<Profesores />} /></>}
          {rol === 'coordinador' && <Route path="profesores" element={<Profesores />} />}
        </Route>
      </Route>)}
    {['routesetter','deportista','acudiente'].map((rol) => <Route key={rol} element={<RutaPrivada rol={rol} />}><Route path={'/'+rol} element={<Estructura />}><Route index element={<Estado titulo="Espacio institucional">Tu cuenta está vinculada a este rol. Sus módulos se habilitarán en las siguientes etapas.</Estado>} /><Route path="perfil" element={<Perfil />} />{rol === 'routesetter' && <><Route path="biblioteca" element={<Biblioteca />} /><Route path="materiales" element={<MaterialesDocentes />} /></>}</Route></Route>)}
    <Route path="/" element={<Inicio />} />
    <Route path="*" element={<Estado titulo="Página no encontrada"><a href="/">Volver a mi espacio</a></Estado>} />
  </Routes>;
}
