
import {
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  render,
  screen,
} from '@testing-library/react';

import {
  PlanificacionSesion,
} from '../componentes/PlanificacionSesion.jsx';

const sesion = {
  id: 12,
  fecha: '2026-11-03',
  hora_inicio: '10:00:00',
  hora_fin: '12:00:00',
  estado: 'planificada',
  version: 3,
  planes: [],
};

const tareas = [
  {
    orden: 1,
    fase: 'inicial',
    minutos: 30,
    objetivo: '',
    instrucciones: 'Calentamiento',
  },
  {
    orden: 2,
    fase: 'central',
    minutos: 60,
    objetivo: '',
    instrucciones: 'Entrenamiento',
  },
  {
    orden: 3,
    fase: 'final',
    minutos: 30,
    objetivo: '',
    instrucciones: 'Cierre',
  },
];

function montar(plan) {
  return render(
    <PlanificacionSesion
      sesion={{
        ...sesion,
        planes: plan ? [plan] : [],
      }}
      onGuardado={vi.fn()}
      onCancelar={vi.fn()}
    />
  );
}

describe('Protecciones curriculares F2', () => {
  it('bloquea la revisión de una malla vinculada', () => {
    montar({
      id: 1,
      objetivo: 'Objetivo curricular',
      programa: 2,
      malla_version: 5,
      tareas,
    });

    expect(
      screen.getByText(
        /Para protegerlas, la edición básica está/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();
  });

  it('bloquea la pérdida de ejercicios asociados', () => {
    montar({
      id: 2,
      objetivo: 'Objetivo con ejercicios',
      competencias: [],
      tareas: tareas.map((tarea, indice) => ({
        ...tarea,
        ejercicio_version: indice === 1 ? 9 : null,
      })),
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();
  });

  it('bloquea planes con más actividades que el editor básico', () => {
    montar({
      id: 3,
      objetivo: 'Objetivo con cuatro tareas',
      tareas: [
        ...tareas,
        {
          orden: 4,
          fase: 'final',
          minutos: 1,
          objetivo: '',
          instrucciones: 'Actividad adicional',
        },
      ],
    });

    expect(
      screen.getByText(
        /Su edición requiere el editor completo/
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeDisabled();
  });

  it('mantiene disponible la planificación básica sin vínculos', () => {
    montar({
      id: 4,
      objetivo: 'Objetivo básico',
      programa: null,
      malla_version: null,
      competencias: [],
      tareas,
    });

    expect(
      screen.getByRole('button', {
        name: 'Guardar planificación',
      })
    ).toBeEnabled();
  });
});
