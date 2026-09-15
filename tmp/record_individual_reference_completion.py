import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from src.core.artifacts import sha256_file,write_json_exclusive
from src.core.paths import REPOSITORY_ROOT as ROOT
from src.experiments.runs import _source_hash

parent=ROOT/'data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation'
batch=parent/'20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42'
qa=parent/'verification_20260908.json'
manifest=json.loads((batch/'manifest.json').read_text())
report=json.loads(qa.read_text())
assert manifest['status']=='complete' and report['status']=='passed'
assert sha256_file(batch/'manifest.json')==report['run_manifest_sha256']
assert sha256_file(qa)=='f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9'
assert _source_hash(ROOT)==manifest['source_hash']
assert subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()==''
sha=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=ROOT,text=True).strip()
assert sha=='6ffe6c5'
paths=[ROOT/'MAPA_TCC_DIDATICO.html',ROOT/'docs/projeto/mapa-tcc-didatico.html',
       ROOT/'docs/projeto/NAVEGACAO.md',ROOT/'AGENTS.md',ROOT/'monografia/cap_metodo/metodo.tex',
       ROOT/'data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/visual_review.json']
write_json_exclusive(ROOT/'data/derived/project_audits/general_20260908/individual_reference_completion_20260908.json',{
    'status':'completed_and_independently_verified','created_at':datetime.now(timezone.utc).isoformat(),
    'implementation_and_execution_commit':'33d191d','results_commit':sha,'git_dirty_at_completion':False,
    'scientific_source_unchanged_since_run':True,'source_hash':manifest['source_hash'],
    'run_manifest':str(batch/'manifest.json'),'run_manifest_sha256':sha256_file(batch/'manifest.json'),
    'verification':str(qa),'verification_sha256':sha256_file(qa),
    'automated_tests':{'passed':1026,'seconds':108.58,'profile':'not optional_ml and not slow',
                       'timing':'before_run'},
    'documentation_links_test':'passed_after_documentation_edits',
    'atlas_static_check':{'root_links':2,'atlas_links':183,'atlas_ids':31,'status':'passed'},
    'figure_static_visual_review':'passed','browser_visual_QA':False,'pdf_recompiled':False,
    'local_artifacts':[{'path':str(p.relative_to(ROOT)),'sha256':sha256_file(p)} for p in paths],
    'next':'causal_consumption_of_common_indices_and_dense_ADE_in_prediction_baselines',
    'test_or_folds_released':False,'predictor_evaluated':False})
print('Completion recorded; Git clean; scientific source and run provenance preserved.')
