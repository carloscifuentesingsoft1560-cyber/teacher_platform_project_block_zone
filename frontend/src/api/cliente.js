let tokenCsrf = null;

export class ErrorApi extends Error {
  constructor(mensaje, estado, errores = null) {
    super(mensaje);
    this.estado = estado;
    this.errores = errores;
  }
}

export async function solicitar(ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch('/api' + ruta, {
      ...opciones,
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
        ...(opciones.body && !(opciones.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(opciones.method && opciones.method !== 'GET' ? { 'X-CSRFToken': tokenCsrf || '' } : {}),
        ...opciones.headers,
      },
    });
  } catch {
    throw new ErrorApi('No pudimos conectar. Comprueba que el servidor esté disponible.', 0);
  }
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok && [401,403].includes(respuesta.status) && ruta !== '/autenticacion/sesion/' && typeof window !== 'undefined') window.dispatchEvent(new Event('zb-permisos'));
  if (!respuesta.ok) throw new ErrorApi(datos.detalle || 'No se pudo completar la solicitud.', respuesta.status, datos.errores);
  return datos;
}

export async function prepararCsrf() {
  const datos = await solicitar('/autenticacion/csrf/');
  tokenCsrf = datos.csrfToken;
}

export async function ingresar(usuario, contrasena) {
  await prepararCsrf();
  const datos = await solicitar('/autenticacion/ingresar/', {
    method: 'POST', body: JSON.stringify({ usuario, contrasena }),
  });
  tokenCsrf = datos.csrfToken;
  return datos.usuario;
}

export async function salir() {
  await prepararCsrf();
  await solicitar('/autenticacion/salir/', { method: 'POST' });
  tokenCsrf = null;
}
