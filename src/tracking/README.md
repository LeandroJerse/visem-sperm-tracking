# Tracking — manter a identidade entre frames

[← Mapa do código](../README.md) · [Comandos de tracking](../../script/README.md#2-tracking) · [Estado dos experimentos](../../docs/projeto/MATRIZ_EXPERIMENTOS.md)

Recebe as detecções de cada frame e atribui IDs às células ao longo do vídeo.
Para encontrar um algoritmo, abra o Python na tabela abaixo; os pequenos
arquivos em `script/` apenas iniciam o executor compartilhado.

## Onde está cada algoritmo

| Método | Implementação Python | Configuração de busca | Ficha científica |
|---|---|---|---|
| Centroide guloso | [classical/centroid.py](classical/centroid.py) | [YAML](../../configs/tracking/centroid_greedy/search.yaml) | [Ficha](../../docs/algoritmos/tracking/centroid_greedy.md) |
| Húngaro | [classical/hungarian.py](classical/hungarian.py) | [YAML](../../configs/tracking/hungarian/search.yaml) | [Ficha](../../docs/algoritmos/tracking/hungarian.md) |
| SORT | [classical/sort.py](classical/sort.py) | [YAML](../../configs/tracking/sort/search.yaml) | [Ficha](../../docs/algoritmos/tracking/sort.md) |
| ByteTrack-style | [modern/bytetrack_style.py](modern/bytetrack_style.py) | [YAML](../../configs/tracking/bytetrack_style/search.yaml) | [Ficha](../../docs/algoritmos/tracking/bytetrack_style.md) |
| Adaptive Flow-SORT | [hybrid/adaptive_flow_sort.py](hybrid/adaptive_flow_sort.py) | [YAML](../../configs/tracking/adaptive_flow_sort/search.yaml) | [Ficha](../../docs/algoritmos/tracking/adaptive_flow_sort.md) |

O Húngaro é curto porque reutiliza o ciclo de vida das trajetórias em
[centroid.py](classical/centroid.py) e a associação em [assignment.py](assignment.py).
ByteTrack-style reutiliza SORT e implementa a associação em dois estágios;
ele não reproduz integralmente o ByteTrack oficial. O filtro de caixas do SORT
usa centro, largura e altura, conforme [kalman.py](kalman.py).

## Arquivos compartilhados

| Arquivo | O que procurar nele |
|---|---|
| [base.py](base.py), [types.py](types.py) | Contrato `update`, tipos de detecção e trajetória, reinício por vídeo. Métodos abstratos definem o contrato a implementar. |
| [factory.py](factory.py), [__init__.py](__init__.py) | Registro dos nomes disponíveis e importações públicas; não contêm o corpo dos algoritmos. |
| [runner.py](runner.py), [pipeline.py](pipeline.py) | Avanço frame a frame, leitura de entradas, configuração e registro da execução. |
| [assignment.py](assignment.py), [_state.py](_state.py), [kalman.py](kalman.py) | Matching, estado das trajetórias e filtro de movimento reutilizados pelos métodos. |
| [flow.py](flow.py), [flow_cache.py](flow_cache.py) | Amostragem e leitura do fluxo `t-1 → t` para o híbrido. |
| [io.py](io.py), [metrics.py](metrics.py) | Exportação de trajetórias e eventos locais de identidade. |
| [Avaliação oficial](../evaluation/tracking.py) | Integração com TrackEval para HOTA, IDF1 e MOTA. |

## Frames, resultados e verificação

Cada vídeo reinicia o rastreador; `update` recebe todos os frames consecutivos,
inclusive os vazios. O executor usa o universo de frames de `frame_metrics.csv`
para distinguir vazio anotado de lacuna. Entradas `manual` permitem avaliar a
associação com caixas anotadas; `detection` avalia a sequência com detecções
estimadas. A CLI aceita cache de fluxo somente no Adaptive Flow-SORT.

As execuções de desenvolvimento ficam em [data/tests/tracking](../../data/tests/tracking/),
organizadas por algoritmo, configuração, etapa e execução. Geram `tracks.csv`,
`tracks_mot.txt`, `identity_events.csv`, resumos e manifesto. Etapas congeladas
de teste, folds e aplicação usam [data/results](../../data/results/).

[Testes automatizados](../../tests/tracking/) verificam o código. Ter uma
implementação ou um teste não significa ter concluído a avaliação científica:
as evidências e promoções pertencem à [matriz de experimentos](../../docs/projeto/MATRIZ_EXPERIMENTOS.md).
Para executar, consulte os [comandos oficiais](../../script/README.md#2-tracking).
