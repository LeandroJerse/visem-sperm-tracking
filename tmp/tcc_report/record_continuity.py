from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess

root=Path(__file__).resolve().parents[2]
dest=root/'data/derived/project_audits/general_20260911/continuity_plan_20260911'
qa=root/'tmp/tcc_report/qa_20260911_continuidade'
def record(path):
    raw=path.read_bytes()
    return {'path':path.relative_to(root).as_posix(),'sha256':sha256(raw).hexdigest(),'bytes':len(raw)}
def git(*args):
    return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,encoding='utf-8').stdout.strip()
assert not git('status','--porcelain')
expected={'README.md','docs/metodologia/PROTOCOLO.md','docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md','docs/projeto/DIARIO.md'}
assert set(git('show','--pretty=','--name-only','HEAD').splitlines())==expected
static=json.loads((qa/'static_checks.json').read_text(encoding='utf-8'))
browser=json.loads((qa/'browser_checks.json').read_text(encoding='utf-8'))
assert static['status']==browser['status']=='passed'
for item in static['reports']+browser['hashes']:
    assert record(root/item['path'])['sha256']==item['sha256']
before=json.loads((dest/'before_manifest.json').read_text(encoding='utf-8'))
for item in before['files']:
    assert record(root/item['snapshot'])['sha256']==item['sha256']
review={'status':'passed','scope':'Manual visual inspection of report next-steps desktop/mobile and atlas desktop; browser geometry covers both documents at 1440 and 390 pixels.',
 'screenshots':[record(qa/name) for name in ['report_next_desktop.png','report_next_mobile.png','atlas_next_desktop.png']],
 'interactive_javascript':'unchanged versus preceding reviewed edition, verified in browser QA script',
 'scientific_figures':'five existing figures retained; no new figure or experiment'}
with (qa/'visual_review.json').open('x',encoding='utf-8') as stream: json.dump(review,stream,ensure_ascii=False,indent=2)
receipt={'status':'complete','scope':'Executive planning and navigation update only','date':'2026-09-11','created_at':datetime.now(timezone.utc).isoformat(),
 'documentary_commit':git('rev-parse','HEAD'),'git_clean':True,'new_scientific_runs':0,'new_model_installations':0,
 'latest_scientific_milestone':'8a, completed 2026-09-09','scientific_execution_commit':'6110c44526c30f8f8f7a2fdeb276f7169d2fcd88',
 'next_deliverable':'Prospective protocol and authenticated reader/executor for descriptive CV versus CV+flow ablation on 10848 existing training-prefix windows; cv_last secondary control.',
 'time_policy':'Researcher removed time as a permanent constraint on 2026-09-11. Prior 120-minute rule and failed projection preserved; new extraction requires its own resource/completeness plan.',
 'files':[record(root/p) for p in sorted(expected)]+[record(root/p) for p in ['AGENTS.md','docs/projeto/NAVEGACAO.md','docs/projeto/RELATORIO_COMPLETO_TCC.html','docs/projeto/mapa-tcc-didatico.html','RELATORIO_COMPLETO_TCC.html','MAPA_TCC_DIDATICO.html']],
 'before':record(dest/'before_manifest.json'),'static':record(qa/'static_checks.json'),'browser':record(qa/'browser_checks.json'),'visual':record(qa/'visual_review.json'),
 'independent_review':'Scientific priorities and flow-consumer feasibility reviewed independently; clarified targets through frame69, fixed secondary control before outcomes, no eliminating flow arm based on exploratory prefixes, constant-input recurrent control.',
 'hardware_read_only':{'gpu':'NVIDIA GeForce RTX 4070 Ti','reported_total_memory_mib':12282,'driver':'596.36','classic_venv_missing_distributions':['torch','torchvision','ultralytics'],'learned_inference_tested':False}}
with (dest/'completion.json').open('x',encoding='utf-8') as stream: json.dump(receipt,stream,ensure_ascii=False,indent=2)
print(json.dumps({'commit':receipt['documentary_commit'],'receipt':record(dest/'completion.json')},ensure_ascii=False))
