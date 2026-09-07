# Threshold fixo + morfologia

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [T200 em desenvolvimento](../../../configs/detection/threshold/t200_o1_c2.yaml) · [T190 em desenvolvimento](../../../configs/detection/threshold/t190_o1_c1.yaml) · [T200 congelada](../../../configs/frozen/detection/threshold/t200_o1_c2.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#threshold-etapa-atual) · [Inspeção de um frame](../../../script/detection/test/threshold/README.md) |
| Ensaios e resultados | [Ensaios do método](../../../data/tests/detection/threshold) · [Seleção congelada](../../../data/results/detection/threshold/t200_o1_c2__cfg3276cf65/README.md) |

A classe é compartilhada com os outros modos de threshold; o YAML e o identificador científico mantêm os experimentos separados.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Um limiar global definido antes da execução separa primeiro plano e fundo. Uma
abertura remove componentes pequenos, um fechamento reconecta fragmentos e
componentes conexos produzem uma box e um centro por região.

## Parâmetros a estudar

`threshold_value` (190–205 na retomada), polaridade, blur, kernel, iterações de
abertura/fechamento e limites de área. Os pilotos `T200/o1/c2` e `T190/o1/c1`
foram mantidos obrigatoriamente na retomada.

## Pontos fortes

- custo muito baixo, comportamento determinístico e fácil de explicar;
- não requer treino, labels de classe, GPU nem sequência temporal;
- bom baseline para quantificar quanto cada etapa mais complexa realmente ganha.

## Pontos fracos

- um único limiar não acompanha mudanças de contraste ou iluminação;
- morfologia pode unir células próximas ou apagar cabeças pequenas;
- detritos com intensidade e área semelhantes viram falsos positivos;
- cada componente recebe score 1, limitando trackers baseados em confiança.

## Adaptação e validação

Filtragem por área e kernel elíptico são adequações ao tamanho/formato das
cabeças. Validar separadamente por vídeo e inspecionar densidade, detritos e
clusters. O baseline deve continuar puro; CLAHE/top-hat pertencem ao híbrido.

## Decisão atual

Nos vídeos completos de validação `14, 19, 36, 52`, T200/o1/c2 obteve o melhor
F1 macro por vídeo (`0,6863`) e menor erro de contagem; T190/o1/c1 preservou
recall maior. A configuração T200 está congelada em
`configs/frozen/detection/threshold/t200_o1_c2.yaml` e sua seleção auditável em
`data/results/detection/threshold/t200_o1_c2__cfg3276cf65/selection/`.

O teste isolado `24, 38, 47, 54` ainda não foi executado. Logo, este resultado
é uma decisão de validação, não a estimativa final fora da amostra.
