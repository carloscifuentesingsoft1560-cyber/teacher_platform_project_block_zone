import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Aplicacion } from '../Aplicacion.jsx';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { SelectorCatalogo } from '../componentes/SelectorCatalogo.jsx';

const grupo = { id: 7, codigo: 'ESC-N1-001', nombre: 'Escalada inicial', periodo_nombre: 'Ciclo octubre', periodo: 4 };
const otro = { id: 8, codigo: 'ESC-N2-002', nombre: 'Escalada avanzada', periodo_nombre: 'Ciclo noviembre', periodo: 5 };
const pagina = (results, next = null) => ({ results, next, count: results.length });
const respuesta = (datos, status = 200) => ({ ok: status < 400, status, json: async () => datos });
let llamadas, rol, falloCupos, falloCatalogo, cuposPendientes, paginasDeportistas;
beforeEach(() => {
  llamadas = []; rol = 'administrador'; falloCupos = false; falloCatalogo = false; cuposPendientes = null; paginasDeportistas = false;
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const u = new URL(ruta, 'http://localhost');llamadas.push({ ruta, p: u.pathname, params: u.searchParams, metodo: opciones.method || 'GET' });
    if (u.pathname.endsWith('/sesion/')) return respuesta({ usuario: { id: 1, rol, nombre: 'Cuenta ficticia' } });
    if (u.pathname.endsWith('/tipos-documento/')) return respuesta(pagina([]));
    if (u.pathname.endsWith('/grupos/7/')) return respuesta(grupo);
    if (u.pathname.endsWith('/grupos/8/')) return respuesta(otro);
    if (u.pathname.endsWith('/grupos/')) {
      if (falloCatalogo) return respuesta({ detalle: 'Catálogo no disponible.' }, 503);
      if (u.searchParams.get('page') === '2') return respuesta(pagina([otro]));
      if (u.searchParams.get('search') === 'avanzada') return respuesta(pagina([otro]));
      return respuesta(pagina([grupo], '/api/organizacion/grupos/?page=2&search='));
    }
    if (u.pathname.endsWith('/periodos/')) return respuesta(pagina([{ id: 4, codigo: 'CIC-2026', nombre: 'Ciclo octubre' }]));
    if (u.pathname.endsWith('/disciplinas/')) return respuesta(pagina([{ id: 2, codigo: 'ESC', nombre: 'Escalada' }]));
    if (u.pathname.endsWith('/niveles/')) return respuesta(pagina([{ id: 3, codigo: 'N1', nombre: 'Nivel 1', disciplina_nombre: 'Escalada' }]));
    if (u.pathname.endsWith('/cupos/')) {
      if (cuposPendientes) return cuposPendientes;
      if (falloCupos) return respuesta({ detalle: 'No puedes consultar ese grupo.' }, 404);
      return respuesta({ grupo: Number(u.searchParams.get('grupo')), cupo_maximo: 15, inscripciones_activas: 4, reservas_vigentes: 2,
        ocupacion_actual: 6, disponibles_actuales: 9, ocupacion_maxima: 8, disponibles: 7, fecha_corte: '2026-10-29', desde: '2026-10-29', hasta: '2026-12-31' });
    }
    if (u.pathname.endsWith('/deportistas/') && paginasDeportistas) return respuesta({ results: [], count: 2, next: u.searchParams.get('page') === '1' ? '/api/deportistas/?page=2' : null });
    if (u.pathname.endsWith('/deportistas/') || u.pathname.endsWith('/inscripciones/')) return respuesta(pagina([]));
    return respuesta({}, 404);
  }));
});
function montar(ruta) {
  return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);
}
const cupos = () => llamadas.filter((x) => x.p.endsWith('/cupos/'));
const grupos = () => llamadas.filter((x) => x.p.endsWith('/grupos/'));

