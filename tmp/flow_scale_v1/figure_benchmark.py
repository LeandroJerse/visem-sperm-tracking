"""Plot authenticated benchmark summaries; no original source or model access."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
state=json.loads((ROOT/'tmp/flow_scale_v1/result_state.json').read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=ROOT/state['manifest']
qa=ROOT/state['verification']
assert sha(manifest)==state['manifest_sha256'] and sha(qa)==state['verification_sha256']
m=json.loads(manifest.read_bytes()); q=json.loads(qa.read_bytes())
assert m['status']=='complete' and not m['git_dirty'] and q['status']=='passed'
s=m['summary']; rows=s['videos']; p=s['projection']
assert s['prediction_evaluated'] is False and s['full_extraction_released'] is False
out=ROOT/'data/derived/flow/reports/farneback_compact_benchmark_v1_20260909'
out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig, axes=plt.subplots(1,3,figsize=(15.2,7.2),gridspec_kw={'width_ratios':[1.15,1,1]})
fig.subplots_adjust(left=.055,right=.985,bottom=.29,top=.76,wspace=.35)
y=np.arange(len(rows)); labels=[r['video_id'] for r in rows]
blue,orange,gray='#137b88','#d98130','#93a8ad'
axes[0].barh(y-.18,[r['historical_uses'] for r in rows],height=.34,color=gray,label='Usos nas janelas')
axes[0].barh(y+.18,[r['unique_samples'] for r in rows],height=.34,color=blue,label='Amostras distintas')
axes[0].set_title('Uma amostra atende várias janelas',loc='left',fontsize=11,fontweight='bold')
axes[0].set_xlabel('Contagem no prefixo'); axes[0].legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.13),fontsize=9)
axes[0].ticklabel_format(axis='x',style='sci',scilimits=(4,4))
for key,color,label in [('loop_seconds',blue,'Laço'),('table_seconds',gray,'Tabelas / hashes'),('checkpoint_seconds',orange,'Sentinelas')]:
    left=np.zeros(len(rows)) if key=='loop_seconds' else (np.array([r['loop_seconds'] for r in rows]) if key=='table_seconds' else np.array([r['loop_seconds']+r['table_seconds'] for r in rows]))
    axes[1].barh(y,[r[key] for r in rows],left=left,color=color,height=.65,label=label)
axes[1].set_title('Custo observado por vídeo',loc='left',fontsize=11,fontweight='bold')
axes[1].set_xlabel('Segundos · parcelas variáveis')
axes[1].legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.13),fontsize=9,ncol=1)
compact=np.array([r['compact_bytes']/1024**2 for r in rows])
axes[2].barh(y,compact,height=.65,color=blue,label='Tabelas / testemunhos')
axes[2].barh(y,[r['checkpoint_bytes']/1024**2 for r in rows],left=compact,height=.65,color=orange,label='Campos / cinzas sentinelas')
axes[2].set_title('Armazenamento observado',loc='left',fontsize=11,fontweight='bold')
axes[2].set_xlabel('MiB · antes dos resumos')
axes[2].legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.13),fontsize=9)
for ax in axes:
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_axisbelow(True);ax.grid(axis='x',alpha=.17);ax.set_xlim(left=0)
axes[0].set_ylabel('Vídeo de treino')
fmt=lambda v:f'{v:,.0f}'.replace(',','.')
fig.text(.055,.95,'Fluxo causal compacto · benchmark de engenharia',fontsize=18,fontweight='bold',color='#183b3d')
fig.text(.055,.897,f"12 treinos · quadros 0–59 · {fmt(s['windows'])} janelas · {fmt(s['unique_samples'])} amostras distintas · {fmt(s['historical_uses'])} usos",fontsize=11)
fig.text(.055,.849,f"Projeção com fator 2: {p['projected_seconds']/60:.1f} min e {p['projected_artifact_bytes']/1024**2:.1f} MiB — tempo acima do teto de 120 min; extração completa bloqueada".replace('.',','),fontsize=10,color='#425b60')
fig.text(.055,.035,'Conferência independente dos derivados aprovada. O custo fixo e os resumos não entram nas barras por vídeo.\nOs prefixos não certificam cobertura ou RAM dos vídeos completos. Sem ADE/FDE, seleção ou medida de velocidade física.',fontsize=9,color='#425b60',linespacing=1.6)
for ext in ('png','svg'):fig.savefig(out/f'benchmark_fluxo_compacto.{ext}',dpi=160,facecolor='#ffffff')
plt.close(fig)
payload={'status':'derived_from_audited_benchmark','created_at':datetime.now(timezone.utc).isoformat(),
    'manifest':state['manifest'],'manifest_sha256':sha(manifest),'verification':state['verification'],
    'verification_sha256':sha(qa),'execution_commit':m['git_sha'],'original_source_reads':False,
    'new_model_runs':0,'data':s,'figures':[{'path':str(f.relative_to(ROOT)).replace('\\','/'),'sha256':sha(f),'bytes':f.stat().st_size} for f in [out/'benchmark_fluxo_compacto.png',out/'benchmark_fluxo_compacto.svg']],
    'visual_review':'pending'}
(out/'provenance.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'figure':str(out/'benchmark_fluxo_compacto.png'),'status':'ready_for_visual_review'},ensure_ascii=False))
