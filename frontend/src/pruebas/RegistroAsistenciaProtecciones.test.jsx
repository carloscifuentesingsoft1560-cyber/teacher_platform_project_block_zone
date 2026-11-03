
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { RegistroAsistenciaSesion } from
  '../componentes/RegistroAsistenciaSesion.jsx';

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
  version: 2,
  estado: 'planificada',
};

const padron = {
  version: 2,
  cerrada: false,
  requiere_preparacion: false,
  participantes: [
    {
      inscripcion: 10,
      deportista: 4,
      nombres: 'Ana',
      apellidos: 'Pérez',
      estado: '',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('F3.2: protecciones de asistencia docente', () => {
  it('impide el doble envío mientras espera respuesta', async () => {
    const usuario = userEvent.setup();
    const pendiente = diferida();
    const onGuardado = vi.fn();

    solicitar.mockResolvedValue(padron);
    guardar.mockReturnValue(pendiente.promesa);

    render(
      <RegistroAsistenciaSesion
        sesion={sesion}
        onGuardado={onGuardado}
        onCancelar={vi.fn()}
      />
    );

    await screen.findByRole('combobox', {
      name: 'Asistencia de Ana Pérez',
    });

    const boton = screen.getByRole('button', {
      name: 'Guardar asistencia',
    });

    await usuario.click(boton);

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardando asistencia…',
      })
    ).toBeDisabled();

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardando asistencia…',
      })
    );

    expect(guardar).toHaveBeenCalledTimes(1);

    pendiente.resolver({
      sesion: { ...sesion, version: 3 },
      asistencia: { ...padron, version: 3 },
    });

    await waitFor(() => {
      expect(onGuardado).toHaveBeenCalledTimes(1);
    });

    expect(guardar).toHaveBeenCalledTimes(1);
  });

  it('descarta el padrón antiguo al cambiar de sesión', async () => {
    const usuario = userEvent.setup();
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
              estado: '',
            },
          ],
        });
      }

      throw new Error('Ruta no esperada');
    });

    const { rerender } = render(
      <RegistroAsistenciaSesion
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
      <RegistroAsistenciaSesion
        sesion={{
          id: 13,
          version: 5,
          estado: 'planificada',
        }}
        onCancelar={vi.fn()}
      />
    );

    expect(
      await screen.findByRole('combobox', {
        name: 'Asistencia de Luis Gómez',
      })
    ).toBeInTheDocument();

    antigua.resolver(padron);

    await waitFor(() => {
      expect(
        screen.queryByRole('combobox', {
          name: 'Asistencia de Ana Pérez',
        })
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByRole('combobox', {
        name: 'Asistencia de Luis Gómez',
      })
    ).toBeEnabled();

    expect(guardar).not.toHaveBeenCalled();

    // La nueva sesión continúa siendo editable.
    await usuario.selectOptions(
      screen.getByRole('combobox', {
        name: 'Asistencia de Luis Gómez',
      }),
      'asistio'
    );

    expect(
      screen.getByRole('combobox', {
        name: 'Asistencia de Luis Gómez',
      })
    ).toHaveValue('asistio');
  });
});
