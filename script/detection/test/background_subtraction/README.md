# Triagem temporal — MOG2 e KNN

MOG2 e KNN não devem ser avaliados em frames isolados. Este executor seleciona
clipes distribuídos do início ao fim de cada vídeo de **treino**, reinicia o
modelo antes de cada clipe, aquece por no mínimo 100 frames e só então calcula
as métricas.

## Contrato científico

- unidade de triagem: clipe temporal, nunca frame isolado;
- distribuição: janelas determinísticas e espaçadas por toda a duração;
- estado: `reset()` antes de cada clipe e, portanto, também entre vídeos;
- aquecimento: `>=100` frames por clipe;
- transiente: nenhum frame de aquecimento entra em `detections.csv`,
  `frame_metrics.csv`, F1 ou latência;
- métrica primária: `f1_individuals_center_10px`, por matching Húngaro
  um-para-um com GT individual das classes 0 e 2;
- política ativa: `individuals_ignore_clusters`, na versão
  `center_distance_v3_individuals_ignore_clusters_10px`;
- sensibilidades: 15 e 20 px, com matching e previsões ignoradas recalculados;
- agregação da seleção: primeiro dentro do vídeo e depois média entre vídeos;
- proteção: este script aceita apenas IDs do treino. Promoção em validação deve
  usar os vídeos completos no executor geral, não estes clipes.

A notação mostrada no `--dry-run` é
`[início_aquecimento:início_avaliação|fim_avaliação)`. O fim é exclusivo.

A política de classes foi aprovada em 07/09/2026 e a continuidade autônoma
está autorizada. O marco técnico é a implementação do contrato e seu smoke;
a busca de parâmetros continua como etapa a planejar. Um smoke não seleciona
nem promove uma configuração. Os resultados anteriores a 15 px permanecem
preservados com seus critérios originais, sem reavaliação automática.

## Indivíduos, agrupamentos e contagem avaliada

Consulte a [política de classes e agrupamentos](../../../../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md).
Todas as previsões participam do matching contra GT das classes 0 e 2,
independentemente da classe prevista. Indivíduos anotados dentro de uma caixa
de cluster continuam válidos. Uma previsão sem par a distância ≤ raio de
qualquer GT individual permanece FP, protegendo contra duplicatas. Das
restantes, somente as com centro dentro de uma caixa GT de classe 1 são
ignoradas. Essa regra é aplicada novamente a 10, 15 e 20 px; o F1 não tem
garantia de crescer com o raio.

`secondary_all_objects_*` registra a comparação binária separada com todas
as classes GT em cada raio. Nessa análise um cluster vale um objeto anotado,
sem representar o número de células que contém.

As contagens são explícitas:

- `n_predictions_raw` e `n_ground_truth_raw`: saídas e objetos GT originais;
- `n_predictions_scored`, `n_predictions_ignored` e `n_ground_truth_scored`:
  previsões avaliadas, ignoradas e alvos individuais, também nas sensibilidades;
- `count_mae`/`count_bias`: erro da contagem avaliada, usando todos os frames
  anotados, inclusive zeros; `count_scope` identifica esse universo;
- `count_mae_raw`/`count_bias_raw`: diferença entre contagens brutas;
- `frames_primary_evaluable`, `frames_cluster_only_gt` e
  `frames_with_ignored_predictions`: diagnósticos dos universos observados.

Um frame só com clusters e sem previsão avaliada tem F1 principal indefinido
e erro de contagem avaliada zero. O diagnóstico `primary_evaluable` não exclui
esse zero da MAE/bias. Nenhuma dessas contagens estima o total biológico de
células na imagem. O detector recebe o frame inteiro; todas as previsões e
todas as anotações originais dos frames avaliados ficam em `detections.csv`.
As regiões GT não filtram entradas do detector ou do rastreamento.

## Um smoke test

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.background_subtraction.batch_clips `
  --config configs/detection/mog2/search.yaml `
  --ids 11 --clip-count 1 --scored-frames 20 --stage smoke
```

Para KNN, troque o YAML por `configs/detection/knn/search.yaml`.

## Conferir o plano sem processar frames

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.background_subtraction.batch_clips `
  --config configs/detection/mog2/search.yaml --dry-run
```

## Uma configuração com overrides

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.background_subtraction.batch_clips `
  --config configs/detection/mog2/search.yaml `
  --set history=100 --set var_threshold=8 --set morph_kernel=3
```

Chaves sem seção entram em `params`. Para alterar amostragem use, por exemplo,
`--set sampling.clip_count=4`; `sampling.warmup_frames` abaixo de 100 é
recusado.

## Grid versionado

A expansão completa é sempre explícita:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.background_subtraction.batch_clips `
  --config configs/detection/knn/search.yaml `
  --expand-search-space --max-configs 12 --seed 42 --dry-run
```

Retire `--dry-run` apenas depois de conferir o número de configurações, vídeos,
clipes e frames impresso no plano. `--max-configs` escolhe uma subamostra
determinística do grid.

## Artefatos

Cada par configuração/vídeo cria uma run imutável em:

```text
data/tests/detection/<mog2|knn>/<configuração>__cfg<hash>/<stage>/<run_id>/
  manifest.json
  metadata.json
  clip_windows.csv
  detections.csv
  frame_metrics.csv
  summary.csv
  summary.json
```

As comparações da bateria ficam em
`data/tests/detection/<algoritmo>/_comparisons/clip_screening/<batch_id>.csv`
e `<batch_id>.json`, em arquivos imutáveis. Ambos explicitam a versão V3,
política e raios; o JSON liga a comparação a todos os `run_id` usados.
O CSV registra `macro_video_f1`, com
`metric_primary=macro_video_f1_individuals_center_10px`, suas sensibilidades,
`macro_video_count_mae` e as métricas `macro_video_secondary_all_objects_*`.
Os campos `total_n_predictions_*`, `total_n_ground_truth_*` e `total_frames_*`
permitem conferir contagens e denominadores. `n_videos_with_gt` distingue-se
de `n_videos_primary_evaluable` quando há referência somente de clusters.
