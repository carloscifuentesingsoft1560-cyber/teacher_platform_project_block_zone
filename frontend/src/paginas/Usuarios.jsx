import { RolesCuenta, opcionesRoles } from '../componentes/RolesCuenta.jsx';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { usarAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { guardar } from '../api/gestion.js';
import { Campo, ErrorGestion, useListado, BarraListado, PieListado, BotonesFormulario } from '../componentes/Gestion.jsx';

const roles = opcionesRoles;
const vacio = { username: '', first_name: '', last_name: '', email: '', rol: 'profesor', contrasena: '' };
export function Usuarios() {
  const { usuario } = usarAutenticacion();
  const [parametros] = useSearchParams();
  const consulta = new URLSearchParams();
  for (const campo of ['rol', 'activo']) if (parametros.has(campo)) consulta.set(campo, parametros.get(campo));
  const listado = useListado('/usuarios/' + (consulta.size ? '?' + consulta : ''));
  const [formulario, cambiarFormulario] = useState(null);
  const [facultades, gestionar] = useState(null);
  const [error, cambiarError] = useState(null);
  const [aviso, cambiarAviso] = useState('');
  const [enviando, cambiarEnviando] = useState(false);
  const [recuperar, cambiarRecuperar] = useState(null);
  const [claveActual, cambiarClave] = useState('');
  const [enlace, cambiarEnlace] = useState(null);
  const campo = (nombre) => (valor) => cambiarFormulario({ ...formulario, [nombre]: valor });

  async function enviar(e) {
    e.preventDefault();
    if (enviando || !window.confirm(formulario.id ? '¿Confirmas los cambios de esta cuenta?' : '¿Confirmas la creación de esta cuenta?')) return;
    cambiarEnviando(true); cambiarError(null); cambiarAviso('');
    try {
      const datos = Object.fromEntries(Object.entries(formulario).filter(([k, v]) => k !== 'id' && k !== 'roles' && k !== 'is_active' && (k !== 'contrasena' || v)));
      await guardar('/usuarios/' + (formulario.id ? formulario.id + '/' : ''), datos, formulario.id ? 'PATCH' : 'POST');
      cambiarFormulario(null); listado.recargar(); cambiarAviso('Cuenta guardada correctamente.');
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }

  async function estado(cuenta) {
    if (enviando || !window.confirm('¿Confirmas ' + (cuenta.is_active ? 'desactivar' : 'activar') + ' esta cuenta?')) return;
    cambiarEnviando(true); cambiarError(null);
    try {
      await guardar('/usuarios/' + cuenta.id + '/', { is_active: !cuenta.is_active }, 'PATCH');
      listado.recargar(); cambiarAviso('Estado de la cuenta actualizado.');
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarEnviando(false); }
  }

  async function restablecer(e) {
    e.preventDefault(); if (enviando) return;
    cambiarEnviando(true); cambiarError(null); cambiarEnlace(null);
    try {
      const r = await guardar('/usuarios/' + recuperar.id + '/restablecer-acceso/', { contrasena_actual: claveActual });
      cambiarEnlace({ ...r, url: window.location.origin + r.ruta });
      cambiarRecuperar(null);
    } catch (fallo) { cambiarError(fallo); }
    finally { cambiarClave(''); cambiarEnviando(false); }
  }

  return <section className="gestion"><h1>Administración de usuarios</h1>
    <p>Cuentas institucionales y permisos de acceso. <Link to="/administracion/coordinacion">Historial y relevo del coordinador</Link></p>
    <ErrorGestion error={error} />{aviso && <p className="aviso" role="status">{aviso}</p>}
    <BarraListado listado={listado}><button onClick={() => { cambiarFormulario({ ...vacio }); cambiarError(null); cambiarEnlace(null); }} disabled={enviando}>Crear usuario</button></BarraListado>
    {facultades && <RolesCuenta cuenta={facultades} cerrar={() => gestionar(null)} actualizada={listado.recargar} />}
    {formulario && <form className="formulario-gestion" onSubmit={enviar} aria-label="Formulario de usuario">
      <h2>{formulario.id ? 'Editar usuario' : 'Crear usuario'}</h2>
      <div className="rejilla-formulario">
        <Campo etiqueta="Usuario" nombre="username" valor={formulario.username} cambiar={campo('username')} maxLength={150} />
        <Campo etiqueta="Nombres" nombre="first_name" valor={formulario.first_name} cambiar={campo('first_name')} requerido={false} maxLength={150} />
        <Campo etiqueta="Apellidos" nombre="last_name" valor={formulario.last_name} cambiar={campo('last_name')} requerido={false} maxLength={150} />
        <Campo etiqueta="Correo" nombre="email" tipo="email" valor={formulario.email} cambiar={campo('email')} requerido={false} maxLength={254} />
        <Campo etiqueta="Rol" nombre="rol" opciones={roles} valor={formulario.rol} cambiar={campo('rol')} disabled={formulario.id === usuario.id || formulario.roles?.length > 1} />
        {!formulario.id && <Campo etiqueta="Contraseña inicial (opcional)" nombre="contrasena" tipo="password" autoComplete="new-password" minLength={12} maxLength={256} valor={formulario.contrasena} cambiar={campo('contrasena')} requerido={false} />}
      </div>
      {!formulario.id && <p>Si omites la contraseña, genera después un enlace de restablecimiento para que la persona configure su acceso.</p>}
      <BotonesFormulario enviando={enviando} cancelar={() => cambiarFormulario(null)} />
    </form>}
    {recuperar && <form className="formulario-gestion" onSubmit={restablecer}>
      <h2>Restablecer acceso de {recuperar.username}</h2>
      <p>Confirma tu contraseña de administrador. Se generará un enlace de un solo uso válido durante 30 minutos. No se enviará correo automáticamente.</p>
      <Campo etiqueta="Tu contraseña actual" nombre="clave-actual" tipo="password" autoComplete="current-password" valor={claveActual} cambiar={cambiarClave} maxLength={256} />
      <BotonesFormulario texto="Confirmar y generar enlace" enviando={enviando} cancelar={() => { cambiarRecuperar(null); cambiarClave(''); }} />
    </form>}
    {enlace && <section className="formulario-gestion" aria-label="Enlace de recuperación">
      <h2>Enlace de un solo uso</h2><p>Compártelo únicamente con la persona autorizada por un canal privado. Vence a las {new Date(enlace.fecha_expira).toLocaleTimeString('es-CO')}.</p>
      <label>Enlace privado<input readOnly value={enlace.url} onFocus={(e) => e.target.select()} /></label>
      <button onClick={() => cambiarEnlace(null)}>Ocultar enlace</button>
    </section>}
    <div className="tabla-contenedor"><table><thead><tr><th>Usuario</th><th>Nombre</th><th>Rol</th><th>Estado</th><th>Acciones</th></tr></thead>
      <tbody>{listado.datos.results.map((cuenta) => <tr key={cuenta.id}>
        <td>{cuenta.username}</td><td>{[cuenta.first_name, cuenta.last_name].filter(Boolean).join(' ') || '—'}</td><td>{(cuenta.roles ?? [cuenta.rol]).map((r) => roles.find(([id]) => id === r)?.[1] || r).join(', ')}</td><td>{cuenta.is_active ? 'Activo' : 'Inactivo'}</td>
        <td className="acciones"><button disabled={cuenta.id === usuario.id || enviando} onClick={() => gestionar(cuenta)}>Facultades de {cuenta.username}</button><button className="boton-secundario" onClick={() => { cambiarFormulario({ ...cuenta }); cambiarError(null); }}>Editar {cuenta.username}</button>
          <button className="boton-secundario" disabled={cuenta.id === usuario.id || enviando} onClick={() => estado(cuenta)}>{cuenta.is_active ? 'Desactivar' : 'Activar'}</button>
          <button className="boton-secundario" disabled={!cuenta.is_active || enviando} onClick={() => { cambiarRecuperar(cuenta); cambiarClave(''); cambiarEnlace(null); }}>Restablecer acceso</button>
        </td></tr>)}</tbody></table></div>
    <PieListado listado={listado} />
  </section>;
}
