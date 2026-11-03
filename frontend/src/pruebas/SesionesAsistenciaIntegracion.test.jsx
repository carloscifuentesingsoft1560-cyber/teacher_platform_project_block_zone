
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
  version: 2,
  planes: [],
};

let llamadas;
let versionActual;
let estadoAsistencia;

beforeEach(() => {
  llamadas = [];
  versionActual = 2;
  estadoAsistencia = '';

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
        ruta === '/api/sesiones/12/asistencia/' &&
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
        estadoAsistencia = datos.registros['20'];

        return responder({
          sesion: {
            ...sesionInicial,
            version: versionActual,
          },
          asistencia: {
            version: versionActual,
            cerrada: false,
            requiere_preparacion: false,
            participantes: [
              {
                inscripcion: 20,
                deportista: 8,
                nombres: 'Ana',
                apellidos: 'Pérez',
                estado: estadoAsistencia,
              },
            ],
          },
        });
      }

      if (
        ruta === '/api/sesiones/12/asistencia/' &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder({
          version: versionActual,
          cerrada: false,
          requiere_preparacion: false,
          participantes: [
            {
              inscripcion: 20,
              deportista: 8,
              nombres: 'Ana',
              apellidos: 'Pérez',
              estado: estadoAsistencia,
            },
          ],
          correcciones: [],
        });
      }

      if (ruta === '/api/sesiones/12/') {
        return responder({
          ...sesionInicial,
          version: versionActual,
        });
      }

      if (
        ruta.startsWith('/api/sesiones/?') &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder({
          count: 1,
          next: null,
          results: [
            {
              ...sesionInicial,
              version: versionActual,
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

describe('F3.2: integración en Mis sesiones', () => {
  it('guarda asistencia y actualiza la versión sin cerrarla', async () => {
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
        name: 'Registrar asistencia',
      })
    );

    const selector = await screen.findByRole(
      'combobox',
      {
        name: 'Asistencia de Ana Pérez',
      }
    );

    await usuario.selectOptions(
      selector,
      'asistio'
    );

    expect(selector).toHaveValue('asistio');

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar asistencia',
      })
    );

    await waitFor(() => {
      expect(
        llamadas.filter(
          ({ ruta, opciones }) =>
            ruta === '/api/sesiones/12/asistencia/' &&
            opciones.method === 'POST'
        )
      ).toHaveLength(1);
    });

    const envio = llamadas.find(
      ({ ruta, opciones }) =>
        ruta === '/api/sesiones/12/asistencia/' &&
        opciones.method === 'POST'
    );

    const datos = JSON.parse(envio.opciones.body);

    expect(datos).toEqual(
      expect.objectContaining({
        version: 2,
        registros: {
          '20': 'asistio',
        },
      })
    );

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(
      envio.opciones.headers['X-CSRFToken']
    ).toBe('csrf-prueba');

    expect(
      await screen.findByText(
        /Asistencia guardada. El cierre definitivo está pendiente./
      )
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('heading', {
        name: 'Registrar asistencia de la sesión',
      })
    ).not.toBeInTheDocument();

    // Comprobar específicamente la versión de la sesión.
    expect(
      screen.getByText('Versión de sesión').nextElementSibling
    ).toHaveTextContent(/^3$/);

    expect(
      screen.getByRole('button', {
        name: 'Registrar asistencia',
      })
    ).toBeEnabled();

    // Guardar asistencia no debe cerrar el registro.
    expect(
      llamadas.some(
        ({ ruta, opciones }) =>
          ruta === '/api/sesiones/12/asistencia/cerrar/' &&
          opciones.method === 'POST'
      )
    ).toBe(false);
  });
});
