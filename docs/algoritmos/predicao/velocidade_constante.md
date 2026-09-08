# Velocidade constante

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [constant_velocity.py](../../../src/prediction/classical/constant_velocity.py) — `ConstantVelocityPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/constant_velocity/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

A primeira bateria fixa está em `data/tests/prediction/baselines/`, com
subpastas por vídeo e método. Os [resultados conferidos](../../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)
ligam os artefatos e a figura; as entradas genéricas acima continuam disponíveis.

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
Resultado v1 conferido: **ADE₁₀ 3,137020 px; FDE₁₀ 5,774373 px**,
com peso igual por ID original dentro do vídeo e por vídeo. São 343.776 janelas
dos 12 vídeos de treino, sob `5289c93`; não é avaliação com tracking ou fluxo.
A bateria não seleciona hiperparâmetros nem promove o método para uso final.
