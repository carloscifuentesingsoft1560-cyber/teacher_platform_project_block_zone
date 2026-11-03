import { useEffect, useState } from 'react';
import { guardar, fechaBogota } from '../api/gestion.js';
import { solicitar } from '../api/cliente.js';
import { FormularioRegistro } from './FormularioRegistro.jsx';
import { ErrorGestion } from './Gestion.jsx';

const campos = [
  { nombre: 'tipo_autorizacion', etiqueta: 'Alcance: finalidad y versión aprobada', ruta: '/tipos-autorizacion/', numero: true },
  { nombre: 'metodo', etiqueta: 'Método de comprobación', opciones: [['presencial', 'Presencial'], ['documental', 'Documental']] },
  { nombre: 'referencia_evidencia', etiqueta: 'Clave privada de custodia de evidencia (UUID)', maxLength: 36 },
  { nombre: 'comprobada_en', etiqueta: 'Fecha y hora de la comprobación', tipo: 'datetime-local' },
  { nombre: 'resultado', etiqueta: 'Resultado de la revisión', opciones: [['pendiente', 'Pendiente'], ['verificada', 'Verificada'], ['rechazada', 'Rechazada'], ['revocada', 'Revocada']] },
  { nombre: 'identidad_contrastada', etiqueta: 'Contrasté la identidad sin copiar sus documentos', tipo: 'checkbox' },
  { nombre: 'facultad_contrastada', etiqueta: 'Revisé evidencia suficiente para este alcance', tipo: 'checkbox' },
  { nombre: 'vigente_desde', etiqueta: 'Inicio de vigencia de la facultad', tipo: 'date' },
  { nombre: 'vigente_hasta', etiqueta: 'Vencimiento acreditado, cuando corresponda', tipo: 'date', requerido: false },
];

export function ComprobacionFacultad({ vinculo, cancelar, completada }) {
  const [historia, cambiarHistoria] = useState([]);
  const [error, cambiarError] = useState(null);
  const [cargando, cambiarCargando] = useState(true);
  useEffect(() => {
    let vigente = true;
    solicitar('/vinculos-acudientes/' + vinculo.id + '/historial-facultades/')
      .then((r) => { if (vigente) cambiarHistoria(r); })
      .catch((e) => { if (vigente) cambiarError(e); })
      .finally(() => { if (vigente) cambiarCargando(false); });
    return () => { vigente = false; };
  }, [vinculo.id]);
  async function enviar(datos) {
    if (datos.resultado === 'verificada' && !(datos.identidad_contrastada && datos.facultad_contrastada)) {
      throw new Error('Una revisión insuficiente no acredita la facultad.');
    }
    await guardar('/vinculos-acudientes/' + vinculo.id + '/verificar/', {
      ...datos, version: vinculo.version,
      comprobada_en: new Date(datos.comprobada_en).toISOString(),
      vigente_hasta: datos.vigente_hasta || null,
    });
    completada();
  }
  return <section aria-label="Comprobación de facultad">
    <p>Vínculo {vinculo.id} · Deportista {vinculo.deportista} · Acudiente {vinculo.acudiente}</p>
    <p>Parentesco declarado: {vinculo.parentesco || 'Sin declarar'} · Contacto principal: {vinculo.es_contacto_principal ? 'Sí' : 'No'}.</p>
    <p>El parentesco y ser contacto principal no acreditan representación. El método no garantiza suficiencia: registra el resultado real de la revisión para una finalidad y versión concretas.</p>
    <p>La evidencia permanece bajo custodia institucional protegida. Introduce únicamente su clave UUID; no pegues números de documento, enlaces públicos ni archivos. El responsable y la fecha de registro los establece el servidor.</p>
    <p>Una decisión no habilita imágenes, vídeos, acceso familiar ni IA. Si la revisión es insuficiente, registra pendiente o rechazada. Revocada retira la acreditación anterior del mismo alcance.</p>
    <ErrorGestion error={error} />
    {cargando && <p role="status">Consultando historial de facultades…</p>}
    {!cargando && !error && <>
      <details><summary>Historial de decisiones ({historia.length})</summary>
        {!historia.length && <p>Sin comprobaciones registradas; una marca histórica no acredita esta finalidad.</p>}
        <ul>{historia.map((e) => <li key={e.id}>
          {e.resultado} · {e.alcance} · v{e.numero_version_texto} · {e.metodo} · Comprobada: {e.comprobada_en} · Responsable: {e.responsable} · Registrada: {e.registrada_en} · Vigencia: {e.vigente_desde} a {e.vigente_hasta || 'sin vencimiento acreditado'} · Referencia privada: {e.referencia_evidencia}
        </li>)}</ul>
      </details>
      <FormularioRegistro titulo="Registrar comprobación de facultad" campos={campos}
        inicial={{ identidad_contrastada: false, facultad_contrastada: false, vigente_desde: fechaBogota() }}
        guardar={enviar} cancelar={cancelar} />
    </>}
    {error && <button type="button" onClick={cancelar}>Cerrar comprobación</button>}
  </section>;
}
