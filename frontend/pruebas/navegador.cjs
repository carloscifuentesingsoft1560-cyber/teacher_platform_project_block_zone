// QA visual con API interceptada y datos ficticios: nunca modifica PostgreSQL.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const grupo = { id: 1, codigo: 'demo-a', nombre: 'Grupo ficticio A', disciplina: 1, disciplina_nombre: 'Escalada', nivel: 1, nivel_nombre: 'Nivel 1', periodo: 1, periodo_nombre: 'Ciclo ficticio', cupo_maximo: 12, activo: true, horarios: [{ id: 1, dia: 0, hora_inicio: '10:00:00', hora_fin: '12:00:00', duracion_minutos: 120 }] };
const usuario = { id: 2, username: 'demo_docente', first_name: 'Docente', last_name: 'Ficticio', email: '', rol: 'profesor', is_active: true };
const pagina = (results) => ({ results, count: results.length, next: null });
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ZDB_NAVEGADOR ? { executablePath: process.env.ZDB_NAVEGADOR } : {}) });
  let revisiones = 0;
  try {
    for (const ancho of [390, 768, 1366]) {
      for (const [rol, ruta] of [['profesor', '/profesor/grupos'], ['coordinador', '/coordinacion/profesores'], ['administrador', '/administracion/usuarios']]) {
        const contexto = await browser.newContext({ viewport: { width: ancho, height: 900 } });
        const errores = [];
        const page = await contexto.newPage();
        page.on('pageerror', (error) => errores.push(error.message));
        await contexto.route('**/api/**', async (route) => {
          if (!new URL(route.request().url()).pathname.startsWith('/api/')) return route.continue();
          assert.equal(route.request().method(), 'GET', 'Esta comprobación visual no admite escrituras');
          const camino = new URL(route.request().url()).pathname;
          let datos = pagina([]);
          if (camino.endsWith('/sesion/')) datos = { usuario: { id: 1, username: 'demo_' + rol, nombre: 'Cuenta ficticia', rol } };
          else if (camino.endsWith('/usuarios/')) datos = pagina([usuario]);
          else if (camino.endsWith('/grupos/')) datos = pagina([grupo]);
          else if (camino.endsWith('/profesores/')) datos = pagina([{ id: 2, nombre: 'Docente Ficticio', username: 'demo_docente', rol: 'profesor' }]);
          else if (camino.endsWith('/calendario/')) datos = { eventos: [] };
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(datos) });
        });
        await page.goto(base + ruta);
        await page.getByRole('heading', { level: 1 }).waitFor();
        if (rol === 'administrador') {
          await page.getByRole('button', { name: 'Crear usuario', exact: true }).click();
          await page.getByRole('form', { name: 'Formulario de usuario' }).waitFor();
        } else if (rol === 'profesor') {
          await page.getByRole('button', { name: 'Ver demo-a', exact: true }).click();
        } else {
          await page.getByText('Docente Ficticio', { exact: true }).waitFor();
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, rol + ' desborda a ' + ancho + 'px');
        assert.deepEqual(errores, []);
        revisiones++;
        await contexto.close();
      }
    }
    const contexto = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await contexto.newPage();
    await contexto.route('**/api/**', (route) => new URL(route.request().url()).pathname.startsWith('/api/') ? route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detalle: 'Sin sesión' }) }) : route.continue());
    await page.goto(base + '/ingresar');
    await page.getByRole('heading', { name: 'Ingresar', exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await contexto.close(); revisiones++;
    console.log('Navegador: ' + revisiones + ' vistas verificadas sin errores JS ni desbordamiento horizontal. API ficticia, sin escrituras.');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
