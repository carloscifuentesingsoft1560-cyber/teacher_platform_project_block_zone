import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

const pagina = (results) => ({ results, count: results.length, next: null });
const respuesta = (datos, estado = 200) => ({ ok: estado < 400, status: estado, headers: { get: () => 'application/json' }, json: async () => datos });
let rol, llamadas, fallo, version, propuestas;
beforeEach(() => {
  rol = 'administrador'; llamadas = []; fallo = null; version = 1;
  propuestas = [{ id: 1, tipo: 'nivel', deportista: 1, grupo_destino: 2, fecha_efectiva: '2026-10-28', justificacion: 'Propuesta ficticia', estado: 'pendiente', creado_por: 3, version: 1, nivel_anterior: 'Nivel 1', nivel_nuevo: 'Nivel 2' }];
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const url = new URL(ruta, 'http://localhost');
    const p = url.pathname, metodo = opciones.method || 'GET', datos = opciones.body ? JSON.parse(opciones.body) : null;
    llamadas.push({ p, metodo, datos });
    if (p.endsWith('/sesion/')) return respuesta({ usuario: { id: 2, nombre: 'Cuenta ficticia', rol } });
    if (p.endsWith('/csrf/')) return respuesta({ csrfToken: 'token-ficticio' });
    if (p.includes('/paneles/')) return respuesta({});
    const contratosPrivados = {
      '/api/acudientes/': ['nombres', 'apellidos', 'telefono', 'correo'],
      '/api/vinculos-acudientes/': ['deportista', 'acudiente', 'parentesco', 'fecha_inicio', 'fecha_fin', 'es_contacto_principal'],
      '/api/autorizaciones/': ['deportista', 'tipo', 'otorgante', 'vinculo_acudiente', 'decision', 'declarada_en', 'vigente_desde', 'vigente_hasta', 'referencia_evidencia'],
      '/api/tipos-autorizacion/': ['codigo', 'numero_version', 'finalidad', 'referencia_texto_aprobado'],
      '/api/politicas-datos/': ['codigo', 'finalidad', 'criterio_conservacion', 'procedimiento_supresion', 'referencia_aprobacion', 'edad_autonomia'],
    };
    if (metodo === 'POST' && contratosPrivados[p]) {
      const extras = Object.keys(datos).filter((k) => !contratosPrivados[p].includes(k));
      return extras.length ? respuesta({ detalle: 'Revisa los datos de la solicitud.', errores: Object.fromEntries(extras.map((k) => [k, 'Campo no permitido.'])) }, 400) : respuesta({ id: 9, ...datos }, 201);
    }
    if (fallo && p.includes(fallo.ruta)) return respuesta({ detalle: fallo.mensaje }, fallo.estado);
    if (p.endsWith('/tipos-documento/')) return respuesta(pagina([{ codigo: 'TI', nombre: 'Tarjeta de identidad', activo: true }]));
    if (p.endsWith('/deportistas/') && metodo === 'POST') return respuesta({ id: 2, ...datos }, 201);
    if (/\/deportistas\/ficticio\/$/.test(p) && metodo === 'PATCH') { version++; return respuesta({ ...datos, version }); }
    if (p.endsWith('/deportistas/')) return respuesta(pagina([{ id: 1, identificador_publico: 'ficticio', codigo_interno: 'ZB-FICTICIO', nombres: 'Ana', apellidos: 'Ejemplo', fecha_nacimiento: '2015-01-01', estado: 'activo', version }]));
    if (p.endsWith('/cupos/')) return respuesta({ cupo_maximo: 2, ocupacion_maxima: 1, disponibles: 1 });
    if (p.endsWith('/historial/')) return respuesta({ eventos: [{ id: 1, tipo: 'ingreso', fecha_efectiva: '2026-10-27', estado_resultante: 'activa' }], reservas: [] });
    if (p.includes('/inscripciones/') && metodo === 'POST') return respuesta({}, 200);
    if (p.endsWith('/inscripciones/')) return respuesta(pagina([{ id: 1, deportista: 1, nombre_deportista: 'Ana Ejemplo', nombre_grupo: 'Grupo ficticio', nivel: 'Nivel 1', periodo: 'Ciclo ficticio', estado: 'activa', fecha_ingreso: '2026-10-27', version: 1 }]));
    if (p.endsWith('/grupos/')) return respuesta(pagina([{ id: 1, nombre: 'Grupo ficticio' }]));
    if (p.endsWith('/propuestas/destinos/')) return respuesta(pagina([{ id: 1, codigo: 'FICTICIO', nombre: 'Grupo ficticio', nivel_nombre: 'Nivel 1', jornada: 'Domingo', periodo_nombre: 'Ciclo ficticio', horarios: [], disponibilidad: { disponibles: 1 } }]));
    if (p.endsWith('/propuestas/')) return respuesta(metodo === 'POST' ? { id: 2, ...datos } : pagina(propuestas), metodo === 'POST' ? 201 : 200);
    if (p.endsWith('/ascensos/')) return respuesta(pagina([]));
    if (/\/propuestas\/1\/(aprobar|rechazar)\//.test(p)) { propuestas = propuestas.map((x) => ({ ...x, estado: p.includes('/aprobar/') ? 'aplicada' : 'rechazada', resolucion: datos.resolucion })); return respuesta(propuestas[0]); }
    if (p.endsWith('/acudientes/')) return respuesta(pagina([{ id: 1, nombres: 'Adulto', apellidos: 'Ficticio', telefono: '3000000000', version: 1 }]));
    if (p.endsWith('/tipos-autorizacion/')) return respuesta(pagina([{ id: 1, finalidad: 'Finalidad ficticia aprobada' }]));
    if (p.endsWith('/autorizaciones/')) return respuesta(pagina([{ id: 1, deportista: 1, decision: 'otorgada', referencia_evidencia: 'Referencia privada ficticia', version: 1 }]));
    if (p.endsWith('/autorizaciones/1/revocar/')) return respuesta({});
    if (p.endsWith('/vinculos-acudientes/')) return respuesta(pagina([]));
    if (p.endsWith('/politicas-datos/')) return respuesta(pagina([]));
    return respuesta({}, 404);
  }));
});
function montar(ruta) { return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>); }

