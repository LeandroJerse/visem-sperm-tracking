# Estatística por vídeo e fronteira de Pareto

Este documento define como comparar os algoritmos depois que cada configuração
for congelada. A unidade independente é sempre o **vídeo**. Frames, detecções,
trajetórias, folds e seeds não podem ser tratados como réplicas independentes.

As implementações estão em:

- `src/evaluation/statistics.py`: agregação de seeds, pareamento, Friedman,
  Wilcoxon, Holm, diferenças e bootstrap;
- `src/evaluation/pareto.py`: dominância e fronteira de Pareto com objetivos
  explícitos de maximização/minimização.

## Formato de entrada

Cada observação deve identificar diretamente o vídeo, método, valor e seed:

```python
from src.evaluation.statistics import VideoMetric

rows = [
    VideoMetric(video_id="11", method="sort", value=0.61, seed=42),
    VideoMetric(video_id="11", method="sort", value=0.63, seed=123),
    VideoMetric(video_id="11", method="hungarian", value=0.54, seed=42),
]
```

Mappings com as chaves `video_id`, `method`, `value` e `seed` também são
aceitos. `value_key` permite usar diretamente outra coluna, como `hota` ou
`f1`. Não existe API que receba apenas listas anônimas: o ID é obrigatório para
impedir pareamento acidental pela ordem das linhas.

Para a confirmação 5-fold, cada vídeo recebe sua previsão fora da amostra e
continua aparecendo uma única vez por método/seed. O número do fold não vira uma
unidade estatística.

## Agregação de seeds

```python
from src.evaluation.statistics import aggregate_seeds_by_video

aggregated = aggregate_seeds_by_video(rows, reducer="mean", nan_policy="omit")
```

Primeiro é calculada a média — ou mediana, se declarada — das seeds dentro de
cada par `video_id/method`. Todas as seeds têm o mesmo peso. Só então métodos
são pareados entre vídeos.

- uma chave `video/método/seed` duplicada gera erro, pois sua média daria peso
  extra àquela seed;
- `NaN` e infinito são rejeitados com `nan_policy="raise"`;
- com `nan_policy="omit"`, cada observação removida e cada grupo que ficou sem
  valor são armazenados em `dropped_nonfinite` e `dropped_groups`;
- seeds ausentes não são preenchidas nem imputadas.

Para o relatório final, registrar quantas seeds válidas contribuíram para cada
vídeo/método e investigar qualquer grupo incompleto.

## Pareamento e valores ausentes

Todos os testes usam pares formados pelo mesmo `video_id`. O padrão
`unmatched_policy="drop"` utiliza casos completos e devolve os IDs removidos em
`pairing.excluded_videos`, junto aos métodos ausentes. Para auditorias e para a
análise final congelada, recomenda-se repetir com `unmatched_policy="raise"`:
qualquer desalinhamento então interrompe a análise.

Essa remoção é por vídeo inteiro no conjunto de métodos solicitado. No pós-hoc
com vários métodos, todos os pares usam o mesmo conjunto de vídeos completos;
não se misturam tamanhos amostrais diferentes na mesma família de testes.

Ausências não devem ser substituídas por zero. Um algoritmo que falhou ao
processar um vídeo precisa ter a falha explicada e corrigida ou ser apresentado
como dado ausente, nunca como desempenho nulo inventado.

## Teste omnibus e comparações pareadas

### Três ou mais métodos

```python
from src.evaluation.statistics import friedman_test, pairwise_wilcoxon_holm

omnibus = friedman_test(rows, methods=["hungarian", "sort", "bytetrack_style"])
posthoc = pairwise_wilcoxon_holm(rows, alpha=0.05)
```

`friedman_test` chama `scipy.stats.friedmanchisquare` e exige pelo menos três
métodos e dois vídeos completos. O teste responde se existe diferença entre os
métodos, mas não identifica quais pares diferem. O pós-hoc só deve ser
interpretado no contexto do protocolo previamente definido, preferencialmente
após um omnibus significativo.

