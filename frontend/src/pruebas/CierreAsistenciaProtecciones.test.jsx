
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import userEvent from '@testing-library/user-event';

import { CierreAsistenciaSesion } from
  '../componentes/CierreAsistenciaSesion.jsx';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';

vi.mock('../api/cliente.js', () => ({
  solicitar: vi.fn(),
}));

vi.mock('../api/gestion.js', () => ({
  guardar: vi.fn(),
}));

function diferida() {
  let resolver;

  const promesa = new Promise((resolve) => {
    resolver = resolve;
  });

  return { promesa, resolver };
}

const sesion = {
  id: 12,
  version: 3,
  fecha: '2026-11-02',
  estado: 'planificada',
  asistencia_confirmada: false,
};

const padron = {
  version: 3,
  cerrada: false,
  requiere_preparacion: false,
  participantes: [
    {
      inscripcion: 10,
      deportista: 4,
      nombres: 'Ana',
      apellidos: 'Pérez',
      estado: 'asistio',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('F3.3: protecciones del cierre definitivo', () => {
  it('impide enviar dos cierres mientras espera respuesta', async () => {
    const usuario = userEvent.setup();
    const pendiente = diferida();
    const onCerrado = vi.fn();

    solicitar.mockResolvedValue(padron);
    guardar.mockReturnValue(pendiente.promesa);

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
        onCerrado={onCerrado}
        onCancelar={vi.fn()}
      />
    );

    const confirmacion = await screen.findByRole(
      'checkbox',
      {
        name: /Confirmo que revisé todos los estados/i,
      }
    );

    await usuario.click(confirmacion);

    const boton = screen.getByRole('button', {
      name: 'Confirmar cierre definitivo',
    });

    expect(boton).toBeEnabled();

    await usuario.click(boton);

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const botonPendiente = screen.getByRole(
      'button',
      {
        name: 'Cerrando asistencia…',
      }
    );

    expect(botonPendiente).toBeDisabled();
    expect(confirmacion).toBeDisabled();

    await usuario.click(botonPendiente);

    expect(guardar).toHaveBeenCalledTimes(1);

    pendiente.resolver({
      sesion: {
        ...sesion,
        version: 4,
        asistencia_confirmada: true,
      },
      asistencia: {
        ...padron,
        version: 4,
        cerrada: true,
      },
    });

    await waitFor(() => {
      expect(onCerrado).toHaveBeenCalledTimes(1);
    });

    expect(guardar).toHaveBeenCalledTimes(1);
  });

  it('descarta respuestas antiguas al cambiar de sesión', async () => {
    const antigua = diferida();

    solicitar.mockImplementation((ruta) => {
      if (ruta === '/sesiones/12/asistencia/') {
        return antigua.promesa;
      }

      if (ruta === '/sesiones/13/asistencia/') {
        return Promise.resolve({
          version: 5,
          cerrada: false,
          requiere_preparacion: false,
          participantes: [
            {
              inscripcion: 20,
              deportista: 7,
              nombres: 'Luis',
              apellidos: 'Gómez',
              estado: 'tarde',
            },
          ],
        });
      }

      throw new Error('Ruta inesperada');
    });

    const { rerender } = render(
      <CierreAsistenciaSesion
        sesion={sesion}
        onCancelar={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(solicitar).toHaveBeenCalledWith(
        '/sesiones/12/asistencia/'
      );
    });

    rerender(
      <CierreAsistenciaSesion
        sesion={{
          id: 13,
          version: 5,
          fecha: '2026-11-02',
          estado: 'planificada',
          asistencia_confirmada: false,
        }}
        onCancelar={vi.fn()}
      />
    );

    expect(
      await screen.findByText('Luis Gómez')
    ).toBeInTheDocument();

    antigua.resolver(padron);

    await waitFor(() => {
      expect(
        screen.queryByText('Ana Pérez')
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByText('Luis Gómez')
    ).toBeInTheDocument();

    expect(
      screen.getByRole('checkbox', {
        name: /Confirmo que revisé todos los estados/i,
      })
    ).toBeEnabled();

    expect(guardar).not.toHaveBeenCalled();
  });
});
