"""Record direct visual inspection and the corrected documentation-link check."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tmp/tcc_report/qa_20260911_refinement'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, record):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)

browser = json.loads((OUT / 'browser_checks.json').read_text(encoding='utf-8'))
static = json.loads((OUT / 'static_checks.json').read_text(encoding='utf-8'))
assert browser['status'] == static['status'] == 'passed'
for record in browser['hashes'] + static['reports']:
    assert sha(ROOT / record['path']) == record['sha256']
viewed = ['report_overview.png', 'report_comparison_desktop.png',
          'report_figure_desktop.png', 'report_comparison_mobile.png',
          'report_figure_mobile.png', 'report_comparison_mobile_right_columns.png',
          'report_next_desktop.png', 'report_next_mobile.png',
          'atlas_comparison_desktop.png', 'atlas_comparison_mobile.png',
          'report_by_video_mobile.png']
write('visual_review.json', {
    'status': 'passed', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
    'method': 'Direct visual inspection of all eleven listed browser screenshots.',
    'html_hashes': browser['hashes'],
    'screenshots': {name: sha(OUT / name) for name in viewed},
    'findings': [
        'Desktop comparison columns and figure are legible and aligned.',
        'Mobile paragraphs and headings fit the viewport without page overflow.',
        'Wide tables scroll horizontally; right-hand columns were inspected.',
        'The figure scales down on mobile; links expose its full PNG and SVG.',
        'Per-video details open correctly and retain the distance sensitivities.',
        'Current milestone, historical references and next steps remain explicit.',
        'Atlas and report navigation pass at desktop and mobile viewport sizes.'
    ],
    'limits': 'Visual review of changed areas; unchanged JavaScript identity checked separately. No new scientific experiment.'
})
log = OUT / 'documentation_links_retry1.log'
assert '1 passed in 1.64s' in log.read_text(encoding='utf-8-sig')
write('documentation_links_initial_failure.json', {
    'status': 'failed', 'recorded_at': datetime.now(timezone.utc).isoformat(),
    'test': 'tests/config/test_documentation_links.py::test_all_active_local_markdown_links_resolve',
    'result': '1 failed in 1.21s',
    'evidence': 'Initial pytest tool output during this edition; this receipt preserves the diagnosis, not a verbatim log.',
    'reason': 'The active-document collector included README.md copies inside project audit snapshots, whose original relative paths are intentionally preserved.',
    'affected_snapshot': 'data/derived/project_audits/general_20260911/classical_refinement_edition/documentation_before/README.md',
    'resolution': 'Exclude only before/documentation_before snapshot paths inside data/derived/project_audits; keep checking canonical documents and all other data README files.',
    'scientific_run_changed': False, 'backups_changed': False
})
write('documentation_links_retry1.json', {
    'status': 'passed', 'result': '1 passed in 1.64s',
    'log': log.relative_to(ROOT).as_posix(), 'log_sha256': sha(log),
    'test_sha256': sha(ROOT / 'tests/config/test_documentation_links.py'),
    'initial_failure': 'documentation_links_initial_failure.json'
})
print(json.dumps({'status': 'passed', 'screenshots_reviewed': len(viewed)}))
