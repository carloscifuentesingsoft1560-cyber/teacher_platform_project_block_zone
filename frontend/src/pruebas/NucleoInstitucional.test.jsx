import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

let cuenta, llamadas;
const pagina = {count:0,results:[],next:null};
beforeEach(() => {
  cuenta={id:10,username:'ficticio',nombre:'Cuenta ficticia',rol:'profesor',roles:['profesor','administrador'],facultades:[]};
  llamadas=[];
  vi.stubGlobal('fetch',vi.fn(async (url,opciones={}) => {
    llamadas.push([url,opciones]);
    let datos=pagina;
    if(url.endsWith('/autenticacion/sesion/')) datos={usuario:structuredClone(cuenta)};
    if(url.endsWith('/csrf/')) datos={csrfToken:'ficticio'};
    if(url.includes('/paneles/')) datos={rol:'profesor',nombre:'Cuenta ficticia',mensaje:'Espacio'};
    return {ok:true,status:200,json:async()=>datos};
  }));
});
function montar(ruta) {return render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>);}

it('elige espacio por una facultad vigente conservando la cuenta',async()=>{
  montar('/administracion/usuarios');
  expect(await screen.findByRole('heading',{name:'Administración de usuarios'})).toBeInTheDocument();
  expect(screen.getByLabelText('Espacio de trabajo')).toHaveValue('administrador');
  await userEvent.setup().selectOptions(screen.getByLabelText('Espacio de trabajo'),'profesor');
  expect(await screen.findByText('ESPACIO PROFESOR')).toBeInTheDocument();
});
it('rol principal no permite entrar si la pertenencia fue revocada',async()=>{
  cuenta.rol='administrador';cuenta.roles=['profesor'];
  montar('/administracion/usuarios');
  expect(await screen.findByRole('heading',{name:'Acceso restringido'})).toBeInTheDocument();
  expect(llamadas.some(([u])=>u==='/api/usuarios/')).toBe(false);
});
it('refresca facultades al recuperar foco y cierra acceso revocado',async()=>{
  montar('/administracion/usuarios');await screen.findByRole('heading',{name:'Administración de usuarios'});
  cuenta.roles=['profesor'];fireEvent(window,new Event('focus'));
  expect(await screen.findByRole('heading',{name:'Acceso restringido'})).toBeInTheDocument();
});
it.each(['routesetter','deportista','acudiente'])('rol %s no activa módulos futuros ni listas privadas',async(rol)=>{
  cuenta.rol=rol;cuenta.roles=[rol];montar('/'+rol);
  await screen.findByText(/Sus módulos se habilitarán/);
  expect(screen.queryByRole('link',{name:'Deportistas'})).not.toBeInTheDocument();
  expect(llamadas.some(([u])=>u.startsWith('/api/deportistas/'))).toBe(false);
});
