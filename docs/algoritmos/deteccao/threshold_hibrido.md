# Híbrido CLAHE + correção de fundo + threshold

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [enhanced_threshold.py](../../../src/detection/hybrid/enhanced_threshold.py) — `HybridThresholdDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/hybrid_threshold/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

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
