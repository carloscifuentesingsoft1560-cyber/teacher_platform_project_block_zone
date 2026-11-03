
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

import {
  PlanificacionSesion,
} from '../componentes/PlanificacionSesion.jsx';

import {
  guardar,
  todas,
} from '../api/gestion.js';

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

const catalogos = {
  programas: [
    { id: 10, modalidad: 'Escuela' },
    { id: 20, modalidad: 'Especialización' },
  ],
  versiones: [
    {
      id: 100,
      numero: 1,
      identidad__nombre: 'Malla Nivel 1',
      identidad__programa_id: 10,
    },
    {
      id: 200,
      numero: 1,
      identidad__nombre: 'Malla Nivel 2',
      identidad__programa_id: 20,
    },
  ],
  fases: [
    { id: 1, nombre: 'Fundamentación' },
  ],
  semanas: [
    { id: 2, ordinal: 1, fase_id: 1 },
  ],
  clases: [
    { id: 3, ordinal: 1, semana_id: 2 },
  ],
  competencias: [
    { id: 4, texto: 'Control corporal' },
    { id: 8, texto: 'Trabajo en equipo' },
  ],
};

let onGuardado;

beforeEach(() => {
  vi.clearAllMocks();

  onGuardado = vi.fn();

  todas.mockImplementation(async (ruta) => {
    const url = new URL(ruta, 'http://localhost');
    const tipo = url.searchParams.get('tipo');

    return catalogos[tipo] || [];
  });

  guardar.mockResolvedValue({
    ...sesion,
    version: 3,
  });
});

function montar() {
  return render(
    <PlanificacionSesion
      sesion={sesion}
      onGuardado={onGuardado}
      onCancelar={vi.fn()}
    />
  );
}

async function llenarActividades(usuario) {
  await usuario.type(
    screen.getByLabelText(
      'Objetivo general de la sesión'
    ),
    'Fortalecer la técnica de escalada'
  );

  const instrucciones = screen.getAllByLabelText(
    'Actividades e instrucciones'
  );

  await usuario.type(
    instrucciones[0],
    'Movilidad articular y calentamiento'
  );

  await usuario.type(
    instrucciones[1],
    'Circuitos técnicos de escalada'
  );

  await usuario.type(
    instrucciones[2],
    'Estiramientos y reflexión grupal'
  );
}

async function abrirCurriculo(usuario) {
  await usuario.click(
    screen.getByRole('checkbox', {
      name: /Vincular esta planificación/,
    })
  );

  await screen.findByRole('option', {
    name: /Programa 10/,
  });
}

async function seleccionarVersion(usuario) {
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
    name: 'Fundamentación',
  });
}

describe('Etapa 4F: guardado curricular', () => {
  it('envía referencias curriculares y competencias', async () => {
    const usuario = userEvent.setup();

    montar();

    await llenarActividades(usuario);
    await abrirCurriculo(usuario);
    await seleccionarVersion(usuario);

    await usuario.selectOptions(
      screen.getByLabelText('Fase curricular'),
      '1'
    );

    await usuario.selectOptions(
      screen.getByLabelText('Semana'),
      '2'
    );

    await usuario.selectOptions(
      screen.getByLabelText('Clase prevista'),
      '3'
    );

    await usuario.click(
      screen.getByRole('checkbox', {
        name: 'Control corporal',
      })
    );

    await usuario.click(
      screen.getByRole('checkbox', {
        name: 'Trabajo en equipo',
      })
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    );

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const [ruta, datos, metodo] =
      guardar.mock.calls[0];

    expect(ruta).toBe('/sesiones/12/');
    expect(metodo).toBe('PATCH');

    expect(datos).toEqual(
      expect.objectContaining({
        version: 2,
        objetivo: 'Fortalecer la técnica de escalada',
        programa_id: 10,
        malla_version_id: 100,
        fase_curricular_id: 1,
        semana_id: 2,
        clase_id: 3,
        competencias_ids: [4, 8],
      })
    );

    expect(datos.clave).toMatch(
      /^[0-9a-f-]{36}$/i
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
      datos.tareas.reduce(
        (total, tarea) => total + tarea.minutos,
        0
      )
    ).toBe(120);

    expect(onGuardado).toHaveBeenCalledTimes(1);
  });

  it('rechaza guardar currículo sin versión de malla', async () => {
    const usuario = userEvent.setup();

    montar();

    await llenarActividades(usuario);
    await abrirCurriculo(usuario);

    await usuario.selectOptions(
      screen.getByLabelText('Programa formativo'),
      '10'
    );

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    );

    expect(
      screen.getByRole('alert')
    ).toHaveTextContent(
      'selecciona un programa y una versión de malla'
    );

    expect(guardar).not.toHaveBeenCalled();
    expect(onGuardado).not.toHaveBeenCalled();
  });

  it('no conserva la malla anterior al cambiar programa', async () => {
    const usuario = userEvent.setup();

    montar();

    await llenarActividades(usuario);
    await abrirCurriculo(usuario);
    await seleccionarVersion(usuario);

    await usuario.selectOptions(
      screen.getByLabelText('Programa formativo'),
      '20'
    );

    expect(
      screen.getByLabelText(
        'Versión de malla curricular'
      )
    ).toHaveValue('');

    await usuario.click(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    );

    expect(guardar).not.toHaveBeenCalled();
    expect(onGuardado).not.toHaveBeenCalled();
  });
});
