# Híbrido CLAHE + correção de fundo + threshold

<!-- refinement-dataset-completion-20260911 -->
## Refinamento de treino concluído e conferido — 11/09/2026

Foram avaliadas 11 configurações locais desta família, nos mesmos 576 quadros dos 12 treinos, dentro da bateria completa de 45 configurações em `ca68f16`. Melhor da vizinhança: `hybrid_threshold_refinement_v1_002`, F1 macro a 10 px **0,364491**, precisão 0,273488, recall 0,662509; F1 a 15/20 px 0,375952/0,387783. Detecção média em cache: 4,770 ms/quadro; 292 previsões ignoradas a 10 px.

Parâmetros completos: `{"background_kernel": 15, "clip_limit": 0.5, "close_iterations": 1, "dark_objects": false, "max_area": 300, "min_area": 3, "morph_kernel": 3, "open_iterations": 1, "threshold_value": null, "tile_grid_size": 8}`.

Finalistas: `hybrid_threshold_refinement_v1_002` e `hybrid_threshold_refinement_v1_007`. A paridade dos pais e as métricas passaram no QA independente; a validação comparativa completa ainda precisa de contrato e execução. A diferença local de F1 em relação à melhor da busca anterior foi 0,179102; é seleção no mesmo treino, sem confirmação independente, promoção ou demonstração de melhor tracking.

[Protocolo, resultados e hashes](../../metodologia/REFINAMENTO_CLASSICOS_V1.md) · [Resumo e valores por vídeo](../../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

A seção da busca abaixo é histórica; os parâmetros e números anteriores foram preservados.

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [enhanced_threshold.py](../../../src/detection/hybrid/enhanced_threshold.py) — `HybridThresholdDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/hybrid_threshold/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | [Runs do método](../../../data/tests/detection/hybrid_threshold/) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Histórico — resultado da busca de treino — 11/09/2026

Oito configurações foram comparadas nos mesmos 576 quadros dos 12 treinos,
sob v3. A melhor desta grade, `hybrid_threshold_v1_002`, usa CLAHE com
clip 1 e grade 8, kernel de fundo 15, objetos claros, Otsu, uma abertura
e um fechamento com kernel 3, área 3–300. F1 macro a 10 px **0,185388**,
precisão 0,127623, recall 0,450986; F1 a 15/20 px 0,195339/0,212585.
Foram 222 previsões ignoradas a 10 px, após a proteção dos indivíduos.
Detecção média em cache: 4,950 ms/quadro.

O F1 varia de 0,005966 no vídeo 23 a 0,601578 no 13. Nesta grade, o
pré-processamento mais elaborado não produziu vantagem sobre a referência
T218. A comparação não isola cada etapa: atribuir a queda especificamente
ao CLAHE ou à correção de fundo exigiria ablações próprias. Não usar esses
números como prova de que todo realce de imagem prejudica a detecção.

Pais para refinamento: `hybrid_threshold_v1_002` e `hybrid_threshold_v1_001`.
A vizinhança prospectiva varia clip ±0,5, fundo ±8 ou abertura ±1,
um parâmetro por vez. Novo YAML/executor e validação completa permanecem
pendentes; nenhum híbrido foi promovido.
[Resumo por vídeo e sensibilidades](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).

## Ideia

Variante explicitamente híbrida de **etapas clássicas**: CLAHE normaliza
contraste local; top-hat (objetos claros) ou black-hat (escuros) remove o fundo
lento; Otsu ou limiar fixo segmenta; morfologia e componentes geram boxes.

## Parâmetros a estudar

`clip_limit`, `tile_grid_size`, `background_kernel`, `dark_objects`, limiar
opcional, kernel, abertura/fechamento e filtros de área.

## Pontos fortes

- trata iluminação não uniforme antes da decisão binária;
- preserva transparência e não requer labels, treino ou GPU;
- permite ablação direta: medir o ganho sobre threshold/Otsu puros.

## Pontos fracos

- acrescenta parâmetros correlacionados e custo de pré-processamento;
- CLAHE/top-hat podem realçar detritos, halos e ruído junto das células;
- kernel de fundo mal escolhido apaga o objeto ou deixa variação residual;
- não aprende contexto e ainda pode unir células próximas.

## Adaptação e validação

O kernel de correção deve ser maior que a cabeça espermática e sempre ímpar. A
implementação ajusta paridade e valida limites. Registrar como
`hybrid_threshold`, nunca como simples `threshold`, para custo e ganho não se
misturarem.
