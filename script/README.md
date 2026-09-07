# Scripts oficiais

Esta é a referência dos comandos oficiais do TCC. Execute-os a partir da raiz
do repositório. Para entender um algoritmo, abra sua implementação em
[`src/`](../src/README.md); para escolher o que executar, use este guia.

**Procurando o threshold usado frame a frame?** Abra a
[bancada de threshold](#threshold-frame-a-frame). O algoritmo está em
[`src/detection/classical/threshold.py`](../src/detection/classical/threshold.py).

## Navegação rápida

- [Entender arquivos curtos e os três lugares chamados teste](#como-ler-esta-pasta)
- [0. Verificações de código antes de uma bateria](#0-verificação-antes-de-uma-bateria)
- [1. Detecção](#1-detecção): [threshold frame a frame](#threshold-frame-a-frame), [execução por vídeo/split](#threshold-por-video), [outros detectores](#outros-detectores), [YOLO](#yolo)
- [2. Tracking](#2-tracking)
- [3. Movimento aparente por fluxo e integração com tracks](#3-movimento-aparente-por-fluxo)
- [4. Predição](#4-predição)
- [5. Catálogo SQLite](#5-catálogo-sqlite)
- [6. Aplicação nos 65 vídeos](#6-aplicação-nos-65-vídeos)

<a id="como-ler-esta-pasta"></a>

## Como ler esta pasta

| O que você abriu | O que contém | Exemplo para seguir |
|---|---|---|
| `__init__.py` | Marca uma pasta como pacote Python; pode conter apenas uma descrição ou disponibilizar imports. Não é a implementação do algoritmo. | [`integration/application/__init__.py`](integration/application/__init__.py) contém só a descrição do pacote. |
| Um executor curto em `script/` | Chama a função principal que está em outro arquivo; poucas linhas são suficientes. | [`enrich_tracks_with_flow.py`](integration/application/enrich_tracks_with_flow.py) chama [`src/integration/enrich_tracks_with_flow.py`](../src/integration/enrich_tracks_with_flow.py). |
| Um algoritmo em `src/` | Implementa a transformação dos dados. | [`threshold.py`](../src/detection/classical/threshold.py) contém limiarização, morfologia e componentes conectados. |

Os nomes parecidos abaixo têm funções diferentes:

| Local | Para que serve | Onde começar |
|---|---|---|
| `script/<tarefa>/test/` | Executar experimentos de desenvolvimento e inspeção em vídeos/frames. | [Threshold frame a frame](#threshold-frame-a-frame) |
| `tests/` | Verificar automaticamente o comportamento do código em casos controlados. | [Mapa dos testes automatizados](../tests/README.md) |
| `data/tests/` | Guardar CSVs, imagens, métricas e manifestos produzidos pelos experimentos. | [Organização dos dados](../data/README.md) |

O nome `test/` dentro de `script/` **não significa abrir o conjunto de teste
bloqueado**. Ele reúne desenvolvimento em treino/validação. O protocolo
determina quando uma avaliação confirmatória pode ser executada.

## Convenção

```text
script/<domínio>/
├── test/          smoke, triagem, busca, refinamento e validação
└── application/   configuração congelada, teste final e aplicação
```

As saídas são escolhidas automaticamente pela etapa:

```text
data/tests/<domínio>/<algoritmo>/<configuração>/<etapa>/<run_id>/
data/results/<domínio>/<algoritmo>/<configuração>/<test|oof|application>/<run_id>/
```

`--out-dir` existe apenas para diagnóstico; omita-o nas baterias oficiais. Uma
run nunca sobrescreve outra. O manifesto registra método, algoritmo científico,
configuração resolvida, hashes, seed, commit, ambiente e custos.

Os wrappers de pipeline são deliberadamente genéricos e finos: a separação por
algoritmo fica simultaneamente no módulo de `src/`, no YAML de `configs/` e na
pasta de saída em `data/`. Isso evita manter várias cópias divergentes do mesmo
executor. Ferramentas que realmente têm um protocolo próprio, como threshold
frame a frame, MOG2/KNN por clipes e treino/avaliação YOLO, ganham subpastas
específicas em `test/`.

## 0. Verificação antes de uma bateria

```powershell
.\.venv\Scripts\python.exe -m script.project.test.validate_repository
.\.venv\Scripts\python.exe -m pytest -q
git status --short
```

O conjunto de teste (`24, 38, 47, 54`) só pode ser aberto por um YAML em
`configs/frozen/`, com `stage: test`, `split: test` e `run.frozen: true`.
O executor de split da detecção também oferece `--frozen`; tracking, fluxo,
integração e predição leem esse estado exclusivamente do YAML promovido.
O mesmo YAML é obrigatório nos folds A-E, sempre com `--frozen` e etapa
`oof`, `five_fold` ou `cross_validation`. Folds nunca são aliases de busca ou
validação. Em uma run congelada, parâmetros do algoritmo e da métrica não
podem ser alterados por `--set`; somente stage, split, seed, vídeo e opções de
renderização permanecem operacionais.

## 1. Detecção

Implementações e famílias: [mapa da detecção](../src/detection/README.md).
Parâmetros por algoritmo: [configurações](../configs/detection/).

Menu exploratório opcional (somente treino/validação):

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.interactive
```

<a id="threshold-frame-a-frame"></a>

### Threshold frame a frame: os três modos

Esta é a bancada que permite abrir um frame, observar as máscaras intermediárias
e comparar detecções com as anotações. Usa a mesma implementação de
[`ThresholdContourDetector`](../src/detection/classical/threshold.py) que a
execução por vídeo. Parâmetros e saídas estão no
[guia da bancada](detection/test/threshold/README.md).

**1. Menu interativo:** pergunta vídeo, frame e parâmetros; mostra o comando
equivalente e pede confirmação antes de executar.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.interactive
```

No menu, digite `200` como limiar, `1` abertura e `2` fechamentos para inspecionar
`T200/o1/c2`. Deixar o limiar vazio escolhe **Otsu automático**.

**2. Frame único com parâmetros explícitos:** exemplo de `T200/o1/c2` no frame
100 do vídeo de treino 11.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.single_frame `
  --id 11 --frame 100 --method threshold `
  --set threshold_value=200 --set morph_iterations=1 --set close_iterations=2
```

`--method threshold` sozinho usa Otsu, porque o padrão de `threshold_value` é
`None`. Para limiar fixo, informe o valor. O primeiro frame tem índice `0`.

**3. Bateria de frames:** primeiro veja o plano sem executar; o segundo bloco
é o comando de execução, para quando a bateria tiver sido combinada.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.batch_frames `
  --split train --dry-run
```

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.batch_frames `
  --split train
```

O padrão é 10 configurações × 12 vídeos de treino × 3 frames (`0, 50, 100`):
360 tentativas. `--frames 0 100 500` muda os frames; `--ids 11 12 13` limita os
vídeos aos IDs permitidos, e `--split val` seleciona validação. Essas escolhas
devem acompanhar a etapa prevista no protocolo.

As saídas ficam em `data/tests/detection/<algoritmo>/<configuração>/frame_screening/`.
A bancada bloqueia os quatro vídeos de teste e rejeita lacunas de anotação.
O F1 espacial é calculado nos frames inspecionados, mas essa amostra não
substitui a validação completa por vídeo. Os 600 ensaios antigos permanecem
somente como evidência exploratória.

<a id="threshold-por-video"></a>
<a id="threshold-etapa-atual"></a>

### Threshold por vídeo e split

Configuração de desenvolvimento:
[`t200_o1_c2.yaml`](../configs/detection/threshold/t200_o1_c2.yaml).
Configuração congelada:
[`t200_o1_c2.yaml`](../configs/frozen/detection/threshold/t200_o1_c2.yaml).
O estado científico é registrado na
[matriz de experimentos](../docs/projeto/MATRIZ_EXPERIMENTOS.md); os comandos
abaixo são referências de execução, não uma autorização para avançar de etapa.

Smoke em um vídeo de treino:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.run_split `
  --config configs/detection/threshold/t200_o1_c2.yaml `
  --split train --stage smoke --video-id 11 --max-frames 10
```

As duas finalistas em validação completa são executadas separadamente:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.run_split `
  --config configs/detection/threshold/t200_o1_c2.yaml `
  --split val --stage validation --save-video

.\.venv\Scripts\python.exe -m script.detection.test.run_split `
  --config configs/detection/threshold/t190_o1_c1.yaml `
  --split val --stage validation --save-video
```

A vencedora já está congelada. Quando o protocolo autorizar abrir o teste:

```powershell
.\.venv\Scripts\python.exe -m script.detection.application.run_split `
  --config configs/frozen/detection/threshold/t200_o1_c2.yaml `
  --split test --stage test --frozen --save-video
```

Depois do teste único, a confirmação OOF executa cada fold separadamente; não
use `--split all` nem reutilize `validation` como nome da etapa:

```powershell
.\.venv\Scripts\python.exe -m script.detection.application.run_split `
  --config configs/frozen/detection/threshold/t200_o1_c2.yaml `
  --split A --stage oof --frozen
```

### Outros detectores

Cada algoritmo possui configuração própria:

| Algoritmo | Código existente | Configuração inicial |
|---|---|---|
| Otsu | [`classical/threshold.py`](../src/detection/classical/threshold.py) | [otsu/search.yaml](../configs/detection/otsu/search.yaml) |
| Threshold adaptativo | [`classical/threshold.py`](../src/detection/classical/threshold.py) | [adaptive_threshold/search.yaml](../configs/detection/adaptive_threshold/search.yaml) |
| Threshold híbrido | [`hybrid/enhanced_threshold.py`](../src/detection/hybrid/enhanced_threshold.py) | [hybrid_threshold/search.yaml](../configs/detection/hybrid_threshold/search.yaml) |
| Blob | [`classical/blob.py`](../src/detection/classical/blob.py) | [blob/search.yaml](../configs/detection/blob/search.yaml) |
| MOG2 | [`classical/background_subtraction.py`](../src/detection/classical/background_subtraction.py) | [mog2/search.yaml](../configs/detection/mog2/search.yaml) |
| KNN | [`classical/background_subtraction.py`](../src/detection/classical/background_subtraction.py) | [knn/search.yaml](../configs/detection/knn/search.yaml) |
| Watershed | [`classical/watershed.py`](../src/detection/classical/watershed.py) | [watershed/search.yaml](../configs/detection/watershed/search.yaml) |
| YOLO | [`learned/yolo.py`](../src/detection/learned/yolo.py) | [yolo/search.yaml](../configs/detection/yolo/search.yaml) |

Ter código e configuração não equivale a ter avaliação científica concluída.
A seleção do algoritmo ocorre pelo YAML; não é necessário procurar uma cópia
de `run_split.py` para cada detector.

Use o mesmo ciclo `smoke → search → refinement → validation`. Otsu e adaptativo
compartilham o módulo de limiarização e componentes conectados, mas o executor
os registra em diretórios de algoritmo diferentes. MOG2/KNN precisam de
sequência e aquecimento.

Para a triagem de MOG2/KNN, use o executor temporal, não o frame a frame:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.background_subtraction.batch_clips `
  --config configs/detection/mog2/search.yaml --dry-run
```

Ele distribui clipes pelo vídeo de treino, exige pelo menos 100 frames de
aquecimento e exclui todo o transiente do F1 e da latência. O contrato completo
está em
[`detection/test/background_subtraction/README.md`](detection/test/background_subtraction/README.md).

Um override curto entra em `params`; uma chave pontuada altera outra seção:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.run_split `
  --config configs/detection/blob/search.yaml `
  --split train --stage search --video-id 11 --max-frames 300 `
  --set min_area=3 --set run.save_video=false
```

### YOLO

Prepare o split oficial 12/4/4 sem treinar:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.yolo.train `
  --config configs/detection/yolo/search.yaml --prepare-only
```

Treine uma seed por processo (`42`, `123`, `2026`):

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.yolo.train `
  --config configs/detection/yolo/search.yaml --seed 42 --stage training
```

Os pesos ficam dentro da run em
`data/tests/detection/yolo/<configuração>/training/<run_id>/ultralytics/`.
Avaliação IoU/mAP é secundária; a promoção continua usando F1 por centro:

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.yolo.evaluate `
  --weights "data/tests/detection/yolo/<config>/training/<run>/ultralytics/weights/best.pt" `
  --data data/datasets/yolo/official_12_4_4/visem.yaml `
  --stage validation --split val --seed 42
```

No teste, pesos, descritor do dataset, `imgsz`, batch, confiança e IoU devem
estar no YAML promovido; a CLI aceita apenas os campos operacionais:

```powershell
.\.venv\Scripts\python.exe -m script.detection.application.yolo.evaluate `
  --config configs/frozen/detection/yolo/<configuração>.yaml `
  --stage test --split test --seed 42 --frozen
```

## 2. Tracking

Implementações e famílias: [mapa do tracking](../src/tracking/README.md).
Parâmetros por algoritmo: [configurações](../configs/tracking/).

Primeiro use as linhas `manual` de `detections.csv` para isolar a associação;
depois repita com `detection` para o cenário fim a fim:

```powershell
.\.venv\Scripts\python.exe -m script.tracking.test.run_tracking `
  --config configs/tracking/centroid_greedy/search.yaml `
  --input-csv "data/tests/detection/threshold/<config>/validation/<run>/detections.csv" `
  --input-source manual --video-id 14 `
  --stage validation --split val --seed 42
```

Ordem: centroide guloso, Húngaro, SORT, ByteTrack-style e Adaptive Flow-SORT.
Somente o híbrido aceita `--flow-cache-index`; baselines recusam fluxo para
preservar a ablação. O HOTA oficial é calculado com TrackEval.

## 3. Movimento aparente por fluxo

Implementações e famílias: [mapa do fluxo](../src/flow/README.md).
Parâmetros por algoritmo: [configurações](../configs/flow/).

```powershell
.\.venv\Scripts\python.exe -m script.flow.test.run_flow `
  --config configs/flow/farneback/search.yaml `
  --input-video data/sources/visem_tracking/dataset/Train/11/11.mp4 `
  --video-id 11 --max-pairs 20 --stage smoke --split train
```

Ordem: Lucas–Kanade, Farneback, Horn–Schunck, RAFT, híbrido robusto e híbrido
robusto+RAFT. Para estimar fundo, use `--mask-csv` e masque as células nos dois
frames. O cache padrão fica em `data/derived/flow/cache/`.

Enriqueça tracks sem sobrescrever o original:

```powershell
.\.venv\Scripts\python.exe -m script.integration.application.enrich_tracks_with_flow `
  --tracks-csv "data/tests/tracking/sort/<config>/validation/<run>/tracks.csv" `
  --cache-index "data/tests/flow/farneback/<config>/validation/<run>/cache_index.csv" `
  --sampling background --radius 7 --inner-radius 2 --min-samples 8 `
  --output data/derived/tracking/tracks/14_tracks_with_flow.csv
```

## 4. Predição

Implementações e famílias: [mapa da predição](../src/prediction/README.md).
Parâmetros por algoritmo: [configurações](../configs/prediction/).

```powershell
.\.venv\Scripts\python.exe -m script.prediction.test.run_prediction `
  --config configs/prediction/constant_velocity/search.yaml `
  --tracks-csv "data/tests/tracking/sort/<config>/validation/<run>/tracks.csv" `
  --video-id 14 --history-length 20 --horizons 1 5 10 `
  --stage validation --split val --seed 42
```

Ordem: persistência, velocidade constante, Kalman, partículas, LSTM sem fluxo
e LSTM com fluxo. As versões `flow_aware_*` são híbridos nomeados. Treino e
avaliação da LSTM usam vídeos disjuntos.

## 5. Catálogo SQLite

```powershell
.\.venv\Scripts\python.exe -m script.project.application.build_database
```

O banco derivado fica em `data/catalog/visem.db`; CSVs e manifestos continuam
sendo as fontes de verdade.

## 6. Aplicação nos 65 vídeos

Depois de congelar todos os módulos, use os wrappers em `application/` com o
respectivo YAML em `configs/frozen/`, contendo `stage: application`,
`split: application` e `run.frozen: true`. A saída irá para `data/results/`.
Esses vídeos não possuem tracking manual: exporte trajetórias e indicadores,
mas não declare acurácia quantitativa real.
