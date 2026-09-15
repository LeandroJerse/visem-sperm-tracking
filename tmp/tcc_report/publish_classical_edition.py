"""Publish authenticated comparison results, preserving all historical sections."""
from pathlib import Path
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / 'tmp/tcc_report'
RESULT = ROOT / 'data/derived/detection/comparison_reports/classical_v1_20260911/summary.json'
result = json.loads(RESULT.read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def number(value, digits=4): return f'{value:.{digits}f}'.replace('.', ',')
def count(value): return f'{value:,}'.replace(',', '.')
def link(path, label): return f'<a href="../../{html.escape(path, quote=True)}">{html.escape(label)}</a>'

assert digest(ROOT / result['source_manifest']) == result['source_manifest_sha256']
assert digest(ROOT / result['verification']) == result['verification_sha256']
qa = json.loads((ROOT / result['verification']).read_text(encoding='utf-8'))
assert qa['status'] == 'passed' and qa['historical_t218_parity']['status'] == 'passed'
assert qa['manifest_sha256'] == result['source_manifest_sha256']
assert qa['mode'] == 'search' and qa['frame_evaluations'] == 24768
source_manifest = json.loads((ROOT / result['source_manifest']).read_text(encoding='utf-8'))
assert source_manifest['status'] == 'complete' and source_manifest['git_dirty'] is False
assert source_manifest['summary']['mode'] == 'search'
assert source_manifest['summary'] == result['batch_summary']
assert source_manifest['git_sha'] == result['run_commit']
assert source_manifest['elapsed_seconds'] == result['elapsed_seconds']
assert result['batch_summary']['frame_evaluations'] == 24768
table = '<table><thead><tr><th>Família</th><th>Configuração da grade</th><th>F1 macro</th><th>Precisão</th><th>Recall</th><th>ms/quadro</th></tr></thead><tbody>'
for row in result['best_per_family']:
    table += '<tr><td>'+html.escape(row['label'])+'</td><td>'+link(row['manifest'], row['configuration_id'])+'</td>'+''.join(
        '<td>'+number(row[k], 4 if k != 'detection_ms' else 3)+'</td>' for k in ('f1','precision','recall','detection_ms'))+'</tr>'
table += '</tbody></table>'
table += '<details><summary>Conferir o F1 de cada um dos 12 vídeos</summary><p>As seis colunas usam a melhor configuração da grade de cada família; os vídeos têm peso igual na média principal.</p><table><thead><tr><th>Vídeo</th>'+''.join('<th>'+html.escape(r['label'])+'</th>' for r in result['best_per_family'])+'</tr></thead><tbody>'
for video in [r['video_id'] for r in result['best_per_family'][0]['videos']]:
    table += '<tr><td>'+video+'</td>'+''.join('<td>'+number(next(v['f1'] for v in r['videos'] if v['video_id'] == video))+'</td>' for r in result['best_per_family'])+'</tr>'
table += '</tbody></table></details>'
evidence = '<p>'+link(result['source_manifest'], 'Manifesto completo')+' · '+link(result['verification'], 'Conferência independente')+' · '+link(str(Path(result['source_manifest']).parent / 'family_finalists.json').replace('\\','/'), 'As 11 candidatas seguintes')+'.</p>'
evidence += f'<p>Execução em <code>{result["run_commit"]}</code>, Git limpo. Foram {count(24768)} avaliações em {number(result["elapsed_seconds"], 2)} s de bateria; RSS amostrado {number(result["batch_summary"]["ram_rss_peak_mb"], 3)} MiB. A autenticação inicial do cache tem tempo separado no manifesto.</p>'
evidence += f'<p>A conferência aprovou {count(qa["files_checked"])} arquivos, {count(qa["comparisons"])} comparações e {count(qa["scipy_matchings"])} matchings SciPy. A referência T218 foi comparada aos mesmos 576 quadros da execução anterior. A conferência lê derivados; não refaz o detector nem a decodificação original.</p>'
best = result['best_per_family'][0]
interpretation = f'<p><strong>{html.escape(best["label"])} obteve o maior F1 nesta primeira grade de treino: {number(best["f1"], 6)}.</strong> Esse valor é uma observação da seleção em 48 quadros por vídeo. Ainda não representa validação dos novos métodos, generalização ou desempenho da cadeia de tracking/predição.</p>'
interpretation += '<p>Leia a precisão para avaliar detecções extras e o recall para avaliar perdas. Na figura, a dispersão dos 12 vídeos revela variação que a média esconde. O custo é do detector sobre imagem em cache; não inclui decodificação ou os módulos seguintes. Os valores de detecção não podem ser comparados numericamente a HOTA ou ADE.</p>'
next_html = '<ol><li>Resolver e executar o refinamento local já proposto no treino, com até 54 configurações antes de deduplicar.</li><li>Validar as duas finalistas de cada família pesquisada nos quatro vídeos completos, sob novo executor. T218 entra como referência histórica autenticada.</li><li>Preparar o dataset derivado seguro, registrar a receita, treinar e avaliar YOLO; executar MOG2/KNN em protocolo temporal próprio.</li><li>Comparar rastreadores nas mesmas detecções com HOTA, IDF1 e MOTA; avaliar identidades, perdas e cobertura.</li><li>Avaliar preditores sobre trajetórias estimadas e ablação causal com/sem fluxo, medindo ADE/FDE e cobertura.</li></ol>'
fragment = (PARTS / 'classical_comparison_template.html').read_text(encoding='utf-8')
for key, value in {'CLASSICAL_TABLE':table, 'CLASSICAL_FIGURE':'{{FIG_CLASSICAL}}', 'CLASSICAL_EVIDENCE':evidence,
                   'CLASSICAL_RESULTS_INTERPRETATION':interpretation, 'CLASSICAL_NEXT':next_html}.items():
    assert '{{'+key+'}}' in fragment, key
    fragment = fragment.replace('{{'+key+'}}', value)

def edit(name, transform):
    path = ROOT / name
    old = path.read_text(encoding='utf-8')
    new = transform(old)
    assert new != old, name
    path.write_text(new, encoding='utf-8', newline='\n')

def core_update(text):
    assert 'id="comparacao-classicos-20260911"' not in text
    marker = '<section id="resultados" class="chapter">'
    position = text.index('</h2>', text.index(marker)) + len('</h2>')
    text = text[:position] + '\n' + fragment + '\n' + text[position:]
    text = text.replace('Onde paramos em 09/09/2026:', 'Marcos anteriores, até 09/09/2026:')
    text = text.replace('<h3>Comparar previsão com e sem fluxo</h3><p>Plano revisto em 11/09: usar as 10.848 janelas já conferidas para a primeira ablação exploratória, sob novo contrato. Avançar também no rastreamento e no ambiente aprendido.</p>',
        '<h3>Refinar e validar os demais detectores</h3><p>A primeira busca comparativa de seis famílias terminou e foi conferida em 11/09. Seguem refinamento, validação completa e YOLO, antes de escolher a cadeia de tracking e predição.</p>')
    text = text.replace('<div class="callout"><strong>Marcos anteriores', '<div class="callout"><strong>Avanço de 11/09:</strong> comparação real de 43 configurações em 576 quadros de treino, com conferência independente. <a href="#comparacao-classicos-20260911">Resultados e interpretação</a>. Ainda não há escolha final da pipeline.</div>\n<div class="callout"><strong>Marcos anteriores', 1)
    return text
edit('tmp/tcc_report/core.html', core_update)

roadmap = '<section id="proximos" class="chapter"><div class="eyebrow">Continuidade após a primeira comparação</div><h2>Onde paramos e para onde vamos</h2><p>A comparação estática de seis famílias está concluída <strong>no treino</strong>. A escolha para a pipeline permanece posterior ao refinamento e à validação, incluindo o método aprendido. A GPU foi validada sinteticamente; o treinamento YOLO atual ainda não ocorreu.</p>'+next_html+'<h3>A hipótese do fluxo continua no plano</h3><p>A ablação exploratória das 10.848 janelas dos prefixos do marco 8a permanece prevista. Ainda não foi executada. Origens 19..59 usam somente informação disponível até a origem; alvos podem chegar ao quadro 69, exclusivamente para avaliação. Os baselines na coorte completa não substituem controles calculados nessas mesmas janelas.</p><p>O teto de tempo do 8a permanece histórico. Novas extrações exigem plano e executor próprios, com memória, armazenamento, causalidade e completude controlados. Teste e folds permanecem bloqueados; a exposição histórica continua declarada.</p><p><a href="../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md">Comparação e próximo refinamento</a> · <a href="../metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md">Plano executivo</a> · <a href="NAVEGACAO.md">Guia de retomada</a>.</p></section>'
edit('tmp/tcc_report/closing.html', lambda t: re.sub(r'<section id="proximos".*?</section>', roadmap, t, flags=re.S))
edit('tmp/tcc_report/reading_guide.html', lambda t: re.sub(r'  <p>A próxima entrega proposta é.*?</section>',
    '  <p>A entrega mais recente é a <a href="#comparacao-classicos-20260911">busca comparativa de detectores no treino</a>. Acompanhe o refinamento e a validação das novas famílias, a preparação do YOLO e, depois, as comparações de tracking/predição. O cenário GT e a ablação causal continuam necessários para interpretar a hipótese do fluxo.</p>\n</section>', t, flags=re.S))
nav = '<div id="pastas-comparacao-classicos"><h3>Novos caminhos: comparação clássica e ambiente aprendido</h3><ul>'+''.join('<li>'+link(p,l)+'</li>' for p,l in [
    ('src/experiments/classical_detection_comparison.py','Biblioteca da bateria'), ('script/detection/test/compare_classical.py','CLI smoke/busca'),
    ('script/detection/test/verify_classical_comparison.py','Conferência independente SciPy'), ('configs/detection/comparison/classical_v1_operational_v2.yaml','Plano operacional vigente'),
    ('requirements-ml.lock','Versões do ambiente aprendido'), ('script/project/test/validate_learned_environment.py','Verificação sintética CUDA')])+'</ul><p>Saídas separadas em data/tests/detection/&lt;família&gt;; o manifesto agregador fica em classical_comparison. A pasta .venv-ml contém dependências locais e permanece fora do Git.</p></div>'
edit('tmp/tcc_report/navigation.html', lambda t: t.replace('<h2>Pastas, arquivos e caminhos do código</h2>', '<h2>Pastas, arquivos e caminhos do código</h2>'+nav, 1).replace('Contagem atual por nomes, após o marco 8a:', 'Contagem histórica por nomes, registrada no marco 8a:'))

def builder_update(text):
    guards = '\nCLASSICAL_RESULT_PATH = ROOT / '+repr(RESULT.relative_to(ROOT).as_posix())+'\nassert sha(CLASSICAL_RESULT_PATH) == '+repr(digest(RESULT))+'\nclassical_result = json.loads(CLASSICAL_RESULT_PATH.read_text(encoding="utf-8"))\nassert sha(ROOT / classical_result["source_manifest"]) == classical_result["source_manifest_sha256"]\nassert sha(ROOT / classical_result["verification"]) == classical_result["verification_sha256"]\nfor filename, expected_hash in classical_result["figures"].items():\n    assert sha(CLASSICAL_RESULT_PATH.parent / filename) == expected_hash\n'
    text = text.replace("core=read('core.html')", guards+"\ncore=read('core.html')", 1)
    text = text.replace("core=read('core.html')", "core=read('core.html')\ncore=core.replace('{{FIG_CLASSICAL}}',figure('data/derived/detection/comparison_reports/classical_v1_20260911/comparacao_classicos_treino.png','F1 médio, F1 por vídeo e custo de detecção da melhor configuração da grade por família.','Busca limitada no treino, com esforço desigual e T218 previamente ajustado. Pontos representam vídeos; nenhuma promoção ou validação comparativa nesta etapa.'))")
    text = text.replace("'scientific_state_date':'2026-09-09'", "'scientific_state_date':'2026-09-11'")
    text = text.replace('documentation_only_expansion=True', 'documentation_only_expansion=False')
    text = text.replace("latest_completed_milestone='8a_compact_engineering_benchmark'", "latest_completed_milestone='classical_detection_training_comparison_v1'")
    text = text.replace("next_proposed_milestone='exploratory_prediction_ablation_on_existing_compact_prefixes'", "next_proposed_milestone='classical_refinement_full_validation_and_yolo_training'")
    text = text.replace('Marco 8a concluído · ablação pendente', 'Comparação clássica no treino concluída')
    text = text.replace('Estado científico de 09/09/2026.', 'Estado científico de 11/09/2026.')
    text = text.replace('Estado científico de 09/09: marco 8a concluído. Próxima entrega proposta: ablação exploratória nos derivados disponíveis.', 'Comparação clássica no treino concluída e conferida em 11/09. Próximas etapas: refinamento, validação e YOLO, antes da escolha da pipeline.')
    text = text.replace('O plano de 11/09 prioriza uma primeira ablação nos derivados disponíveis e exige plano próprio para ampliar a extração.', 'A ablação nos derivados permanece prevista; a comparação dos demais detectores avançou em 11/09 e está documentada neste relatório.')
    insertion = '\nmeta.update(classical_comparison='+repr({'manifest':result['source_manifest'], 'manifest_sha256':result['source_manifest_sha256'], 'verification':result['verification'], 'verification_sha256':result['verification_sha256'], 'run_commit':result['run_commit'], 'evaluations':24768})+')\n'
    assert 'meta_json=' in text
    return text.replace('meta_json=', insertion+'meta_json=', 1)
edit('tmp/tcc_report/build_report.py', builder_update)

atlas_intro = '<section id="comparacao-classicos-atual" class="section"><h2>11/09: primeira comparação clássica concluída no treino</h2><p>43 configurações, seis famílias, 576 quadros, 24.768 avaliações. Conferência independente aprovada; 11 candidatas seguem para a próxima etapa. O smoke inicial interrompido foi preservado e recebeu revisão operacional própria.</p><ul>'+''.join('<li>'+html.escape(r['label'])+': F1 macro '+number(r['f1'],6)+'</li>' for r in result['best_per_family'])+'</ul><p>Melhor configuração desta grade por família; T218 previamente ajustado e esforço desigual. Ainda não houve validação comparativa dos novos métodos nem escolha final. GPU validada sinteticamente, sem treino YOLO atual.</p><p><a href="RELATORIO_COMPLETO_TCC.html#comparacao-classicos-20260911">Tabela, figura e explicação completa</a> · <a href="../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md">Protocolo e evidências</a>.</p></section>'
def atlas_update(text):
    match = re.search(r'<main\b[^>]*>', text)
    assert match and 'id="comparacao-classicos-atual"' not in text
    text = text[:match.end()] + atlas_intro + text[match.end():]
    text = text.replace('Marco 8a conferido · escala completa pendente · 09/09/2026', 'Comparação clássica no treino conferida · 11/09/2026')
    text = text.replace('19 capítulos, exemplos e quatro laboratórios · 10/09/2026', '19 capítulos, seis figuras e quatro laboratórios · 11/09/2026')
    text = re.sub(r'<section id="continuidade-20260911".*?</section>', '<section id="continuidade-20260911" class="section"><h2>Próximas etapas: refinamento, validação e YOLO</h2>'+next_html+'<p>A ablação nas 10.848 janelas do fluxo compacto permanece prevista. A escala ampliada terá protocolo próprio; o orçamento anterior de 120 minutos permanece histórico.</p><p><a href="RELATORIO_COMPLETO_TCC.html#proximos">Sequência e critérios</a> · <a href="../metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md">Plano executivo</a>.</p></section>', text, flags=re.S)
    text = text.replace('O último resultado científico continua sendo o marco 8a', 'Na frente de fluxo, o último resultado continua sendo o marco 8a')
    text = text.replace('primeira ablação nos derivados disponíveis, rastreamento e métodos aprendidos', 'refinamento e validação dos detectores, YOLO e depois comparação de rastreadores e preditores; a ablação nos derivados permanece prevista')
    return text
edit('docs/projeto/mapa-tcc-didatico.html', atlas_update)
print(json.dumps({'status':'parts_updated','results':str(RESULT)}, ensure_ascii=False))
