from pathlib import Path

parts = Path(__file__).resolve().parent
old = 'qa_20260911_classical_final_retry1'
new = 'qa_20260911_refinement'
(parts/new).mkdir(exist_ok=False)
browser = (parts/'qa_classical_final_retry1.cjs').read_text(encoding='utf-8')
browser = browser.replace(old,new).replace('classical_comparison_edition/before','classical_refinement_edition/before')
browser = browser.replace('classical_detection_training_comparison_v1','classical_refinement_and_yolo_dataset_v1')
browser = browser.replace("page.locator('img').count(),6", "page.locator('img').count(),7")
browser = browser.replace('comparacao-classicos-20260911','refinamento-classicos-20260911').replace('comparacao-classicos-atual','refinamento-classicos-atual')
browser = browser.replace('19 chapters and six figures','19 chapters and seven figures')
browser = browser.replace('authenticated comparison provenance','authenticated refinement and YOLO dataset provenance')
browser = browser.replace("assert.equal(meta.report_is_new_experiment,false);", """assert.equal(meta.latest_completed_milestone,'classical_refinement_and_yolo_dataset_v1');
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
 assert.equal(meta.report_is_new_experiment,false);""")
# The first details block in the new article is the per-video table.
with (parts/'qa_refinement.cjs').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(browser)
static = (parts/'check_report_classical_final_retry1.py').read_text(encoding='utf-8').replace(old,new)
static = static.replace("assert meta['documentation_only_expansion'] is False", "assert meta['documentation_only_expansion'] is False\n        assert meta['latest_completed_milestone'] == 'classical_refinement_and_yolo_dataset_v1'\n        assert len(meta['figures']) == 7")
with (parts/'check_report_refinement.py').open('x',encoding='utf-8',newline='\n') as stream:
    stream.write(static)
print('Prepared new static/browser QA; not executed before publication.')
