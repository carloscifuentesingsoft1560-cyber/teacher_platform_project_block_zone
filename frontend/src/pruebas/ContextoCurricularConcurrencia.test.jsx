
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ContextoCurricularSesion } from
  '../componentes/ContextoCurricularSesion.jsx';
import { todas } from '../api/gestion.js';

vi.mock('../api/gestion.js', () => ({
  todas: vi.fn(),
}));

const inicial = {
  programa_id: null,
  malla_version_id: null,
  fase_curricular_id: null,
  semana_id: null,
  clase_id: null,
  competencias_ids: [],
};

function diferida() {
  let resolver;

  const promesa = new Promise((resolve) => {
    resolver = resolve;
  });

  return { promesa, resolver };
}

function Formulario() {
  const [valor, cambiar] = useState(inicial);

  return (
    <ContextoCurricularSesion
      sesionId={12}
      valor={valor}
      cambiar={cambiar}
    />
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('Protección de catálogos curriculares', () => {
  it('retira las fases anteriores al cambiar la malla', async () => {
    const usuario = userEvent.setup();
    const consultaPendiente = diferida();

    todas.mockImplementation((ruta) => {
      const parametros = new URL(
        ruta,
        'http://localhost'
      ).searchParams;

      const tipo = parametros.get('tipo');
      const version = parametros.get('malla_version');

      if (tipo === 'programas') {
        return Promise.resolve([
          { id: 10, modalidad: 'Escuela' },
        ]);
      }

      if (tipo === 'versiones') {
        return Promise.resolve([
          {
            id: 100,
            numero: 1,
            identidad__nombre: 'Malla A',
            identidad__programa_id: 10,
          },
          {
            id: 200,
            numero: 2,
            identidad__nombre: 'Malla B',
            identidad__programa_id: 10,
          },
        ]);
      }

      if (version === '100') {
        if (tipo === 'fases') {
          return Promise.resolve([
            { id: 1, nombre: 'Fase de malla A' },
          ]);
        }

        return Promise.resolve([]);
      }

      if (version === '200') {
        if (tipo === 'fases') {
          return consultaPendiente.promesa;
        }

        return Promise.resolve([]);
      }

      return Promise.resolve([]);
    });

    render(<Formulario />);

    await screen.findByRole('option', {
      name: /Programa 10/,
    });

    await usuario.selectOptions(
      screen.getByLabelText('Programa formativo'),
      '10'
    );

    await usuario.selectOptions(
      screen.getByLabelText(
        'Versión de malla curricular'
      ),
      '100'
    );

    await screen.findByRole('option', {
      name: 'Fase de malla A',
    });

    await usuario.selectOptions(
      screen.getByLabelText(
        'Versión de malla curricular'
      ),
      '200'
    );

    await waitFor(() => {
      expect(todas).toHaveBeenCalledWith(
        expect.stringContaining(
          'malla_version=200'
        )
      );
    });

    // Las opciones de la versión anterior deben desaparecer
    // sin esperar a que termine la nueva consulta.
    expect(
      screen.queryByRole('option', {
        name: 'Fase de malla A',
      })
    ).not.toBeInTheDocument();

    consultaPendiente.resolver([
      { id: 5, nombre: 'Fase de malla B' },
    ]);

    expect(
      await screen.findByRole('option', {
        name: 'Fase de malla B',
      })
    ).toBeInTheDocument();
  });
});
