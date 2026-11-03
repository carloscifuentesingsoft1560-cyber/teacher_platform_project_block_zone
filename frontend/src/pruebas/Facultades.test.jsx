import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ComprobacionFacultad } from '../componentes/ComprobacionFacultad.jsx';

const referencia = 'e49d9985-68ae-4a38-9df1-8faf703c824b';
const vinculo = { id: 3, deportista: 9, acudiente: 1, parentesco: 'Madre', es_contacto_principal: true, version: 7 };
let envios, resultadoApi, historia, errorHistoria, completada;
const responder = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
beforeEach(() => {
  envios = []; historia = []; errorHistoria = false; resultadoApi = 200; completada = vi.fn();
  vi.stubGlobal('confirm', vi.fn(() => true));
  vi.stubGlobal('fetch', vi.fn(async (ruta, opciones = {}) => {
    if (ruta.includes('/historial-facultades/')) return responder(errorHistoria ? { detalle: 'Migración pendiente.' } : historia, errorHistoria ? 503 : 200);
    if (ruta.includes('/tipos-autorizacion/')) return responder({ results: [{ id: 4, finalidad: 'Finalidad aprobada ficticia', numero_version: 2 }], next: null });
    if (ruta.includes('/csrf/')) return responder({ csrfToken: 'ficticio' });
    if (ruta.endsWith('/verificar/')) {
      envios.push(JSON.parse(opciones.body));
      return responder(resultadoApi === 200 ? {} : { detalle: 'El vínculo cambió. Recarga la versión.' }, resultadoApi);
    }
    return responder({}, 404);
  }));
});
function montar() { render(<ComprobacionFacultad vinculo={vinculo} cancelar={vi.fn()} completada={completada} />); }
async function llenar(resultado = 'verificada') {
  const f = await screen.findByRole('form', { name: 'Registrar comprobación de facultad' });
  await screen.findByRole('option', { name: 'Finalidad aprobada ficticia · v2' });
  const campos = [
    ['Alcance: finalidad y versión aprobada', '4'], ['Método de comprobación', 'documental'],
    ['Clave privada de custodia de evidencia (UUID)', referencia], ['Fecha y hora de la comprobación', '2026-10-28T09:00'],
    ['Resultado de la revisión', resultado], ['Inicio de vigencia de la facultad', '2026-10-28'],
  ];
  for (const [etiqueta, valor] of campos) fireEvent.change(within(f).getByLabelText(etiqueta), { target: { value: valor } });
  return f;
}

describe('Comprobaciones de facultades', () => {
  it('explica parentesco, contacto y alcance sin formulario vacío', async () => {
    montar();
    expect(await screen.findByRole('form')).toBeInTheDocument();
    expect(screen.getByText(/Parentesco declarado: Madre/)).toBeInTheDocument();
    expect(screen.getByText(/no acreditan representación/)).toBeInTheDocument();
    expect(screen.getByText(/El responsable y la fecha de registro los establece el servidor/)).toBeInTheDocument();
    expect(screen.getByLabelText('Clave privada de custodia de evidencia (UUID)')).toBeRequired();
    expect(screen.queryByLabelText('Responsable')).not.toBeInTheDocument();
  });
  it('no envía confirmación vacía sin evidencia', async () => {
    montar();
    await userEvent.click(await screen.findByRole('button', { name: 'Guardar cambios' }));
    expect(envios).toHaveLength(0);
  });
  it('impide acreditar una revisión insuficiente', async () => {
    montar();const f = await llenar();
    await userEvent.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Una revisión insuficiente');
    expect(envios).toHaveLength(0);
  });
  it.each(['verificada','rechazada','revocada','pendiente'])('registra %s con alcance, evidencia y versión sin números de identidad', async (resultado) => {
    montar();const f = await llenar(resultado);
    if (resultado === 'verificada') {
      await userEvent.click(within(f).getByLabelText('Contrasté la identidad sin copiar sus documentos'));
      await userEvent.click(within(f).getByLabelText('Revisé evidencia suficiente para este alcance'));
    }
    await userEvent.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(completada).toHaveBeenCalledOnce());
    expect(envios[0]).toEqual({ version: 7, tipo_autorizacion: 4, metodo: 'documental', referencia_evidencia: referencia,
      resultado, identidad_contrastada: resultado === 'verificada', facultad_contrastada: resultado === 'verificada',
      comprobada_en: new Date('2026-10-28T09:00').toISOString(), vigente_desde: '2026-10-28', vigente_hasta: null });
    expect(envios[0]).not.toHaveProperty('numero_documento');
    expect(envios[0]).not.toHaveProperty('responsable');
  });
  it('mantiene formulario ante conflicto sin reenvío automático', async () => {
    resultadoApi = 409;montar();const f = await llenar('rechazada');
    await userEvent.click(within(f).getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El vínculo cambió');
    expect(completada).not.toHaveBeenCalled();expect(f).toBeInTheDocument();expect(envios).toHaveLength(1);
  });
  it('no permite decidir si no puede leer el historial', async () => {
    errorHistoria = true;montar();
    expect(await screen.findByRole('alert')).toHaveTextContent('Migración pendiente');
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
    expect(envios).toHaveLength(0);
  });
});
