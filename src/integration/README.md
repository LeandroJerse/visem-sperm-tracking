# Integração — acrescentar fluxo às trajetórias

[← Mapa do código](../README.md) · [Comandos de integração com fluxo](../../script/README.md#3-movimento-aparente-por-fluxo) · [Predição](../prediction/README.md)

Este módulo conecta dois resultados existentes: `tracks.csv`, produzido pelo
[tracking](../tracking/README.md), e `cache_index.csv`, produzido pelo
[fluxo óptico](../flow/README.md). A saída é `tracks_with_flow.csv`.
Ele não detecta células, não cria IDs e não estima um novo campo de fluxo.

## Onde está a implementação

| Operação | Implementação Python | Configuração | Referência |
|---|---|---|---|
| Anexar fluxo por vídeo e frame | [enrich_tracks_with_flow.py](enrich_tracks_with_flow.py) | `DEFAULT_CONFIG` no mesmo arquivo; aceita YAML externo, mas não há YAML dedicado em `configs/` | [Guia de fluxo](../flow/README.md) |
| Amostrar no centro (`direct`) ou em anel (`background`) | [cache.py](../flow/cache.py) | Seção `sampling` da configuração de integração | [Contrato do fluxo](../flow/base.py) |

[enrich_tracks_with_flow.py](enrich_tracks_with_flow.py) reúne a leitura do índice,
a função reutilizável `enrich_track_rows` e o executor `main`, que registra a
configuração e os artefatos. Não existem `base.py`, `registry.py` ou `pipeline.py`
próprios neste módulo: a integração utiliza os contratos de fluxo e o suporte
comum de [experimentos](../experiments/).
[__init__.py](__init__.py) apenas exporta a função reutilizável.

## Como os frames se conectam

Uma posição no frame `t` recebe o campo do par `t → t+1`. A predição seleciona
as transições do histórico para usar somente informação disponível até o seu
instante inicial. A associação preserva vídeo, frame, chave do cache e validade.

`direct` interpola o campo no centro da célula; `background` usa amostras válidas
em um anel ao redor dela, útil quando a célula foi mascarada. Sem par de cache
ou amostra válida, `flow_valid=0` e os atributos numéricos ficam vazios.
Ausência de medida não vira vetor zero.

## Saídas e verificação

São acrescentados `flow_u`, `flow_v`, magnitude, direção em radianos, validade,
confiança e informações do par de frames. O CSV original é preservado.
A execução gera `tracks_with_flow.csv`, resumos, metadados e manifesto sob
[data/tests/flow](../../data/tests/flow/) com algoritmo `track_flow_enrichment`;
por padrão, etapas finais de teste, folds e aplicação usam
[data/results](../../data/results/). Uma cópia adicional
pode ser destinada a [data/derived/tracking/tracks](../../data/derived/tracking/tracks/).
Destinos existentes não são sobrescritos.

Os [testes de integração](../../tests/integration/test_flow_prediction_pipeline.py)
verificam essa conexão. Ter o CSV enriquecido não demonstra que o fluxo melhora
a predição: essa conclusão depende da comparação registrada na
[matriz de experimentos](../../docs/projeto/MATRIZ_EXPERIMENTOS.md).
Veja a execução no [guia oficial](../../script/README.md#3-movimento-aparente-por-fluxo).
