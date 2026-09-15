const {chromium}=require('C:/Users/leand/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'), {createHash}=require('node:crypto');
(async()=>{
 const dir=path.resolve('tmp/tcc_report/qa_20260911_classical_final'); fs.mkdirSync(dir,{recursive:true});
 const report=path.resolve('docs/projeto/RELATORIO_COMPLETO_TCC.html'), atlas=path.resolve('docs/projeto/mapa-tcc-didatico.html');
 const prior=path.resolve('data/derived/project_audits/general_20260911/classical_comparison_edition/before/docs/projeto/RELATORIO_COMPLETO_TCC.html');
 const js=raw=>raw.match(/<script>([\s\S]*?)<\/script>/)[1];
 assert.equal(js(fs.readFileSync(report,'utf8')),js(fs.readFileSync(prior,'utf8')));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--no-first-run','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(report).href);
 const meta=JSON.parse(await page.locator('#report-provenance').textContent());
 assert.equal(meta.scientific_state_date,'2026-09-11'); assert.equal(meta.classical_comparison.evaluations,24768);
 assert.equal(meta.report_is_new_experiment,false); assert.equal(meta.new_model_runs,0);
 assert.equal(await page.locator('main > section').count(),19); assert.equal(await page.locator('img').count(),6);
 assert.equal(await page.locator('#comparacao-classicos-20260911').count(),1);
 await page.screenshot({path:path.join(dir,'report_overview.png')});
 for(const [width,height,label] of [[1440,1000,'desktop'],[390,844,'mobile']]){
  await page.setViewportSize({width,height});
  for(const [selector,name] of [['#comparacao-classicos-20260911 table:nth-of-type(1)','comparison'],['#comparacao-classicos-20260911 figure','figure'],['#proximos','next']]){
   const locator=selector.includes('table:nth') ? page.locator('#comparacao-classicos-20260911 table').nth(1) : page.locator(selector);
   await locator.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'report overflow');
   await page.screenshot({path:path.join(dir,`report_${name}_${label}.png`)});
  }
 }

 const comparison=page.locator('#comparacao-classicos-20260911 table').nth(1);
 const scroll=await comparison.evaluate(el=>{el.scrollLeft=el.scrollWidth;return {left:el.scrollLeft,client:el.clientWidth,width:el.scrollWidth};});
 assert.ok(scroll.width>scroll.client && scroll.left>0,'mobile table horizontal scroll');
 await comparison.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
 await page.screenshot({path:path.join(dir,'report_comparison_mobile_right_columns.png')});
 await page.locator('#comparacao-classicos-20260911 details').first().evaluate(el=>el.open=true);
 const byVideo=page.locator('#comparacao-classicos-20260911 details').first();
 await byVideo.screenshot({path:path.join(dir,'report_by_video_mobile.png')});
 await page.goto(pathToFileURL(path.resolve('MAPA_TCC_DIDATICO.html')).href+'#comparacao-classicos-atual');
 await page.waitForURL(url=>url.hash==='#comparacao-classicos-atual'&&url.pathname.endsWith('/docs/projeto/mapa-tcc-didatico.html'));
 for(const [width,height,label] of [[1440,1000,'desktop'],[390,844,'mobile']]){
  await page.setViewportSize({width,height});
  await page.locator('#comparacao-classicos-atual').evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'atlas overflow');
  await page.locator('#comparacao-classicos-atual').screenshot({path:path.join(dir,`atlas_comparison_${label}.png`)});
 }
 await page.locator('#comparacao-classicos-atual a[href*="#comparacao-classicos-20260911"]').click();
 await page.waitForURL(url=>url.hash==='#comparacao-classicos-20260911');
 assert.equal(errors.length,0,JSON.stringify(errors));
 const hashes=[report,atlas].map(p=>({path:path.relative(process.cwd(),p).replaceAll('\\','/'),sha256:createHash('sha256').update(fs.readFileSync(p)).digest('hex')}));
 fs.writeFileSync(path.join(dir,'browser_checks.json'),JSON.stringify({status:'passed',hashes,checks:['unchanged interactive JavaScript','19 chapters and six figures','authenticated comparison provenance','desktop/mobile report and atlas without overflow','root redirect and atlas-to-report navigation'],console_errors:errors,visual_review:'pending'},null,2)+'\n');
 await browser.close(); console.log(JSON.stringify({status:'passed',hashes}));
})().catch(e=>{console.error(e);process.exit(1);});
