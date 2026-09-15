"""Resolve the already proposed neighborhoods from authenticated parent metadata."""
from pathlib import Path
from decimal import Decimal
import copy
import hashlib
import json
import yaml

ROOT=Path(__file__).resolve().parents[2]
SEARCH='data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/20260911T144742812472Z__2547109__cfgbecfe1d189e7__srcf14ede5a12__s42/manifest.json'
QA='data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/verification_20260911.json'
def read(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
assert sha(SEARCH)=='8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0'
assert sha(QA)=='c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792'
m=read(SEARCH)
q=read(QA)
assert m['status']=='complete' and q['status']=='passed'
finalpath=Path(SEARCH).parent/'family_finalists.json'
assert sha(finalpath)==m['artifact_hashes']['family_finalists.json']
finals=read(finalpath)
childpins={str(Path(r['path']).resolve()):r['sha256'] for r in m['candidate_manifests']}
parents=[]
for row in finals:
    p=Path(row['manifest_path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest()==childpins[str(p.resolve())]
    child=json.loads(p.read_text(encoding='utf-8'))
    parents.append({'configuration_id':row['configuration_id'],'family':row['family'],'params':child['config']['params'], 'method':row['method']})

def axis(parameter,step,minimum=None,maximum=None,odd=False):
    return {'parameter':parameter,'step':step,'min':minimum,'max':maximum,'odd':odd}
neighborhood=[
    {'family':'otsu','axes':[axis('morph_iterations',1,0,2),axis('close_iterations',1,0,3)]},
    {'family':'adaptive_threshold','axes':[axis('adaptive_block',8,3,127,True),axis('adaptive_c',2),axis('morph_iterations',1,0,2)]},
    {'family':'hybrid_threshold','axes':[axis('clip_limit',0.5,0.5,4),axis('background_kernel',8,3,63,True),axis('open_iterations',1,0,2)]},
    {'family':'blob','axes':[axis('min_threshold',20,0,245)]},
    {'family':'watershed','axes':[axis('blur',2,1,7,True),axis('dist_ratio',0.1,0.1,0.9)]},
]
all_proposals=[]
counts={}
for family in neighborhood:
    signatures={}
    for parent in [r for r in parents if r['family']==family['family']]:
        proposals=[(None,0,copy.deepcopy(parent['params']),True)]
        for a in family['axes']:
            for direction in (-1,1):
                value=Decimal(str(parent['params'][a['parameter']]))+direction*Decimal(str(a['step']))
                valid=(a['min'] is None or value>=Decimal(str(a['min']))) and (a['max'] is None or value<=Decimal(str(a['max'])))
                params=copy.deepcopy(parent['params'])
                params[a['parameter']]=int(value) if type(parent['params'][a['parameter']]) is int and type(a['step']) is int else float(value)
                if a['odd']:
                    valid=valid and value%2==1
                proposals.append((a['parameter'],direction*a['step'],params,valid))
        for key,delta,params,valid in proposals:
            record={'family':family['family'],'parent':parent['configuration_id'],'axis':key,'delta':delta,'valid':valid,'params':params}
            all_proposals.append(record)
            if valid:
                sig=json.dumps({'method':parent['method'],'params':params},sort_keys=True,separators=(',',':'))
                signatures.setdefault(sig,[]).append(record)
    counts[family['family']]=len(signatures)
assert len(all_proposals)==54
assert sum(x['valid'] for x in all_proposals)==51
assert counts=={'otsu':8,'adaptive_threshold':13,'hybrid_threshold':11,'blob':6,'watershed':7}
prior=yaml.safe_load((ROOT/'configs/detection/comparison/classical_v1_operational_v2.yaml').read_text(encoding='utf-8'))
plan={
    'plan_id':'classical_detection_refinement_v1_20260911',
    'kind':'static_classical_detection_refinement_v1',
    'expected_candidates':45,'expected_proposals':54,'expected_valid_proposals':51,'expected_by_family':counts,
    'parents':{
        'search_manifest':{'path':SEARCH,'sha256':sha(SEARCH)},
        'search_qa':{'path':QA,'sha256':sha(QA)},
        'comparison_plan':{'path':'configs/detection/comparison/classical_v1_operational_v2.yaml','canonical_sha256':'a86c8a68180e89802150a2cb3d354a5dc9657e64270d820d9fb7269f64a6dbf5'},
        'finalists':{'path':finalpath.as_posix(),'sha256':sha(finalpath)},
    },
    'input':prior['input'],'evaluation':prior['evaluation'],'train_ids':prior['train_ids'],
    'sampling':{'smoke_mode':'benchmark','refinement_mode':'master','smoke_frames_per_video':1,'refinement_frames_per_video':48},
    'run':prior['run'],'budget':prior['budget'],
    'selection':{
        'primary':prior['selection']['primary'],'tie_breakers':prior['selection']['tie_breakers'],
        'comparisons_require_all_candidates_and_all_planned_frames':True,
        'timing_used_for_ranking':False,'finalists_per_family':2,'expected_finalists':10,
        'historical_threshold_reference_reexecuted':False,'promotion_allowed':False,'validation_released':False,
        'interpretation':'limited_training_refinement_for_full_validation_contract',
        'comparability_limit':'unequal_search_effort_and_previously_selected_threshold_reference',
    },
    'neighborhood':neighborhood,
}
target=ROOT/'configs/detection/comparison/classical_refinement_v1.yaml'
with target.open('x',encoding='utf-8',newline='\n') as stream: yaml.safe_dump(plan,stream,sort_keys=False,allow_unicode=True)
with (ROOT/'tmp/tcc_report/refinement_resolution_v1.json').open('x',encoding='utf-8') as stream:
    json.dump({'scope':'parent_metadata_only_no_new_detector_runs','parents':parents,'proposals':all_proposals,'unique_by_family':counts},stream,ensure_ascii=False,indent=2)
print(json.dumps({'plan':str(target),'proposals':len(all_proposals),'valid':51,'unique':counts,'smoke_evaluations':540,'refinement_evaluations':25920},ensure_ascii=False))
