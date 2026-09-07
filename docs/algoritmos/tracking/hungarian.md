# Associação Húngara

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [hungarian.py](../../../src/tracking/classical/hungarian.py) — `HungarianTracker` · [Estado compartilhado](../../../src/tracking/classical/centroid.py) · [Matching Húngaro](../../../src/tracking/assignment.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/tracking/hungarian/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#2-tracking) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/tracking/README.md) · [Área de resultados promovidos](../../../data/results/tracking/README.md) |

Esta classe curta altera a associação e reutiliza o estado e o ciclo de atualização da classe `_DistanceTracker` em `centroid.py`.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Definição

Usa a mesma distância de centroide e o mesmo ciclo de vida do baseline guloso,
mas resolve uma atribuição um-para-um global que minimiza a soma dos custos. Os
pares acima de `max_distance` ou incompatíveis por classe são inválidos.

SciPy é usado quando estiver disponível. O módulo inclui um solver Húngaro
retangular em NumPy como fallback, mantendo o experimento executável sem uma
dependência adicional e sem substituir o método por uma heurística gulosa.

## Parâmetros

São os mesmos do centroide guloso: `max_distance`, `max_age`, `min_hits`,
`class_aware`, `emit_predictions` e `emit_tentative`. Isso permite comparar os
dois métodos alterando somente a estratégia de associação.

## Pontos fortes

- associação global ótima para a matriz de custo definida;
- determinístico;
- reduz erros causados pela ordem de processamento das tracks;
- custo ainda pequeno para a quantidade de células por frame do conjunto.

## Pontos fracos

- ótimo apenas para a distância instantânea, não para a identidade temporal;
- não possui memória de velocidade;
- gate fixo continua sensível à velocidade e densidade;
- pode trocar IDs em cruzamentos simétricos ou oclusões.

## Comparação controlada

Usar exatamente os mesmos frames e hiperparâmetros do centroide guloso. A
diferença de ID switches/HOTA entre ambos estima o benefício exclusivo da
otimização global. Não adicionar Kalman nesta etapa.

Status: implementação, fallback NumPy e caso sintético de atribuição ambígua
concluídos; avaliação VISEM pendente.
