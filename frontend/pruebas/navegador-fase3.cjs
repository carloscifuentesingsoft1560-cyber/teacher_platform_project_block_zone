// Navegación de Fase 3 con API ficticia: no conecta ni escribe en PostgreSQL.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const pagina = (results) => ({ results, count: results.length, next: null });
const persona = { id: 1, identificador_publico: 'ficticio', codigo_interno: 'ZB-FICTICIO', nombres: 'Nombre', apellidos: 'Ficticio', fecha_nacimiento: '2015-01-01', estado: 'activo', version: 1 };
const inscripcion = { id: 1, deportista: 1, nombre_deportista: 'Nombre Ficticio', nombre_grupo: 'Grupo ficticio', nivel: 'Nivel 1', periodo: 'Periodo ficticio', fecha_ingreso: '2026-10-27', estado: 'activa', version: 1 };
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.ZDB_NAVEGADOR ? { executablePath: process.env.ZDB_NAVEGADOR } : {}) });
  let casos = 0;
  try {
    for (const ancho of [390, 768, 1366]) {
      for (const [rol, ruta, titulo] of [
        ['administrador', '/administracion/deportistas', 'Deportistas'],
        ['administrador', '/administracion/deportistas/ficticio', 'Ficha individual del deportista'],
        ['coordinador', '/coordinacion/inscripciones', 'Inscripciones e historial'],
        ['coordinador', '/coordinacion/propuestas', 'Propuestas y decisiones'],
        ['administrador', '/administracion/autorizaciones', 'Acudientes y autorizaciones'],
        ['profesor', '/profesor/deportistas', 'Deportistas'],
      ]) {
        console.log("Verificando", ruta, ancho);
        const context = await browser.newContext({ viewport: { width: ancho, height: 900 } });
        try {
          const page = await context.newPage(), errores = [];
          page.on('pageerror', (e) => { errores.push(e.message); console.error('Error JS:', e.message); });
          await context.route('**/api/**', async (route) => {
            assert.equal(route.request().method(), 'GET', 'Solo lectura en QA de navegación');
            const p = new URL(route.request().url()).pathname;
            if (!p.startsWith('/api/')) return route.continue();
            let datos = pagina([]);
            if (p.endsWith('/sesion/')) datos = { usuario: { id: 1, nombre: 'Cuenta ficticia', rol } };
            else if (p.endsWith('/deportistas/ficticio/')) datos = rol === 'profesor' ? { ...persona, fecha_nacimiento: undefined } : persona;
            else if (p.endsWith('/deportistas/')) datos = pagina([rol === 'profesor' ? { ...persona, fecha_nacimiento: undefined } : persona]);
            else if (p.endsWith('/inscripciones/') || p.endsWith('/trayectoria/')) datos = pagina([inscripcion]);
            else if (p.endsWith('/propuestas/')) datos = pagina([{ id: 1, tipo: 'nivel', justificacion: 'Propuesta ficticia', estado: 'pendiente', grupo_destino: 2, creado_por: 3, version: 1, nivel_anterior: 'Nivel 1', nivel_nuevo: 'Nivel 2' }]);
            else if (p.endsWith('/grupos/')) datos = pagina([{ id: 1, nombre: 'Grupo ficticio' }]);
            await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(datos) });
          });
          await page.goto(base + ruta);
          await page.getByRole('heading', { name: titulo, exact: true }).first().waitFor();
          if (ruta.endsWith('/deportistas') && rol !== 'profesor') {
            await page.getByRole('button', { name: 'Crear deportista', exact: true }).click();
            await page.getByRole('form', { name: 'Crear ficha de deportista' }).waitFor();
          }
          if (ruta.endsWith('/inscripciones')) {
            await page.getByRole('button', { name: 'Inscribir deportista', exact: true }).click();
            await page.getByRole('form', { name: 'Nueva inscripción' }).waitFor();
          }
          if (rol === 'profesor') assert.equal(await page.getByRole('button', { name: 'Crear deportista' }).count(), 0);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, ruta + ' a ' + ancho);
          assert.deepEqual(errores, []);
          casos++;
        } finally { await context.close(); }
      }
    }
    console.log('Fase 3: ' + casos + ' vistas/formularios responsivos aprobados. API ficticia; sin escrituras.');
  } finally { await browser.close(); }
})().catch((e) => { console.error(e.message); process.exitCode = 1; });
