# Testes automatizados do código

Esta pasta verifica propriedades conhecidas em dados sintéticos, contratos de
entrada/saída, proteção dos splits e registro das execuções. Os arquivos
`test_*.py` contêm as verificações; [`__init__.py`](__init__.py) apenas identifica
o pacote. Passar nesses testes não demonstra desempenho científico nos vídeos
do VISEM nem conclui a validação de um algoritmo.

O marco de referência individual adiciona
[elegibilidade e segmentos](integration/test_individual_ground_truth.py),
[preparação e falhas de integridade](experiments/test_individual_preparation.py)
e [escopo do congelamento](experiments/test_frozen_release.py).
Antes da primeira preparação v1, a suíte curta passou em 1.026 testes.

**Procurando a inspeção visual frame a frame?** Ela está em
[`script/detection/test/threshold/`](../script/detection/test/threshold/README.md).
Os [três modos e comandos oficiais](../script/README.md#threshold-frame-a-frame)
ficam no guia de execução.

## O que significa cada pasta de teste

| Local | Conteúdo |
|---|---|
| `tests/` — esta pasta | Verificações automáticas da implementação. |
| [`script/<tarefa>/test/`](../script/README.md#como-ler-esta-pasta) | Executores de experimentos de desenvolvimento em treino/validação. |
| [`data/tests/`](../data/README.md) | Resultados de experimentos: imagens, CSVs, métricas e manifestos. |

Os 600 ensaios históricos frame a frame usaram os 20 vídeos e permanecem como
evidência exploratória. Eles não devem ser promovidos a resultado confirmatório.
O split atual está em [`configs/protocol/splits.yaml`](../configs/protocol/splits.yaml).

## Onde está cada verificação

| Área | Abra primeiro | Outras verificações |
|---|---|---|
| Configurações e navegação | [`config/test_configs.py`](config/test_configs.py) | [Links da documentação](config/test_documentation_links.py). |
| Algoritmos de detecção | [`detection/test_algorithms.py`](detection/test_algorithms.py) | [Anotações, CSVs e execução por vídeo](detection/test_io.py); [matching e métricas](detection/test_evaluation.py). |
| Execução dos experimentos de detecção | [`detection/test_script_layout.py`](detection/test_script_layout.py) | [Splits e configurações congeladas](detection/test_split_pipeline.py); [clipes MOG2/KNN e aquecimento](detection/test_background_subtraction_script.py). |
| Validação estrita dos finalistas | [Entradas](detection/test_strict_inputs.py) · [Vídeo completo](detection/test_strict_video_runner.py) | [Coordenador e falhas](detection/test_threshold_validation_cli.py) · [Plano/agregação](experiments/test_detection_validation.py) · [Métricas por quadro](experiments/test_validation_frame_checks.py). |
| YOLO | [`detection/test_yolo_training.py`](detection/test_yolo_training.py) | [Contrato de avaliação](detection/test_yolo_evaluation.py). Casos simulados não substituem uma bateria com pesos e ambiente validados. |
| Tracking | [`tracking/test_tracking.py`](tracking/test_tracking.py) | [Pipeline, frames vazios, cache e exportação](tracking/test_pipeline.py). |
| Fluxo e predição | [`integration/test_flow_prediction.py`](integration/test_flow_prediction.py) | Translações conhecidas, métricas de fluxo, preditores, janelas e ADE/FDE. Esses testes estão hoje em `integration/`, não em pastas separadas `flow/` e `prediction/`. |
| Pipelines de fluxo, predição e integração | [`integration/test_flow_prediction_pipeline.py`](integration/test_flow_prediction_pipeline.py) | Contratos dos executores, anotações ausentes, máscaras, cache e enriquecimento de trajetórias. |
| Estatística e comparação de métodos | [`evaluation/test_statistics.py`](evaluation/test_statistics.py) | Agregação por vídeo, pareamento, incerteza e fronteira de Pareto. |
| Protocolo e registro de execuções | [`experiments/test_experiments.py`](experiments/test_experiments.py) | Amostragem, folds, proteção do teste, configuração congelada e manifestos. |
| Catálogo de resultados | [`db/test_db_runs.py`](db/test_db_runs.py) | Ingestão de execuções, caminhos e reconstrução do banco derivado. |

## Como executar

O comando da suíte e a verificação do repositório estão centralizados em
[script/README.md — verificações antes de uma bateria](../script/README.md#0-verificação-antes-de-uma-bateria).
Para localizar a implementação que um teste exercita, consulte o
[mapa de código-fonte](../src/README.md).
