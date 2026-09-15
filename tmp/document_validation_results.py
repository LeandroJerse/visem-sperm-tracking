"""Update project records only after the immutable validation and QA pass."""
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RUN = Path('data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42')
QA = RUN.parent / 'verification_20260908_retry2.json'
FIG = Path('data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/validacao_threshold_completa.png')
batch = json.loads((ROOT / RUN / 'manifest.json').read_text(encoding='utf-8'))
qa = json.loads((ROOT / QA).read_text(encoding='utf-8'))
assert batch['status'] == 'complete' and qa['status'] == 'passed'
assert hashlib.sha256((ROOT / RUN / 'manifest.json').read_bytes()).hexdigest() == qa['batch_manifest_sha256']
assert (ROOT / FIG).is_file()
with (ROOT / RUN / 'ranking.csv').open(encoding='utf-8', newline='') as f:
    ranking = list(csv.DictReader(f))
with (ROOT / RUN / 'video_metrics.csv').open(encoding='utf-8', newline='') as f:
    videos = list(csv.DictReader(f))
assert [r['configuration_id'] for r in ranking] == qa['independent_ranking'] == ['t218_o0_c2', 't219_o0_c2']
assert len(videos) == 8 and qa['frame_evaluations'] == 11700 and len(qa['matching_checks']) == 144

def write(name, text):
    (ROOT / name).write_bytes(text.encode('utf-8'))

def read(name):
    return (ROOT / name).read_bytes().decode('utf-8')

def replace(name, old, new):
    text = read(name)
    if old not in text and '\r\n' in text:
        old, new = old.replace('\n', '\r\n'), new.replace('\n', '\r\n')
    assert old in text, (name, old[:90])
    write(name, text.replace(old, new, 1))

def pt(value, digits=6):
    return f'{float(value):.{digits}f}'.replace('.', ',')

table = '| Configuração | F1 macro 10 px | Precisão macro | Revocação macro | MAE de contagem macro |\n|---|---:|---:|---:|---:|\n'
for row in ranking:
    table += '| ' + ' | '.join([row['configuration_id'], *[pt(row[k]) for k in ('macro_video_f1', 'macro_video_precision', 'macro_video_recall', 'macro_video_count_mae')]]) + ' |\n'
video_table = '| Vídeo | Quadros | F1 T218 | F1 T219 |\n|---|---:|---:|---:|\n'
for video in ('14', '19', '36', '52'):
    rows = {r['configuration_id']: r for r in videos if r['video_id'] == video}
    video_table += f"| {video} | {rows['t218_o0_c2']['frames_total']} | {pt(rows['t218_o0_c2']['f1'])} | {pt(rows['t219_o0_c2']['f1'])} |\n"

