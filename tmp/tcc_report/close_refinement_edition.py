"""Close the local scientific/editorial record after a clean documentary commit."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--dataset-manifest',type=Path,required=True)
parser.add_argument('--dataset-qa',type=Path,required=True)
args=parser.parse_args()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def relative(path):return Path(path).resolve().relative_to(ROOT).as_posix()
def git(*command):return subprocess.run(['git',*command],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
assert not git('status','--porcelain')
head=git('rev-parse','HEAD')
assert head!='ca68f16ef5ca4ef8fae91b85cb8a00bc132bbd0d'
committed=git('diff-tree','--no-commit-id','--name-only','-r',head).splitlines()
assert committed and not any(p.endswith('.html') or p.startswith('monografia/') or p in {'AGENTS.md','docs/projeto/NAVEGACAO.md'} for p in committed)
summary_path=ROOT/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json'
summary=load(summary_path)
run_path,qa_path=ROOT/summary['source_manifest'],ROOT/summary['verification']
assert sha(run_path)==summary['source_manifest_sha256'] and sha(qa_path)==summary['verification_sha256']
run,qa=load(run_path),load(qa_path)
assert run['status']=='complete' and run['git_dirty'] is False and qa['status']=='passed'
dm,dq=load(args.dataset_manifest),load(args.dataset_qa)
assert dm['status']=='complete' and dm['git_dirty'] is False and dq['status']=='passed'
assert dq['manifest_sha256']==sha(args.dataset_manifest)
assert run['git_sha']==dm['git_sha']=='ca68f16'
assert run['source_hash']==dm['source_hash']=='f2ecb55da1bf19ff1fd2247f0e196d30f064fc95fc399c6b465c805c219a8766'
qa_dir=ROOT/'tmp/tcc_report/qa_20260911_refinement'
for name in ('static_checks.json','browser_checks.json','visual_review.json','documentation_links_retry1.json'):
    assert load(qa_dir/name)['status']=='passed'
figure_dir=summary_path.parent
assert load(figure_dir/'visual_review.json')['status']=='passed'
for filename,digest in summary['figures'].items():assert sha(figure_dir/filename)==digest
for name in ('AGENTS.md','docs/projeto/NAVEGACAO.md'):
    path=ROOT/name
    text=path.read_text(encoding='utf-8')
    marker='<!-- refinement-dataset-completion-20260911 -->'
    assert text.count(marker)==1
    note=f'\n\nResultados documentados em `{head}`, com Git limpo ao concluir.\nEsse commit documental não altera a proveniência das runs em `ca68f16`.\nA edição local foi conferida: 19 capítulos, sete figuras e quatro laboratórios,\ncom QA estático, navegação e revisão visual. Registro da entrega:\n`data/derived/project_audits/general_20260911/classical_refinement_edition/completion.json`.\n'
    text=text.replace(marker,marker+note,1)
    text=text.replace('o commit documental final será registrado no fechamento.', 'o commit documental final está registrado no início desta seção.')
    if name.endswith('NAVEGACAO.md'):
        text+='\n\nNotas preparatórias locais para o próximo marco: '
        notes=['classical_full_validation_design_v1.md','yolo_training_design_v1.md']
        for filename in notes:
            assert (ROOT/'tmp/tcc_report'/filename).is_file()
        text+=' · '.join(f'[{filename}](../../tmp/tcc_report/{filename})' for filename in notes)
        text+='. São propostas de implementação, sem autorização executável por si mesmas; a nota clássica antecede a conclusão da run acima. O próximo contrato deve vincular as dez finalistas e os hashes agora conferidos.\n'
    path.write_text(text,encoding='utf-8',newline='\n')
files=[summary_path,figure_dir/'visual_review.json',qa_dir/'static_checks.json',qa_dir/'browser_checks.json',qa_dir/'visual_review.json']
files += [qa_dir/'documentation_links_initial_failure.json',qa_dir/'documentation_links_retry1.json',qa_dir/'documentation_links_retry1.log']
files += [ROOT/p for p in ('AGENTS.md','docs/projeto/NAVEGACAO.md','docs/projeto/RELATORIO_COMPLETO_TCC.html','docs/projeto/mapa-tcc-didatico.html','RELATORIO_COMPLETO_TCC.html','MAPA_TCC_DIDATICO.html','monografia/cap_metodo/metodo.tex','monografia/cap_conclusao/conclusao.tex')]
receipt={'status':'complete','created_at':datetime.now(timezone.utc).isoformat(),'documentation_commit':head,'git_clean':True,
 'scientific_commit':'ca68f16ef5ca4ef8fae91b85cb8a00bc132bbd0d','scientific_source_hash':run['source_hash'],
 'refinement':{'manifest':relative(run_path),'manifest_sha256':sha(run_path),'qa':relative(qa_path),'qa_sha256':sha(qa_path),'summary':run['summary'],'elapsed_seconds':run['elapsed_seconds'],'qa_counts':{k:qa[k] for k in ('files_checked','comparisons','numeric_comparisons','scipy_matchings','maximum_numeric_difference','elapsed_seconds')}},
 'yolo_dataset':{'manifest':relative(args.dataset_manifest),'manifest_sha256':sha(args.dataset_manifest),'qa':relative(args.dataset_qa),'qa_sha256':sha(args.dataset_qa),'summary':dm['summary'],'elapsed_seconds':dm['elapsed_seconds'],'qa_summary':dq['summary']},
 'files':{relative(p):sha(p) for p in files},'committed_files':committed,'html_guides_manuscript_committed':False,
 'training_executed':False,'tracking_hota_executed':False,'flow_prediction_hypothesis_tested':False,
 'next_milestone':'prospective_full_validation_of_ten_classical_finalists_and_yolo_training_contract',
 'preservation':'Sources, previous scientific runs, initial plot and its required layout revision remain preserved.'}
out=ROOT/'data/derived/project_audits/general_20260911/classical_refinement_edition/completion.json'
assert not out.exists()
with out.open('x',encoding='utf-8') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False)
assert not git('status','--porcelain')
print(json.dumps({'status':'complete','documentation_commit':head,'receipt':relative(out),'git_clean':True}))
