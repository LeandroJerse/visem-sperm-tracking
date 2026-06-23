# Comandos do projeto — fluxo do TCC

Registro dos comandos importantes, na ordem do fluxo de trabalho. Rodar sempre a
partir da raiz do projeto (`my_tcc/`).

> Convenção das cores no vídeo gerado: **verde = detecção do algoritmo (sua
> máquina)** · **vermelho = anotação manual / ground truth (vem no VISEM-Tracking)**.

---

## 0. Modo interativo (mais fácil — recomendado)

Não precisa montar o caminho à mão. Roda, ele mostra os IDs anotados disponíveis,
pergunta o ID e as demais opções (Enter aceita o padrão), mostra o comando
equivalente e executa.

```bash
python -m src.detection.interactive
```

Fluxo: **fonte do vídeo** (`anotado` = VISEM-Tracking com gabarito / `bruto` =
VISEM original sem gabarito) → **ID do vídeo** (lista os IDs permitidos da fonte
escolhida) → **método** → (se anotado) **comparar com gabarito? (S/n)** → **nº de
frames** (Enter = todos) → **pasta de saída** → **gerar vídeo? + modo de desenho**
→ confirma e roda. No modo anotado monta sozinho os caminhos `Train/<id>/<id>.mp4`
e `Train/<id>/labels_ftid` (sem risco de misturar IDs); no bruto resolve o `.avi`
correspondente em `data/raw/videos/`.

Os comandos manuais abaixo (seções 1–2) continuam valendo para uso avançado/scripts.

---

## 1. Detecção / segmentação (gera os dados)

Roda um algoritmo de detecção no vídeo e salva os resultados. **Não compara com
nada** — apenas detecta. Use para qualquer vídeo (inclusive o VISEM original, que
não tem anotação).

```bash
python -m src.detection.run_detection --method threshold \
    --video "data/raw/videos/1_09.09.02_SSW.avi" \
    --max-frames 300
```

Saídas em `results/`:
- `1_09.09.02_SSW_threshold.csv` — coordenadas detectadas (`source=detection`).
- `1_09.09.02_SSW_threshold.mp4` — vídeo com as caixas verdes desenhadas.
- `1_09.09.02_SSW_threshold_summary.csv` — **resumo por vídeo**: `dataset_id` (ID 1–85
  resolvido via `videos.csv`), contagem total e por frame
  (`det_per_frame_mean/median/max`) e os dados clínicos do laudo já casados
  (concentração, total count, motilidade progressiva %).

> O resumo já liga automaticamente o vídeo ao seu ID e à contagem. **Atenção:** a
> contagem por frame é nº de *detecções* (precisa de tracking para contar células
> *únicas*); e os números clínicos do laudo são contagens de laboratório
> (x10⁶/mL), úteis para validação **correlacional**, não exata. Contagem exata por
> frame só com o `sperm_counts_per_frame.csv` do VISEM-Tracking.

Trocar o algoritmo é só mudar `--method`:
```bash
python -m src.detection.run_detection --method blob      --video "<video>" --max-frames 300
python -m src.detection.run_detection --method bgsub     --video "<video>" --max-frames 300
python -m src.detection.run_detection --method watershed --video "<video>" --max-frames 300
```

---

## 2. Comparação com o gabarito (detecção × anotação manual)

Mesmo comando da etapa 1, **mais** o `--gt-dir` apontando para os labels manuais
do **VISEM-Tracking** (já baixado em `data/tracked/`). Lê as anotações humanas,
desenha em vermelho por cima das verdes e grava ambas no CSV (`source=detection`
e `source=manual`).

> `11` = nº do vídeo anotado (subpasta em `Train/`); `labels_ftid` = labels com
> tracking id. Vídeos anotados disponíveis: 11–15, 19, 21–24, etc. (20 no total).

```bash
python -m src.detection.run_detection --method threshold \
    --video "data/tracked/VISEM_Tracking_Train_v4/Train/11/11.mp4" \
    --gt-dir "data/tracked/VISEM_Tracking_Train_v4/Train/11/labels_ftid" \
    --max-frames 300
```

