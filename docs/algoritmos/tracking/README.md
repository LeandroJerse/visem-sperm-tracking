# Mapa do módulo de tracking

[Catálogo](../README.md) · [Código e contratos](../../../src/tracking/README.md) · [Parâmetros](../../../configs/tracking/) · [Comandos oficiais](../../../script/README.md#2-tracking) · [Ensaios](../../../data/tests/tracking/README.md) · [Resultados promovidos](../../../data/results/tracking/README.md)

Esta pasta documenta somente os rastreadores. Todos estão implementados em
[`src/tracking/`](../../../src/tracking/README.md), compartilham a API
`reset()`/`update()` e foram validados com sequências sintéticas em
[`tests/tracking/`](../../../tests/tracking/). Isso comprova propriedades
algorítmicas básicas, mas **não** constitui resultado no VISEM-Tracking.

## Ordem experimental

| Ordem | Nome estável | Tipo | Documento | Papel na comparação |
|---:|---|---|---|---|
| 1 | `centroid_greedy` | clássico | [centroid_greedy.md](centroid_greedy.md) | baseline mínimo de custo |
| 2 | `hungarian` | clássico | [hungarian.md](hungarian.md) | efeito da associação global |
| 3 | `sort` | clássico | [sort.md](sort.md) | efeito do modelo de movimento |
| 4 | `bytetrack_style` | clássico moderno | [bytetrack_style.md](bytetrack_style.md) | efeito do segundo estágio de baixa confiança |
| 5 | `adaptive_flow_sort` | híbrido proposto | [adaptive_flow_sort.md](adaptive_flow_sort.md) | fluxo + gate adaptativo para microscopia |

Os baselines não recebem melhorias escondidas. Em particular, `sort` ignora o
argumento opcional de fluxo. Toda adaptação aparece em
`adaptive_flow_sort`, preservando uma comparação interpretável.

## Arquivos e responsabilidades

| Arquivo | Conteúdo |
|---|---|
| [types.py](../../../src/tracking/types.py) | `TrackDetection` e `TrackResult`, em pixels |
| [base.py](../../../src/tracking/base.py) | contrato abstrato `Tracker` e validação da sequência de frames |
| [assignment.py](../../../src/tracking/assignment.py) | distâncias, IoU e Húngaro; SciPy opcional, fallback NumPy |
| [kalman.py](../../../src/tracking/kalman.py) | Kalman de velocidade constante para `(cx, cy, w, h)` |
| [classical/centroid.py](../../../src/tracking/classical/centroid.py) | associação gulosa por centroide |
| [classical/hungarian.py](../../../src/tracking/classical/hungarian.py) | associação global por centroide |
| [classical/sort.py](../../../src/tracking/classical/sort.py) | Kalman + Húngaro por IoU |
| [modern/bytetrack_style.py](../../../src/tracking/modern/bytetrack_style.py) | associação moderna em dois estágios por confiança |
| [hybrid/adaptive_flow_sort.py](../../../src/tracking/hybrid/adaptive_flow_sort.py) | variante híbrida com fluxo e gates adaptativos |
| [flow_cache.py](../../../src/tracking/flow_cache.py) | leitura lazy do `cache_index.csv`, com máscara inválida em NaN |
| [runner.py](../../../src/tracking/runner.py) | processamento de listas de detecções frame a frame |
| [io.py](../../../src/tracking/io.py) | CSV analítico e exportação MOTChallenge |
| [metrics.py](../../../src/tracking/metrics.py) | eventos auditáveis de ID switch e fragmentação |
| [src/evaluation/tracking.py](../../../src/evaluation/tracking.py) | fronteira para TrackEval; não inventa HOTA local |
| [factory.py](../../../src/tracking/factory.py) | registro `TRACKERS` e `create_tracker()` |

## Contrato de uso

```python
from src.tracking import TrackDetection, create_tracker

tracker = create_tracker("sort", iou_threshold=0.10, max_age=3, min_hits=2)
tracker.reset()

for frame_index, detector_output in enumerate(detections_by_frame):
    detections = [TrackDetection.from_detection(item) for item in detector_output]
    tracks = tracker.update(detections, frame_index=frame_index)
```

- Deve existir uma chamada para cada frame, inclusive `update([])` quando não
  houver detecção. Pular frames alteraria artificialmente `max_age` e gera erro.
- IDs reiniciam deterministicamente em 1 após `reset()`.
- `emit_predictions=False` evita avaliar previsões Kalman como se fossem
  detecções observadas. Ative-o apenas no experimento específico de oclusão.
- `class_aware=False` é o padrão da avaliação binária. Ative a opção somente na
  análise secundária por classe.
- CSVs não são sobrescritos por padrão.

## Avaliação

1. Primeiro usar as caixas GT como entrada, isolando associação e movimento.
2. Depois repetir com cada detector congelado, medindo o pipeline fim a fim.
3. Ajustar hiperparâmetros somente no treino/validação; liberar o teste uma vez.
4. Reportar HOTA pelo TrackEval oficial, além de IDF1/MOTA quando integrados.
5. Usar `evaluate_identity_events` para auditoria local dos eventos; seus
   contadores não são apresentados como substitutos de HOTA.

Consulte
[`docs/metodologia/METRICAS_TRACKING.md`](../../metodologia/METRICAS_TRACKING.md)
para definições, eventos de identidade e formato de saída.

## Executor reproduzível

O executor oficial recebe o CSV longo produzido pela detecção. Os
[comandos de tracking](../../../script/README.md#2-tracking) são a referência
de execução; o [guia do módulo](../../../src/tracking/README.md) explica as entradas.

`--frame-start/--frame-end` são inclusivos. O executor chama o tracker também
nos frames sem linhas, com uma lista vazia, preservando corretamente `max_age`.
Linhas `manual` do mesmo CSV ficam separadas para auditoria de identidade. O
arquivo irmão `frame_metrics.csv` é detectado automaticamente, ou pode ser
informado com `--frame-metrics-csv`. Ele recupera o intervalo completo e inclui
frames anotados sem nenhum objeto no GT. Sem esse companion, o executor mantém
o fallback conservador por linhas manuais e registra a limitação no metadata.

O híbrido recebe o cache de uma run de fluxo explicitamente, conforme o
[guia de entradas do tracking](../../../src/tracking/README.md).

O campo não é pré-carregado: no update do frame `t`, lê-se somente o `.npz` do
par `t-1 → t`. Pixels marcados como inválidos no cache viram `NaN` e são
ignorados pela mediana local; eles nunca são convertidos em falso fluxo zero.
O hash do índice, pares carregados/ausentes e a política de validade ficam no
manifest/metadata. A flag é recusada para os baselines puros.

Cada chamada cria uma nova pasta de run com `tracks.csv`, `tracks_mot.txt`,
eventos/avaliação de identidade, `summary.json`, `summary.csv`, `metadata.json`
e `manifest.json`. O arquivo MOT é a entrada para TrackEval; o CLI não produz um
valor HOTA interno.
