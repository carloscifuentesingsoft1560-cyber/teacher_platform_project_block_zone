import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EjecucionAscenso } from '../componentes/EjecucionAscenso.jsx';
import { Propuestas } from '../paginas/Propuestas.jsx';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';

vi.mock('../api/cliente.js', () => ({ solicitar: vi.fn() }));
vi.mock('../api/gestion.js', () => ({ guardar: vi.fn() }));
let rol, datos;
vi.mock('../autenticacion/ContextoAutenticacion.jsx', () => ({ usarAutenticacion: () => ({ usuario: { rol } }) }));
const pagina = (results) => ({ count: results.length, results, next: null });
const grupo = (id, nombre) => ({ id, codigo: 'ESC-' + id, nombre, nivel: 'Nivel 2', periodo: 'Ciclo ficticio',
  horarios: [{ dia: 0, hora_inicio: '12:00', hora_fin: '13:00' }], capacidad: 10, ocupacion_maxima: 4, reservas_vigentes: 1, disponibles: 6 });
const fila = (id) => ({ afectacion: id + 10, inscripcion: id, estado: 'activa', situacion: 'activa', fecha_ingreso: '2020-01-01',
  origen: grupo(id, 'Origen ficticio'), destino: grupo(id + 100, 'Destino ficticio'), destino_id: id + 100,
  disposicion: 'reubicar', motivo: 'Plan revisado', puede_ejecutar: true, ejecutada: false, bloqueos: [] });
