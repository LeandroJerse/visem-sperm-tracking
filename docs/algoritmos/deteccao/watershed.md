# Watershed por marcadores

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [watershed.py](../../../src/detection/classical/watershed.py) — `WatershedDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/watershed/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/watershed/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

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
clusters e casos isolados, mas manter a promoção principal binária. Falhas de
uma única região dividida em muitas devem aparecer em count bias e precision.
