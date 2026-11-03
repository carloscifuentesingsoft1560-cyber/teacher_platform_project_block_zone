
import { useEffect, useState } from 'react';
import { todas } from '../api/gestion.js';
import { ErrorGestion } from './Gestion.jsx';

const VACIOS = {
  fases: [],
  semanas: [],
  clases: [],
  competencias: [],
};

function rutaOpciones(sesionId, tipo, filtros = {}) {
  const parametros = new URLSearchParams({ tipo });

  Object.entries(filtros).forEach(([clave, valor]) => {
    if (valor !== null && valor !== undefined && valor !== '') {
      parametros.set(clave, String(valor));
    }
  });

  return `/sesiones/${sesionId}/opciones-plan/?${parametros}`;
}

function id(valor) {
  if (!valor) return null;
  const numero = Number(valor);
  return Number.isInteger(numero) && numero > 0 ? numero : null;
}

export function ContextoCurricularSesion({
  sesionId,
  valor,
  cambiar,
  disabled = false,
  onEstadoCambio,
}) {
  const [principales, establecerPrincipales] = useState({
    sesionId: null,
    programas: [],
    versiones: [],
  });

  const [estructura, establecerEstructura] = useState({
    sesionId: null,
    version: null,
    ...VACIOS,
  });

  const [cargandoPrincipales, establecerCargandoPrincipales] =
    useState(true);

  const [cargandoEstructura, establecerCargandoEstructura] =
    useState(false);

  const [errorPrincipales, establecerErrorPrincipales] =
    useState(null);

  const [errorEstructura, establecerErrorEstructura] =
    useState(null);

  const programa = valor.programa_id ?? '';
  const version = valor.malla_version_id ?? '';
  const fase = valor.fase_curricular_id ?? '';
  const semana = valor.semana_id ?? '';
  const clase = valor.clase_id ?? '';
  const competencias = valor.competencias_ids ?? [];

  useEffect(() => {
    let vigente = true;

    establecerCargandoPrincipales(true);
    establecerErrorPrincipales(null);

    async function cargar() {
      try {
        const [programas, versiones] = await Promise.all([
          todas(rutaOpciones(sesionId, 'programas')),
          todas(rutaOpciones(sesionId, 'versiones')),
        ]);

        if (!vigente) return;

        establecerPrincipales({
          sesionId,
          programas,
          versiones,
        });
      } catch (fallo) {
        if (!vigente) return;

        establecerPrincipales({
          sesionId,
          programas: [],
          versiones: [],
        });

        establecerErrorPrincipales(fallo);
      } finally {
        if (vigente) establecerCargandoPrincipales(false);
      }
    }

    cargar();

    return () => {
      vigente = false;
    };
  }, [sesionId]);

  useEffect(() => {
    let vigente = true;

    establecerErrorEstructura(null);

    if (!version) {
      establecerCargandoEstructura(false);
      establecerEstructura({
        sesionId,
        version: null,
        ...VACIOS,
      });

      return () => {
        vigente = false;
      };
    }

    establecerCargandoEstructura(true);

    async function cargar() {
      const filtros = { malla_version: version };

      try {
        const [
          fases,
          semanas,
          clases,
          nuevasCompetencias,
        ] = await Promise.all([
          todas(rutaOpciones(sesionId, 'fases', filtros)),
          todas(rutaOpciones(sesionId, 'semanas', filtros)),
          todas(rutaOpciones(sesionId, 'clases', filtros)),
          todas(rutaOpciones(sesionId, 'competencias', filtros)),
        ]);

        if (!vigente) return;

        establecerEstructura({
          sesionId,
          version,
          fases,
          semanas,
          clases,
          competencias: nuevasCompetencias,
        });
      } catch (fallo) {
        if (!vigente) return;

        establecerEstructura({
          sesionId,
          version,
          ...VACIOS,
        });

        establecerErrorEstructura(fallo);
      } finally {
        if (vigente) establecerCargandoEstructura(false);
      }
    }

    cargar();

    return () => {
      vigente = false;
    };
  }, [sesionId, version]);

  const principalesVigentes =
    principales.sesionId === sesionId;

  const estructuraVigente =
    estructura.sesionId === sesionId &&
    estructura.version === (version || null);

  const catalogosPrincipales = principalesVigentes
    ? principales
    : { programas: [], versiones: [] };

  const catalogos =
    estructuraVigente && !errorEstructura
      ? estructura
      : VACIOS;

  const cargando =
    cargandoPrincipales ||
    cargandoEstructura ||
    !principalesVigentes ||
    (!!version && !estructuraVigente);

  const error = errorPrincipales || errorEstructura;

  const listo =
    !cargando &&
    !error &&
    principalesVigentes &&
    (!version || estructuraVigente);

  // El padre solo autoriza el guardado cuando recibe
  // confirmación del catálogo de la versión exacta.
  const claveCatalogo = `${sesionId}:${version || 0}`;

  useEffect(() => {
    onEstadoCambio?.({
      clave: claveCatalogo,
      listo: Boolean(listo),
    });
  }, [onEstadoCambio, claveCatalogo, listo]);

  const versionesDisponibles =
    catalogosPrincipales.versiones.filter(
      (item) =>
        !programa ||
        item.identidad__programa_id === Number(programa)
    );

  const semanasDisponibles = catalogos.semanas.filter(
    (item) =>
      !fase || item.fase_id === Number(fase)
  );

  const clasesDisponibles = catalogos.clases.filter(
    (item) =>
      !semana || item.semana_id === Number(semana)
  );

  const bloqueado =
    disabled ||
    !listo;

  function seleccionarPrograma(evento) {
    cambiar({
      programa_id: id(evento.target.value),
      malla_version_id: null,
      fase_curricular_id: null,
      semana_id: null,
      clase_id: null,
      competencias_ids: [],
    });
  }

  function seleccionarVersion(evento) {
    cambiar({
      ...valor,
      malla_version_id: id(evento.target.value),
      fase_curricular_id: null,
      semana_id: null,
      clase_id: null,
      competencias_ids: [],
    });
  }

  function seleccionarFase(evento) {
    cambiar({
      ...valor,
      fase_curricular_id: id(evento.target.value),
      semana_id: null,
      clase_id: null,
    });
  }

  function seleccionarSemana(evento) {
    cambiar({
      ...valor,
      semana_id: id(evento.target.value),
      clase_id: null,
    });
  }

  function seleccionarClase(evento) {
    cambiar({
      ...valor,
      clase_id: id(evento.target.value),
    });
  }

  function alternarCompetencia(competenciaId, marcada) {
    cambiar({
      ...valor,
      competencias_ids: marcada
        ? [...new Set([...competencias, competenciaId])]
        : competencias.filter(
            (actual) => actual !== competenciaId
          ),
    });
  }

  return (
    <fieldset
      className="formulario-gestion"
      disabled={disabled}
    >
      <legend>Vinculación curricular de la sesión</legend>

      <p>
        Selecciona contenidos autorizados para el grupo
        y asociados a una versión curricular vigente.
      </p>

      <ErrorGestion error={error} />

      {cargando && (
        <p role="status">
          Consultando contenidos curriculares…
        </p>
      )}

      <div className="rejilla-formulario">
        <label className="campo-gestion">
          Programa formativo
          <select
            value={programa}
            onChange={seleccionarPrograma}
            disabled={bloqueado}
          >
            <option value="">
              Sin vinculación curricular
            </option>
            {catalogosPrincipales.programas.map((item) => (
              <option key={item.id} value={item.id}>
                Programa {item.id} · {item.modalidad}
              </option>
            ))}
          </select>
        </label>

        <label className="campo-gestion">
          Versión de malla curricular
          <select
            value={version}
            onChange={seleccionarVersion}
            disabled={bloqueado || !programa}
          >
            <option value="">Seleccionar versión</option>
            {versionesDisponibles.map((item) => (
              <option key={item.id} value={item.id}>
                {item.identidad__nombre} · Versión {item.numero}
              </option>
            ))}
          </select>
        </label>

        <label className="campo-gestion">
          Fase curricular
          <select
            value={fase}
            onChange={seleccionarFase}
            disabled={bloqueado || !version}
          >
            <option value="">Seleccionar fase</option>
            {catalogos.fases.map((item) => (
              <option key={item.id} value={item.id}>
                {item.nombre}
              </option>
            ))}
          </select>
        </label>

        <label className="campo-gestion">
          Semana
          <select
            value={semana}
            onChange={seleccionarSemana}
            disabled={bloqueado || !version}
          >
            <option value="">Seleccionar semana</option>
            {semanasDisponibles.map((item) => (
              <option key={item.id} value={item.id}>
                Semana {item.ordinal}
              </option>
            ))}
          </select>
        </label>

        <label className="campo-gestion">
          Clase prevista
          <select
            value={clase}
            onChange={seleccionarClase}
            disabled={bloqueado || !semana}
          >
            <option value="">Seleccionar clase</option>
            {clasesDisponibles.map((item) => (
              <option key={item.id} value={item.id}>
                Clase {item.ordinal}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!!version && (
        <section>
          <h3>Competencias curriculares</h3>

          {listo && !catalogos.competencias.length && (
            <p>
              No hay competencias disponibles para esta versión.
            </p>
          )}

          {catalogos.competencias.map((item) => (
            <label
              key={item.id}
              className="campo-checkbox"
            >
              <input
                type="checkbox"
                checked={competencias.includes(item.id)}
                disabled={bloqueado}
                onChange={(evento) =>
                  alternarCompetencia(
                    item.id,
                    evento.target.checked
                  )
                }
              />
              {item.texto}
            </label>
          ))}
        </section>
      )}
    </fieldset>
  );
}
