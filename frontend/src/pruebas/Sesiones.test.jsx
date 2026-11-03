
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

import { Sesiones } from '../paginas/Sesiones.jsx';

function responder(datos, estado = 200) {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    json: async () => datos,
  };
}

const sesionFicticia = {
  id: 12,
  grupo: 4,
  profesor: 3,
  fecha: '2026-11-02',
  hora_inicio: '10:00:00',
  hora_fin: '12:00:00',
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  asistencia_confirmada: false,
  version: 2,
  planes: [],
};

let llamadas;
let creaciones;

beforeEach(() => {
  llamadas = [];
  creaciones = [];

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

      if (ruta === '/api/sesiones/12/') {
        return responder({
          ...sesionFicticia,
          planes: [
            {
              id: 8,
              numero: 1,
              objetivo: 'Desarrollar equilibrio',
              tareas: [
                {
                  orden: 1,
                  fase: 'inicial',
                  minutos: 20,
                  instrucciones: 'Movilidad articular',
                },
              ],
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
        ruta === '/api/sesiones/' &&
        opciones.method === 'POST'
      ) {
        creaciones.push({
          datos: JSON.parse(opciones.body),
          opciones,
        });

        return responder(
          {
            ...sesionFicticia,
            id: 13,
          },
          201
        );
      }

      if (
        ruta.startsWith('/api/sesiones/') &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        const url = new URL(
          ruta,
          'http://localhost'
        );

        if (
          url.searchParams.get('situacion') ===
          'canceladas'
        ) {
          return responder({
            count: 0,
            next: null,
            results: [],
          });
        }

        return responder({
          count: 1,
          next: null,
          results: [sesionFicticia],
        });
      }

      return responder(
        { detalle: 'Ruta no simulada' },
        404
      );
    })
  );
});

describe('Etapa 4F: Mis sesiones', () => {
  it('consulta y muestra las sesiones autorizadas', async () => {
    render(<Sesiones />);

    expect(
      await screen.findByText('Programada')
    ).toBeInTheDocument();

    expect(
      screen.getByRole('heading', {
        name: 'Mis sesiones',
      })
    ).toBeInTheDocument();

    expect(
      screen.getByText('2026-11-02')
    ).toBeInTheDocument();

    expect(
      llamadas.some(
        ({ ruta }) =>
          ruta === '/api/sesiones/?page=1'
      )
    ).toBe(true);
  });

  it('envía el filtro de situación a Django', async () => {
    const usuario = userEvent.setup();

    render(<Sesiones />);

    await screen.findByText('Programada');

    await usuario.selectOptions(
      screen.getByLabelText('Situación'),
      'canceladas'
    );

    expect(
      await screen.findByText(
        'No hay sesiones registradas para esta consulta.'
      )
    ).toBeInTheDocument();

    expect(
      llamadas.some(
        ({ ruta }) =>
          ruta.includes('situacion=canceladas')
      )
    ).toBe(true);
  });

  it('consulta el detalle y muestra su planificación', async () => {
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

    expect(
      screen.getByText('Desarrollar equilibrio')
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Movilidad articular/)
    ).toBeInTheDocument();
  });

  it('crea una sesión con UUID y protección CSRF', async () => {
    const usuario = userEvent.setup();

    render(<Sesiones />);

    await screen.findByText('Programada');

    await usuario.click(
      screen.getByRole('button', {
        name: 'Nueva sesión',
      })
    );

    await usuario.selectOptions(
      screen.getByLabelText('Grupo'),
      '4'
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Crear sesión',
      })
    );

    await waitFor(() => {
      expect(creaciones).toHaveLength(1);
    });

    const { datos, opciones } = creaciones[0];

    expect(datos.grupo).toBe(4);

    expect(datos.fecha).toMatch(
      /^\d{4}-\d{2}-\d{2}$/
    );

    expect(datos.hora_inicio).toBe('10:00');
    expect(datos.hora_fin).toBe('12:00');

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(datos).not.toHaveProperty('profesor');
    expect(datos).not.toHaveProperty('actor');

    expect(
      opciones.headers['X-CSRFToken']
    ).toBe('csrf-prueba');

    expect(
      await screen.findByText(
        'Sesión creada correctamente.'
      )
    ).toBeInTheDocument();
  });
});
