import json
from pathlib import Path
root = Path.cwd()
search = 'data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search'
run = search + '/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42'
bench = 'data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark'
new_bench = bench + '/20260908T141314464252Z__3f73a52__cfgcbefe6ab9f8a__srceae1c32fd9__s42/manifest.json'
figure = 'data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.png'
top = json.loads(Path(run, 'shortlist.json').read_text())
def get(p): return Path(p).read_text(encoding='utf-8')
def put(p,s): Path(p).write_text(s,encoding='utf-8')
rows = ''.join(f"<tr><td>{r['rank']}</td><td><code>{r['configuration_id']}</code></td><td>{r['macro_video_f1']:.4f}</td><td>{r['macro_video_recall']:.4f}</td><td>{r['macro_video_count_mae']:.4f}</td></tr>" for r in top)
block = f'''        <section id="busca-threshold-v3" class="section">
          <span class="kicker">Agora · busca grossa concluída · 08/09/2026</span>
          <h2>Threshold v3: cinco candidatos para refinar</h2>
          <p class="section-intro">Concluímos <strong>171 configurações nos mesmos 144 quadros de treino: 24.624 avaliações</strong>. A classificação foi reconstruída de forma independente. <strong>T224, sem abertura e com dois fechamentos</strong>, liderou essa amostra com F1 médio por vídeo de <strong>0,7753</strong>. Isso seleciona candidatos para a próxima etapa; ainda não promove um detector.</p>
          <div class="grid two">
            <article class="card">
              <h3>O que foi comparado</h3>
              <p>São 12 quadros de cada um dos 12 vídeos de treino. A amostra contém 2.961 anotações individuais e 44 agrupamentos, estes em 33 quadros. Os indivíduos são avaliados a 10 px, com sensibilidades obrigatórias de 15/20 px.</p>
              <p>Todos usam os mesmos pixels e o GT integral. Os 144 quadros pertencem ao cache de <strong>576 quadros (48 por vídeo)</strong>, cerca de 508 MiB, que será reutilizado no refinamento. Lacunas do vídeo 23 permanecem excluídas.</p>
              <p><a href="../../data/derived/detection/frame_samples/threshold_search_v3_20260908/manifest.json">Manifesto da amostra</a> · <a href="../../configs/detection/threshold/search_v3.yaml">Plano registrado antes da execução</a></p>
            </article>
            <article class="card">
              <h3>Como sabemos que a comparação está completa</h3>
              <p>A bateria terminou em <strong>291,32 s</strong>, com pico amostrado de RAM de 94,594 MiB. O commit <code>3f73a52</code>, o Git limpo, o código e o ambiente foram conferidos ao final.</p>
              <p>A suíte curta passou em <strong>442 testes</strong>. Uma conferência independente aprovou 1.205 arquivos, 1.631.066 comparações numéricas e 72 verificações de associação SciPy em casos predeterminados. O ranking e os cinco candidatos coincidiram.</p>
              <p><a href="../../{run}/manifest.json">Manifesto da busca</a> · <a href="../../{search}/verification_20260908.json">Conferência independente</a></p>
            </article>
          </div>
          <div class="table-wrap"><table>
            <thead><tr><th>Ordem</th><th>Configuração</th><th>F1 macro</th><th>Recall macro</th><th>MAE de contagem</th></tr></thead>
            <tbody>{rows}</tbody>
          </table></div>
          <p><code>t</code> é o limiar de intensidade; <code>o</code>, o número de aberturas; <code>c</code>, o número de fechamentos. As métricas são calculadas por vídeo e depois recebem pesos iguais. Arredondamento é apenas para apresentação. <a href="../../{run}/ranking.csv">Classificação completa das 171 configurações</a>.</p>
          <figure><a href="../../{figure}"><img src="../../{figure}" alt="Curvas de F1 de treino por limiar e morfologia, e comparação dos cinco candidatos nos 12 vídeos." loading="lazy"></a><figcaption>O primeiro colocado não vence em todos os vídeos. As diferenças são descritivas da amostra usada na seleção, sem teste de significância ou estimativa de generalização.</figcaption></figure>
          <div class="callout">
            <strong>Próximo marco: refinamento no treino.</strong>
            <p>Aplicar a regra já registrada — limiares inteiros ±15 em torno dos cinco candidatos, mantendo sua morfologia — produz <strong>117 configurações distintas</strong>. Serão 67.392 avaliações nos 576 quadros já preparados, após implementar o executor e medir o custo. A lista está pronta; <strong>o refinamento ainda não foi executado</strong>.</p>
            <p><a href="../../{search}/refinement_plan_20260908.json">Plano derivado com os 117 candidatos</a> · <a href="../metodologia/BUSCA_THRESHOLD_V3.md">Regras, resultados e limites científicos</a>. Validação, teste e folds continuam pendentes na v3; a exposição histórica do teste permanece registrada.</p>
          </div>
          <details><summary>Por que repetimos o benchmark de custo?</summary>
            <p>O plano foi registrado em <code>9940337</code> antes dos dados. O primeiro benchmark projetou 3.167,83 s, acima do limite de 1.200 s. Consultas repetidas ao Git e ao ambiente dominavam o custo evitável. A otimização em <code>3f73a52</code> passou a compartilhar uma captura explícita na bateria, conferida novamente ao final.</p>
            <p>O novo laço de benchmark levou 40,85 s, com projeção de 986,31 s. Arquivos de detecções e GT dos 171 candidatos permaneceram idênticos byte a byte; métricas por quadro também, exceto tempo. Plano, parâmetros, imagens, métricas e orçamento não mudaram.</p>
            <p><a href="../../{bench}/cost_review_20260908.json">Revisão do custo</a> · <a href="../../{new_bench}">Novo benchmark</a> · <a href="../../{bench}/benchmark_parity_20260908.json">Conferência de equivalência</a></p>
          </details>
          <p><a href="../../script/README.md#busca-threshold-v3">Comandos oficiais</a> · <a href="../../script/detection/test/threshold/search.py">Executor</a> · <a href="../../src/detection/classical/threshold.py">Algoritmo</a> · <a href="NAVEGACAO.md">Guia permanente</a> · <a href="DIARIO.md">Diário</a></p>
        </section>
'''
p='docs/projeto/mapa-tcc-didatico.html';s=get(p);a=s.index('        <section id="busca-threshold-v3"');b=s.index('        <section id="retomada-nivel1"',a);put(p,s[:a]+block+s[b:])

