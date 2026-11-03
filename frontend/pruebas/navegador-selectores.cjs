// QA aislado: solo GET interceptados; no utiliza PostgreSQL ni sesiones reales.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const pagina = (results) => ({ results, count: results.length, next: null });
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ZDB_NAVEGADOR ? { executablePath: process.env.ZDB_NAVEGADOR } : {}) });
  let casos = 0;
  try {
    for (const width of [390, 768, 1366]) for (const rol of ['administrador', 'coordinador', 'profesor']) for (const pantalla of ['deportistas', 'inscripciones']) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      try {
        const page = await context.newPage(), errores = [], consultas = [];
        page.on('pageerror', (e) => errores.push(e.message));
        await context.route('**/api/**', async (route) => {
          const url = new URL(route.request().url());
          if (!url.pathname.startsWith('/api/')) return route.continue();
          assert.equal(route.request().method(), 'GET');
          consultas.push(url);
          let datos = pagina([]);
          if (url.pathname.endsWith('/sesion/')) datos = { usuario: { id: 1, nombre: 'Cuenta ficticia', rol } };
          else if (url.pathname.endsWith('/grupos/')) datos = pagina([{ id: 7, codigo: 'ESC-N1-001', nombre: 'Escalada inicial con nombre institucional extenso', periodo_nombre: 'Periodo de formación octubre a diciembre 2026' }]);
          else if (url.pathname.endsWith('/cupos/')) datos = { cupo_maximo: 15, inscripciones_activas: 4, reservas_vigentes: 2, ocupacion_actual: 6,
            disponibles_actuales: 9, ocupacion_maxima: 8, disponibles: 7, fecha_corte: '2026-10-29', desde: '2026-10-29', hasta: '2026-12-31' };
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(datos) });
        });
        const prefijo = { administrador: '/administracion', coordinador: '/coordinacion', profesor: '/profesor' }[rol];
        await page.goto(base + prefijo + '/' + pantalla);
        const etiqueta = pantalla === 'deportistas' ? 'Filtrar grupo' : 'Grupo para consultar cupos';
        try {
          await page.locator('select option').filter({ hasText: 'ESC-N1-001' }).waitFor({ state: 'attached', timeout: 10000 });
        } catch (error) {
          console.error(JSON.stringify({ rol, pantalla, width, errores, consultas: consultas.map((u) => u.pathname), texto: (await page.locator('body').innerText()).slice(0, 2200) }));
          throw error;
        }
        const filtroAplicado = pantalla === 'deportistas' ? page.waitForResponse((r) => {
          const u = new URL(r.url());return u.pathname === '/api/deportistas/' && u.searchParams.get('grupo') === '7';
        }, { timeout: 10000 }).then(() => true).catch(() => false) : null;
        await page.getByLabel(etiqueta, { exact: true }).selectOption('7');
        if (pantalla === 'inscripciones') {
          await page.getByRole('region', { name: 'Cupos del grupo' }).waitFor();
          assert.match(await page.getByRole('region', { name: 'Cupos del grupo' }).innerText(), /Reservas vigentes: 2/);
          assert.ok(consultas.some((u) => u.pathname.endsWith('/cupos/') && u.searchParams.get('grupo') === '7'));
        } else {
          if (!await filtroAplicado) {
            console.error(JSON.stringify({ rol, pantalla, width, url: page.url(), consultas: consultas.map((u) => u.href), errores }));
            throw new Error('No se observó el GET filtrado por grupo.');
          }
        }
        const medidas = await page.locator('.selector-catalogo').evaluateAll((els) => els.map((e) => {
          const r = e.getBoundingClientRect();return { left: r.left, right: r.right, width: document.documentElement.clientWidth };
        }));
        for (const r of medidas) assert.ok(r.left >= 0 && r.right <= r.width + 1, 'Selector dentro del viewport');
        assert.deepEqual(errores, []);casos++;
      } finally { await context.close(); }
    }
    process.stdout.write('Selectores y cupos: ' + casos + ' recorridos aprobados (tres roles, dos pantallas, tres anchos).\n');
  } finally { await browser.close(); }
})().catch((e) => { console.error(e.message); process.exitCode = 1; });
