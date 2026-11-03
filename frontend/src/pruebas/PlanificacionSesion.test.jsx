
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
  within,
} from '@testing-library/react';

import userEvent from '@testing-library/user-event';

import {
  PlanificacionSesion,
} from '../componentes/PlanificacionSesion.jsx';

const sesionBase = {
  id: 12,
  grupo: 4,
  profesor: 3,
  fecha: '2026-11-03',
  hora_inicio: '10:00:00',
  hora_fin: '12:00:00',
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  version: 2,
  planes: [],
};

let llamadas;
let respuestaPlan;
let guardado;

function responder(datos, estado = 200) {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    json: async () => datos,
  };
}

function montar(sesion = sesionBase) {
  guardado = vi.fn();

  return render(
    <PlanificacionSesion
      sesion={sesion}
      onGuardado={guardado}
      onCancelar={vi.fn()}
    />
  );
}

async function completarActividades(usuario) {
  const instrucciones = screen.getAllByLabelText(
    'Actividades e instrucciones'
  );

  await usuario.type(
    instrucciones[0],
    'Movilidad articular y activacion general'
  );

  await usuario.type(
    instrucciones[1],
    'Trabajo tecnico de escalada en bloques'
  );

  await usuario.type(
    instrucciones[2],
    'Vuelta a la calma y reflexion'
  );
}

beforeEach(() => {
  llamadas = [];
  respuestaPlan = null;

  vi.stubGlobal(
    'fetch',
    vi.fn(async (ruta, opciones = {}) => {
      llamadas.push({ ruta, opciones });

      if (ruta === '/api/autenticacion/csrf/') {
        return responder({
          csrfToken: 'csrf-planificacion',
        });
      }

      if (
        ruta === '/api/sesiones/12/' &&
        opciones.method === 'PATCH'
      ) {
        if (respuestaPlan) {
          return respuestaPlan;
        }

        return responder({
          ...sesionBase,
          version: 3,
          planes: [
            {
              id: 21,
              numero: 1,
              objetivo: 'Mejorar la tecnica de escalada',
              tareas: [],
            },
          ],
        });
      }

      return responder(
        { detalle: 'Ruta no simulada' },
        404
      );
    })
  );
});

describe('Etapa 4F: Planificacion de sesiones F2', () => {
  it('muestra tres fases y distribuye los minutos', () => {
    montar();

    expect(
      screen.getByRole('heading', {
        name: 'Planificación de la sesión',
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText('Fase inicial')
    ).toBeInTheDocument();

    expect(
      screen.getByText('Fase central')
    ).toBeInTheDocument();

    expect(
      screen.getByText('Fase final')
    ).toBeInTheDocument();

    const fases = [
      screen.getByRole('group', {
        name: 'Fase inicial',
      }),
      screen.getByRole('group', {
        name: 'Fase central',
      }),
      screen.getByRole('group', {
        name: 'Fase final',
      }),
    ];

    expect(
      within(fases[0]).getByLabelText(
        'Duración en minutos'
      )
    ).toHaveValue(30);

    expect(
      within(fases[1]).getByLabelText(
        'Duración en minutos'
      )
    ).toHaveValue(60);

    expect(
      within(fases[2]).getByLabelText(
        'Duración en minutos'
      )
    ).toHaveValue(30);

    expect(
      screen.getByText('0 minutos')
    ).toBeInTheDocument();
  });

  it('impide guardar si los minutos no coinciden', async () => {
    const usuario = userEvent.setup();

    montar();

    const faseInicial = screen.getByRole('group', {
      name: 'Fase inicial',
    });

    const minutos = within(faseInicial).getByLabelText(
      'Duración en minutos'
    );

    await usuario.clear(minutos);
    await usuario.type(minutos, '20');

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();

    expect(
      screen.getByText(/Ajusta los minutos/)
    ).toBeInTheDocument();

    expect(
      llamadas.some(
        ({ opciones }) => opciones.method === 'PATCH'
      )
    ).toBe(false);
  });

  it('guarda una revision con version, UUID y tres fases', async () => {
    const usuario = userEvent.setup();

    montar();

    await usuario.type(
      screen.getByLabelText(
        'Objetivo general de la sesión'
      ),
      'Mejorar la tecnica de escalada'
    );

    await completarActividades(usuario);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    );

    await waitFor(() => {
      expect(guardado).toHaveBeenCalledTimes(1);
    });

    const envio = llamadas.find(
      ({ ruta, opciones }) =>
        ruta === '/api/sesiones/12/' &&
        opciones.method === 'PATCH'
    );

    expect(envio).toBeDefined();

    const datos = JSON.parse(envio.opciones.body);

    expect(datos.version).toBe(2);

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(datos.objetivo).toBe(
      'Mejorar la tecnica de escalada'
    );

    expect(datos.tareas).toHaveLength(3);

    expect(
      datos.tareas.map((tarea) => tarea.fase)
    ).toEqual([
      'inicial',
      'central',
      'final',
    ]);

    expect(
      datos.tareas.map((tarea) => tarea.minutos)
    ).toEqual([30, 60, 30]);

    expect(
      datos.tareas.reduce(
        (total, tarea) => total + tarea.minutos,
        0
      )
    ).toBe(120);

    expect(
      envio.opciones.headers['X-CSRFToken']
    ).toBe('csrf-planificacion');

    expect(
      envio.opciones.credentials
    ).toBe('same-origin');

    expect(
      guardado.mock.calls[0][0].version
    ).toBe(3);
  });

  it('bloquea la planificacion de sesiones canceladas', () => {
    montar({
      ...sesionBase,
      estado: 'cancelada',
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();

    expect(
      screen.getByText(
        /Esta sesión no está en estado planificada/
      )
    ).toBeInTheDocument();
  });

  it('no confirma el guardado ante conflicto de version', async () => {
    const usuario = userEvent.setup();

    respuestaPlan = responder(
      {
        detalle: 'La versión de la sesión cambió.',
      },
      409
    );

    montar();

    await usuario.type(
      screen.getByLabelText(
        'Objetivo general de la sesión'
      ),
      'Objetivo de prueba'
    );

    await completarActividades(usuario);

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    );

    expect(
      await screen.findByText(
        'La versión de la sesión cambió.'
      )
    ).toBeInTheDocument();

    expect(guardado).not.toHaveBeenCalled();

    expect(
      screen.getByText(
        /Actualiza la sesión y comprueba/
      )
    ).toBeInTheDocument();
  });
});
