# Triagem frame a frame — threshold

Bancada exploratória para observar a família threshold em frames escolhidos:
salva etapas intermediárias, compara as posições com as anotações e registra
a diferença de contagem. A avaliação usa o F1 espacial oficial nesses frames,
mas essa amostra não substitui uma validação completa por vídeo.

**Para executar:** os três modos e os comandos oficiais estão em
[script/README.md — threshold frame a frame](../../../README.md#threshold-frame-a-frame).
Este guia explica os arquivos, parâmetros e resultados da bancada.

## Onde está o código

| Arquivo | Responsabilidade |
|---|---|
| [`src/detection/classical/threshold.py`](../../../../src/detection/classical/threshold.py) | Algoritmo: cinza, limiarização, morfologia, componentes conectados e filtro de área. |
| [`interactive.py`](interactive.py) | Menu: pergunta vídeo/frame/parâmetros e chama o executor de frame único. |
| [`single_frame.py`](single_frame.py) | Executa um frame, calcula métricas e salva imagens/CSV/manifesto. |
| [`batch_frames.py`](batch_frames.py) | Repete configurações em frames e agrega os resultados por vídeo. A lista `CONFIGS` define as configurações dessa bancada. |
| [`frames.py`](frames.py) | Localiza o vídeo, lê um frame e carrega as anotações correspondentes. |
| [`__init__.py`](__init__.py) | Identifica o pacote e contém sua descrição; o algoritmo não fica nesse arquivo. |

Para `T200/o1/c2`, os parâmetros centrais são `threshold_value=200`,
`morph_iterations=1` e `close_iterations=2`. O YAML de desenvolvimento está em
[`configs/detection/threshold/t200_o1_c2.yaml`](../../../../configs/detection/threshold/t200_o1_c2.yaml).
Esta bancada recebe parâmetros por `--set`; o executor por vídeo/split descrito
no [guia oficial](../../../README.md#threshold-por-video) recebe o YAML.

O conjunto de teste (`24, 38, 47, 54`) é recusado antes da decodificação. Uma
lacuna sem arquivo de label também é recusada, em vez de virar GT vazio.

## Modos de execução

| Modo | Quando usar | Comportamento |
|---|---|---|
| Interativo | Inspecionar um frame com perguntas guiadas. | Pergunta fonte, frame, limiar e morfologia; mostra o comando equivalente e pede confirmação para executar. |
| Frame único | Repetir uma configuração explícita em um frame determinado. | Salva as etapas e as métricas da execução. Para limiar fixo, é necessário informar `threshold_value`. |
| Bateria automática | Comparar um conjunto predefinido de configurações em frames de desenvolvimento. | O padrão tenta 10 configurações × 12 vídeos de treino × 3 frames (`0, 50, 100`) = 360 execuções. `--dry-run` somente mostra o plano. |

`--method threshold` seleciona a família. **Sem `threshold_value`, o método
efetivamente executado é Otsu**; no menu, isso corresponde a deixar o limiar
vazio. Se `adaptive=true`, a variante adaptativa tem prioridade sobre o limiar
fixo. As variantes produzem pastas de algoritmo distintas (`threshold`, `otsu`
ou `adaptive_threshold`).

O resumo da bateria ordena configurações por `macro_video_f1`; `mean_abs_diff`
é diagnóstico e desempate da listagem. Essa ordenação exploratória não congela
uma configuração nem promove uma etapa do protocolo.

## Argumentos — `single_frame`

| Flag | Descrição |
|---|---|
| `--method` | `threshold` (fixo, Otsu ou adaptativo via parâmetros) |
| `--id N` | Vídeo anotado VISEM-Tracking (`Train/N/N.mp4` + `labels_ftid`) |
| `--video PATH` | Vídeo bruto qualquer (sem GT). Exclusivo com `--id` |
| `--frame N` | Índice do frame (0-based). Default `0` |
| `--set key=value` | Sobrescreve um parâmetro do construtor do detector. Repetível |
| `--draw-mode` | `box`, `centroid`, `circle`, `both` (default `both`) |
| `--no-stages` | Não salva PNGs de etapas intermediárias (útil em baterias) |
| `--seed` | Semente registrada no manifesto (default `42`) |

### Parâmetros ajustáveis por `--set` — `threshold`

| Parâmetro | Default | Descrição |
|---|---|---|
| `threshold_value` | `None` | Valor fixo 0-255. `None` = Otsu automático |
| `adaptive` | `false` | Ativa o threshold adaptativo gaussiano; tem prioridade sobre `threshold_value` |
| `adaptive_block` | `21` | Tamanho da vizinhança do threshold adaptativo; precisa ser ímpar e maior que 1 |
| `adaptive_c` | `5` | Constante subtraída da média local ponderada no threshold adaptativo |
| `morph_iterations` | `1` | Iterações de abertura morfológica (remove ruído) |
| `close_iterations` | `1` | Iterações de fechamento morfológico (preenche buracos). `0` = desabilitado |
| `blur` | `1` | Kernel do GaussianBlur (ímpar). `1` = desabilitado |
| `invert` | `false` | `true` detecta objetos escuros; `false` detecta objetos claros (cabeças brancas) |
| `morph_kernel` | `3` | Tamanho do elemento estruturante elíptico |
| `min_area` | `3` | Área mínima (px²) de um componente para ser detecção |
| `max_area` | `300` | Área máxima (px²) — descarta debris e aglomerados |

## Saída — `single_frame`

Cada execução ganha timestamp e configuração identificada por hash. O frame de
entrada é armazenado uma só vez em `_shared_inputs`:

```
data/tests/detection/
  _shared_inputs/video_11/frame_0.png
  threshold/
    t200_o1_c2__cfgXXXXXXXX/
      frame_screening/<run_id_imutável>/
        manifest.json
        01_1_gray.png
        02_3_fixed_thresh_200.png
        03_4_morph_open_x1.png
        04_5_morph_close_x2.png
        05_6_labeled_components.png
        detections.png
        detections.csv
        summary.json
    _comparisons/frame_screening/by_video/video_11.csv
```

O vídeo e o frame ficam no `manifest.json`/`summary.json`. Essa separação segue
o contrato único `<algoritmo>/<configuração>/<etapa>/<run_id>` e evita
sobrescrita.

## Saída — `batch`

```
data/tests/detection/threshold/_comparisons/frame_screening/
  by_video/video_<id>.csv
  batch_<timestamp>.csv
```

Colunas principais do resumo global: `config`, `n_runs`, `macro_video_f1`,
`mean_frame_f1`, `total_tp/fp/fn`, `mean_abs_diff` e `mean_ratio`. TP/FP/FN são
obtidos pelo matching Húngaro um-para-um com gate de centro de 15 px; frames são
agregados dentro de cada vídeo antes da média macro.

## Como funciona

- **Algoritmo de contagem**: `cv2.connectedComponentsWithStats` (CCL, 8-conn).
  Cada pixel da imagem binarizada recebe um rótulo inteiro; área e bounding box
  vêm direto da matriz de stats, sem aproximação de contornos.
- **Pipeline threshold**: cinza → (blur opcional) → threshold (fixo, Otsu ou adaptativo) →
  abertura morfológica × N → fechamento morfológico × M → CCL → filtro de área.
- **Etapas diagnósticas**: são emitidas pelo próprio
  `ThresholdContourDetector`; o script não reimplementa o algoritmo. Alterar
  parâmetros via `--set` afeta detecção e PNGs pela mesma execução canônica.
- **Comparação principal**: matching Húngaro um-para-um entre centros, gate de
  15 px, produz TP, FP, FN, precision, recall, F1 e erro de centro. O batch
  agrega dentro de cada vídeo e ordena a listagem por F1 macro.
- **Contagem complementar**: `count_diff = detectado − GT` (positivo = excesso,
  negativo = falta) e `count_ratio = detectado / GT` (1.0 = contagens iguais,
  sem garantir que as células corretas foram localizadas).

Os 600 ensaios históricos que usaram os 20 vídeos foram preservados somente
como evidência exploratória em `data/tests/detection/`; não são reproduzidos
pelo padrão atual nem promovidos ao protocolo confirmatório.

Os testes automatizados que verificam esta bancada estão em
[`tests/detection/test_script_layout.py`](../../../../tests/detection/test_script_layout.py)
e os do algoritmo em
[`tests/detection/test_algorithms.py`](../../../../tests/detection/test_algorithms.py).
Consulte o [mapa dos testes de código](../../../../tests/README.md) para a distinção
entre verificar a implementação e realizar experimentos em vídeos.
