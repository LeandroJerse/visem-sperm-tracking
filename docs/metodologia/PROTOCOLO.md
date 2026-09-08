# Protocolo experimental mestre

Este documento registra decisões metodológicas e o planejamento das etapas.
Na retomada de 07/09/2026, foram aprovados os centros como referência e o raio
principal de 10 px, com sensibilidade obrigatória a 15/20 px, e a política
principal de indivíduos com tratamento de agrupamentos descrita abaixo.
O pesquisador autorizou a continuidade autônoma com registros e commits.
Código, configuração, testes e orçamento prospectivo precisam existir antes
de uma bateria longa. Em 08/09, a busca grossa e o refinamento do threshold
concluíram a seleção de dois finalistas de treino. A conferência independente
do refinamento foi aprovada; o próximo marco é preparar a validação
completa dos quatro vídeos. Não houve promoção, validação completa ou teste
na v3. O desenho confirmatório posterior continua pendente.

## Escopo dos dados e interpretação do movimento

Decisão de escopo confirmada em 2026-09-07: o TCC utiliza exclusivamente
vídeos do VISEM e anotações do VISEM-Tracking, que estende a mesma coleção.
Os trechos iniciais de aproximadamente 30 segundos anotados em 20 vídeos
compõem o desenvolvimento e a avaliação quantitativa; os outros 65 vídeos,
sem tracking manual, destinam-se à aplicação posterior ao congelamento.
Não há uma segunda coleção de vídeos
com tubo no escopo deste trabalho.

