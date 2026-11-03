
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { PlanificacionSesion } from
  '../componentes/PlanificacionSesion.jsx';

import { guardar, todas } from '../api/gestion.js';

vi.mock('../api/gestion.js', () => ({
  guardar: vi.fn(),
  todas: vi.fn(),
}));

const sesion = {
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

function diferida() {
  let resolver;

  const promesa = new Promise((resolve) => {
    resolver = resolve;
  });

  return { promesa, resolver };
}

function montar() {
  return render(
    <PlanificacionSesion
      sesion={sesion}
      onGuardado={vi.fn()}
      onCancelar={vi.fn()}
    />
  );
}

async function completarFormulario(usuario) {
  await usuario.type(
    screen.getByLabelText('Objetivo general de la sesión'),
    'Fortalecer la coordinación'
  );

  const instrucciones = screen.getAllByLabelText(
    'Actividades e instrucciones'
  );

  await usuario.type(instrucciones[0], 'Calentamiento general');
  await usuario.type(instrucciones[1], 'Ejercicios técnicos');
  await usuario.type(instrucciones[2], 'Vuelta a la calma');
}

beforeEach(() => {
  vi.clearAllMocks();
  guardar.mockResolvedValue({ ...sesion, version: 3 });
});

describe('Bloqueos del guardado curricular', () => {
  it('impide guardar mientras consulta los catálogos', async () => {
    const usuario = userEvent.setup();
    const pendiente = diferida();

    todas.mockImplementation(() => pendiente.promesa);

    montar();
    await completarFormulario(usuario);

    await usuario.click(
      screen.getByRole('checkbox', {
        name: /Vincular esta planificación/,
      })
    );

    await waitFor(() => {
      expect(todas).toHaveBeenCalled();
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();

    pendiente.resolver([]);
  });

  it('impide guardar cuando falla un catálogo autorizado', async () => {
    const usuario = userEvent.setup();

    todas.mockRejectedValue(
      new Error('No se pudo consultar el catálogo')
    );

    montar();
    await completarFormulario(usuario);

    await usuario.click(
      screen.getByRole('checkbox', {
        name: /Vincular esta planificación/,
      })
    );

    expect(
      await screen.findByText('No se pudo consultar el catálogo')
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });
});