beforeEach(() => {
  vi.clearAllMocks(); rol = 'coordinador';
  vi.stubGlobal('confirm', vi.fn(() => true));
  datos = { progresion: 5, version: 8, revision: 9, revision_numero: 1, estado_decision: 'aprobada',
    estado_ejecucion: 'pendiente', ejecucion_habilitada: true, plan_completo: true, discrepancias: [],
    advertencias_destinos: [], inscripciones_nuevas: [], excepciones: [],
    deportista: 'Ana Ficticia', disciplina: 'Escalada', disciplina_id: 1, nivel_destino_id: 3,
    nivel_origen: 'Nivel 1', nivel_destino: 'Nivel 2', afectaciones: [fila(1), fila(2)] };
  solicitar.mockImplementation(async (ruta) => {
    if (ruta === '/ascensos/5/ejecucion/') return structuredClone(datos);
    if (ruta.includes('/revisiones/')) return pagina([{ id: 9, numero: 1, actor_id: 2, motivo: 'Plan previo',
      disposiciones: [{ afectacion: 11, origen: 1, disposicion: 'reubicar', destino: 101, motivo: 'Con cupo' }] }]);
    if (ruta.includes('/resultados/')) return pagina([{ id: 20, origen_id: 20, destino_id: 21, estado: 'ejecutada', motivo: 'Movimiento anterior', actor_id: 2 }]);
    if (ruta.includes('/organizacion/grupos/')) {
      const detalle = ruta.match(/\/grupos\/(\d+)\//);
      return detalle ? { id: Number(detalle[1]), codigo: 'ESC-' + detalle[1], nombre: 'Destino ficticio' }
        : pagina([{ id: 101, codigo: 'ESC-101', nombre: 'Destino ficticio' }]);
    }
    if (ruta.startsWith('/ascensos/')) return pagina([{ id: 5, nombre_deportista: 'Ana Ficticia', disciplina_nombre: 'Escalada', estado_decision: 'aprobada' }]);
    return pagina([]);
  });
  guardar.mockImplementation(async () => ({ resultado: 30 }));
});
const montar = (props = {}) => render(<EjecucionAscenso formalizar id={5} cerrar={vi.fn()} {...props} />);
const listo = () => screen.findByRole('heading', { name: 'Ana Ficticia · Escalada' });
async function preparar() {
  const u = userEvent.setup();
  await u.click(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 1' }));
  await u.type(screen.getByLabelText('Motivo de la reubicación'), 'Movimiento autorizado');
  return u;
}

it('muestra varias afectaciones, horarios, cupos, reservas e historial separado', async () => {
  montar(); await listo();
  expect(screen.getAllByText(/Lunes 12:00/)).toHaveLength(4);
  expect(screen.getAllByText(/Reservas vigentes: 1/)).toHaveLength(4);
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(await screen.findByText(/Movimiento anterior/)).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Historial de revisiones' })).toHaveTextContent('Plan previo');
  expect(screen.queryByRole('button', { name: /Aprobar progresión/ })).not.toBeInTheDocument();
});
it('bloquea ejecución y revisión mientras falta 0004', async () => {
  datos.ejecucion_habilitada = false; datos.aviso_instalacion = 'Instalar y verificar 0004';
  montar(); await listo();
  expect(screen.getByText('Instalar y verificar 0004')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 1' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Preparar nueva revisión administrativa' })).toBeDisabled();
  expect(guardar).not.toHaveBeenCalled();
});
it.each(['reserva', 'futura', 'destino_inexistente', 'cupo_agotado', 'plan_incompleto'])('no habilita una afectación bloqueada: %s', async (caso) => {
  Object.assign(datos.afectaciones[0], { puede_ejecutar: false, bloqueos: [caso] });
  if (caso === 'destino_inexistente') datos.afectaciones[0].destino = null;
  montar(); await listo();
  expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 1' })).toBeDisabled();
  expect(screen.getByText(caso)).toBeInTheDocument();
  expect(guardar).not.toHaveBeenCalled();
});
it('confirmación cancelada no envía la reubicación', async () => {
  montar(); await listo(); const u = await preparar();
  window.confirm.mockReturnValue(false);
  await u.click(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  expect(guardar).not.toHaveBeenCalled();
});
it('no ofrece ejecución con plan incompleto aunque una fila conserve una elegibilidad vieja', async () => {
  datos.plan_completo = false;
  montar(); await listo();
  expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 1' })).toBeDisabled();
});
it('envía solo el contrato autorizado, confirma y recarga', async () => {
  const actualizada = vi.fn(); montar({ actualizada }); await listo(); const u = await preparar();
  await u.click(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  await screen.findByText('Reubicación confirmada. Consulta su resultado histórico.');
  expect(guardar).toHaveBeenCalledWith('/ascensos/5/ejecutar/', { revision: 9, version: 8, afectacion: 11,
    motivo: 'Movimiento autorizado', clave: expect.stringMatching(/^[0-9a-f-]{36}$/) });
  expect(actualizada).toHaveBeenCalledOnce();
  expect(solicitar.mock.calls.filter(([ruta]) => ruta === '/ascensos/5/ejecucion/')).toHaveLength(2);
});
it('bloquea doble envío mientras espera respuesta', async () => {
  let resolver; guardar.mockImplementation(() => new Promise((r) => { resolver = r; }));
  montar(); await listo(); const u = await preparar();
  await u.dblClick(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  expect(guardar).toHaveBeenCalledOnce();
  expect(screen.getByRole('button', { name: 'Reintentar misma reubicación' })).toBeDisabled();
  resolver({ resultado: 30 }); await screen.findByText(/Reubicación confirmada/);
});
it('respuesta perdida permite reintentar exactamente la misma clave y payload', async () => {
  guardar.mockRejectedValueOnce(Object.assign(new Error('Respuesta perdida'), { estado: 0 }));
  montar(); await listo(); const u = await preparar();
  await u.click(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Motivo de la reubicación')).toBeDisabled();
  await u.click(screen.getByRole('button', { name: 'Reintentar misma reubicación' }));
  expect(guardar.mock.calls[0]).toEqual(guardar.mock.calls[1]);
});
it.each([403, 409, 400])('error %s exige actualizar y no permite reintento con versión vieja', async (estado) => {
  guardar.mockRejectedValueOnce(Object.assign(new Error('Actualiza el plan o tus permisos'), { estado }));
  montar(); await listo(); const u = await preparar();
  await u.click(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Reintentar misma reubicación' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Actualizar ejecución' })).toBeEnabled();
});
it('revisión completa exige motivo y no modifica aprobación', async () => {
  montar(); await listo(); const u = userEvent.setup();
  await u.click(screen.getByRole('button', { name: 'Preparar nueva revisión administrativa' }));
  await u.type(screen.getByLabelText('Motivo de la revisión administrativa'), 'Revisión operativa');
  await u.click(screen.getByRole('button', { name: 'Registrar revisión completa' }));
  await waitFor(() => expect(guardar).toHaveBeenCalledOnce());
  expect(guardar).toHaveBeenCalledWith('/ascensos/5/revisiones/', { version: 8, motivo: 'Revisión operativa',
    disposiciones: [{ afectacion: 11, disposicion: 'reubicar', destino: 101, motivo: 'Plan revisado' },
      { afectacion: 12, disposicion: 'reubicar', destino: 102, motivo: 'Plan revisado' }] });
  expect(await screen.findByText(/Revisión administrativa registrada/)).toBeInTheDocument();
});
it.each(['administrador', 'coordinador'])('integra reubicaciones en Propuestas para %s', async (valor) => {
  rol = valor; render(<Propuestas />);
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Reubicaciones del ascenso 5' }));
  await listo();
  if (valor === 'administrador') expect(screen.queryByRole('button', { name: 'Revisar ascenso 5' })).not.toBeInTheDocument();
});
it('profesor no recibe controles ni consulta de ejecución', async () => {
  rol = 'profesor'; render(<Propuestas />);
  await screen.findByRole('table', { name: 'Propuestas de ascenso institucional' });
  expect(screen.queryByRole('button', { name: 'Reubicaciones del ascenso 5' })).not.toBeInTheDocument();
  expect(solicitar.mock.calls.some(([r]) => r.includes('/ejecucion/'))).toBe(false);
});
it('errores de consulta muestran alerta sin habilitar escrituras', async () => {
  solicitar.mockRejectedValue(new Error('Acceso restringido'));
  montar(); await screen.findByRole('alert');
  expect(screen.queryByRole('button', { name: 'Preparar nueva revisión administrativa' })).not.toBeInTheDocument();
});

it('consulta coordinadora no habilita formalizacion aunque exista elegibilidad antigua', async () => {
  montar({formalizar:false}); await listo();
  expect(screen.getByRole('button',{name:'Preparar ejecuci\u00f3n de inscripci\u00f3n 1'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Preparar nueva revisi\u00f3n administrativa'})).toBeDisabled();
  expect(guardar).not.toHaveBeenCalled();
});
