import { beforeEach, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RolesCuenta } from '../componentes/RolesCuenta.jsx';
import { Identidades } from '../paginas/Identidades.jsx';
import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';
vi.mock('../api/cliente.js',()=>({solicitar:vi.fn()}));
vi.mock('../api/gestion.js',()=>({guardar:vi.fn()}));
beforeEach(()=>{
  vi.clearAllMocks();vi.stubGlobal('confirm',vi.fn(()=>true));
  solicitar.mockImplementation(async(ruta)=>{
    if(ruta.includes('/roles/'))return [{id:3,rol:'profesor',vigente:true,version:1}];
    if(ruta.startsWith('/usuarios/'))return {count:1,results:[{id:4,username:'Cuenta ficticia'}],next:null};
    return {count:0,results:[],next:null};
  });
  guardar.mockResolvedValue({});
});
it('otorga facultad adicional sin reemplazar rol principal',async()=>{
  render(<RolesCuenta cuenta={{id:4,username:'Cuenta ficticia'}} cerrar={vi.fn()} actualizada={vi.fn()} />);
  await screen.findByRole('button',{name:'Revocar profesor'});
  const u=userEvent.setup();await u.type(screen.getByLabelText('Motivo del cambio'),'Función adicional');
  await u.selectOptions(screen.getByLabelText('Facultad adicional'),'routesetter');
  await u.click(screen.getByRole('button',{name:'Otorgar facultad'}));
  await waitFor(()=>expect(guardar).toHaveBeenCalledWith('/usuarios/4/roles/',{rol:'routesetter',motivo:'Función adicional'}));
});
it('revoca la pertenencia exacta con version y conserva el historial',async()=>{
  render(<RolesCuenta cuenta={{id:4,username:'Cuenta ficticia'}} cerrar={vi.fn()} actualizada={vi.fn()} />);
  await screen.findByRole('button',{name:'Revocar profesor'});
  const u=userEvent.setup();await u.type(screen.getByLabelText('Motivo del cambio'),'Fin de docencia');
  await u.click(screen.getByRole('button',{name:'Revocar profesor'}));
  await waitFor(()=>expect(guardar).toHaveBeenCalledWith('/usuarios/4/revocar-rol/',{pertenencia:3,version:1,motivo:'Fin de docencia'}));
});
it('acredita identidad solo tras seleccionar perfil y confirmar contraste',async()=>{
  render(<Identidades />);const u=userEvent.setup();
  expect(screen.getByRole('button',{name:'Acreditar enlace'})).toBeDisabled();
  await screen.findByRole('option',{name:'Cuenta ficticia'});
  await u.selectOptions(screen.getByLabelText('Registro existente',{selector:'select'}),'4');
  const evidencia='123e4567-e89b-42d3-a456-426614174000';
  await u.type(screen.getByLabelText('Referencia privada de verificación'),evidencia);
  expect(screen.getByRole('button',{name:'Acreditar enlace'})).toBeDisabled();
  await u.click(screen.getByRole('checkbox'));
  await u.click(screen.getByRole('button',{name:'Acreditar enlace'}));
  await waitFor(()=>expect(guardar).toHaveBeenCalledWith('/identidad/',{persona:null,tipo:'usuario',perfil:4,evidencia,identidad_contrastada:true}));
});
