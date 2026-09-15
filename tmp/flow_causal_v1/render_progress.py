"""Render checked smoke outputs; no raw video/GT and no new experiments."""
from pathlib import Path
import argparse
import json
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser=argparse.ArgumentParser()
parser.add_argument('--run',required=True)
parser.add_argument('--verification',required=True)
args=parser.parse_args()
root=Path.cwd(); run=Path(args.run)
manifest=json.loads((run/'manifest.json').read_text())
verification=json.loads(Path(args.verification).read_text())
assert manifest['status']=='complete' and verification['status']=='passed'
out=root/'data/derived/flow/reports/farneback_causal_smoke_v1_20260909'
out.mkdir(parents=True,exist_ok=False)
rows=manifest['summary']['videos']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,2,figsize=(13,10),gridspec_kw={'height_ratios':[1.4,1]})
fig.suptitle('Farnebäck causal: primeiro smoke no treino',fontsize=18,x=.075,ha='left',y=.97)
fig.text(.075,.935,'Vídeos 11/12 · quadros 0–19 · origem 19 · uma configuração fixa · sem predição',fontsize=11,color='#52615a')
for col,row in enumerate(rows):
    folder=run/'by_video'/row['video_id']
    gray=np.load(folder/'frames/000018.npy',allow_pickle=False)
    index=json.loads((folder/'pair_index.json').read_text())
    pair=index['pairs'][18]
    path=folder/'pairs'/pair['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==pair['sha256']
    with np.load(path,allow_pickle=False) as arrays:
        flow=arrays['forward'];valid=arrays['forward_valid']
    ax=axes[0,col]
    ax.imshow(gray,cmap='gray',vmin=0,vmax=255,origin='upper')
    y,x=np.mgrid[12:480:24,12:640:24]
    use=valid[y,x]
    ax.quiver(x[use],y[use],flow[y,x,0][use],flow[y,x,1][use],angles='xy',scale_units='xy',scale=.2,
              color='#24d6b4',width=.0032,headwidth=3,headlength=4)
    ax.set_title(f"Vídeo {row['video_id']} · campo 18→19 sobre o quadro 18",fontsize=11,pad=10)
    ax.set_xlabel(f"{row['selected_windows']} janelas GT · {row['valid_feature_rows']}/{row['feature_rows']} amostras válidas",fontsize=9)
    ax.set_xticks([]);ax.set_yticks([])
colors=['#347e6e','#4776a8']; names=['Vídeo '+r['video_id'] for r in rows]; x=np.arange(2)
for ax,keys,labels,title,ylabel in [
 (axes[1,0],['photometric_zero_mae','photometric_warp_mae'],['Deslocamento zero','Após warp'],
  'Fotometria no mesmo suporte','Erro absoluto de intensidade (0–1)'),
 (axes[1,1],['forward_backward_mae','advected_temporal_mean_change'],['Ida e volta (FB)','Mudança temporal'],
  'Diagnósticos de movimento aparente','Pixels por par')]:
    for j,(key,label) in enumerate(zip(keys,labels)):
        values=[r['metrics'][key]['mean_equal_pairs_with_support'] for r in rows]
        bars=ax.bar(x+(j-.5)*.34,values,width=.32,label=label,color=colors[j],zorder=3)
        ax.bar_label(bars,labels=[f'{v:.4f}'.replace('.',',') for v in values],padding=4,fontsize=9)
    ax.set_xticks(x,names);ax.set_title(title,fontsize=12,pad=16);ax.set_ylabel(ylabel)
    ax.grid(axis='y',alpha=.16,zorder=0);ax.legend(frameon=False,fontsize=9,loc='upper left')
    ax.set_ylim(0,ax.get_ylim()[1]*1.26)
fig.text(.075,.063,'Setas: deslocamentos ampliados 5× para visualização, amostrados em uma grade de 24 pixels; não são trajetórias previstas.',fontsize=9)
fig.text(.075,.043,'Barras: médias descritivas entre pares com suporte dentro de cada vídeo. Cobertura numérica não demonstra acurácia.',fontsize=9)
fig.text(.075,.023,'O smoke verifica causalidade e integridade. Não mede velocidade do fluido, generalização ou ganho de ADE/FDE.',fontsize=9)
fig.subplots_adjust(left=.075,right=.975,top=.89,bottom=.14,hspace=.32,wspace=.28)
fig.savefig(out/'smoke_fluxo_causal.png',dpi=150,facecolor='white')
fig.savefig(out/'smoke_fluxo_causal.svg',facecolor='white')
plt.close(fig)
(out/'provenance.json').write_text(json.dumps({'source_run':str(run),'run_manifest_sha256':hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest(),
 'verification':str(args.verification),'verification_sha256':hashlib.sha256(Path(args.verification).read_bytes()).hexdigest(),
 'new_experiment':False,'raw_sources_read':False,'visual_review':'pending','arrow_magnification':5,'arrow_grid_pixels':24},indent=2)+'\n')
print(out/'smoke_fluxo_causal.png')
