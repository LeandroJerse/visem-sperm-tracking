from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[2]
out=root/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
with (out/'visual_review.json').open('x',encoding='utf-8') as stream:
    json.dump({'status':'layout_revision_required','files':{p.name:sha(p) for p in out.iterdir() if p.name in {'summary.json','refinamento_classicos_treino.png','refinamento_classicos_treino.svg'}},'finding':'Right panel T218 historical annotation touches x-axis because the five cost bars and six F1 bars use different automatic y limits.','resolution':'Set both panels to identical explicit y limits in a new revision_02. Preserve original files; scientific runs and metrics unchanged.'},stream,ensure_ascii=False,indent=2)
for name in ('publish_refinement_edition.py','update_refinement_monograph.py'):
    p=root/'tmp/tcc_report'/name
    text=p.read_text(encoding='utf-8')
    text=text.replace('comparison_reports/classical_refinement_v1_20260911/summary.json','comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json')
    text=text.replace('comparison_reports/classical_refinement_v1_20260911/refinamento_classicos_treino.png','comparison_reports/classical_refinement_v1_20260911/revision_02/refinamento_classicos_treino.png')
    p.write_text(text,encoding='utf-8',newline='\n')
print('Layout finding preserved; new publishing paths point to revision_02, not yet generated.')
