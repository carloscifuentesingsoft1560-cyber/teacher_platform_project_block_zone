import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FormularioPropuesta } from '../componentes/FormularioPropuesta.jsx';
import { Propuestas } from '../paginas/Propuestas.jsx';

vi.mock('../autenticacion/ContextoAutenticacion.jsx', () => ({ usarAutenticacion: () => ({ usuario: { rol: 'profesor' } }) }));
const pagina = (results) => ({ results, count: results.length, next: null, previous: null });
const respuesta = (datos, status = 200) => ({ ok: status < 400, status, json: async () => datos });
const origen = { id: 18, grupo_codigo: 'ESC-N1-SEM', grupo_nombre: 'Mi grupo entre semana', periodo_nombre: 'Periodo vigente',
  nivel_origen: { id: 101, nombre: 'Nivel 1', orden: 2 } };
const siguiente = { id: 1, nombre: 'Nivel 2', codigo: 'nivel-2', disciplina: 3, orden: 3 };
const historica = { id: 1, tipo: 'nivel', justificacion: 'Historia anterior conservada', estado: 'pendiente',
  fecha_efectiva: '2026-10-28', nivel_anterior: 'Nivel 1', nivel_nuevo: 'Nivel 2',
  mecanismo_deshabilitado: true, aviso_procedimiento: 'Mecanismo anterior deshabilitado. Revisión administrativa.' };
let llamadas, vacio, fallo, incompatible, demoraPost, resolverPost, demoraNivel, resolverNivel, ascensos, completada;
beforeEach(() => {
  llamadas = []; vacio = ''; fallo = ''; incompatible = false; demoraPost = false; demoraNivel = false;
  resolverPost = null; resolverNivel = null; ascensos = []; completada = vi.fn();
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const u = new URL(ruta, 'http://localhost'), metodo = opciones.method || 'GET';
    const datos = opciones.body ? JSON.parse(opciones.body) : null;
    llamadas.push({ ruta: u.pathname, params: u.searchParams, metodo, datos });
    if (u.pathname.endsWith('/csrf/')) return respuesta({ csrfToken: 'ficticio' });
    if (u.pathname === '/api/deportistas/') return respuesta(pagina([
      { id: 9, nombres: 'Ana', apellidos: 'Ficticia', documento_presentacion: 'TI ****1234' },
      { id: 10, nombres: 'Bea', apellidos: 'Ficticia', documento_presentacion: 'Documento pendiente' },
    ]));
    if (u.pathname === '/api/ascensos/contexto/') {
      if (fallo === 'contexto') return respuesta({ detalle: 'Tu asignación ya no está vigente.' }, 403);
      if (u.searchParams.get('vista') === 'disciplinas') return respuesta(pagina(vacio === 'disciplinas' ? [] : [{ id: 3, codigo: 'escalada', nombre: 'Escalada' }]));
      return respuesta(pagina(vacio === 'referencias' ? [] : [{ ...origen, id: u.searchParams.get('deportista') === '10' ? 19 : 18 }]));
    }
    if (u.pathname === '/api/ascensos/niveles/') {
      if (fallo === 'niveles') return respuesta({ detalle: 'La referencia ya no está autorizada.' }, 404);
      const datos = pagina(vacio === 'niveles' ? [] : [{ ...siguiente, orden: incompatible ? 4 : 3 }]);
      if (demoraNivel) { demoraNivel = false; return new Promise((resolve) => { resolverNivel = () => resolve(respuesta(datos)); }); }
      return respuesta(datos);
    }
    if (u.pathname === '/api/ascensos/' && metodo === 'POST') {
      if (fallo === 'post') return respuesta({ detalle: 'Existe una progresión abierta. Solicita revisión a coordinación.' }, 409);
      if (fallo === 'red') throw new Error('Conexión interrumpida');
      expect(Object.keys(datos).sort()).toEqual(['deportista', 'disciplina', 'inscripcion_referencia', 'justificacion', 'nivel_destino']);
      const nuevo = { id: 1, nombre_deportista: 'Ana Ficticia', disciplina_nombre: 'Escalada',
        nivel_origen_nombre: 'Nivel 1', nivel_destino_nombre: 'Nivel 2', periodo_nombre: 'Periodo vigente',
        justificacion: datos.justificacion, estado_decision: 'pendiente', estado_plan: 'pendiente' };
      const completar = () => { ascensos = [nuevo]; return respuesta(nuevo, 201); };
      if (demoraPost) return new Promise((resolve) => { resolverPost = () => resolve(completar()); });
      return completar();
    }
    if (u.pathname === '/api/ascensos/') {
      if (u.searchParams.has('search')) return respuesta({ detalle: 'Campo search no permitido.' }, 400);
      const estado = u.searchParams.get('estado_decision');
      return respuesta(pagina(ascensos.filter((p) => !estado || p.estado_decision === estado)));
    }
    if (u.pathname === '/api/propuestas/') return respuesta(pagina([historica]));
    return respuesta({ detalle: 'Ruta no prevista por el contrato.' }, 404);
  }));
});
const posts = () => llamadas.filter((l) => l.metodo === 'POST');
async function abrir(enPagina = false) {
  const u = userEvent.setup();
  if (enPagina) { render(<Propuestas />); await u.click(screen.getByRole('button', { name: 'Crear propuesta' })); }
  else render(<FormularioPropuesta completada={completada} cancelar={vi.fn()} />);
  await u.selectOptions(screen.getByLabelText('Tipo de propuesta'), 'ascenso');
  return u;
}
async function persona(u, valor = '9') {
  await screen.findByRole('option', { name: /TI \*\*\*\*1234/ });
  await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'), valor);
}
async function disciplina(u) {
  await screen.findByRole('option', { name: /escalada · Escalada/ });
  await u.selectOptions(screen.getByLabelText('Disciplina disponible'), '3');
}
async function referencia(u, valor = '18') {
  await screen.findByRole('option', { name: /ESC-N1-SEM/ });
  await u.selectOptions(screen.getByLabelText('Inscripción activa de referencia'), valor);
}
async function completar(u) {
  await persona(u); await disciplina(u); await referencia(u);
  await waitFor(() => expect(screen.getByLabelText('Nivel propuesto')).toHaveTextContent('Nivel 2'));
  await u.type(screen.getByLabelText('Justificación pedagógica y deportiva'), 'Motivo pedagógico ficticio');
}

