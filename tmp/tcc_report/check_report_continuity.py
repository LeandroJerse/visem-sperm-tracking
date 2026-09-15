"""Static review of local HTML, without opening linked scientific inputs."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json

ROOT = Path(__file__).resolve().parents[2]
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.ids, self.links, self.stack, self.errors = [], [], [], []
        self.remote_dependencies, self.provenance = [], ''
        self.collect_provenance = False
        self.feed(path.read_text(encoding='utf-8'))
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        for key in ('href', 'src'):
            if values.get(key):
                self.links.append(values[key])
        if tag in ('script', 'img', 'iframe', 'link'):
            source = values.get('src', values.get('href', ''))
            if source.startswith(('http:', 'https:', '//')):
                self.remote_dependencies.append(source)
        if tag == 'script' and values.get('id') == 'report-provenance':
            self.collect_provenance = True
        if tag not in VOID:
            self.stack.append(tag)
    def handle_endtag(self, tag):
        if tag == 'script':
            self.collect_provenance = False
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append({'closing': tag, 'expected': self.stack[-1] if self.stack else None})
        elif self.stack:
            self.stack.pop()
    def handle_data(self, data):
        if self.collect_provenance:
            self.provenance += data

reports = []
cache = {}
for name in ('docs/projeto/RELATORIO_COMPLETO_TCC.html', 'RELATORIO_COMPLETO_TCC.html', 'docs/projeto/mapa-tcc-didatico.html', 'MAPA_TCC_DIDATICO.html'):
    page = Page(ROOT / name)
    assert not page.errors and not page.stack, (name, page.errors, page.stack)
    assert len(page.ids) == len(set(page.ids)), (name, 'duplicate IDs')
    assert not page.remote_dependencies, (name, page.remote_dependencies)
    counts = Counter()
    external_links = set()
    for link in page.links:
        url = urlsplit(link)
        if url.scheme == 'data':
            assert link.startswith('data:image/png;base64,'), link[:70]
            counts['embedded_figures'] += 1
            continue
        if url.scheme or url.netloc:
            assert url.scheme in ('http', 'https'), (name, link)
            external_links.add(link)
            counts['external_references'] += 1
            continue
        target = (page.path.parent / unquote(url.path)).resolve() if url.path else page.path.resolve()
        assert target.exists(), (name, link)
        counts['local_links'] += 1
        if url.fragment and target.suffix.lower() == '.html':
            if target not in cache:
                cache[target] = Page(target)
            assert unquote(url.fragment) in cache[target].ids, (name, link)
            counts['checked_html_anchors'] += 1
    meta = json.loads(page.provenance) if page.provenance else None
    if meta:
        assert meta['new_model_runs'] == 0
        assert len(meta['top_level_chapters']) == 19
        assert meta['edition_date'] == '2026-09-11'
        assert meta['scientific_state_date'] == '2026-09-09'
        assert meta['documentation_only_expansion'] is True
    reports.append({'path': name, 'sha256': sha256(page.path.read_bytes()).hexdigest(), 'bytes': page.path.stat().st_size, 'ids': len(page.ids), 'counts': dict(counts), 'external_links': sorted(external_links), 'status': 'passed'})

out = ROOT / 'tmp/tcc_report/qa_20260911_continuidade/static_checks.json'
out.write_text(json.dumps({'status': 'passed', 'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': 'HTML structure, IDs, local path existence, HTML fragments, offline dependencies; no external HTTP availability check and no linked scientific input content read', 'reports': reports}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': 'passed', 'reports': [{k: v for k, v in r.items() if k != 'external_links'} for r in reports]}, ensure_ascii=False))
