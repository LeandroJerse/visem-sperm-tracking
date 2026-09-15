"""Close the documentary milestone without modifying any scientific run."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

root=Path(__file__).resolve().parents[2]
audit=root/'data/derived/project_audits/general_20260911/classical_comparison_edition'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def record(path):
    p=root/path
    return {'path':path,'sha256':sha(p),'bytes':p.stat().st_size}
def read(path): return json.loads((root/path).read_text(encoding='utf-8'))
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert commit=='27bec7abfd245a13798b64742e01770443405243'
status=subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
assert not status,status
result=read('data/derived/detection/comparison_reports/classical_v1_20260911/summary.json')
assert sha(root/result['source_manifest'])==result['source_manifest_sha256']
assert sha(root/result['verification'])==result['verification_sha256']
qa=read(result['verification'])
assert qa['status']=='passed'
presentation='tmp/tcc_report/qa_20260911_classical_final_retry1/'
visual=read(presentation+'visual_review.json')
assert visual['status']=='passed'
for row in visual['report_hashes']:
    assert sha(root/row['path'])==row['sha256']
for name in ('AGENTS.md','docs/projeto/NAVEGACAO.md'):
    path=root/name
    text=path.read_text(encoding='utf-8')
    header='## Continuidade vigente — comparação clássica conferida em 11/09/2026\n'
    assert header in text
    text=text.replace(header,header+'\nResultados científicos documentados em `27bec7a`, com Git limpo ao concluir.\nEsse commit documental não muda a proveniência da busca/smoke em `2547109`.\nRegistro local desta entrega em\n`data/derived/project_audits/general_20260911/classical_comparison_edition/completion.json`.\n',1)
    path.write_text(text,encoding='utf-8',newline='\n')

paths=['docs/projeto/RELATORIO_COMPLETO_TCC.html','docs/projeto/mapa-tcc-didatico.html',
       'RELATORIO_COMPLETO_TCC.html','MAPA_TCC_DIDATICO.html','AGENTS.md','docs/projeto/NAVEGACAO.md',
       'data/derived/detection/comparison_reports/classical_v1_20260911/summary.json',
       'data/derived/detection/comparison_reports/classical_v1_20260911/visual_review.json',
       presentation+'static_checks.json',presentation+'browser_checks.json',presentation+'visual_review.json',
       'monografia/cap_metodo/metodo.tex','monografia/cap_conclusao/conclusao.tex']
helpers=['build_report.py','classical_results_artifacts.py','classical_comparison_template.html',
         'publish_classical_edition.py','classical_status_corrections.py','document_classical_completion.py',
         'qa_classical_final_retry1.cjs','check_report_classical_final_retry1.py']
receipt={'status':'complete','completed_at':datetime.now(timezone.utc).isoformat(),
         'completed_scope':'classical_detection_training_screening_and_documentation',
         'scientific_run_commit':result['run_commit'],'documentation_commit':commit,'git_dirty_at_close':False,
         'scientific_manifest':record(result['source_manifest']),'scientific_qa':record(result['verification']),
         'evaluations':24768,'candidates':43,'families':6,'frames_per_candidate':576,
         'selection':'two parents per searched family plus fixed T218; no final pipeline choice',
         'best_per_family':[{k:v for k,v in row.items() if k in ('family','configuration_id','f1')} for row in result['best_per_family']],
         'qa':result['qa_counts'],'report':{'chapters':19,'figures':6,'labs':4,'words_approx':41160,'generation_runs_models':False},
         'checks':{'scientific_code_tests_before_v2':{'producer_passed':89,'independent_verifier_passed':76},
                   'documentation_links':'1 passed in 6.02 s','browser_and_visual':'passed; initial viewport-scope and wrapper-test issues preserved'},
         'files':[record(p) for p in paths],
         'editing_helpers':[record('tmp/tcc_report/'+p) for p in helpers],
         'monografia_audit_files':[record(p.relative_to(root).as_posix()) for p in sorted((audit/'before_monografia').glob('*.json'))],
         'unchanged_scientific_frontiers':['T218 development-only freeze','ground-truth prediction reference and baselines','causal Farneback smoke and compact benchmark'],
         'pending':['prospectively defined local refinement under a new plan and executor','full validation of new classical finalists','temporal MOG2/KNN comparison','authenticated YOLO dataset, recipe and training','official tracking evaluation and detector-tracker comparison','prediction on estimated trajectories and causal flow ablation'],
         'no_final_promotion':True,'hypothesis_tested':False,'test_and_folds_opened':False,
         'local_only':['HTML reports and atlas','navigation guide and instructions','monografia','scientific runs and presentation artifacts'],
         'pushed_to_remote':False}
with (audit/'completion.json').open('x',encoding='utf-8') as stream:
    json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({'status':'complete','path':str(audit/'completion.json'),'documentation_commit':commit,'scientific_run_commit':result['run_commit']},ensure_ascii=False))
