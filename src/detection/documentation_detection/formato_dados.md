# Formato dos dados: VISEM original vs VISEM-Tracking

## VISEM original (Zenodo 2640506) — `data/raw/`

```
data/raw/
├── videos/                       # 85 vídeos .avi brutos, 640×480, ~50 fps
│   └── ID_DATA_OBSERVADOR.avi    # ex.: 1_09.09.02_SSW.avi
├── videos.csv                    # ID;video  (liga ID 1–85 ao arquivo)
├── semen_analysis_data.csv       # qualidade do sêmen (por participante)
├── participant_related_data.csv  # idade, IMC, abstinência
├── sex_hormones.csv
├── fatty_acids_serum.csv
├── fatty_acids_spermatoza.csv
└── descriptions.txt              # glossário
```

CSVs com separador `;`, decimal `,`, e **BOM** (lidos com `utf-8-sig`).
**Sem anotação por frame / bounding box / track ID.**

## VISEM-Tracking (Zenodo 7293726) — `data/tracked/`

```
data/tracked/
├── VISEM_Tracking_Train_v4/Train/<id>/   # 20 vídeos anotados (11,12,...,82)
│   ├── images/        # <id>_frame_N.jpg   (≈1470 frames/vídeo)
│   ├── labels/        # <id>_frame_N.txt              -> YOLO sem track id
│   ├── labels_ftid/   # <id>_frame_N_with_ftid.txt    -> YOLO com track id
│   ├── <id>.mp4       # vídeo do clipe (usar no --video)
│   └── <id>.txt       # lista interna de paths (ignorar)
├── sperm_counts_per_frame.csv    # frame_name, sperm_count, cluster_count, small_or_pinhead_count
├── *_Train.csv                   # metadados clínicos do subconjunto anotado
├── visem-extracted-30s-excluding-selected-20/   # clipes extras NÃO anotados
└── visem-extracted-30s-selected-20-videos-excluding-first-30s/
```

3 classes: `0` normal sperm, `1` cluster, `2` small/pinhead.

### Formato das anotações (CONFIRMADO nos dados reais)

Coordenadas em **YOLO normalizado** `[0,1]`. **Atenção:** os dois arquivos têm
**ordem de colunas diferente**:

`labels/` → `class cx cy w h`
```
0 0.27578125 0.4125 0.0265625 0.0375
```

`labels_ftid/` → `track_id class cx cy w h`  (track_id **primeiro**, é uma
**string** do LabelBox, não um inteiro)
```
ckz3v9nzv00033867jsekqdcl 0 0.27578125 0.4125 0.0265625 0.0375
```

`parse_label_line` em `visem_io.py` detecta qual layout é pelo 1º token (numérico
= `labels/`; texto = `labels_ftid/`). O `track_id` string é preservado em
`Detection.object_id`.

### Conversão YOLO ↔ pixels

```python
x, y, w_px, h_px, cx_px, cy_px = yolo_to_pixels(cx, cy, w, h, img_w, img_h)
cx, cy, w, h = pixels_to_yolo(x, y, w_px, h_px, img_w, img_h)  # inverso
```
`x, y` = canto superior-esquerdo; `cx, cy` = centro.

## Mapeamento para o CSV unificado

CSV inicialmente proposto:
```
video_id | frame | object_id | x | y | w | h | cx | cy | manual_annotation_x | manual_annotation_y
```

Ajustes frente aos dados reais:

1. O GT é **bounding box completa + classe + track id (string)**, não um ponto →
   guardamos `class_id`/`class_name` e a caixa inteira.
2. Casar detecção e GT na **mesma linha** exige *matching* (IoU/distância) →
   pertence à **avaliação**, não à detecção.

Solução: **formato longo** com coluna `source` (`detection`|`manual`); ambos
convivem no mesmo arquivo. O formato *wide* com pares casados sai na etapa de
avaliação.

Alinhamento frame↔label no `runner.py`: arquivos de label casados por **ordem
natural** (`frame_2` antes de `frame_10`); frame *i* ↔ i-ésimo `.txt`.

## Validação de contagem

`sperm_counts_per_frame.csv` (em `data/tracked/`) traz a **contagem exata por
frame** dos vídeos anotados — gabarito direto para validar nº de detecções por
frame. Cabeçalho: `frame_name, sperm_count, cluster_count, small_or_pinhead_count`
(ex.: `11_frame_0,43,0,0`). Os números clínicos do laudo (x10⁶/mL) são contagens
de laboratório → só validação **correlacional**, não exata.
