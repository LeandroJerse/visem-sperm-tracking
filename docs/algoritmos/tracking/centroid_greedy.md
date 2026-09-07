# Centroide guloso

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [centroid.py](../../../src/tracking/classical/centroid.py) — `CentroidGreedyTracker` |
| Configuração | [YAML de desenvolvimento](../../../configs/tracking/centroid_greedy/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#2-tracking) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/tracking/README.md) · [Área de resultados promovidos](../../../data/results/tracking/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Definição

Baseline online mínimo. Para cada frame, calcula a distância euclidiana entre
os centros das tracks existentes e das detecções. Seleciona repetidamente o par
disponível de menor distância, desde que ele esteja dentro de `max_distance`.
Não há previsão de movimento nem otimização global.

O algoritmo implementado é deliberadamente guloso. Isso permite medir
separadamente o ganho da associação Húngara e evita chamar um procedimento
aproximado de associação ótima.

## Parâmetros

| Parâmetro | Efeito |
|---|---|
| `max_distance` | gate máximo em pixels |
| `max_age` | quantidade de frames ausentes tolerada |
| `min_hits` | observações necessárias para confirmar a track |
| `class_aware` | proíbe associação entre classes diferentes |
| `emit_predictions` | emite a última caixa durante desaparecimentos |

Faixa inicial sugerida no VISEM: `max_distance` em 5, 10, 15, 20 e 30 px;
`max_age` em 0, 1, 2, 3 e 5. A faixa deve ser confirmada pela distribuição real
de deslocamentos entre frames.

## Pontos fortes

- custo e implementação mínimos;
- determinístico e fácil de auditar;
- não exige confiança calibrada, treino ou GPU;
- referência adequada para quantificar o valor dos métodos mais complexos.

## Pontos fracos

- a decisão local pode impedir uma associação global melhor;
- não antecipa movimento, portanto troca IDs em cruzamentos;
- distância fixa é frágil quando velocidade e densidade variam;
- uma célula desaparecida permanece na última posição.

## Testes obrigatórios

- persistência do ID em movimento isolado;
- desaparecimento por 0–5 frames;
- duas trajetórias em cruzamento;
- densidades diferentes e objetos muito próximos;
- sensibilidade conjunta de `max_distance` e `max_age`.

Status: implementação e testes sintéticos concluídos; avaliação VISEM pendente.
