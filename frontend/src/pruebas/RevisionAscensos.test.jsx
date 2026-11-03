import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RevisionAscenso } from '../componentes/RevisionAscenso.jsx';
import { Propuestas } from '../paginas/Propuestas.jsx';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';

let rol, datos, fallo, resolver;
vi.mock('../autenticacion/ContextoAutenticacion.jsx', () => ({ usarAutenticacion: () => ({ usuario: { rol } }) }));
vi.mock('../api/cliente.js', () => ({ solicitar: vi.fn() }));
vi.mock('../api/gestion.js', () => ({ guardar: vi.fn() }));
const pagina = (results) => ({ results, count: results.length, next: null });
const fila = (id, situacion) => ({ inscripcion: id, afectacion: id + 10, estado: situacion === 'reserva' ? 'suspendida' : 'activa',
  situacion_actual: situacion, situacion_observada: situacion, fecha_ingreso: '2026-10-29',
  grupo: { id, codigo: 'ESC-' + id, nombre: 'Grupo ' + id }, nivel: { nombre: 'Nivel 1' },
  periodo: { nombre: 'Ciclo', inicio: '2026-01-01', fin: '2026-12-31' },
  disposicion: 'revisar', reservas_vigentes: situacion === 'reserva' ? [{ id: 1, inicio: '2026-10-29', vencimiento: '2026-11-01' }] : [] });
beforeEach(() => {
  vi.clearAllMocks(); rol = 'coordinador'; fallo = null; resolver = null;
  vi.stubGlobal('confirm', vi.fn(() => true));
  datos = { id: 5, version: 2, nombre_deportista: 'Ana Ficticia', disciplina: 1, disciplina_nombre: 'Escalada',
    nivel_destino: 3, nivel_origen_nombre: 'Nivel 1', nivel_destino_nombre: 'Nivel 2', estado_decision: 'pendiente', estado_plan: 'parcial',
    profesor_proponente: { nombre: 'Profesor Ficticio' }, justificacion: 'Motivo pedagógico', creado_en: '2026-10-30',
    inscripciones: [fila(1, 'activa'), fila(2, 'reserva'), fila(3, 'futura')], excepciones: [],
    eventos: [{ id: 1, tipo: 'proponer_ascenso', motivo: 'Origen', responsable: { nombre: 'Profesor Ficticio' } }],
    revision: { puede_preparar: true, puede_aprobar: false, puede_rechazar: true, advertencias: [{ mensaje: 'Faltan disposiciones' }] } };
  solicitar.mockImplementation(async (ruta) => {
    if (fallo) throw fallo;
    if (ruta.startsWith('/ascensos/5/')) return datos;
    if (ruta.startsWith('/ascensos/')) return pagina([datos]);
    if (ruta.startsWith('/organizacion/grupos/') && ruta.includes('?')) return pagina([]);
    if (ruta.startsWith('/organizacion/grupos/')) return { id: 1, codigo: 'ESC', nombre: 'Grupo autorizado', horarios: [{ dia: 0, hora_inicio: '10:00', hora_fin: '11:00' }] };
    return pagina([{ id: 99, tipo: 'nivel', estado: 'pendiente', justificacion: 'Histórica', mecanismo_deshabilitado: true }]);
  });
  guardar.mockImplementation(async () => ({ ...datos, version: 3, estado_decision: 'rechazada' }));
});
const montar = () => render(<RevisionAscenso id={5} cerrar={vi.fn()} actualizada={vi.fn()} />);
const listo = () => screen.findByText('Ana Ficticia · Escalada');

