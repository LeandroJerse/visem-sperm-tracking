# Persistência

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [persistence.py](../../../src/prediction/classical/persistence.py) — `PersistencePredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/persistence/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

A primeira bateria fixa está em `data/tests/prediction/baselines/`, com
subpastas por vídeo e método. Os [resultados conferidos](../../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)
ligam os artefatos e a figura; as entradas genéricas acima continuam disponíveis.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria

Repete a última posição em todos os horizontes. É uma referência para medir
o valor da extrapolação; outro método não necessariamente a supera quando a
velocidade é ruidosa ou o movimento muda. Não usa fluxo ou treinamento.

## Pontos fortes

- Determinístico, sem parâmetros e praticamente sem custo.
- Detecta se métricas favorecem artificialmente movimentos curtos.
- Excelente teste de alinhamento de janelas e horizontes.

## Pontos fracos e falhas esperadas

- Erro cresce rapidamente para células móveis.
- Não representa corrente, direção nem curvatura.

## Custo e decisão

Custo baixo, sem treino; deve constar das comparações como referência. O
[protocolo v1](../../metodologia/BASELINES_PREDICAO_V1.md) registra sua avaliação
no treino, usando `predict_batch` float64, janelas comuns e ADE denso.
Não será escolhido ou descartado para a pipeline final por esta bateria.
Resultado v1 conferido: **ADE₁₀ 3,890964 px; FDE₁₀ 6,619751 px**,
com peso igual por ID original dentro do vídeo e por vídeo. São 343.776 janelas
dos 12 vídeos de treino, sob `5289c93`; não é avaliação com tracking ou fluxo.
A bateria não seleciona hiperparâmetros nem promove o método para uso final.
