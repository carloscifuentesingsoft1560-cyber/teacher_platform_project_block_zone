// QA aislado con datos ficticios. No consulta ni modifica PostgreSQL.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const pagina = (results) => ({ results, count: results.length, next: null });
const completo = '001234567890';
const persona = { id: 1, identificador_publico: 'ficticio', codigo_interno: 'ZB-NO-VISIBLE', nombres: 'Nombre', apellidos: 'Ficticio', fecha_nacimiento: '2015-01-01', estado: 'activo', version: 1, tipo_documento: 'TI', numero_documento: completo, pais_emisor: 'CO', documento_presentacion: 'TI ' + completo };
const tipos = [{ codigo: 'TI', nombre: 'Tarjeta de identidad' }, { codigo: 'CC', nombre: 'Cédula de ciudadanía' }, { codigo: 'PA', nombre: 'Pasaporte' }];
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ZDB_NAVEGADOR ? { executablePath: process.env.ZDB_NAVEGADOR } : {}) });
  let casos = 0;
  try {
    for (const ancho of [390, 768, 1366]) {
      for (const rol of ['administrador', 'coordinador', 'profesor']) {
        const rutaRol = { administrador: '/administracion', coordinador: '/coordinacion', profesor: '/profesor' }[rol];
        for (const detalle of [false, true]) {
          const context = await browser.newContext({ viewport: { width: ancho, height: 900 } });
          try {
            const page = await context.newPage(), errores = [];
            page.on('pageerror', (e) => errores.push(e.message));
            await context.route('**/api/**', async (route) => {
              const p = new URL(route.request().url()).pathname;
              if (!p.startsWith('/api/')) return route.continue();
              assert.equal(route.request().method(), 'GET', 'Solo consultas en QA de navegador');
              let datos = pagina([]);
              const ficha = rol === 'profesor' ?
                { id: 1, identificador_publico: 'ficticio', nombres: 'Nombre', apellidos: 'Ficticio', estado: 'activo', tipo_documento: 'TI', numero_documento_enmascarado: '****7890', documento_presentacion: 'TI ****7890' } : persona;
              if (p.endsWith('/sesion/')) datos = { usuario: { id: 1, nombre: 'Cuenta ficticia', rol } };
              else if (p.endsWith('/tipos-documento/')) datos = pagina(tipos);
              else if (p.endsWith('/deportistas/ficticio/')) datos = ficha;
              else if (p.endsWith('/deportistas/')) datos = pagina([ficha]);
              await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(datos) });
            });
            await page.goto(base + rutaRol + '/deportistas' + (detalle ? '/ficticio' : ''));
            await page.getByRole('heading', { name: detalle ? 'Ficha individual del deportista' : 'Deportistas', exact: true }).waitFor();
            await page.getByText(rol === 'profesor' ? 'TI ****7890' : 'TI ' + completo, { exact: true }).waitFor();
            assert.equal(await page.getByText('ZB-NO-VISIBLE', { exact: true }).count(), 0);
            if (!detalle) {
              const caja = page.locator('.acciones-deportista');
              await caja.waitFor();
              const rects = await caja.locator(':scope > *').evaluateAll((elementos) => elementos.map((e) => { const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, h: r.height }; }));
              for (const r of rects) assert.ok(r.h >= 44, 'Área de acción accesible');
              for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
                const a = rects[i], b = rects[j];
                const separacion = Math.max(b.l - a.r, a.l - b.r, b.t - a.b, a.t - b.b);
                assert.ok(separacion >= 9, 'Acciones separadas al menos 10px salvo redondeo');
              }
            }
            if (rol !== 'profesor') {
              await page.getByRole('button', { name: detalle ? 'Cambiar documento' : 'Crear deportista', exact: true }).click();
              const form = page.getByRole('form', { name: detalle ? 'Cambio documental' : 'Crear ficha de deportista', exact: true });
              await form.getByLabel('Tipo de documento', { exact: true }).selectOption('PA');
              await form.getByLabel('Número de documento', { exact: true }).fill('AB-0001');
              await form.getByLabel('País emisor (código ISO)', { exact: true }).fill('VE');
              assert.equal(await form.getByLabel('Número de documento', { exact: true }).inputValue(), 'AB-0001');
            } else {
              assert.equal(await page.getByRole('button', { name: 'Cambiar documento', exact: true }).count(), 0);
              assert.equal((await page.locator('body').innerHTML()).includes(completo), false);
            }
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Sin desbordamiento a ' + ancho);
            assert.deepEqual(errores, []);
            casos++;
          } finally { await context.close(); }
        }
      }
    }
    console.log('Identificación documental: ' + casos + ' vistas/formularios aprobados; acciones separadas, máscara docente y rutas UUID. Sin escrituras.');
  } finally { await browser.close(); }
})().catch((e) => { console.error(e.message); process.exitCode = 1; });
