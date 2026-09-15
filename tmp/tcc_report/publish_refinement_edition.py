"""Update the local explanatory edition from authenticated completed records."""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT/'tmp/tcc_report'
parser = argparse.ArgumentParser()
parser.add_argument('--dataset-manifest', type=Path, required=True)
parser.add_argument('--dataset-qa', type=Path, required=True)
args = parser.parse_args()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return Path(path).read_text(encoding='utf-8')
def load(path): return json.loads(read(path))
def write(path, text): Path(path).write_text(text,encoding='utf-8',newline='\n')
def number(value, digits=6): return f'{value:.{digits}f}'.replace('.',',')
def count(value): return f'{value:,}'.replace(',','.')
def rel(path): return Path(path).resolve().relative_to(ROOT).as_posix()
def link(path, label): return f'<a href="../../{html.escape(str(path),quote=True)}">{html.escape(label)}</a>'
def once(text, old, new):
    assert text.count(old)==1, (old[:90],text.count(old))
    return text.replace(old,new,1)

summary_path = ROOT/'data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json'
summary = load(summary_path)
assert digest(ROOT/summary['source_manifest']) == summary['source_manifest_sha256']
assert digest(ROOT/summary['verification']) == summary['verification_sha256']
run, qa = load(ROOT/summary['source_manifest']), load(ROOT/summary['verification'])
assert run['status']=='complete' and run['git_dirty'] is False and run['stage']=='refinement'
assert qa['status']=='passed' and qa['manifest_sha256']==summary['source_manifest_sha256']
assert qa['parent_parity']['status']=='passed' and qa['parent_parity']['controls']==10
dm_path, dq_path = args.dataset_manifest.resolve(),args.dataset_qa.resolve()
dm,dq = load(dm_path),load(dq_path)
assert dm['status']=='complete' and dm['git_dirty'] is False and dm['training_allowed'] is False
assert dq['status']=='passed' and dq['manifest_sha256']==digest(dm_path)
assert dq['summary']['copied_file_count']==46632 and dq['summary']['copied_jpegs_decoded']==23316
assert dq['summary']['test_sources_traversed'] is False
source_metadata_binding=dm['artifacts']['source_metadata']
assert digest(source_metadata_binding['path'])==source_metadata_binding['sha256']
sidecar_count=len(load(source_metadata_binding['path'])['excluded_legacy_sidecars'])
rows=summary['best_per_family']
parents_path=ROOT/summary['source_manifest']
parents_path=parents_path.parent/'parents.json'
assert digest(parents_path)==run['artifact_hashes']['parents.json']
parents_by_id={p['configuration_id']:p for p in load(parents_path)}
table='<table><thead><tr><th>Família</th><th>Melhor configuração local</th><th>F1 anterior</th><th>F1 refinado</th><th>Precisão</th><th>Recall</th><th>ms/quadro</th></tr></thead><tbody>'
for row in rows:
    table+='<tr><td>'+html.escape(row['label'])+'</td><td>'+link(row['manifest'],row['configuration_id'])+'</td>'+''.join('<td>'+number(row[k],3 if k=='detection_ms' else 6)+'</td>' for k in ('previous_f1','f1','precision','recall','detection_ms'))+'</tr>'
table+='</tbody></table><p>“F1 anterior” é a melhor configuração da primeira busca dentro da mesma família. Incluir os pais garante que o refinamento possa conservar essa configuração; um ganho local continua sendo seleção no treino.</p>'
table+='<details><summary>Resultados por vídeo e sensibilidades de distância</summary><table><thead><tr><th>Vídeo</th>'+''.join('<th>'+r['label']+'</th>' for r in rows)+'</tr></thead><tbody>'
for video in [v['video_id'] for v in rows[0]['videos']]:
    table+='<tr><td>'+video+'</td>'+''.join('<td>'+number(next(v['f1'] for v in r['videos'] if v['video_id']==video),4)+'</td>' for r in rows)+'</tr>'
table+='</tbody></table><table><thead><tr><th>Família</th><th>F1 a 15 px</th><th>F1 a 20 px</th><th>Previsões ignoradas a 10 px</th></tr></thead><tbody>'
for row in rows:
    table+='<tr><td>'+row['label']+'</td><td>'+number(row['f1_15px'])+'</td><td>'+number(row['f1_20px'])+'</td><td>'+count(row['n_predictions_ignored'])+'</td></tr>'
