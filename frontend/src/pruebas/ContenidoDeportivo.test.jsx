import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Curriculo, Biblioteca, MaterialesDocentes, FuentesCurriculares } from '../paginas/ContenidoDeportivo.jsx';
import { solicitar, prepararCsrf } from '../api/cliente.js';
import { MemoryRouter } from 'react-router-dom';
import { Estructura } from '../componentes/Estructura.jsx';
let usuario;
vi.mock('../autenticacion/ContextoAutenticacion.jsx', () => ({ usarAutenticacion: () => ({ usuario }), rutaDelRol: (r) => ({coordinador:'/coordinacion',administrador:'/administracion'}[r] || '/'+r) }));
vi.mock('../api/cliente.js', () => ({ solicitar: vi.fn(), prepararCsrf: vi.fn() }));
const malla = { id:1, uuid:'malla-1', nombre:'Malla ficticia', programa:1, numero:1, revision:2, estado:'en_revision', naturaleza:'propuesta_revisada', vigente:false };
const ejercicio = { id:1, uuid:'ejercicio-1', nombre:'Pies ficticios', numero:1, revision:1, estado:'borrador', naturaleza:'adaptacion_docente', disciplina:1, programas:[1], pasos:[], adaptaciones:[], exigencias:[], materiales:[], objetivo:'Precisión', poblacion:'Ficticia', metodologia:'Juego', descripcion:'En suelo', riesgos:'Caídas', controles:'Supervisión', derechos:'Redacción propia', duracion_min:5, duracion_max:10 };
beforeEach(() => {
  vi.clearAllMocks(); usuario = { id:1, rol:'coordinador', roles:['coordinador'] }; prepararCsrf.mockResolvedValue({});
  solicitar.mockImplementation(async (ruta, opciones) => {
    if (ruta.endsWith('/estructura/')) return { fases:[{id:1,uuid:'fase-1',nombre:'Exploración'}],semanas:[],clases:[],elementos:[],actividades:[] };
    if (ruta.includes('/aprobar/')) return { ...malla, estado:'aprobado', vigente:true, revision:3 };
    if (ruta.includes('/derivar/')) return { ...malla, uuid:'malla-2', numero:2, estado:'borrador', revision:1 };
    if (ruta.startsWith('/curriculo/versiones/')) return { count:1,results:[malla] };
    if (ruta.startsWith('/curriculo/programas/')) return { count:1,results:[{id:1,nombre:'Nivel 1',formalizado:true}] };
    if (ruta.startsWith('/organizacion/disciplinas/')) return { count:1,results:[{id:1,nombre:'Escalada'}] };
    if (ruta.startsWith('/biblioteca/versiones/')) return opciones ? ejercicio : { count:1,results:[ejercicio] };
    return {count:0,results:[]};
  });
});
it('distingue clase prevista de sesión ejecutada con encabezado accesible',async()=>{
  render(<Curriculo />);expect(screen.getByRole('heading',{level:1,name:'Currículo'})).toBeInTheDocument();
  expect(screen.getByText(/No registran sesiones realizadas/)).toBeInTheDocument();await screen.findByRole('button',{name:/Malla ficticia/});
});
it('coordinador publica edición exacta con CSRF y versión esperada',async()=>{
  render(<Curriculo />);const u=userEvent.setup();await u.click(await screen.findByRole('button',{name:/Malla ficticia/}));
  await u.click(screen.getByRole('button',{name:'Aprobar y publicar esta edición'}));
  await waitFor(()=>expect(solicitar).toHaveBeenCalledWith('/curriculo/versiones/malla-1/aprobar/',expect.objectContaining({method:'POST'})));
  const op=solicitar.mock.calls.find(([r])=>r.endsWith('/aprobar/'))[1];expect(JSON.parse(op.body).revision).toBe(2);expect(prepararCsrf).toHaveBeenCalled();
});
it('profesor no recibe control de publicación institucional',async()=>{
  usuario={id:2,rol:'profesor',roles:['profesor','routesetter']};render(<Curriculo />);await userEvent.click(await screen.findByRole('button',{name:/Malla ficticia/}));
  expect(screen.queryByRole('button',{name:'Aprobar y publicar esta edición'})).not.toBeInTheDocument();
});
it('retirar requiere motivo y no escribe con el campo vacío',async()=>{
  render(<Curriculo />);const u=userEvent.setup();await u.click(await screen.findByRole('button',{name:/Malla ficticia/}));await u.click(screen.getByRole('button',{name:'Retirar con motivo'}));
  expect(screen.getByRole('alert')).toHaveTextContent('Escribe un motivo');expect(solicitar.mock.calls.some(([r])=>r.endsWith('/retirar/'))).toBe(false);
});
it('biblioteca expone seguridad y no atribuye aprobación a candidatos',async()=>{
  render(<Biblioteca />);await userEvent.click(await screen.findByRole('button',{name:/Pies ficticios/}));
  expect(screen.getByText(/Los candidatos históricos no se publican/)).toBeInTheDocument();expect(screen.getByRole('heading',{name:'Adaptaciones'})).toBeInTheDocument();
  expect(screen.getByLabelText('Controles de seguridad')).toHaveValue('Supervisión');
});
it('filtros de búsqueda usan texto codificado',async()=>{
  render(<Biblioteca />);const u=userEvent.setup();await u.type(screen.getByLabelText('Buscar ejercicio'),'pies & equilibrio');await u.click(screen.getByRole('button',{name:'Buscar'}));
  await waitFor(()=>expect(solicitar).toHaveBeenCalledWith('/biblioteca/versiones/?buscar=pies%20%26%20equilibrio'));
});
it('formulario nuevo etiqueta población metodología y duraciones sin imponer cero',async()=>{
  render(<Biblioteca />);await userEvent.click(screen.getByRole('button',{name:'Preparar ejercicio propio'}));
  expect(screen.getByLabelText('Población')).toBeRequired();expect(screen.getByLabelText('Metodología')).toBeRequired();expect(screen.getByLabelText('Duración mínima orientativa (min)')).not.toBeRequired();
});
it('conflicto de edición deja mensaje recuperable',async()=>{
  const anterior=solicitar.getMockImplementation();solicitar.mockImplementation(async(r,o)=>{if(r.endsWith('/aprobar/'))throw Object.assign(new Error('Conflicto'),{estado:409});return anterior(r,o);});
  render(<Curriculo />);const u=userEvent.setup();await u.click(await screen.findByRole('button',{name:/Malla ficticia/}));await u.click(screen.getByRole('button',{name:'Aprobar y publicar esta edición'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('La edición cambió');
});
it('material exige declaración de derechos y no publica al crear',async()=>{
  render(<MaterialesDocentes />);expect(screen.getByRole('checkbox',{name:/Tengo derechos/})).toBeRequired();expect(screen.queryByRole('button',{name:'Aprobar y publicar esta edición'})).not.toBeInTheDocument();
  expect(screen.getByText(/No adjuntes datos de deportistas/)).toBeInTheDocument();
});
it('vista de fuentes distingue confirmar archivo y publicar',async()=>{
  render(<FuentesCurriculares />);expect(screen.getByRole('heading',{name:'Fuentes e importación curricular'})).toBeInTheDocument();
  expect(screen.getByText(/la confirmación no publica una malla/)).toBeInTheDocument();expect(screen.getByLabelText('Excel original')).toHaveAttribute('accept','.xlsx');
});
it('navegación coordinadora incluye currículo biblioteca y custodia',()=>{
  render(<MemoryRouter><Estructura /></MemoryRouter>);
  expect(screen.getByRole('link',{name:'Currículo'})).toHaveAttribute('href','/coordinacion/curriculo');
  expect(screen.getByRole('link',{name:'Biblioteca de ejercicios'})).toHaveAttribute('href','/coordinacion/biblioteca');
  expect(screen.getByRole('link',{name:'Fuentes e importación'})).toBeInTheDocument();
});
it('routesetter tiene biblioteca técnica sin acceso a deportistas o currículo',()=>{
  usuario={id:2,rol:'routesetter',roles:['routesetter']};render(<MemoryRouter><Estructura /></MemoryRouter>);
  expect(screen.getByRole('link',{name:'Biblioteca de ejercicios'})).toHaveAttribute('href','/routesetter/biblioteca');
  expect(screen.queryByRole('link',{name:'Currículo'})).not.toBeInTheDocument();expect(screen.queryByRole('link',{name:'Deportistas'})).not.toBeInTheDocument();
});
it('portal acudiente no incorpora navegación al contenido docente',()=>{
  usuario={id:3,rol:'acudiente',roles:['acudiente']};render(<MemoryRouter><Estructura /></MemoryRouter>);
  expect(screen.queryByRole('link',{name:'Materiales docentes'})).not.toBeInTheDocument();
});
