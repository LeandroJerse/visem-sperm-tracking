const {chromium}=require('C:/Users/leand/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'),{createHash}=require('node:crypto');
(async()=>{
 const dir=path.resolve('tmp/tcc_report/qa_20260911_continuidade');
 const report=path.resolve('docs/projeto/RELATORIO_COMPLETO_TCC.html'), atlas=path.resolve('docs/projeto/mapa-tcc-didatico.html');
 const prior=path.resolve('data/derived/project_audits/general_20260911/continuity_plan_20260911/before/docs/projeto/RELATORIO_COMPLETO_TCC.html');
 const script=raw=>raw.match(/<script>([\s\S]*?)<\/script>/)[1];
 assert.equal(script(fs.readFileSync(report,'utf8')),script(fs.readFileSync(prior,'utf8')));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--no-first-run','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(report).href);const meta=JSON.parse(await page.locator('#report-provenance').textContent());
 assert.equal(meta.planning_date,'2026-09-11');assert.equal(meta.scientific_state_date,'2026-09-09');assert.equal(meta.new_model_runs,0);
 assert.equal(await page.locator('main > section').count(),19);assert.equal(await page.locator('img').count(),5);
 assert.match(await page.locator('#proximos').innerText(),/alvos podem chegar ao quadro 69/);
 assert.match(await page.locator('#proximos').innerText(),/Ainda não foi executada/);
 await page.screenshot({path:path.join(dir,'report_overview.png')});
 for(const [width,height,label] of [[1440,1000,'desktop'],[390,844,'mobile']]){
  await page.setViewportSize({width,height});
  await page.locator('#proximos').evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:path.join(dir,`report_next_${label}.png`)});
 }
 await page.goto(pathToFileURL(path.resolve('MAPA_TCC_DIDATICO.html')).href+'#continuidade-20260911');
 await page.waitForURL(url=>url.hash==='#continuidade-20260911'&&url.pathname.endsWith('/docs/projeto/mapa-tcc-didatico.html'));
 for(const [width,height,label] of [[390,844,'mobile'],[1440,1000,'desktop']]){
  await page.setViewportSize({width,height});await page.locator('#continuidade-20260911').evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(dir,`atlas_next_${label}.png`)});
 }
 await page.locator('#continuidade-20260911 a[href$="#proximos"]').click();await page.waitForURL(url=>url.hash==='#proximos');
 assert.equal(errors.length,0,JSON.stringify(errors));
 const hashes=[report,atlas].map(p=>({path:path.relative(process.cwd(),p).replaceAll('\\','/'),sha256:createHash('sha256').update(fs.readFileSync(p)).digest('hex')}));
 fs.writeFileSync(path.join(dir,'browser_checks.json'),JSON.stringify({status:'passed',hashes,checks:['same interactive JavaScript as preceding reviewed edition','planning date separate from scientific state','19 chapters and five figures','unexecuted exploratory scope and future targets explicit','desktop/mobile report and atlas without document overflow','root atlas anchor redirect','atlas to report chapter link'],console_errors:errors,visual_review:'pending'},null,2)+'\n');
 await browser.close();console.log(JSON.stringify({status:'passed',hashes}));
})().catch(e=>{console.error(e);process.exit(1);});
