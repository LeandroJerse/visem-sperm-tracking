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
- métrica primária: F1 binário por matching Húngaro um-para-um a 15 px;
- sensibilidades: 10 e 20 px quando definidas no YAML;
- agregação da seleção: primeiro dentro do vídeo e depois média entre vídeos;
- proteção: este script aceita apenas IDs do treino. Promoção em validação deve
  usar os vídeos completos no executor geral, não estes clipes.

A notação mostrada no `--dry-run` é
`[início_aquecimento:início_avaliação|fim_avaliação)`. O fim é exclusivo.

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
`data/tests/detection/<algoritmo>/_comparisons/clip_screening/`. O CSV ordenável
registra `macro_video_f1`; o JSON liga a comparação a todos os `run_id` usados.
