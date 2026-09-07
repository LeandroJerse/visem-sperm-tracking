# Predição — estimar posições futuras

[← Mapa do código](../README.md) · [Comandos de predição](../../script/README.md#4-predição) · [Estado dos experimentos](../../docs/projeto/MATRIZ_EXPERIMENTOS.md)

Recebe o histórico de posições de uma trajetória e prevê posições em horizontes
futuros. As variantes com fluxo acrescentam movimento aparente ao histórico,
permitindo comparar cada família com e sem esse atributo.

## Onde está cada algoritmo

| Método | Implementação Python | Configuração de busca | Ficha científica |
|---|---|---|---|
| Persistência | [classical/persistence.py](classical/persistence.py) | [YAML](../../configs/prediction/persistence/search.yaml) | [Ficha](../../docs/algoritmos/predicao/persistencia.md) |
| Velocidade constante | [classical/constant_velocity.py](classical/constant_velocity.py) | [YAML](../../configs/prediction/constant_velocity/search.yaml) | [Ficha](../../docs/algoritmos/predicao/velocidade_constante.md) |
| Velocidade constante com fluxo | [hybrid/constant_velocity_with_flow.py](hybrid/constant_velocity_with_flow.py) | [YAML](../../configs/prediction/flow_aware_constant_velocity/search.yaml) | [Ficha](../../docs/algoritmos/predicao/velocidade_constante_com_fluxo.md) |
| Kalman | [classical/kalman.py](classical/kalman.py) | [YAML](../../configs/prediction/kalman/search.yaml) | [Ficha](../../docs/algoritmos/predicao/kalman.md) |
| Kalman com fluxo | [hybrid/kalman_with_flow.py](hybrid/kalman_with_flow.py) | [YAML](../../configs/prediction/flow_aware_kalman/search.yaml) | [Ficha](../../docs/algoritmos/predicao/kalman_com_fluxo.md) |
| Filtro de partículas | [classical/particle_filter.py](classical/particle_filter.py) | [YAML](../../configs/prediction/particle_filter/search.yaml) | [Ficha](../../docs/algoritmos/predicao/filtro_particulas.md) |
| Partículas com fluxo | [hybrid/particle_filter_with_flow.py](hybrid/particle_filter_with_flow.py) | [YAML](../../configs/prediction/flow_aware_particle_filter/search.yaml) | [Ficha](../../docs/algoritmos/predicao/particulas_com_fluxo.md) |
| LSTM | [learned/lstm.py](learned/lstm.py) | [YAML](../../configs/prediction/lstm/search.yaml) | [Ficha](../../docs/algoritmos/predicao/lstm.md) |
| LSTM com fluxo | [hybrid/lstm_with_flow.py](hybrid/lstm_with_flow.py) | [YAML](../../configs/prediction/flow_aware_lstm/search.yaml) | [Ficha](../../docs/algoritmos/predicao/lstm_com_fluxo.md) |

Persistência é curta porque repete a última posição. A LSTM com fluxo é curta
porque herda a arquitetura, o treino e a predição de [learned/lstm.py](learned/lstm.py),
habilitando a entrada de fluxo. Esse arquivo contém `fit`, `predict`, `save`
e `load`; o treino exige PyTorch e vídeos distintos dos usados na avaliação.
Kalman e partículas com fluxo também reutilizam seus filtros clássicos.

## Arquivos compartilhados

| Arquivo | O que procurar nele |
|---|---|
| [base.py](base.py) | Contrato `predict`, validação de posições/horizontes e convenções de fluxo. Métodos abstratos definem a interface. |
| [registry.py](registry.py), [__init__.py](__init__.py) | Nomes disponíveis e importações públicas. |
| [windows.py](windows.py) | Construção de janelas contínuas, separadas por vídeo, ID e split. |
| [pipeline.py](pipeline.py) | Leitura das trajetórias, seleção de janelas, treino explícito ou checkpoint, avaliação e registro da execução. |
| [metrics.py](metrics.py) | ADE, FDE e erros por horizonte. |
| [Integração com fluxo](../integration/README.md) | Produção de `tracks_with_flow.csv` a partir de trajetórias e cache. |

## Janelas, resultados e verificação

A unidade de entrada é uma **janela de trajetória**. O CSV científico precisa
de `video_id`, `frame_index`, `annotated`, `track_id`, `cx` e `cy`; as variantes
com fluxo exigem atributos válidos em cada transição. As janelas não cruzam
lacunas, vídeos, IDs ou splits. Ausência de anotação não vira negativo.
Na aplicação sem GT, a política distinta fica registrada no manifesto.

A LSTM com fluxo usa atributos históricos. Nos híbridos clássicos, o modo
operacional mantém o último fluxo observado para os passos futuros. Fluxo
futuro observado é uma condição retrospectiva e não pode ser apresentado como
informação disponível no instante da previsão.

As execuções de desenvolvimento ficam em [data/tests/prediction](../../data/tests/prediction/),
por algoritmo, configuração, etapa e execução, com `predictions.csv`,
`window_metrics.csv`, resumos e manifesto. Por padrão, etapas finais de teste,
folds e aplicação usam
[data/results](../../data/results/).

Os [testes dos métodos](../../tests/integration/test_flow_prediction.py) e do
[executor](../../tests/integration/test_flow_prediction_pipeline.py) são separados
das avaliações científicas. Criar uma LSTM sem carregar PyTorch não verifica seu
treino ou sua inferência; a [matriz](../../docs/projeto/MATRIZ_EXPERIMENTOS.md)
registra a etapa experimental efetivamente alcançada.
Os [comandos oficiais](../../script/README.md#4-predição) ficam em `script/README.md`.
