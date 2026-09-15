"""Descriptive error comparison; use only a completed registered baseline run."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from src.core.artifacts import sha256_file,write_json_exclusive

parser=argparse.ArgumentParser()
parser.add_argument('manifest',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
manifest=json.loads(args.manifest.read_text())
assert manifest['status']=='complete'
assert manifest['summary']['status']=='complete_descriptive_training_baselines'
with (args.manifest.parent/'video_metrics.csv').open(newline='',encoding='utf-8') as stream:
    videos=list(csv.DictReader(stream))
ids=manifest['summary']['video_ids']
methods=[('persistence','Persistência','#377b6b'),('cv_median5','Velocidade constante · mediana5','#6483b1')]
rows={(r['video_id'],r['configuration_id']):r for r in videos}
macros={r['configuration_id']:r for r in manifest['summary']['methods']}
args.output.mkdir(parents=True,exist_ok=False)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
                     'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(15.6,9.6))
ys=np.arange(len(ids)+1)
figure_data=[]
for axis,metric,title in zip(axes,('ade_h10','fde_h10'),('Erro médio nos dez passos (ADE₁₀)','Erro no décimo passo (FDE₁₀)')):
    maximum=0
    for j,(method,label,color) in enumerate(methods):
        values=[float(rows[(v,method)][metric]) for v in ids]+[macros[method]['macro_'+metric]]
        maximum=max(maximum,max(values))
        axis.barh(ys+(j-.5)*.33,values,height=.31,label=label,color=color)
        for y,value in zip(ys+(j-.5)*.33,values):
            axis.annotate(f'{value:.2f}'.replace('.',','),(value,y),xytext=(4,0),
                          textcoords='offset points',va='center',fontsize=9)
        figure_data.append({'metric':metric,'configuration_id':method,'video_ids':ids+['macro_equal_videos'],'values':values})
    axis.set(yticks=ys,yticklabels=[f'Vídeo {v}' for v in ids]+['Média dos vídeos'],
             xlim=(0,maximum*1.23 if maximum else 1),xlabel='Erro em pixels · menor é melhor',title=title)
    axis.axhline(len(ids)-.5,color='#8b969f',linewidth=.8,linestyle='--')
    axis.invert_yaxis();axis.set_axisbelow(True);axis.grid(axis='x',alpha=.15)
fig.suptitle('Baselines causais sobre a referência do treino',fontsize=20,x=.045,ha='left',y=.977)
fig.text(.045,.924,'343.776 janelas comuns por método · histórico de 20 posições · futuro de 10 quadros',fontsize=12,color='#4d5865')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='lower left',bbox_to_anchor=(.038,.077),ncol=2,frameon=False,fontsize=12)
fig.text(.045,.025,'Agregação principal: média de janelas por ID original, depois IDs e vídeos com pesos iguais.\n'
         'Resultados descritivos em GT de treino. Nenhum fluxo ou erro de rastreamento é avaliado nesta figura.',fontsize=10,color='#4d5865')
fig.subplots_adjust(left=.105,right=.975,top=.86,bottom=.185,wspace=.38)
for ext in ('png','svg'):fig.savefig(args.output/f'baselines_predicao_treino.{ext}',dpi=240)
plt.close(fig)
write_json_exclusive(args.output/'figure_data.json',figure_data)
write_json_exclusive(args.output/'manifest.json',{'status':'generated_pending_visual_review',
    'source_manifest':str(args.manifest.resolve()),'source_manifest_sha256':sha256_file(args.manifest),
    'source_video_metrics_sha256':sha256_file(args.manifest.parent/'video_metrics.csv'),
    'script_sha256':sha256_file(Path(__file__)),
    'artifacts':[{'path':str(p.resolve()),'sha256':sha256_file(p)} for p in sorted(args.output.iterdir())],
    'interpretation':'training_GT_descriptive_equal_original_IDs_then_equal_videos',
    'matplotlib':matplotlib.__version__})
print(args.output)
