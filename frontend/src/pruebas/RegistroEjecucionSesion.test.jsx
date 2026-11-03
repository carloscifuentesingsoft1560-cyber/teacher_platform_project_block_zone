
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

const sesion = {
  id: 12,
  version: 3,
  fecha: '2026-11-02',
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  asistencia_confirmada: false,
  planes: [
    {
      id: 25,
      numero: 1,
      objetivo: 'Trabajo de técnica en escalada',
      tareas: [
        {
          id: 101,
          orden: 1,
          fase: 'inicial',
          minutos: 30,
          instrucciones: 'Calentamiento general',
        },
        {
          id: 102,
          orden: 2,
          fase: 'central',
          minutos: 60,
          instrucciones: 'Ejercicios técnicos',
        },
        {
          id: 103,
          orden: 3,
          fase: 'final',
          minutos: 30,
          instrucciones: 'Vuelta a la calma',
        },
      ],
    },
  ],
};

function errorApi(mensaje, estado) {
  return Object.assign(new Error(mensaje), { estado });
}

beforeEach(() => {
  vi.clearAllMocks();

  // No existe todavía un borrador de ejecución.
  solicitar.mockRejectedValue(
    errorApi('No encontrado', 404)
  );

  guardar.mockResolvedValue({
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
});

async function prepararFormulario(usuario) {
  await waitFor(() => {
    expect(solicitar).toHaveBeenCalledWith(
      '/sesiones/12/ejecucion/'
    );
  });

  const selector = await screen.findByRole(
    'combobox',
    { name: 'Revisión del plan' }
  );

  await usuario.selectOptions(selector, '25');

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
          value: `Actividad ${numero} ejecutada`,
        },
      }
    );
  }
}

describe('F3.4: registro de ejecución real', () => {
  it('guarda el borrador usando los IDs reales de tareas', async () => {
    const usuario = userEvent.setup();
    const onGuardado = vi.fn();

    render(
      <RegistroEjecucionSesion
        sesion={sesion}
        onGuardado={onGuardado}
        onCancelar={vi.fn()}
      />
    );

    await prepararFormulario(usuario);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const [ruta, datos] = guardar.mock.calls[0];

    expect(ruta).toBe('/sesiones/12/ejecucion/');

    expect(datos.version).toBe(3);
    expect(datos.plan).toBe(25);

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(datos.inicio).toBe(
      '2026-11-02T10:00:00-05:00'
    );

    expect(datos.fin).toBe(
      '2026-11-02T12:00:00-05:00'
    );

    expect(datos.actividades).toEqual([
      {
        tarea: 101,
        resultado: 'realizada',
        minutos: 30,
        descripcion: 'Actividad 1 ejecutada',
        adaptacion_metodologica: '',
        motivo_omision: '',
      },
      {
        tarea: 102,
        resultado: 'realizada',
        minutos: 60,
        descripcion: 'Actividad 2 ejecutada',
        adaptacion_metodologica: '',
        motivo_omision: '',
      },
      {
        tarea: 103,
        resultado: 'realizada',
        minutos: 30,
        descripcion: 'Actividad 3 ejecutada',
        adaptacion_metodologica: '',
        motivo_omision: '',
      },
    ]);

    await waitFor(() => {
      expect(onGuardado).toHaveBeenCalledTimes(1);
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    ).toBeDisabled();

    expect(
      screen.getByText(
        /Ejecución guardada como borrador/i
      )
    ).toBeInTheDocument();
  });

  it('exige adaptación para una actividad modificada', async () => {
    const usuario = userEvent.setup();

    render(
      <RegistroEjecucionSesion sesion={sesion} />
    );

    await prepararFormulario(usuario);

    await usuario.selectOptions(
      screen.getByLabelText(
        'Resultado de actividad 2'
      ),
      'modificada'
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    expect(
      await screen.findByText(
        /actividades modificadas requieren describir la adaptación/i
      )
    ).toBeInTheDocument();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('exige motivo para una actividad omitida', async () => {
    const usuario = userEvent.setup();

    render(
      <RegistroEjecucionSesion sesion={sesion} />
    );

    await prepararFormulario(usuario);

    await usuario.selectOptions(
      screen.getByLabelText(
        'Resultado de actividad 2'
      ),
      'omitida'
    );

    expect(
      screen.getByLabelText(
        'Minutos reales de actividad 2'
      )
    ).toHaveValue(0);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    expect(
      await screen.findByText(
        /actividad omitida requiere cero minutos/i
      )
    ).toBeInTheDocument();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea actividades que superan la duración real', async () => {
    const usuario = userEvent.setup();

    render(
      <RegistroEjecucionSesion sesion={sesion} />
    );

    await prepararFormulario(usuario);

    fireEvent.change(
      screen.getByLabelText('Finalización real'),
      {
        target: {
          value: '2026-11-02T11:00',
        },
      }
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    expect(
      await screen.findByText(
        /superan la duración real del entrenamiento/i
      )
    ).toBeInTheDocument();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea una versión desactualizada', async () => {
    solicitar.mockResolvedValue({
      version: 5,
      ejecucion: {},
    });

    render(
      <RegistroEjecucionSesion sesion={sesion} />
    );

    expect(
      await screen.findByText(
        /La versión consultada no coincide/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea reintentos cuando la respuesta es incierta', async () => {
    const usuario = userEvent.setup();

    guardar.mockRejectedValue(
      errorApi('Sin respuesta del servidor', 0)
    );

    render(
      <RegistroEjecucionSesion sesion={sesion} />
    );

    await prepararFormulario(usuario);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    expect(
      await screen.findByText(
        /La operación podría haberse guardado/i
      )
    ).toBeInTheDocument();

    expect(guardar).toHaveBeenCalledTimes(1);

    expect(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    ).toBeDisabled();
  });
});
