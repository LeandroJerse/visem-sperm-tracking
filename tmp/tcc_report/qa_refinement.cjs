const {chromium}=require('C:/Users/leand/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url'), {createHash}=require('node:crypto');
(async()=>{
 const dir=path.resolve('tmp/tcc_report/qa_20260911_refinement'); fs.mkdirSync(dir,{recursive:true});
 const report=path.resolve('docs/projeto/RELATORIO_COMPLETO_TCC.html'), atlas=path.resolve('docs/projeto/mapa-tcc-didatico.html');
 const prior=path.resolve('data/derived/project_audits/general_20260911/classical_refinement_edition/before/docs/projeto/RELATORIO_COMPLETO_TCC.html');
 const js=raw=>raw.match(/<script>([\s\S]*?)<\/script>/)[1];
 assert.equal(js(fs.readFileSync(report,'utf8')),js(fs.readFileSync(prior,'utf8')));
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',args:['--no-first-run','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(report).href);
 const meta=JSON.parse(await page.locator('#report-provenance').textContent());
 assert.equal(meta.scientific_state_date,'2026-09-11'); assert.equal(meta.classical_comparison.evaluations,24768);
 assert.equal(meta.latest_completed_milestone,'classical_refinement_and_yolo_dataset_v1');
 assert.equal(meta.classical_refinement.evaluations,25920);
 assert.equal(meta.yolo_dataset.images,23316); assert.equal(meta.yolo_dataset.trained,false);
 for(const record of [meta.classical_refinement,meta.yolo_dataset]){
  const bytes=fs.readFileSync(path.resolve(record.manifest)), qaBytes=fs.readFileSync(path.resolve(record.verification));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),record.manifest_sha256);
  assert.equal(createHash('sha256').update(qaBytes).digest('hex'),record.verification_sha256);
  const manifest=JSON.parse(bytes), verification=JSON.parse(qaBytes);
  assert.equal(manifest.status,'complete'); assert.equal(manifest.git_dirty,false);
  assert.equal(verification.status,'passed'); assert.equal(verification.manifest_sha256,record.manifest_sha256);
 }
 assert.equal(meta.report_is_new_experiment,false); assert.equal(meta.new_model_runs,0);
 assert.equal(await page.locator('main > section').count(),19); assert.equal(await page.locator('img').count(),7);
 assert.equal(await page.locator('#refinamento-classicos-20260911').count(),1);
 await page.screenshot({path:path.join(dir,'report_overview.png')});
 for(const [width,height,label] of [[1440,1000,'desktop'],[390,844,'mobile']]){
  await page.setViewportSize({width,height});
  for(const [selector,name] of [['#refinamento-classicos-20260911 table:nth-of-type(1)','comparison'],['#refinamento-classicos-20260911 figure','figure'],['#proximos','next']]){
   const locator=selector.includes('table:nth') ? page.locator('#refinamento-classicos-20260911 table').nth(1) : page.locator(selector);
   await locator.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'report overflow');
   await page.screenshot({path:path.join(dir,`report_${name}_${label}.png`)});
  }
 }

 const comparison=page.locator('#refinamento-classicos-20260911 table').nth(1);
 const scroll=await comparison.evaluate(el=>{const container=el.closest(".table-scroll");container.scrollLeft=container.scrollWidth;return {left:container.scrollLeft,client:container.clientWidth,width:container.scrollWidth};});
 assert.ok(scroll.width>scroll.client && scroll.left>0,'mobile table horizontal scroll');
 await comparison.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
 await page.screenshot({path:path.join(dir,'report_comparison_mobile_right_columns.png')});
 await page.locator('#refinamento-classicos-20260911 details').first().evaluate(el=>el.open=true);
 const byVideo=page.locator('#refinamento-classicos-20260911 details').first();
 await byVideo.screenshot({path:path.join(dir,'report_by_video_mobile.png')});
 await page.goto(pathToFileURL(path.resolve('MAPA_TCC_DIDATICO.html')).href+'#refinamento-classicos-atual');
 await page.waitForURL(url=>url.hash==='#refinamento-classicos-atual'&&url.pathname.endsWith('/docs/projeto/mapa-tcc-didatico.html'));
 for(const [width,height,label] of [[1440,1000,'desktop'],[390,844,'mobile']]){
  await page.setViewportSize({width,height});
  await page.locator('#refinamento-classicos-atual').evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'atlas overflow');
  await page.locator('#refinamento-classicos-atual').screenshot({path:path.join(dir,`atlas_comparison_${label}.png`)});
 }
 await page.locator('#refinamento-classicos-atual a[href*="#refinamento-classicos-20260911"]').click();
 await page.waitForURL(url=>url.hash==='#refinamento-classicos-20260911');
 assert.equal(errors.length,0,JSON.stringify(errors));
 const hashes=[report,atlas].map(p=>({path:path.relative(process.cwd(),p).replaceAll('\\','/'),sha256:createHash('sha256').update(fs.readFileSync(p)).digest('hex')}));
 fs.writeFileSync(path.join(dir,'browser_checks.json'),JSON.stringify({status:'passed',hashes,checks:['unchanged interactive JavaScript','19 chapters and seven figures','authenticated refinement and YOLO dataset provenance','desktop/mobile report and atlas without overflow','root redirect and atlas-to-report navigation'],console_errors:errors,visual_review:'pending'},null,2)+'\n');
 await browser.close(); console.log(JSON.stringify({status:'passed',hashes}));
})().catch(e=>{console.error(e);process.exit(1);});