Se todos os métodos forem exatamente iguais em todos os blocos, algumas versões
do SciPy retornam valores não finitos. O resultado mantém esses valores e marca
`status="degenerate_all_methods_equal"`; não fabrica significância.

### Dois métodos ou pós-hoc

```python
from src.evaluation.statistics import wilcoxon_paired

result = wilcoxon_paired(rows, "sort", "hungarian", alternative="two-sided")
```

`wilcoxon_paired` chama `scipy.stats.wilcoxon`. O padrão bilateral testa
diferença em qualquer direção. Hipóteses unilaterais (`greater` ou `less`) só
devem ser usadas se registradas antes de observar os resultados. Quando todas
as diferenças são exatamente zero, o caso degenerado é retornado com p=1 e
status próprio.

`pairwise_wilcoxon_holm` calcula todos os pares e aplica a correção step-down de
Holm para controlar o erro familiar. São reportados p bruto, p corrigido e a
decisão para `alpha`. Não selecionar apenas os pares favoráveis depois do teste.

## Diferença pareada e IC95

```python
from src.evaluation.statistics import paired_difference, paired_bootstrap_ci

difference = paired_difference(rows, "sort", "hungarian")
interval = paired_bootstrap_ci(
    rows,
    "sort",
    "hungarian",
    statistic="mean",
    confidence=0.95,
    n_resamples=10_000,
    seed=42,
)
```

A convenção é sempre `método A - método B`:

- diferença positiva favorece A em métricas maximizadas, como F1 e HOTA;
- diferença negativa favorece A em métricas minimizadas, como ADE, FDE e
  latência.

São fornecidas média e mediana das diferenças. O IC percentil reamostra os
**vetores pareados por vídeo**, com reposição; todas as informações daquele
vídeo permanecem juntas. Antes do bootstrap, as seeds já foram agregadas.
`seed` é a semente do gerador de reamostragem, não uma seed de treinamento, e
deve constar no relatório para reprodução.

O intervalo descreve a incerteza do efeito observado. P-valor não mede tamanho
de efeito, e IC não substitui a apresentação dos valores individuais por vídeo.

## Fronteira de Pareto

Não será criado um placar ponderado. Pesos arbitrários esconderiam trocas entre
qualidade, custo e esforço. Cada direção é declarada diretamente:

```python
from src.evaluation.pareto import pareto_frontier

front = pareto_frontier(
    records,
    {
        "hota": "max",
        "latency_p95_ms": "min",
        "memory_mb": "min",
        "implementation_hours": "min",
    },
    id_key="method",
)
```

Um método domina outro somente quando é pelo menos tão bom em todos os
objetivos e estritamente melhor em pelo menos um. Métodos com vetores idênticos
permanecem empatados na fronteira. O resultado contém:

- `frontier`: métodos não dominados;
- `dominated`: método dominado e todos os seus dominadores;
- `excluded_nonfinite`: candidatos removidos quando `nan_policy="drop"`.

O padrão é rejeitar `NaN`/infinito. Removê-los só é aceitável se a exclusão e o
motivo forem reportados. Objetivos qualitativos precisam ser operacionalizados
antes — por exemplo, horas registradas, número de dependências ou necessidade
de GPU — e não convertidos retrospectivamente em pesos para favorecer um
método.

## Sequência de análise final

1. Congelar métrica, direção, métodos e política de ausências.
2. Produzir um valor por vídeo/método/seed.
3. Agregar seeds dentro de cada vídeo.
4. Auditar `dropped_*` e IDs não pareados; na análise oficial, preferir erro.
5. Executar Friedman quando houver três ou mais métodos.
6. Executar Wilcoxon pareado e Holm para a família de pares planejada.
7. Reportar valores por vídeo, diferença A−B e IC95 agrupado.
8. Construir fronteiras de Pareto separadas para detecção, tracking e predição.
9. Interpretar qualidade, custo e complexidade sem placar único.
