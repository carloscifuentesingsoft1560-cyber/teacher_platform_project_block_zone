import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

function responder(datos, estado = 200) {
  return { ok: estado >= 200 && estado < 300, status: estado, json: async () => datos };
}
const cuenta = (rol) => ({ id: 1, username: 'demo_' + rol, nombre: 'Cuenta ficticia', rol });
let autenticado;
let rolActual;
let llamadas;
let ingresoPendiente;

beforeEach(() => {
  autenticado = false;
  rolActual = 'profesor';
  llamadas = [];
  ingresoPendiente = null;
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta.endsWith('/csrf/')) return responder({ csrfToken: 'csrf-inicial' });
    if (ruta.endsWith('/sesion/')) return responder(autenticado ? { usuario: cuenta(rolActual) } : { detalle: 'Sin sesión' }, autenticado ? 200 : 403);
    if (ruta.endsWith('/ingresar/')) {
      if (ingresoPendiente) return ingresoPendiente;
      autenticado = true;
      return responder({ usuario: cuenta(rolActual), csrfToken: 'csrf-rotado' });
    }
    if (ruta.endsWith('/salir/')) { autenticado = false; return responder({ detalle: 'Sesión cerrada' }); }
    if (ruta.includes('/paneles/') && ruta.includes('/resumen/')) return responder({
      fecha_corte: '2026-10-28', filtros: {},
      profesores: { activos: 0, inactivos: 0, sin_grupo: 0 },
      grupos: { activos: 0, inactivos: 0 }, periodos: { total: 0 },
      asignaciones: { vigentes: 0, operativas: 0 },
      coordinacion: { actual: null, estado: 'vacante' }, disciplinas: [], niveles: [],
    });
    if (ruta.includes('/paneles/')) return responder({ rol: rolActual, nombre: 'Cuenta ficticia', mensaje: 'Espacio inicial' });
    return responder({}, 404);
  }));
});

function montar(ruta = '/') {
  return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);
}

describe('Autenticación y rutas privadas', () => {
  it('redirige al visitante a ingresar', async () => {
    montar('/administracion');
    expect(await screen.findByRole('heading', { name: 'Ingresar' })).toBeInTheDocument();
    expect(llamadas.some(({ ruta }) => ruta.includes('/paneles/'))).toBe(false);
  });

  it.each([
    ['profesor', '/profesor', 'Tu espacio para enseñar'],
    ['coordinador', '/coordinacion', 'Acompañar cada proceso'],
    ['administrador', '/administracion', 'Organizar para crecer'],
  ])('restaura la sesión del %s', async (rol, ruta, titulo) => {
    autenticado = true; rolActual = rol;
    montar(ruta);
    expect(await screen.findByRole('heading', { name: titulo })).toBeInTheDocument();
    expect(llamadas.some(({ ruta: destino }) => destino === '/api/paneles/' + rol + '/')).toBe(true);
  });

  it('bloquea rutas de otro rol sin solicitar su panel', async () => {
    autenticado = true;
    montar('/administracion');
    expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeInTheDocument();
    expect(llamadas.some(({ ruta }) => ruta.includes('/paneles/'))).toBe(false);
  });

  it('ingresa con CSRF y cierra la sesión', async () => {
    const usuario = userEvent.setup();
    montar();
    await usuario.type(await screen.findByLabelText('Usuario'), 'demo_profesor');
    await usuario.type(screen.getByLabelText('Contraseña'), 'clave-ficticia');
    await usuario.click(screen.getByRole('button', { name: /Ingresar a mi espacio/ }));
    expect(await screen.findByRole('heading', { name: 'Tu espacio para enseñar' })).toBeInTheDocument();
    const envio = llamadas.find(({ ruta }) => ruta.endsWith('/ingresar/'));
    expect(envio.opciones.headers['X-CSRFToken']).toBe('csrf-inicial');
    expect(envio.opciones.credentials).toBe('same-origin');
    await usuario.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByRole('heading', { name: 'Ingresar' })).toBeInTheDocument();
  });

  it('muestra errores de credenciales y permite volver a intentar', async () => {
    ingresoPendiente = Promise.resolve(responder({ detalle: 'Usuario o contraseña incorrectos.' }, 400));
    const usuario = userEvent.setup();
    montar();
    await usuario.type(await screen.findByLabelText('Usuario'), 'demo_profesor');
    await usuario.type(screen.getByLabelText('Contraseña'), 'incorrecta');
    await usuario.click(screen.getByRole('button', { name: /Ingresar a mi espacio/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario o contraseña incorrectos.');
    expect(screen.getByLabelText('Contraseña')).toHaveValue('');
    expect(screen.getByRole('button', { name: /Ingresar a mi espacio/ })).toBeEnabled();
  });

  it('distingue un servidor caído de una sesión anónima', async () => {
    fetch.mockRejectedValue(new TypeError('sin conexión'));
    montar();
    expect(await screen.findByRole('heading', { name: 'Servidor no disponible' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('el botón de menú expone su estado y permite navegar al perfil', async () => {
    autenticado = true;
    const usuario = userEvent.setup();
    montar('/profesor');
    const boton = await screen.findByRole('button', { name: 'Menú' });
    expect(boton).toHaveAttribute('aria-expanded', 'false');
    await usuario.click(boton);
    expect(boton).toHaveAttribute('aria-expanded', 'true');
    await usuario.click(screen.getByRole('link', { name: 'Mi cuenta' }));
    expect(await screen.findByRole('heading', { name: 'Tu perfil institucional' })).toBeInTheDocument();
    expect(boton).toHaveAttribute('aria-expanded', 'false');
  });

  it('el cierre de sesión bloquea el botón durante el envío', async () => {
    autenticado = true;
    const usuario = userEvent.setup();
    montar('/profesor');
    await screen.findByRole('heading', { name: 'Tu espacio para enseñar' });
    const original = fetch.getMockImplementation();
    let resolver;
    fetch.mockImplementation(async (ruta, opciones) => ruta.endsWith('/salir/')
      ? new Promise((resolve) => { resolver = resolve; })
      : original(ruta, opciones));
    await usuario.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(screen.getByRole('button', { name: 'Cerrando…' })).toBeDisabled();
    resolver(responder({ detalle: 'Sesión cerrada' }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Ingresar' })).toBeInTheDocument());
  });
});
