import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

let rol, usuarios, grupos, solicitudes;
const disciplina = { id: 1, codigo: 'escalada', nombre: 'Escalada', activo: true };
const nivel = { id: 1, codigo: 'nivel-1', nombre: 'Nivel 1', disciplina: 1, disciplina_nombre: 'Escalada', orden: 2, activo: true };
const periodo = { id: 1, codigo: 'demo-ciclo', nombre: 'Ciclo ficticio', fecha_inicio: '2026-01-01', fecha_fin: '2027-12-31', activo: true };
function responder(datos, estado = 200) {
  return { ok: estado >= 200 && estado < 300, status: estado, json: async () => datos };
}
const pagina = (datos) => ({ count: datos.length, next: null, previous: null, results: datos });

beforeEach(() => {
  rol = 'administrador'; solicitudes = [];
  usuarios = [{ id: 2, username: 'demo_docente', first_name: 'Docente', last_name: 'Ficticio', email: '', rol: 'profesor', is_active: true }];
  grupos = [{ id: 1, codigo: 'demo-a', nombre: 'Grupo ficticio A', disciplina: 1, disciplina_nombre: 'Escalada', nivel: 1, nivel_nombre: 'Nivel 1', periodo: 1, periodo_nombre: 'Ciclo ficticio', cupo_maximo: 12, activo: true, horarios: [{ id: 1, dia: 0, hora_inicio: '10:00:00', hora_fin: '12:00:00', duracion_minutos: 120 }] }];
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const url = new URL(ruta, 'http://localhost');
    const camino = url.pathname;
    const metodo = opciones.method || 'GET';
    const cuerpo = opciones.body ? JSON.parse(opciones.body) : null;
    solicitudes.push({ camino, metodo, cuerpo, opciones });
    if (camino.endsWith('/sesion/')) return responder({ usuario: { id: 1, username: 'demo_admin', nombre: 'Cuenta ficticia', rol } });
    if (camino.endsWith('/csrf/')) return responder({ csrfToken: 'token-csrf-ficticio' });
    if (camino.includes('/restablecer-acceso/')) return responder({ ruta: '/restablecer-acceso#token=token-ficticio', fecha_expira: '2026-10-28T05:00:00Z' });
    if (camino === '/api/recuperacion/confirmar/') return responder({ detalle: 'Listo' });
    if (camino === '/api/usuarios/' && metodo === 'POST') {
      const nuevo = { id: 9, is_active: true, ...cuerpo }; usuarios.push(nuevo); return responder(nuevo, 201);
    }
    if (/\/usuarios\/\d+\/$/.test(camino) && metodo === 'PATCH') {
      const usuario = usuarios.find((u) => camino.endsWith('/' + u.id + '/'));
      Object.assign(usuario, cuerpo); return responder(usuario);
    }
    if (camino === '/api/usuarios/') return responder(pagina(usuarios.filter((u) => u.username.includes(url.searchParams.get('search') || ''))));
    if (camino.endsWith('/disciplinas/')) return responder(metodo === 'GET' ? pagina([disciplina]) : { id: 9, ...cuerpo }, metodo === 'GET' ? 200 : 201);
    if (camino.endsWith('/niveles/')) return responder(pagina([nivel]));
    if (camino.endsWith('/periodos/')) return responder(pagina([periodo]));
    if (camino.endsWith('/grupos/')) {
      if (metodo === 'POST') { const nuevo = { ...grupos[0], id: 9, ...cuerpo }; grupos.push(nuevo); return responder(nuevo, 201); }
      return responder(pagina(grupos));
    }
    if (camino.endsWith('/asignaciones/')) return responder(metodo === 'GET' ? pagina([]) : { id: 1, ...cuerpo }, metodo === 'GET' ? 200 : 201);
    if (camino.endsWith('/calendario/')) return responder({ eventos: [{ id: '1:2026-10-27', fecha: '2026-10-27', grupo_nombre: 'Grupo ficticio A', hora_inicio: '10:00', hora_fin: '12:00', duracion_minutos: 120 }] });
    if (camino.endsWith('/profesores/')) return responder(pagina([{ id: 2, nombre: 'Docente Ficticio', username: 'demo_docente', rol: 'profesor' }]));
    return responder({ detalle: 'No disponible' }, 404);
  }));
});
function montar(ruta) {
  return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);
}

