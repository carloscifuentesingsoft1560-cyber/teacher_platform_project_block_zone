import { prepararCsrf, solicitar } from './cliente.js';

export async function guardar(ruta, datos, metodo = 'POST') {
  await prepararCsrf();
  return solicitar(ruta, { method: metodo, body: JSON.stringify(datos) });
}
export async function todas(ruta) {
  const datos = [];
  let siguiente = ruta;
  for (let pagina = 0; siguiente && pagina < 100; pagina++) {
    const respuesta = await solicitar(siguiente);
    datos.push(...(respuesta.results || []));
    siguiente = respuesta.next ? new URL(respuesta.next, window.location.origin).pathname.replace(/^\/api/, '') + new URL(respuesta.next, window.location.origin).search : null;
  }
  if (siguiente) throw new Error('Refina la consulta: hay demasiados registros para este selector.');
  return datos;
}
export const fechaBogota = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Bogota' }).format(new Date());
