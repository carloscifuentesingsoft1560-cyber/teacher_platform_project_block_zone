
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
    {
      inscripcion: 11,
      deportista: 5,
      nombres: 'Luis',
      apellidos: 'Gómez',
      estado: 'tarde',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();

  solicitar.mockResolvedValue(padron);

  guardar.mockResolvedValue({
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
});

describe('F3.3: cierre definitivo de asistencia', () => {
  it('exige confirmación y envía versión y UUID', async () => {
    const usuario = userEvent.setup();
    const onCerrado = vi.fn();

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
        onCerrado={onCerrado}
        onCancelar={vi.fn()}
      />
    );

    const boton = await screen.findByRole(
      'button',
      { name: 'Confirmar cierre definitivo' }
    );

    expect(boton).toBeDisabled();

    expect(
      screen.getAllByText('Asistió')[0]
    ).toBeInTheDocument();

    expect(
      screen.getAllByText('Llegó tarde')[0]
    ).toBeInTheDocument();

    await usuario.click(
      screen.getByRole('checkbox', {
        name: /Confirmo que revisé todos los estados/i,
      })
    );

    expect(boton).toBeEnabled();

    await usuario.click(boton);

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const [ruta, datos] = guardar.mock.calls[0];

    expect(ruta).toBe(
      '/sesiones/12/asistencia/cerrar/'
    );

    expect(datos.version).toBe(3);

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(datos).not.toHaveProperty(
      'registros'
    );

    await waitFor(() => {
      expect(onCerrado).toHaveBeenCalledTimes(1);
    });
  });

  it('bloquea participantes sin registrar', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      participantes: [
        padron.participantes[0],
        {
          ...padron.participantes[1],
          estado: '',
        },
      ],
    });

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /Completa la asistencia antes del cierre/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('checkbox')
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea asistencia ya cerrada', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      cerrada: true,
    });

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /Esta asistencia ya está cerrada/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea un padrón pendiente de preparación', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      requiere_preparacion: true,
    });

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /El padrón requiere preparación/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea una versión desactualizada', async () => {
    solicitar.mockResolvedValue({
      ...padron,
      version: 5,
    });

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
      />
    );

    expect(
      await screen.findByText(
        /La versión del padrón no coincide/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('impide el cierre de una sesión futura', async () => {
    render(
      <CierreAsistenciaSesion
        sesion={{
          ...sesion,
          fecha: '2099-12-31',
        }}
      />
    );

    expect(
      await screen.findByText(
        /No se puede cerrar la asistencia de una sesión futura/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea nuevos intentos ante una respuesta incierta', async () => {
    const usuario = userEvent.setup();

    guardar.mockRejectedValue(
      Object.assign(
        new Error('No se recibió respuesta'),
        { estado: 0 }
      )
    );

    render(
      <CierreAsistenciaSesion
        sesion={sesion}
      />
    );

    const confirmacion = await screen.findByRole(
      'checkbox',
      {
        name: /Confirmo que revisé todos los estados/i,
      }
    );

    await usuario.click(confirmacion);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    );

    expect(
      await screen.findByText(
        /El cierre podría haberse realizado/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Confirmar cierre definitivo',
      })
    ).toBeDisabled();

    expect(guardar).toHaveBeenCalledTimes(1);
  });
});