results = f'''

## Resultados da validação — 08/09/2026

Protocolo e executor registrados em **`7f47afb`**, antes da abertura das
fontes desta bateria, após **824 testes em 110,00 s**. A run concluiu os
oito pares previstos, com Git limpo e rechecagem de fontes, pais, saídas,
código e ambiente. Foram **11.700 avaliações em 5.850 quadros físicos**,
166,657535 s totais e pico amostrado de RSS de 236,594 MiB. Os artefatos
somavam 63.093.945 bytes antes da escrita do manifesto final, dentro do
orçamento. Tempo e memória não participaram da seleção.

**T218/o0/c2 foi selecionada na validação**, com abertura zero e dois
fechamentos. Os demais parâmetros permaneceram idênticos aos do treino.

{table}
{video_table}
A diferença de F1 macro é **0,0011402996734879**, ou **0,11403 ponto
percentual**, a favor de T218. T218 vence nos vídeos 19/36; T219, em 14/52.
A escolha segue a regra previamente fixada, sem evidência de superioridade
geral ou significância estatística. Os valores da amostra de treino e dos
vídeos completos de validação pertencem a universos distintos; sua diferença
não mede isoladamente melhora ou piora do algoritmo.

As sensibilidades preservaram a mesma ordem: T218 teve F1 macro
0,663448/0,664873 a 15/20 px; T219, 0,662237/0,663842. Cada configuração
usou o mesmo GT exportado: 123.242 objetos, sendo 115.629 indivíduos e
7.613 anotações de agrupamento. São ocorrências ao longo dos quadros, não
células únicas. Foram ignoradas 16.147 previsões de T218 e 15.792 de T219
a 10 px, mantendo todas as previsões e anotações brutas nos CSVs. A métrica
secundária conta cada agrupamento como um objeto, sem inferir quantas células
ele contém. A grande variação entre vídeos merece análise futura, sem
atribuir uma causa visual que esta bateria quantitativa não verificou.

### Conferência e limitações

A conferência independente aprovou **46 arquivos**, **1.772.878 comparações
de campos/valores**, todos os registros e agregados e **144 verificações
SciPy** nos casos previamente definidos. O ranking foi reconstruído e o GT
exportado coincidiu entre candidatos. Essa conferência não reabriu fontes:
hashes dos MP4/anotações e EOF são evidência registrada pelo executor;
o matching independente foi amostral, não integral.

Duas tentativas iniciais do verificador falharam por suposições de formato:
tamanho opcional nas referências e igualdade literal entre inteiros e
decimais das sensibilidades. Corrigiu-se somente o verificador local; as
falhas foram preservadas e a terceira tentativa foi aprovada. Nenhuma run
científica, configuração ou fonte foi alterada ou reexecutada para isso.

O resultado é uma **seleção de validação ainda não congelada**. Não houve
teste, folds ou nova busca após observar estes resultados. A hipótese de
predição com fluxo continua pendente. O próximo marco é registrar critérios
de congelamento e o contrato de trajetórias individuais, preparando tracking
com GT e janelas causais comuns para a futura ablação.

### Artefatos locais preservados

- [Manifesto da bateria](../../{RUN.as_posix()}/manifest.json),
  [seleção](../../{RUN.as_posix()}/selection.json),
  [ranking](../../{RUN.as_posix()}/ranking.csv) e
  [oito resumos por vídeo](../../{RUN.as_posix()}/video_metrics.csv).
- [Conferência aprovada](../../{QA.as_posix()}) e
  [histórico das três tentativas](../../{RUN.parent.as_posix()}/verification_attempts_20260908.json).
- [Figura PNG](../../{FIG.as_posix()}), [SVG](../../{FIG.with_suffix('.svg').as_posix()})
  e [revisão visual](../../{FIG.parent.as_posix()}/visual_review.json).

SHA-256 do manifesto: `{qa['batch_manifest_sha256']}`.
SHA-256 da conferência: `{hashlib.sha256((ROOT / QA).read_bytes()).hexdigest()}`.
'''
with (ROOT / 'docs/metodologia/VALIDACAO_THRESHOLD_V3.md').open('a', encoding='utf-8') as f:
    f.write(results)
replace('docs/metodologia/VALIDACAO_THRESHOLD_V3.md', '## Estado e finalidade',
        'Resultado posterior: [validação concluída e conferida](#resultados-da-validação--08092026),\ncom T218/o0/c2 selecionada, ainda sem congelamento. O protocolo prospectivo\nabaixo permanece preservado.\n\n## Estado e finalidade')
entry = '''## 2026-09-08 — validação completa v3 concluída; T218 selecionada

- Bateria científica executada uma vez, após commit `7f47afb` e 824 testes,
  com Git limpo. Oito runs completas, 11.700 avaliações, 5.850 quadros físicos.
  Fontes, pais, planos, métricas exportadas e saídas conferidos antes da seleção.
- Tempo total 166,657535 s; pico amostrado de RSS 236,594 MiB; 63.093.945
  bytes de artefatos antes do manifesto final. Todos os limites respeitados.
- T218/o0/c2: F1 macro 0,658959, recall 0,794711, MAE de contagem 4,408433.
  T219/o0/c2: F1 macro 0,657819. Diferença 0,11403 ponto percentual;
  cada configuração vence em dois vídeos. Sem inferência de significância.
- Conferência independente aprovada: 46 arquivos, 1.772.878 comparações,
  11.700 registros e 144 matchings SciPy. Duas tentativas anteriores falharam
  por suposições do verificador sobre metadados/serialização numérica; foram
  preservadas e corrigidas somente no verificador. Runs científicas intactas.
- Figura PNG/SVG revisada, com a primeira renderização preservada; mapa,
  ficha, matriz, guia local e fonte da monografia atualizados. PDF não recompilado.
- [Resultados, figura, hashes e histórico das conferências](../metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026).
  Seleção de validação, sem congelamento, teste ou folds. Próximo marco:
  critérios de congelamento e elegibilidade de trajetórias individuais,
  preparando tracking com GT e a comparação causal de predição com/sem fluxo.

'''
replace('docs/projeto/DIARIO.md', '## 2026-09-08 — revisão geral aprovada e validação v3 preparada antes dos dados',
        entry + '## 2026-09-08 — revisão geral aprovada e validação v3 preparada antes dos dados')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
        '| Dois finalistas de treino | T219/o0/c2 e T218/o0/c2; nenhuma validação completa, teste ou promoção na v3 |',
        '| Dois finalistas de treino | T219/o0/c2 e T218/o0/c2; comparados posteriormente na validação completa |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
        '| Preparação da validação v3 | Plano e executor estrito implementados para 2 × 5.850 = 11.700 avaliações; fontes ainda não abertas nesta etapa |\n| Próximo marco | Executar a validação registrada depois do commit e conferir as oito runs, sem congelamento automático |',
        '| Validação v3 completa | 11.700 avaliações em 7f47afb, Git limpo; 824 testes antes da execução; conferência independente aprovada |\n'
        '| Seleção de validação | T218/o0/c2: F1 macro 0,658959; T219: 0,657819; sem congelamento, teste ou folds |\n'
        '| Próximo marco | Registrar critérios de congelamento e contrato de trajetórias individuais; preparar tracking com GT e janelas causais comuns |\n\n'
        '[Resultados, oito vídeos/configurações, figura e conferência](../metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026).\n'
        'Cada finalista vence em dois vídeos; a diferença macro de 0,11403 ponto\npercentual não demonstra superioridade geral. A conferência verificou 46\narquivos, 1.772.878 campos/valores e 144 matchings. As duas correções do\nverificador e as tentativas iniciais estão preservadas; as runs não mudaram.')
