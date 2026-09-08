# Velocidade constante

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [constant_velocity.py](../../../src/prediction/classical/constant_velocity.py) — `ConstantVelocityPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/constant_velocity/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e versões

O baseline puro calcula deslocamentos recentes e usa mediana, média ou o último
vetor para extrapolar. A mediana reduz o efeito de jitter do tracking. A versão
`flow_aware` subtrai de cada deslocamento o fluxo aparente amostrado na célula,
estima o deslocamento residual na imagem e soma o fluxo previsto a cada passo.
Essa decomposição não identifica velocidade física do fluido ou de nado.

## Parâmetros a testar

- janela: 1, 3, 5, 10 e todo o histórico;
- estimador: último, média e mediana;
- com fluxo: vetor futuro conhecido no cenário controlado versus último vetor.

## Pontos fortes

- Muito rápido, interpretável e sem treino.
- A mediana é robusta a erros isolados de posição.
- A versão híbrida testa diretamente o valor informativo do fluxo.

## Pontos fracos e falhas esperadas

- Não modela curvas, aceleração ou mudança de direção.
- Janela longa atrasa mudanças; curta amplifica jitter.
- Fluxo ruidoso pode piorar o híbrido; manter último fluxo constante é uma
  hipótese forte para horizontes longos.

## Custo e decisão

Custo baixo. Manter baseline puro e híbrido como linhas separadas. O
[protocolo v1](../../metodologia/BASELINES_PREDICAO_V1.md) fixa mediana das últimas
cinco diferenças antes de avaliar as janelas GT do treino; não é busca de janela
ou seleção de estimador. A API em lote usa float64 e recebe somente histórico.
Resultado da execução v1: **pendente**; nenhum híbrido é avaliado nesta bateria.
