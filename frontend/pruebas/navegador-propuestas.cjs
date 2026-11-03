// Verificación aislada de propuestas; todas las APIs son simuladas, sin PostgreSQL.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.ZDB_PLAYWRIGHT || 'playwright');
const base = process.env.ZDB_FRONTEND_URL || 'http://127.0.0.1:5176';
const pagina = (results) => ({ results, count: results.length, next: null });
const destino = { id:7,codigo:'ESC-N1-DOM',nombre:'Escalada domingo',nivel_nombre:'Nivel 1',jornada:'Domingo',periodo_nombre:'Ciclo ficticio',
  fecha_inicio_periodo:'2026-10-01',fecha_fin_periodo:'2026-12-31',horarios:[{dia:6,hora_inicio:'09:00',hora_fin:'10:00'}],disponibilidad:{disponibles:2,desde:'2026-10-29',hasta:'2026-12-31'} };
(async () => {
  const browser = await chromium.launch({headless:true,...(process.env.ZDB_NAVEGADOR ? {executablePath:process.env.ZDB_NAVEGADOR} : {})});
  let casos=0;
  try {
    for (const width of [390,768,1366]) for (const rol of ['profesor','coordinador','administrador']) {
      const context=await browser.newContext({viewport:{width,height:950}});
      try {
        const page=await context.newPage(),errores=[],posts=[],rutas=[];
        page.on('pageerror',(e)=>errores.push(e.message));
        await context.route('**/api/**',async(route)=>{
          const u=new URL(route.request().url()),p=u.pathname;
          if(!p.startsWith('/api/')) return route.continue();
          rutas.push(p);let datos=pagina([]),status=200;
          if(p.endsWith('/sesion/')) datos={usuario:{id:1,nombre:'Cuenta ficticia',rol}};
          else if(p.endsWith('/csrf/')) datos={csrfToken:'ficticio'};
          else if(p.endsWith('/deportistas/')) datos=pagina([{id:1,nombres:'Persona',apellidos:'Ficticia',documento_presentacion:'TI ****1234'}]);
          else if(p.endsWith('/inscripciones/')) datos=pagina([{id:11,nombre_grupo:'Origen entre semana',nivel:'Nivel 1',periodo:'Ciclo ficticio'}]);
          else if(p.endsWith('/propuestas/destinos/')) datos=pagina([destino]);
          else if(p.endsWith('/propuestas/') && route.request().method()==='POST') {
            posts.push({p,datos:route.request().postDataJSON()});datos={id:6};status=201;
          } else if(p.endsWith('/propuestas/')) datos=pagina([{id:5,tipo:'nivel',estado:'pendiente',grupo_destino:8,codigo_destino:'ESC-N2-DOM',nombre_destino:'Nivel 2 domingo',nivel_anterior:'Nivel 1',nivel_nuevo:'Nivel 2',creado_por:1,version:1,justificacion:'Revisión ficticia'}]);
          await route.fulfill({status,contentType:'application/json',body:JSON.stringify(datos)});
        });
        const prefijo={profesor:'/profesor',coordinador:'/coordinacion',administrador:'/administracion'}[rol];
        await page.goto(base+prefijo+'/propuestas');
        await page.getByRole('heading',{name:'Propuestas y decisiones',exact:true}).waitFor();
        if(rol==='profesor') {
          await page.getByRole('button',{name:'Crear propuesta'}).click();
          await page.getByLabel('Tipo de propuesta',{exact:true}).selectOption('traslado');
          await page.locator('select option').filter({hasText:'TI ****1234'}).waitFor({state:'attached'});
          await page.getByLabel('Deportista de mis grupos',{exact:true}).selectOption('1');
          await page.locator('select option').filter({hasText:'Origen entre semana'}).waitFor({state:'attached'});
          await page.getByLabel('Inscripción de origen',{exact:true}).selectOption('11');
          await page.locator('select option').filter({hasText:'ESC-N1-DOM'}).waitFor({state:'attached'});
          await page.getByLabel('Grupo destino autorizado',{exact:true}).selectOption('7');
          assert.match(await page.getByRole('region',{name:'Información mínima del destino'}).innerText(),/Domingo: 09:00 a 10:00/);
          const rects=await page.locator('.selector-catalogo').evaluateAll((els)=>els.map((e)=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,max:document.documentElement.clientWidth};}));
          for(const r of rects) assert.ok(r.left>=0 && r.right<=r.max+1,'Selector dentro del viewport');
          await page.getByLabel('Justificación de la propuesta',{exact:true}).fill('Cambio de jornada ficticio');
          page.once('dialog',(d)=>d.accept());
          await page.getByRole('button',{name:'Guardar cambios',exact:true}).click();
          await page.getByText('Propuesta registrada sin modificar inscripciones.').waitFor();
          assert.equal(posts.length,1);assert.equal(posts[0].datos.grupo_destino,7);assert.equal(posts[0].datos.inscripcion_origen,11);
          assert.ok(!rutas.some((p)=>p.startsWith('/api/organizacion/grupos/')));
          assert.equal(await page.getByRole('button',{name:'aprobar propuesta 5'}).count(),0);
        } else {
          await page.getByText('Revisión ficticia',{exact:false}).waitFor();
          assert.equal(await page.getByRole('button',{name:'aprobar propuesta 5'}).count(),rol==='coordinador'?1:0);
          assert.equal(await page.getByRole('button',{name:'Crear propuesta'}).count(),0);
          assert.equal(posts.length,0);
        }
        assert.deepEqual(errores,[]);casos++;
      } finally {await context.close();}
    }
    process.stdout.write('Propuestas: '+casos+' recorridos aprobados, tres roles y tres anchos; APIs simuladas.\n');
  } finally {await browser.close();}
})().catch((e)=>{console.error(e.message);process.exitCode=1;});