replace('README.md', 'São candidatos para\n   validação completa; nenhuma configuração foi congelada no novo contrato.',
        'A [validação completa](docs/metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026)\n   selecionou **T218/o0/c2**, com F1 macro de 0,658959; nenhuma configuração\n   foi congelada no novo contrato.')
replace('docs/algoritmos/deteccao/threshold_fixo.md', '## Decisão atual',
        '## Decisão atual\n\nA validação completa das duas finalistas terminou em `7f47afb`, após 824\ntestes: oito runs, 11.700 avaliações, Git limpo, conferência independente\naprovada (46 arquivos, 1.772.878 comparações e 144 matchings).\n\n'
        + table + '\n**T218/o0/c2 foi selecionada na validação**, sem congelamento ou teste.\n'
        'Cada candidata vence em dois vídeos; a diferença macro é 0,11403 ponto\npercentual, sem inferência de significância. Tempo total 166,657535 s e\nRSS amostrado 236,594 MiB. Os detalhes e limites estão no\n'
        '[relatório de validação](../../metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026).\n\n'
        '## Histórico do refinamento no treino')
replace('docs/algoritmos/deteccao/threshold_fixo.md',
        'O próximo marco é **executar a validação registrada das duas finalistas**.',
        'A etapa seguinte foi a **validação registrada das duas finalistas**, concluída acima.')
replace('docs/algoritmos/deteccao/threshold_fixo.md',
        'Fontes de validação ainda não foram abertas nesta preparação.',
        'As fontes foram abertas somente após registrar plano e executor em `7f47afb`.')
replace('docs/metodologia/PROTOCOLO.md',
        'registrado antes da execução. O desenho confirmatório posterior continua pendente.',
        'registrado antes da execução. A bateria completa posteriormente selecionou\nT218/o0/c2, com F1 macro 0,658959, sem congelamento, teste ou folds; os\n[resultados conferidos](VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026)\nestão separados das regras prospectivas. O desenho confirmatório continua pendente.')

current_note = '''

### Desfecho posterior à preparação

Run completa em `7f47afb`, Git limpo, após 824 testes. T218/o0/c2 foi
selecionada com F1 macro 0,658959; T219/o0/c2 teve 0,657819. Todas as
11.700 avaliações passaram na conferência independente: 46 arquivos,
1.772.878 comparações e 144 matchings. Bateria 166,657535 s/RSS 236,594 MiB.
Os dois erros iniciais do verificador estão preservados; as runs não mudaram.
Nenhum congelamento, teste ou fold foi executado.

'''
with (ROOT / 'docs/projeto/NAVEGACAO.md').open('a', encoding='utf-8') as f:
    f.write(current_note + f'Manifesto: `{RUN.as_posix()}/manifest.json`.\n\n'
            + f'Conferência aprovada: `{QA.as_posix()}`.\n\n'
            + f'Figura final: `{FIG.as_posix()}`.\n\n'
            + 'Próximo marco: critérios de congelamento e contrato de trajetórias\n'
            + 'individuais, tracking com GT e janelas causais comuns. Não repetir a\n'
            + 'validação, escolher novos limiares usando esses resultados ou abrir teste\n'
            + 'e OOF sem desenho próprio. Código/custos continuam em `7f47afb`.\n')
