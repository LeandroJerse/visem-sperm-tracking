# Variantes híbridas com fluxo

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementações | [Velocidade](../../../src/prediction/hybrid/constant_velocity_with_flow.py) · [Kalman](../../../src/prediction/hybrid/kalman_with_flow.py) · [Partículas](../../../src/prediction/hybrid/particle_filter_with_flow.py) · [LSTM](../../../src/prediction/hybrid/lstm_with_flow.py) |
| Configurações | [Velocidade](../../../configs/prediction/flow_aware_constant_velocity/search.yaml) · [Kalman](../../../configs/prediction/flow_aware_kalman/search.yaml) · [Partículas](../../../configs/prediction/flow_aware_particle_filter/search.yaml) · [LSTM](../../../configs/prediction/flow_aware_lstm/search.yaml) |
| Execução | [Comandos oficiais de predição](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios de predição](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Esta é uma ficha de protocolo comum, não um quinto algoritmo. As quatro variantes têm implementação e configuração próprias.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

Este arquivo registra o protocolo comum. Cada método tem uma ficha própria:

- [velocidade constante com fluxo](velocidade_constante_com_fluxo.md);
- [Kalman com fluxo](kalman_com_fluxo.md);
- [partículas com fluxo](particulas_com_fluxo.md);
- [LSTM com fluxo](lstm_com_fluxo.md).

## Hipótese

O deslocamento observado é tratado como soma aproximada de movimento intrínseco
da célula e movimento aparente ambiental. Esta decomposição é uma hipótese de
modelagem, não uma identidade física garantida.

## Híbridos implementados

- `flow_aware_constant_velocity`: residual robusto + fluxo acumulado;
- `flow_aware_kalman`: Kalman em coordenadas compensadas + fluxo;
- `flow_aware_particle_filter`: partículas em coordenadas compensadas + fluxo;
- `flow_aware_lstm`: LSTM recebe fluxo como atributo auxiliar, sem decomposição
  rígida, permitindo que a rede aprenda quanto utilizá-lo.

## Ablações obrigatórias

1. Preditor puro.
2. Mesmo preditor com fluxo ground truth sintético, como verificação.
3. Mesmo preditor com cada fluxo estimado congelado.
4. Fluxo verdadeiro futuro apenas em análise controlada.
5. Último fluxo observado no cenário operacional.
6. Fluxo mascarado versus não mascarado.

## Riscos

- Subtrair fluxo contaminado cria velocidade intrínseca falsa.
- O campo do fundo na posição da célula precisa ser interpolado de vizinhos
  válidos quando a célula estiver mascarada; não usar silenciosamente zero.
- Fornecer fluxo futuro real ao modelo em teste seria vazamento se esse fluxo
  não estiver disponível no momento da previsão.
- Melhor desempenho com fluxo não prova causalidade física.

## Decisão

Comparar ADE/FDE pareados por vídeo e reportar custo adicional de obter o fluxo.
O híbrido é promovido somente se o ganho fora da amostra sobreviver às sementes
e justificar esse custo. Resultado: **pendente**.
