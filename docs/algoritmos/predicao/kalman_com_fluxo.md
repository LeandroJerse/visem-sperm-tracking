# Filtro de Kalman com fluxo

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [kalman_with_flow.py](../../../src/prediction/hybrid/kalman_with_flow.py) — `FlowAwareKalmanPredictor` · [Kalman reutilizado](../../../src/prediction/classical/kalman.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/flow_aware_kalman/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

A variante reutiliza o preditor Kalman e adiciona a compensação pelo fluxo; os dois métodos mantêm configurações separadas.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia e hipótese

`FlowAwareKalmanPredictor` aplica o modelo de velocidade constante em
coordenadas compensadas pelo movimento aparente e adiciona novamente o fluxo
no horizonte previsto.

## Pontos fortes

- Mantém filtragem online, baixa latência e covariância explícita.
- Separa de modo auditável o prior ambiental da dinâmica residual.
- Permite ablação direta com o mesmo Kalman sem fluxo.

## Pontos fracos

- Herda as hipóteses linear/gaussiana do Kalman.
- Erros persistentes do fluxo deslocam todas as previsões.
- A incerteza do fluxo não entra automaticamente na covariância do estado.

## Parâmetros e decisão

Manter ruídos de processo/medição idênticos à comparação pura e variar apenas
a fonte do fluxo em primeiro lugar. Promover somente com ganho por vídeo em
ADE/FDE que compense o custo do campo. Resultado: **pendente**.