replace('docs/projeto/NAVEGACAO.md',
        '   e levou à preparação do executor estrito e do protocolo de validação.',
        '   e levou ao executor estrito e à validação completa das duas finalistas.\n'
        '   T218/o0/c2 foi selecionada, F1 macro 0,658959, sem congelamento/teste.\n'
        '   Runs de `7f47afb`, 824 testes e conferência independente aprovada.')
replace('AGENTS.md', 'Consulte a seção 13 do guia e o diário para o desfecho, sem repetir a bateria.',
        'Bateria concluída em `7f47afb`: T218/o0/c2 selecionada (F1 macro\n'
        '0,658959), sem congelamento, teste ou folds. QA aprovada em\n'
        '`verification_20260908_retry2.json`: 46 arquivos, 1.772.878 comparações\n'
        'e 144 matchings. As duas falhas iniciais do verificador estão preservadas.\n'
        'Consulte a seção 13 do guia e o diário, sem repetir a bateria.')

tex_result = r'''Em seguida, a validação completa foi executada sob o commit \texttt{7f47afb}, com Git limpo e 824 testes aprovados antes da bateria. As oito runs somaram 11.700 avaliações em 166,657535 segundos, com pico amostrado de RSS de 236,594 MiB. T218/o0/c2 foi selecionada pelo critério prospectivo, com F1 macro de 0,658959, revocação macro de 0,794711 e MAE de contagem macro de 4,408433. T219/o0/c2 obteve F1 macro de 0,657819. A diferença de 0,11403 ponto percentual é descritiva: T218 teve F1 maior em 19/36, e T219 em 14/52. A conferência independente reconstruiu os 11.700 registros e agregados, com 1.772.878 comparações de campos/valores e 144 verificações amostrais de matching com SciPy. Duas tentativas iniciais foram preservadas após correções de suposições do verificador sobre formato de metadados; nenhuma run científica foi alterada. A seleção ainda não foi congelada e não constitui teste independente, avaliação de folds ou evidência sobre a hipótese de fluxo.'''
replace('monografia/cap_metodo/metodo.tex', r'\section{Estimação do movimento aparente}',
        tex_result + '\n\n' + r'\section{Estimação do movimento aparente}')
replace('monografia/cap_conclusao/conclusao.tex',
        'A continuidade priorizará a elegibilidade de trajetórias individuais,',
        'Após essa preparação, a validação completa selecionou T218/o0/c2, com F1 macro de 0,658959, contra 0,657819 de T219/o0/c2. As 11.700 avaliações e a conferência independente foram concluídas; a diferença foi pequena e cada configuração teve F1 maior em dois vídeos. Esse marco estabelece a seleção de uma linha de base de localização, ainda sem congelamento ou teste, e não demonstra contribuição do fluxo à predição.\n\n'
        + 'A continuidade priorizará a elegibilidade de trajetórias individuais,')

html_table = '<div class="table-wrap"><table><thead><tr><th>Configuração</th><th>F1 macro a 10 px</th><th>Recall macro</th><th>MAE de contagem</th></tr></thead><tbody>'
for row in ranking:
    html_table += '<tr>' + ''.join(f'<td>{value}</td>' for value in [row['configuration_id'], pt(row['macro_video_f1']), pt(row['macro_video_recall']), pt(row['macro_video_count_mae'])]) + '</tr>'
