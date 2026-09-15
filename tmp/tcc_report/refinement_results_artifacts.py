"""Derive a descriptive figure only from completed, independently checked runs."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--manifest', type=Path, required=True)
parser.add_argument('--verification', type=Path, required=True)
parser.add_argument('--revision', choices=('revision_02',))
args = parser.parse_args()

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def csv_rows(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))

manifest_path, qa_path = args.manifest.resolve(), args.verification.resolve()
manifest, qa = read(manifest_path), read(qa_path)
assert manifest['status'] == 'complete' and manifest['git_dirty'] is False
assert manifest['stage'] == 'refinement' and manifest['summary']['frame_evaluations'] == 25920
assert qa['status'] == 'passed' and qa['manifest_sha256'] == digest(manifest_path)
assert qa['mode'] == 'refinement' and qa['parent_parity']['controls'] == 10
assert qa['parent_parity']['frames_per_control'] == 576
ranking_path = manifest_path.parent/'ranking.csv'
assert digest(ranking_path) == manifest['artifact_hashes']['ranking.csv']
ranking = csv_rows(ranking_path)
assert len(ranking) == 45 and not any(r['family'] == 'threshold' for r in ranking)
prior_path = ROOT/'data/derived/detection/comparison_reports/classical_v1_20260911/summary.json'
assert digest(prior_path) == 'd2f6889e80f971d2684cbf7277208b91fa80301608f15030ee0b4cfcc45ef282'
prior = read(prior_path)
assert digest(ROOT/prior['source_manifest']) == prior['source_manifest_sha256']
assert digest(ROOT/prior['verification']) == prior['verification_sha256']
names = {'otsu':'Otsu','adaptive_threshold':'Adaptativo','hybrid_threshold':'Híbrido CLAHE','blob':'Blob','watershed':'Watershed'}
child_hashes = {str(Path(r['path']).resolve()):r['sha256'] for r in manifest['candidate_manifests']}
rows = []
for family, label in names.items():
    row = next(r for r in ranking if r['family'] == family)
    child_path = Path(row['manifest_path']).resolve()
    assert digest(child_path) == child_hashes[str(child_path)]
    child = read(child_path)
    video_path = child_path.parent/'video_summary.csv'
    assert digest(video_path) == child['artifact_hashes']['video_summary_csv']
    videos = csv_rows(video_path)
    assert len(videos) == 12
    previous = next(r for r in prior['best_per_family'] if r['family'] == family)
    current = {'family':family,'label':label,'configuration_id':row['configuration_id'],
        'params':child['config']['params'],'lineage':child['config']['refinement_lineage'],
        'f1':float(row['macro_video_f1']),'precision':float(row['macro_video_precision']),
        'recall':float(row['macro_video_recall']),'detection_ms':float(row['macro_video_detection_ms_mean']),
        'f1_15px':float(row['macro_video_f1_at_15px']),'f1_20px':float(row['macro_video_f1_at_20px']),
        'n_predictions_ignored':int(row['n_predictions_ignored']),
        'manifest':child_path.relative_to(ROOT).as_posix(),'manifest_sha256':digest(child_path),
        'videos':[{'video_id':v['video_id'],'f1':float(v['f1'])} for v in videos],
        'previous_configuration_id':previous['configuration_id'],'previous_f1':previous['f1']}
    current['delta_f1'] = current['f1']-current['previous_f1']
    assert current['delta_f1'] >= -1e-12
    rows.append(current)
rows.sort(key=lambda r:(-r['f1'],r['configuration_id']))
reference = next(r for r in prior['best_per_family'] if r['family']=='threshold')
# The child reference is authenticated by the new run and its independent QA.
historical_path = manifest_path.parent/'historical_reference.json'
assert digest(historical_path) == manifest['artifact_hashes']['historical_reference.json']
historical = read(historical_path)
assert historical['reexecuted'] is False
assert digest(Path(historical['parent_manifest']['path'])) == historical['parent_manifest']['sha256']
assert Path(historical['parent_manifest']['path']).resolve() == (ROOT/reference['manifest']).resolve()
combined = rows+[dict(reference, label='T218 · histórico')]
out = ROOT/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911'
if args.revision:
    out=out/args.revision
out.mkdir(parents=True, exist_ok=False)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig, (ax,bx) = plt.subplots(1,2,figsize=(13.2,5.8),gridspec_kw={'width_ratios':[1.65,1]})
fig.patch.set_facecolor('#fbfaf6')
indices = list(range(6))
colors = ['#136c70']*5+['#b26020']
ax.barh(indices,[r['f1'] for r in combined],color=colors,height=.52,alpha=.88)
for i,row in enumerate(combined):
    for j,v in enumerate(row['videos']):
        ax.scatter(v['f1'],i+(j-5.5)*.031,s=15,color='#16282c',alpha=.62,zorder=3)
    ax.text(min(row['f1']+.018,.94),i-.31,f"{row['f1']:.4f}",fontsize=9)
ax.set(yticks=indices,yticklabels=[r['label'] for r in combined],xlim=(0,1),
       xlabel='F1 de centros a 10 px',title='Refinamento: média e valores dos 12 vídeos')
bx.barh(indices[:5],[r['detection_ms'] for r in rows],color=colors[:5],height=.52)
bx.text(0,5,'Referência não reexecutada',va='center',fontsize=9,color='#8a481e')
bx.set(yticks=indices,yticklabels=[],xlabel='Tempo médio de detecção (ms/quadro)',
       title='Custo atual do detector com imagem em cache')
for item in (ax,bx):
    item.set_facecolor('#fbfaf6'); item.set_ylim(-.55,5.55); item.invert_yaxis(); item.grid(axis='x',alpha=.18)
    item.set_axisbelow(True); item.spines[['top','right']].set_visible(False)
fig.suptitle('Refinamento dos detectores clássicos — seleção no treino',x=.045,ha='left',fontweight='bold',fontsize=15)
fig.text(.045,.03,'Melhor configuração da grade por família; 48 quadros por vídeo. Pontos = vídeos; barras = médias com peso igual.\n'
         'T218 vem da busca anterior nos mesmos quadros. Esforço desigual; sem validação comparativa ou promoção.',fontsize=9,color='#435156')
fig.tight_layout(rect=(.025,.105,.985,.91))
for ext in ('png','svg'):
    fig.savefig(out/f'refinamento_classicos_treino.{ext}',dpi=170,facecolor=fig.get_facecolor())
plt.close(fig)
summary = {'scope':'descriptive_training_local_refinement','source_manifest':manifest_path.relative_to(ROOT).as_posix(),
    'source_manifest_sha256':digest(manifest_path),'verification':qa_path.relative_to(ROOT).as_posix(),
    'verification_sha256':digest(qa_path),'run_commit':manifest['git_sha'],'batch_summary':manifest['summary'],
    'elapsed_seconds':manifest['elapsed_seconds'],'qa_counts':{k:qa[k] for k in ('files_checked','comparisons','numeric_comparisons','scipy_matchings','maximum_numeric_difference')},
    'best_per_family':rows,'historical_threshold':reference,'prior_summary':prior_path.relative_to(ROOT).as_posix(),
    'prior_summary_sha256':digest(prior_path),'figures':{p.name:digest(p) for p in sorted(out.glob('refinamento_classicos_treino.*'))}}
with (out/'summary.json').open('x',encoding='utf-8') as stream:
    json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False)
print(json.dumps({'output':str(out),'best_per_family':[{k:r[k] for k in ('family','configuration_id','f1','previous_f1','delta_f1','detection_ms')} for r in rows]},ensure_ascii=False))
