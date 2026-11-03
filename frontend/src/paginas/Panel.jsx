import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { solicitar } from '../api/cliente.js';
import { Estado } from '../componentes/Estado.jsx';
import { ResumenInstitucional } from '../componentes/ResumenInstitucional.jsx';

const contenido = {
  profesor: {
    titulo: 'Tu espacio para enseñar',
    descripcion: 'Planea cada encuentro y acompaña el aprendizaje de tu grupo.',
    tarjetas: [['01', 'Mis grupos', 'Aquí encontrarás los grupos que te asigne la escuela.'],
      ['02', 'Calendario', 'Consulta tus entrenamientos recurrentes en el calendario.'],
      ['03', 'Recursos pedagógicos', 'Material de apoyo para preparar tus próximos encuentros.']],
  },
  coordinador: {
    titulo: 'Acompañar cada proceso',
    descripcion: 'Una mirada compartida al trabajo pedagógico de la escuela.',
    tarjetas: [['01', 'Equipo de profesores', 'Gestiona todos los profesores, grupos, horarios y asignaciones de la escuela.'],
      ['02', 'Seguimiento pedagógico', 'Un espacio para observar sesiones y acompañar al equipo.'],
      ['03', 'Reportes de la escuela', 'Los reportes estarán disponibles al habilitar la operación.']],
  },
  administrador: {
    titulo: 'Organizar para crecer',
    descripcion: 'La base para conectar personas, grupos y aprendizaje.',
    tarjetas: [['01', 'Cuentas y acceso', 'Crea cuentas y gestiona sus permisos desde Usuarios.'],
      ['02', 'Organización deportiva', 'Gestiona disciplinas, niveles, grupos y asignaciones desde el menú.'],
      ['03', 'Currículo y documentos', 'Aquí se organizarán los contenidos institucionales autorizados.']],
  },
};

export function Panel() {
  const { usuario, invalidarSesion } = usarAutenticacion();
  const [datos, establecerDatos] = useState(null);
  const [error, establecerError] = useState('');
  const [intento, establecerIntento] = useState(0);
  useEffect(() => {
    let vigente = true;
    establecerDatos(null);
    establecerError('');
    solicitar('/paneles/' + usuario.rol + '/')
      .then((respuesta) => { if (vigente) establecerDatos(respuesta); })
      .catch((fallo) => {
        if (!vigente) return;
        if (fallo.estado === 401 || fallo.estado === 403) invalidarSesion();
        else establecerError(fallo.message);
      });
    return () => { vigente = false; };
  }, [usuario.rol, intento]); // La identidad se valida en cada solicitud al backend.

  if (error) return <Estado titulo="No pudimos cargar tu panel" accion={() => establecerIntento(intento + 1)}>{error}</Estado>;
  if (!datos) return <Estado titulo="Cargando tu espacio…" />;
  const vista = contenido[usuario.rol];
  return <>
    <section className="presentacion">
      <div><span className="etiqueta">MI PANEL / ZONA DE BLOQUE</span>
        <p className="saludo">Hola, {datos.nombre}</p>
        <h1>{vista.titulo}</h1><p>{vista.descripcion}</p>
      </div>
      <span className="insignia">Acceso institucional</span>
    </section>
    <nav className="accesos-panel" aria-label="Accesos de organización">
      <Link to={rutaDelRol(usuario.rol) + '/grupos'}>Consultar grupos</Link>
      <Link to={rutaDelRol(usuario.rol) + '/calendario'}>Consultar calendario</Link>
      {usuario.rol === 'administrador' && <Link to="/administracion/usuarios">Gestionar usuarios</Link>}
      {usuario.rol === 'coordinador' && <Link to="/coordinacion/profesores">Consultar profesores</Link>}
    </nav>
    {usuario.rol !== 'profesor' && <ResumenInstitucional />}
    <div className="seccion-titulo"><h2>Tu espacio de trabajo</h2><span>Primeros pasos</span></div>
    <section className="tarjetas" aria-label="Áreas de trabajo">
      {vista.tarjetas.map(([numero, titulo, descripcion]) => <article className="tarjeta" key={numero}>
        <span className="tarjeta__numero">{numero}</span><span className="etiqueta tarjeta__estado">ÁREA DE TRABAJO</span>
        <h3>{titulo}</h3><p>{descripcion}</p>
      </article>)}
    </section>
    <section className="nota-inicial"><h2>Todo comienza con una buena base.</h2>
      <p>{datos.mensaje}</p>
    </section>
  </>;
}

export function Perfil() {
  const { usuario } = usarAutenticacion();
  return <section className="perfil"><span className="etiqueta">MI CUENTA</span><h1>Tu perfil institucional</h1>
    <dl><dt>Nombre</dt><dd>{usuario.nombre}</dd><dt>Usuario</dt><dd>{usuario.username}</dd><dt>Rol</dt><dd>{usuario.rol}</dd></dl>
    <p>Para solicitar cambios en tu cuenta, contacta con la administración.</p>
  </section>;
}