html_table += '</tbody></table></div>'
section = f'''<section id="validacao-threshold-v3" class="section">
          <span class="kicker">Agora · validação completa e conferida · 08/09/2026</span>
          <h2>T218 foi selecionada na validação; o projeto segue alinhado</h2>
          <p class="section-intro">A revisão geral confirmou o alinhamento ao TCC e conferiu 3.248 arquivos sem divergências. Após corrigir e testar o executor, concluímos <strong>11.700 avaliações nos quatro vídeos completos</strong>. T218/o0/c2 ficou à frente na média, ainda sem congelamento ou teste.</p>
          {html_table}
          <p>A diferença é de <strong>0,11403 ponto percentual</strong>. T218 vence nos vídeos 19/36; T219, em 14/52. A regra de escolha foi registrada antes dos dados. A comparação seleciona uma linha de base; não demonstra superioridade geral nem a hipótese de predição com fluxo.</p>
          <div class="grid two">
            <article class="card"><h3>Execução completa e rastreável</h3><p>Commit <code>7f47afb</code>, Git limpo e <strong>824 testes</strong> antes da bateria. Tempo total de <strong>166,66 s</strong>, RSS amostrado de <strong>236,594 MiB</strong>. Os vídeos 14/19/36 têm 1.470 quadros; 52 tem 1.440.</p><p>Entradas, leitura até o fim, métricas exportadas e hashes foram verificados. Os dois candidatos usam os mesmos 5.850 quadros físicos.</p><p><a href="../../{RUN.as_posix()}/manifest.json">Manifesto</a> · <a href="../../{RUN.as_posix()}/selection.json">Seleção completa</a> · <a href="../metodologia/VALIDACAO_THRESHOLD_V3.md">Protocolo e resultados</a></p></article>
            <article class="card"><h3>Conferência e próximo marco</h3><p><strong>46 arquivos, 1.772.878 comparações e 144 matchings</strong> independentes aprovados. As duas falhas iniciais do verificador estão preservadas; foram corrigidas suposições de formato, sem alterar os experimentos.</p><p>Próximo: critérios de congelamento e trajetórias individuais, preparando tracking com GT e janelas comuns, sem informação futura. A hipótese com/sem fluxo e a avaliação confirmatória continuam pendentes.</p><p><a href="../../{QA.as_posix()}">Conferência aprovada</a> · <a href="REVISAO_GERAL_20260908.md">Revisão geral</a> · <a href="NAVEGACAO.md">Guia para retomar</a></p></article>
          </div>
          <figure><a href="../../{FIG.as_posix()}"><img src="../../{FIG.as_posix()}" alt="F1 de T219 e T218 nos quatro vídeos completos, média com peso igual por vídeo e diferenças pareadas em pontos percentuais." loading="lazy"></a><figcaption>Resultados descritivos da seleção na validação. O painel da direita amplia as diferenças; cada configuração vence em dois vídeos. <a href="../../{FIG.with_suffix('.svg').as_posix()}">Figura vetorial SVG</a>.</figcaption></figure>
        </section>'''
name = 'docs/projeto/mapa-tcc-didatico.html'
text = read(name)
start, end = text.index('<section id="validacao-threshold-v3"'), text.index('<section id="busca-threshold-v3"')
write(name, text[:start] + section + '\n        ' + text[end:])
replace(name, 'Nível 3: refinamento concluído · 08/09/2026', 'Nível 4: validação concluída · 08/09/2026')
replace(name, 'Validação, teste e folds continuam pendentes na v3;', 'A validação posterior está descrita acima; teste e folds continuam pendentes na v3;')
replace(name, '<strong>Próximo marco: preparar o protocolo e o executor da validação.</strong>',
        '<strong>Etapa seguinte concluída: <a href="#validacao-threshold-v3">validação completa das duas finalistas</a>.</strong>')
replace(name, 'Histórico: T200 congelada a 15 px. V3: contrato e smoke de engenharia concluídos',
        'Histórico: T200 congelada a 15 px. V3: T218 selecionada na validação, F1 macro 0,658959')
replace(name, 'Planejar a busca prospectiva e a nova seleção', 'Critérios de congelamento e contrato de trajetórias; teste e folds pendentes')
replace(name, '<tr><td>84 entradas Git da reorganização sem commit</td><td>Não saber exatamente qual estado produziu o teste</td><td>revisar e criar checkpoint antes de executar</td><td>imediata</td></tr>',
        '<tr><td>Executar código sem registrar sua versão</td><td>Dificultar a reprodução</td><td>validação em 7f47afb com Git limpo e hashes; repetir esse controle nas próximas baterias</td><td>contínua</td></tr>')
replace(name, 'Na v3, contrato e smoke em seis frames concluíram o nível 2, sem seleção ou promoção. A execução do plano registrado é acompanhada no <a href="#busca-threshold-v3">nível 3</a>.',
        'Na v3, busca e refinamento foram seguidos por <a href="#validacao-threshold-v3">validação completa</a>: T218/o0/c2 selecionada, F1 macro 0,658959, ainda sem congelamento.')
replace(name, 'Na v3, o contrato e o smoke de engenharia concluíram o nível 2, sem promover uma configuração. O plano prospectivo foi registrado; confira a execução e seus limites no <a href="#busca-threshold-v3">estado atual do nível 3</a>.',
        'Na v3, <a href="#validacao-threshold-v3">T218/o0/c2 foi selecionada na validação</a>, ainda sem congelamento ou teste. Esse resultado pertence ao novo contrato, separado do histórico.')
print(json.dumps({'status': 'documented', 'batch': str(RUN), 'qa': str(QA), 'selected': ranking[0]['configuration_id']}))
