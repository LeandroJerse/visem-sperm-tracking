"""Read-only link and anchor check for the two local atlas entry points."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import json

ROOT = Path(__file__).resolve().parents[1]

class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.path, self.ids, self.links = path, [], []
        self.feed(path.read_text(encoding='utf-8'))
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        self.links.extend(values[key] for key in ('href', 'src') if values.get(key))

for name in ('MAPA_TCC_DIDATICO.html', 'docs/projeto/mapa-tcc-didatico.html'):
    page = Page(ROOT / name)
    assert len(page.ids) == len(set(page.ids)), (name, 'duplicate IDs')
    for link in page.links:
        url = urlsplit(link)
        if url.scheme or url.netloc:
            continue
        target = (page.path.parent / unquote(url.path)).resolve() if url.path else page.path
        assert target.exists(), (name, link)
        if url.fragment and target.suffix == '.html':
            assert unquote(url.fragment) in Page(target).ids, (name, link)
    print(json.dumps({'path': name, 'status': 'passed', 'ids': len(page.ids), 'links': len(page.links)}))
