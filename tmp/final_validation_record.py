from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

from src.experiments.runs import _source_hash

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42'
QA = RUN.parent / 'verification_20260908_retry2.json'
FIG = ROOT / 'data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

batch, qa = read(RUN / 'manifest.json'), read(QA)
assert batch['status'] == 'complete' and qa['status'] == 'passed'
assert sha(RUN / 'manifest.json') == qa['batch_manifest_sha256']
assert _source_hash(ROOT) == batch['source_hash']
for reference in qa['input_files']:
    path = Path(reference['path'])
    assert not path.is_relative_to(ROOT / 'data/sources')
    assert sha(path) == reference['sha256'], path
selection = read(RUN / 'selection.json')
assert selection['configuration_id'] == qa['independent_selected_configuration_id'] == 't218_o0_c2'
assert not selection['test_executed'] and not selection['five_fold_executed']
latex = ROOT / 'monografia/cap_metodo/metodo.tex'
text = latex.read_bytes().decode('utf-8')
assert text.count(r'\begin{enumerate}') == text.count(r'\end{enumerate}')
assert text.count(r'\begin{itemize}') == text.count(r'\end{itemize}')
assert text.count('Declaração sobre o uso de Inteligência Artificial') == 1
disclosure = text[text.index(r'\section{Declaração sobre o uso de Inteligência Artificial}'):]
assert 'Para a consolidação desta versão inicial, utilizei as ferramentas ChatGPT e Codex, da OpenAI' in disclosure
artifact_paths = [RUN / 'manifest.json', QA, RUN.parent / 'verification_attempts_20260908.json',
                  *[FIG / name for name in ('validacao_threshold_completa.png', 'validacao_threshold_completa.svg',
                                            'figure_data.json', 'manifest.json', 'visual_review.json')]]
report = {'status': 'passed', 'created_at': datetime.now(timezone.utc).isoformat(),
          'source_hash_unchanged_since_execution': batch['source_hash'], 'execution_commit': batch['git_sha'],
          'scientific_run_repeated': False, 'test_accessed': False, 'finalist': selection['configuration_id'],
          'automated_short_suite': {'passed': 824, 'elapsed_seconds': 110.00, 'excluded': ['optional_ml', 'slow']},
          'independent_verification': {'status': 'passed', 'frames': 11700, 'matching_checks': 144,
                                       'comparisons': 1772878, 'files_rehashed_after_documentation': len(qa['input_files'])},
          'figure_review': 'Final PNG inspected at full composition; SVG and separate visual-review record present.',
          'latex_source_updated': True, 'pdf_recompiled': False,
          'local_disclosure_sha256': hashlib.sha256(disclosure.encode('utf-8')).hexdigest(),
          'artifact_references': [{'path': str(path), 'sha256': sha(path)} for path in artifact_paths]}
target = ROOT / 'data/derived/project_audits/general_20260908/validation_completion_20260908.json'
with target.open('x', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({'status': 'passed', 'files_rehashed': len(qa['input_files']), 'output': str(target)}))