Os artigos descrevem gravação por câmera acoplada ao microscópio, mas não
documentam tubo, bombeamento ou contracorrente imposta durante a aquisição.
O artigo original menciona deriva em algumas gravações; isso não identifica
sua causa nem demonstra uma contracorrente controlada. A ausência de um
aparato documentado também não comprova ausência absoluta de movimento do
líquido. Fontes: [VISEM, 2019](https://doi.org/10.1145/3304109.3325814) e
[VISEM-Tracking, 2023](https://www.nature.com/articles/s41597-023-02173-4).

A hipótese principal permanece: características locais de movimento aparente
por fluxo óptico, combinadas ao histórico de posições, podem reduzir ADE e
FDE em relação a preditores equivalentes que utilizem apenas posição e
velocidade. Essa hipótese não pressupõe contracorrente. Sem ground truth
físico correspondente, o fluxo óptico não mede a velocidade física do fluido.

A correção da origem dos dados preservou os splits, configurações congeladas
e resultados. A decisão posterior sobre a tolerância de detecção está
versionada na seção de detecção; não reescreve o histórico.

## Regra comum de promoção

O planejamento anterior registrou a seguinte sequência por algoritmo. A busca
e o refinamento do threshold já possuem um
[registro prospectivo próprio](BUSCA_THRESHOLD_V3.md). Os critérios da nova
validação, do congelamento e da confirmação em folds ainda precisam ser
detalhados antes dessas etapas. Preservar a lista abaixo não torna seus
desempates históricos uma regra automática da avaliação v3:

1. validar a implementação com caso sintético e smoke test;
2. fazer busca grossa exclusivamente no treino;
3. refinar as cinco melhores configurações;
4. rodar as duas finalistas nos quatro vídeos completos de validação;
5. escolher uma por métrica primária, desempatar por recall, latência e memória;
6. congelar parâmetros e hash da configuração;
7. executar uma única vez no teste bloqueado;
8. confirmar a configuração congelada em previsões fora da amostra de 5 folds;
9. fechar a ficha individual e incorporar o resultado na monografia.

### Estado atual do threshold e preparação da validação — 08/09/2026

A busca grossa preservada avaliou 171 configurações em 12 quadros por vídeo
de treino e forneceu cinco pais. O refinamento registrado percorreu 117
configurações distintas nos 48 quadros por vídeo já manifestados: **67.392
avaliações**, commit `da057ef`, Git limpo. A bateria terminou em 454,647241 s,
com pico amostrado de RSS de 140,77 MiB; **502 testes** passaram antes da
execução. A conferência independente foi aprovada na primeira execução:
2.451 arquivos, 4.029.280 comparações de campos/valores, ranking das 117
configurações e dois finalistas reconstruídos. Foram verificadas com SciPy
162 avaliações de matching em 27 combinações predeterminadas de
configuração/quadro, nos três raios e nas duas políticas. Os 720 pares
configuração/quadro dos cinco pais coincidiram com a busca grossa nos mesmos
144 quadros físicos, exceto pelo tempo `detection_ms`.

Foram selecionados **T219/o0/c2** e **T218/o0/c2**, com F1 macro de treino
de 0,775790026345069 e 0,7756341553985521, respectivamente. O F1 de cada vídeo
foi calculado após somar seus TP/FP/FN; a média deu o mesmo peso aos 12 vídeos.
O raio de 10 px, a política v3 e as sensibilidades de 15/20 px permaneceram
fixos. Esses resultados selecionam finalistas para desenvolvimento posterior,
sem promover o detector ou estimar desempenho fora da amostra de treino.
A diferença de aproximadamente 0,000156 de F1 macro é pequena nesta amostra;
não constitui evidência de superioridade estatística ou generalização.

O manifesto e `finalists.json` estão em
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/`.

O relatório local é
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json`;
a figura está em
`data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.png`,
com versão `refinamento_threshold_treino.svg` na mesma pasta. A verificação
reconstruiu toda a aritmética dos quadros e a agregação por vídeo. O matching
independente foi amostral, com GT dos CSVs das runs; fontes originais de
vídeos/anotações e pixels do cache não foram reabertos nessa conferência.

Preparar agora uma avaliação de **duas configurações × quatro
vídeos completos de validação: 14, 19, 36 e 52**. Antes de consultar essas
fontes, o registro deve fixar os parâmetros e hashes dos dois finalistas,
a agregação e o desempate entre quatro vídeos, o orçamento e o tratamento
de falhas. O desempate histórico por recall, latência e memória acima não
substitui esse registro; tampouco se deve transportar silenciosamente o
desempate da triagem de treino para outra etapa.

O [executor por split](../../script/detection/test/run_split.py) já encaminha
vídeos completos ao avaliador v3, mas ainda é necessário garantir oito runs
comparáveis: universo de quadros e anotações explícito, leitura estrita do GT,
recusa de cortes/subconjuntos ou término prematuro, hashes das entradas e
saídas e agregação específica dos quatro vídeos. Os utilitários de seleção
de treino exigem 12 vídeos. As configurações históricas T190/T200 a 15 px
permanecem preservadas e não devem servir como substitutas dos finalistas v3.
Essa preparação não abre o teste nem define automaticamente a confirmação
em folds, cujo desenho continua pendente.

As seeds de modelos estocásticos são `42`, `123` e `2026`. Buscas em massa
geram métricas e previsões, não MP4. MP4 é produzido nos quatro vídeos de teste
e em poucos casos típicos ou de falha.

### Guardas executáveis

- `split=test` é aceito exclusivamente com `stage=test`, `frozen=true` e um
  YAML existente dentro de `configs/frozen/`;
- os folds A-E são aceitos exclusivamente com configuração congelada e etapa
  `oof`, `five_fold` ou `cross_validation`;
- `search`, `refine` e `validation` nunca aceitam um fold como split;
- o alias `all`, por incluir o teste, só existe para `stage=final` com uma
  configuração congelada; a confirmação 5-fold sempre roda A-E separadamente;
- `stage=application` e `split=application` formam um par inseparável e também
  exigem configuração congelada;
- uma run congelada recusa overrides de algoritmo, parâmetros, métrica e
  amostragem. Stage, split, seed, vídeo e renderização continuam operacionais;
- quando o executor recebe um split/fold nomeado, o ID real obtido do vídeo,
  `detections.csv`, `tracks.csv` ou cache é conferido contra
  `configs/protocol/splits.yaml` antes do processamento pesado.

### Limitação do holdout recuperado

Antes deste protocolo, a exploração frame a frame usou três frames dos 20
vídeos, incluindo `24, 38, 47, 54` (30 summaries por vídeo na árvore
histórica). Esses quatro vídeos não são, portanto, um holdout totalmente cego.
As 120 observações permanecem marcadas como legado e não são usadas para a
seleção retomada. A execução confirmatória só pode ocorrer após congelamento
e aprovação do desenho. A simples aplicação de uma configuração já escolhida
a cinco grupos não remove a influência histórica nem estabelece avaliação
independente da seleção. O desenho dos folds continua pendente.

## Fila 0 — infraestrutura

- [x] Proteger a fonte LaTeX em `monografia/`.
- [x] Registrar split 12/4/4, cinco folds, seeds e manifesto dos 20 vídeos.
- [x] Validar disjunção dos splits e cobertura dos folds.
- [x] Fechar testes do alinhamento de GT por número de frame.
- [x] Fechar executor com `--config`, `--set`, `--split`, `--stage`, `--seed`.
- [x] Fechar tabelas SQLite de runs, métricas por frame/vídeo e custos.
- [x] Rodar toda a suíte curta antes de qualquer bateria.

Critério: ambiente reproduzível, monografia protegida, splits sem vazamento e
testes sintéticos verdes.

Fila 0 fechada em 2026-08-29 para o núcleo clássico/CPU. A validação específica
de PyTorch/CUDA para YOLO, RAFT e LSTM permanece antes das baterias neurais e
não deve ser confundida com a validação estrutural já concluída.

## Fila 1 — detecção

Unidade de triagem: frame para threshold/Otsu/adaptativo/Blob/Watershed/YOLO;
clipe com aquecimento para MOG2/KNN.

Ordem de fechamento do planejamento anterior, a revisar antes de novas buscas:

1. threshold fixo + morfologia (`T200/o1/c2` e `T190/o1/c1` obrigatórios);
2. Otsu;
3. threshold adaptativo;
4. híbrido de normalização local + realce morfológico + segmentação;
5. Blob;
6. MOG2;
7. KNN;
8. Watershed;
9. YOLO com early stopping e três seeds.

### Avaliação por centros aprovada na retomada

Identificador ativo: **`center_distance_v3_individuals_ignore_clusters_10px`** em
`evaluation.protocol_id` de `configs/protocol/splits.yaml`.
O gate principal é **10 px**, com matching Húngaro um-para-um. As análises de
sensibilidade a **15 e 20 px são obrigatórias e iguais para todos os detectores**,
mesmo quando alterarem a ordenação dos métodos. As distâncias usam a resolução
original de **640 × 480 px**, desfazendo redimensionamento e padding antes da
comparação. Essa decisão não altera os splits.

A escolha é uma convenção operacional de precisão de localização, não um
raio ótimo estimado ou uma medida do erro dos anotadores. O centro da caixa
é referência geométrica, não ground truth anatômico exato. Fundamentação e
limites: [Tolerância espacial](TOLERANCIA_ESPACIAL.md).

F1 por centros dos indivíduos anotados nas classes 0 e 2 é a métrica principal
de detecção (`f1_individuals_center_10px`). Todas as previsões participam do
matching, independentemente de sua classe prevista. Após associar os
indivíduos, previsões excedentes a até um raio de qualquer indivíduo são FP;
das demais, somente as de centro dentro de uma caixa GT de classe 1 são
ignoradas. Indivíduos anotados dentro de agrupamentos continuam avaliados.
A regra é recalculada nos três raios, sem garantia de F1 monotônico.
Nenhuma máscara manual é fornecida ao detector ou ao rastreador.

O resultado complementar `secondary_all_objects_*` avalia todos os objetos
anotados, com cada agrupamento contado como um objeto. Relatar contagens
brutas, avaliadas e ignoradas e cobertura dos agrupamentos por vídeo.
Precision, recall,
erro de centro dos pares aceitos, count MAE, bias, latência e RAM/VRAM
complementam a leitura; mAP é secundário no YOLO. O erro dos pares aceitos
não substitui contar FP/FN. A MAE de contagem principal usa previsões
avaliadas versus indivíduos GT, com denominador fixo de quadros anotados.
Casos sem referência, duplicatas e limites estão formalizados em
[Classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md).

Referência histórica: **`center_distance_v1_15px`**, com 15 px principal e
10/20 px de sensibilidade. Esse identificador retrospectivo não modifica
manifestos ou resultados antigos. YAMLs históricos T200/T190 e configurações
congeladas permanecem em 15 px; não são as configurações ativas da avaliação
v3. A versão intermediária `center_distance_v2_10px` registrou a escolha do
raio, antes da política de agrupamentos, sem novas runs de detector.
Não misturar métricas entre versões nem promover uma seleção histórica por
mudança de contrato. O smoke v3 usa somente parâmetros históricos fixos,
três quadros dos vídeos de treino 11 e 12, para verificar a implementação.
Ele não é busca, validação completa ou promoção de algoritmo.

Saída: um vencedor congelado por método e dois detectores na fronteira de Pareto
(melhor qualidade e melhor eficiência).

## Fila 2 — tracking

Cada tracker roda em dois cenários: boxes GT (associação isolada) e boxes do
detector congelado (fim a fim).

1. centroide guloso;
2. associação Húngara;
3. SORT (Kalman + Húngaro);
4. ByteTrack, principalmente com scores do YOLO;
5. híbrido adaptativo com movimento/fluxo, comparado separadamente.

Promoção: HOTA; complementares IDF1, MOTA, ID switches, fragmentações, track
recall, mediana/p95 de tempo por frame e memória. O adaptador TrackEval está
pronto; a dependência e a avaliação oficial ainda precisam ser executadas.

## Fila 3 — movimento aparente

1. Lucas–Kanade esparso;
2. Farneback denso;
3. Horn–Schunck denso e suave;
4. RAFT opcional;
5. híbrido robusto CPU (compensação global/consistência + estimador local);
6. o mesmo híbrido com refino RAFT, como variante neural separada.

Avaliação: erro fotométrico pós-warp, consistência forward/backward, estabilidade
temporal e latência. EPE só em sequências sintéticas com deslocamento conhecido.
Ao estimar fundo, células/artefatos são mascarados. Features cacheadas por ponto:
`flow_u`, `flow_v`, magnitude e direção.

O handoff também é parte da ablação: as caixas dos dois frames podem mascarar
células/artefatos na estimação, e o cache é associado às tracks por amostragem
direta ou por anel de fundo. Medida ausente permanece inválida, nunca é
codificada como vetor zero.

## Fila 4 — predição

Histórico padrão de 20 frames; horizontes 1, 5 e 10. Primeiro trajetórias GT,
depois trajetórias do tracker. O split é sempre por vídeo.

1. persistência;
2. velocidade constante;
3. Kalman;
4. filtro de partículas;
5. LSTM sem fluxo;
6. LSTM com fluxo;
7. híbrido cinemático/fluxo, se distinto das ablações acima.

Promoção: ADE e FDE, com erro por horizonte, duração de trajetória e densidade.
A ablação LSTM usa exatamente dados, arquitetura, seeds e hiperparâmetros iguais;
somente as features de fluxo mudam.

## Fila 5 — estatística e aplicação

- Agregar primeiro por frame/trajetória e depois por vídeo.
- Três ou mais métodos: Friedman e Wilcoxon pareado pós-hoc com Holm.
- Dois métodos: Wilcoxon pareado.
- Reportar diferença pareada, efeito e IC95 por bootstrap agrupado por vídeo.
- Construir fronteiras de Pareto sem placar único subjetivo.
- Medir qualidade, mediana/p95/FPS/memória, treino, tamanho, esforço registrado,
  dependências, labels e necessidade de GPU/calibração.
- Retreinar modelos aprendidos nos 20 anotados com hiperparâmetros congelados.
- Executar os dois representantes nos 65 sem tracking e exportar tabelas/caches.
- Nesses 65, relatar aplicação e estabilidade; não acurácia contra ground truth.

## Critérios de aceitação antes de dizer “concluído”

- matching sintético tem TP/FP/FN conhecidos e associação um-para-um;
- labels ausentes não viram frames negativos;
- MOG2/KNN reiniciam por vídeo e excluem aquecimento;
- tracking cobre cruzamento, desaparecimento e nascimento sintéticos;
- fluxo recupera translação sintética dentro da tolerância;
- janelas não atravessam splits, IDs nem lacunas;
- ADE/FDE batem com exemplos analíticos;
- cada run guarda config resolvida, seed, commit, ambiente, status e custo;
- nenhuma execução sobrescreve outra;
- conjunto de teste só é usado depois do congelamento.
