# Matriz algoritmo × teste

<!-- refinement-dataset-completion-20260911 -->
## Estado vigente — refinamento clássico e dataset conferidos

Refinamento concluído e conferido em `ca68f16`, com Git limpo na execução: **45 configurações × 576 quadros = 25.920 avaliações**, somente nos 12 treinos. A vizinhança previamente definida gerou 54 propostas, 51 válidas e 45 configurações únicas. Os dez pais passaram na paridade de objetos brutos e métricas; T218 permaneceu histórico, sem nova execução. Há dez finalistas, duas por família, sem promoção ou liberação automática da validação.

Bateria: 528,244100 s; RSS amostrado 410,406 MiB; 394.820.008 bytes dos artefatos das candidatas, excluindo o agregador. QA: 1.061 arquivos, 39.670.198 comparações, 26.831.879 numéricas e 155.520 matchings SciPy em 281,243874 s; diferença numérica máxima 0.

[Manifesto do refinamento](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json) · [Resumo e resultados por vídeo](../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

| Família | Melhor configuração local | F1 macro 10 px | Precisão | Recall | ms/quadro |
|---|---|---:|---:|---:|---:|
| Blob | `blob_refinement_v1_001` | 0,791005 | 0,760180 | 0,848556 | 1,257 |
| Watershed | `watershed_refinement_v1_003` | 0,627005 | 0,567531 | 0,794746 | 21,020 |
| Otsu | `otsu_refinement_v1_003` | 0,626315 | 0,591799 | 0,742933 | 2,208 |
| Adaptativo | `adaptive_threshold_refinement_v1_007` | 0,446885 | 0,338566 | 0,854802 | 3,303 |
| Híbrido CLAHE | `hybrid_threshold_refinement_v1_002` | 0,364491 | 0,273488 | 0,662509 | 4,770 |

Os números apresentados descrevem a melhor configuração da vizinhança por família no treino. Frames e configurações não são réplicas independentes; F1 é calculado dentro de cada vídeo e depois recebe peso igual entre vídeos. Esforço desigual e seleção prévia de T218 impedem interpretar este ranking como superioridade universal ou detector final da pipeline. Tempo com imagem em cache não mede a cadeia completa.

Dataset YOLO materializado e conferido em `ca68f16`: **23.316 pares JPEG/anotação**, sendo 17.466 de treino e 5.850 de validação; 174 lacunas de anotação excluídas. Preservadas as três classes e as caixas da referência FTID. O conjunto contém 491.729 observações anotadas, não indivíduos únicos. Foram copiados 46.632 arquivos e gerados três descritores.

Preparação: 1.237,798253 s; RSS amostrado 198,160 MiB; dataset com 1.471.015.512 bytes. QA: 116.590 arquivos, 8.724.385 comparações e 23.316 cópias JPEG decodificadas em 195,027052 s. A conferência verificou paridade de 491.729 anotações, com diferença máxima 0.

[Manifesto do dataset](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json). O teste ficou fora da preparação. **Não houve treinamento YOLO:** `training_allowed=false` e `consumer_clone_required=true`; o consumidor deve gerar outro clone independente dentro de sua própria run antes de chamar a biblioteca.

A paridade geométrica entre anotações YOLO e FTID não certifica igualdade de pixels entre JPEG e MP4. Os JPEGs servem ao treinamento e à validação nativa do modelo aprendido. Para comparar F1 v3 com os clássicos, YOLO deverá processar os mesmos quadros MP4/cache usados por eles, com pré-processamento explicitamente registrado. Essa distinção delimita o derivado e o futuro contrato de comparação; não representa falha na organização atual do dataset.

Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold.

As tabelas e etapas seguintes preservam os resultados anteriores; suas pendências de busca/refinamento/preparação correspondem ao momento histórico indicado.

Esta tabela é o quadro de acompanhamento. `✓` significa que há evidência no
repositório; `API` significa apenas que construtor/configuração foram validados;
`piloto` não é resultado do protocolo; `—` ainda precisa ser executado.

## Detecção

### Histórico — busca estática concluída e conferida — 11/09/2026

O [protocolo comparativo](../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026)
concluiu smoke de 516 avaliações e busca de **43 × 576 = 24.768 avaliações**
em `2547109`, com Git limpo. São 48 quadros por vídeo, somente nos 12 treinos.
As cinco famílias pesquisadas conservam duas candidatas cada para refinamento;
T218 entra como referência fixa. A tabela mostra apenas a melhor configuração
de cada família **dentro da grade registrada**, sem promoção.

| Família | Configurações nesta busca | Melhor da grade | F1 macro 10 px | Detecção ms/quadro | Estado seguinte |
|---|---:|---|---:|---:|---|
| Blob | 6 | `blob_v1_003` | 0,791005 | 1,285 | Refinar 003/002 |
| Threshold fixo | 1 referência | `t218_o0_c2_reference_v1` | 0,775634 | 1,950 | Preservar referência; sem novo ajuste |
| Watershed | 6 | `watershed_v1_005` | 0,609765 | 21,674 | Refinar 005/002 |
| Otsu | 4 | `otsu_v1_004` | 0,546675 | 2,172 | Refinar 004/003 |
| Híbrido CLAHE | 8 | `hybrid_threshold_v1_002` | 0,185388 | 4,950 | Refinar 002/001 |
| Adaptativo | 18 | `adaptive_threshold_v1_002` | 0,148689 | 3,512 | Refinar 002/008 |
| MOG2/KNN | Fora desta busca estática | — | — | — | Registrar execução temporal contínua com aquecimento |
| YOLO | Fora desta busca clássica | — | — | — | Derivado autenticado e novo executor estrito antes do treino |

F1 é calculado após somar TP/FP/FN dentro do vídeo e depois dar peso igual
aos 12 vídeos. Blob fica acima de T218 em 7/12 vídeos, com diferença macro
de 0,015371, aproximadamente 1,54 ponto percentual. É uma diferença
descritiva no treino, sem significância ou generalização demonstradas.
A grade tem esforço desigual e T218 já havia recebido ajuste extenso.
Os 576 quadros e as 24.768 avaliações não são réplicas independentes.

A conferência passou na primeira tentativa: 289 arquivos, 30.927.965
comparações, 21.050.826 numéricas, 148.608 matchings SciPy, diferença máxima
zero, 338,200844 s. Reconstruiu derivados e métricas sem repetir inferência
ou decodificação. T218 reproduziu a evidência anterior dos mesmos 576
quadros, exceto tempo e identidade da nova execução. Fonte e QA estão
vinculados no [resumo autenticado](../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json).
SHA256 do manifesto: `8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0`;
SHA256 do QA: `c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792`.

Run de 752,160737 s após a autenticação inicial do cache, 823,145 MiB de
RSS amostrado e 523.379.582 bytes de artefatos das candidatas. Tempo da
tabela mede detecção em cache, sem a pipeline completa. O smoke v1 falhou
com a guarda de 2.000 previsões; a revisão v2 elevou-a a 307.200 mantendo
dados, grade e limites de RAM/artefatos de 2.048 MiB. Falha e YAML original
foram preservados, sem truncar saídas ou remover candidatas.

Próximo marco: novo YAML/executor para refinamento local e, após conferência,
validação das finalistas nos quatro vídeos completos. Ainda faltam as
comparações temporal e aprendida pertinentes antes de escolher o detector
da cadeia. Rastreamento/HOTA e predição/ADE/FDE exigem avaliação própria;
nenhuma célula dessas etapas é concluída por um F1 de detecção. As tabelas
históricas abaixo permanecem identificadas com seus contratos originais.

### Contrato ativo da retomada — 07/09/2026

**`center_distance_v3_individuals_ignore_clusters_10px`**: indivíduos das
classes 0/2 como alvos, regiões de agrupamentos para ignorados após o matching,
raio principal 10 px e sensibilidades obrigatórias 15/20 px. A análise
secundária `binary_all_objects` inclui todos os objetos. As predições não são
filtradas pela classe prevista, e os discos de proteção dos indivíduos
impedem que duplicatas próximas sejam ignoradas.

| Marco atual | Estado |
|---|---|
| Auditoria de geometria dos 12 vídeos de treino | Concluída; descrição do GT, sem detector |
| Auditoria das regiões de agrupamento | Concluída; contagens, união exata das caixas e figura do GT |
| Avaliador v3 e precisão de exportação | Implementados; suíte curta com 287 testes passou após seis regressões adicionais |
| Smoke inicial: frames 0–2 de cada vídeo 11/12 | Executado; duas runs completas no commit 42ced6b, Git limpo; TP/FP/FN confirmados |
| Fechamento do nível 2 | Concluído após repetir os mesmos seis frames em duas novas runs de 6b0a1e9, Git limpo; 36 associações e 168 comparações espaciais independentes aprovadas |
| Busca grossa e seleção de treino na v3 | Concluídas: 171 × 144 avaliações; cinco candidatos para refinamento; nenhuma promoção |
| Plano prospectivo de busca — 08/09 | Registrado antes da execução em 9940337; otimização 3f73a52; 442 testes aprovados e conferência independente da busca |
| Refinamento e seleção de treino v3 — 08/09 | Concluídos em da057ef, Git limpo: 117 × 576 = 67.392 avaliações; 502 testes aprovados; conferência independente aprovada na primeira execução |
| Dois finalistas de treino | T219/o0/c2 e T218/o0/c2; comparados posteriormente na validação completa |
| Revisão geral de alinhamento | Aprovada com controles documentados; 3.248 arquivos e 17.753 conferências de integridade, 502 testes antes das alterações |
| Validação v3 completa | 11.700 avaliações em 7f47afb, Git limpo; 824 testes antes da execução; conferência independente aprovada |
| Seleção de validação | T218/o0/c2: F1 macro 0,658959; T219: 0,657819; a bateria precedeu o congelamento de desenvolvimento |
| Congelamento v3 | T218/o0/c2 fixa para desenvolvimento; teste e folds bloqueados pelo escopo executável |
| Referência individual do treino | Concluída em 33d191d: 363.074 observações, 725 segmentos, 343.776 janelas; 86 arquivos conferidos |
| Baselines de predição no treino | Concluídos em 5289c93: persistência e CV mediana5 nas mesmas 343.776 janelas; conferência integral aprovada |
| Nível 7 concluído e conferido | Farnebäck causal em 11/12, origem 19: 40 quadros, 68 janelas, 1.292 amostras válidas; QA 190 arquivos. Sem busca, ablação ou predição |
| Nível 8a concluído e conferido | 720 quadros, 10.848 janelas, 15.762 amostras distintas; QA 288 arquivos. Projeção 134,21 min não passou no teto histórico de 120 min. Novo plano de 11/09 permite monitorar tempo sem esse corte; a CLI compacta continua sem liberar extração completa. Preditor com fluxo só testado sinteticamente |
| Contrato HOTA | Desenho próprio em preparação, com YAML de smoke; avaliador e bateria real ainda não liberados |

[Resultados, oito pares configuração–vídeo, figura e conferência](../metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026).
Cada finalista vence em dois vídeos; a diferença macro de 0,11403 ponto
percentual não demonstra superioridade geral. A conferência verificou 46
arquivos, 1.772.878 campos/valores e 144 matchings. As duas correções do
verificador e as tentativas iniciais estão preservadas; as runs não mudaram.

A [busca grossa v3](../metodologia/BUSCA_THRESHOLD_V3.md) selecionou para refinamento
T224/o0/c2, T208/o0/c2, T224/o0/c1, T200/o1/c2 e T208/o1/c2.
O primeiro atingiu F1 macro de treino de 0,7753 a 10 px, após agregação por
vídeo. São resultados de seleção em 12 quadros por vídeo, sem promoção.

O refinamento posterior usou os 48 quadros por vídeo previamente manifestados.
T219/o0/c2 obteve F1 macro de treino de **0,775790026345069** e T218/o0/c2,
**0,7756341553985521**, nessa ordem. O lote terminou em 454,647241 s, com pico
amostrado de RSS de 140,77 MiB. Os dois foram selecionados pelo critério
registrado, sem escolher morfologias diferentes artificialmente. Esses
valores descrevem a seleção no treino e não uma estimativa de generalização.
A diferença de aproximadamente 0,000156 de F1 macro é pequena nesta amostra
e não demonstra superioridade estatística.
Manifesto, ranking e `finalists.json` ficam em
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/`.

A conferência independente aprovou 2.451 arquivos, 4.029.280 comparações de
campos/valores, o ranking das 117 configurações e os dois finalistas. Houve
162 verificações de matching com SciPy em 27 combinações predeterminadas
de configuração/quadro. Os 720 pares configuração/quadro dos cinco pais nos
144 quadros físicos comuns coincidiram com a busca grossa, exceto pelo tempo
`detection_ms`. A aritmética e a agregação foram verificadas integralmente;
o matching foi amostral, a partir dos CSVs, sem reabrir fontes ou pixels.
Relatório local:
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json`.
Figura local:
`data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.png`
(também disponível como `refinamento_threshold_treino.svg` na mesma pasta).

O [plano de validação](../metodologia/VALIDACAO_THRESHOLD_V3.md) registra
agregação, desempates, orçamento e hashes dos finalistas. O coordenador próprio
exige oito runs completas, GT estrito, leitura até o fim e reconciliação dos
CSVs; a agregação específica dá peso igual aos quatro vídeos. A
[revisão geral](REVISAO_GERAL_20260908.md) registra alinhamento e limites. O [protocolo mestre](../metodologia/PROTOCOLO.md)
mantém separadas essas pendências e as decisões históricas a 15 px.

A auditoria encontrou 5.413 anotações de agrupamento em 4.056 quadros dos
vídeos 11/12/15/29. Há 4.250 centros individuais dentro das regiões e 6.277
caixas individuais com interseção positiva; zero quadros contêm somente
agrupamentos. A cobertura da união exata é, em média, 0,2869% considerando
todos os quadros anotados e peso igual entre os 12 vídeos; condicionada a
quadros com agrupamento, a média entre os quatro vídeos pertinentes é 1,1233%.
São observações por quadro e geometria de caixas, não células únicas ou
segmentações. Os artefatos locais ficam em
`data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/`.

A versão `center_distance_v2_10px` e T200 sob a avaliação histórica de 15 px
permanecem preservados. **Nenhum método está promovido para teste/aplicação
no contrato v3; T218 está congelado somente para desenvolvimento.** A
tabela seguinte mantém as evidências anteriores; suas marcas não indicam
smoke, validação ou congelamento sob a nova política de agrupamentos.

### Evidências históricas de detecção

| Algoritmo | Código | Sintético/smoke | Busca treino | Refinar top 5 | 2 finalistas: val completa | Congelar | Teste 24/38/47/54 | 5-fold OOF | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Threshold fixo | ✓ | ✓ | piloto | duas finalistas preservadas | ✓ vídeos 14/19/36/52 | ✓ T200/o1/c2 | — | — | — |
| Otsu | ✓ | ✓ sintético | piloto | — | — | — | — | — | — |
| Adaptativo | ✓ | ✓ sintético | piloto | — | — | — | — | — | — |
| Threshold híbrido | ✓ | ✓ | — | — | — | — | — | — | — |
| Blob | ✓ | ✓ sintético | exploração | — | — | — | — | — | — |
| MOG2 | ✓ | ✓ sintético/reset + executor temporal | exploração | — | — | — | — | — | — |
| KNN | ✓ | ✓ sintético/reset + executor temporal | — | — | — | — | — | — | — |
| Watershed | ✓ | ✓ sintético | exploração | — | — | — | — | — | — |
| YOLO | ✓ | ✓ wrapper lazy/fake; piloto real | piloto 16/4 | — | — | — | — | — | — |

As configurações `T200/o1/c2` e `T190/o1/c1` foram executadas nos quatro vídeos
completos de validação. T200 venceu em F1 macro por vídeo e erro de contagem;
T190 reteve a vantagem de recall. A decisão foi registrada e T200 foi
congelado antes da execução confirmatória. Os quatro vídeos do holdout já
apareceram no piloto frame a frame antigo; por isso ele não é totalmente cego,
mas aquelas observações legadas não entram na seleção atual. O smoke curto
apenas validou o executor e não entra na tabela científica final.
O avaliador secundário YOLO/mAP também está validado estruturalmente, mas ainda
precisa de pesos novos para produzir evidência no split oficial.
MOG2 e KNN agora possuem uma bancada específica para clipes distribuídos no
treino, com `>=100` frames de aquecimento descartados e agregação macro por
vídeo. Nenhuma bateria VISEM desse grid foi executada durante a organização.

## Tracking

| Algoritmo | Código | Teste sintético | Boxes GT: tuning/val | Detector congelado: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Centroide guloso | ✓ | ✓ | — | — | — | — | — | — |
| Húngaro | ✓ | ✓ | — | — | — | — | — | — |
| SORT | ✓ | ✓ | — | — | — | — | — | — |
| ByteTrack-style | ✓ | ✓ | — | — | — | — | — | — |
| Adaptive Flow-SORT | ✓ | ✓ | — | — | — | — | — | — |

O adaptador para TrackEval existe; HOTA, IDF1 e MOTA completos continuam
pendentes de execução com a dependência externa. Os contadores locais de
associação, ID-switch e fragmentação são auditoria, não substitutos dessas
métricas.

Em 11/09 foi registrado o desenho
[Rastreamento comparação v1](../metodologia/RASTREAMENTO_COMPARACAO_V1.md):
diagnóstico com caixas GT sem IDs, depois detecções automáticas e ablação
do fluxo na associação. O YAML descreve o smoke, mas a CLI histórica não
implementa ainda todas essas garantias; o contrato e a bateria não estão
liberados apenas por existirem arquivos. Nenhuma célula da tabela acima
passa a avaliação VISEM concluída por esse registro documental.

## Movimento aparente

| Algoritmo | Código | Sintético/arquitetura | Busca/val real | Máscara/ablação | Congelar | Teste | Cache 85 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lucas–Kanade | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Farneback | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Horn–Schunck | ✓ | ✓ translação pequena, single-scale | — | ✓ contrato; VISEM — | — | — | — |
| RAFT | ✓ | ✓ small CUDA sem pesos; forma/finitude, sem EPE | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto CPU | ✓ | ✓ fusão e translação sem compensação | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto + RAFT | ✓ | CUDA disponível; híbrido com pesos ainda pendente | — | ✓ contrato; VISEM — | — | — | — |

**Atualização de 09/09/2026:** [smoke causal de Farnebäck](../metodologia/FLUXO_CAUSAL_V1.md) concluído e conferido em `16eecbb`, QA corrigido em `0fccda8`. Uma configuração fixa, sem máscara, quadros 0..19 dos treinos 11/12. A coluna busca/val real permanece pendente: este smoke não seleciona parâmetros nem testa a hipótese.

O contrato legado de máscara une boxes dos dois frames e o enriquecimento de tracks
foi validado com vetores conhecidos e pixels inválidos. A coluna ainda marca
`VISEM —` porque a ablação real mascarado/não mascarado não foi executada.

## Predição

A [referência individual v1](../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md#resultados-da-preparação--08092026)
foi preparada e conferida somente no treino: 363.074 observações, 725 segmentos
e 343.776 janelas. Os 102 segmentos sem janela foram preservados. A
[bateria fixa v1](../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)
concluiu persistência e CV mediana5 nessas mesmas janelas; a conferência
independente aprovou previsões, métricas e agregações. Isso é desenvolvimento
descritivo com GT de treino, sem tuning, validação, seleção de vencedor ou fluxo.

| Algoritmo | Código | Analítico/sintético | GT: desenvolvimento fixo | GT: tuning/val | Tracker: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistência | ✓ | ✓ | ✓ v1 | — | — | — | — | — | — |
| Velocidade constante | ✓ | ✓ | ✓ mediana5 v1 | — | — | — | — | — | — |
| Kalman | ✓ | ✓ | — | — | — | — | — | — | — |
| Filtro de partículas | ✓ | ✓ | — | — | — | — | — | — | — |
| LSTM sem fluxo | ✓ | ✓ arquitetura CUDA e backward; treino pendente | — | — | — | — | — | — | — |
| LSTM com fluxo | ✓ | ✓ arquitetura CUDA e backward; treino pendente | — | — | — | — | — | — | — |
| Híbridos clássicos flow-aware | ✓ | ✓ | — | — | — | — | — | — | — |

## Ambiente aprendido — engenharia conferida em 11/09/2026

`.venv-ml` preserva a `.venv` clássica: Python 3.13.3, torch 2.9.1+cu128,
torchvision 0.24.1+cu128, Ultralytics 8.4.147, 55 versões fixadas e
`pip check` aprovado. Seis checks passaram em 12,0624322 s na RTX 4070 Ti:
matmul e NMS CUDA, RAFT small sem pesos, YOLOv8n YAML de três classes, LSTM
sem/com fluxo com forward e backward finitos. Zero dados VISEM, pesos
externos e passos de otimização nesse smoke. A capacidade da LSTM aumenta
de 22.868 para 23.380 parâmetros com fluxo e precisa de controle próprio
na ablação científica.

Esse resultado não substitui treinamento YOLO, pesos RAFT, avaliação de
fluxo ou ADE/FDE aprendidos. O próximo preparo YOLO deve produzir cópia
derivada autenticada, impedir caches/reparos nas fontes e assegurar que o
executor repasse e registre os parâmetros efetivos. Não usar o executor
histórico como se essas garantias já estivessem implementadas. Evidência:
[Ambiente aprendido v1](../metodologia/AMBIENTE_APRENDIDO_V1.md), recibo
`data/derived/project_audits/learned_environment/20260911_validation_v1.json`,
SHA256 `29414ce0667c40ccd23e317cc86c07b6ed048e2efa249d968fb60c3fa907312b`.

## Nível 2 concluído: precisão dos CSVs conferida

O smoke inicial do contrato v3 está concluído. A verificação independente
confirmou TP/FP/FN, mas identificou que os centros exportados em
`detections.csv` eram arredondados a duas casas, impedindo reconstruir
exatamente as somas de distâncias calculadas com os valores originais.
A correção e seis regressões adicionais estão implementadas; a suíte curta
completa passou com 287 testes. A repetição em novas runs confirmou os erros
espaciais reconstruídos a 1e-9 px. Foram executados somente os frames 0–2 dos vídeos de treino
11/12, com `protocol_smoke_v3.yaml`: 106 TP/29 FP/23 FN no vídeo 11 e
73 TP/9 FP/10 FN no vídeo 12, a 10 px. Ambos os manifestos registram
`status: complete`, commit `6b0a1e9` e `git_dirty: false`. As duas runs
iniciais de `42ced6b` permanecem preservadas junto às duas corrigidas.

Nenhuma predição foi ignorada no smoke, inclusive nos frames com agrupamento
do vídeo 12. Testes sintéticos cobrem ignorados, proteção de duplicatas e
ramos de quadros vazios; esses casos não foram todos exercitados no smoke.
As métricas dos seis frames são diagnóstico de engenharia, não estimativa
de qualidade geral, ranking ou seleção de limiar. As runs locais estão em
`data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/`.

O pesquisador autorizou continuidade autônoma. Naquele marco, o próximo
trabalho era registrar a busca prospectiva, posteriormente executada junto
ao refinamento descrito no estado atual. A repetição em `6b0a1e9` preservou
parâmetros e contagens e confirmou os erros reconstruídos dos CSVs a 1e-9 px.
A limitação de exposição histórica do teste permanece. O roteiro anterior
de teste isolado e folds segue abaixo apenas como referência histórica.

<details>
<summary>Roteiro anterior: teste isolado do threshold</summary>

1. Conferir a seleção e o YAML congelado já registrados.
2. Fazer commit do estado limpo e executar uma única bateria confirmatória nos
   vídeos `24, 38, 47, 54`, registrando a exposição histórica como limitação.
3. Manter as runs de validação em `data/tests/` e gravar somente o teste
   congelado para `data/results/`.
4. Agregar o resultado por vídeo e registrar falhas visuais, latência e memória.
5. Produzir a confirmação 5-fold congelada e, em seguida, iniciar o mesmo ciclo
   para Otsu e threshold adaptativo.

</details>

Os comandos vigentes estão em [`script/README.md`](../../script/README.md).
