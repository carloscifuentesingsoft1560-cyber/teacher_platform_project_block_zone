// QA de la ampliación con API ficticia. No crea cuentas ni escribe en PostgreSQL.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const pagina = (results) => ({ results, count: results.length, next: null });
const docente = { id: 22, username: 'demo_docente', nombre: 'Docente ficticio', first_name: 'Docente', rol: 'profesor', is_active: true, grupos: [] };
const titular = { id: 20, nombre: 'Coordinador ficticio', rol: 'coordinador' };
const resumen = {
  fecha_corte: '2026-10-28', filtros: { periodo: null, disciplina: null, nivel: null },
  profesores: { activos: 1, inactivos: 0, sin_grupo: 1 },
  grupos: { activos: 1, inactivos: 0 }, periodos: { total: 1, activos: 1, en_curso: 1 },
  asignaciones: { vigentes: 0, operativas: 0 },
  coordinacion: { estado: 'activo', cantidad_activos: 1, actual: titular },
  disciplinas: [{ id: 1, nombre: 'Escalada', total: 1, activos: 1 }],
  niveles: [{ id: 1, nombre: 'Nivel 1', total: 1, activos: 1 }],
};
(async () => {
  const browser = await chromium.launch({ headless: true, timeout: 20000, ...(process.env.ZDB_NAVEGADOR ? { executablePath: process.env.ZDB_NAVEGADOR } : {}) });
  let casos = 0;
  try {
    for (const ancho of [390, 768, 1366]) {
      for (const [rol, ruta, tipo] of [
        ['administrador', '/administracion', 'tablero'],
        ['coordinador', '/coordinacion', 'tablero'],
        ['coordinador', '/coordinacion/asignaciones', 'asignaciones'],
        ['administrador', '/administracion/coordinacion', 'cargo'],
      ]) {
        const contexto = await browser.newContext({ viewport: { width: ancho, height: 900 } });
        const page = await contexto.newPage(); const errores = [];
        page.on('pageerror', (error) => errores.push(error.message));
        await contexto.route('**/api/**', async (route) => {
          const camino = new URL(route.request().url()).pathname;
          if (!camino.startsWith('/api/')) return route.continue();
          assert.equal(route.request().method(), 'GET', 'QA visual sin escrituras');
          let datos = pagina([]);
          if (camino.endsWith('/sesion/')) datos = { usuario: { id: 1, nombre: 'Cuenta ficticia', rol } };
          else if (camino.endsWith('/resumen/')) datos = resumen;
          else if (camino.includes('/paneles/')) datos = { nombre: 'Cuenta ficticia', rol, mensaje: 'Organización disponible' };
          else if (camino.endsWith('/coordinacion/')) datos = { ...pagina([]), actual: titular };
          else if (camino.endsWith('/usuarios/') || camino.endsWith('/profesores/')) datos = pagina([docente]);
          else if (camino.endsWith('/disciplinas/')) datos = pagina([{ id: 1, nombre: 'Escalada' }]);
          else if (camino.endsWith('/niveles/')) datos = pagina([{ id: 1, nombre: 'Nivel 1', disciplina: 1 }]);
          else if (camino.endsWith('/periodos/')) datos = pagina([{ id: 1, nombre: 'Ciclo ficticio' }]);
          else if (camino.endsWith('/grupos/')) datos = pagina([{ id: 1, codigo: 'demo', nombre: 'Grupo ficticio', activo: true }]);
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(datos) });
        });
        await page.goto(base + ruta);
        if (tipo === 'tablero') await page.getByRole('heading', { name: 'Profesores activos', exact: true }).waitFor();
        if (tipo === 'asignaciones') {
          await page.getByRole('button', { name: 'Crear asignación', exact: true }).click();
          await page.getByRole('form', { name: 'Formulario de asignación' }).waitFor();
        }
        if (tipo === 'cargo') await page.getByRole('button', { name: 'Confirmar relevo', exact: true }).waitFor();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, tipo + ' a ' + ancho + 'px');
        assert.deepEqual(errores, []);
        casos++;
        await contexto.close();
      }
    }
    console.log('Ampliación: ' + casos + ' vistas en navegador aprobadas, sin errores JS ni desbordamiento. API ficticia, sin escrituras.');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.message); process.exitCode = 1; });
