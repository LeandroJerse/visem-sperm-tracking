# TCC — Rastreamento e Predição de Trajetória de Espermatozoides

Trabalho de Conclusão de Curso (UFU). Usa visão computacional **clássica e moderna**
sobre vídeos de microscopia de espermatozoides nadando contra uma contracorrente
gerada por tubo, com três objetivos:

1. **Fluxo** — estimar o vetor de movimento do fluido (a contracorrente).
2. **Rastreamento** — detectar e rastrear múltiplos espermatozoides ao longo dos frames.
3. **Predição** — prever a trajetória futura de cada célula a partir do histórico e do campo de fluxo.

Domínio: **CASA** (Computer-Aided Sperm Analysis). Métricas de motilidade: VCL, VSL,
VAP, LIN = VSL/VCL. Células pequenas, baixo contraste e movimento errático tornam
a detecção/rastreamento mais difíceis que benchmarks típicos de MOT.

## Pipeline

```
Vídeo → Extração de Frames → Detecção → Multi-Object Tracking
                          ↘ Estimação de Fluxo Óptico ↗
                                                      ↓
                                            Predição de Trajetória
```

Os módulos são **independentes** — o campo de fluxo pode ser pré-computado e cacheado.

## Estrutura

```
my_tcc/
├── data/
│   ├── raw/videos/        # vídeos brutos VISEM original (.avi)
│   ├── tracked/           # VISEM-Tracking (Train/<id>/{images,labels,labels_ftid})
│   └── yolo/              # dataset YOLO gerado (train.txt/val.txt/visem.yaml)
├── docs/                  # relatórios e análises exportadas
├── src/
│   ├── db/                # ingestão dos CSVs num SQLite analítico (results/visem.db)
│   ├── detection/         # detecção (baselines clássicos + YOLO)
│   ├── flow/              # fluxo óptico (Farneback, RAFT)
│   ├── tracking/          # SORT, DeepSORT, ByteTrack
│   ├── prediction/        # Kalman, LSTM, Transformer
│   └── evaluation/        # HOTA, MOTA, ADE, FDE
├── configs/               # hiperparâmetros por experimento (YAML)
├── tests/
└── results/               # CSVs, vídeos anotados, runs de treino YOLO
```

## Instalação

```bash
pip install -r requirements.txt
```

### GPU (CUDA) — recomendado para treinar o YOLO

O `torch` padrão do PyPI pode vir **CPU-only**, o que torna o treino inviável.
Para usar a GPU (ex.: RTX, driver CUDA 12.x+), reinstale a build com CUDA:

```bash
pip uninstall -y torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Verifique:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## Detecção

Módulo `src/detection`. Detectores clássicos (`threshold`, `blob`, `bgsub`,
`watershed`) funcionam sem treino; `yolo` exige pesos treinados.

### Modo interativo (recomendado)

```bash
python -m src.detection.interactive
```

Mostra os IDs anotados, pergunta método e opções (Enter aceita o padrão). Para o
método `yolo`, oferece: usar `best.pt` de um treino anterior, informar um caminho,
ou **treinar na hora**.

> Cores no vídeo gerado: **verde = detecção do algoritmo** · **vermelho = ground truth (VISEM-Tracking)**.

### Linha de comando

```bash
# Baseline clássico nos primeiros 300 frames, comparando com o gabarito:
python -m src.detection.run_detection --method threshold \
    --video data/tracked/VISEM_Tracking_Train_v4/Train/11/11.mp4 \
    --gt-dir data/tracked/VISEM_Tracking_Train_v4/Train/11/labels_ftid \
    --max-frames 300

# YOLO com pesos treinados:
python -m src.detection.run_detection --method yolo \
    --weights results/yolo/visem_full/weights/best.pt \
    --video <video> --gt-dir <labels>
```

Saídas: `results/<video>_<method>.csv`, `.mp4` e `_summary.csv` (com join clínico).

## Banco de dados analítico (SQLite)

O módulo `src/db` ingere todos os CSVs gerados pelo pipeline em um único SQLite
local (`results/visem.db`) para consultas SQL rápidas, joins e plotagem via pandas.

```bash
python -m src.db.build_db
# opcional: caminho customizado
python -m src.db.build_db --db results/meu_banco.db
```

Tabelas criadas:

| Tabela | Fonte | Descrição |
|---|---|---|
| `detections` | `results/**/<v>_<method>.csv` | todas as detecções e anotações GT |
| `summaries` | `results/**/<v>_<method>_summary.csv` | uma linha por run (métricas agregadas) |
| `clinical` | `data/raw/semen_analysis_data.csv` | dados laboratoriais por participante |
| `counts_gt` | `data/tracked/sperm_counts_per_frame.csv` | contagem GT por frame |

O build é atômico (gera `.db.tmp` e substitui), portanto não bloqueia leitores
abertos no DB Browser for SQLite. `results/visem.db` está no `.gitignore`.

## Treino do YOLO no VISEM-Tracking

Os labels do VISEM-Tracking já vêm em formato YOLO nativo (`class cx cy w h`).
O script faz o **split por vídeo** (não por frame, para evitar vazamento), gera o
dataset e treina.

3 classes: `0=sperm`, `1=cluster`, `2=small_or_pinhead`. Imagens 640×480.

```bash
# Apenas gerar/inspecionar o dataset (não treina):
python -m src.detection.train_yolo --prepare-only

# Treino completo na GPU (auto-batch + cache em disco):
python -m src.detection.train_yolo --epochs 100 --batch -1 --cache disk --name visem_full

# Treino-amostra leve na CPU (subamostra cada vídeo):
python -m src.detection.train_yolo --max-frames-per-video 40 --epochs 5 --batch 4

# Retomar um treino interrompido (continua de weights/last.pt):
python -m src.detection.train_yolo --resume --name visem_full
```

Principais flags: `--batch -1` (auto-batch ~60% da VRAM), `--cache disk` (corta o
gargalo de I/O — maior ganho no dataset completo), `--imgsz`, `--device`,
`--val-ids`, `--max-frames-per-video`, `--resume`.

Saída: `results/yolo/<name>/weights/best.pt` — é o `--weights` da detecção.

## Avaliação

- **Rastreamento**: MOTA, MOTP, **HOTA** (primária).
- **Predição**: **ADE** (erro médio de deslocamento), **FDE** (erro no passo final).

## Algoritmos (clássico → moderno)

| Problema | Clássico | Moderno |
|---|---|---|
| Fluxo óptico | Lucas-Kanade, Farneback, Horn-Schunck | RAFT, PWC-Net, VideoFlow |
| Detecção | Limiarização + Morfologia | YOLO, U-Net |
| Rastreamento | Kalman + Hungarian (SORT) | DeepSORT, ByteTrack, BoT-SORT |
| Predição | Filtro de Kalman, Filtro de Partículas | LSTM, GRU, Transformer |

## Testes

```bash
pytest tests/
```