it('lista institucional con filtros, autor, fecha e historial separado', async () => {
  render(<Propuestas />);
  await screen.findByRole('button', { name: 'Revisar ascenso 5' });
  expect(screen.getByRole('table', { name: 'Propuestas de ascenso institucional' })).toHaveTextContent('Profesor: Profesor Ficticio');
  expect(screen.getByRole('table', { name: 'Propuestas anteriores y administrativas' })).toHaveTextContent('Histórica');
  fireEvent.change(screen.getByLabelText('Filtrar decisión de ascenso'), { target: { value: 'aprobada' } });
  await waitFor(() => expect(solicitar).toHaveBeenCalledWith(expect.stringContaining('estado_decision=aprobada')));
});
it('detalle autorizado con múltiples situaciones, reservas, horarios e historial', async () => {
  montar(); await listo();
  expect(screen.getByText(/Reserva vigente:/)).toBeInTheDocument();
  expect(screen.getByText(/Situación: futura/)).toBeInTheDocument();
  await screen.findAllByText(/Lunes 10:00/);
  expect(screen.getByText(/proponer_ascenso/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Aprobar progresión pedagógica' })).toBeDisabled();
});
it('opciones condicionadas y ninguna continuidad sin excepción vigente', async () => {
  montar(); await listo();
  const activa = within(screen.getByRole('form', { name: 'Disposición de inscripción 1' }));
  expect(activa.queryByRole('option', { name: 'continuidad' })).not.toBeInTheDocument();
  expect(activa.queryByRole('option', { name: 'reserva' })).not.toBeInTheDocument();
  expect(within(screen.getByRole('form', { name: 'Disposición de inscripción 2' })).getByRole('option', { name: 'reserva' })).toBeInTheDocument();
  expect(within(screen.getByRole('form', { name: 'Disposición de inscripción 3' })).getByRole('option', { name: 'futura' })).toBeInTheDocument();
});
it('continuidad solo con excepción vigente proporcionada por API', async () => {
  datos.excepciones = [{ id: 1, afectacion: 11, situacion: 'vigente', motivo: 'Excepción explícita' }];
  montar(); await listo();
  expect(within(screen.getByRole('form', { name: 'Disposición de inscripción 1' })).getByRole('option', { name: 'continuidad' })).toBeInTheDocument();
});
it('envía disposición con versión y payload exactos', async () => {
  montar(); await listo(); const u = userEvent.setup();
  const f = within(screen.getByRole('form', { name: 'Disposición de inscripción 1' }));
  await u.selectOptions(f.getByLabelText('Disposición'), 'pendiente');
  await u.type(f.getByLabelText('Motivo de la disposición'), 'Revisada');
  await u.click(f.getByRole('button', { name: 'Registrar disposición' }));
  expect(guardar).toHaveBeenCalledWith('/ascensos/5/disponer/', { version: 2, afectacion: 11, disposicion: 'pendiente', motivo: 'Revisada', destino: null });
  await screen.findByText(/Registro confirmado/);
});
it('consulta destinos autorizados y bloquea si no hay selección', async () => {
  montar(); await listo(); const u = userEvent.setup();
  const f = within(screen.getByRole('form', { name: 'Disposición de inscripción 1' }));
  await u.selectOptions(f.getByLabelText('Disposición'), 'reubicar');
  await u.type(f.getByLabelText('Motivo de la disposición'), 'Destino');
  await waitFor(() => expect(solicitar).toHaveBeenCalledWith(expect.stringContaining('/organizacion/grupos/?disciplina=1&nivel=3&activo=true')));
  expect(f.getByRole('button', { name: 'Registrar disposición' })).toBeDisabled();
  expect(guardar).not.toHaveBeenCalled();
});
it('error de permisos sin controles utilizables', async () => {
  fallo = new Error('No tienes permiso'); montar();
  await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: 'Aprobar progresión pedagógica' })).not.toBeInTheDocument();
});
it('selecciona un destino del catálogo autorizado y envía únicamente su ID', async () => {
  const original = solicitar.getMockImplementation();
  solicitar.mockImplementation((ruta) => ruta.startsWith('/organizacion/grupos/?') ? Promise.resolve(pagina([
    { id: 40, codigo: 'ESC-N2', nombre: 'Destino compatible', periodo_nombre: 'Ciclo' },
  ])) : original(ruta));
  montar(); await listo(); const u = userEvent.setup();
  const f = within(screen.getByRole('form', { name: 'Disposición de inscripción 1' }));
  await u.selectOptions(f.getByLabelText('Disposición'), 'reubicar');
  await f.findByRole('option', { name: /Destino compatible/ });
  await u.selectOptions(f.getByLabelText('Destino propuesto'), '40');
  await u.type(f.getByLabelText('Motivo de la disposición'), 'Destino revisado');
  await u.click(f.getByRole('button', { name: 'Registrar disposición' }));
  expect(guardar).toHaveBeenCalledWith('/ascensos/5/disponer/', {
    version: 2, afectacion: 11, disposicion: 'reubicar', motivo: 'Destino revisado', destino: 40,
  });
});
it('versión obsoleta bloquea nuevos envíos hasta recarga', async () => {
  guardar.mockRejectedValue(new Error('Versión obsoleta')); montar(); await listo();
  const u = userEvent.setup(); await u.type(screen.getByLabelText('Motivo de la resolución'), 'Revisada');
  await u.click(screen.getByRole('button', { name: 'Rechazar progresión pedagógica' }));
  await screen.findByText('Versión obsoleta');
  expect(screen.getByLabelText('Motivo de la resolución')).toBeDisabled();
  await u.click(screen.getByRole('button', { name: 'Actualizar revisión' })); await listo();
});
it.each(['aprobar', 'rechazar'])('decisión %s explícita, motivada y con recarga del listado', async (decision) => {
  datos.revision.puede_aprobar = true;
  const actualizada = vi.fn(); render(<RevisionAscenso id={5} cerrar={vi.fn()} actualizada={actualizada} />); await listo();
  const u = userEvent.setup(); await u.type(screen.getByLabelText('Motivo de la resolución'), 'Resolución');
  await u.click(screen.getByRole('button', { name: decision === 'aprobar' ? 'Aprobar progresión pedagógica' : 'Rechazar progresión pedagógica' }));
  await waitFor(() => expect(actualizada).toHaveBeenCalledOnce());
  expect(guardar).toHaveBeenCalledWith(`/ascensos/5/${decision}/`, { version: 2, decision, resolucion: 'Resolución' });
});
it('previene doble envío durante la solicitud', async () => {
  guardar.mockImplementation(() => new Promise((r) => { resolver = r; }));
  montar(); await listo(); const u = userEvent.setup();
  await u.type(screen.getByLabelText('Motivo de la resolución'), 'Resolución');
  await u.dblClick(screen.getByRole('button', { name: 'Rechazar progresión pedagógica' }));
  expect(guardar).toHaveBeenCalledOnce();
  resolver({ ...datos, estado_decision: 'rechazada', version: 3 });
  await screen.findByText(/Registro confirmado/);
});
it.each(['profesor', 'administrador'])('no muestra decisiones al rol %s', async (valor) => {
  rol = valor; render(<Propuestas />);
  await screen.findByRole('table', { name: 'Propuestas anteriores y administrativas' });
  expect(screen.queryByRole('button', { name: 'Revisar ascenso 5' })).not.toBeInTheDocument();
});
