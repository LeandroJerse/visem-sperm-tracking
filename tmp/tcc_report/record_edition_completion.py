"""Record the reviewed local edition without changing scientific artifacts."""
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / 'tmp/tcc_report/qa_20260910_ampliado'
DEST = ROOT / 'data/derived/project_audits/general_20260910/relatorio_ampliado_20260910'

def record(path):
    raw = path.read_bytes()
    return {'path': path.relative_to(ROOT).as_posix(), 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}

def write_new(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')

def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, check=True,
                          encoding='utf-8').stdout.strip()

assert not git('status', '--porcelain'), 'Commit documentary changes before final receipt'
assert git('show', '--pretty=', '--name-only', 'HEAD') == 'docs/projeto/DIARIO.md'

static = json.loads((QA / 'static_checks.json').read_text(encoding='utf-8'))
browser = json.loads((QA / 'browser_checks.json').read_text(encoding='utf-8'))
targeted = json.loads((QA / 'final_targeted_checks.json').read_text(encoding='utf-8'))
for receipt in [static, browser, targeted]:
    assert receipt['status'] == 'passed'
for item in static['reports'] + targeted['hashes']:
    assert record(ROOT / item['path'])['sha256'] == item['sha256']
before = json.loads((DEST / 'before_manifest.json').read_text(encoding='utf-8'))
for item in before['files']:
    assert record(ROOT / item['snapshot'])['sha256'] == item['sha256']

reviewed = ['desktop_abertura.png', 'guia-leitura_desktop.png', 'bilinear_desktop.png',
    'lab-causalidade_mobile.png', 'ler-artefatos_mobile.png', 'causalidade_desktop.png',
    'algoritmos-detalhados_desktop.png', 'exemplo-completo_desktop.png',
    'lab-bilinear_mobile.png', 'impressao_metricas.png', 'final_causalidade_mobile.png',
    'final_atlas_desktop.png', 'final_atlas_mobile.png']
visual = {
    'status': 'passed', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'scope': 'Manual inspection of generated screenshots plus browser geometry checks; no PDF pagination review',
    'screenshots': [record(QA / name) for name in reviewed],
    'notes': ['Report and new chapters readable; tables and code fields stay within mobile document width.',
      'Final mobile causal labels enlarged and contained within SVG after targeted correction.',
      'Atlas reading card and state distinction readable on desktop and mobile.',
      'Scientific figures retained unchanged; no new scientific plot or result was created.'],
    'final_report': record(ROOT / 'docs/projeto/RELATORIO_COMPLETO_TCC.html'),
    'final_targeted_checks': record(QA / 'final_targeted_checks.json')
}
write_new(QA / 'visual_review.json', visual)

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.raw = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'report-provenance': self.active = True
    def handle_endtag(self, tag):
        if tag == 'script': self.active = False
    def handle_data(self, data):
        if self.active: self.raw += data

parser = Metadata(); parser.feed((ROOT / 'docs/projeto/RELATORIO_COMPLETO_TCC.html').read_text(encoding='utf-8'))
meta = json.loads(parser.raw)
assert meta['new_model_runs'] == 0 and len(meta['top_level_chapters']) == 19
assert meta['compact_benchmark_manifest_sha256'] == '72c7df2d895d1fa02014dfa1100a1a7defc8351ea19d86392ad09e5473fcd278'
assert meta['compact_benchmark_verification_sha256'] == '20af88c5930434685a86330d98692f99d9a429f0e0e61723ae41138e1af1435c'

completion = {
 'status': 'complete', 'created_at': datetime.now(timezone.utc).isoformat(),
 'edition_date': '2026-09-10', 'scientific_state_date': '2026-09-09',
 'purpose': 'Expand comprehension of the existing TCC; documentary edition only',
 'documentary_commit': git('rev-parse', 'HEAD'), 'git_clean': True,
 'unchanged_scientific_code_run_commit': meta['compact_execution_commit'],
 'unchanged_scientific_results_commit': '400cc2d0ed042a27ae88e8c4a81d2d9ae2da7981',
 'latest_completed_scientific_milestone': '8a_compact_engineering_benchmark',
 'next_scientific_step': 'Instrument dominant loop costs and register an operational adjustment with numerical equivalence and resource verification before another cost trial; full extraction and paired ablation remain pending.',
 'new_scientific_runs': 0, 'read_original_video_sources': False,
 'changed_scientific_code_or_configs': False, 'repeated_scientific_test_suite': False,
 'before_manifest': record(DEST / 'before_manifest.json'),
 'final_files': [record(ROOT / p) for p in ['docs/projeto/RELATORIO_COMPLETO_TCC.html', 'RELATORIO_COMPLETO_TCC.html',
    'docs/projeto/mapa-tcc-didatico.html', 'MAPA_TCC_DIDATICO.html', 'docs/projeto/NAVEGACAO.md', 'AGENTS.md', 'docs/projeto/DIARIO.md']],
 'report_chapters': meta['top_level_chapters'], 'word_count_approx': meta['word_count_approx'],
 'embedded_figures': meta['figures'], 'learning_widgets': meta['synthetic_learning_widgets'],
 'authenticated_excerpt_sources': meta['documentary_excerpt_sources'],
 'source_parts': meta['parts'],
 'builder': record(ROOT / 'tmp/tcc_report/build_report.py'),
 'static_verification': record(QA / 'static_checks.json'),
 'general_browser_verification': {'receipt': record(QA / 'browser_checks.json'),
    'tested_report_sha256': '1c00cddd265c739354fb9bb149eec21f919f76f015e8c5b608e3d38cb63b84e6',
    'additional_executed_checks': ['causal origins 19,29,59 and 30 diagram positions',
      'bilinear values, invalid positive weight, valid zero weight and corners',
      'no nested table scroll wrappers', 'new chapter desktop/mobile screenshots'],
    'followup_changes': 'Chapter title and introductory wording; mobile diagram label size/geometry. Mathematical logic unchanged; final targeted receipt verifies followup.'},
 'final_targeted_verification': record(QA / 'final_targeted_checks.json'),
 'preserved_layout_failure': record(QA / 'final_layout_attempt1.json'),
 'visual_review': record(QA / 'visual_review.json'),
 'independent_documentary_review': {
    'status': 'passed_after_two_wording_corrections',
    'scope': 'Algorithm descriptions and worked example reviewed against code; real window/sample/link/coverage checked against five authenticated CSVs; temporal availability and bilinear control mathematics checked.',
    'corrections': ['Mark pre-smoke next-step wording as history resolved by level 7.',
        'Explain causal access per window while producer processes frames for multiple origins.'],
    'limitations': 'No new scientific experiment, original MP4 decoding, or independent Farneback estimation.'},
 'publication_policy': 'Only public documentary diary entry committed; HTML, local guides, instructions, edit components and presentation evidence remain excluded.'
}
write_new(DEST / 'completion.json', completion)
print(json.dumps({'status': 'complete', 'documentary_commit': completion['documentary_commit'], 'receipt': record(DEST / 'completion.json')}, ensure_ascii=False))
