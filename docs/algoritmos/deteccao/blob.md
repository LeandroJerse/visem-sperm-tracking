# Simple Blob Detector

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [blob.py](../../../src/detection/classical/blob.py) — `BlobDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/blob/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/blob/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Busca regiões estáveis ao longo de uma sequência de limiares e filtra keypoints
por polaridade, área e, opcionalmente, circularidade e convexidade. O diâmetro
do keypoint vira uma box quadrada.

## Parâmetros a estudar

Faixa e passo de threshold, polaridade clara/escura, área, circularidade e
convexidade. Filtros geométricos devem começar desligados e entrar por ablação.

## Pontos fortes

- rápido, sem treino e diretamente ajustável ao tamanho esperado da cabeça;
- pode rejeitar componentes muito grandes/pequenos e formas incompatíveis;
- oferece centro e escala sem segmentação densa explícita.

## Pontos fracos

- muito sensível à polaridade e escala da imagem;
- formas pequenas e ruidosas tornam circularidade/convexidade instáveis;
- clusters e células encostadas tendem a virar um blob ou desaparecer;
- box quadrada aproximada pode prejudicar métricas de IoU.

## Adaptação e validação

Usar F1 por distância de centro como métrica principal evita punir apenas a
aproximação quadrada da box. Distribuir frames por toda a duração e calibrar
área em pixels na resolução original, sem redimensionamento silencioso.
