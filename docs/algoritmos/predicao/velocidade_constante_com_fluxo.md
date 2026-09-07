# Velocidade constante com fluxo

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [constant_velocity_with_flow.py](../../../src/prediction/hybrid/constant_velocity_with_flow.py) — `FlowAwareConstantVelocityPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/flow_aware_constant_velocity/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia e hipótese

`FlowAwareConstantVelocityPredictor` subtrai o fluxo aparente acumulado dos
deslocamentos observados, estima por mediana a velocidade residual da célula e
recompõe o fluxo ao prever. Isso testa a decomposição aproximada “movimento
observado = movimento intrínseco + ambiente”.

## Pontos fortes

- Continua barato, determinístico e interpretável.
- Produz a ablação clássica mais simples da hipótese do TCC.
- A mediana reduz a influência de uma transição aberrante.

## Pontos fracos

- A decomposição pode não representar a interação física real.
- Fluxo contaminado vira velocidade residual falsa.
- No cenário operacional, repetir o último fluxo não prevê mudanças futuras.

## Parâmetros e decisão

Testar janela de velocidade, fonte/máscara do fluxo e último fluxo versus
oráculo controlado. Comparar pareado ao baseline puro por ADE/FDE e custo.
Resultado: **pendente**.
