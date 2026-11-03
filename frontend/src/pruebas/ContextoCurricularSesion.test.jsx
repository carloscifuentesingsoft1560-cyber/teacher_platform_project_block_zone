
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

const catalogos = {
  programas: [
    { id: 10, modalidad: 'Escuela' },
    { id: 20, modalidad: 'Especialización' },
  ],
  versiones: [
    {
      id: 100,
      numero: 1,
      identidad__nombre: 'Malla A',
      identidad__programa_id: 10,
    },
    {
      id: 200,
      numero: 1,
      identidad__nombre: 'Malla B',
      identidad__programa_id: 20,
    },
  ],
  fases: [
    { id: 1, nombre: 'Fundamentación' },
    { id: 5, nombre: 'Especialización' },
  ],
  semanas: [
    { id: 2, ordinal: 1, fase_id: 1 },
    { id: 6, ordinal: 2, fase_id: 5 },
  ],
  clases: [
    { id: 3, ordinal: 1, semana_id: 2 },
    { id: 7, ordinal: 2, semana_id: 6 },
  ],
  competencias: [
    { id: 4, texto: 'Control corporal' },
    { id: 8, texto: 'Trabajo en equipo' },
  ],
};

function Simulador({ alCambiar = () => {} }) {
  const [valor, establecerValor] = useState({
    programa_id: null,
    malla_version_id: null,
    fase_curricular_id: null,
    semana_id: null,
    clase_id: null,
    competencias_ids: [],
  });

  function cambiar(nuevo) {
    establecerValor(nuevo);
    alCambiar(nuevo);
  }

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

  todas.mockImplementation(async (ruta) => {
    const url = new URL(ruta, 'http://localhost');
    const tipo = url.searchParams.get('tipo');
    return catalogos[tipo] || [];
  });
});

async function seleccionarMalla(usuario) {
  await screen.findByRole('option', {
    name: /Programa 10/,
  });

  await usuario.selectOptions(
    screen.getByLabelText('Programa formativo'),
    '10'
  );

  await usuario.selectOptions(
    screen.getByLabelText('Versión de malla curricular'),
    '100'
  );

  await screen.findByRole('option', {
    name: 'Fundamentación',
  });
}

describe('Contexto curricular de sesiones', () => {
  it('consulta opciones autorizadas por sesión', async () => {
    render(<Simulador />);

    await waitFor(() => {
      expect(todas).toHaveBeenCalledWith(
        '/sesiones/12/opciones-plan/?tipo=programas'
      );

      expect(todas).toHaveBeenCalledWith(
        '/sesiones/12/opciones-plan/?tipo=versiones'
      );
    });

    expect(
      await screen.findByRole('option', {
        name: /Programa 10/,
      })
    ).toBeInTheDocument();
  });

  it('filtra las mallas según el programa', async () => {
    const usuario = userEvent.setup();
    render(<Simulador />);

    await screen.findByRole('option', {
      name: /Programa 10/,
    });

    await usuario.selectOptions(
      screen.getByLabelText('Programa formativo'),
      '10'
    );

    expect(
      screen.getByRole('option', { name: /Malla A/ })
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('option', { name: /Malla B/ })
    ).not.toBeInTheDocument();
  });

  it('limpia referencias al cambiar programa', async () => {
    const usuario = userEvent.setup();
    const alCambiar = vi.fn();

    render(<Simulador alCambiar={alCambiar} />);

    await seleccionarMalla(usuario);

    await usuario.selectOptions(
      screen.getByLabelText('Programa formativo'),
      '20'
    );

    expect(alCambiar).toHaveBeenLastCalledWith({
      programa_id: 20,
      malla_version_id: null,
      fase_curricular_id: null,
      semana_id: null,
      clase_id: null,
      competencias_ids: [],
    });
  });

  it('mantiene la jerarquía fase, semana y clase', async () => {
    const usuario = userEvent.setup();
    const alCambiar = vi.fn();

    render(<Simulador alCambiar={alCambiar} />);

    await seleccionarMalla(usuario);

    await usuario.selectOptions(
      screen.getByLabelText('Fase curricular'),
      '1'
    );

    expect(
      screen.getByRole('option', { name: 'Semana 1' })
    ).toBeInTheDocument();

    expect(
      screen.queryByRole('option', { name: 'Semana 2' })
    ).not.toBeInTheDocument();

    await usuario.selectOptions(
      screen.getByLabelText('Semana'),
      '2'
    );

    await usuario.selectOptions(
      screen.getByLabelText('Clase prevista'),
      '3'
    );

    expect(alCambiar).toHaveBeenLastCalledWith(
      expect.objectContaining({
        fase_curricular_id: 1,
        semana_id: 2,
        clase_id: 3,
      })
    );

    await usuario.selectOptions(
      screen.getByLabelText('Fase curricular'),
      '5'
    );

    expect(alCambiar).toHaveBeenLastCalledWith(
      expect.objectContaining({
        fase_curricular_id: 5,
        semana_id: null,
        clase_id: null,
      })
    );

    expect(
      screen.getByRole('option', { name: 'Semana 2' })
    ).toBeInTheDocument();
  });

  it('permite seleccionar y quitar competencias', async () => {
    const usuario = userEvent.setup();
    const alCambiar = vi.fn();

    render(<Simulador alCambiar={alCambiar} />);

    await seleccionarMalla(usuario);

    const competencia = screen.getByRole('checkbox', {
      name: 'Control corporal',
    });

    await usuario.click(competencia);

    expect(competencia).toBeChecked();

    expect(alCambiar).toHaveBeenLastCalledWith(
      expect.objectContaining({
        competencias_ids: [4],
      })
    );

    await usuario.click(competencia);

    expect(competencia).not.toBeChecked();

    expect(alCambiar).toHaveBeenLastCalledWith(
      expect.objectContaining({
        competencias_ids: [],
      })
    );
  });

  it('informa si no se pueden cargar los catálogos', async () => {
    todas.mockRejectedValueOnce(
      new Error('Catálogo curricular no disponible')
    );

    render(<Simulador />);

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent(
      'Catálogo curricular no disponible'
    );
  });
});
