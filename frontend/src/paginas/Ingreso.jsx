import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { usarAutenticacion, rutaDelRol } from '../autenticacion/ContextoAutenticacion.jsx';
import { Marca } from '../componentes/Marca.jsx';

export function Ingreso() {
  const { usuario, ingresar } = usarAutenticacion();
  const [nombre, establecerNombre] = useState('');
  const [contrasena, establecerContrasena] = useState('');
  const [enviando, establecerEnviando] = useState(false);
  const [error, establecerError] = useState('');
  if (usuario) return <Navigate to={rutaDelRol(usuario.rol)} replace />;

  async function enviar(evento) {
    evento.preventDefault();
    if (enviando) return;
    establecerEnviando(true);
    establecerError('');
    try { await ingresar(nombre, contrasena); }
    catch (fallo) { establecerError(fallo.message); }
    finally { establecerContrasena(''); establecerEnviando(false); }
  }

  return <main className="ingreso">
    <section className="ingreso__identidad">
      <Marca />
      <div><span className="etiqueta">DEPORTE · APRENDIZAJE · COMUNIDAD</span>
        <h1>Cada movimiento<br />es un nuevo<br /><em>aprendizaje.</em></h1>
        <p>Un espacio para acompañar el desarrollo deportivo y pedagógico de nuestra escuela.</p>
      </div>
      <span className="ingreso__pie">ESCUELA DE ESCALADA / ZONA DE BLOQUE</span>
    </section>
    <section className="ingreso__formulario">
      <div className="formulario">
        <span className="etiqueta">BIENVENIDO A TU ESPACIO</span>
        <h2>Ingresar</h2><p>Accede con tu cuenta institucional.</p>
        <form onSubmit={enviar} aria-busy={enviando}>
          <label htmlFor="usuario">Usuario</label>
          <input id="usuario" name="username" autoComplete="username" value={nombre} onChange={(e) => establecerNombre(e.target.value)} required maxLength={150} disabled={enviando} />
          <label htmlFor="contrasena">Contraseña</label>
          <input id="contrasena" name="password" type="password" autoComplete="current-password" value={contrasena} onChange={(e) => establecerContrasena(e.target.value)} required maxLength={256} disabled={enviando} />
          {error && <p className="mensaje-error" role="alert">{error}</p>}
          <button className="boton-principal" type="submit" disabled={enviando}>{enviando ? 'Ingresando…' : 'Ingresar a mi espacio →'}</button>
        </form>
        <p className="ayuda">Si necesitas una cuenta o recuperar tu acceso, contacta con la administración de la escuela.</p>
      </div>
    </section>
  </main>;
}
