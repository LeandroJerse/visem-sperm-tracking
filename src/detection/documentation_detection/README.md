# Módulo de Detecção de Espermatozoides

Detecta/segmenta espermatozoides frame a frame, salva as coordenadas em CSV e
gera um vídeo anotado para inspeção visual. Começa por **baselines clássicos**
(OpenCV) e deixa o detector **moderno** (YOLO) preparado para a fase seguinte.

## Estrutura do módulo

```
src/detection/
├── base_detector.py     # Detection (dataclass) + Detector (ABC)
├── visem_io.py          # conversão YOLO<->pixels, parser de labels, escrita do CSV
├── visualize.py         # desenho de boxes/centroides, legenda, writer de vídeo
├── runner.py            # run_on_video: loop de frames -> CSV + vídeo anotado
├── detect_threshold_contours.py   # clássico: threshold + contornos
├── detect_blob.py                 # clássico: SimpleBlobDetector
├── detect_bgsub.py                # clássico: background subtraction (movimento)
├── detect_watershed.py            # intermediário: watershed (separar grudados)
├── detect_yolo.py                 # moderno (stub): YOLO
├── run_detection.py     # CLI (--method, --video, ...)
└── documentation_detection/       # esta documentação
```

Todos os detectores implementam a mesma interface `Detector.detect(frame) ->
list[Detection]`, então são intercambiáveis via `--method`.

## Como rodar

```bash
# baseline clássico, primeiros 300 frames de um vídeo (VISEM original, sem GT)
python -m src.detection.run_detection --method threshold \
    --video "data/raw/videos/1_09.09.02_SSW.avi" \
    --max-frames 300

# comparando com o ground truth do VISEM-Tracking (sobreposto em vermelho)
python -m src.detection.run_detection --method threshold \
    --video "data/tracked/VISEM_Tracking_Train_v4/Train/11/11.mp4" \
    --gt-dir "data/tracked/VISEM_Tracking_Train_v4/Train/11/labels_ftid" \
    --max-frames 300
```

Métodos disponíveis: `threshold`, `blob`, `bgsub`, `watershed`, `yolo`.

Saídas em `results/`:
- `results/<video>_<method>.csv` — coordenadas detectadas (+ GT, se `--gt-dir`).
- `results/<video>_<method>.mp4` — vídeo anotado (detecção verde, GT vermelho).

Use `--no-video` para gerar só o CSV; `--draw-mode` (`box|centroid|circle|both`)
controla como as detecções aparecem.

## Schema do CSV

Formato longo, uma linha por objeto por frame:

| coluna | descrição |
|---|---|
| `video_id` | identificador do vídeo (stem do arquivo) |
| `frame` | índice do frame (0-based) |
| `source` | `detection` (automático) ou `manual` (ground truth) |
| `object_id` | id do detector (índice no frame) ou `track_id` do GT |
| `class_id` / `class_name` | 0/normal, 1/cluster, 2/pinhead |
| `cx`, `cy` | centro da bounding box (pixels) |
| `w`, `h` | largura e altura (pixels) |
| `x`, `y` | canto superior-esquerdo (pixels) |
| `score` | confiança (1.0 para clássicos e GT) |

Detecção e anotação manual convivem no mesmo arquivo (`source`). O formato *wide*
com `manual_annotation_x/y` casado por linha será gerado na etapa de avaliação,
após o *matching* detecção↔GT (IoU/distância). Veja [`formato_dados.md`](formato_dados.md).

## Progressão de algoritmos

| Nível | Algoritmo | Arquivo | Doc |
|---|---|---|---|
| Clássico | Threshold + Contours | `detect_threshold_contours.py` | [threshold_contours.md](threshold_contours.md) |
| Clássico | Blob Detection | `detect_blob.py` | [blob.md](blob.md) |
| Clássico/vídeo | Background Subtraction | `detect_bgsub.py` | [background_subtraction.md](background_subtraction.md) |
| Intermediário | Watershed | `detect_watershed.py` | [watershed.md](watershed.md) |
| Moderno | YOLO | `detect_yolo.py` (stub) | — |
| Futuro | Faster R-CNN, U-Net/Mask R-CNN, SAM | — | — |

## Estado dos dados

- `data/raw/` — **VISEM original** (85 vídeos `.avi` brutos + CSVs por
  participante, **sem anotação por frame**).
- `data/tracked/` — **VISEM-Tracking** (20 vídeos anotados em
  `VISEM_Tracking_Train_v4/Train/<id>/` com `images/`, `labels/`, `labels_ftid/`,
  `<id>.mp4`; + `sperm_counts_per_frame.csv` com contagem exata por frame).
- `data/processed/` — saídas intermediárias nossas.

Os baselines clássicos rodam em qualquer vídeo; a validação quantitativa usa o
VISEM-Tracking. Detalhes do formato em [`formato_dados.md`](formato_dados.md).
