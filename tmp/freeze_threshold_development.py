"""One-time metadata-only materialization of the completed validation decision."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import yaml
from src.core.artifacts import sha256_file, write_json_exclusive
from src.core.paths import REPOSITORY_ROOT as ROOT
from src.experiments.config import config_hash
from src.experiments.detection_validation import load_validation_plan

parent = ROOT / 'data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation'
batch = parent / '20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42'
qa_path = parent / 'verification_20260908_retry2.json'
attempts = parent / 'verification_attempts_20260908.json'
assert sha256_file(batch/'manifest.json') == 'ce0a391b792b8a8081f1ea41aaa7678fcae4973c48cc6a5ce159a27147b3cd55'
assert sha256_file(qa_path) == '9f6b79f5d68b5db59cda035d93036752801b77568d2a24fff8c265865037ffd7'
assert sha256_file(attempts) == '154c167e9254062000c74c32c80da346feff83b53ab6d49b59ba26e0340d4d19'
qa = json.loads(qa_path.read_text())
assert qa['status'] == 'passed' and qa['independent_selected_configuration_id'] == 't218_o0_c2'
checked = []
for item in qa['input_files']:
    p = Path(item['path'])
    assert p.is_relative_to(ROOT/'data/tests') and p.suffix in {'.json', '.csv'}
    assert sha256_file(p) == item['sha256'] and p.stat().st_size == item['bytes']
    checked.append({'path': p.relative_to(ROOT).as_posix(), 'sha256': item['sha256'], 'bytes': item['bytes']})
plan, candidates, provenance = load_validation_plan(ROOT/'configs/detection/threshold/validation_v3.yaml')
selection = json.loads((batch/'selection.json').read_text())
assert config_hash(plan,64) == selection['plan_hash'] == qa['plan_hash']
assert selection['status'] == 'validation_selected_not_frozen'
assert selection['ranking'][0]['configuration_id'] == selection['configuration_id'] == 't218_o0_c2'
assert config_hash(selection['params'],64) == '5b9dacca7e53b226fe90c42f1cb98d673193f0b43d0af8e2952677bc733acfa3'
assert selection['evaluation'] == plan['evaluation']
assert all(r['complete'] and r['frame_coverage_verified'] and r['frames_annotated']==5850 for r in selection['ranking'])
assert not selection['test_executed'] and not selection['five_fold_executed']
critical = ['src/detection/classical/threshold.py','src/detection/base.py','src/detection/registry.py',
            'src/detection/runner.py','src/detection/io.py','src/detection/strict_inputs.py',
            'src/evaluation/detection.py','src/experiments/validation_frame_checks.py']
implementation = []
for name in critical:
    old = subprocess.run(['git','show',f'7f47afb:{name}'],cwd=ROOT,capture_output=True,check=True).stdout
    current = (ROOT/name).read_bytes()
    # Git may normalize CRLF; compare normalized text, and retain exact live SHA.
    assert old.replace(b'\r\n',b'\n') == current.replace(b'\r\n',b'\n'), name
    implementation.append({'path':name,'sha256':sha256_file(ROOT/name),'unchanged_vs':'7f47afb',
                           'comparison':'bytes_after_crlf_normalization'})
def ref(path):
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha256_file(path)}
config = {
    'configuration_id':'t218_o0_c2_v3','method':'threshold',
    'freeze':{'scope':'development_only','allowed_splits':['train','val'],'confirmatory_plan':None},
    'selection':{'date':'2026-09-08','status':'frozen_for_development',
        'candidate_id':'t218_o0_c2','primary_metric':'macro_video_f1_individuals_center_10px',
        'macro_validation_f1':selection['ranking'][0]['macro_video_f1'],
        'interpretation':'fixed_development_baseline_not_independent_confirmation',
        'validation_manifest':ref(batch/'manifest.json'),'validation_selection':ref(batch/'selection.json'),
        'verification':ref(qa_path),'verification_attempts':ref(attempts),
        'parameter_hash':config_hash(selection['params'],64),'evaluation_run_commit':'7f47afb',
        'evaluation_run_source_hash':qa['source_hash_of_verified_runs'],
        'test_executed_for_this_configuration':False,'five_fold_executed':False,
        'historical_test_exposure':True},
    'params':selection['params'],'evaluation':selection['evaluation'],
    'protocol':{'splits_config':plan['protocol']['splits_config'],'splits_sha256':plan['protocol']['splits_sha256']},
    'run':{'stage':'development','split':'train','seed':42,'save_video':False,
           'max_frames':None,'draw_mode':'both','frozen':True},
}
target = ROOT/'configs/frozen/detection/threshold/t218_o0_c2_v3.yaml'
with target.open('x',encoding='utf-8',newline='\n') as out:
    yaml.safe_dump(config,out,sort_keys=False,allow_unicode=True)
receipt = ROOT/'data/derived/project_audits/general_20260908/freeze_t218_development_20260908.json'
write_json_exclusive(receipt,{'status':'frozen_for_development','created_at':datetime.now(timezone.utc).isoformat(),
    'config':ref(target),'verified_exported_artifacts':checked,'implementation':implementation,
    'validation_plan_hash':selection['plan_hash'],'validation_parent_provenance_rechecked':True,
    'raw_sources_opened':False,'new_model_runs':False,'test_or_folds_released':False,
    'basis':'completed_registered_selection_plus_passed_independent_QA_no_new_quality_cutoff',
    'note':'Receipt materializes a prior result; it is not a new experiment or clean-Git run certificate.'})
print(json.dumps({'config':str(target),'receipt':str(receipt),'exported_files_rechecked':len(checked)}))
