
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

import { FinalizacionEjecucionSesion } from
  '../componentes/FinalizacionEjecucionSesion.jsx';

import { solicitar } from '../api/cliente.js';
import { guardar } from '../api/gestion.js';

vi.mock('../api/cliente.js', () => ({
  solicitar: vi.fn(),
}));

vi.mock('../api/gestion.js', () => ({
  guardar: vi.fn(),
}));

const sesion = {
  id: 12,
  version: 4,
  fecha: '2026-11-02',
  estado: 'planificada',
  estado_ejecucion: 'borrador',
  asistencia_confirmada: false,
};

const ejecucion = {
  id: 31,
  plan: {
    id: 25,
    numero: 1,
  },
  inicio: '2026-11-02T10:00:00-05:00',
  fin: '2026-11-02T12:00:00-05:00',
  finalizada_en: null,
  actividades: [
    {
      tarea: 101,
      resultado: 'realizada',
      minutos: 60,
      descripcion: 'Trabajo técnico',
    },
  ],
};

const asistencia = {
  version: 4,
  cerrada: false,
  requiere_preparacion: false,
  participantes: [
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
  ],
};

const respuestaFinalizacion = {
  sesion: {
    ...sesion,
    version: 5,
    estado_ejecucion: 'registrada_pendiente_validacion',
    asistencia_confirmada: true,
  },
  asistencia: {
    ...asistencia,
    version: 5,
    cerrada: true,
  },
};

function prepararConsultas({
  versionEjecucion = 4,
  ejecucionActual = ejecucion,
  asistenciaActual = asistencia,
} = {}) {
  solicitar.mockImplementation((ruta) => {
    if (ruta === '/sesiones/12/ejecucion/') {
      return Promise.resolve({
        version: versionEjecucion,
        ejecucion: ejecucionActual,
      });
    }

    if (ruta === '/sesiones/12/asistencia/') {
      return Promise.resolve(asistenciaActual);
    }

    throw new Error(`Ruta no simulada: ${ruta}`);
  });
}

async function esperarFormulario() {
  await screen.findByText('Comprobaciones antes de finalizar');

  await waitFor(() => {
    expect(
      screen.getByRole('checkbox')
    ).toBeEnabled();
  });
}

function botonFinalizar() {
  return screen.getByRole('button', {
    name: 'Confirmar finalización definitiva',
  });
}

function crearPromesaPendiente() {
  let resolver;

  const promesa = new Promise((resolve) => {
    resolver = resolve;
  });

  return { promesa, resolver };
}

beforeEach(() => {
  vi.clearAllMocks();

  prepararConsultas();

  guardar.mockResolvedValue(respuestaFinalizacion);
});

describe('F3.5: finalización protegida de ejecución', () => {
  it('exige confirmación antes de permitir finalizar', async () => {
    const usuario = userEvent.setup();

    render(
      <FinalizacionEjecucionSesion
        sesion={sesion}
        onFinalizado={vi.fn()}
        onCancelar={vi.fn()}
      />
    );

    await esperarFormulario();

    expect(botonFinalizar()).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();

    await usuario.click(screen.getByRole('checkbox'));

    expect(botonFinalizar()).toBeEnabled();
  });

  it('finaliza ejecución y verifica el cierre de asistencia sin validar institucionalmente', async () => {
    const usuario = userEvent.setup();
    const onFinalizado = vi.fn();

    render(
      <FinalizacionEjecucionSesion
        sesion={sesion}
        onFinalizado={onFinalizado}
        onCancelar={vi.fn()}
      />
    );

    await esperarFormulario();

    await usuario.click(screen.getByRole('checkbox'));
    await usuario.click(botonFinalizar());

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const [ruta, datos] = guardar.mock.calls[0];

    expect(ruta).toBe(
      '/sesiones/12/ejecucion/finalizar/'
    );

    expect(datos).toEqual({
      clave: expect.stringMatching(
        /^[0-9a-f-]{36}$/i
      ),
      version: 4,
    });

    await waitFor(() => {
      expect(onFinalizado).toHaveBeenCalledWith(
        respuestaFinalizacion
      );
    });

    expect(
      respuestaFinalizacion.sesion.estado
    ).toBe('planificada');

    expect(
      respuestaFinalizacion.asistencia.cerrada
    ).toBe(true);

    expect(
      respuestaFinalizacion.sesion.estado_ejecucion
    ).toBe('registrada_pendiente_validacion');

    expect(guardar).toHaveBeenCalledTimes(1);
  });

  it('bloquea la finalización con asistencia incompleta', async () => {
    const usuario = userEvent.setup();

    prepararConsultas({
      asistenciaActual: {
        ...asistencia,
        participantes: [
          asistencia.participantes[0],
          {
            ...asistencia.participantes[1],
            estado: '',
          },
        ],
      },
    });

    render(
      <FinalizacionEjecucionSesion sesion={sesion} />
    );

    await screen.findByText(
      /Hay 1 participantes sin estado/i
    );

    expect(
      screen.getByRole('checkbox')
    ).toBeDisabled();

    expect(botonFinalizar()).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();

    // No debe convertirse en una acción válida al hacer clic.
    await usuario.click(botonFinalizar());

    expect(guardar).not.toHaveBeenCalled();
  });

  it('bloquea registros con versiones diferentes', async () => {
    prepararConsultas({
      versionEjecucion: 3,
    });

    render(
      <FinalizacionEjecucionSesion sesion={sesion} />
    );

    expect(
      await screen.findByText(
        /Los registros consultados no coinciden/i
      )
    ).toBeInTheDocument();

    expect(
      screen.getByRole('checkbox')
    ).toBeDisabled();

    expect(botonFinalizar()).toBeDisabled();

    expect(guardar).not.toHaveBeenCalled();
  });

  it('impide dos envíos mientras espera respuesta', async () => {
    const usuario = userEvent.setup();
    const pendiente = crearPromesaPendiente();
    const onFinalizado = vi.fn();

    guardar.mockReturnValue(pendiente.promesa);

    render(
      <FinalizacionEjecucionSesion
        sesion={sesion}
        onFinalizado={onFinalizado}
      />
    );

    await esperarFormulario();

    await usuario.click(screen.getByRole('checkbox'));
    await usuario.click(botonFinalizar());

    await waitFor(() => {
      expect(guardar).toHaveBeenCalledTimes(1);
    });

    const enviando = screen.getByRole('button', {
      name: 'Finalizando ejecución…',
    });

    expect(enviando).toBeDisabled();

    await usuario.click(enviando);

    expect(guardar).toHaveBeenCalledTimes(1);

    pendiente.resolver(respuestaFinalizacion);

    await waitFor(() => {
      expect(onFinalizado).toHaveBeenCalledTimes(1);
    });

    expect(guardar).toHaveBeenCalledTimes(1);
  });

  it('bloquea reintentos cuando la respuesta de red es incierta', async () => {
    const usuario = userEvent.setup();

    guardar.mockRejectedValue(
      Object.assign(
        new Error('No hubo respuesta del servidor'),
        { estado: 0 }
      )
    );

    render(
      <FinalizacionEjecucionSesion sesion={sesion} />
    );

    await esperarFormulario();

    await usuario.click(screen.getByRole('checkbox'));
    await usuario.click(botonFinalizar());

    expect(
      await screen.findByText(
        /La finalización podría haberse realizado/i
      )
    ).toBeInTheDocument();

    expect(botonFinalizar()).toBeDisabled();

    expect(guardar).toHaveBeenCalledTimes(1);
  });
});
