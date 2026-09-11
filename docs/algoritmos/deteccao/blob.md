# Simple Blob Detector

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [blob.py](../../../src/detection/classical/blob.py) — `BlobDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/blob/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/blob/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Resultado de treino conferido — 11/09/2026

Seis configurações foram avaliadas nos mesmos 576 quadros dos 12 treinos,
sob o contrato v3. A melhor desta grade foi `blob_v1_003`: objetos claros,
varredura com início 180, limite configurado 255 e passo 10, área 3–300, circularidade e
convexidade desativadas. F1 macro a 10 px **0,791005**, precisão 0,760180,
recall 0,848556; F1 a 15/20 px 0,798632/0,799925. Houve 79 previsões
ignoradas a 10 px, após a proteção de indivíduos. Detecção média em cache:
1,285 ms/quadro; isso não mede a pipeline completa.

O F1 supera T218 em 7/12 vídeos e na média desta amostra, por cerca de
1,54 ponto percentual. Varia de 0,619516 no vídeo 35 a 0,924324 no 22.
É um candidato promissor para refinamento, sem evidência de superioridade
geral ou promoção. A referência T218 já recebeu ajuste mais extenso; a
grade Blob limitada não certifica o ótimo do algoritmo. A área interna do
Blob é geométrica de contorno, diferente da contagem de pixels dos
componentes conexos, apesar de usar os mesmos limites numéricos.

Pais registrados para refinamento: `blob_v1_003` e `blob_v1_002`.
A vizinhança prospectiva varia apenas o início da varredura em ±20,
preservando os demais parâmetros; precisa de novo YAML/executor antes da
execução e de validação completa depois. Evidência em
[resumo e valores por vídeo](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).

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
