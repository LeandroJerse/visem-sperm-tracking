# Filtro de Kalman

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [kalman.py](../../../src/prediction/classical/kalman.py) — `KalmanPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/kalman/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e versões

O estado é `[x, y, vx, vy]`, com movimento de velocidade constante, ruído de
aceleração e observações de posição. A implementação NumPy usa atualização de
Joseph para preservar uma covariância numericamente estável. A versão
`flow_aware` filtra posições em coordenadas compensadas pelo fluxo e recompõe o
movimento ambiental na previsão.

## Parâmetros a testar

- variância de processo: 0,01, 0,1, 0,25, 1 e 4;
- variância de medição conforme o erro do detector/tracker: 0,25, 1, 4 e 9;
- versões pura e `flow_aware` com os mesmos parâmetros.

## Pontos fortes

- Online, rápido, interpretável e com incerteza explícita.
- Suaviza jitter de posição e tolera ruído gaussiano.
- Não depende de `filterpy`, facilitando reprodutibilidade.

## Pontos fracos e falhas esperadas

- Modelo linear não representa bem nado errático ou curvas fechadas.
- Covariância depende da calibração das variâncias.
- Outliers severos não são gaussianos e podem deslocar o estado.
- Fluxo incorreto contamina diretamente a versão híbrida.

## Custo e decisão

CPU e memória constantes por trajetória, sem treino. É candidato natural ao
pipeline eficiente. Promover por ADE/FDE, estabilidade e latência. Resultado:
**pendente**.