describe('Filtros y cupos comprensibles', () => {
  it.each(['administrador','coordinador','profesor'])('consulta cupos por nombre como %s sin ampliar permisos', async (r) => {
    rol = r; montar((r === 'administrador' ? '/administracion' : r === 'coordinador' ? '/coordinacion' : '/profesor') + '/inscripciones');
    const u = userEvent.setup();
    await screen.findByRole('option', { name: 'ESC-N1-001 · Escalada inicial · Ciclo octubre' });
    expect(cupos()).toHaveLength(0);
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '7');
    const resumen = await screen.findByRole('region', { name: 'Cupos del grupo' });
    expect(resumen).toHaveTextContent('Capacidad: 15');
    expect(resumen).toHaveTextContent('Inscripciones activas: 4. Reservas vigentes: 2. Ocupación actual: 6. Disponibles actualmente: 9.');
    expect(resumen).toHaveTextContent('ocupación máxima 8; disponibles durante todo ese intervalo: 7');
    expect(cupos()).toHaveLength(1); expect(cupos()[0].params.get('grupo')).toBe('7');
    if (r === 'profesor') expect(screen.queryByRole('button', { name: 'Inscribir deportista' })).not.toBeInTheDocument();
    expect(llamadas.every((x) => x.metodo === 'GET')).toBe(true);
  });
  it('filtra grupo, periodo, disciplina y nivel con IDs internos conservando parámetros', async () => {
    montar('/administracion/deportistas?estado=activo');const u = userEvent.setup();
    for (const [nombre, id] of [['grupo','7'],['periodo','4'],['disciplina','2'],['nivel','3']]) {
      const select = await screen.findByLabelText('Filtrar ' + nombre);
      await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
      await u.selectOptions(select, id);
    }
    await waitFor(() => {
      const ultima = llamadas.filter((x) => x.p === '/api/deportistas/').at(-1).params;
      expect(Object.fromEntries(['grupo','periodo','disciplina','nivel','estado'].map((k) => [k, ultima.get(k)]))).toEqual({ grupo:'7', periodo:'4', disciplina:'2', nivel:'3', estado:'activo' });
    });
    expect(screen.queryByLabelText(/por identificador/)).not.toBeInTheDocument();
    expect(grupos()).toHaveLength(1);
    await u.selectOptions(screen.getByLabelText('Filtrar nivel'), '');
    await waitFor(() => expect(llamadas.filter((x) => x.p === '/api/deportistas/').at(-1).params.has('nivel')).toBe(false));
  });
  it('busca con espera breve, pagina y conserva la opción seleccionada', async () => {
    const cambiar = vi.fn();
    const vista = render(<SelectorCatalogo etiqueta="Filtrar grupo" nombre="prueba" ruta="/organizacion/grupos/" valor="7" cambiar={cambiar} />);
    await screen.findByRole('option', { name: /ESC-N1-001/ });
    expect(llamadas.filter((x) => /grupos\/7\//.test(x.p))).toHaveLength(0);
    const u = userEvent.setup();
    await u.click(screen.getByRole('button', { name: 'Más opciones de filtrar grupo' }));
    await screen.findByRole('option', { name: /ESC-N2-002/ });
    await u.type(screen.getByLabelText('Buscar grupo'), 'avanzada');
    await waitFor(() => expect(grupos().filter((x) => x.params.get('search') === 'avanzada')).toHaveLength(1));
    expect(screen.getByLabelText('Filtrar grupo')).toHaveValue('7');
    expect(screen.getByRole('option', { name: /ESC-N1-001/ })).toBeInTheDocument();
    vista.unmount();
  });
  it('resuelve por nombre una selección de URL que no aparece en la primera página', async () => {
    montar('/administracion/deportistas?grupo=8');
    await waitFor(() => expect(screen.getByLabelText('Filtrar grupo')).toHaveDisplayValue('ESC-N2-002 · Escalada avanzada · Ciclo noviembre'));
    expect(llamadas.filter((x) => x.p.endsWith('/grupos/8/'))).toHaveLength(1);
  });
  it('reinicia la paginación del listado cuando cambia un filtro', async () => {
    paginasDeportistas = true;montar('/administracion/deportistas');const u = userEvent.setup();
    const boton = await screen.findByRole('button', { name: 'Siguiente', exact: true });
    await waitFor(() => expect(boton).toBeEnabled());await u.click(boton);
    await waitFor(() => expect(llamadas.filter((x) => x.p === '/api/deportistas/').at(-1).params.get('page')).toBe('2'));
    await screen.findByRole('option', { name: /ESC-N1-001/ });
    await u.selectOptions(screen.getByLabelText('Filtrar grupo'), '7');
    await waitFor(() => {
      const p = llamadas.filter((x) => x.p === '/api/deportistas/').at(-1).params;
      expect(p.get('grupo')).toBe('7');expect(p.get('page')).toBe('1');
    });
  });
  it('limpia resultados al quitar el grupo y permite refrescar sin consultar catálogos otra vez', async () => {
    montar('/administracion/inscripciones');const u = userEvent.setup();
    await screen.findByRole('option', { name: /ESC-N1-001/ });
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '7');
    await screen.findByRole('region', { name: 'Cupos del grupo' });
    await u.click(screen.getByRole('button', { name: 'Actualizar cupos' }));
    await waitFor(() => expect(cupos()).toHaveLength(2));
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '');
    expect(screen.queryByRole('region', { name: 'Cupos del grupo' })).not.toBeInTheDocument();
    expect(screen.queryByText('Consultando cupos…')).not.toBeInTheDocument();
    expect(grupos()).toHaveLength(1);
  });
  it('muestra rechazo de API sin inventar disponibilidad', async () => {
    falloCupos = true;montar('/administracion/inscripciones');const u = userEvent.setup();
    await screen.findByRole('option', { name: /ESC-N1-001/ });
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '7');
    expect(await screen.findByRole('alert')).toHaveTextContent('No puedes consultar ese grupo');
    expect(screen.queryByRole('region', { name: 'Cupos del grupo' })).not.toBeInTheDocument();
  });
  it('descarta una respuesta de cupos tardía tras limpiar la selección', async () => {
    let resolver;cuposPendientes = new Promise((r) => { resolver = r; });
    montar('/administracion/inscripciones');const u = userEvent.setup();
    await screen.findByRole('option', { name: /ESC-N1-001/ });
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '7');
    await waitFor(() => expect(cupos()).toHaveLength(1));
    await u.selectOptions(screen.getByLabelText('Grupo para consultar cupos'), '');
    resolver(respuesta({ cupo_maximo: 15 }));
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Cupos del grupo' })).not.toBeInTheDocument());
  });
  it('presenta el error de catálogo y permite reintentar', async () => {
    falloCatalogo = true;render(<SelectorCatalogo etiqueta="Filtrar grupo" nombre="prueba" ruta="/organizacion/grupos/" valor="" cambiar={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Catálogo no disponible');
    falloCatalogo = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar filtrar grupo' }));
    expect(await screen.findByRole('option', { name: /ESC-N1-001/ })).toBeInTheDocument();
  });
});
