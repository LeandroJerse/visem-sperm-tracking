# Busca prospectiva do threshold fixo — 08/09/2026

[Protocolo](PROTOCOLO.md) · [Classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md)
· [Configuração registrada](../../configs/detection/threshold/search_v3.yaml)
· [Comandos oficiais](../../script/README.md#busca-threshold-v3)

As regras a seguir foram registradas antes do processamento. O
[registro de execução](#estado-deste-registro) distingue o plano dos
resultados e das revisões operacionais posteriores.

## Pergunta, alcance e limite

Qual configuração de limiar fixo e morfologia apresenta o melhor F1 de
localização individual na amostra de treino definida antes da busca?
O resultado será uma lista de candidatos para refinamento. Não é estimativa
de generalização, promoção de detector ou comparação final do TCC.

Esta busca é hierárquica e limitada por orçamento. Não demonstra ótimo global
do método. O raio de avaliação, a política de agrupamentos e os vídeos não
serão ajustados pelos resultados. O histórico de exploração dos quatro vídeos
reservados ao teste continua registrado; novo planejamento não restaura cegueira.

A otimização de um critério medido em uma amostra finita pode produzir viés
de seleção. Separar seleção e avaliação e relatar todo o procedimento é
necessário para interpretar resultados. [Cawley e Talbot, JMLR, 2010](https://www.jmlr.org/papers/v11/cawley10a.html).

## Amostra compartilhada

Usar exclusivamente os vídeos de treino 11, 12, 13, 15, 21, 22, 23, 29,
30, 35, 60 e 82. Antes de abrir as fontes, conferir essa lista contra o
split vigente e contra a auditoria de geometria anterior.

1. Ordenar os índices dos quadros com arquivo GT existente. Conferir hashes
   e contagens contra a auditoria anterior; nenhuma linha malformada será
   omitida silenciosamente. GT existente e vazio é negativo explícito;
   GT ausente é desconhecido, fora da amostra.
2. Selecionar 48 índices por vídeo sobre essa lista ordenada. Para uma lista
   de tamanho N e k posições, usar `floor(j*(N-1)/(k-1))`, j de 0 a k−1.
   Exigir a quantidade planejada, sem devolver uma amostra menor silenciosamente.
3. Selecionar 12 posições da lista de 48 pela mesma regra para a busca grossa.
4. Para o benchmark, usar a posição `len(coarse)//2` da lista de 12: o elemento
   mediano superior. Os três universos ficam aninhados e seus índices exatos
   são gravados antes de executar qualquer candidato.

Essa distribuição é uniforme na ordem das anotações disponíveis. Com lacunas,
não corresponde a intervalos iguais no relógio. Os quadros do vídeo 23 sem
anotação continuam excluídos. Cada candidato recebe exatamente o mesmo universo.
Quadros adjacentes ou do mesmo vídeo não se tornam réplicas independentes.

Os pixels vêm da decodificação sequencial do MP4 canônico, desde o quadro 0,
sem seek por candidato. Os JPEGs fornecidos não substituem esses pixels,
pois podem conter diferenças de compressão. Guardar os 48 quadros selecionados
em um array BGR `uint8` por vídeo, sem nova compressão com perda, e consumir
o cache em modo somente leitura. “Sem perda” refere-se aos pixels já
decodificados, não ao vídeo microscópico antes de sua compressão original.

O cache registra índices, GT com IDs e precisão integral, hashes dos MP4,
labels e arrays, versão/backend do decodificador, código, ambiente, tempos e
memória. A identidade da amostra é obrigatória em cada execução; o hash dos
parâmetros, isoladamente, não identifica as imagens usadas.

## Espaço de busca grossa

| Parâmetro | Valores |
|---|---|
| Limiar de intensidade | 0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 190, 192, 200, 208, 224, 240, 255 |
| Iterações de abertura | 0, 1, 2 |
| Iterações de fechamento | 0, 1, 2 |
| Kernel morfológico | Elíptico, 3 × 3, fixo |
| Área aceita do componente | 3 a 300 pixels, inclusive, fixa |
| Blur, inversão e adaptativo | Desativados: blur=1, invert=false, adaptive=false |

São **19 × 3 × 3 = 171 configurações**, cada uma em **12 × 12 = 144
quadros**, totalizando **24.624 avaliações configuração–quadro**. O algoritmo
é o threshold fixo existente, sem Otsu misturado à mesma busca.

A grade de intensidade cobre toda a escala de 8 bits em passos grossos,
incluindo extremos; 190 e 200 são âncoras históricas explicitamente registradas.
Elas recebem as mesmas condições de avaliação que os demais valores.
O limiar de intensidade separa pixels; ele é diferente do raio de 10 px que
associa centros na avaliação. No modo binário usado, intensidades maiores
que o limiar tornam-se primeiro plano. [Documentação OpenCV](https://docs.opencv.org/4.13.0/d7/d4d/tutorial_py_thresholding.html).

Os níveis morfológicos representam ausência da operação e uma ou duas iterações.
Kernel, polaridade, blur e faixa de área preservam a definição operacional
do baseline. Não são declarados ótimos. A área de pixels de um componente
segmentado não equivale à área de sua caixa nem à área da caixa manual.
Um estudo posterior desses parâmetros exigirá outra definição prospectiva.

## Custo, ordem e falhas

O benchmark executa todas as 171 configurações em um quadro por vídeo:
**2.052 avaliações**, sem produzir lista de melhores parâmetros. Usa a
mesma detecção, avaliação e exportação pretendidas para a busca grossa.
A preparação do cache é medida separadamente e não é repetida por candidato.

A projeção operacional para a busca grossa é:

`tempo_validacao_cache + 2 × (12/1) × tempo_loop_candidatos_benchmark`.

O laço inclui detecção, matching, exportação, metadados e progresso; o fator 2
é margem operacional, não intervalo de confiança ou garantia de pior caso.
Um quadro por vídeo não cobre a variabilidade temporal do custo. A busca
grossa só inicia se o benchmark terminar completo e a projeção for ≤1.200 s.

Tetos operacionais: benchmark 600 s, busca grossa 1.800 s, RSS amostrado
2.048 MiB, artefatos da bateria 2.048 MiB, cache 1.024 MiB e 2.000 previsões
por quadro. Os limites são verificados entre operações: não são interrupções
rígidas de uma chamada nativa. Exceder um teto interrompe a bateria e preserva
o material parcial; não se truncam detecções para obter métricas favoráveis.
Os tetos de tempo são decisões de orçamento, não tempos previstos de execução.

Usar uma thread OpenCV, execução serial e ordem de candidatos embaralhada
deterministicamente com seed 42. O método é determinístico; repetir seeds não
criaria novos vídeos ou réplicas estatísticas. Tempos são informativos nesta
triagem e não decidem empates. Comparações finais de custo exigem medição própria.

Qualquer erro de leitura, hash, dimensão, GT, detector ou universo invalida a
bateria para seleção. Não continuar omitindo o quadro e comparar denominadores
diferentes. Não produzir ranking de candidatos parcialmente avaliados. Uma
mudança no orçamento ou espaço exige novo registro antes da execução correspondente.

## Agregação e seleção

Para cada candidato, somar TP/FP/FN nos 12 quadros de cada vídeo e calcular o
F1 daquele vídeo. O critério principal é a média dos 12 F1, com pesos iguais.
Não usar F1 dos totais de todos os vídeos ou média de F1 por quadro como substitutos.

Ordenar por F1 macro decrescente; em igualdade, recall macro decrescente,
MAE de contagem avaliada macro crescente e identificador crescente. O último
critério apenas garante ordem determinística, sem interpretação de superioridade.
Usar precisão integral para ordenar, sem arredondamento de apresentação.

Reportar também precisão, erros de centro, contagens brutas/avaliadas/ignoradas,
avaliação secundária de todos os objetos e sensibilidades de 15/20 px. Os
quadros anotados formam o denominador fixo da contagem. Não escolher o raio
que produz a classificação mais favorável e não usar os 12 vídeos como se
as 144 observações fossem 144 amostras independentes.

Somente uma busca grossa completa pode fornecer os cinco candidatos para
refinamento. Preservar a tabela de todos os 171 candidatos e os resultados
por vídeo; não salvar somente os vencedores.

## Refinamento e etapas posteriores

O refinamento previsto percorre todos os inteiros de T−15 até T+15 de cada
um dos cinco pais, limitados a 0–255, mantendo sua morfologia e a área 3–300.
Deduplicar parâmetros idênticos. Limite: 155 candidatos × 576 quadros =
89.280 avaliações, nos mesmos 48 quadros por vídeo já manifestados.

Esse desenho melhora a resolução do limiar em regiões selecionadas pelo
treino; não promete explorar todos os parâmetros conjuntamente. O teto
registrado é 7.200 s, mas a execução exigirá nova projeção de custo. O executor
deste marco oferece somente preparação, benchmark e busca grossa.

Depois de refinamento completo, duas finalistas poderão seguir para os
quatro vídeos completos de validação. Congelamento, avaliação reservada e
folds permanecem etapas posteriores, com a limitação histórica do teste
explicitada. A hipótese sobre fluxo óptico e predição não é testada nesta busca.

## Estado deste registro

O registro inicial antecedeu a formação do cache e qualquer resultado de
benchmark ou busca grossa. As subseções preservam a sequência das execuções
e revisões operacionais. O [estado mais recente](#refinamento-v3) é o
refinamento concluído no treino; a validação completa na v3 ainda está pendente.

### Primeiro benchmark e revisão operacional — 08/09/2026

O plano foi registrado em `9940337` antes da preparação real. A amostra foi
concluída em 19,29 s: 576 quadros, 532.540.304 bytes, com hashes verificados
e pico amostrado de RSS de 156,473 MiB. Seu identificador é
`77ad9cbda76c03d61f3b28dd99520d0c1d6e285452929d847742bc6331473478`.

O benchmark inicial terminou todas as 2.052 avaliações, com Git limpo e sem
classificação. O laço levou 131,7403 s; pela fórmula registrada, a projeção
foi 3.167,83 s, superior ao limite de 1.200 s. A busca grossa não foi iniciada
com esse benchmark. Detector, avaliação e exportação somaram respectivamente
6,569 s, 11,236 s e 2,823 s; o restante inclui a criação repetida das runs.

Um perfil de três contextos sintéticos, sem imagens reais, confirmou custo
dominante nas consultas ao Git: 1,998 s totais, dos quais 1,161 s na consulta
do estado, 0,378 s na consulta do commit e 0,218 s nos snapshots de ambiente.
A revisão operacional captura esses metadados uma vez por bateria, explicita
essa origem comum e confere o código e o Git ao encerramento. O plano,
os candidatos, os quadros, as métricas e o orçamento permanecem iguais.
O benchmark completo será repetido após um novo commit, em novas runs;
nenhuma métrica de qualidade foi usada para decidir essa otimização.

O primeiro benchmark e a análise de custo permanecem em
`data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark/`,
com `cost_review_20260908.json` como índice da revisão operacional.

<a id="resultados-v3"></a>

### Busca grossa concluída e conferida — 08/09/2026

A otimização foi registrada em `3f73a52`, após **442 testes aprovados**.
O segundo benchmark manteve plano e amostra: laço de 40,8452 s e projeção de
986,31 s, dentro do limite original. A comparação entre as duas execuções
confirmou os 171 arquivos de detecções/GT idênticos byte a byte e todas as
métricas por quadro iguais, exceto o tempo de detecção. A redução observada
de tempo é operacional, não uma estimativa estatística de aceleração.

A busca completa avaliou **171 configurações × 144 quadros = 24.624 casos**.
As 144 imagens contêm 2.961 anotações individuais e 44 agrupamentos, estes em
33 quadros. Cada vídeo contribuiu com 12 quadros. A run terminou em 291,32 s
(laço de 289,06 s), com pico amostrado de RSS de 94,594 MiB e 128.422.020 bytes
nos artefatos dos candidatos. Commit `3f73a52`, Git limpo e proveniência
reverificada antes da classificação. Validação e teste não foram processados.

| Ordem | Configuração | F1 macro | Recall macro | MAE de contagem |
|---:|---|---:|---:|---:|
| 1 | t224_o0_c2 | 0,7753 | 0,8424 | 4,1528 |
| 2 | t208_o0_c2 | 0,7557 | 0,8568 | 4,6111 |
| 3 | t224_o0_c1 | 0,7418 | 0,8504 | 5,7500 |
| 4 | t200_o1_c2 | 0,7410 | 0,7842 | 3,7292 |
| 5 | t208_o1_c2 | 0,7378 | 0,7727 | 4,1944 |


Os valores são médias entre os 12 vídeos de treino, calculadas após agregar
os quadros dentro de cada vídeo. A precisão média do primeiro colocado é
0,7374; seu F1 a 15/20 px é 0,7823/0,7836. Houve 15 previsões ignoradas a
10 px. No mesmo candidato, o F1 por vídeo variou de 0,6166 a 0,8982 nesta
amostra, mostrando que a média não descreve igualmente todos os vídeos.
T200/o1/c2 foi reavaliado na v3 e ficou em quarto; o registro congelado
histórico a 15 px permanece intacto. Nenhum desses resultados confirma
generalização, ótimo global, significância estatística ou promoção do método.

A conferência independente aprovou 1.205 arquivos, 1.631.066 comparações
numéricas e 72 verificações de associação com SciPy em casos predeterminados.
Reconstruiu agregações e a ordem dos 171 candidatos; não reutilizou o código
de avaliação ou classificação do projeto. Isso certifica a consistência dos
artefatos verificados, sem certificar completude do gabarito nem desempenho
em quadros não amostrados.

| Artefato local | Abrir |
|---|---|
| Busca completa | [Manifesto](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/manifest.json) |
| Classificação completa | [ranking.csv](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/ranking.csv) |
| Cinco candidatos | [shortlist.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/shortlist.json) |
| Conferência independente | [verification_20260908.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/verification_20260908.json) |
| Equivalência dos benchmarks | [benchmark_parity_20260908.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark/benchmark_parity_20260908.json) |
| Figura: curvas e resultados por vídeo | [PNG](../../data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.png) · [SVG](../../data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.svg) |
| Lista registrada antes do refinamento | [117 candidatos derivados](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/refinement_plan_20260908.json) |

Ao encerrar a busca grossa, foi registrada a lista para o refinamento
previamente definido. Deduplicar as faixas dos cinco pais produz **117 configurações**,
com 67.392 avaliações nos 576 quadros já preparados: T193–239 com abertura 0
e fechamento 2; T209–239 com abertura 0 e fechamento 1; T185–223 com abertura 1
e fechamento 2. Essa redução de 155 para 117 elimina apenas parâmetros
idênticos, conforme o plano. Área, kernel, polaridade e métrica permanecem
iguais. O estado `planned_not_executed` desse artefato descreve o instante
de seu registro; a execução posterior está documentada abaixo, em nova run.

### Execução do refinamento: orçamento registrado antes do benchmark

A [configuração operacional do refinamento](../../configs/detection/threshold/refinement_v3.yaml)
referencia por SHA-256 o plano-base, a busca grossa e a lista derivada dos
117 candidatos. O YAML original e a lista derivada permanecem imutáveis:
o campo histórico `design_only_not_executable_in_current_runner` descreve
o executor no instante do registro inicial, anterior à extensão da CLI.

O benchmark específico executará **todos os 117 candidatos nos mesmos 12
quadros de benchmark** do cache: 1.404 avaliações. Esses quadros pertencem à
amostra de 48 por vídeo já preparada. Não há escolha de novas imagens ou
alteração dos parâmetros por esse benchmark. A projeção será:

`validação do cache + validação dos pais + 2 × 48 × tempo do laço do benchmark`.

O fator 48 corresponde à passagem de um para 48 quadros por vídeo, e o fator
2 mantém a margem operacional anterior. Autorizar a execução se essa
projeção for **até 4.800 s**, preservando o teto registrado de **7.200 s** para
o refinamento e 600 s para seu benchmark. Essa escolha operacional antecede
o novo benchmark e não é determinada pelas métricas de qualidade. A projeção
não é garantia de pior caso temporal. Recursos mantêm os limites anteriores:
2 GiB de RSS, 2 GiB nos artefatos da bateria, no máximo 2.000 previsões por
quadro; exceder um limite interrompe a comparação, sem truncar previsões.

O refinamento avaliará novamente todos os candidatos em todos os **576
quadros**. Não somará resultados antigos de 12 quadros aos novos. Só uma
bateria completa, com proveniência revalidada, produzirá `finalists.json`
contendo os **dois primeiros** pela ordenação já registrada. Não forçar
diversidade de morfologia ou escolher finalistas pelas sensibilidades de
15/20 px. A finalidade é escolher candidatos para a futura validação completa,
sem promover ou congelar o método nesta etapa.

<a id="refinamento-v3"></a>

### Refinamento concluído no treino — 08/09/2026

Executor e orçamento registrados em **`da057ef`**, após **502 testes
aprovados** em 95,97 s e antes do novo benchmark. A validação somente dos
metadados da busca grossa reconstruiu os 117 candidatos e conferiu 1.035
entradas, preservando os pais na ordem original de classificação.

O benchmark específico concluiu 117 × 12 = 1.404 avaliações. O laço levou
16,9821 s; validar cache e pais levou 6,1535 s e 3,2060 s. A projeção registrada
foi **1.639,64 s**, inferior ao limite de liberação de 4.800 s. Não houve
seleção por qualidade nesse benchmark nem mudança de orçamento.

O refinamento concluiu **117 × 576 = 67.392 avaliações**, em **454,65 s**
para a bateria, incluindo 452,79 s no laço. A validação prévia do cache e
dos pais levou, separadamente, 5,94 s e 3,14 s. O pico amostrado de RSS foi
140,77 MiB, e os artefatos dos candidatos somaram 338.594.816 bytes.
Todas as runs registram Git limpo em `da057ef`; código, Git e ambiente foram
reconferidos antes do ranking. As fontes e as execuções anteriores permanecem
intactas; os novos resultados ficam em `data/tests/`, como seleção de treino.

| Ordem | Configuração | F1 macro a 10 px | Precisão macro | Recall macro | MAE de contagem |
|---:|---|---:|---:|---:|---:|
| 1 | t219_o0_c2 | 0,775790 | 0,729686 | 0,852050 | 4,255208 |
| 2 | t218_o0_c2 | 0,775634 | 0,728333 | 0,852686 | 4,237847 |

Ambos usam abertura desativada e duas iterações de fechamento. A diferença
de F1 é **0,000155871**, aproximadamente 0,0156 ponto percentual. A regra
registrada seleciona os dois primeiros, mesmo que tenham limiares vizinhos
e a mesma morfologia. O arredondamento da tabela não participou da escolha.
Esses valores são médias com peso igual entre os 12 vídeos, após agregar
48 quadros dentro de cada vídeo; não são o F1 calculado sobre a união de
todas as detecções.

Os 576 quadros contêm 11.864 anotações individuais e 176 de agrupamentos;
são observações por quadro, não contagens de células únicas. Cada finalista
teve 60 previsões ignoradas na avaliação principal. O F1 por vídeo do T219
variou de 0,5551 a 0,8847. A 15 px, os F1 macro de T219/T218 foram
0,783759/0,783613; a 20 px, 0,786210/0,786278. A pequena inversão de ordem
na sensibilidade de 20 px não muda a seleção pela regra principal de 10 px.

Não há teste de significância, intervalo de confiança ou declaração de
superioridade geral entre os finalistas. Também não se interpreta a
diferença para o F1 da busca grossa como melhora: a amostra passou de 12
para 48 quadros por vídeo. O refinamento é uma seleção local nos intervalos
registrados, sem demonstração de ótimo global ou de generalização.

A conferência independente foi aprovada na primeira execução: **2.451
arquivos**, **4.029.280 comparações de campos e valores** e **162 verificações
de associação com SciPy**. Reconstruiu a aritmética de todos os quadros, as
agregações por vídeo, o ranking dos 117 candidatos e os dois finalistas.
O matching independente abrangeu 27 combinações predeterminadas de candidato
e quadro, nas três tolerâncias e nas duas políticas; não refez todas as
associações da bateria. Os hashes, vínculos e registros de proveniência foram
conferidos a partir dos artefatos, sem nova leitura dos pixels ou do GT-fonte.

Os cinco pais também foram comparados nos quadros compartilhados com a
busca grossa: **720 pares configuração–quadro**, correspondentes a 144
quadros físicos distintos. Todas as linhas brutas de GT e previsões,
preservando multiplicidade, e todos os campos de métricas por quadro
coincidiram, exceto `detection_ms`. Isso confirma a consistência da
reavaliação, sem acrescentar réplicas independentes à análise.

| Artefato local | Abrir |
|---|---|
| Benchmark do refinamento | [Manifesto](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg10615a87/refinement_benchmark/20260908T145306368969Z__da057ef__cfg6ed5cd6a66dd__src3847d91dfb__s42/manifest.json) |
| Refinamento completo | [Manifesto](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/manifest.json) |
| Classificação dos 117 candidatos | [ranking.csv](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/ranking.csv) |
| Dois candidatos para validação | [finalists.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/finalists.json) |
| Conferência independente e equivalência dos pais | [verification_20260908.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json) |
| Curvas e comparação dos finalistas por vídeo | [PNG](../../data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.png) · [SVG](../../data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.svg) |
| Revisão da figura | [visual_review_20260908.json](../../data/derived/detection/search_reports/threshold_refinement_v3_20260908/visual_review_20260908.json) |

Próximo marco: registrar a validação v3 dos dois finalistas nos vídeos
completos 14/19/36/52, fixando parâmetros por hash, critério de escolha e
orçamento antes de ler esses dados. O executor deverá recusar leitura
incompleta, GT malformado e comparações com menos de oito runs completas,
além de registrar hashes e agregação com peso igual entre quatro vídeos.
O contrato atual de busca exige 12 vídeos e não será reutilizado silenciosamente
para esse universo diferente. Validação, congelamento, teste e confirmação
em folds permanecem pendentes na v3; a hipótese de predição com fluxo óptico
ainda não foi avaliada.
