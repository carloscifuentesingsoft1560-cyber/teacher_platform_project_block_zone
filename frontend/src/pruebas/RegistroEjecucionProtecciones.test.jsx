
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import userEvent from '@testing-library/user-event';

import { RegistroEjecucionSesion } from
  '../componentes/RegistroEjecucionSesion.jsx';

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

const tareas = [
  {
    id: 101,
    orden: 1,
    fase: 'inicial',
    minutos: 30,
    instrucciones: 'Calentamiento',
  },
  {
    id: 102,
    orden: 2,
    fase: 'central',
    minutos: 60,
    instrucciones: 'Trabajo técnico',
  },
  {
    id: 103,
    orden: 3,
    fase: 'final',
    minutos: 30,
    instrucciones: 'Vuelta a la calma',
  },
];

const sesion = {
  id: 12,
  version: 3,
  fecha: '2026-11-02',
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  planes: [
    {
      id: 25,
      numero: 1,
      objetivo: 'Técnica de escalada',
      tareas,
    },
  ],
};

async function completarFormulario(usuario) {
  const plan = await screen.findByRole(
    'combobox',
    { name: 'Revisión del plan' }
  );

  await usuario.selectOptions(plan, '25');

  fireEvent.change(
    screen.getByLabelText('Inicio real'),
    {
      target: {
        value: '2026-11-02T10:00',
      },
    }
  );

  fireEvent.change(
    screen.getByLabelText('Finalización real'),
    {
      target: {
        value: '2026-11-02T12:00',
      },
    }
  );

  for (const numero of [1, 2, 3]) {
    fireEvent.change(
      screen.getByLabelText(
        `Descripción ejecutada de actividad ${numero}`
      ),
      {
        target: {
          value: `Descripción de actividad ${numero}`,
        },
      }
    );
  }
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('F3.4: protecciones del registro de ejecución', () => {
  it('impide dos envíos mientras espera respuesta', async () => {
    const usuario = userEvent.setup();
    const pendiente = diferida();
    const onGuardado = vi.fn();

    solicitar.mockRejectedValue(
      Object.assign(new Error('Sin borrador'), {
        estado: 404,
      })
    );

    guardar.mockReturnValue(pendiente.promesa);

    render(
      <RegistroEjecucionSesion
        sesion={sesion}
        onGuardado={onGuardado}
        onCancelar={vi.fn()}
      />
    );

    await completarFormulario(usuario);

    const boton = screen.getByRole('button', {
      name: 'Guardar ejecución como borrador',
    });

    await usuario.click(boton);

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const botonPendiente = screen.getByRole(
      'button',
      { name: 'Guardando ejecución…' }
    );

    expect(botonPendiente).toBeDisabled();

    await usuario.click(botonPendiente);

    expect(guardar).toHaveBeenCalledTimes(1);

    pendiente.resolver({
      sesion: {
        ...sesion,
        version: 4,
        estado_ejecucion: 'borrador',
      },
      asistencia: {
        version: 4,
        cerrada: false,
        participantes: [],
      },
    });

    await waitFor(() => {
      expect(onGuardado).toHaveBeenCalledTimes(1);
    });

    expect(guardar).toHaveBeenCalledTimes(1);
  });

  it('descarta una consulta antigua al cambiar de sesión', async () => {
    const antigua = diferida();

    solicitar.mockImplementation((ruta) => {
      if (ruta === '/sesiones/12/ejecucion/') {
        return antigua.promesa;
      }

      if (ruta === '/sesiones/13/ejecucion/') {
        return Promise.reject(
          Object.assign(new Error('Sin borrador'), {
            estado: 404,
          })
        );
      }

      throw new Error('Ruta inesperada');
    });

    const siguienteSesion = {
      ...sesion,
      id: 13,
      version: 5,
      planes: [
        {
          id: 35,
          numero: 2,
          objetivo: 'Resistencia en escalada',
          tareas: [
            {
              id: 201,
              orden: 1,
              fase: 'inicial',
              minutos: 30,
              instrucciones: 'Movilidad',
            },
            {
              id: 202,
              orden: 2,
              fase: 'central',
              minutos: 60,
              instrucciones: 'Circuitos',
            },
            {
              id: 203,
              orden: 3,
              fase: 'final',
              minutos: 30,
              instrucciones: 'Recuperación',
            },
          ],
        },
      ],
    };

    const { rerender } = render(
      <RegistroEjecucionSesion
        sesion={sesion}
        onCancelar={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(solicitar).toHaveBeenCalledWith(
        '/sesiones/12/ejecucion/'
      );
    });

    rerender(
      <RegistroEjecucionSesion
        sesion={siguienteSesion}
        onCancelar={vi.fn()}
      />
    );

    const selector = await screen.findByRole(
      'combobox',
      { name: 'Revisión del plan' }
    );

    await waitFor(() => {
      expect(selector).toBeEnabled();
    });

    antigua.resolver({
      version: 3,
      ejecucion: {
        plan: { id: 25 },
        inicio: '2026-11-02T10:00:00-05:00',
        fin: '2026-11-02T12:00:00-05:00',
        actividades: [],
      },
    });

    await waitFor(() => {
      expect(
        screen.queryByRole('option', {
          name: /Técnica de escalada/i,
        })
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByRole('option', {
        name: /Resistencia en escalada/i,
      })
    ).toBeInTheDocument();

    expect(selector).toHaveValue('');

    expect(guardar).not.toHaveBeenCalled();
  });
});
