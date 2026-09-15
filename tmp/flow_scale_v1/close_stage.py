from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
state=json.loads((ROOT/'tmp/flow_scale_v1/result_state.json').read_text(encoding='utf-8'))
doc_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert doc_commit=='400cc2d0ed042a27ae88e8c4a81d2d9ae2da7981'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
out=ROOT/'data/derived/project_audits/general_20260909/compact_flow_level8a_completion_20260909'
out.mkdir(parents=True,exist_ok=True)
receipt=out/'completion.json';assert not receipt.exists()
for name in ('AGENTS.md','docs/projeto/NAVEGACAO.md'):
    p=ROOT/name;s=p.read_text(encoding='utf-8')
    marker='Registro atual: **nível 8a concluído e conferido — 09/09/2026**.'
    addition='\nResultados documentados em `'+doc_commit+'`, com Git limpo ao concluir.\nEsse commit documental não altera a proveniência da run/código em `6110c44`.\n'
    s=s.replace(marker,marker+addition,1).replace('remover fator2','remover o fator 2').replace('min) >7.200','min) > 7.200')
    if name.startswith('docs/'):
        s+='''
A edição final do nível 8a tem 15 capítulos, cinco figuras incorporadas e
915 links locais do relatório canônico conferidos. As interações passaram
em computador/celular; o atlas tem 245 links conferidos e não alarga a página
nessas telas. Alterações finais de contagem de arquivos e separador decimal
receberam conferência estática e visual direcionada; os controles interativos
permaneceram iguais. O LaTeX foi atualizado localmente, sem compilar PDF.
Evidências visuais: `tmp/tcc_report/qa_20260909_nivel8a/`.
Registro completo: [completion.json](../../data/derived/project_audits/general_20260909/compact_flow_level8a_completion_20260909/completion.json).
O HTML do nível 7 foi preservado byte a byte em
[snapshot anterior](../../data/derived/project_audits/general_20260909/compact_flow_level8a_report_20260909/level7_before_compact_5629f67773ad15e0.html).
'''
    p.write_text(s,encoding='utf-8',newline='\n')
qa_folder=ROOT/'tmp/tcc_report/qa_20260909_nivel8a'
for name in ('browser_checks.json','final_targeted_checks.json'):
    p=qa_folder/name;r=json.loads(p.read_bytes());assert r['status']=='passed'
    r['visual_review']='passed'
    r['visual_review_scope']='Opening desktop/mobile, atlas new section desktop/mobile, new figure and updated next steps inspected; no overlap or unreadable layout found.'
    if name=='browser_checks.json':
        r['subsequent_changes']='Only final navigation file counts and decimal separators; final static and targeted browser checks certify the final HTML. CSS and interactive JavaScript unchanged.'
    p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ref(p):
    p=ROOT/p if isinstance(p,str) else p
    return {'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
for key in ('manifest','verification'):
    assert ref(state[key])['sha256']==state[key+'_sha256']
old='data/derived/project_audits/general_20260909/compact_flow_level8a_report_20260909/level7_before_compact_5629f67773ad15e0.html'
assert ref(old)['sha256']=='5629f67773ad15e04092e4018c737d8a88732a713c5940c64534adbb39ff1756'
payload={
 'status':'level8a_complete_and_independently_verified_full_extraction_blocked_by_time_projection',
 'completed_at':datetime.now(timezone.utc).isoformat(),'local_scientific_date':'2026-09-09','timezone':'America/Sao_Paulo',
 'execution_commit':state['execution_commit_full'],'documentation_commit':doc_commit,
 'git_clean_at_completion':True,'source_hash':state['source_hash'],
 'code_validation':{**state['code_tests'],'command':'.venv/Scripts/python.exe -X utf8 -B -m pytest -q -m "not optional_ml and not slow"','self_test':'passed','post_documentation_link_check':{'passed':1,'seconds':.81}},
 'run':ref(state['manifest']),'verification':ref(state['verification']),'independent_qa':state['qa'],
 'benchmark_elapsed_seconds':state['benchmark_elapsed_seconds'],'resources':state['resources'],'final_run_bytes':state['final_bytes'],
 'benchmark_summary':state['summary'],
 'original_runs_preserved':True,'new_benchmark_runs':1,'real_prediction_runs':0,'hypothesis_evaluated':False,
 'reports':[ref(x) for x in ('docs/projeto/RELATORIO_COMPLETO_TCC.html','RELATORIO_COMPLETO_TCC.html','docs/projeto/mapa-tcc-didatico.html','MAPA_TCC_DIDATICO.html')],
 'guide':ref('docs/projeto/NAVEGACAO.md'),'instructions':ref('AGENTS.md'),'local_latex':ref('monografia/cap_metodo/metodo.tex'),'latex_compiled':False,
 'previous_report_snapshot':ref(old),
 'report_qa':[ref(qa_folder/name) for name in ('static_checks.json','browser_checks.json','final_targeted_checks.json')],
 'figure_provenance':ref('data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/provenance.json'),
 'figure_visual_review':ref('data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/visual_review.json'),
 'next_stage':'Register timing decomposition of decoding, forward estimation and sampling; assess controlled operational changes with numerical equivalence and resource checks, preserving parameters, cohort and original budget. Full extraction and paired causal ablation remain pending.',
 'limitations':['No independent MP4 decode or estimator rerun in QA','Non-checkpoint fields discarded; witnesses rely on registered producer provenance','Prefix does not certify full coverage or RSS','Planning time limit exceeded; no retrospective limit increase','No ADE/FDE with flow or learned model/tracking evaluation']
}
with receipt.open('x',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
print(json.dumps({'status':payload['status'],'receipt':str(receipt),'sha256':ref(receipt)['sha256'],'documentation_commit':doc_commit},ensure_ascii=False))
