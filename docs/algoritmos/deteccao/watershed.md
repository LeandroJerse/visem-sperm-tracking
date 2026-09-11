# Watershed por marcadores

<!-- refinement-dataset-completion-20260911 -->
## Refinamento de treino concluído e conferido — 11/09/2026

Foram avaliadas 7 configurações locais desta família, nos mesmos 576 quadros dos 12 treinos, dentro da bateria completa de 45 configurações em `ca68f16`. Melhor da vizinhança: `watershed_refinement_v1_003`, F1 macro a 10 px **0,627005**, precisão 0,567531, recall 0,794746; F1 a 15/20 px 0,637745/0,639022. Detecção média em cache: 21,020 ms/quadro; 146 previsões ignoradas a 10 px.

Parâmetros completos: `{"blur": 5, "dist_ratio": 0.4, "invert": false, "max_area": 300, "min_area": 3, "morph_kernel": 3}`.

Finalistas: `watershed_refinement_v1_003` e `watershed_refinement_v1_005`. A paridade dos pais e as métricas passaram no QA independente; a validação comparativa completa ainda precisa de contrato e execução. A diferença local de F1 em relação à melhor da busca anterior foi 0,017240; é seleção no mesmo treino, sem confirmação independente, promoção ou demonstração de melhor tracking.

[Protocolo, resultados e hashes](../../metodologia/REFINAMENTO_CLASSICOS_V1.md) · [Resumo e valores por vídeo](../../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

A seção da busca abaixo é histórica; os parâmetros e números anteriores foram preservados.

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [watershed.py](../../../src/detection/classical/watershed.py) — `WatershedDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/watershed/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/watershed/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Histórico — resultado da busca de treino — 11/09/2026

Seis configurações foram comparadas nos mesmos 576 quadros dos 12 treinos,
sob v3. A melhor desta grade, `watershed_v1_005`, usa blur 3, razão de
distância 0,4, kernel 3, objetos claros e área 3–300. F1 macro a 10 px
**0,609765**, precisão 0,540194 e recall 0,797990; F1 a 15/20 px
0,620451/0,621864. Houve 215 previsões ignoradas a 10 px, após a proteção
dos indivíduos. Detecção média em cache: 21,674 ms/quadro, o maior custo
entre as seis configurações que lideram suas famílias nesta grade.

O F1 varia de 0,280374 no vídeo 23 a 0,907000 no 13. A média é menor
que a de T218, mas isso não ocorre em todo vídeo. A avaliação de detecção
não mede diretamente separação de regiões nem preservação de identidade;
não afirmar melhoria de tracking apenas pelo mecanismo do Watershed.

Pais para refinamento: `watershed_v1_005` e `watershed_v1_002`. A
vizinhança prospectiva varia blur ±2 ou razão de distância ±0,1, um por
vez; exige novo YAML/executor, depois validação completa. Sem promoção.
[Resumo por vídeo e sensibilidades](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).

## Ideia

Uma máscara de primeiro plano gera mapa de distância e sementes seguras. O
watershed inunda as regiões a partir dessas sementes e tenta separar objetos
encostados; cada rótulo final vira uma detecção.

## Parâmetros a estudar

Polaridade, blur, kernel, `dist_ratio` e limites de área. O `dist_ratio` controla
quão conservadoras são as sementes.

## Pontos fortes

- oferece mecanismo clássico explícito para separar células ou regiões tocantes;
- não requer labels, treino ou GPU;
- produz regiões individualizadas, úteis em imagens densas.

## Pontos fracos

- sementes ruins propagam sobre ou subsegmentação;
- distância global máxima pode ser dominada por um cluster grande;
- blur, polaridade e `dist_ratio` são sensíveis ao vídeo;
- custo é maior que componentes conexos simples.

## Adaptação e validação

Distribuir frames por densidade e por toda a duração. Analisar separadamente
clusters e casos isolados, mantendo a avaliação principal v3 dos indivíduos
0/2 e a regra de ignorados em clusters após matching. Falhas de
uma única região dividida em muitas devem aparecer em count bias e precision.
