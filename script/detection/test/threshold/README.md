# Triagem frame a frame — threshold

Bancada exploratória para observar a família threshold em frames escolhidos:
salva etapas intermediárias, compara as posições com as anotações e registra
a diferença de contagem avaliada. O protocolo ativo é
`center_distance_v3_individuals_ignore_clusters_10px`: F1 de localização de
células individualmente anotadas, com raio principal de 10 px e sensibilidades
de 15 e 20 px. Essa amostra não substitui uma validação completa por vídeo.

A política de classes foi aprovada em 07/09/2026 e a continuidade autônoma
está autorizada. A implementação e seu smoke verificam o contrato técnico;
a busca de parâmetros continua como etapa a planejar, sem configuração
promovida pela simples atualização do avaliador.

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

O conjunto de teste (`24, 38, 47, 54`) é recusado antes da decodificação,
inclusive quando `--video` aponta para seus caminhos conhecidos no
VISEM-Tracking. Uma lacuna sem arquivo de label também é recusada, em vez de
virar GT vazio. Vídeos brutos externos sem GT permitem inspeção sem métricas.

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

O resumo da bateria ordena configurações por `macro_video_f1` e usa
`macro_video_count_mae` como desempate. `mean_abs_diff` permanece diagnóstico
por frame. Essa ordenação exploratória não congela uma configuração nem
promove uma etapa do protocolo.

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
    _comparisons/frame_screening/center_distance_v3_individuals_ignore_clusters_10px/
      by_video/video_11.csv
```

O vídeo e o frame ficam no `manifest.json`/`summary.json`. Essa separação segue
o contrato único `<algoritmo>/<configuração>/<etapa>/<run_id>` e evita
sobrescrita.

## Saída — `batch`

```
data/tests/detection/threshold/_comparisons/frame_screening/center_distance_v3_individuals_ignore_clusters_10px/
  by_video/video_<id>.csv
  batch_<timestamp>.csv
```

Colunas principais do resumo global: `config`, `n_runs`, `macro_video_f1`,
`mean_frame_f1`, `total_tp/fp/fn`, `macro_video_count_mae`, `mean_abs_diff` e
`mean_ratio`. TP/FP/FN são agregados dentro de cada vídeo antes da média macro.
`metric_primary` identifica `macro_video_f1_individuals_center_10px`; no frame
único, identifica `f1_individuals_center_10px`.

Os comparativos registram versão, política de classes, raio principal e raios
complementares. Os sufixos `_at_15px` e `_at_20px` identificam sensibilidades
recalculadas, incluindo suas contagens avaliadas e ignoradas. A avaliação
complementar aparece como `secondary_all_objects_*` nos frames e como
`macro_video_secondary_all_objects_*`/`total_secondary_all_objects_*` no
resumo da bateria. `total_frames_*` e `n_videos_primary_evaluable*` informam
os universos observados.

As saídas históricas a 15 px e eventuais saídas da versão 2 permanecem
preservadas em seus caminhos e com seus critérios originais; não são
mescladas à subpasta V3. Uma mudança do critério não reavalia nem promove
automaticamente os resultados antigos.

## Classes e significado das contagens

A referência completa é a [política de classes e agrupamentos](../../../../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md).
Todas as previsões participam do matching principal contra GT das classes
0 e 2, independentemente da classe prevista. Um indivíduo anotado dentro de
um cluster continua sendo alvo válido. Entre previsões sem par, aquelas a
distância ≤ raio de qualquer GT individual permanecem FP, protegendo contra
duplicatas. Das demais, somente as com centro dentro de uma caixa GT de
classe 1 são ignoradas. A regra inteira é refeita em cada raio; o F1 não tem
garantia de aumentar com o raio.

O prefixo `secondary_all_objects_*` identifica uma avaliação binária separada
com todas as classes GT, contando cada cluster como um objeto anotado. Essa
análise não estima quantas células existem dentro de um agrupamento.

| Campo no frame | Significado |
|---|---|
| `n_predictions_raw`, `n_detections` | Todas as saídas do detector. |
| `n_ground_truth_raw`, `n_ground_truth` | Todos os objetos anotados, incluindo clusters. |
| `n_predictions_scored`, `n_predictions_ignored` | Previsões que recebem pontuação e previsões ignoradas no raio indicado. |
| `n_ground_truth_scored` | Alvos individuais GT das classes 0 e 2. |
| `count_diff`, `count_error` | Previsões avaliadas menos alvos individuais; positivo indica excesso. |
| `count_ratio` | Previsões avaliadas divididas pelos alvos individuais; indefinido quando não há alvo individual. |
| `count_diff_raw`, `count_error_raw` | Diferença entre saídas brutas e todos os objetos GT. |
| `primary_evaluable` | Diagnóstico de evidência para PRF; não seleciona o denominador da contagem. |

MAE/bias da contagem usam todos os frames anotados, inclusive erro zero em um
frame só com clusters e sem previsão avaliada. Nesse caso, o F1 principal é
indefinido. Contagem igual não garante localização correta nem representa o
total biológico de células. `count_scope` explicita esse universo nos resumos.
As regiões GT são usadas apenas pelo avaliador: todas as previsões e todas
as anotações originais permanecem em `detections.csv`.

## Como funciona

- **Algoritmo de contagem**: `cv2.connectedComponentsWithStats` (CCL, 8-conn).
  Cada pixel da imagem binarizada recebe um rótulo inteiro; área e bounding box
  vêm direto da matriz de stats, sem aproximação de contornos.
- **Pipeline threshold**: cinza → (blur opcional) → threshold (fixo, Otsu ou adaptativo) →
  abertura morfológica × N → fechamento morfológico × M → CCL → filtro de área.
- **Etapas diagnósticas**: são emitidas pelo próprio
  `ThresholdContourDetector`; o script não reimplementa o algoritmo. Alterar
  parâmetros via `--set` afeta detecção e PNGs pela mesma execução canônica.
- **Comparação principal**: matching Húngaro um-para-um entre centros, com
  prioridade aos indivíduos e tratamento dos clusters descrito acima. O
  batch agrega dentro de cada vídeo e ordena pelo F1 macro principal.
- **Contagem complementar**: diferença e razão do universo avaliado,
  acompanhadas das quantidades brutas e das previsões ignoradas.

Os 600 ensaios históricos que usaram os 20 vídeos foram preservados somente
como evidência exploratória em `data/tests/detection/`; não são reproduzidos
pelo padrão atual nem promovidos ao protocolo confirmatório.

Os testes automatizados que verificam esta bancada estão em
[`tests/detection/test_script_layout.py`](../../../../tests/detection/test_script_layout.py)
e [`tests/detection/test_cluster_orchestration.py`](../../../../tests/detection/test_cluster_orchestration.py);
os do algoritmo ficam em
[`tests/detection/test_algorithms.py`](../../../../tests/detection/test_algorithms.py).
Consulte o [mapa dos testes de código](../../../../tests/README.md) para a distinção
entre verificar a implementação e realizar experimentos em vídeos.