describe('Gestión de Fase 2', () => {
  it('crea un usuario con rol y CSRF', async () => {
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.click(await screen.findByRole('button', { name: 'Crear usuario' }));
    await u.type(screen.getByLabelText('Usuario'), 'demo_nuevo');
    await u.selectOptions(screen.getByLabelText('Rol'), 'coordinador');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('Cuenta guardada correctamente.')).toBeInTheDocument();
    const envio = solicitudes.find((s) => s.camino === '/api/usuarios/' && s.metodo === 'POST');
    expect(envio.cuerpo.rol).toBe('coordinador');
    expect(envio.opciones.headers['X-CSRFToken']).toBe('token-csrf-ficticio');
  });

  it('busca usuarios y modifica su rol', async () => {
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.type(await screen.findByLabelText('Buscar'), 'demo_docente');
    await u.click(await screen.findByRole('button', { name: 'Editar demo_docente' }));
    await u.selectOptions(screen.getByLabelText('Rol'), 'coordinador');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(solicitudes.some((s) => s.metodo === 'PATCH' && s.cuerpo.rol === 'coordinador')).toBe(true));
    expect(solicitudes.some((s) => s.camino === '/api/usuarios/' && s.metodo === 'GET')).toBe(true);
  });

  it('desactiva con confirmación y nunca elimina usuarios', async () => {
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.click(await screen.findByRole('button', { name: 'Desactivar' }));
    expect(await screen.findByText('Estado de la cuenta actualizado.')).toBeInTheDocument();
    expect(confirm).toHaveBeenCalled();
    expect(solicitudes.find((s) => s.metodo === 'PATCH').cuerpo).toEqual({ is_active: false });
    expect(solicitudes.some((s) => s.metodo === 'DELETE')).toBe(false);
  });

  it('cancelar confirmación no envía una modificación', async () => {
    confirm.mockReturnValue(false);
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.click(await screen.findByRole('button', { name: 'Desactivar' }));
    expect(solicitudes.some((s) => s.metodo === 'PATCH')).toBe(false);
  });

  it('restablece acceso solo tras solicitar contraseña actual', async () => {
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.click(await screen.findByRole('button', { name: 'Restablecer acceso' }));
    await u.type(screen.getByLabelText('Tu contraseña actual'), 'clave-ficticia-admin');
    await u.click(screen.getByRole('button', { name: 'Confirmar y generar enlace' }));
    expect(await screen.findByRole('heading', { name: 'Enlace de un solo uso' })).toBeInTheDocument();
    expect(screen.getByLabelText('Enlace privado').value).toContain('#token=token-ficticio');
    expect(screen.queryByLabelText('Tu contraseña actual')).not.toBeInTheDocument();
  });

  it('crea una disciplina desde los catálogos', async () => {
    const u = userEvent.setup(); montar('/administracion/catalogos');
    await u.click(await screen.findByRole('button', { name: 'Crear registro' }));
    await u.type(screen.getByLabelText('Código'), 'demo-deporte');
    await u.type(screen.getByLabelText('Nombre'), 'Deporte ficticio');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('Catálogo guardado correctamente.')).toBeInTheDocument();
    expect(solicitudes.find((s) => s.metodo === 'POST').cuerpo.codigo).toBe('demo-deporte');
  });

  it('permite consultar niveles y periodos sin inventar contenidos', async () => {
    const u = userEvent.setup(); montar('/administracion/catalogos');
    await u.click(await screen.findByRole('button', { name: 'Niveles', exact: true }));
    expect(await screen.findByText('Nivel 1')).toBeInTheDocument();
    await u.click(screen.getByRole('button', { name: 'Periodos', exact: true }));
    expect(await screen.findByText('Ciclo ficticio')).toBeInTheDocument();
  });

  it('crea un grupo con nivel, cupo y horarios', async () => {
    const u = userEvent.setup(); montar('/administracion/grupos');
    await u.click(await screen.findByRole('button', { name: 'Crear grupo' }));
    await u.type(screen.getByLabelText('Código del grupo'), 'demo-nuevo');
    await u.type(screen.getByLabelText('Nombre del grupo'), 'Grupo ficticio nuevo');
    await waitFor(() => expect(within(screen.getByLabelText('Disciplina')).getByRole('option', { name: 'Escalada' })).toBeInTheDocument());
    await u.selectOptions(screen.getByLabelText('Disciplina'), '1');
    await u.selectOptions(screen.getByLabelText('Nivel'), '1');
    await u.selectOptions(screen.getByLabelText('Periodo'), '1');
    fireEvent.change(screen.getByLabelText('Hora de inicio'), { target: { value: '15:00' } });
    fireEvent.change(screen.getByLabelText('Hora de finalización'), { target: { value: '17:00' } });
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('Grupo guardado correctamente.')).toBeInTheDocument();
    const envio = solicitudes.find((s) => s.camino.endsWith('/grupos/') && s.metodo === 'POST');
    expect(envio.cuerpo.horarios).toEqual([{ dia: 0, hora_inicio: '15:00', hora_fin: '17:00' }]);
    expect(envio.cuerpo.cupo_maximo).toBe(12);
  });

  it('crea una asignación de profesor con vigencia', async () => {
    const u = userEvent.setup(); montar('/administracion/asignaciones');
    await u.click(await screen.findByRole('button', { name: 'Crear asignación' }));
    await waitFor(() => expect(within(screen.getByLabelText('Grupo')).getByRole('option', { name: /demo-a/ })).toBeInTheDocument());
    await u.selectOptions(screen.getByLabelText('Grupo'), '1');
    await u.selectOptions(screen.getByLabelText('Persona'), '2');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('Asignación guardada. El historial se conserva.')).toBeInTheDocument();
    const envio = solicitudes.find((s) => s.camino.endsWith('/asignaciones/') && s.metodo === 'POST');
    expect(envio.cuerpo).toMatchObject({ grupo: 1, usuario: 2, tipo: 'profesor', fecha_fin: null });
  });

  it('profesor consulta sus grupos y detalle sin controles administrativos', async () => {
    rol = 'profesor'; const u = userEvent.setup(); montar('/profesor/grupos');
    await u.click(await screen.findByRole('button', { name: 'Ver demo-a' }));
    expect(await screen.findByText(/Lunes · 10:00–12:00 · 120 minutos/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Crear grupo' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios', exact: true })).not.toBeInTheDocument();
  });

  it('coordinador consulta profesores y calendario sin escrituras', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/profesores');
    expect(await screen.findByText('Docente Ficticio')).toBeInTheDocument();
    await u.click(screen.getByRole('link', { name: 'Calendario', exact: true }));
    expect(await screen.findByText('120 minutos')).toBeInTheDocument();
    expect(solicitudes.some((s) => s.metodo !== 'GET')).toBe(false);
  });

  it('rechaza entrada directa del profesor a gestión de usuarios', async () => {
    rol = 'profesor'; montar('/administracion/usuarios');
    expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeInTheDocument();
    expect(solicitudes.some((s) => s.camino === '/api/usuarios/')).toBe(false);
  });

  it('muestra errores de campo devueltos por el servidor', async () => {
    const u = userEvent.setup(); montar('/administracion/usuarios');
    await u.click(await screen.findByRole('button', { name: 'Crear usuario' }));
    await u.type(screen.getByLabelText('Usuario'), 'demo_error');
    const original = fetch.getMockImplementation();
    fetch.mockImplementation((ruta, opciones) => opciones?.method === 'POST' && ruta.endsWith('/usuarios/')
      ? Promise.resolve(responder({ detalle: 'Revisa los datos.', errores: { username: ['Usuario ya registrado.'] } }, 400)) : original(ruta, opciones));
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuario ya registrado.');
  });

  it('permite confirmar un enlace sin exponer el token en una consulta URL', async () => {
    const u = userEvent.setup(); montar('/restablecer-acceso#token=token-ficticio');
    await u.type(await screen.findByLabelText('Nueva contraseña'), 'Nueva-clave-ficticia-572!');
    await u.type(screen.getByLabelText('Repetir contraseña'), 'Nueva-clave-ficticia-572!');
    await u.click(screen.getByRole('button', { name: 'Confirmar nueva contraseña' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Tu contraseña se actualizó.');
    expect(solicitudes.find((s) => s.camino.endsWith('/recuperacion/confirmar/')).cuerpo.token).toBe('token-ficticio');
  });
});
