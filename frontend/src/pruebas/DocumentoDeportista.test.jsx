import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ProveedorAutenticacion } from '../autenticacion/ContextoAutenticacion.jsx';
import { Aplicacion } from '../Aplicacion.jsx';

const pagina = (results) => ({ results, count: results.length, next: null });
const respuesta = (datos, estado = 200) => ({ ok: estado < 400, status: estado, headers: { get: () => 'application/json' }, json: async () => datos });
let rol, llamadas, ficha, conflicto;
function vista() {
  if (rol === 'profesor') {
    const mascara = ficha.numero_documento ? '****' + (ficha.numero_documento.length > 4 ? ficha.numero_documento.slice(-4) : '') : '';
    return { id: ficha.id, identificador_publico: ficha.identificador_publico, nombres: ficha.nombres, apellidos: ficha.apellidos, estado: ficha.estado, tipo_documento: ficha.tipo_documento,
      numero_documento_enmascarado: mascara, documento_presentacion: mascara ? ficha.tipo_documento + ' ' + mascara : 'Documento pendiente' };
  }
  return { ...ficha, documento_presentacion: ficha.numero_documento ? ficha.tipo_documento + (ficha.tipo_documento === 'PA' ? ' (' + ficha.pais_emisor + ')' : '') + ' ' + ficha.numero_documento : 'Documento pendiente' };
}
beforeEach(() => {
  rol = 'administrador'; llamadas = []; conflicto = false;
  ficha = { id: 1, identificador_publico: 'ficticio', codigo_interno: 'ZB-NO-VISIBLE', nombres: 'Nombre', apellidos: 'Ficticio', fecha_nacimiento: '2015-01-01', estado: 'activo', version: 1, tipo_documento: 'TI', numero_documento: '001234567890', pais_emisor: 'CO' };
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    const u = new URL(ruta, 'http://localhost'), p = u.pathname, metodo = opciones.method || 'GET';
    const datos = opciones.body ? JSON.parse(opciones.body) : null;
    llamadas.push({ ruta, p, metodo, datos });
    if (p.endsWith('/sesion/')) return respuesta({ usuario: { id: 2, nombre: 'Cuenta ficticia', rol } });
    if (p.endsWith('/csrf/')) return respuesta({ csrfToken: 'csrf-ficticio' });
    if (p.endsWith('/tipos-documento/')) return respuesta(pagina([{ codigo: 'TI', nombre: 'Tarjeta de identidad' }, { codigo: 'CC', nombre: 'Cédula de ciudadanía' }, { codigo: 'PA', nombre: 'Pasaporte' }]));
    if (p.endsWith('/cambiar-documento/')) {
      if (conflicto) return respuesta({ detalle: 'La ficha cambió. Actualiza la información.' }, 409);
      ficha = { ...ficha, ...datos, numero_documento: datos.numero_documento?.replace(/[.\s]/g, ''), version: ficha.version + 1 };
      return respuesta(vista());
    }
    if (p.endsWith('/buscar-documento/')) return respuesta(pagina([vista()]));
    if (p.endsWith('/historial-documental/')) return respuesta(pagina(ficha.version === 1 ? [] : [{ id: 1, motivo: 'nuevo_documento', tipo_anterior: 'TI', documento_anterior_enmascarado: '****7890', tipo_nuevo: 'CC', documento_nuevo_enmascarado: '****7890', actor: 2, fecha: '2026-10-28T12:00:00Z' }]));
    if (p.endsWith('/trayectoria/')) return respuesta(pagina([]));
    if (p.endsWith('/deportistas/ficticio/') && metodo === 'PATCH') { ficha = { ...ficha, ...datos, version: ficha.version + 1 }; return respuesta(vista()); }
    if (p.endsWith('/deportistas/ficticio/')) return respuesta(vista());
    if (p.endsWith('/deportistas/')) return respuesta(metodo === 'POST' ? { id: 2, ...datos } : pagina([vista()]), metodo === 'POST' ? 201 : 200);
    return respuesta(pagina([]));
  }));
});
function montar(ruta) { render(<MemoryRouter initialEntries={[ruta]}><ProveedorAutenticacion><Aplicacion /></ProveedorAutenticacion></MemoryRouter>); }

