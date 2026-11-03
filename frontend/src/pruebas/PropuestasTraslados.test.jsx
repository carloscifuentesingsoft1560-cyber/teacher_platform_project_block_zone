import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FormularioPropuesta } from '../componentes/FormularioPropuesta.jsx';

const pagina = (results) => ({ results, count: results.length, next: null });
const responder = (datos, status = 200) => ({ ok: status < 400, status, json: async () => datos });
const destino = { id: 7, codigo: 'ESC-N1-DOM', nombre: 'Escalada domingo', nivel_nombre: 'Nivel 1', jornada: 'Domingo',
  periodo_nombre: 'Ciclo vigente', fecha_inicio_periodo: '2026-10-01', fecha_fin_periodo: '2026-12-31',
  horarios: [{ dia:6, hora_inicio:'09:00', hora_fin:'10:00' }], disponibilidad: { disponibles:2, desde:'2026-10-29', hasta:'2026-12-31' } };
let llamadas, multi, conflicto, completada, cancelar;
beforeEach(() => {
  llamadas=[];multi=false;conflicto=false;completada=vi.fn();cancelar=vi.fn();
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const u = new URL(ruta,'http://localhost'), metodo=opciones.method || 'GET';
    llamadas.push({ p:u.pathname, params:u.searchParams, metodo, datos:opciones.body ? JSON.parse(opciones.body) : null });
    if (u.pathname.endsWith('/csrf/')) return responder({ csrfToken:'ficticio' });
    if (u.pathname.endsWith('/deportistas/')) return responder(pagina([
      { id:1,nombres:'Ana',apellidos:'Ficticia',documento_presentacion:'TI ****1234' },
      { id:2,nombres:'Otra',apellidos:'Ficticia',documento_presentacion:'Documento pendiente' },
    ]));
    if (u.pathname.endsWith('/inscripciones/')) return responder(pagina([
      { id:Number(u.searchParams.get('deportista')) + 10,nombre_grupo:'Origen entre semana',nivel:'Nivel 1',periodo:'Ciclo vigente' },
    ]));
    if (u.pathname.endsWith('/propuestas/destinos/')) {
      if (multi && u.searchParams.get('tipo') === 'nivel') return responder({ detalle:'El cambio global requiere el Incremento 2; no se realizará un cambio parcial.' },400);
      return responder(pagina([u.searchParams.get('tipo') === 'nivel' ? { ...destino, id:8,nivel_nombre:'Nivel 2' } : destino]));
    }
    if (u.pathname.endsWith('/propuestas/') && metodo === 'POST') return responder(conflicto ? { detalle:'El cupo cambió. Actualiza los destinos.' } : { id:1 },conflicto ? 409 : 201);
    return responder({},404);
  }));
});
function montar() { render(<FormularioPropuesta completada={completada} cancelar={cancelar} />); }
async function seleccionarPersona(u,id='1') {
  await screen.findByRole('option',{name:/TI \*\*\*\*1234/});
  await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'),id);
}
async function elegirTraslado(u,tipo='traslado') {
  await u.selectOptions(screen.getByLabelText('Tipo de propuesta'),tipo);
  await seleccionarPersona(u);
  await screen.findByRole('option',{name:/Origen entre semana/});
  await u.selectOptions(screen.getByLabelText('Inscripción de origen'),'11');
}
const posts=()=>llamadas.filter((r)=>r.metodo==='POST');
const consultasDestino=()=>llamadas.filter((r)=>r.p.endsWith('/destinos/'));

