# Sandbox de teste unitário — detecção

Bancada manual de tuning: roda um detector em um único frame, inspeciona cada
etapa intermediária e compara a contagem detectada com o ground truth. Não é
pytest — é uma ferramenta de ajuste de parâmetros.

## Modos de execução

### Interativo (recomendado)

Menu guiado que pergunta fonte, frame, método e parâmetros (Enter aceita o
padrão), mostra o comando equivalente e executa.

```bash
python -m tests.sandbox.interactive
```

### Frame único (CLI)

```bash
# Threshold no frame 0 do vídeo anotado 11 (GT sobreposto em vermelho)
python -m tests.sandbox.single_frame --method threshold --id 11 --frame 0

# Threshold com valor fixo, 2 fechamentos morfológicos
python -m tests.sandbox.single_frame --method threshold --id 11 --frame 0 \
    --set threshold_value=200 --set close_iterations=2

# Background subtraction com 30 frames de aquecimento
python -m tests.sandbox.single_frame --method bgsub --id 11 --frame 50 --warmup 30

# Vídeo bruto (sem GT), sem salvar imagens de etapas
python -m tests.sandbox.single_frame --method threshold \
    --video "data/raw/videos/1_09.09.02_SSW.avi" --frame 100 --no-stages
```

### Bateria automática

Roda múltiplas configurações em todos os vídeos anotados e gera um resumo
global rankeado por `mean_abs_diff`.

```bash
# Padrão: 10 configs × 20 vídeos × frames [0, 50, 100] = 600 runs
python -m tests.sandbox.batch

# Frames e vídeos personalizados
python -m tests.sandbox.batch --frames 0 100 500 --ids 11 12 13

# Dry-run (mostra o plano sem executar)
python -m tests.sandbox.batch --dry-run
```

## Argumentos — `single_frame`

| Flag | Descrição |
|---|---|
| `--method` | `threshold`, `blob`, `bgsub`, `watershed`, `yolo` |
| `--id N` | Vídeo anotado VISEM-Tracking (`Train/N/N.mp4` + `labels_ftid`) |
| `--video PATH` | Vídeo bruto qualquer (sem GT). Exclusivo com `--id` |
| `--frame N` | Índice do frame (0-based). Default `0` |
| `--warmup N` | Frames de aquecimento antes do alvo (só `bgsub`) |
| `--set key=value` | Sobrescreve um parâmetro do construtor do detector. Repetível |
| `--draw-mode` | `box`, `centroid`, `circle`, `both` (default `both`) |
| `--no-stages` | Não salva PNGs de etapas intermediárias (útil em baterias) |
| `--weights PATH` | Pesos `.pt` (só `--method yolo`) |
| `--out-dir` | Raiz das saídas (default `results/tests`) |

### Parâmetros ajustáveis por `--set` — `threshold`

| Parâmetro | Default | Descrição |
|---|---|---|
| `threshold_value` | `None` | Valor fixo 0-255. `None` = Otsu automático |
| `morph_iterations` | `1` | Iterações de abertura morfológica (remove ruído) |
| `close_iterations` | `1` | Iterações de fechamento morfológico (preenche buracos). `0` = desabilitado |
| `blur` | `1` | Kernel do GaussianBlur (ímpar). `1` = desabilitado |
| `invert` | `false` | `true` detecta objetos escuros; `false` detecta objetos claros (cabeças brancas) |
| `morph_kernel` | `3` | Tamanho do elemento estruturante elíptico |
| `min_area` | `3` | Área mínima (px²) de um componente para ser detecção |
| `max_area` | `300` | Área máxima (px²) — descarta debris e aglomerados |

## Saída — `single_frame`

Uma pasta por execução em `results/tests/<vídeo>/<método>__f<frame>[__params]/`:

```
results/tests/
  11/
    comparisons.csv              ← acumula todas as runs deste vídeo
    threshold__f0/               ← run com defaults
      00_input.png
      01_1_gray.png
      02_3_otsu_thresh_117.png   ← nome inclui o valor calculado
      03_4_morph_open_x1.png
      04_5_morph_close_x1.png
      05_6_labeled_components.png
      detections.png             ← boxes verdes (det) + vermelhas (GT)
      detections.csv
      summary.json
    threshold__f0__threshold_value=200__close_iterations=2/
      ...
```

`results/` está no `.gitignore` — as saídas não vão para o repositório.

## Saída — `batch`

```
results/tests/
  <video_id>/
    comparisons.csv    ← acumulativo, uma linha por run
  batch_<timestamp>.csv  ← resumo global, rankeado por mean_abs_diff
```

Colunas do resumo global: `config`, `n_runs`, `mean_diff`, `median_diff`,
`std_diff`, `mean_ratio`, `median_ratio`, `mean_abs_diff`, `median_abs_diff`.

## Como funciona

- **Algoritmo de contagem**: `cv2.connectedComponentsWithStats` (CCL, 8-conn).
  Cada pixel da imagem binarizada recebe um rótulo inteiro; área e bounding box
  vêm direto da matriz de stats, sem aproximação de contornos.
- **Pipeline threshold**: cinza → (blur opcional) → threshold (fixo ou Otsu) →
  abertura morfológica × N → fechamento morfológico × M → CCL → filtro de área.
- **`stages.py`** lê os atributos do próprio objeto detector (`det.blur`,
  `det.kernel`, `det.threshold_value`...) para gerar as imagens de etapa.
  Alterar parâmetros via `--set` reflete automaticamente nos PNGs, sem
  duplicar valores.
- **`bgsub`** é stateful: use `--warmup N` para alimentar N frames anteriores
  ao modelo de fundo antes de avaliar o frame alvo.
- **Comparação**: `count_diff = detectado − GT` (positivo = excesso, negativo =
  falta). `count_ratio = detectado / GT` (1.0 = perfeito). Ambos vão para
  `summary.json` e `comparisons.csv`.