Saída: CSV com detecção + gabarito juntos, e vídeo com **verde (algoritmo)** vs
**vermelho (humano)** para comparação visual.

> A comparação **quantitativa automática** (precision / recall / F1 por vídeo,
> sem olhar frame a frame) será o módulo `src/evaluation/` — ainda a implementar.

---

## 3. Referência dos argumentos

### Anatomia do comando

```bash
python -m src.detection.run_detection \   # executa o programa de detecção
    --method threshold \                   # QUAL algoritmo usar (a etapa que detecta)
    --video "<caminho do vídeo>" \         # O QUE processar
    --gt-dir "<pasta de labels>" \         # CONTRA O QUE comparar (opcional)
    --max-frames 300                       # QUANTO processar (opcional)
```

> Rodar sempre da raiz do projeto (`my_tcc/`). O `-m` carrega o módulo
> `run_detection.py` dentro de `src/detection/`; fora da raiz o Python não o acha.

### Tabela completa

| argumento | obrigatório | padrão | para que serve |
|---|---|---|---|
| `--method` | sim | — | algoritmo de detecção: `threshold` \| `blob` \| `bgsub` \| `watershed` \| `yolo`. É a etapa que encontra os espermatozoides. |
| `--video` | sim | — | caminho do vídeo de entrada a processar. |
| `--gt-dir` | não | nenhum | pasta com o **gabarito** (anotações manuais, ex.: `labels_ftid`). Com ela, lê o GT, desenha em vermelho e grava no CSV (`source=manual`). **Sem ela, só detecta.** |
| `--max-frames` | não | vídeo todo | processa só os primeiros N frames — **teste rápido** sem rodar o vídeo inteiro (~1470 frames). |
| `--out-dir` | não | `results` | pasta onde salvar as saídas (CSV, vídeo, resumo). |
| `--draw-mode` | não | `both` | como desenhar no vídeo: `box` (caixa) \| `centroid` (ponto) \| `circle` \| `both` (caixa+ponto). |
| `--no-video` | não | (desligado) | gera **só o CSV**, sem o vídeo anotado — mais rápido quando você só quer os números. |
| `--weights` | só p/ `yolo` | nenhum | arquivo do modelo YOLO treinado (usado apenas com `--method yolo`). |
| `--videos-csv` | não | `data/raw/videos.csv` | `videos.csv` alternativo para resolver o `dataset_id`. Normalmente não precisa. |

### Receitas rápidas

| objetivo | o que usar |
|---|---|
| só detectar (qualquer vídeo) | `--method` + `--video` |
| detectar + comparar com gabarito | adicionar `--gt-dir` |
| testar rápido | adicionar `--max-frames 50` |
| só os números (sem vídeo) | adicionar `--no-video` |
| trocar de algoritmo | mudar o `--method` |

### O que sai em `results/` (por execução)

| arquivo | conteúdo |
|---|---|
| `<vídeo>_<método>.csv` | uma linha por objeto/frame (`source=detection` verde; `source=manual` vermelho se usou `--gt-dir`). |
| `<vídeo>_<método>.mp4` | vídeo anotado (verde = algoritmo, vermelho = gabarito). Omitido com `--no-video`. |
| `<vídeo>_<método>_summary.csv` | resumo por vídeo: `dataset_id`, contagem total e por frame, dados clínicos do laudo casados. |

---

## Utilitários

```bash
# instalar dependências
pip install -r requirements.txt

# rodar os testes
python -m pytest tests/ -q
```

---

## Etapas seguintes (a preencher conforme o cronograma)

- [ ] Avaliação automática — `src/evaluation/` (matching IoU + métricas).
- [ ] Tracking — `src/tracking/` (SORT/ByteTrack, IDs persistentes).
- [ ] Optical flow — `src/flow/` (Farneback, RAFT).
- [ ] Predição de trajetória — `src/prediction/` (Kalman, LSTM).
