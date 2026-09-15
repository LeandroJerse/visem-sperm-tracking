"""Preserve the preceding edition and editing components before refinement."""
from pathlib import Path
import hashlib
import json
root=Path(__file__).resolve().parents[2]
target=root/'data/derived/project_audits/general_20260911/classical_refinement_edition'
target.mkdir(parents=True,exist_ok=False)
names=['docs/projeto/RELATORIO_COMPLETO_TCC.html','RELATORIO_COMPLETO_TCC.html',
       'docs/projeto/mapa-tcc-didatico.html','MAPA_TCC_DIDATICO.html','AGENTS.md','docs/projeto/NAVEGACAO.md',
       'monografia/cap_metodo/metodo.tex','monografia/cap_conclusao/conclusao.tex']
names += ['tmp/tcc_report/'+x for x in ['core.html','closing.html','navigation.html','reading_guide.html','build_report.py','algorithms_deep.html','metrics.html','report.js','lab_extensions.js','report.css']]
rows=[]
for name in names:
    content=(root/name).read_bytes()
    dest=target/'before'/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as stream: stream.write(content)
    rows.append({'path':name,'snapshot':dest.relative_to(root).as_posix(),'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)})
with (target/'before_manifest.json').open('x',encoding='utf-8') as stream:
    json.dump({'scope':'preserve_comparison_edition_before_refinement_update','files':rows},stream,ensure_ascii=False,indent=2)
print(json.dumps({'preserved_files':len(rows),'path':str(target)},ensure_ascii=False))
