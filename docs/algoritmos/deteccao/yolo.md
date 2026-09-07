# YOLO

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [yolo.py](../../../src/detection/learned/yolo.py) — `YoloDetector` · [Treino](../../../src/detection/yolo_training.py) · [Avaliação nativa](../../../src/detection/yolo_evaluation.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/yolo/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#yolo) |
| Ensaios e resultados | Caminho local `data/tests/detection/yolo/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Detector aprendido de uma etapa que prevê boxes, classe e confiança. No TCC é
fine-tuned no VISEM-Tracking; a comparação principal colapsa as três classes em
objeto e uma análise secundária mantém normal, cluster e small/pinhead.

## Parâmetros a estudar

Arquitetura/pesos iniciais, resolução, augmentations, batch, learning rate,
early stopping, seed e, na inferência, confiança e NMS. O split é sempre por
vídeo.

## Pontos fortes

- aprende textura e contexto, não apenas intensidade ou movimento;
- fornece boxes, classes e confiança apropriada para ByteTrack;
- pode lidar com variação visual que quebra regras globais feitas à mão.

## Pontos fracos

- requer anotações, GPU, treino e mais dependências;
- objetos minúsculos e desbalanceamento de classes são difíceis;
- risco alto de memorizar frames correlacionados se o split não for por vídeo;
- custo e diferença de domínio podem não justificar ganho pequeno.

## Estado e protocolo

O piloto treinou 100 épocas, mas teve melhor resultado por volta da época 6
(`mAP50=0,259`, `mAP50-95=0,106`) e depois piorou. Ele não é o resultado final.
Refazer em 12/4/4 com early stopping, seeds 42/123/2026 e varredura de confiança
e NMS somente na validação. Reportar F1 por centro junto de mAP e custo total.

## Treino e avaliação secundária reproduzíveis

O treino lê `configs/protocol/splits.yaml`: `train.txt` contém somente os 12
vídeos de treino, `val.txt` os quatro de validação e `test.txt` os quatro de
teste. O descritor `data/datasets/yolo/official_12_4_4/visem.yaml` referencia
as três listas, mas o teste
não participa de ajuste, early stopping ou escolha de confiança/NMS. Cada seed
é uma execução explícita; use os
[comandos oficiais de YOLO](../../../script/README.md#yolo).

Depois de congelar pesos e hiperparâmetros, a avaliação nativa por IoU é feita
separadamente da avaliação principal por distância de centro. Os mesmos
[comandos oficiais](../../../script/README.md#yolo) distinguem validação e teste.

O YAML promovido registra `input.weights`, `input.data` e os campos
`evaluation.imgsz`, `evaluation.batch`, `evaluation.conf` e
`evaluation.nms_iou`. Em teste, esses valores não podem ser sobrescritos pela
CLI.

Cada chamada cria uma run imutável sob
`data/tests/detection/yolo/<configuração>/<etapa>/<run_id>/`; no teste
congelado, a raiz passa automaticamente a `data/results/`. A run contém
manifesto, hashes dos pesos e do YAML, custo, `summary.csv/json` e
`metrics_per_class.csv`. `map50` e `map50_95` são métricas secundárias do YOLO;
não substituem o F1 binário com gate de centro de 15 px usado para promover e
comparar todos os detectores.

O treino também cria uma run nova em
`data/tests/detection/yolo/<configuração>/training/<run_id>/`. A saída nativa do
Ultralytics fica no subdiretório `ultralytics/`; manifesto e metadados registram
configuração resolvida, split, seed, hashes do descritor/listas, checkpoint de
entrada quando local, `best.pt`/`last.pt`, tempo, RAM e VRAM. `--prepare-only`
continua apenas regenerando `data/datasets/yolo/official_12_4_4/`, sem criar
uma run de treino.
O estágio padrão específico desse comando é `training`, independentemente do
`run.stage: screen` compartilhado pelo YAML de inferência. `--stage` pode
registrar explicitamente `search`, `refine` ou outra etapa. Por segurança,
`--name` e `--project` são apenas metadados de compatibilidade: não mudam o
destino científico `<RunContext>/ultralytics`.

Os pilotos antigos em
`data/tests/detection/yolo/pilot_100_epochs__cfglegacy/` permanecem históricos
e não são
sobrescritos. Como o `resume=True` do Ultralytics pode reutilizar o diretório
gravado dentro do checkpoint, o `--resume` in-place foi bloqueado. Para partir
de um `last.pt` antigo sem modificar o piloto, use-o como modelo inicial de uma
nova run imutável, conforme o
[comando de retomada do treino](../../../script/README.md#yolo).
