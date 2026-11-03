import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

const pagina = (results) => ({ results, count: results.length, next: null });
const respuesta = (datos, status = 200) => ({ ok: status < 400, status, json: async () => datos });
let rol, datos, llamadas, resultados, retener, liberar;
beforeEach(() => {
  rol = 'coordinador'; llamadas = []; resultados = []; retener = false; liberar = null;
  vi.stubGlobal('confirm', vi.fn(() => true));
  const grupo = (id) => ({ id, codigo: 'ESC-FICTICIO-' + id, nombre: 'Grupo ficticio ' + id,
    nivel: id === 1 ? 'Nivel 1' : 'Nivel 2', periodo: 'Ciclo ficticio',
    horarios: [{ dia: 0, hora_inicio: '12:00', hora_fin: '13:00' }], capacidad: 2, ocupacion_maxima: 0,
    reservas_vigentes: 0, disponibles: 2 });
  datos = { progresion: 7, version: 4, revision: 3, revision_numero: 1, estado_decision: 'aprobada',
    estado_ejecucion: 'pendiente', ejecucion_habilitada: true, plan_completo: true,
    discrepancias: [], advertencias_destinos: [], inscripciones_nuevas: [], excepciones: [],
    deportista: 'Deportista Ficticio B3-D', disciplina: 'Escalada', nivel_origen: 'Nivel 1', nivel_destino: 'Nivel 2',
    afectaciones: [{ afectacion: 11, inscripcion: 10, estado: 'activa', situacion: 'activa',
      fecha_ingreso: '2026-10-20', origen: grupo(1), destino: grupo(2), destino_id: 2,
      disposicion: 'reubicar', motivo: 'Plan ficticio revisado', puede_ejecutar: true, ejecutada: false, bloqueos: [] }] };
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const p = new URL(ruta, 'http://localhost').pathname;
    const metodo = opciones.method || 'GET';
    llamadas.push({ p, metodo, opciones, datos: opciones.body ? JSON.parse(opciones.body) : null });
    if (p.endsWith('/autenticacion/sesion/')) return respuesta({ usuario: { id: 1, rol, nombre: 'Cuenta ficticia' } });
    if (p.endsWith('/autenticacion/csrf/')) return respuesta({ csrfToken: 'csrf-ficticio-b3d' });
    if (p === '/api/propuestas/') return respuesta(pagina([]));
    if (p === '/api/ascensos/') return respuesta(pagina([{ id: 7, nombre_deportista: datos.deportista,
      disciplina_nombre: 'Escalada', nivel_origen_nombre: 'Nivel 1', nivel_destino_nombre: 'Nivel 2',
      justificacion: 'Propuesta ficticia', estado_decision: datos.estado_decision, estado_plan: 'preparado',
      profesor_proponente: { nombre: 'Profesor ficticio' } }]));
    if (p === '/api/ascensos/7/ejecucion/') return respuesta(structuredClone(datos));
    if (p === '/api/ascensos/7/revisiones/') return respuesta(pagina([]));
    if (p === '/api/ascensos/7/resultados/') return respuesta(pagina(resultados));
    if (p === '/api/ascensos/7/ejecutar/' && metodo === 'POST') {
      if (retener) await new Promise((r) => { liberar = r; });
      datos = { ...datos, version: 5, estado_ejecucion: 'ejecutado',
        afectaciones: datos.afectaciones.map((f) => ({ ...f, ejecutada: true, puede_ejecutar: false,
          estado: 'finalizada', bloqueos: ['Movimiento confirmado'] })) };
      resultados = [{ id: 31, revision_id: 3, afectacion_id: 11, origen_id: 10, destino_id: 20,
        estado: 'ejecutada', fecha_efectiva: '2026-10-30', motivo: 'Movimiento ficticio', actor_id: 1 }];
      return respuesta({ resultado: 31, revision: 3, afectacion: 11, origen: 10, destino: 20, estado: 'ejecutada' });
    }
    return respuesta({ detalle: 'Ruta simulada no prevista: ' + p }, 404);
  }));
});
function montar(ruta) {
  return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);
}
async function abrir(ruta) {
  montar(ruta); const u = userEvent.setup();
  await u.click(await screen.findByRole('button', { name: 'Reubicaciones del ascenso 7' }));
  await screen.findByRole('heading', { name: 'Deportista Ficticio B3-D · Escalada' });
  return u;
}
const envios = () => llamadas.filter((r) => r.metodo === 'POST');

