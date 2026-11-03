export function Estado({ titulo, children, accion, textoAccion = 'Reintentar' }) {
  return <section className="estado" aria-live="polite">
    <h2>{titulo}</h2>{children && <p>{children}</p>}
    {accion && <button type="button" onClick={accion}>{textoAccion}</button>}
  </section>;
}