state = f'''## 12. Estado atual: busca grossa concluída — 08/09/2026

Plano prospectivo em `9940337`, antes dos dados. A otimização de proveniência
em `3f73a52` passou em 442 testes da suíte curta. Benchmark inicial preservado:
131,7403 s, projeção 3.167,83 s acima do limite. Novo benchmark: 40,8452 s,
projeção 986,31 s dentro do mesmo limite. CSVs de detecções/GT idênticos nos
171 candidatos e métricas por quadro iguais exceto tempo. Não repetir a busca
por desconhecer esse histórico: ela foi concluída e conferida.

Busca grossa: **171 × 144 = 24.624 avaliações**, 291,32 s totais, Git limpo,
commit `3f73a52` e checagem final de código/ambiente aprovada. Top5 para
refinamento: T224/o0/c2 (F1 0,7753), T208/o0/c2, T224/o0/c1, T200/o1/c2,
T208/o1/c2. A avaliação é a v3 dos indivíduos a 10 px, com sensibilidades
15/20 px. É seleção no treino, sem promoção; não confundir com T200 histórica
congelada a 15 px. Validação, teste e folds não foram abertos nesta etapa.

A conferência independente aprovou 1.205 arquivos, 1.631.066 comparações
numéricas e 72 verificações SciPy em 12 casos predeterminados. Ela reconstrói
rankings e agregações; não certifica GT completo nem generalização.

| Para retomar | Abra |
|---|---|
| Plano prospectivo | [search_v3.yaml](../../configs/detection/threshold/search_v3.yaml) |
| Método e resultados detalhados | [BUSCA_THRESHOLD_V3.md](../metodologia/BUSCA_THRESHOLD_V3.md) |
| Comandos oficiais | [Busca v3](../../script/README.md#busca-threshold-v3) |
| Executor, amostra e classificação | [search.py](../../script/detection/test/threshold/search.py) · [detection_sample.py](../../src/experiments/detection_sample.py) · [detection_search.py](../../src/experiments/detection_search.py) |
| Proveniência compartilhada | [runs.py](../../src/experiments/runs.py) — RunSnapshot opt-in; demais runs mantêm comportamento anterior |
| Cache completo | [manifest.json](../../data/derived/detection/frame_samples/threshold_search_v3_20260908/manifest.json) |
| Novo benchmark | [manifest.json](../../{new_bench}) |
| Busca completa | [manifest.json](../../{run}/manifest.json) · [ranking.csv](../../{run}/ranking.csv) · [shortlist.json](../../{run}/shortlist.json) |
| Conferência independente | [verification_20260908.json](../../{search}/verification_20260908.json) |
| Comparação dos benchmarks | [benchmark_parity_20260908.json](../../{bench}/benchmark_parity_20260908.json) |
| Figura científica | [PNG](../../{figure}) · [SVG](../../{figure.replace('.png','.svg')}) |
| Próximo refinamento, ainda sem executar | [117 candidatos](../../{search}/refinement_plan_20260908.json) |

O cache conserva 576 quadros (48 por vídeo de treino), com subconjuntos
aninhados de 144/12, 532.540.304 bytes, preparo em 19,285 s. Identidade:
`77ad9cbda76c03d61f3b28dd99520d0c1d6e285452929d847742bc6331473478`.
Não recriar a amostra para escolher outro conjunto de quadros. A seleção é
uniforme na lista de índices anotados, não no tempo onde há lacunas.

**Próxima etapa:** implementar e medir o refinamento da regra já registrada.
Deduplicação dos cinco pais: 117 configurações × 576 quadros = 67.392
avaliações. T193–239/o0/c2, T209–239/o0/c1, T185–223/o1/c2; área 3–300,
kernel 3, polaridade e métrica inalteradas. Teto 7.200 s com nova projeção
obrigatória antes da execução. A CLI atual só tem prepare/benchmark/coarse;
não execute o refinamento usando o antigo batch_frames.py. Duas finalistas
seguirão para validação completa somente depois do refinamento. Não abrir
teste para escolher hiperparâmetros; folds não desfazem a exposição histórica.

O atlas e este guia são locais. Código/plano e registro de resultados recebem
commits; HTMLs, instruções de agentes e a monografia permanecem excluídos,
conforme preferência registrada. O método LaTeX recebeu o desenho da busca e
a ressalva correta sobre folds; o PDF ainda não foi recompilado.
'''
p='docs/projeto/NAVEGACAO.md';s=get(p);s=s[:s.index('## 12. Estado atual:')]+state
s=s.replace('   acima do orçamento. Conferir a otimização de proveniência e repetir somente\n   o benchmark sob o mesmo plano; a busca grossa ainda não foi executada.', '   acima do orçamento, seguido de otimização e repetição bem-sucedidas. A busca\n   grossa já foi concluída e conferida; o próximo marco é o refinamento\n   registrado, com 117 candidatos e nova medição de custo.')
put(p,s)
p='AGENTS.md';s=get(p);a=s.index('Estado de 08/09/2026');b=s.index('## Objetivo',a)
s=s[:a]+'''Estado de 08/09/2026: busca grossa v3 concluída e conferida. Plano em
`9940337` antes dos dados; otimização de proveniência em `3f73a52`, com
442 testes aprovados. Benchmark inicial preservado (projeção 3167,83 s),
segundo benchmark compatível com o mesmo orçamento (986,31 s); CSVs de
detecções/GT idênticos para 171 candidatos. Busca: 171 × 144 = 24.624 avaliações,
291,32 s, Git limpo e proveniência revalidada antes de classificar. Conferência
independente: 1205 arquivos, 1631066 comparações e 72 verificações SciPy.
Top5 no treino: T224/o0/c2, T208/o0/c2, T224/o0/c1, T200/o1/c2, T208/o1/c2;
primeiro F1 macro 0,7753 a 10 px. Nenhum método promovido na v3.

Próximo marco: implementar e medir o refinamento já registrado. A lista
derivada contém 117 configurações distintas × 576 quadros = 67.392 avaliações;
ela ainda não foi executada. Usar o cache existente de 48 quadros por vídeo,
sem alterar área, kernel, polaridade ou métrica. Teto 7200 s e nova projeção
antes de executar. A CLI search.py atual não executa refinamento; não usar
o batch_frames.py histórico para isso. Guia seção 12 e atlas bloco
`busca-threshold-v3` ligam planos, cache, runs, conferência e figuras. Não
repetir busca grossa já encerrada nem confundir a shortlist com congelamento.
Validação e teste não foram reabertos. Fontes e todas as runs preservadas.

'''+s[b:];put(p,s)

p='docs/algoritmos/deteccao/threshold_fixo.md';s=get(p);s=s.replace('O pesquisador autorizou continuidade autônoma. O planejamento prospectivo\nde threshold virá depois, com raio e política de classes já definidos.', 'Após esse marco, o plano prospectivo foi registrado e a busca grossa foi\nexecutada, como descrito na decisão atual. Raio e política de classes\npermaneceram iguais. O refinamento é a próxima etapa.');put(p,s)
p='monografia/README.md';s=get(p);s=s.replace('O desenho da seleção e da avaliação confirmatória continua pendente.', 'O desenho da busca grossa e do refinamento de threshold foi registrado em\n08/09; a busca grossa foi executada e o refinamento continua pendente. O método\nincorpora a amostragem, as regras de seleção e a ressalva de que folds não\nrestauram a independência perdida na exposição histórica do teste.');put(p,s)
print('Atlas, navegação, instruções locais e ficha atualizados.')