table+='</tbody></table><p>Aumentar o raio relaxa a tolerância espacial; os valores de 15/20 px não substituem o critério principal registrado de 10 px. Ignorados são contabilizados depois de proteger os indivíduos contra detecções duplicadas.</p></details>'
table+='<details><summary>Quais parâmetros produziram essas configurações?</summary><table><thead><tr><th>Família</th><th>Pai na primeira busca</th><th>Alteração local</th></tr></thead><tbody>'
axis_names={'morph_iterations':'Iterações de abertura','clip_limit':'Limite do CLAHE','blur':'Tamanho do kernel de suavização'}
for row in rows:
    for origin in row['lineage']:
        parent=parents_by_id[origin['parent_configuration_id']]
        axis=origin['axis']
        change='Configuração pai preservada, sem alteração de parâmetros.' if axis is None else axis_names.get(axis,axis)+': '+str(parent['params'][axis]).replace('.',',')+' → '+str(row['params'][axis]).replace('.',',')
        table+='<tr><td>'+row['label']+'</td><td><code>'+html.escape(parent['configuration_id'])+'</code></td><td>'+html.escape(change)+'</td></tr>'
table+='</tbody></table><p>Os demais parâmetros do pai foram mantidos. A linha registra a mudança observada na grade; não demonstra que essa escolha será melhor em novos vídeos. As configurações completas estão nos manifestos vinculados na tabela principal.</p></details>'
results=f'<p><strong>Refinamento concluído e conferido:</strong> 45 configurações × 576 quadros. Foram registradas duas finalistas por família, totalizando dez. A maior média desta grade foi {html.escape(rows[0]["label"])} com F1 {number(rows[0]["f1"])}; isso não escolhe o detector final.</p>'+table
evidence=f'<p>Execução em <code>{html.escape(run["git_sha"])}</code>, com Git limpo e proveniência revalidada. Duração da bateria: {number(run["elapsed_seconds"],3)} s, após autenticações iniciais registradas separadamente; pico de RSS amostrado: {number(run["summary"]["ram_rss_peak_mb"],3)} MiB. Artefatos das candidatas: {count(run["summary"]["candidate_artifact_bytes"])} bytes, sem os arquivos do agregador.</p>'
evidence+=f'<p>Conferência independente: {count(qa["files_checked"])} arquivos, {count(qa["comparisons"])} comparações e {count(qa["scipy_matchings"])} matchings SciPy. Paridade aprovada para os dez pais nos mesmos 576 quadros. A maior diferença numérica foi {html.escape(str(qa["maximum_numeric_difference"]))}.</p>'
evidence+='<p>'+link(summary['source_manifest'],'Manifesto do refinamento')+' · '+link(summary['verification'],'Conferência independente')+' · '+link(str(Path(summary['source_manifest']).parent/'family_finalists.json').replace('\\','/'),'As dez finalistas')+' · <a href="../metodologia/REFINAMENTO_CLASSICOS_V1.md">Plano, lógica e recursos</a>.</p>'
dataset=f'<p><strong>Dataset materializado e conferido:</strong> 17.466 pares de treino e 5.850 de validação, totalizando 23.316 imagens e 23.316 arquivos de rótulos. As 174 lacunas de anotação do vídeo 23 foram excluídas. As fontes locais permaneceram inalteradas, e os {count(sidecar_count)} caches NPY históricos foram inventariados e excluídos da cópia.</p>'
dataset+=f'<p>A preparação durou {number(dm["elapsed_seconds"],3)} s, registrou {number(dm["summary"]["resources"]["ram_rss_peak_mb"],3)} MiB de RSS amostrado e produziu {count(dq["summary"]["run_bytes"])} bytes finais. A conferência independente decodificou as 23.316 cópias JPEG, verificou hashes e constatou paridade das caixas YOLO com a referência FTID. Os pixels das fontes não foram decodificados por essa conferência. Não houve acesso ao teste ou treinamento.</p>'
dataset+='<p>'+link(rel(dm_path),'Manifesto da preparação')+' · '+link(rel(dq_path),'QA do dataset')+' · <a href="../metodologia/DATASET_YOLO_V1.md">Contrato e interpretação</a> · <a href="../../script/README.md#dataset-yolo-v1">Comandos oficiais</a>.</p>'
fragment=read(PARTS/'classical_refinement_template.html')
for key,value in {'REFINEMENT_RESULTS':results,'REFINEMENT_EVIDENCE':evidence,'YOLO_DATASET_RESULTS':dataset}.items():
    fragment=once(fragment,'{{'+key+'}}',value)
