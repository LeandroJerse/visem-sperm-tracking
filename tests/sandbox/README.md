# Sandbox de teste unitário — detecção

Ambiente para rodar **um detector** em **um único frame**, inspecionar cada
etapa intermediária (cinza, binário, morfologia, transformada de distância...) e
ajustar parâmetros em isolamento. Não é pytest — é uma bancada manual de tuning.

## Modo interativo (recomendado)

Igual ao `src.detection.interactive` de produção: um menu pergunta a fonte, o
frame, o método e os parâmetros (com defaults — Enter aceita), mostra o comando
equivalente e executa.

```bash
python -m tests.sandbox.interactive
```

## Uso direto (CLI)

```bash
# Threshold no frame 0 do vídeo anotado 11 (GT sobreposto em vermelho)
python -m tests.sandbox.single_frame --method threshold --id 11 --frame 0

# Background subtraction no frame 50, aquecendo o modelo com 30 frames anteriores
python -m tests.sandbox.single_frame --method bgsub --id 11 --frame 50 --warmup 30

# Blob num vídeo bruto, com limites de área ajustados
python -m tests.sandbox.single_frame --method blob \
    --video "data/raw/videos/1_09.09.02_SSW.avi" --frame 100 \
    --set min_area=3 --set max_area=150

# Watershed ajustando o ratio do seed de foreground
python -m tests.sandbox.single_frame --method watershed --id 11 --frame 0 \
    --set dist_ratio=0.3
```

## Argumentos

| Flag | Descrição |
|---|---|
| `--method` | `threshold`, `blob`, `bgsub`, `watershed`, `yolo` |
| `--id N` | Vídeo anotado VISEM-Tracking (`Train/N/N.mp4` + `labels_ftid`) |
| `--video PATH` | Vídeo bruto qualquer (sem GT). Exclusivo com `--id` |
| `--frame N` | Índice do frame (0-based). Default `0` |
| `--warmup N` | Frames de aquecimento antes do alvo (só `bgsub`) |
| `--set key=value` | Sobrescreve um parâmetro do construtor do detector. Repetível |
| `--draw-mode` | `box`, `centroid`, `circle`, `both` (default `both`) |
| `--weights PATH` | Pesos `.pt` (só `--method yolo`) |
| `--out-dir` | Raiz das saídas (default `results/tests`) |

`--set` aceita os mesmos parâmetros do construtor de cada detector
(ex.: `min_area`, `max_area`, `blur`, `invert`, `adaptive`, `morph_kernel`,
`dist_ratio`, `var_threshold`, `min_threshold`...). O cast é automático
(int/float/bool/str).

## Saída

Uma pasta por execução em `results/tests/<método>__<vídeo>__f<frame>/`:

```
00_input.png         frame bruto
NN_<etapa>.png       etapas intermediárias (cinza, máscara, morfologia, ...)
detections.png       boxes finais (verde) + ground truth (vermelho)
detections.csv       uma linha por detecção (schema unificado)
summary.json         params, contagens e a lista de detecções
```

`results/` está no `.gitignore` — as saídas não vão para o repositório.

## Como funciona

- As etapas são extraídas em `stages.py`, que **lê os atributos do próprio
  detector** (`min_area`, `kernel`, thresholds...). Editar um detector base em
  `src/detection/` reflete aqui sem duplicar valores.
- `bgsub` é stateful: o modelo de fundo se adapta ao longo do tempo. Em um único
  frame ele fica ruidoso — use `--warmup` para alimentar os frames anteriores e
  ver a máscara contra um fundo já adaptado.
```
