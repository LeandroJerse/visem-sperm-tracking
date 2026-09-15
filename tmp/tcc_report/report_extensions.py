"""Authenticate small documentary excerpts from an already audited training run."""
import csv
import hashlib
from html import escape
import io
import json


def artifact_fragments(root, run, manifest):
    records = []
    def first(name):
        path = run / 'by_video/11' / name
        relative = path.relative_to(root).as_posix()
        record = next(r for r in manifest['artifacts'] if r['path'] == relative)
        raw = path.read_bytes()
        assert len(raw) == record['bytes']
        assert hashlib.sha256(raw).hexdigest() == record['sha256']
        records.append(record)
        return next(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    window = first('selected_windows.csv')
    request = first('requests.csv')
    sample = first('features.csv')
    coverage = first('window_coverage.csv')
    assert request['sample_id'] == sample['sample_id']
    assert window['window_id'] == coverage['window_id']
    assert window['track_id'] == sample['track_id'] and window['video_id'] == '11'
    assert (sample['frame_from'], sample['frame_to'], sample['cx'], sample['cy']) == ('0','1','176.5','198.0')
    def table(row, keys, name):
        link = '../../' + (run / 'by_video/11' / name).relative_to(root).as_posix()
        return '<table><caption>Campos selecionados da primeira linha de <a href="'+link+'">'+escape(name)+'</a></caption><thead><tr><th>Campo</th><th>Conteúdo exportado</th></tr></thead><tbody>'+''.join(
            '<tr><td><code>'+escape(k)+'</code></td><td>'+('<code>'+escape(row[k])+'</code>' if row[k] else '<em>Célula vazia</em>')+'</td></tr>' for k in keys)+'</tbody></table>'
    parent = run.parent.relative_to(root).as_posix()
    values = {
      'ARQUIVO_LINKS': '<a href="../../'+run.relative_to(root).as_posix()+'/manifest.json">Manifesto real do benchmark</a> · <a href="../../'+parent+'/verification_20260909.json">Conferência independente aprovada</a>.',
      'ARQUIVO_MANIFESTO': escape(json.dumps({k:manifest[k] for k in ['run_id','status','stage','seed','git_sha','git_dirty','config_hash','source_hash']},ensure_ascii=False,indent=2)),
      'ARQUIVO_JANELA': table(window,['window_id','video_id','track_id','segment_id','split','history_start','origin_frame','future_end','history_length','forecast_horizon'],'selected_windows.csv'),
      'ARQUIVO_AMOSTRA': table(sample,['sample_id','frame_from','frame_to','cx','cy','u','v','valid','reason'],'features.csv'),
      'ARQUIVO_COBERTURA': table(coverage,['sample_count','valid_history19','valid_last5','eligible_last5','invalid_reasons_history19','invalid_reasons_last5'],'window_coverage.csv'),
    }
    return values, records
