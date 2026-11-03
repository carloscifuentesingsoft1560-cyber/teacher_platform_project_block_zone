import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

let rol, llamadas, titular, falloRelevo;
const profesor = { id: 21, username: 'demo_entrante', nombre: 'Persona entrante ficticia', first_name: 'Persona entrante', last_name: 'ficticia', rol: 'profesor', is_active: true, grupos: [] };
const grupo = { id: 1, codigo: 'demo-a', nombre: 'Grupo ficticio A', disciplina: 1, nivel: 1, periodo: 1, disciplina_nombre: 'Escalada', nivel_nombre: 'Nivel 1', periodo_nombre: 'Ciclo ficticio', activo: true, cupo_maximo: 10,
  horarios: [{ id: 1, dia: 0, hora_inicio: '10:00:00', hora_fin: '11:00:00', duracion_minutos: 60 }] };
const pagina = (results) => ({ count: results.length, results, next: null });
const respuesta = (datos, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => datos });
function resumen(periodo) {
  return {
    fecha_corte: '2026-10-28', filtros: { periodo: periodo ? Number(periodo) : null, disciplina: null, nivel: null },
    profesores: { activos: 3, inactivos: 1, sin_grupo: 1 },
    grupos: { activos: periodo === '2' ? 0 : 2, inactivos: 1 },
    periodos: { total: 2, activos: 1, en_curso: 1 },
    asignaciones: { vigentes: 4, operativas: 3 },
    coordinacion: { estado: 'activo', cantidad_activos: 1, actual: titular },
    disciplinas: [{ id: 1, nombre: 'Escalada', total: 3, activos: 2 }],
    niveles: [{ id: 1, nombre: 'Nivel 1', total: 3, activos: 2 }],
  };
}
beforeEach(() => {
  rol = 'administrador'; llamadas = []; falloRelevo = false;
  titular = { id: 20, username: 'demo_titular', nombre: 'Titular ficticio', rol: 'coordinador' };
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const url = new URL(ruta, 'http://localhost');
    const camino = url.pathname; const metodo = opciones.method || 'GET';
    const cuerpo = opciones.body ? JSON.parse(opciones.body) : null;
    llamadas.push({ camino, metodo, cuerpo, url });
    if (camino.endsWith('/sesion/')) return respuesta({ usuario: { id: 1, username: 'demo_cuenta', nombre: 'Cuenta ficticia', rol } });
    if (camino.endsWith('/csrf/')) return respuesta({ csrfToken: 'csrf-ficticio' });
    if (camino.endsWith('/resumen/')) return respuesta(resumen(url.searchParams.get('periodo')));
    if (camino.includes('/paneles/')) return respuesta({ nombre: 'Cuenta ficticia', rol, mensaje: 'Organización disponible' });
    if (camino.endsWith('/coordinacion/relevar/')) {
      if (falloRelevo) return respuesta({ detalle: 'La coordinación cambió. Actualiza la información.' }, 409);
      titular = { id: profesor.id, nombre: profesor.nombre, rol: 'coordinador' };
      return respuesta({ actual: titular });
    }
    if (camino.endsWith('/coordinacion/')) return respuesta({ ...pagina([{ id: 1, accion: 'coordinacion_fin', fecha: '2026-10-28T14:00:00Z', nombre: 'Titular anterior ficticio', autorizado_por: 'Administrador ficticio' }]), actual: titular });
    if (camino.endsWith('/usuarios/')) return respuesta(pagina([{ id: 1, username: 'demo_cuenta', rol: 'administrador' }, { ...titular }, profesor]));
    if (camino.endsWith('/profesores/')) return respuesta(pagina([profesor]));
    if (camino.endsWith('/disciplinas/')) return respuesta(pagina([{ id: 1, nombre: 'Escalada', activo: true }]));
    if (camino.endsWith('/niveles/')) return respuesta(pagina([{ id: 1, nombre: 'Nivel 1', disciplina: 1, activo: true }]));
    if (camino.endsWith('/periodos/')) return respuesta(pagina([{ id: 1, nombre: 'Ciclo ficticio', activo: true }, { id: 2, nombre: 'Ciclo anterior ficticio', activo: false }]));
    if (camino.endsWith('/grupos/')) return respuesta(pagina([grupo]));
    if (camino.endsWith('/grupos/1/') && metodo === 'PATCH') return respuesta({ detalle: 'El horario entra en conflicto con otra asignación.' }, 400);
    if (camino.endsWith('/asignaciones/')) return respuesta(metodo === 'POST' ? { id: 1, ...cuerpo } : pagina([]), metodo === 'POST' ? 201 : 200);
    return respuesta({}, 404);
  }));
});
function montar(ruta) {
  return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);
}
describe('Coordinación única y tablero institucional', () => {
  it('administración recibe y muestra conteos del servidor', async () => {
    montar('/administracion');
    expect(await screen.findByRole('heading', { name: 'Tablero general de la empresa' })).toBeInTheDocument();
    const titulo = await screen.findByRole('heading', { name: 'Profesores activos', exact: true });
    expect(titulo.closest('article')).toHaveTextContent('3');
    expect(await screen.findByText('Titular ficticio')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Asistencias' })).not.toBeInTheDocument();
  });

  it('aplica filtros y transporta los mismos filtros al detalle', async () => {
    const u = userEvent.setup(); montar('/administracion');
    await screen.findByRole('heading', { name: 'Profesores activos', exact: true });
    await u.selectOptions(screen.getByLabelText('Periodo'), '2');
    await u.click(screen.getByRole('button', { name: 'Aplicar filtros' }));
    await waitFor(() => expect(llamadas.some((l) => l.camino.endsWith('/resumen/') && l.url.searchParams.get('periodo') === '2')).toBe(true));
    const titulo = await screen.findByRole('heading', { name: 'Grupos activos (filtros)' });
    await waitFor(() => expect(titulo.closest('article')).toHaveTextContent('0'));
    expect(within(titulo.closest('article')).getByRole('link').getAttribute('href')).toContain('periodo=2');
  });

  it('coordinador puede crear asignaciones usando solo el selector docente', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/asignaciones');
    await u.click(await screen.findByRole('button', { name: 'Crear asignación' }));
    await waitFor(() => expect(within(screen.getByLabelText('Persona')).getByRole('option', { name: profesor.nombre })).toBeInTheDocument());
    await u.selectOptions(screen.getByLabelText('Grupo'), '1');
    await u.selectOptions(screen.getByLabelText('Persona'), '21');
    expect(within(screen.getByLabelText('Responsabilidad')).queryByRole('option', { name: 'Coordinador' })).not.toBeInTheDocument();
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('Asignación guardada. El historial se conserva.')).toBeInTheDocument();
    expect(llamadas.some((l) => l.camino === '/api/usuarios/')).toBe(false);
    expect(llamadas.find((l) => l.camino.endsWith('/asignaciones/') && l.metodo === 'POST').cuerpo.tipo).toBe('profesor');
  });

  it('coordinador edita horarios y recibe el rechazo de incompatibilidades', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/grupos');
    await u.click(await screen.findByRole('button', { name: 'Editar demo-a' }));
    fireEvent.change(screen.getByLabelText('Hora de finalización'), { target: { value: '11:30' } });
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El horario entra en conflicto');
    expect(screen.getByRole('form', { name: 'Formulario de grupo' })).toBeInTheDocument();
  });

  it('no ofrece cuentas, catálogos ni relevo al coordinador', async () => {
    rol = 'coordinador'; montar('/coordinacion');
    expect(await screen.findByRole('heading', { name: 'Resumen operativo de la escuela' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios', exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Catálogos', exact: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Cargo de coordinador', exact: true })).not.toBeInTheDocument();
  });

  it('administra el relevo con confirmación y versión del titular', async () => {
    const u = userEvent.setup(); montar('/administracion/coordinacion');
    expect(await screen.findByText('Titular anterior ficticio')).toBeInTheDocument();
    await waitFor(() => expect(within(screen.getByLabelText('Persona entrante')).getByRole('option', { name: /Persona entrante/ })).toBeInTheDocument());
    await u.selectOptions(screen.getByLabelText('Persona entrante'), '21');
    await u.click(screen.getByRole('button', { name: 'Confirmar relevo' }));
    expect(await screen.findByText('Coordinación actualizada. Se conservó el historial.')).toBeInTheDocument();
    expect(llamadas.find((l) => l.camino.endsWith('/relevar/')).cuerpo).toEqual({ usuario: 21, coordinador_actual: 20 });
    expect(confirm).toHaveBeenCalled();
  });

  it('un relevo obsoleto muestra error y vuelve a consultar el cargo', async () => {
    falloRelevo = true;
    const u = userEvent.setup(); montar('/administracion/coordinacion');
    await waitFor(() => expect(within(screen.getByLabelText('Persona entrante')).getByRole('option', { name: /Persona entrante/ })).toBeInTheDocument());
    await u.selectOptions(screen.getByLabelText('Persona entrante'), '21');
    await u.click(screen.getByRole('button', { name: 'Confirmar relevo' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La coordinación cambió');
    await waitFor(() => expect(llamadas.filter((l) => l.camino.endsWith('/coordinacion/')).length).toBeGreaterThan(1));
  });

  it('el profesor no recibe estadísticas institucionales ni acciones operativas', async () => {
    rol = 'profesor'; montar('/profesor');
    expect(await screen.findByRole('heading', { name: 'Tu espacio para enseñar' })).toBeInTheDocument();
    expect(llamadas.some((l) => l.camino.endsWith('/resumen/'))).toBe(false);
    expect(screen.queryByRole('button', { name: 'Crear asignación' })).not.toBeInTheDocument();
  });

  it('la tarjeta sin grupo consulta profesores por el mismo filtro', async () => {
    const u = userEvent.setup(); montar('/administracion');
    const titulo = await screen.findByRole('heading', { name: 'Profesores sin grupo operativo (filtros)' });
    await u.click(within(titulo.closest('article')).getByRole('link'));
    expect(await screen.findByRole('heading', { name: 'Profesores de la escuela' })).toBeInTheDocument();
    expect(llamadas.some((l) => l.camino.endsWith('/profesores/') && l.url.searchParams.get('sin_grupo') === 'true')).toBe(true);
  });
});
