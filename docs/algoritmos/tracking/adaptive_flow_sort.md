# Adaptive Flow-SORT — variante híbrida

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [adaptive_flow_sort.py](../../../src/tracking/hybrid/adaptive_flow_sort.py) — `AdaptiveFlowSortTracker` · [SORT reutilizado](../../../src/tracking/classical/sort.py) · [Leitura do cache de fluxo](../../../src/tracking/flow_cache.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/tracking/adaptive_flow_sort/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#2-tracking) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/tracking/README.md) · [Área de resultados promovidos](../../../data/results/tracking/README.md) |

A classe estende o SORT, mantendo a variante com fluxo separada do baseline.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Motivação

Espermatozoides apresentam deslocamento rápido, trajetórias erráticas, caixas
pequenas e alta densidade. IoU puro pode zerar entre frames. A variante híbrida
mantém o Kalman do SORT, mas acrescenta duas adaptações explícitas:

1. **prior de fluxo opcional:** desloca a previsão por uma fração do vetor
   `(u, v)` local;
2. **associação adaptativa:** combina distância normalizada e IoU, expandindo o
   gate com a velocidade prevista e limitando-o pela separação entre detecções
   em cenas densas.

Isso é uma proposta experimental separada, não uma alteração silenciosa do
baseline SORT.

## Fluxo aceito

- `None`: funciona como Adaptive SORT sem prior externo;
- par `(u, v)`: deslocamento uniforme no frame;
- função `flow(cx, cy) -> (u, v)`;
- matriz densa `H x W x 2`.

No campo denso usa-se a mediana vetorial dentro de uma janela ao redor da caixa,
mais robusta que um único pixel a vetores espúrios da célula ou de artefatos.
Valores não finitos são ignorados. O campo deve representar deslocamento por
frame nas mesmas coordenadas em pixels das caixas.

Na CLI, `--flow-cache-index <run_de_fluxo>/cache_index.csv` liga explicitamente
o cache ao tracker. O update do frame `t` usa o campo forward `t-1 → t`; o
primeiro frame após `reset()` recebe `None`, pois ainda não há estado anterior a
propagar. A leitura é lazy, um `.npz` por update, e a máscara `valid` do cache é
aplicada convertendo pixels inválidos em `NaN`. Pares ausentes degradam para
`None` e são contados no metadata, sem serem confundidos com movimento zero.

## Custo e gate

O gate inicial por track é:

`base_distance + velocity_scale * ||(vx, vy)||`.

Quando existem múltiplas detecções, ele é limitado por
`density_fraction * mediana(distância ao vizinho mais próximo)`, respeitando
`min_distance`. A associação Húngara minimiza uma soma normalizada de distância
e `1 - IoU`. Uma sobreposição mínima pode liberar um par ligeiramente fora do
gate de centro.

## Pontos fortes

- mantém candidatos mesmo quando o IoU zera por deslocamento rápido;
- aproveita o módulo de movimento aparente sem torná-lo obrigatório;
- reduz gates em cenas densas, limitando associações distantes;
- não exige treino nem rede de aparência.

## Pontos fracos e riscos

- fluxo do fundo pode não coincidir com o movimento da célula;
- um campo contaminado desloca a previsão na direção errada;
- mais hiperparâmetros elevam o risco de ajuste excessivo;
- a densidade global aproximada não representa toda ambiguidade local;
- custo maior e interpretação menos direta que SORT.

## Ablações necessárias

Executar com os mesmos dados e seeds:

1. SORT puro;
2. híbrido com `flow_weight=0` — somente custo/gate adaptativo;
3. híbrido com fluxo não mascarado;
4. híbrido com fluxo do fundo após mascarar células;
5. opcionalmente fluxo uniforme mediano versus campo local.

Promover a variante somente se o ganho em HOTA/IDF1 permanecer nos vídeos, não
apenas em frames ou tracks individuais, e se justificar o custo de computar o
fluxo.

Status: fluxo uniforme/denso, gate adaptativo e associação sintética validados;
avaliação e ablação VISEM pendentes.