describe('Propuestas entre grupos institucionales',()=>{
  it('no consulta destinos hasta disponer de contexto y filtra el origen por deportista',async()=>{
    montar();const u=userEvent.setup();
    await u.selectOptions(screen.getByLabelText('Tipo de propuesta'),'traslado');
    await seleccionarPersona(u);
    expect(consultasDestino()).toHaveLength(0);
    await screen.findByRole('option',{name:/Origen entre semana/});
    expect(llamadas.find((r)=>r.p.endsWith('/inscripciones/')).params.get('deportista')).toBe('1');
    await u.selectOptions(screen.getByLabelText('Inscripción de origen'),'11');
    await screen.findByRole('option',{name:/ESC-N1-DOM/});
    expect(consultasDestino().at(-1).params.get('inscripcion_origen')).toBe('11');
    expect(consultasDestino().at(-1).params.get('tipo')).toBe('traslado');
    expect(llamadas.some((r)=>r.p.startsWith('/api/organizacion/grupos'))).toBe(false);
  });
  it('presenta horarios, jornada y disponibilidad sin expedientes del destino',async()=>{
    montar();const u=userEvent.setup();await elegirTraslado(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});
    await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    const panel=screen.getByRole('region',{name:'Información mínima del destino'});
    expect(panel).toHaveTextContent('Domingo: 09:00 a 10:00');
    expect(panel).toHaveTextContent('Disponibilidad consultada: 2 plazas');
    expect(within(panel).queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('option',{name:/Origen entre semana/})).toBeInTheDocument();
    expect(within(screen.getByLabelText('Grupo destino autorizado')).queryByRole('option',{name:/Origen entre semana/})).not.toBeInTheDocument();
  });
  it('envía traslado con IDs internos sin ejecutar inscripciones ni aprobación',async()=>{
    montar();const u=userEvent.setup();await elegirTraslado(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    await u.type(screen.getByLabelText('Justificación de la propuesta'),'Cambio de jornada');
    await u.click(screen.getByRole('button',{name:'Guardar cambios'}));
    await waitFor(()=>expect(completada).toHaveBeenCalledOnce());
    expect(posts()).toHaveLength(1);
    expect(posts()[0].p).toBe('/api/propuestas/');
    expect(posts()[0].datos).toEqual({ tipo:'traslado',deportista:1,inscripcion_origen:11,grupo_destino:7,justificacion:'Cambio de jornada',fecha_efectiva:expect.any(String) });
  });
  it('limpia origen y destino al cambiar deportista',async()=>{
    montar();const u=userEvent.setup();await elegirTraslado(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    await u.selectOptions(screen.getByLabelText('Deportista de mis grupos'),'2');
    expect(screen.queryByLabelText('Grupo destino autorizado')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Inscripción de origen')).toHaveValue('');
    await screen.findByRole('option',{name:/Origen entre semana/});
    await u.selectOptions(screen.getByLabelText('Inscripción de origen'),'12');
    await screen.findByRole('option',{name:/ESC-N1-DOM/});
    expect(consultasDestino().at(-1).params.get('deportista')).toBe('2');
    expect(consultasDestino().at(-1).params.get('inscripcion_origen')).toBe('12');
  });
  it('cambio de operación obliga a seleccionar origen y destino nuevos',async()=>{
    montar();const u=userEvent.setup();await seleccionarPersona(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    await u.selectOptions(screen.getByLabelText('Tipo de propuesta'),'traslado');
    expect(screen.queryByLabelText('Grupo destino autorizado')).not.toBeInTheDocument();
    await screen.findByRole('option',{name:/Origen entre semana/});await u.selectOptions(screen.getByLabelText('Inscripción de origen'),'11');
    await screen.findByRole('option',{name:/ESC-N1-DOM.*Nivel 1/});
    expect(screen.getByLabelText('Grupo destino autorizado')).toHaveValue('');
  });
  it('reemplaza el cambio de nivel antiguo sin consultar destinos individuales',async()=>{
    montar();const u=userEvent.setup();await u.selectOptions(screen.getByLabelText('Tipo de propuesta'),'ascenso');
    expect(screen.getByRole('form',{name:'Nueva propuesta de ascenso institucional'})).toBeInTheDocument();
    expect(screen.queryByRole('option',{name:'Cambio de nivel'})).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Grupo destino autorizado')).not.toBeInTheDocument();
    expect(consultasDestino()).toHaveLength(0);
    expect(posts()).toHaveLength(0);
  });
  it('mantiene el formulario ante revalidación fallida y permite actualizar candidatos',async()=>{
    conflicto=true;montar();const u=userEvent.setup();await elegirTraslado(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    await u.type(screen.getByLabelText('Justificación de la propuesta'),'Motivo ficticio');
    await u.click(screen.getByRole('button',{name:'Guardar cambios'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('El cupo cambió');
    expect(completada).not.toHaveBeenCalled();expect(posts()).toHaveLength(1);
    await u.click(screen.getByRole('button',{name:'Actualizar destinos compatibles'}));
    await waitFor(()=>expect(consultasDestino()).toHaveLength(2));
    expect(screen.getByLabelText('Grupo destino autorizado')).toHaveValue('');
  });
  it('sin contexto completo no publica aunque se manipule el submit',async()=>{
    montar();fireEvent.submit(screen.getByRole('form',{name:'Nueva propuesta docente'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('Selecciona deportista');expect(posts()).toHaveLength(0);
  });
  it('inscripción adicional no envía origen y no abre datos del grupo general',async()=>{
    montar();const u=userEvent.setup();await seleccionarPersona(u);
    await screen.findByRole('option',{name:/ESC-N1-DOM/});await u.selectOptions(screen.getByLabelText('Grupo destino autorizado'),'7');
    await u.type(screen.getByLabelText('Justificación de la propuesta'),'Grupo adicional');
    await u.click(screen.getByRole('button',{name:'Guardar cambios'}));
    await waitFor(()=>expect(completada).toHaveBeenCalledOnce());
    expect(posts()[0].datos.tipo).toBe('inscripcion');expect(posts()[0].datos).not.toHaveProperty('inscripcion_origen');
    expect(llamadas.some((x)=>x.p.startsWith('/api/organizacion/'))).toBe(false);
  });
});