describe('Fase 3', () => {
  it.each([
    ['Acudientes', 'acudientes', { nombres: 'Acudiente', apellidos: 'Prueba Fase Tres', telefono: '3000000000', correo: 'acudiente.prueba@example.com' },
      [['Nombres', 'Acudiente'], ['Apellidos', 'Prueba Fase Tres'], ['Teléfono de contacto', '3000000000'], ['Correo de contacto', 'acudiente.prueba@example.com']]],
    ['Vínculos con acudientes', 'vinculos-acudientes', { fecha_inicio: '2026-10-28', deportista: 1, acudiente: 1 },
      [['Deportista', '1'], ['Acudiente', '1'], ['Inicio del vínculo', '2026-10-28']]],
    ['Autorizaciones diferenciadas', 'autorizaciones', { deportista: 1, tipo: 1, otorgante: 'acudiente', vinculo_acudiente: 1, decision: 'otorgada', declarada_en: new Date('2026-10-28T15:00').toISOString(), vigente_desde: '2026-10-28', referencia_evidencia: 'Referencia privada ficticia' },
      [['Deportista', '1'], ['Tipo y finalidad aprobada', '1'], ['Otorgante', 'acudiente'], ['Vínculo acreditado, cuando corresponda', '1'], ['Decisión acreditada', 'otorgada'], ['Fecha y hora de la declaración', '2026-10-28T15:00'], ['Vigente desde', '2026-10-28'], ['Referencia privada de la evidencia', 'Referencia privada ficticia']]],
    ['Tipos y versiones de autorización', 'tipos-autorizacion', { numero_version: 1, codigo: 'PRUEBA', finalidad: 'Finalidad ficticia', referencia_texto_aprobado: 'Referencia ficticia' },
      [['Código de finalidad', 'PRUEBA'], ['Finalidad institucional aprobada', 'Finalidad ficticia'], ['Referencia del texto aprobado', 'Referencia ficticia']]],
    ['Políticas de conservación y supresión', 'politicas-datos', { codigo: 'PRUEBA', finalidad: 'Finalidad ficticia', criterio_conservacion: 'Criterio ficticio', procedimiento_supresion: 'Procedimiento ficticio', referencia_aprobacion: 'Referencia ficticia' },
      [['Código de política', 'PRUEBA'], ['Finalidad', 'Finalidad ficticia'], ['Criterio institucional de conservación', 'Criterio ficticio'], ['Procedimiento autorizado de supresión', 'Procedimiento ficticio'], ['Referencia de aprobación institucional', 'Referencia ficticia']]],
  ])('crea %s con su contrato exclusivo desde la ruta filtrada', async (seccion, ruta, esperado, campos) => {
    const u = userEvent.setup(); montar('/administracion/autorizaciones?deportista=9');
    await u.click(await screen.findByRole('button', { name: seccion, exact: true }));
    await u.click(await screen.findByRole('button', { name: 'Crear registro de ' + seccion.toLowerCase() }));
    const f = screen.getByRole('form', { name: 'crear · ' + seccion });
    for (const [etiqueta, valor] of campos) {
      const campo = within(f).getByLabelText(etiqueta, { exact: true });
      if (campo.tagName === 'SELECT') {
        await waitFor(() => expect(within(campo).getAllByRole('option').length).toBeGreaterThan(1));
        fireEvent.change(campo, { target: { value: valor } });
      } else fireEvent.change(campo, { target: { value: valor } });
    }
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.find((x) => x.p === '/api/' + ruta + '/' && x.metodo === 'POST')?.datos).toEqual(esperado));
    expect(await screen.findByText('Operación guardada con auditoría.')).toBeInTheDocument();
  });
  it('lista fichas y navegación institucional', async () => {
    montar('/administracion/deportistas');
    expect(await screen.findByText('Documento pendiente')).toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Navegación principal' })).getByRole('link', { name: 'Acudientes y autorizaciones' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Crear deportista' })).toBeInTheDocument();
  });
  it('crea ficha mínima sin cuentas ni credenciales', async () => {
    const u = userEvent.setup(); montar('/administracion/deportistas');
    await u.click(await screen.findByRole('button', { name: 'Crear deportista' }));
    const f = screen.getByRole('form', { name: 'Crear ficha de deportista' });
    await u.type(within(f).getByLabelText('Nombres'), 'Nombre ficticio');
    await u.type(within(f).getByLabelText('Apellidos'), 'Ejemplo');
    fireEvent.change(within(f).getByLabelText('Fecha de nacimiento'), { target: { value: '2015-02-01' } });
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.some((x) => x.p.endsWith('/deportistas/') && x.metodo === 'POST')).toBe(true));
    expect(llamadas.find((x) => x.metodo === 'POST' && x.p.endsWith('/deportistas/')).datos).toEqual({ nombres: 'Nombre ficticio', apellidos: 'Ejemplo', fecha_nacimiento: '2015-02-01' });
  });
  it('edita con control de versión', async () => {
    const u = userEvent.setup(); montar('/administracion/deportistas');
    await u.click(await screen.findByRole('button', { name: 'Editar ficha de Ana' }));
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.find((x) => x.metodo === 'PATCH')?.datos.version).toBe(1));
  });
  it('profesor consulta y propone sin botones administrativos', async () => {
    rol = 'profesor'; montar('/profesor/inscripciones');
    expect(await screen.findByText('Ana Ejemplo')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Inscribir deportista' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Proponer inscripción o traslado' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Acudientes y autorizaciones' })).not.toBeInTheDocument();
  });
  it('reserva requiere vencimiento y envía versión', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/inscripciones');
    await u.click(await screen.findByRole('button', { name: 'suspender inscripción 1' }));
    const f = screen.getByRole('form', { name: 'Confirmar suspender' });
    await u.type(within(f).getByLabelText('Motivo administrativo'), 'Pausa ficticia');
    fireEvent.change(within(f).getByLabelText('Último día autorizado de reserva'), { target: { value: '2026-11-02' } });
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.find((x) => x.p.endsWith('/suspender/'))?.datos).toEqual({ motivo: 'Pausa ficticia', fecha_vencimiento: '2026-11-02', version: 1 }));
  });
  it('muestra conflicto de cupo sin cerrar formulario', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/inscripciones');
    await u.click(await screen.findByRole('button', { name: 'suspender inscripción 1' }));
    fallo = { ruta: '/suspender/', estado: 409, mensaje: 'El cupo cambió.' };
    const f = screen.getByRole('form', { name: 'Confirmar suspender' });
    await u.type(within(f).getByLabelText('Motivo administrativo'), 'Pausa ficticia');
    fireEvent.change(within(f).getByLabelText('Último día autorizado de reserva'), { target: { value: '2026-11-02' } });
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('El cupo cambió.')).toBeInTheDocument();
    expect(f).toBeInTheDocument();
  });
  it('historial muestra eventos sin editar el pasado', async () => {
    const u = userEvent.setup(); montar('/administracion/inscripciones');
    await u.click(await screen.findByRole('button', { name: 'Historial de inscripción 1' }));
    expect(await screen.findByText(/2026-10-27 · ingreso/)).toBeInTheDocument();
  });
  it('coordinador conserva aprobación administrativa con resolución y versión', async () => {
    propuestas = propuestas.map((p) => ({ ...p, tipo: 'traslado', nivel_nuevo: 'Nivel 1' }));
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/propuestas');
    await u.click(await screen.findByRole('button', { name: 'aprobar propuesta 1' }));
    await u.type(screen.getByLabelText('Resolución motivada'), 'Revisada presencialmente');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('aplicada')).toBeInTheDocument();
    expect(llamadas.find((x) => x.p.endsWith('/aprobar/')).datos.version).toBe(1);
  });
  it('administrador no sustituye aprobación pedagógica', async () => {
    montar('/administracion/propuestas');
    await screen.findByText(/Propuesta ficticia/);
    expect(screen.queryByRole('button', { name: 'aprobar propuesta 1' })).not.toBeInTheDocument();
  });
  it('profesor crea una propuesta sin ejecutarla', async () => {
    rol = 'profesor'; const u = userEvent.setup(); montar('/profesor/propuestas');
    await u.click(await screen.findByRole('button', { name: 'Crear propuesta' }));
    await screen.findByRole('option', { name: /Documento pendiente/ });
    await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'), '1');
    await screen.findByRole('option', { name: /FICTICIO · Grupo ficticio/ });
    await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'), '1');
    await u.type(screen.getByLabelText('Justificación de la propuesta'), 'Solicitud ficticia');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.some((x) => x.p.endsWith('/propuestas/') && x.metodo === 'POST')).toBe(true));
    expect(llamadas.filter((x) => x.metodo === 'POST' && x.p.includes('/inscripciones/'))).toHaveLength(0);
  });
  it('muestra bloqueo controlado mientras no se autoricen migraciones', async () => {
    fallo = { ruta: '/deportistas/', estado: 503, mensaje: 'La Fase 3 requiere migraciones pendientes de autorización.' };
    montar('/administracion/deportistas');
    expect(await screen.findByText(fallo.mensaje)).toBeInTheDocument();
  });
  it('autorización se revoca con motivo y no habilita medios', async () => {
    const u = userEvent.setup(); montar('/administracion/autorizaciones');
    await u.click(await screen.findByRole('button', { name: 'Autorizaciones diferenciadas' }));
    await u.click(await screen.findByRole('button', { name: 'Revocar autorización 1' }));
    await u.type(screen.getByLabelText('Motivo acreditado de revocación'), 'Solicitud acreditada');
    await u.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.find((x) => x.p.endsWith('/revocar/'))?.datos).toEqual({ motivo: 'Solicitud acreditada', version: 1 }));
    expect(screen.getByText(/no habilitan acceso digital/)).toBeInTheDocument();
  });
});
