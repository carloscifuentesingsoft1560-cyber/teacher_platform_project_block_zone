import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion } from '../componentes/Gestion.jsx';
import { Marca } from '../componentes/Marca.jsx';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';

export function RestablecerAcceso() {
  const { invalidarSesion } = usarAutenticacion();
  const ubicacion = useLocation();
  const navegar = useNavigate();
  const [token, cambiarToken] = useState(() => new URLSearchParams(ubicacion.hash.slice(1)).get('token') || '');
  const [contrasena, cambiarClave] = useState('');
  const [repeticion, cambiarRepeticion] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  const [completado, cambiarCompletado] = useState(false);
  const [error, cambiarError] = useState(null);
  useEffect(() => {
    if (ubicacion.hash) navegar('/restablecer-acceso', { replace: true });
  }, []);
  async function enviar(e) {
    e.preventDefault();
    if (enviando) return;
    if (contrasena !== repeticion) { cambiarError(new Error('Las contraseñas no coinciden.')); return; }
    cambiarEnviando(true); cambiarError(null);
    try {
      await guardar('/recuperacion/confirmar/', { token, contrasena });
      cambiarCompletado(true); cambiarToken(''); invalidarSesion();
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarClave(''); cambiarRepeticion(''); cambiarEnviando(false); }
  }
  return <main className="recuperacion gestion"><Marca /><h1>Restablecer acceso</h1>
    {completado ? <><p role="status">Tu contraseña se actualizó. Las sesiones anteriores quedaron invalidadas.</p><Link to="/ingresar">Ir al inicio de sesión</Link></> :
      !token ? <p>Necesitas un enlace vigente proporcionado por la administración.</p> :
      <form onSubmit={enviar} className="formulario-gestion"><p>Elige una contraseña de al menos 12 caracteres. El enlace se puede usar una sola vez.</p>
        <ErrorGestion error={error} />
        <Campo etiqueta="Nueva contraseña" nombre="nueva-clave" tipo="password" autoComplete="new-password" minLength={12} maxLength={256} valor={contrasena} cambiar={cambiarClave} />
        <Campo etiqueta="Repetir contraseña" nombre="repetir-clave" tipo="password" autoComplete="new-password" minLength={12} maxLength={256} valor={repeticion} cambiar={cambiarRepeticion} />
        <button disabled={enviando}>{enviando ? 'Actualizando…' : 'Confirmar nueva contraseña'}</button>
      </form>}
  </main>;
}
