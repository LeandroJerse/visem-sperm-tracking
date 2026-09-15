"""Build a descriptive figure from an independently verified comparison."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--verification', type=Path, required=True)
args = parser.parse_args()

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

manifest_path = args.manifest.resolve()
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
qa_path = args.verification.resolve()
qa = json.loads(qa_path.read_text(encoding='utf-8'))
assert manifest['status'] == 'complete' and manifest['summary']['mode'] == 'search'
assert qa['status'] == 'passed' and qa['manifest_sha256'] == digest(manifest_path)
ranking_path = manifest_path.parent / 'ranking.csv'
assert digest(ranking_path) == manifest['artifact_hashes']['ranking.csv']
with ranking_path.open(encoding='utf-8', newline='') as stream:
    ranking = list(csv.DictReader(stream))
assert len(ranking) == 43
names = {'threshold': 'Threshold T218', 'otsu': 'Otsu',
         'adaptive_threshold': 'Adaptativo', 'hybrid_threshold': 'Híbrido CLAHE',
         'blob': 'Blob', 'watershed': 'Watershed'}
selected = [next(row for row in ranking if row['family'] == family) for family in names]
selected.sort(key=lambda row: -float(row['macro_video_f1']))
rows = []
child_records = {str(Path(row['path']).resolve()): row['sha256'] for row in manifest['candidate_manifests']}
for row in selected:
    child_path = Path(row['manifest_path'])
    assert digest(child_path) == child_records[str(child_path.resolve())]
    child = json.loads(child_path.read_text(encoding='utf-8'))
    videos_path = child_path.parent / 'video_summary.csv'
    assert digest(videos_path) == child['artifact_hashes']['video_summary_csv']
    with videos_path.open(encoding='utf-8', newline='') as stream:
        videos = list(csv.DictReader(stream))
    assert len(videos) == 12
    rows.append({'family': row['family'], 'label': names[row['family']],
                 'configuration_id': row['configuration_id'], 'params': child['config']['params'],
                 'f1': float(row['macro_video_f1']), 'precision': float(row['macro_video_precision']),
                 'recall': float(row['macro_video_recall']),
                 'detection_ms': float(row['macro_video_detection_ms_mean']),
                 'f1_15px': float(row['macro_video_f1_at_15px']),
                 'f1_20px': float(row['macro_video_f1_at_20px']),
                 'n_predictions_ignored': int(row['n_predictions_ignored']),
                 'manifest': child_path.relative_to(ROOT).as_posix(),
                 'videos': [{'video_id': v['video_id'], 'f1': float(v['f1'])} for v in videos]})

out = ROOT / 'data/derived/detection/comparison_reports/classical_v1_20260911'
out.mkdir(parents=True, exist_ok=False)
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
fig, (ax, bx) = plt.subplots(1, 2, figsize=(12.8, 5.4), gridspec_kw={'width_ratios': [1.6, 1]})
fig.patch.set_facecolor('#fbfaf6')
colors = ['#136c70' if r['family'] != 'threshold' else '#b26020' for r in rows]
indices = list(range(len(rows)))
ax.barh(indices, [r['f1'] for r in rows], color=colors, height=.52, alpha=.9)
for i, row in enumerate(rows):
    values = [v['f1'] for v in row['videos']]
    for j, value in enumerate(values):
        ax.scatter(value, i + (j - 5.5) * .031, s=15, color='#16282c', alpha=.62, zorder=3)
    ax.text(min(row['f1'] + .018, .94), i - .30, f"{row['f1']:.4f}", fontsize=9)
ax.set(yticks=indices, yticklabels=[r['label'] for r in rows], xlim=(0, 1),
       xlabel='F1 de centros a 10 px', title='Média dos 12 vídeos e valores por vídeo')
ax.invert_yaxis()
ax.grid(axis='x', alpha=.18)
ax.set_axisbelow(True)
bx.barh(indices, [r['detection_ms'] for r in rows], color=colors, height=.52)
bx.set(yticks=indices, yticklabels=[], xlabel='Tempo médio de detecção (ms/quadro)',
       title='Custo do detector com imagem em cache')
bx.invert_yaxis()
bx.grid(axis='x', alpha=.18)
bx.set_axisbelow(True)
for ax_ in (ax, bx):
    ax_.set_facecolor('#fbfaf6')
    ax_.spines[['top', 'right']].set_visible(False)
fig.suptitle('Primeira comparação clássica — seleção no treino', x=.05, ha='left', fontweight='bold', fontsize=15)
fig.text(.05, .035, 'Melhor configuração desta grade por família; 48 quadros por vídeo. Pontos = vídeos; barras = média com peso igual.\n'
         'Busca de esforço desigual; T218 previamente ajustado. Sem validação comparativa, promoção ou teste de generalização.',
         fontsize=9, color='#435156')
fig.tight_layout(rect=(.035, .105, .985, .91))
for ext in ('png', 'svg'):
    fig.savefig(out / f'comparacao_classicos_treino.{ext}', dpi=170, facecolor=fig.get_facecolor())
plt.close(fig)
summary = {'scope': 'descriptive_training_screening', 'source_manifest': manifest_path.relative_to(ROOT).as_posix(),
           'source_manifest_sha256': digest(manifest_path), 'verification': qa_path.relative_to(ROOT).as_posix(),
           'verification_sha256': digest(qa_path), 'run_commit': manifest['git_sha'],
           'batch_summary': manifest['summary'], 'elapsed_seconds': manifest['elapsed_seconds'],
           'qa_counts': {k: qa[k] for k in ('files_checked', 'comparisons', 'numeric_comparisons', 'scipy_matchings', 'maximum_numeric_difference')},
           'best_per_family': rows,
           'figures': {p.name: digest(p) for p in sorted(out.glob('comparacao_classicos_treino.*'))}}
with (out / 'summary.json').open('x', encoding='utf-8') as stream:
    json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({'output': str(out), 'best_per_family': [{k: v for k, v in r.items() if k not in ('params', 'videos')} for r in rows]}, ensure_ascii=False))
