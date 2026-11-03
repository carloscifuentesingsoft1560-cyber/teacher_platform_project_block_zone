
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
    {
      inscripcion: 11,
      deportista: 5,
      nombres: 'Luis',
      apellidos: 'Gómez',
      estado: '',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();

  solicitar.mockResolvedValue(padron);

  guardar.mockResolvedValue({
    sesion: {
      ...sesion,
      version: 3,
    },
    asistencia: {
      ...padron,
      version: 3,
    },
  });
});

describe('F3.2: registro docente de asistencia', () => {
  it('guarda el padrón completo con UUID y versión', async () => {
    const usuario = userEvent.setup();
    const onGuardado = vi.fn();

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

    await usuario.selectOptions(
      screen.getByLabelText('Asistencia de Ana Pérez'),
      'asistio'
    );

    await usuario.selectOptions(
      screen.getByLabelText('Asistencia de Luis Gómez'),
      'tarde'
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    );

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const [ruta, datos] = guardar.mock.calls[0];

    expect(ruta).toBe('/sesiones/12/asistencia/');

    expect(datos).toEqual(
      expect.objectContaining({
        version: 2,
        registros: {
          '10': 'asistio',
          '11': 'tarde',
        },
      })
    );

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    await waitFor(() => {
      expect(onGuardado).toHaveBeenCalledTimes(1);
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    ).toBeDisabled();
  });

  it('bloquea el guardado cuando la asistencia está cerrada', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      cerrada: true,
    });

    render(
      <RegistroAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /Esta asistencia está cerrada/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea un padrón que requiere preparación', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      requiere_preparacion: true,
    });

    render(
      <RegistroAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /El padrón ha cambiado/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea versiones de sesión desactualizadas', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      version: 4,
    });

    render(
      <RegistroAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /La versión consultada no coincide/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('impide repetir una operación de resultado incierto', async () => {
    const usuario = userEvent.setup();

    guardar.mockRejectedValue(
      Object.assign(
        new Error('Respuesta no recibida'),
        { estado: 0 }
      )
    );

    render(
      <RegistroAsistenciaSesion
        sesion={sesion}
      />
    );

    await screen.findByRole('combobox', {
      name: 'Asistencia de Ana Pérez',
    });

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    );

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    expect(
      await screen.findByText(
        /No llegó una respuesta confirmada/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    ).toBeDisabled();
  });
});
