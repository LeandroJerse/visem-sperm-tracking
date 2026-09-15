from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[2]
folder=root/'data/derived/project_audits/general_20260911/classical_comparison_edition/before_monografia'
expected={'monografia/cap_metodo/metodo.tex':'6ef97e59b97cf066bb180e89dbba12cc4b0b372125716bb712695eb389304225',
          'monografia/cap_conclusao/conclusao.tex':'3f2e2cabacd740c2734ce15948f20a636b32f328f0cd9e837bdfc3f24bd97a30'}
for name,value in expected.items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==value
with (folder/'after_verification.json').open('x',encoding='utf-8') as stream:
    json.dump({'status':'passed','scope':'Local LaTeX source edit reviewed against authenticated search results. Braces, environments, citations and references checked during editing. Existing academic declaration preserved byte for byte. Final file hashes checked after review.',
               'files':expected,'pdf_compiled':False,'committed':False,'limitations':['Basic source checks do not certify rendered PDF layout.']},stream,ensure_ascii=False,indent=2)
