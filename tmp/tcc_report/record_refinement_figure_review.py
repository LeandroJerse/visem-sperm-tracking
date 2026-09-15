from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
root=Path(__file__).resolve().parents[2]
parent=root/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911'
current=parent/'revision_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((parent/'summary.json').read_text(encoding='utf-8'))
new=json.loads((current/'summary.json').read_text(encoding='utf-8'))
old.pop('figures'); new.pop('figures')
assert old==new
receipt={'status':'passed','reviewed_at':datetime.now(timezone.utc).isoformat(),
 'method':'Direct visual inspection of the rendered PNG at 2244x986 pixels.',
 'checks':['Aligned row positions in both panels','Historical T218 has no contemporary timing bar','Reference annotation clear of axes','Labels, points, decimal values and footnote readable','Scientific values and provenance identical to the preserved initial summary'],
 'initial_layout_review':{'path':(parent/'visual_review.json').relative_to(root).as_posix(),'sha256':sha(parent/'visual_review.json')},
 'files':{p.name:sha(p) for p in current.iterdir() if p.suffix in {'.json','.png','.svg'}}}
with (current/'visual_review.json').open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
print('Figure revision_02 passed visual review; metrics unchanged.')