assert fragment.count('{{FIG_REFINEMENT}}')==1
core=read(PARTS/'core.html')
core=once(core,'<div id="comparacao-classicos-20260911">',fragment+'\n<div id="comparacao-classicos-20260911"><p class="source"><strong>Histórico: primeira busca, anterior ao refinamento acima.</strong> O roteiro ao fim deste bloco registra a continuidade prevista quando essa busca terminou; consulte o marco atual acima para o que já avançou.</p>')
core=re.sub(r'<div class="callout"><strong>Avanço de 11/09:</strong>.*?</div>', '<div class="callout"><strong>Avanço de 11/09:</strong> refinamento de 45 configurações concluído e conferido no treino; dataset YOLO preparado e autenticado. <a href="#refinamento-classicos-20260911">Resultados e interpretação</a>. Validação completa e treinamento continuam sendo as próximas etapas.</div>',core,count=1,flags=re.S)
core=core.replace('<h3>Refinar e validar os demais detectores</h3><p>A primeira busca comparativa de seis famílias terminou e foi conferida em 11/09. Seguem refinamento, validação completa e YOLO, antes de escolher a cadeia de tracking e predição.</p>','<h3>Validar as finalistas e treinar YOLO</h3><p>Busca e refinamento clássicos passaram pela conferência. O dataset YOLO também está pronto. A próxima etapa compara as finalistas nos vídeos completos e prepara o treinamento aprendido, antes da escolha para tracking e predição.</p>')
write(PARTS/'core.html',core)
closing=read(PARTS/'closing.html')
pattern=r'(<section id="proximos"[^>]*>).*?(<h3>A hipótese do fluxo continua no plano</h3>)'
next_list='<ol><li>Registrar e executar a validação das dez finalistas clássicas nos quatro vídeos completos; autenticar T218 como referência histórica.</li><li>Preparar a receita e o executor de treinamento YOLO sobre cópia independente do dataset autenticado; depois avaliar sob o mesmo contrato v3.</li><li>Executar a comparação temporal MOG2/KNN com reinício por vídeo e aquecimento.</li><li>Comparar rastreadores com detecções comuns e métricas de identidade; avaliar predição sobre trajetórias estimadas e a ablação causal do fluxo.</li></ol>'
new_next='<div class="eyebrow">Continuidade após o refinamento</div><h2>Onde paramos e para onde vamos</h2><p><strong>Busca e refinamento clássicos concluídos no treino; dataset YOLO materializado e conferido.</strong> Ainda faltam validação comparativa completa e treinamento aprendido antes da escolha do detector. Rastreamento e predição terão avaliações próprias.</p>'+next_list
closing,n=re.subn(pattern,lambda m:m[1]+new_next+m[2],closing,count=1,flags=re.S)
assert n==1
closing=closing.replace('Comparação e próximo refinamento','Histórico da primeira comparação')
write(PARTS/'closing.html',closing)
reading=read(PARTS/'reading_guide.html')
reading=reading.replace('A entrega mais recente é a <a href="#comparacao-classicos-20260911">busca comparativa de detectores no treino</a>. Acompanhe o refinamento e a validação das novas famílias, a preparação do YOLO e, depois, as comparações de tracking/predição.','A entrega mais recente é o <a href="#refinamento-classicos-20260911">refinamento dos detectores no treino e o dataset YOLO conferido</a>. Acompanhe a validação completa das finalistas, o treinamento YOLO e, depois, as comparações de tracking/predição.')
write(PARTS/'reading_guide.html',reading)
nav=read(PARTS/'navigation.html')
nav_extra='<div id="pastas-refinamento-yolo"><h3>Novos caminhos: refinamento e dataset YOLO</h3><ul>'+''.join('<li>'+link(path,label)+'</li>' for path,label in [
    ('src/experiments/classical_detection_refinement.py','Refinamento: biblioteca e controles'),('configs/detection/comparison/classical_refinement_v1.yaml','Grade prospectiva de 45 configurações'),('script/detection/test/refine_classical.py','CLI de smoke/refinamento'),('script/detection/test/verify_classical_refinement.py','Conferência independente do refinamento'),('src/detection/yolo_dataset.py','Cópia e autenticação do dataset YOLO'),('configs/detection/yolo/dataset_v1.yaml','Contrato de dados YOLO'),('script/detection/test/yolo/prepare_dataset.py','CLI de planejamento/materialização')])+'</ul><p>O agregador do refinamento está em <code>data/tests/detection/classical_refinement/</code>; as saídas de cada método continuam em sua família. O dataset está em <code>data/datasets/yolo/materialized/</code>. Fontes recebidas permanecem em <code>data/sources/</code>. Use os <a href="../../script/README.md#refinamento-classicos-v1">comandos oficiais</a> e consulte <a href="#refinamento-classicos-20260911">o resultado e os manifestos</a> antes de iniciar uma nova etapa.</p></div>'
