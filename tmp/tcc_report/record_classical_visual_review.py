from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

root=Path(__file__).resolve().parents[2]
folder=root/'tmp/tcc_report/qa_20260911_classical_final_retry1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
browser=json.loads((folder/'browser_checks.json').read_text(encoding='utf-8'))
static=json.loads((folder/'static_checks.json').read_text(encoding='utf-8'))
assert browser['status']==static['status']=='passed'
for record in browser['hashes']:
    assert sha(root/record['path'])==record['sha256']
viewed=['atlas_comparison_desktop.png','atlas_comparison_mobile.png',
        'report_comparison_mobile_right_columns.png','report_by_video_mobile.png','report_next_mobile.png']
prior=['report_overview.png','report_comparison_desktop.png','report_figure_desktop.png','report_comparison_mobile.png']
receipt={'status':'passed','reviewed_at':datetime.now(timezone.utc).isoformat(),
         'scope':'Visual review of new comparison table, figure, expanded by-video table, next steps and atlas on desktop/mobile. Horizontal scroll confirmed on the wrapper. Original PNG inspected separately. Existing interactive JS unchanged; previous widget QA is not repeated.',
         'report_hashes':browser['hashes'],
         'screenshots':[{'path':str((folder/p).relative_to(root)).replace('\\','/'),'sha256':sha(folder/p)} for p in viewed],
         'earlier_layout_views':[{'path':'tmp/tcc_report/qa_20260911_classical/'+p,'sha256':sha(root/'tmp/tcc_report/qa_20260911_classical'/p)} for p in prior],
         'limitations':['On narrow screens, tables scroll horizontally. Figures can be opened at original size.','No PDF generated; external URLs were not checked for current HTTP availability.'],
         'prior_qa_attempts_preserved':['tmp/tcc_report/qa_20260911_classical/visual_review.json','tmp/tcc_report/qa_20260911_classical_final/failure.json']}
with (folder/'visual_review.json').open('x',encoding='utf-8') as stream: json.dump(receipt,stream,ensure_ascii=False,indent=2)
fig=root/'data/derived/detection/comparison_reports/classical_v1_20260911/comparacao_classicos_treino.png'
with (fig.parent/'visual_review.json').open('x',encoding='utf-8') as stream:
    json.dump({'status':'passed','reviewed_at':receipt['reviewed_at'],'figure_sha256':sha(fig),'checks':['Six families, axes, labels, per-video dots and descriptive-training caveat are legible.','PNG original and embedded HTML figure inspected.'],'report_visual_review':str((folder/'visual_review.json').relative_to(root)).replace('\\','/')},stream,ensure_ascii=False,indent=2)
for name in ('AGENTS.md','docs/projeto/NAVEGACAO.md'):
    path=root/name
    text=path.read_text(encoding='utf-8').replace('classes 0/2 e regra de clusters v3.', 'treino nas três classes e avaliação de indivíduos 0/2 com a regra de clusters v3.')
    path.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps({'visual_review':'passed','folder':str(folder)},ensure_ascii=False))
