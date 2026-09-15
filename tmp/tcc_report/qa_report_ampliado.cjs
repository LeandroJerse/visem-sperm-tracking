const {chromium}=require('C:/Users/leand/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
(async()=>{
 const dir=path.resolve('tmp/tcc_report/qa_20260910_ampliado');fs.mkdirSync(dir,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--no-first-run','--disable-gpu']});
 const errors=[];const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 const file=path.resolve('docs/projeto/RELATORIO_COMPLETO_TCC.html');await page.goto(pathToFileURL(file).href);
 await page.evaluate(()=>document.querySelectorAll('img').forEach(img=>img.loading='eager'));
 await page.waitForFunction(()=>[...document.images].every(img=>img.complete&&img.naturalWidth>0));
 assert.ok(await page.evaluate(()=>[...document.images].every(img=>Number(img.getAttribute('width'))===img.naturalWidth&&Number(img.getAttribute('height'))===img.naturalHeight)));
 const structure=await page.evaluate(()=>({title:document.title,chapters:document.querySelectorAll('main > section').length,details:document.querySelectorAll('main details').length,figures:document.images.length,ids:[...document.querySelectorAll('[id]')].map(n=>n.id),pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,sideWidth:document.querySelector('.sidebar').getBoundingClientRect().width}));
 assert.equal(structure.chapters,19);assert.equal(new Set(structure.ids).size,structure.ids.length);assert.equal(structure.figures,5);assert.ok(structure.pageWidth<=structure.viewport+1);
 await page.screenshot({path:path.join(dir,'desktop_abertura.png'),animations:'disabled'});
 await page.locator('#lab-tp').fill('80');await page.locator('#lab-fp').fill('20');await page.locator('#lab-fn').fill('10');
 assert.match(await page.locator('#lab-prf').innerText(),/0,8421/);
 await page.locator('#lab-tp').fill('0');await page.locator('#lab-fp').fill('0');await page.locator('#lab-fn').fill('0');assert.match(await page.locator('#lab-prf').innerText(),/Sem evidência/);
 await page.locator('#lab-tp').fill('80');await page.locator('#lab-fp').fill('20');await page.locator('#lab-fn').fill('10');
 await page.locator('#lab-errors').selectOption('growing');assert.match(await page.locator('#lab-ade').innerText(),/5,5000/);
 await page.locator('#lab-errors').selectOption('early');assert.match(await page.locator('#lab-ade').innerText(),/FDE10 = 0,0000/);
 await page.locator('#lab-errors').selectOption('late');assert.match(await page.locator('#lab-ade').innerText(),/ADE10 = 10\/10 = 1,0000/);assert.match(await page.locator('#lab-ade').innerText(),/FDE10 = 10,0000/);
 await page.locator('#lab-h').fill('5');assert.match(await page.locator('#lab-ade').innerText(),/ADE5 = 0\/5 = 0,0000/);
 await page.locator('#lab-h').fill('10');await page.locator('#lab-errors').selectOption('growing');
 assert.equal(await page.locator('.table-scroll .table-scroll').count(),0);
 const meta=await page.locator('#report-provenance').textContent().then(JSON.parse);
 assert.equal(meta.edition_date,'2026-09-10');assert.equal(meta.scientific_state_date,'2026-09-09');assert.equal(meta.new_model_runs,0);
 for(const t of [29,19,59]){
  await page.locator('#lab-origin').fill(String(t));
  const output=await page.locator('#lab-causal-output').innerText();
  assert.ok(output.includes(`Histórico: ${t-19}..${t} (20 posições)`));
  assert.ok(output.includes(`Último par permitido: ${t-1}→${t}`));
  assert.ok(output.includes(`par futuro proibido na entrada: ${t}→${t+1}`));
  assert.equal(await page.locator('#lab-causal-chart rect').count(),30);
 }
 await page.locator('#lab-origin').fill('29');
 assert.match(await page.locator('#lab-bilinear-output').innerText(),/\(1,000; 1,000\)/);
 await page.locator('#lab-invalid-corner').check();assert.match(await page.locator('#lab-bilinear-output').innerText(),/Amostra inválida/);
 await page.locator('#lab-alpha').fill('0');assert.match(await page.locator('#lab-bilinear-output').innerText(),/\(0,000; 1,000\)/);assert.match(await page.locator('#lab-bilinear-output').innerText(),/peso zero/);
 await page.locator('#lab-alpha').fill('1');await page.locator('#lab-beta').fill('0');assert.match(await page.locator('#lab-bilinear-output').innerText(),/\(4,000; 0,000\)/);
 await page.locator('#lab-beta').fill('1');assert.match(await page.locator('#lab-bilinear-output').innerText(),/Amostra inválida/);
 await page.locator('#lab-invalid-corner').uncheck();assert.match(await page.locator('#lab-bilinear-output').innerText(),/\(4,000; 2,000\)/);
 await page.locator('#lab-alpha').fill('0.25');await page.locator('#lab-beta').fill('0.5');
 for(const [selector,name] of [['#lab-causalidade','causalidade'],['#lab-bilinear','bilinear']]){
  await page.locator(selector).screenshot({path:path.join(dir,`${name}_desktop.png`),animations:'disabled'});
 }
 for(const id of ['guia-leitura','algoritmos-detalhados','exemplo-completo','ler-artefatos']){
  await page.locator(`#${id} > h2`).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,`${id}_desktop.png`),animations:'disabled'});
 }
 await page.locator('#laboratorio').screenshot({path:path.join(dir,'laboratorio.png'),animations:'disabled'});
 await page.locator('#metricas-tracking').screenshot({path:path.join(dir,'metricas_tracking.png'),animations:'disabled'});
 await page.locator('#search').fill('hipotese');await page.locator('#search').press('Enter');assert.ok(await page.locator('#search-results li').count()>0);await page.locator('#search').press('Escape');assert.ok(await page.locator('#search-results').isHidden());
 await page.locator('#expand').click();assert.equal(await page.locator('main details:not([open])').count(),0);await page.locator('#collapse').click();assert.equal(await page.locator('main details[open]').count(),0);
 await page.locator('#font-size').click();assert.match(await page.locator('body').getAttribute('class'),/large-text/);await page.locator('#font-size').click();
 const link=page.locator('#toc a[href="#pastas"]');await link.click();await page.waitForTimeout(250);assert.ok(new URL(page.url()).hash.includes('pastas'));
 await page.locator('#pastas > h2').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'pastas_desktop.png'),animations:'disabled'});
 await page.locator('#pastas-inventario-src').evaluate(el=>{for(let n=el;n;n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;});
 await page.locator('#pastas-inventario-src').scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('#toc a.active')?.getAttribute('href')==='#pastas');
 await page.screenshot({path:path.join(dir,'inventario_codigo.png'),animations:'disabled'});
 await page.locator('#collapse').click();
 await page.locator('#pipeline .pipeline').screenshot({path:path.join(dir,'pipeline.png'),animations:'disabled'});
 await page.locator('#resultados figure').last().screenshot({path:path.join(dir,'resultados_fluxo_compacto.png'),animations:'disabled'});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(dir,'mobile_abertura.png'),animations:'disabled'});
 const mobile=await page.evaluate(()=>({pageWidth:document.documentElement.scrollWidth,viewport:innerWidth}));assert.ok(mobile.pageWidth<=mobile.viewport+1,JSON.stringify(mobile));
 await page.locator('#menu').click();assert.equal(await page.locator('#menu').getAttribute('aria-expanded'),'true');await page.locator('#menu').click();
 await page.locator('#laboratorio').screenshot({path:path.join(dir,'mobile_laboratorio.png'),animations:'disabled'});
 for(const id of ['guia-leitura','algoritmos-detalhados','exemplo-completo','ler-artefatos','lab-causalidade','lab-bilinear']){
  await page.locator(`#${id}`).scrollIntoViewIfNeeded();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),id);
  if(id.startsWith('lab-'))await page.locator(`#${id}`).screenshot({path:path.join(dir,`${id}_mobile.png`),animations:'disabled'});
  else await page.screenshot({path:path.join(dir,`${id}_mobile.png`),animations:'disabled'});
 }
 await page.setViewportSize({width:900,height:1100});await page.emulateMedia({media:'print'});await page.evaluate(()=>dispatchEvent(new Event('beforeprint')));assert.equal(await page.locator('main details:not([open])').count(),0);await page.locator('#metricas-guia').scrollIntoViewIfNeeded();await page.locator('#metricas-confusao').screenshot({path:path.join(dir,'impressao_metricas.png'),animations:'disabled'});
 await page.evaluate(()=>dispatchEvent(new Event('afterprint')));await page.emulateMedia({media:'screen'});assert.equal(await page.locator('main details[open]').count(),0);
 await page.goto(pathToFileURL(path.resolve('RELATORIO_COMPLETO_TCC.html')).href+'#resultados');await page.waitForURL(url=>url.pathname.endsWith('/docs/projeto/RELATORIO_COMPLETO_TCC.html')&&url.hash==='#resultados');
 const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:1440,height:1000}});const plain=await nojs.newPage();await plain.goto(pathToFileURL(file).href);assert.ok(await plain.locator('main').isVisible());assert.equal(await plain.locator('main > section').count(),19);await nojs.close();
 assert.equal(errors.length,0,JSON.stringify(errors));
 fs.writeFileSync(path.join(dir,'browser_checks.json'),JSON.stringify({status:'passed',browser:await browser.version(),runtime:'headless Edge via Playwright, local file URL',structure,mobile,checks:['local load and embedded figures','no duplicate IDs','no desktop/mobile document overflow','F1 interactive normal and zero cases','ADE/FDE dense presets and horizon change','accent-insensitive search and clear','details expand/collapse','text size toggle','internal links','mobile menu','print stylesheet and restoration of details','root redirect preserves anchor','text readable without JavaScript'],console_errors:errors,pdf_generated:false,visual_review:'pending_model_inspection'},null,2)+'\n');
 await browser.close();console.log(JSON.stringify({status:'passed',output:dir,structure,mobile}));
})().catch(e=>{console.error(e);process.exit(1);});
