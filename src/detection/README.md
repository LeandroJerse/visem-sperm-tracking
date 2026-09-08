# Detecção — algoritmos, configuração e execução

[Mapa do código](../README.md) · [Comandos oficiais](../../script/README.md#1-detecção)
· [Fichas científicas](../../docs/algoritmos/deteccao/README.md)

## O threshold que já usamos

Abra [classical/threshold.py](classical/threshold.py). A classe
`ThresholdContourDetector` executa cinza → limiar → abertura → fechamento →
componentes conexos → filtro de área. `detect()` retorna as detecções e
`diagnostic_stages()` fornece as imagens intermediárias da mesma implementação.

O nome antigo era `src/detection/detect_threshold_contours.py`. Apesar do nome
da classe, o código atual extrai **componentes conexos**, não contornos.

| Quero… | Arquivo ou guia |
|---|---|
| Acompanhar a busca atual e os candidatos para refinamento | [Plano v3](../../configs/detection/threshold/search_v3.yaml) · [Resultados da busca](../../docs/metodologia/BUSCA_THRESHOLD_V3.md#resultados-v3) |
| Ver os parâmetros T200/o1/c2 | [Configuração de desenvolvimento](../../configs/detection/threshold/t200_o1_c2.yaml) |
| Consultar a seleção congelada | [YAML congelado](../../configs/frozen/detection/threshold/t200_o1_c2.yaml) |
| Inspecionar cada etapa de um frame | [Bancada frame a frame](../../script/detection/test/threshold/README.md) |
| Verificar vídeo completo e GT antes da validação | [Contrato estrito de entrada](strict_inputs.py) · [Coordenador da validação](../../script/detection/test/threshold/validate.py) |
| Encontrar as imagens e tabelas existentes | [Artefatos do threshold](../../data/tests/detection/threshold/) |

## Todos os detectores presentes

| Método | Implementação | Configuração | Ficha |
|---|---|---|---|
| Threshold fixo | [classical/threshold.py](classical/threshold.py) | [T200](../../configs/detection/threshold/t200_o1_c2.yaml), [T190](../../configs/detection/threshold/t190_o1_c1.yaml) | [Threshold fixo](../../docs/algoritmos/deteccao/threshold_fixo.md) |
| Otsu | [classical/threshold.py](classical/threshold.py) | [otsu/search.yaml](../../configs/detection/otsu/search.yaml) | [Otsu](../../docs/algoritmos/deteccao/otsu.md) |
| Adaptativo | [classical/threshold.py](classical/threshold.py) | [adaptive_threshold/search.yaml](../../configs/detection/adaptive_threshold/search.yaml) | [Adaptativo](../../docs/algoritmos/deteccao/threshold_adaptativo.md) |
| Blob | [classical/blob.py](classical/blob.py) | [blob/search.yaml](../../configs/detection/blob/search.yaml) | [Blob](../../docs/algoritmos/deteccao/blob.md) |
| MOG2 | [classical/background_subtraction.py](classical/background_subtraction.py) | [mog2/search.yaml](../../configs/detection/mog2/search.yaml) | [MOG2](../../docs/algoritmos/deteccao/mog2.md) |
| KNN | [classical/background_subtraction.py](classical/background_subtraction.py) | [knn/search.yaml](../../configs/detection/knn/search.yaml) | [KNN](../../docs/algoritmos/deteccao/knn.md) |
| Watershed | [classical/watershed.py](classical/watershed.py) | [watershed/search.yaml](../../configs/detection/watershed/search.yaml) | [Watershed](../../docs/algoritmos/deteccao/watershed.md) |
| Threshold híbrido | [hybrid/enhanced_threshold.py](hybrid/enhanced_threshold.py) | [hybrid_threshold/search.yaml](../../configs/detection/hybrid_threshold/search.yaml) | [Híbrido](../../docs/algoritmos/deteccao/threshold_hibrido.md) |
| YOLO | [learned/yolo.py](learned/yolo.py) | [yolo/search.yaml](../../configs/detection/yolo/search.yaml) | [YOLO](../../docs/algoritmos/deteccao/yolo.md) |

Fixo, Otsu e adaptativo compartilham código, mas mantêm configurações e
resultados separados. `threshold_value: null` com `adaptive: false` seleciona
Otsu; `threshold_value: 200` seleciona o limiar fixo. MOG2 e KNN também
compartilham uma base, com classes próprias e estado reiniciado por vídeo.

## Execução e arquivos de apoio

| Responsabilidade | Implementação |
|---|---|
| Interface de um detector e formato da caixa | [base.py](base.py) |
| Construir detector e identificar a variante científica | [registry.py](registry.py) |
| Processar um vídeo e registrar a run | [pipeline.py](pipeline.py) |
| Percorrer os frames e calcular métricas | [runner.py](runner.py) |
| Executar os vídeos de uma divisão | [split_runner.py](split_runner.py) |
| Ler anotações e escrever CSV | [io.py](io.py) |
| Desenhar detecções e gravar vídeo | [visualization.py](visualization.py) |
| Localizar vídeos e pesos locais | [discovery.py](discovery.py) |
| Associar metadados do dataset | [metadata.py](metadata.py) |
| Treinar YOLO / calcular métricas secundárias | [yolo_training.py](yolo_training.py), [yolo_evaluation.py](yolo_evaluation.py) |

Os arquivos curtos em `script/detection/` chamam estes serviços. Os comandos
ficam somente no [guia oficial](../../script/README.md#1-detecção).
Para MOG2/KNN existe uma [bancada temporal por clipes](../../script/detection/test/background_subtraction/README.md),
pois um frame isolado não fornece o histórico necessário ao modelo de fundo.

Saídas: `detections.csv` e `frame_metrics.csv`, além de manifestos e diagnósticos.
Veja [onde encontrar os artefatos](../../data/tests/detection/README.md) e
[quais etapas foram avaliadas](../../docs/projeto/MATRIZ_EXPERIMENTOS.md).
