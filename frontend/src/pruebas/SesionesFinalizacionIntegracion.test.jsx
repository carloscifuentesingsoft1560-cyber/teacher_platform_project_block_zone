
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

import { Sesiones } from '../paginas/Sesiones.jsx';

function responder(datos, estado = 200) {
  return {
    ok: estado >= 200 && estado < 300,
    status: estado,
    json: async () => datos,
  };
}

const sesionBase = {
  id: 12,
  grupo: 4,
  profesor: 3,
  fecha: '2026-11-02',
  hora_inicio: '10:00:00',
  hora_fin: '12:00:00',
  estado: 'planificada',
  estado_ejecucion: 'borrador',
  asistencia_confirmada: false,
  version: 4,
  planes: [
    {
      id: 25,
      numero: 1,
      objetivo: 'Técnica de escalada',
      autor: 3,
      creado_en: '2026-11-01T15:00:00-05:00',
      tareas: [
        {
          id: 101,
          orden: 1,
          fase: 'inicial',
          minutos: 30,
          instrucciones: 'Calentamiento',
        },
      ],
    },
  ],
};

const ejecucion = {
  id: 31,
  plan: sesionBase.planes[0],
  inicio: '2026-11-02T10:00:00-05:00',
  fin: '2026-11-02T12:00:00-05:00',
  duracion_real_minutos: 120,
  tiempo_no_distribuido_minutos: 90,
  observaciones: '',
  incidencias_pedagogicas: '',
  finalizada_en: null,
  actividades: [
    {
      tarea: 101,
      resultado: 'realizada',
      minutos: 30,
      descripcion: 'Calentamiento completado',
    },
  ],
};

const participantes = [
  {
    inscripcion: 11,
    deportista: 21,
    nombres: 'Andrea',
    apellidos: 'Rojas',
    estado: 'asistio',
  },
  {
    inscripcion: 12,
    deportista: 22,
    nombres: 'Felipe',
    apellidos: 'Díaz',
    estado: 'tarde',
  },
];

let llamadas;
let versionActual;
let finalizada;
let asistenciaCerrada;

function sesionActual() {
  return {
    ...sesionBase,
    version: versionActual,
    estado_ejecucion: finalizada
      ? 'registrada_pendiente_validacion'
      : 'borrador',
    asistencia_confirmada: asistenciaCerrada,
  };
}

function asistenciaActual() {
  return {
    version: versionActual,
    cerrada: asistenciaCerrada,
    requiere_preparacion: false,
    participantes,
    correcciones: [],
  };
}

beforeEach(() => {
  llamadas = [];
  versionActual = 4;
  finalizada = false;
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
          csrfToken: 'csrf-prueba-f35',
        });
      }

      if (
        ruta === '/api/sesiones/12/ejecucion/finalizar/' &&
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
        finalizada = true;
        asistenciaCerrada = true;

        return responder({
          sesion: sesionActual(),
          asistencia: asistenciaActual(),
        });
      }

      if (ruta === '/api/sesiones/12/ejecucion/') {
        return responder({
          version: versionActual,
          ejecucion: {
            ...ejecucion,
            finalizada_en: finalizada
              ? '2026-11-03T18:00:00-05:00'
              : null,
          },
        });
      }

      if (ruta === '/api/sesiones/12/asistencia/') {
        return responder(asistenciaActual());
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

describe('F3.5: integración en Mis sesiones', () => {
  it('finaliza ejecución, cierra asistencia y mantiene pendiente la validación', async () => {
    const usuario = userEvent.setup();

    render(<Sesiones />);

    await screen.findByRole('button', {
      name: 'Ver detalle',
    });

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
      await screen.findByRole('button', {
        name: 'Finalizar ejecución',
      })
    );

    const formulario = await screen.findByRole(
      'heading',
      { name: 'Finalización definitiva de ejecución' }
    );

    expect(formulario).toBeInTheDocument();

    const boton = screen.getByRole('button', {
      name: 'Confirmar finalización definitiva',
    });

    expect(boton).toBeDisabled();

    await waitFor(() => {
      expect(screen.getByRole('checkbox')).toBeEnabled();
    });

    await usuario.click(screen.getByRole('checkbox'));

    expect(boton).toBeEnabled();

    await usuario.click(boton);

    await waitFor(() => {
      expect(
        llamadas.filter(
          ({ ruta, opciones }) =>
            ruta ===
              '/api/sesiones/12/ejecucion/finalizar/' &&
            opciones.method === 'POST'
        )
      ).toHaveLength(1);
    });

    const envio = llamadas.find(
      ({ ruta, opciones }) =>
        ruta ===
          '/api/sesiones/12/ejecucion/finalizar/' &&
        opciones.method === 'POST'
    );

    const datos = JSON.parse(envio.opciones.body);

    expect(Object.keys(datos).sort()).toEqual([
      'clave',
      'version',
    ]);

    expect(datos.version).toBe(4);
    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
    );

    expect(
      envio.opciones.headers['X-CSRFToken']
    ).toBe('csrf-prueba-f35');

    expect(
      await screen.findByText(
        /Ejecución finalizada y asistencia cerrada\. La validación institucional continúa pendiente/i
      )
    ).toBeInTheDocument();

    await waitFor(() => {
      const detalle = screen.getByRole('heading', {
        name: 'Detalle de la sesión',
      }).closest('section');

      expect(
        within(detalle)
          .getByText('Versión de sesión')
          .nextElementSibling
      ).toHaveTextContent('5');
    });

    expect(
      screen.getByText('Estado', { selector: 'dt' })
        .nextElementSibling
    ).toHaveTextContent(
      'Ejecución cerrada; validación pendiente'
    );

    expect(
      screen.getByText(
        'Asistencia confirmada',
        { selector: 'dt' }
      ).nextElementSibling
    ).toHaveTextContent('Sí');

    expect(
      screen.queryByRole('heading', {
        name: 'Finalización definitiva de ejecución',
      })
    ).not.toBeInTheDocument();

    expect(sesionActual().estado).toBe('planificada');
    expect(finalizada).toBe(true);
    expect(asistenciaCerrada).toBe(true);

    expect(
      screen.queryByRole('button', {
        name: 'Finalizar ejecución',
      })
    ).not.toBeInTheDocument();

    expect(
      llamadas.some(
        ({ ruta, opciones }) =>
          ruta === '/api/sesiones/12/realizar/' &&
          opciones.method === 'POST'
      )
    ).toBe(false);
  });
});
