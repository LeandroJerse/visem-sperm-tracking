# Threshold adaptativo gaussiano

<!-- refinement-dataset-completion-20260911 -->
## Refinamento de treino concluído e conferido — 11/09/2026

Foram avaliadas 13 configurações locais desta família, nos mesmos 576 quadros dos 12 treinos, dentro da bateria completa de 45 configurações em `ca68f16`. Melhor da vizinhança: `adaptive_threshold_refinement_v1_007`, F1 macro a 10 px **0,446885**, precisão 0,338566, recall 0,854802; F1 a 15/20 px 0,457221/0,459709. Detecção média em cache: 3,303 ms/quadro; 786 previsões ignoradas a 10 px.

Parâmetros completos: `{"adaptive": true, "adaptive_block": 15, "adaptive_c": -5, "blur": 1, "close_iterations": 1, "invert": false, "max_area": 300, "min_area": 3, "morph_iterations": 2, "morph_kernel": 3, "threshold_value": null}`.

Finalistas: `adaptive_threshold_refinement_v1_007` e `adaptive_threshold_refinement_v1_013`. A paridade dos pais e as métricas passaram no QA independente; a validação comparativa completa ainda precisa de contrato e execução. A diferença local de F1 em relação à melhor da busca anterior foi 0,298196; é seleção no mesmo treino, sem confirmação independente, promoção ou demonstração de melhor tracking.

[Protocolo, resultados e hashes](../../metodologia/REFINAMENTO_CLASSICOS_V1.md) · [Resumo e valores por vídeo](../../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

A seção da busca abaixo é histórica; os parâmetros e números anteriores foram preservados.

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/adaptive_threshold/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | [Runs do método](../../../data/tests/detection/adaptive_threshold/) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Usa o registro `threshold` com `adaptive: true`; o identificador científico das saídas é `adaptive_threshold`. A implementação é compartilhada com os limiares fixo e Otsu.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Histórico — resultado da busca de treino — 11/09/2026

Foram 18 configurações nos mesmos 576 quadros dos 12 treinos, sob v3.
`adaptive_threshold_v1_002` foi a melhor desta grade: bloco 15, C=−5,
uma abertura e um fechamento, kernel 3, blur 1, objetos claros, área 3–300.
F1 macro a 10 px **0,148689**, precisão 0,083095, recall 0,929020;
F1 a 15/20 px 0,152374/0,154454. Foram 1.267 previsões ignoradas a 10 px,
após a proteção dos indivíduos. Detecção média em cache: 3,512 ms/quadro.

O recall alto vem com precisão muito baixa: localizar muitos indivíduos
acompanhados de muitos falsos positivos não produz bom F1. O F1 por vídeo
varia de 0,036974 no 23 a 0,355305 no 13. Não concluir que nenhuma
configuração adaptativa funcionaria: a conclusão cobre a grade registrada.

Uma configuração diferente, `adaptive_threshold_v1_004`, excedeu a guarda
de 2.000 previsões no smoke v1 e interrompeu o lote. A revisão v2 mudou
somente a guarda operacional e sua linhagem para permitir medir a
superdetecção; a run completa conservou candidatos e previsões. A falha
original permanece preservada, sem contagem exata acima de 2.000 registrada.

Pais para refinamento: `adaptive_threshold_v1_002` e
`adaptive_threshold_v1_008`. A vizinhança prospectiva varia bloco ±8,
C ±2 ou abertura ±1, um parâmetro por vez; novo YAML/executor e validação
completa são próximos passos, sem promoção agora.
[Resumo por vídeo](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, falha preservada, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md).

## Ideia

Cada pixel recebe um limiar calculado de sua vizinhança ponderada, menos uma
constante `C`. A máscara passa por morfologia e componentes conexos.

## Parâmetros a estudar

`adaptive_block` ímpar, `adaptive_c`, polaridade, blur, kernel,
abertura/fechamento e filtros de área.

## Pontos fortes

- acomoda gradientes de iluminação e regiões com fundo diferente;
- continua sem treino e com baixo custo;
- explicita o compromisso entre escala local (`block`) e sensibilidade (`C`).

## Pontos fracos

- amplifica textura e ruído local, criando muitos componentes;
- janela pequena fragmenta objetos; janela grande se aproxima do caso global;
- é sensível à resolução e exige calibração de `block`/`C`;
- pode marcar halos e bordas do microscópio como células.

## Adaptação e validação

O tamanho do bloco deve ser maior que uma cabeça típica e menor que a escala do
gradiente de fundo. Avaliar count bias e precision junto ao F1; não usar apenas
um frame central quando a iluminação muda ao longo do vídeo.
