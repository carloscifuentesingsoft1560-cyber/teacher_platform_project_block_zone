
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ConsultaEjecucionSesion } from
  '../componentes/ConsultaEjecucionSesion.jsx';

import { solicitar } from '../api/cliente.js';

vi.mock('../api/cliente.js', () => ({
  solicitar: vi.fn(),
}));

const sesion = {
  id: 12,
  estado: 'planificada',
  estado_ejecucion: 'sin_registro',
  version: 2,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('F3.1: consulta de ejecución y asistencia', () => {
  it('muestra el padrón sin enviar operaciones de escritura', async () => {
    solicitar.mockResolvedValue({
      version: 2,
      cerrada: false,
      requiere_preparacion: false,
      participantes: [
        {
          inscripcion: 25,
          deportista: 8,
          nombres: 'Ana',
          apellidos: 'Pérez',
          estado: 'tarde',
        },
      ],
    });

    render(<ConsultaEjecucionSesion sesion={sesion} />);

    expect(
      await screen.findByText('Ana Pérez')
    ).toBeInTheDocument();

    expect(
      screen.getByText('Llegó tarde')
    ).toBeInTheDocument();

    expect(solicitar).toHaveBeenCalledTimes(1);

    expect(solicitar).toHaveBeenCalledWith(
      '/sesiones/12/asistencia/'
    );

    expect(
      screen.queryByRole('button', {
        name: /guardar asistencia/i,
      })
    ).not.toBeInTheDocument();
  });

  it('distingue ejecución finalizada de validación institucional', async () => {
    solicitar.mockImplementation(async (ruta) => {
      if (ruta === '/sesiones/12/asistencia/') {
        return {
          version: 3,
          cerrada: true,
          requiere_preparacion: false,
          participantes: [],
        };
      }

      if (ruta === '/sesiones/12/ejecucion/') {
        return {
          version: 3,
          ejecucion: {
            id: 7,
            plan: { id: 9, numero: 1 },
            inicio: '2026-11-02T10:00:00-05:00',
            fin: '2026-11-02T12:00:00-05:00',
            duracion_real_minutos: 120,
            tiempo_no_distribuido_minutos: 0,
            finalizada_en: '2026-11-02T12:10:00-05:00',
            observaciones: 'Trabajo completado',
            incidencias_pedagogicas: '',
            actividades: [
              {
                tarea: 30,
                resultado: 'realizada',
                minutos: 120,
                descripcion: 'Circuito técnico',
              },
            ],
          },
        };
      }

      throw new Error('Ruta inesperada');
    });

    render(
      <ConsultaEjecucionSesion
        sesion={{
          ...sesion,
          estado_ejecucion:
            'registrada_pendiente_validacion',
        }}
      />
    );

    expect(
      await screen.findByText('Trabajo completado')
    ).toBeInTheDocument();

    expect(
      screen.getAllByRole('listitem')[0]
    ).toHaveTextContent(/Circuito técnico/);

    expect(
      screen.getByText(
        /no implica que la sesión haya sido validada/i
      )
    ).toBeInTheDocument();

    expect(solicitar).toHaveBeenCalledTimes(2);
  });
});