it.each([['coordinador', '/coordinacion/propuestas'], ['administrador', '/administracion/propuestas']])(
  'ruta %s permite consultar un rechazo con revisiones/resultados vacíos sin ejecutar', async (papel, ruta) => {
    rol = papel; datos.estado_decision = 'rechazada'; datos.revision = null; datos.revision_numero = null; datos.plan_completo = false;
    datos.afectaciones[0].puede_ejecutar = false;
    await abrir(ruta);
    expect(screen.getByRole('heading', { name: 'Propuestas y decisiones' })).toBeInTheDocument();
    expect(await within(screen.getByRole('region', { name: 'Historial de revisiones' })).findByText('Sin registros históricos.')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Historial de resultados' })).getByText('Sin registros históricos.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 10' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Preparar nueva revisión administrativa' })).toBeDisabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(envios()).toHaveLength(0);
  });

it.each([['administrador', '/administracion/propuestas']])(
  'ruta %s integra confirmación, CSRF, ejecución simulada y resultado histórico', async (papel, ruta) => {
    rol = papel; const u = await abrir(ruta);
    await u.click(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 10' }));
    await u.type(screen.getByLabelText('Motivo de la reubicación'), 'Movimiento ficticio');
    await u.click(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
    expect(window.confirm).toHaveBeenCalledOnce();
    await screen.findByText(/Reubicación confirmada/);
    expect(await screen.findByText(/Resultado 31/)).toBeInTheDocument();
    expect(envios()).toHaveLength(1);
    expect(envios()[0].opciones.headers['X-CSRFToken']).toBe('csrf-ficticio-b3d');
    expect(envios()[0].datos).toEqual({ revision: 3, version: 4, afectacion: 11,
      clave: expect.any(String), motivo: 'Movimiento ficticio' });
    expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 10' })).toBeDisabled();
    expect(envios().some((r) => r.p.includes('/aprobar/'))).toBe(false);
  });

it.each(['reserva', 'futura', 'plan_incompleto'])('ruta real de React respeta bloqueo %s y muestra advertencia', async (caso) => {
  datos.plan_completo = caso !== 'plan_incompleto';
  datos.afectaciones[0] = { ...datos.afectaciones[0], situacion: caso, puede_ejecutar: false,
    bloqueos: ['Condición bloqueada: ' + caso] };
  await abrir('/coordinacion/propuestas');
  expect(screen.getByText('Condición bloqueada: ' + caso)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 10' })).toBeDisabled();
  expect(envios()).toHaveLength(0);
});

it('doble clic en la ruta completa produce un solo envío pendiente', async () => {
  rol = 'administrador'; const u = await abrir('/administracion/propuestas'); retener = true;
  await u.click(screen.getByRole('button', { name: 'Preparar ejecución de inscripción 10' }));
  await u.type(screen.getByLabelText('Motivo de la reubicación'), 'Movimiento ficticio');
  await u.dblClick(screen.getByRole('button', { name: 'Confirmar reubicación individual' }));
  await waitFor(() => expect(envios()).toHaveLength(1));
  expect(screen.getByRole('button', { name: 'Reintentar misma reubicación' })).toBeDisabled();
  liberar(); await screen.findByText(/Reubicación confirmada/);
});

it('profesor no accede por URL a la pantalla de coordinación', async () => {
  rol = 'profesor'; montar('/coordinacion/propuestas');
  await screen.findByRole('heading', { name: 'Acceso restringido' });
  expect(llamadas.some((r) => r.p.includes('/ascensos/'))).toBe(false);
});

it('coordinador consulta pero no formaliza aunque el estado anterior marcara elegibilidad', async () => {
  rol='coordinador';await abrir('/coordinacion/propuestas');
  expect(screen.getByRole('button',{name:'Preparar ejecuci\u00f3n de inscripci\u00f3n 10'})).toBeDisabled();
  expect(envios()).toHaveLength(0);
});
