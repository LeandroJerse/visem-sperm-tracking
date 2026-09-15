"""Descriptive training-reference figure; never an independent-sample claim."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from src.core.artifacts import sha256_file, write_json_exclusive

parser=argparse.ArgumentParser()
parser.add_argument('manifest',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
manifest=json.loads(args.manifest.read_text())
assert manifest['status']=='complete'
rows=manifest['summary']['videos']
assert manifest['summary']['video_ids']==['11','12','13','15','21','22','23','29','30','35','60','82']
args.output.mkdir(parents=True,exist_ok=False)
data=[]
for r in rows:
    total=r['individual_observations']
    data.append({'video_id':r['video_id'],'origins_total':total,
                 'history_incomplete':total-r['origins_with_complete_history'],
                 'future_incomplete':r['origins_excluded_incomplete_future'],
                 'accepted_windows':r['windows_total'],
                 'segments_total':r['segments_total'],
                 'segments_with_windows':r['segments_with_windows']})
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,
                     'axes.spines.right':False,'svg.fonttype':'none'})
fig,(ax,bx)=plt.subplots(1,2,figsize=(15,8.4),gridspec_kw={'width_ratios':[1.25,1]})
ys=np.arange(len(data))
left=np.zeros(len(data))
for key,color,label in [('accepted_windows','#287a66','Janela aceita'),
                         ('future_incomplete','#de9b47','Futuro incompleto após histórico válido'),
                         ('history_incomplete','#a6b1be','Histórico incompleto')]:
    vals=np.array([100*r[key]/r['origins_total'] for r in data])
    ax.barh(ys,vals,left=left,color=color,label=label,height=.65)
    if key=='accepted_windows':
        for y,v in zip(ys,vals): ax.text(v/2,y,f'{v:.1f}%',ha='center',va='center',color='white',fontsize=11)
    left+=vals
ax.set(yticks=ys,yticklabels=[f"Vídeo {r['video_id']}" for r in data],xlim=(0,100),
       xlabel='Origens individuais (%)',title='Elegibilidade das origens no treino')
ax.invert_yaxis()
windows=[r['accepted_windows'] for r in data]
bx.barh(ys,windows,color='#287a66',height=.65)
for y,r in zip(ys,data):
    bx.text(r['accepted_windows']+max(windows)*.015,y,f"{r['accepted_windows']:,}".replace(',','.'),
            va='center',fontsize=11)
bx.set(yticks=ys,yticklabels=[f"Vídeo {r['video_id']}" for r in data],xlim=(0,max(windows)*1.23),
       xlabel='Janelas de 20 posições passadas + 10 futuras',title='Quantidade de janelas por vídeo')
bx.invert_yaxis()
for a in (ax,bx): a.set_axisbelow(True); a.grid(axis='x',alpha=.15)
fig.suptitle('Referência individual preservada antes dos preditores',fontsize=20,x=.055,ha='left',y=.98)
fig.text(.055,.918,'Classes 0/2 • IDs originais • stride 1 • todos os segmentos preservados',fontsize=12,color='#4d5865')
handles,labels=ax.get_legend_handles_labels()
fig.legend(handles,labels,loc='lower left',bbox_to_anchor=(.05,.075),ncol=1,frameon=False,fontsize=11)
fig.text(.055,.025,'Descrição de 12 vídeos de treino. Janelas sobrepostas não são amostras independentes.\n'
         'A elegibilidade exige GT individual futuro disponível; nenhuma métrica de predição foi calculada.',fontsize=10,color='#4d5865')
fig.subplots_adjust(left=.085,right=.98,top=.85,bottom=.25,wspace=.3)
for suffix in ('png','svg'): fig.savefig(args.output/f'trajetorias_individuais_treino.{suffix}',dpi=240)
plt.close(fig)
write_json_exclusive(args.output/'figure_data.json',data)
write_json_exclusive(args.output/'manifest.json',{'status':'generated_pending_visual_review',
    'source_manifest':str(args.manifest.resolve()),'source_manifest_sha256':sha256_file(args.manifest),
    'script':str(Path(__file__).resolve()),'script_sha256':sha256_file(Path(__file__)),
    'artifacts':[{ 'path':str(p.resolve()),'sha256':sha256_file(p)} for p in sorted(args.output.iterdir())],
    'interpretation':'descriptive_training_reference_no_predictor_no_inference',
    'matplotlib':matplotlib.__version__})
print(args.output)
