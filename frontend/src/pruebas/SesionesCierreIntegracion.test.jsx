
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
  version: 3,
  planes: [],
};

let llamadas;
let versionActual;
let asistenciaCerrada;

function sesionActual() {
  return {
    ...sesionInicial,
    version: versionActual,
    asistencia_confirmada: asistenciaCerrada,
  };
}

function padronActual() {
  return {
    version: versionActual,
    cerrada: asistenciaCerrada,
    requiere_preparacion: false,
    participantes: [
      {
        inscripcion: 20,
        deportista: 8,
        nombres: 'Ana',
        apellidos: 'Pérez',
        estado: 'asistio',
      },
      {
        inscripcion: 21,
        deportista: 9,
        nombres: 'Luis',
        apellidos: 'Gómez',
        estado: 'tarde',
      },
    ],
    correcciones: [],
  };
}

beforeEach(() => {
  llamadas = [];
  versionActual = 3;
  asistenciaCerrada = false;

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
        ruta === '/api/sesiones/12/asistencia/cerrar/' &&
        opciones.method === 'POST'
      ) {
        const datos = JSON.parse(opciones.body);

        if (
          datos.version !== versionActual ||
          asistenciaCerrada
        ) {
          return responder(
            { detalle: 'La versión o el estado ya cambió.' },
            409
          );
        }

        versionActual += 1;
        asistenciaCerrada = true;

        return responder({
          sesion: sesionActual(),
          asistencia: padronActual(),
        });
      }

      if (
        ruta === '/api/sesiones/12/asistencia/' &&
        (!opciones.method || opciones.method === 'GET')
      ) {
        return responder(padronActual());
      }

      if (ruta === '/api/sesiones/12/ejecucion/') {
        return responder(
          { detalle: 'No hay ejecución registrada.' },
          404
        );
      }

      if (
        ruta === '/api/sesiones/12/' &&
        (!opciones.method || opciones.method === 'GET')
      ) {
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

describe('F3.3: integración del cierre en Mis sesiones', () => {
  it('cierra la asistencia sin marcar la sesión como realizada', async () => {
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
      screen.getByRole('button', {
        name: 'Cerrar asistencia',
      })
    ).toBeEnabled();

    await usuario.click(
      screen.getByRole('button', {
        name: 'Cerrar asistencia',
      })
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Cierre definitivo de asistencia',
      })
    ).toBeInTheDocument();

    expect(
      screen.getAllByText('Ana Pérez')[0]
    ).toBeInTheDocument();

    expect(
      screen.getAllByText('Luis Gómez')[0]
    ).toBeInTheDocument();

    const confirmacion = screen.getByRole('checkbox', {
      name: /Confirmo que revisé todos los estados/i,
    });

    const botonCierre = screen.getByRole('button', {
      name: 'Confirmar cierre definitivo',
    });

    expect(botonCierre).toBeDisabled();

    await usuario.click(confirmacion);

    expect(botonCierre).toBeEnabled();

    await usuario.click(botonCierre);

    await waitFor(() => {
      expect(
        llamadas.filter(
          ({ ruta, opciones }) =>
            ruta === '/api/sesiones/12/asistencia/cerrar/' &&
            opciones.method === 'POST'
        )
      ).toHaveLength(1);
    });

    const envio = llamadas.find(
      ({ ruta, opciones }) =>
        ruta === '/api/sesiones/12/asistencia/cerrar/' &&
        opciones.method === 'POST'
    );

    const datos = JSON.parse(envio.opciones.body);

    expect(datos.version).toBe(3);

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(Object.keys(datos).sort()).toEqual([
      'clave',
      'version',
    ]);

    expect(
      envio.opciones.headers['X-CSRFToken']
    ).toBe('csrf-prueba');

    expect(
      await screen.findByText(
        /Asistencia cerrada correctamente/i
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.getByText('Versión de sesión')
          .nextElementSibling
      ).toHaveTextContent(/^4$/);
    });

    expect(
      screen.getByText('Asistencia confirmada')
        .nextElementSibling
    ).toHaveTextContent('Sí');

    expect(
      screen.queryByRole('button', {
        name: 'Cerrar asistencia',
      })
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole('button', {
        name: 'Registrar asistencia',
      })
    ).not.toBeInTheDocument();

    expect(
      screen.queryByRole('heading', {
        name: 'Cierre definitivo de asistencia',
      })
    ).not.toBeInTheDocument();

    // El cierre no debe ejecutar la validación institucional.
    expect(
      llamadas.some(
        ({ ruta, opciones }) =>
          ruta === '/api/sesiones/12/realizar/' &&
          opciones.method === 'POST'
      )
    ).toBe(false);

    expect(
      screen.getByText('Estado', { selector: 'dt' }).nextElementSibling
    ).toBeTruthy();

    expect(sesionActual().estado).toBe('planificada');
  });
});
