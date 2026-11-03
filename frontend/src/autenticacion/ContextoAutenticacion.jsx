import { useLocation } from 'react-router-dom';
import { createContext, useContext, useEffect, useState } from 'react';
import * as api from '../api/cliente.js';

const ContextoAutenticacion = createContext(null);
export const rutaDelRol = (rol) => ({ profesor: '/profesor', coordinador: '/coordinacion', administrador: '/administracion', routesetter: '/routesetter', deportista: '/deportista', acudiente: '/acudiente' }[rol]);

export function ProveedorAutenticacion({ children }) {
  const [cuenta, establecerUsuario] = useState(null);
  const ubicacion = useLocation();
  const roles = cuenta?.roles ?? (cuenta ? [cuenta.rol] : []);
  const espacio = {profesor: "profesor", coordinacion: "coordinador", administracion: "administrador", routesetter: "routesetter", deportista: "deportista", acudiente: "acudiente"}[ubicacion.pathname.split("/")[1]];
  const usuario = cuenta ? {...cuenta, rol_principal: cuenta.rol, roles, rol: roles.includes(espacio) ? espacio : roles.includes(cuenta.rol) ? cuenta.rol : roles[0]} : null;
  const [cargando, establecerCargando] = useState(true);
  const [error, establecerError] = useState('');

  async function restaurar() {
    establecerCargando(true);
    establecerError('');
    try {
      const datos = await api.solicitar('/autenticacion/sesion/');
      establecerUsuario(datos.usuario);
    } catch (fallo) {
      establecerUsuario(null);
      if (fallo.estado !== 401 && fallo.estado !== 403) establecerError(fallo.message);
    } finally {
      establecerCargando(false);
    }
  }

  useEffect(() => { restaurar(); }, []);

  useEffect(() => {
    async function refrescar() {
      try { const r = await api.solicitar('/autenticacion/sesion/'); establecerUsuario(r.usuario); }
      catch (e) { if (e.estado === 401 || e.estado === 403) establecerUsuario(null); }
    }
    window.addEventListener('focus', refrescar);
    window.addEventListener('zb-permisos', refrescar);
    const reloj = setInterval(() => { if (document.visibilityState === 'visible') refrescar(); }, 30000);
    return () => { window.removeEventListener('focus', refrescar); window.removeEventListener('zb-permisos', refrescar); clearInterval(reloj); };
  }, []);

  async function ingresar(usuarioIngresado, contrasena) {
    const cuenta = await api.ingresar(usuarioIngresado, contrasena);
    establecerUsuario(cuenta);
  }

  async function salir() {
    await api.salir();
    establecerUsuario(null);
  }

  function invalidarSesion() {
    establecerUsuario(null);
  }

  return <ContextoAutenticacion.Provider value={{ usuario, cargando, error, restaurar, ingresar, salir, invalidarSesion }}>
    {children}
  </ContextoAutenticacion.Provider>;
}
export const usarAutenticacion = () => useContext(ContextoAutenticacion);