nav=once(nav,'<h2>Pastas, arquivos e caminhos do código</h2>','<h2>Pastas, arquivos e caminhos do código</h2>'+nav_extra)
write(PARTS/'navigation.html',nav)

# Retain the old authenticated pins; add independent guards for the new edition.
builder=read(PARTS/'build_report.py')
guards=f'''REFINEMENT_RESULT_PATH = ROOT / {rel(summary_path)!r}
assert sha(REFINEMENT_RESULT_PATH) == {digest(summary_path)!r}
refinement_result = json.loads(REFINEMENT_RESULT_PATH.read_text(encoding="utf-8"))
assert sha(ROOT / refinement_result["source_manifest"]) == refinement_result["source_manifest_sha256"]
assert sha(ROOT / refinement_result["verification"]) == refinement_result["verification_sha256"]
for filename, expected_hash in refinement_result["figures"].items():
    assert sha(REFINEMENT_RESULT_PATH.parent / filename) == expected_hash
assert sha(ROOT / {rel(dm_path)!r}) == {digest(dm_path)!r}
assert sha(ROOT / {rel(dq_path)!r}) == {digest(dq_path)!r}
'''
builder=once(builder,"core=read('core.html')",guards+"\ncore=read('core.html')\ncore=core.replace('{{FIG_REFINEMENT}}',figure('data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/refinamento_classicos_treino.png','F1 por vídeo e média de cada família após refinamento; referência T218 histórica.','Seleção no treino, 45 configurações e esforço desigual. Pontos são vídeos; custo atual apenas dos cinco métodos reexecutados. T218 provém da busca anterior.'))")
builder=builder.replace("latest_completed_milestone='classical_detection_training_comparison_v1'","latest_completed_milestone='classical_refinement_and_yolo_dataset_v1'")
builder=builder.replace("next_proposed_milestone='classical_refinement_full_validation_and_yolo_training'","next_proposed_milestone='classical_full_validation_and_yolo_training'")
metadata={'summary':rel(summary_path),'summary_sha256':digest(summary_path),'manifest':summary['source_manifest'],'manifest_sha256':summary['source_manifest_sha256'],'verification':summary['verification'],'verification_sha256':summary['verification_sha256'],'run_commit':run['git_sha'],'evaluations':25920}
dataset_metadata={'manifest':rel(dm_path),'manifest_sha256':digest(dm_path),'verification':rel(dq_path),'verification_sha256':digest(dq_path),'run_commit':dm['git_sha'],'images':23316,'trained':False}
builder=once(builder,'meta_json=json.dumps(meta,ensure_ascii=False)',f'meta.update(classical_refinement={metadata!r}, yolo_dataset={dataset_metadata!r})\nmeta_json=json.dumps(meta,ensure_ascii=False)')
builder=builder.replace('Comparação clássica no treino concluída','Refinamento clássico e dataset YOLO conferidos')
builder=builder.replace('Refinamento clássico e dataset YOLO conferidos e conferida em 11/09.','Refinamento clássico e dataset YOLO concluídos e conferidos em 11/09.')
builder=builder.replace('Próximas etapas: refinamento, validação e YOLO, antes da escolha da pipeline.','Próximas etapas: validação completa e treinamento YOLO, antes da escolha da pipeline.')
builder=builder.replace('Comparação clássica no treino concluída e conferida em 11/09.','Refinamento clássico e dataset YOLO concluídos e conferidos em 11/09.')
write(PARTS/'build_report.py',builder)

