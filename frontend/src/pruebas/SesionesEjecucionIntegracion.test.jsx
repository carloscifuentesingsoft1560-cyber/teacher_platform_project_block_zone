
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

import { Sesiones } from '../paginas/Sesiones.jsx';

function responder(datos, estado = 200) {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    json: async () => datos,
  };
}

const sesionInicial = {
  id: 12,
  grupo: 4,
  profesor: 3,
  fecha: '2026-11-02',
  hora_inicio: '10:00:00',
  hora_fin: '12:00:00',
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  asistencia_confirmada: false,
  version: 3,
  planes: [
    {
      id: 25,
      numero: 1,
      objetivo: 'Técnica de escalada',
      tareas: [
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
      ],
    },
  ],
};

let llamadas;
let versionActual;
let estadoEjecucion;

function sesionActual() {
  return {
    ...sesionInicial,
    version: versionActual,
    estado_ejecucion: estadoEjecucion,
  };
}

beforeEach(() => {
  llamadas = [];
  versionActual = 3;
  estadoEjecucion = 'sin_registro';

  vi.stubGlobal(
    'fetch',
    vi.fn(async (ruta, opciones = {}) => {
      llamadas.push({ ruta, opciones });

      if (ruta === '/api/sesiones/grupos/') {
        return responder({
          count: 1,
          next: null,
          results: [
            {
              id: 4,
              nombre: 'Escalada Nivel 1',
            },
          ],
        });
      }

      if (ruta === '/api/autenticacion/csrf/') {
        return responder({
          csrfToken: 'csrf-prueba',
        });
      }

      if (
        ruta === '/api/sesiones/12/ejecucion/' &&
        opciones.method === 'POST'
      ) {
        const datos = JSON.parse(opciones.body);

        if (datos.version !== versionActual) {
          return responder(
            { detalle: 'Conflicto de versión' },
            409
          );
        }

        versionActual += 1;
        estadoEjecucion = 'borrador';

        return responder({
          sesion: sesionActual(),
          asistencia: {
            version: versionActual,
            cerrada: false,
            requiere_preparacion: false,
            participantes: [],
          },
        });
      }

      if (
        ruta === '/api/sesiones/12/ejecucion/' &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder(
          { detalle: 'Sin ejecución registrada' },
          404
        );
      }

      if (
        ruta === '/api/sesiones/12/asistencia/' &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder({
          version: versionActual,
          cerrada: false,
          requiere_preparacion: false,
          participantes: [],
          correcciones: [],
        });
      }

      if (ruta === '/api/sesiones/12/') {
        return responder(sesionActual());
      }

      if (
        ruta.startsWith('/api/sesiones/?') &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder({
          count: 1,
          next: null,
          results: [sesionActual()],
        });
      }

      return responder(
        { detalle: 'Ruta no simulada' },
        404
      );
    })
  );
});

describe('F3.4: integración de ejecución en Mis sesiones', () => {
  it('guarda ejecución como borrador sin finalizar ni validar la sesión', async () => {
    const usuario = userEvent.setup();

    render(<Sesiones />);

    await screen.findByText('Programada');

    await usuario.click(
      screen.getByRole('button', {
        name: 'Ver detalle',
      })
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Detalle de la sesión',
      })
    ).toBeInTheDocument();

    await usuario.click(
      screen.getByRole('button', {
        name: 'Registrar ejecución',
      })
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Registro de ejecución real',
      })
    ).toBeInTheDocument();

    const selector = screen.getByRole('combobox', {
      name: 'Revisión del plan',
    });

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
            value: `Actividad ${numero} realizada`,
          },
        }
      );
    }

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar ejecución como borrador',
      })
    );

    await waitFor(() => {
      expect(
        llamadas.filter(
          ({ ruta, opciones }) =>
            ruta === '/api/sesiones/12/ejecucion/' &&
            opciones.method === 'POST'
        )
      ).toHaveLength(1);
    });

    const envio = llamadas.find(
      ({ ruta, opciones }) =>
        ruta === '/api/sesiones/12/ejecucion/' &&
        opciones.method === 'POST'
    );

    const datos = JSON.parse(envio.opciones.body);

    expect(datos.version).toBe(3);
    expect(datos.plan).toBe(25);

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(
      datos.actividades.map((actividad) => actividad.tarea)
    ).toEqual([101, 102, 103]);

    expect(datos.inicio).toBe(
      '2026-11-02T10:00:00-05:00'
    );

    expect(datos.fin).toBe(
      '2026-11-02T12:00:00-05:00'
    );

    expect(
      envio.opciones.headers['X-CSRFToken']
    ).toBe('csrf-prueba');

    expect(
      await screen.findByText(
        /La finalización y la validación institucional siguen pendientes/i
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText('Versión de sesión')
          .nextElementSibling
      ).toHaveTextContent(/^4$/);
    });

    expect(
      screen.queryByRole('heading', {
        name: 'Registro de ejecución real',
      })
    ).not.toBeInTheDocument();

    expect(
      screen.getByText('Estado', { selector: 'dt' })
        .nextElementSibling
    ).toHaveTextContent('Ejecución en borrador');

    expect(
      sesionActual().estado
    ).toBe('planificada');

    // Guardar no debe finalizar la ejecución.
    expect(
      llamadas.some(
        ({ ruta, opciones }) =>
          ruta === '/api/sesiones/12/ejecucion/finalizar/' &&
          opciones.method === 'POST'
      )
    ).toBe(false);

    // Guardar tampoco valida la sesión institucionalmente.
    expect(
      llamadas.some(
        ({ ruta, opciones }) =>
          ruta === '/api/sesiones/12/realizar/' &&
          opciones.method === 'POST'
      )
    ).toBe(false);
  });
});
