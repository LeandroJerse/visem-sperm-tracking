"""Preserve the preceding local report before the comparison results edition."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'data/derived/project_audits/general_20260911/classical_comparison_edition'
NAMES = ['docs/projeto/RELATORIO_COMPLETO_TCC.html', 'RELATORIO_COMPLETO_TCC.html',
         'docs/projeto/mapa-tcc-didatico.html', 'MAPA_TCC_DIDATICO.html',
         'AGENTS.md', 'docs/projeto/NAVEGACAO.md', 'tmp/tcc_report/core.html',
         'tmp/tcc_report/closing.html', 'tmp/tcc_report/navigation.html',
         'tmp/tcc_report/reading_guide.html', 'tmp/tcc_report/build_report.py']
records = []
for name in NAMES:
    raw = (ROOT / name).read_bytes()
    target = DEST / 'before' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle:
        handle.write(raw)
    records.append({'path': name, 'snapshot': target.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(raw).hexdigest()})
with (DEST / 'before_manifest.json').open('x', encoding='utf-8') as handle:
    json.dump({'purpose': 'Preserve preceding edition before reporting classical comparison',
               'files': records}, handle, ensure_ascii=False, indent=2)
print(json.dumps({'preserved_files': len(records), 'directory': str(DEST)}))