atlas_path=ROOT/'docs/projeto/mapa-tcc-didatico.html'
atlas=read(atlas_path)
atlas_new='<section id="refinamento-classicos-atual" class="section"><h2>11/09: refinamento clássico e dataset YOLO conferidos</h2><p>45 configurações únicas, cinco famílias, 576 quadros de treino e 25.920 avaliações. Os dez pais reproduziram suas saídas anteriores; dez finalistas seguem para validação em vídeos completos.</p><ul>'+''.join('<li>'+r['label']+': F1 macro '+number(r['f1'])+'</li>' for r in rows)+'</ul><p>Seleção no treino, com esforço desigual. T218 é referência histórica, sem nova execução. O dataset YOLO possui 23.316 pares autenticados de treino/validação; ainda não houve treinamento. Não existe escolha final do detector, HOTA real atual ou resultado da hipótese com fluxo.</p><p><a href="RELATORIO_COMPLETO_TCC.html#refinamento-classicos-20260911">Tabela, figura, lógica e evidências completas</a> · <a href="../metodologia/REFINAMENTO_CLASSICOS_V1.md">Protocolo do refinamento</a> · <a href="../metodologia/DATASET_YOLO_V1.md">Dataset YOLO</a>.</p></section>'
atlas=once(atlas,'<section id="comparacao-classicos-atual"',atlas_new+'\n<section id="comparacao-classicos-atual"')
atlas=once(atlas,'<nav class="toc" id="toc">','<nav class="toc" id="toc"><a href="#refinamento-classicos-atual">Atual: refinamento e dataset YOLO</a><a href="#comparacao-classicos-atual">Histórico: primeira comparação</a><a href="#continuidade-20260911">Próximas etapas</a>')
atlas=atlas.replace('<h2>11/09: primeira comparação clássica concluída no treino</h2>','<h2>Histórico de 11/09: primeira comparação clássica no treino</h2>')
atlas,n=re.subn(r'(<section id="continuidade-20260911"[^>]*>).*?(</section>)',lambda m:m[1]+'<h2>Próximas etapas: validação completa e treinamento YOLO</h2>'+next_list+'<p>A ablação causal nas 10.848 janelas permanece prevista. <a href="RELATORIO_COMPLETO_TCC.html#proximos">Sequência completa e limites</a>.</p>'+m[2],atlas,count=1,flags=re.S)
assert n==1
atlas=atlas.replace('Comparação clássica no treino conferida · 11/09/2026','Refinamento e dataset YOLO conferidos · 11/09/2026')
atlas=atlas.replace('19 capítulos, seis figuras e quatro laboratórios','19 capítulos, sete figuras e quatro laboratórios')
atlas=atlas.replace('19 capítulos, cinco figuras científicas e quatro laboratórios didáticos','19 capítulos, sete figuras científicas e quatro laboratórios didáticos')
atlas=atlas.replace('Em detecção, a busca comparativa de seis famílias foi concluída e conferida em 11/09.','Em detecção, a busca e o refinamento foram concluídos e conferidos em 11/09; o dataset YOLO também foi materializado e autenticado.')
atlas=atlas.replace('Leitura orientada · edição de 10/09/2026','Leitura orientada · edição ampliada em 11/09/2026')
atlas=atlas.replace('<a href="#comparacao-classicos-atual">resumo de 11/09</a>','<a href="#refinamento-classicos-atual">resumo atual de 11/09</a>')
atlas=atlas.replace('<a href="#comparacao-classicos-atual">comparação de detecção conferida em 11/09</a>','<a href="#refinamento-classicos-atual">comparação de detecção e refinamento conferidos em 11/09</a>')
write(atlas_path,atlas)
print(json.dumps({'status':'components_updated','report_build':'pending','scientific_inputs_authenticated':True}))
