# Diário de Progresso — TCC VISEM

Registro simples e cronológico do que foi feito e testado. Entrada mais recente no topo.

---

## 2026-06-23

**Detecção — módulo completo**
- Baselines clássicos prontos: `threshold`, `blob`, `bgsub`, `watershed`.
- CLI `run_detection` e modo interativo (`interactive`) funcionando.
- Convenção do vídeo: verde = detecção do algoritmo · vermelho = ground truth.

**YOLO — detector moderno**
- `detect_yolo.py`: wrapper do Ultralytics; exige `--weights`.
- Corrigido o erro "YoloDetector requer --weights" no modo interativo: agora
  o menu detecta pesos de treinos anteriores, deixa informar o caminho, ou treinar na hora.

**Treino do YOLO (`train_yolo.py`)** — criado e testado:
- Split **por vídeo** (16 treino / 4 val) para não vazar frames quase-iguais.
- Gera `data/yolo/{train,val}.txt` + `visem.yaml`. 3 classes (sperm/cluster/small_or_pinhead).
- Flags: `--batch -1` (auto), `--cache disk`, `--max-frames-per-video`, `--resume`.
- ✅ Testado `--prepare-only` (29.196 frames) e smoke test de 1 época na GPU.

**GPU / CUDA** — habilitado:
- torch era CPU-only → reinstalado com CUDA (`cu128`).
- ✅ `torch.cuda.is_available() == True` — RTX 4070 Ti (12 GB) reconhecida.
- Treino completo (`--epochs 100 --batch -1 --cache disk --name visem_full`) iniciado;
  auto-batch escolheu 22, AMP ligado. Saída: `results/yolo/visem_full/weights/best.pt`.

**Infra**
- README, `requirements.txt` (+ultralytics), `.gitignore` (PDFs, `runs/`, `data/yolo/`).
- Testes de I/O de detecção (`tests/`).

---

## Como retomar o treino interrompido

```bash
python -m src.detection.train_yolo --resume --name visem_full
```

## Próximos passos
- [ ] Concluir o treino completo do YOLO e avaliar (mAP50 / mAP50-95).
- [ ] Rodar detecção YOLO com o `best.pt` e comparar com os baselines clássicos.
- [ ] Módulo de fluxo óptico (`src/flow`): Farneback → RAFT.
- [ ] Rastreamento (`src/tracking`): SORT → ByteTrack.
- [ ] Predição (`src/prediction`): Kalman → LSTM.
