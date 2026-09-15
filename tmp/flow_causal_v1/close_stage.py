from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE='data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/'
RUN=BASE+'20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/'
OUT=ROOT/'data/derived/project_audits/general_20260909/causal_flow_level7_completion_20260909'
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def ref(p): return {'path':p,'sha256':sha(p),'bytes':(ROOT/p).stat().st_size}
def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert commit=='581f15c62b6f345b0a5e5b72bc89c1c337eeb319'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
for p in ['AGENTS.md','docs/projeto/NAVEGACAO.md']:
 path=ROOT/p;s=path.read_text(encoding='utf-8');mark='Registro atual: **nível 7 concluído e conferido — 09/09/2026**.'
 assert mark in s
 s=s.replace(mark,mark+'\nResultados documentados em `581f15c62b6f345b0a5e5b72bc89c1c337eeb319`,\ncom Git limpo ao concluir. Esse commit documental não altera a proveniência\nda run em `16eecbb` nem a correção do verificador em `0fccda8`.',1)
 path.write_text(s,encoding='utf-8',newline='\n')
manifest=read(RUN+'manifest.json');qa=read(BASE+'verification_20260909_retry1.json')
assert sha(RUN+'manifest.json')=='fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98'
assert sha(BASE+'verification_20260909_retry1.json')=='b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652'
assert manifest['status']=='complete' and qa['status']=='passed'
assert len(manifest['artifacts'])==97
qa_browser=read('tmp/tcc_report/qa_20260909/final_targeted_checks.json')
for r in qa_browser['hashes']:assert sha(r['path'])==r['sha256']
assert qa_browser['status']=='passed'
receipt={
 'schema':'causal_flow_level7_completion_v1','status':'complete','completed_at':datetime.now(timezone.utc).isoformat(),
 'level':7,'scientific_execution_commit':'16eecbb32b3edb4b4908ced344367670132a4cc1',
 'verifier_schema_fix_commit':'0fccda8f663dc64a9ebc815b8cbaa60d5146fde1','results_documentation_commit':commit,'git_clean_at_completion':True,
 'run_manifest':ref(RUN+'manifest.json'),'independent_verification':ref(BASE+'verification_20260909_retry1.json'),
 'first_failed_verification_preserved':ref(BASE+'verification_20260909.json'),
 'canonical_plan_hash':qa['plan_hash'],'execution_source_hash':manifest['source_hash'],
 'scientific_summary':manifest['summary'],'resources':manifest['resources'],'elapsed_seconds':manifest['elapsed_seconds'],
 'qa_counts':{k:qa[k] for k in ['files_verified','comparisons','numeric_comparisons','coordinate_comparisons','max_absolute_difference','elapsed_seconds','pair_pixels_diagnosed','temporal_pixels_diagnosed','directional_field_pixels_validated']},
 'tests':{'selected_full_suite_before_pixels':{'selector':'not optional_ml and not slow','passed':1495,'seconds':160.71},'verifier_self_test_groups_before_pixels':12,'schema_fix_targeted_regressions':{'passed':9,'seconds':4.32},'documentation_links_final':{'passed':1,'seconds':0.78},'full_suite_repeated_after_documentation':False},
 'local_documents':[ref(p) for p in ['docs/projeto/RELATORIO_COMPLETO_TCC.html','RELATORIO_COMPLETO_TCC.html','docs/projeto/mapa-tcc-didatico.html','MAPA_TCC_DIDATICO.html','docs/projeto/NAVEGACAO.md','AGENTS.md','monografia/cap_metodo/metodo.tex']],
 'figure_artifacts':[ref('data/derived/flow/reports/farneback_causal_smoke_v1_20260909/'+n) for n in ['smoke_fluxo_causal.png','smoke_fluxo_causal.svg','provenance.json','visual_review.json']],
 'html_qa':{'status':'passed','report_chapters':15,'report_figures':4,'canonical_report_local_links':883,'desktop_mobile_and_interactions_passed':True,'atlas_mobile_overflow_found_and_fixed':True,'visual_review':'passed_representative_pages','evidence_files':[ref(str(p.relative_to(ROOT)).replace('\\','/')) for p in OUT.iterdir() if p.is_file() and p.name!='completion.json']},
 'preserved_previous_report':ref('data/derived/project_audits/general_20260908/relatorio_completo_tcc_20260908/RELATORIO_COMPLETO_TCC_20260908.html'),
 'limits':{'hypothesis_tested':False,'predictors_executed_in_level7':False,'farneback_selected_or_promoted':False,'raw_validation_test_read':False,'raw_training_labels_reread':False,'reference_or_baselines_reexecuted':False,'gray_decode_and_estimator_independently_reexecuted_by_verifier':False,'reported_flow_is_physical_fluid_velocity':False,'monograph_pdf_recompiled':False,'html_and_local_guides_committed':False},
 'next_milestone':'Register resource benchmark and storage/audit policy before extending causal features in training; adapt legacy flow-aware CV to dense float64 causal inputs and a predeclared common cohort for descriptive paired ablation. Keep learned comparisons and tracking/HOTA under their own protocols.',
}
(OUT/'completion.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
print(json.dumps({'status':'complete','documentation_commit':commit,'git_clean':True,'completion':str(OUT/'completion.json'),'run_and_qa_hashes_preserved':True},ensure_ascii=False))
