# Matriz algoritmo × teste

Esta tabela é o quadro de acompanhamento. `✓` significa que há evidência no
repositório; `API` significa apenas que construtor/configuração foram validados;
`piloto` não é resultado do protocolo; `—` ainda precisa ser executado.

## Detecção

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
| Busca, seleção ou promoção de threshold na v3 | Não executadas |
| Plano prospectivo de busca — 08/09 | Registrado: 171 candidatos, 12 quadros por vídeo de treino; benchmark e busca aguardam execução |

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
permanecem preservados. **Nenhum método está promovido no contrato v3.** A
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

## Movimento aparente

| Algoritmo | Código | Translação sintética | Busca/val real | Máscara/ablação | Congelar | Teste | Cache 85 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lucas–Kanade | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Farneback | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Horn–Schunck | ✓ | ✓ translação pequena, single-scale | — | ✓ contrato; VISEM — | — | — | — |
| RAFT | ✓ | sem torch/pesos | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto CPU | ✓ | ✓ fusão e translação sem compensação | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto + RAFT | ✓ | sem torch/pesos | — | ✓ contrato; VISEM — | — | — | — |

O contrato de máscara une boxes dos dois frames e o enriquecimento de tracks
foi validado com vetores conhecidos e pixels inválidos. A coluna ainda marca
`VISEM —` porque a ablação real mascarado/não mascarado não foi executada.

## Predição

| Algoritmo | Código | Analítico/sintético | GT: tuning/val | Tracker: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistência | ✓ | ✓ | — | — | — | — | — | — |
| Velocidade constante | ✓ | ✓ | — | — | — | — | — | — |
| Kalman | ✓ | ✓ | — | — | — | — | — | — |
| Filtro de partículas | ✓ | ✓ | — | — | — | — | — | — |
| LSTM sem fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| LSTM com fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| Híbridos clássicos flow-aware | ✓ | ✓ | — | — | — | — | — | — |

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

O pesquisador autorizou continuidade autônoma. O próximo trabalho é
**planejar a busca prospectiva de threshold**, com raio e política de classes
já definidos. A repetição em `6b0a1e9` preservou parâmetros e contagens e
confirmou os erros reconstruídos dos CSVs a 1e-9 px. Formalizar a amostragem,
o espaço de busca, o orçamento e os critérios antes de executar a busca,
mantendo a limitação de exposição histórica do teste. O roteiro anterior de
teste isolado e folds permanece abaixo apenas como referência histórica.

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
