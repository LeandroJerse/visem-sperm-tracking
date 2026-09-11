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

Detector aprendido de uma etapa que prevê boxes, classe e confiança. Houve
fine-tuning em piloto histórico; o treinamento no protocolo vigente ainda
precisa ser executado. A avaliação principal v3 usa indivíduos GT das classes
0/2, com ignorados em clusters após matching e proteção dos indivíduos.
Todas as previsões entram, inclusive classe prevista 1. A avaliação nativa
secundária mantém as três classes: sperm, cluster e small_or_pinhead.

## Parâmetros a estudar

Arquitetura/pesos iniciais, resolução, augmentations, batch, learning rate,
early stopping, seed e, na inferência, confiança e NMS. O split é sempre por
vídeo.

## Pontos fortes

- aprende textura e contexto, não apenas intensidade ou movimento;
- fornece boxes, classes e confiança contínua para associação em duas etapas;
- pode lidar com variação visual que quebra regras globais feitas à mão.

## Pontos fracos

- requer anotações, GPU, treino e mais dependências;
- objetos minúsculos e desbalanceamento de classes são difíceis;
- risco alto de memorizar frames correlacionados se o split não for por vídeo;
- custo e diferença de domínio podem não justificar ganho pequeno.

## Estado e protocolo

O registro histórico do piloto informa 100 épocas, com melhor resultado por volta da época 6
(`mAP50=0,259`, `mAP50-95=0,106`) e depois piorou. Ele não é o resultado final.
Esse comportamento não define retrospectivamente a época de parada da nova
bateria. Registrar receita, regra de checkpoint e seeds 42/123/2026 antes de
treinar. Ajustes de confiança/NMS serão pesquisados no treino; a validação
selecionará finalistas conforme contrato próprio. Se ela também orientar
early stopping, esse uso deverá ser explícito e não será uma estimativa
independente de desempenho. Reportar F1 v3 junto de mAP e custo total.

## Ambiente CUDA conferido — 11/09/2026

O ambiente isolado `.venv-ml` tem Python 3.13.3, torch 2.9.1+cu128,
torchvision 0.24.1+cu128 e Ultralytics 8.4.147. Os seis checks sintéticos
passaram na RTX 4070 Ti em 12,0624322 s, incluindo YOLOv8n de três classes
construído por YAML, sem pesos externos. Foram conferidos 55 pacotes e
`pip check`; a `.venv` clássica foi preservada. O smoke não treinou YOLO,
não leu VISEM nem mediu qualidade de detecção. Recibo, hashes e limites:
[Ambiente aprendido v1](../../metodologia/AMBIENTE_APRENDIDO_V1.md).

## Infraestrutura existente e preparação necessária

O executor existente lê `configs/protocol/splits.yaml`: `train.txt` contém os 12
vídeos de treino, `val.txt` os quatro de validação e `test.txt` os quatro de
teste. O descritor `data/datasets/yolo/official_12_4_4/visem.yaml` referencia
as três listas. Esse comportamento descreve a infraestrutura anterior, não
uma preparação já aprovada para a nova bateria. Listas apontando diretamente
para `data/sources` são inadequadas: a biblioteca pode criar caches junto a
labels/imagens e reparar JPEGs no próprio caminho. É necessário preparar uma
cópia derivada autenticada, preservar fontes e verificar universos, classes,
lacunas, duplicatas e hashes antes/depois da execução. O descritor de treino
novo deve excluir o teste; o leitor precisa conferir também os IDs e
conteúdos das listas, não apenas o nome lógico do split.

Cada seed será uma execução explícita. O próximo smoke usa somente os
treinos 11/12, antes da receita completa. Os
[comandos oficiais de YOLO](../../../script/README.md#yolo) documentam as
entradas disponíveis; um novo executor estrito e seu contrato ainda são
necessários para essas garantias.

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
não substituem o F1 por centros da comparação comum. Na nova avaliação, o
raio principal aprovado é 10 px e as sensibilidades são 15/20 px, sob a
política v3 de indivíduos e ignorados em clusters já definida. Resultados
históricos a 15 px mantêm sua definição original. Consulte a
[decisão de tolerância](../../metodologia/TOLERANCIA_ESPACIAL.md).

O treino também cria uma run nova em
`data/tests/detection/yolo/<configuração>/training/<run_id>/`. A saída nativa do
Ultralytics fica no subdiretório `ultralytics/`; manifesto e metadados registram
configuração resolvida, split, seed, hashes do descritor/listas, checkpoint de
entrada quando local, `best.pt`/`last.pt`, tempo, RAM e VRAM. `--prepare-only`
continua apenas regenerando `data/datasets/yolo/official_12_4_4/`, sem criar
uma run de treino. Esses hashes das listas não autenticam sozinhos o conteúdo
de todas as imagens e anotações; essa ligação será exigida no novo preparo.
O estágio padrão específico desse comando é `training`, independentemente do
`run.stage: screen` compartilhado pelo YAML de inferência. `--stage` pode
registrar explicitamente `search`, `refine` ou outra etapa. Por segurança,
`--name` e `--project` são apenas metadados de compatibilidade: não mudam o
destino científico `<RunContext>/ultralytics`. A configuração atual aceita
chaves que `_training_kwargs` não repassa, como optimizer, augmentations e
amp. O novo executor deverá rejeitar campos desconhecidos, repassar os
admitidos e registrar todos os argumentos efetivos, junto do lock de versões.

Na versão instalada, o `best.pt` nativo é escolhido pelo mAP50–95; não é
automaticamente o checkpoint com melhor F1 v3. O `last.pt` guarda a última
época executada, possivelmente anterior ao limite por early stopping. A
regra de checkpoint deverá ser registrada antes dos erros. Preservar ambos
com hashes, época, origem e indicação de EMA.

Para ByteTrack-style, exportar detecções com piso de confiança compatível
com o menor `low_threshold` prospectivo. O wrapper preserva scores, mas seu
corte padrão 0,25 pode excluir as observações de baixa confiança antes da
associação. Fixar NMS, máximo de detecções e precisão; manter todas as
previsões/classes e aplicar filtros de avaliação somente no avaliador.

Os pilotos antigos em
`data/tests/detection/yolo/pilot_100_epochs__cfglegacy/` permanecem históricos
e não são
sobrescritos. Como o `resume=True` do Ultralytics pode reutilizar o diretório
gravado dentro do checkpoint, o `--resume` in-place foi bloqueado. Para partir
de um `last.pt` antigo sem modificar o piloto, use-o como modelo inicial de uma
nova run imutável, conforme o
[comando de retomada do treino](../../../script/README.md#yolo). Essa
inicialização por pesos antigos não equivale a recuperar o estado completo
do otimizador, scheduler e época; sua proveniência e exposição anterior
devem ser declaradas. Os pilotos não serão promovidos ao protocolo atual.