describe('Identificación documental', () => {
  it('documento principal y rutas estables sin mostrar ZB o UUID', async () => {
    montar('/administracion/deportistas');
    expect(await screen.findByText('TI 001234567890')).toBeInTheDocument();
    expect(screen.queryByText('ZB-NO-VISIBLE')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver ficha individual' })).toHaveAttribute('href', '/administracion/deportistas/ficticio');
    expect(screen.queryByText('ficticio', { exact: true })).not.toBeInTheDocument();
  });
  it('alta conserva ceros y envía el número como texto', async () => {
    const u = userEvent.setup(); montar('/administracion/deportistas');
    await u.click(await screen.findByRole('button', { name: 'Crear deportista' }));
    const f = screen.getByRole('form', { name: 'Crear ficha de deportista' });
    await u.selectOptions(within(f).getByLabelText('Tipo de documento'), 'TI');
    await u.type(within(f).getByLabelText('Número de documento'), '000123');
    await u.type(within(f).getByLabelText('Nombres'), 'Persona ficticia');
    await u.type(within(f).getByLabelText('Apellidos'), 'Prueba');
    fireEvent.change(within(f).getByLabelText('Fecha de nacimiento'), { target: { value: '2015-01-01' } });
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.find((l) => l.p.endsWith('/deportistas/') && l.metodo === 'POST')?.datos.numero_documento).toBe('000123'));
    expect(llamadas.find((l) => l.metodo === 'POST' && l.p.endsWith('/deportistas/')).datos.pais_emisor).toBe('CO');
  });
  it('documento pendiente sin números provisionales', async () => {
    ficha.tipo_documento = null; ficha.numero_documento = null; ficha.pais_emisor = null;
    montar('/administracion/deportistas');
    expect(await screen.findByText('Documento pendiente')).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('ZB-NO-VISIBLE');
  });
  it('cambia documento por acción dedicada, motivo y versión', async () => {
    rol = 'coordinador'; const u = userEvent.setup(); montar('/coordinacion/deportistas/ficticio');
    await u.click(await screen.findByRole('button', { name: 'Cambiar documento' }));
    const f = screen.getByRole('form', { name: 'Cambio documental' });
    await u.selectOptions(within(f).getByLabelText('Tipo de documento'), 'CC');
    await u.type(within(f).getByLabelText('Número de documento'), '001234567890');
    await u.selectOptions(within(f).getByLabelText('Motivo del cambio documental'), 'nuevo_documento');
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('CC 001234567890')).toBeInTheDocument();
    const l = llamadas.find((l) => l.p.endsWith('/cambiar-documento/'));
    expect(l.datos).toEqual({ tipo_documento: 'CC', numero_documento: '001234567890', pais_emisor: 'CO', version: 1, motivo: 'nuevo_documento' });
    expect(llamadas.filter((l) => l.metodo === 'PATCH')).toHaveLength(0);
  });
  it('conflicto mantiene formulario sin repetir automáticamente', async () => {
    conflicto = true; const u = userEvent.setup(); montar('/administracion/deportistas/ficticio');
    await u.click(await screen.findByRole('button', { name: 'Cambiar documento' }));
    const f = screen.getByRole('form', { name: 'Cambio documental' });
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByText('La ficha cambió. Actualiza la información.')).toBeInTheDocument();
    expect(f).toBeInTheDocument();
    expect(llamadas.filter((l) => l.p.endsWith('/cambiar-documento/'))).toHaveLength(1);
  });
  it('profesor ve máscara y no recibe controles de gestión', async () => {
    rol = 'profesor'; montar('/profesor/deportistas/ficticio');
    expect(await screen.findByText('TI ****7890')).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain('001234567890');
    expect(document.body.innerHTML).not.toContain('ZB-NO-VISIBLE');
    expect(screen.queryByRole('button', { name: 'Cambiar documento' })).not.toBeInTheDocument();
    expect(llamadas.some((l) => l.p.endsWith('/historial-documental/'))).toBe(false);
  });
  it('número corto queda completamente enmascarado', async () => {
    rol = 'profesor'; ficha.numero_documento = '1234'; montar('/profesor/deportistas');
    expect(await screen.findByText('TI ****')).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain('1234');
    expect(screen.queryByRole('button', { name: 'Buscar por documento' })).not.toBeInTheDocument();
  });
  it('consulta exacta usa POST y no coloca el documento en URL', async () => {
    const u = userEvent.setup(); montar('/administracion/deportistas');
    await u.click(await screen.findByRole('button', { name: 'Buscar por documento' }));
    const f = screen.getByRole('form', { name: 'Buscar por documento' });
    await u.selectOptions(within(f).getByLabelText('Tipo de documento'), 'PA');
    await u.type(within(f).getByLabelText('Número de documento'), 'AB-001');
    await u.type(within(f).getByLabelText('País emisor (código ISO)'), 've');
    await u.click(within(f).getByRole('button', { name: 'Consultar documento' }));
    await waitFor(() => expect(llamadas.some((l) => l.p.endsWith('/buscar-documento/') && l.metodo === 'POST')).toBe(true));
    expect(llamadas.find((l) => l.p.endsWith('/buscar-documento/')).datos).toEqual({ tipo_documento: 'PA', numero_documento: 'AB-001', pais_emisor: 'VE' });
    expect(llamadas.every((l) => !l.ruta.includes('AB-001'))).toBe(true);
  });
  it('edición ordinaria no modifica documentos ni copia datos de ficha al PATCH', async () => {
    const u = userEvent.setup(); montar('/administracion/deportistas');
    await u.click(await screen.findByRole('button', { name: 'Editar ficha de Nombre' }));
    const f = screen.getByRole('form', { name: 'Editar ficha de deportista' });
    expect(within(f).queryByLabelText('Número de documento')).not.toBeInTheDocument();
    await u.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(llamadas.some((l) => l.metodo === 'PATCH')).toBe(true));
    const d = llamadas.find((l) => l.metodo === 'PATCH').datos;
    expect(d).not.toHaveProperty('numero_documento');
    expect(d).not.toHaveProperty('tipo_documento');
    expect(d.version).toBe(1);
  });
});
