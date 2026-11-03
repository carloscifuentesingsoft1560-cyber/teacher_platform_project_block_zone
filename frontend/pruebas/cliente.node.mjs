// Pruebas del cliente HTTP con Node; no requieren descargar dependencias.
import { test } from 'node:test';
import assert from 'node:assert/strict';

let numero = 0;
const clienteNuevo = () => import('../src/api/cliente.js?prueba=' + ++numero);
const respuesta = (datos, estado = 200) => new Response(JSON.stringify(datos), {
  status: estado, headers: { 'Content-Type': 'application/json' },
});

test('las consultas usan el origen propio y no envían CSRF innecesario', async (t) => {
  const api = await clienteNuevo();
  t.mock.method(globalThis, 'fetch', async (ruta, opciones) => {
    assert.equal(ruta, '/api/autenticacion/sesion/');
    assert.equal(opciones.credentials, 'same-origin');
    assert.equal(opciones.headers.Accept, 'application/json');
    assert.equal(opciones.headers['X-CSRFToken'], undefined);
    return respuesta({ usuario: { rol: 'profesor' } });
  });
  assert.equal((await api.solicitar('/autenticacion/sesion/')).usuario.rol, 'profesor');
});

test('el login obtiene CSRF, envía credenciales y conserva el token rotado', async (t) => {
  const api = await clienteNuevo();
  const solicitudes = [];
  t.mock.method(globalThis, 'fetch', async (ruta, opciones) => {
    solicitudes.push({ ruta, opciones });
    if (ruta.endsWith('/csrf/')) return respuesta({ csrfToken: 'token-inicial' });
    if (ruta.endsWith('/ingresar/')) return respuesta({ usuario: { rol: 'profesor' }, csrfToken: 'token-rotado' });
    return respuesta({});
  });
  assert.equal((await api.ingresar('demo_profesor', 'clave-ficticia')).rol, 'profesor');
  assert.equal(solicitudes[1].opciones.headers['X-CSRFToken'], 'token-inicial');
  assert.deepEqual(JSON.parse(solicitudes[1].opciones.body), { usuario: 'demo_profesor', contrasena: 'clave-ficticia' });
  await api.solicitar('/operacion-de-prueba/', { method: 'POST', body: '{}' });
  assert.equal(solicitudes[2].opciones.headers['X-CSRFToken'], 'token-rotado');
});

test('el logout requiere POST con CSRF y descarta el token al terminar', async (t) => {
  const api = await clienteNuevo();
  const solicitudes = [];
  t.mock.method(globalThis, 'fetch', async (ruta, opciones) => {
    solicitudes.push({ ruta, opciones });
    return ruta.endsWith('/csrf/') ? respuesta({ csrfToken: 'token-salida' }) : respuesta({});
  });
  await api.salir();
  assert.equal(solicitudes[1].opciones.method, 'POST');
  assert.equal(solicitudes[1].opciones.headers['X-CSRFToken'], 'token-salida');
  await api.solicitar('/prueba/', { method: 'POST' });
  assert.equal(solicitudes[2].opciones.headers['X-CSRFToken'], '');
});

test('los errores de permisos conservan estado y mensaje del backend', async (t) => {
  const api = await clienteNuevo();
  t.mock.method(globalThis, 'fetch', async () => respuesta({ detalle: 'Acceso restringido' }, 403));
  await assert.rejects(api.solicitar('/paneles/administrador/'), (error) =>
    error instanceof api.ErrorApi && error.estado === 403 && error.message === 'Acceso restringido');
});

test('la caída de red se distingue de un acceso denegado', async (t) => {
  const api = await clienteNuevo();
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('sin conexión'); });
  await assert.rejects(api.solicitar('/autenticacion/sesion/'), (error) =>
    error instanceof api.ErrorApi && error.estado === 0);
});

test('una respuesta no JSON no expone contenido HTML del servidor', async (t) => {
  const api = await clienteNuevo();
  t.mock.method(globalThis, 'fetch', async () => new Response('<html>error privado</html>', { status: 502 }));
  await assert.rejects(api.solicitar('/prueba/'), (error) =>
    error.estado === 502 && error.message === 'No se pudo completar la solicitud.');
});