describe('Interfaz docente de ascensos institucionales', () => {
  it('ofrece las tres modalidades sin el cambio de nivel antiguo', async () => {
    await abrir();
    const tipo = screen.getByLabelText('Tipo de propuesta');
    for (const nombre of ['Inscripción adicional', 'Traslado al mismo nivel', 'Ascenso institucional']) expect(within(tipo).getByRole('option', { name: nombre })).toBeInTheDocument();
    expect(within(tipo).queryByRole('option', { name: 'Cambio de nivel' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Grupo destino autorizado')).not.toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });
  it('consulta disciplina y referencias solo después de elegir contexto autorizado', async () => {
    const u = await abrir();
    expect(llamadas.some((l) => l.ruta.includes('/ascensos/contexto'))).toBe(false);
    await persona(u); await disciplina(u); await referencia(u);
    await waitFor(() => expect(screen.getByLabelText('Nivel propuesto')).toHaveTextContent('Nivel 2'));
    const nivel = llamadas.find((l) => l.ruta.endsWith('/niveles/'));
    expect(Object.fromEntries(nivel.params)).toEqual({ deportista: '9', disciplina: '3', inscripcion_referencia: '18' });
    expect(screen.getByLabelText('Nivel de origen de la referencia')).toHaveTextContent('Nivel 1');
    expect(llamadas.some((l) => /organizacion|inscripciones|destinos/.test(l.ruta))).toBe(false);
  });
  it('envía solo intención docente y confirma la respuesta pendiente', async () => {
    const u = await abrir(); await completar(u);
    await u.click(screen.getByRole('button', { name: 'Registrar propuesta de ascenso' }));
    await waitFor(() => expect(completada).toHaveBeenCalledOnce());
    expect(posts()).toHaveLength(1);
    expect(posts()[0]).toMatchObject({ ruta: '/api/ascensos/', datos: { deportista: 9, disciplina: 3,
      inscripcion_referencia: 18, nivel_destino: 1, justificacion: 'Motivo pedagógico ficticio' } });
    expect(completada.mock.calls[0][0].modalidad).toBe('ascenso');
    expect(llamadas.some((l) => /aprobar|ejecutar|trasladar/.test(l.ruta))).toBe(false);
  });
  it('bloquea doble submit y los controles durante el envío', async () => {
    demoraPost = true; const u = await abrir(); await completar(u);
    const f = screen.getByRole('form', { name: 'Nueva propuesta de ascenso institucional' });
    fireEvent.submit(f); fireEvent.submit(f);
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(screen.getByRole('button', { name: 'Guardando…' })).toBeDisabled();
    expect(screen.getByLabelText('Tipo de propuesta')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
    await act(async () => resolverPost());
    await waitFor(() => expect(completada).toHaveBeenCalledOnce());
  });
  it('limpia disciplina, referencia y nivel al cambiar deportista', async () => {
    const u = await abrir(); await completar(u);
    await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'), '10');
    expect(screen.getByLabelText('Disciplina disponible')).toHaveValue('');
    expect(screen.queryByLabelText('Inscripción activa de referencia')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Nivel propuesto')).not.toBeInTheDocument();
    await disciplina(u); await referencia(u, '19');
    await waitFor(() => expect(llamadas.filter((l) => l.ruta.endsWith('/niveles/')).at(-1).params.get('deportista')).toBe('10'));
  });
  it('descarta una respuesta de nivel tardía de otro contexto', async () => {
    demoraNivel = true; const u = await abrir(); await persona(u); await disciplina(u); await referencia(u);
    await waitFor(() => expect(resolverNivel).toBeTypeOf('function'));
    await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'), '10');
    await act(async () => resolverNivel());
    expect(screen.queryByLabelText('Nivel propuesto')).not.toBeInTheDocument();
    expect(posts()).toHaveLength(0);
  });
  it.each(['disciplinas', 'referencias'])('presenta estado vacío sin %s válidas', async (tipo) => {
    vacio = tipo; const u = await abrir(); await persona(u);
    if (tipo === 'referencias') await disciplina(u);
    expect(await screen.findByText('No hay opciones para esta búsqueda.')).toBeInTheDocument();
    const f = screen.getByRole('form', { name: 'Nueva propuesta de ascenso institucional' });
    fireEvent.submit(f);
    expect(await screen.findByRole('alert')).toHaveTextContent('Selecciona deportista');
    expect(posts()).toHaveLength(0);
  });
  it('explica ausencia de nivel superior sin solicitar un grupo de destino', async () => {
    vacio = 'niveles'; const u = await abrir(); await persona(u); await disciplina(u); await referencia(u);
    expect(await screen.findByText(/No hay un nivel inmediatamente superior activo disponible/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Grupo destino autorizado')).not.toBeInTheDocument();
    fireEvent.submit(screen.getByRole('form', { name: 'Nueva propuesta de ascenso institucional' }));
    expect(posts()).toHaveLength(0);
  });
  it('rechaza un nivel no consecutivo aun si la respuesta simulada lo incluyera', async () => {
    incompatible = true; const u = await abrir(); await persona(u); await disciplina(u); await referencia(u);
    expect(await screen.findByRole('alert')).toHaveTextContent('no es consecutivo');
    fireEvent.submit(screen.getByRole('form', { name: 'Nueva propuesta de ascenso institucional' }));
    expect(posts()).toHaveLength(0);
  });
  it('muestra pérdida de permisos sin revelar expedientes', async () => {
    fallo = 'contexto'; const u = await abrir(); await persona(u);
    expect(await screen.findByRole('alert')).toHaveTextContent('asignación ya no está vigente');
    expect(screen.queryByLabelText('Inscripción activa de referencia')).not.toBeInTheDocument();
  });
  it('permite reconsultar un nivel tras error de autorización', async () => {
    fallo = 'niveles'; const u = await abrir(); await persona(u); await disciplina(u); await referencia(u);
    expect(await screen.findByRole('alert')).toHaveTextContent('referencia ya no está autorizada');
    fallo = ''; await u.click(screen.getByRole('button', { name: 'Actualizar nivel disponible' }));
    await waitFor(() => expect(screen.getByLabelText('Nivel propuesto')).toHaveTextContent('Nivel 2'));
  });
  it('no confirma creación cuando la API devuelve un conflicto', async () => {
    fallo = 'post'; const u = await abrir(); await completar(u);
    await u.click(screen.getByRole('button', { name: 'Registrar propuesta de ascenso' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('progresión abierta');
    expect(completada).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Justificación pedagógica y deportiva')).toHaveValue('Motivo pedagógico ficticio');
  });
  it('advierte sobre resultado incierto de red sin reenviar automáticamente', async () => {
    fallo = 'red'; const u = await abrir(); await completar(u);
    await u.click(screen.getByRole('button', { name: 'Registrar propuesta de ascenso' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('consulta el listado antes de reenviar');
    expect(posts()).toHaveLength(1); expect(completada).not.toHaveBeenCalled();
  });
  it('valida justificación y contexto ante submit manipulado', async () => {
    await abrir(); fireEvent.submit(screen.getByRole('form', { name: 'Nueva propuesta de ascenso institucional' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('justificación');
    expect(screen.getByLabelText('Justificación pedagógica y deportiva')).toHaveAttribute('maxlength', '500');
    expect(posts()).toHaveLength(0);
  });
  it('cancelar la confirmación no publica', async () => {
    const u = await abrir(); await completar(u); vi.mocked(window.confirm).mockReturnValue(false);
    await u.click(screen.getByRole('button', { name: 'Registrar propuesta de ascenso' }));
    expect(posts()).toHaveLength(0);
  });
  it('mantiene historial y ascensos separados y actualiza la bandeja solo tras éxito', async () => {
    const u = await abrir(true);
    const lista = screen.getByRole('region', { name: 'Ascensos institucionales' });
    expect(await within(lista).findByText('No hay propuestas institucionales para esta consulta.')).toBeInTheDocument();
    await completar(u); await u.click(screen.getByRole('button', { name: 'Registrar propuesta de ascenso' }));
    expect(await screen.findByText(/Ascenso institucional propuesto, pendiente/)).toHaveAttribute('role', 'status');
    expect(await within(screen.getByRole('table', { name: 'Propuestas de ascenso institucional' })).findByText('Motivo pedagógico ficticio')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Propuestas anteriores y administrativas' })).getByText('Mecanismo anterior deshabilitado. Revisión administrativa.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /aprobar|ejecutar/i })).not.toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Propuestas de ascenso institucional' })).queryByRole('button')).not.toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Propuestas anteriores y administrativas' })).getByRole('button', { name: 'Cancelar propuesta 1' })).toBeInTheDocument();
    expect(llamadas.filter((l) => l.ruta === '/api/ascensos/' && l.metodo === 'GET').every((l) => !l.params.has('search'))).toBe(true);
  });
  it('filtra los estados institucionales con el contrato exacto', async () => {
    render(<Propuestas />); const u = userEvent.setup();
    await u.selectOptions(screen.getByLabelText('Filtrar decisión de ascenso'), 'pendiente');
    await waitFor(() => expect(llamadas.some((l) => l.ruta === '/api/ascensos/' && l.params.get('estado_decision') === 'pendiente')).toBe(true));
    expect(llamadas.filter((l) => l.ruta === '/api/ascensos/').every((l) => [...l.params.keys()].every((k) => ['page', 'estado_decision'].includes(k)))).toBe(true);
  });
  it('incluye etiquetas, instrucciones, avisos y navegación accesibles', async () => {
    const u = await abrir(true); await completar(u);
    const texto = screen.getByLabelText('Justificación pedagógica y deportiva');
    expect(texto).toBeRequired(); expect(texto).toHaveAccessibleDescription(/Hasta 500 caracteres/);
    expect(screen.getByLabelText('Nivel propuesto')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('navigation', { name: 'Paginación de ascensos institucionales' })).toBeInTheDocument();
    expect(screen.getByText(/No aprueba, no cambia grupos ni niveles efectivos/)).toBeInTheDocument();
  });
});
