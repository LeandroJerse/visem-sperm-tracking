# Código-fonte — encontre a implementação

[Início do projeto](../README.md) · [Mapa do projeto](../docs/projeto/MAPA_PROJETO.md)
· [Comandos de execução](../script/README.md)

Esta pasta contém os algoritmos e as funções reutilizáveis. Para encontrar um
método, abra o guia de sua tarefa; cada linha leva ao arquivo Python real,
à configuração e à explicação científica.

## Algoritmos por tarefa

| Tarefa | Métodos presentes | Abra |
|---|---|---|
| Detecção | Threshold fixo, Otsu, adaptativo, Blob, MOG2, KNN, Watershed, híbrido e YOLO | [Mapa da detecção](detection/README.md) |
| Tracking | Centroide, Húngaro, SORT, ByteTrack-style e Adaptive Flow-SORT | [Mapa do tracking](tracking/README.md) |
| Fluxo óptico | Lucas–Kanade, Farneback, Horn–Schunck, RAFT e híbridos | [Mapa do fluxo](flow/README.md) |
| Predição | Persistência, velocidade constante, Kalman, partículas, LSTM e variantes com fluxo | [Mapa da predição](prediction/README.md) |
| Integração | Acrescentar fluxo válido às trajetórias | [Mapa da integração](integration/README.md) |

**Threshold usado anteriormente:**
[detection/classical/threshold.py](detection/classical/threshold.py).
Sua [bancada frame a frame](../script/detection/test/threshold/README.md)
reutiliza essa implementação para mostrar as etapas intermediárias.

## Como ler as pastas dos algoritmos

- `classical/`: algoritmos clássicos, sem melhorias híbridas escondidas.
- `modern/`: métodos modernos sem treino próprio, quando essa categoria existir.
- `learned/`: modelos aprendidos ou adaptadores de modelos com pesos.
- `hybrid/`: adaptações nomeadas e combinações avaliadas separadamente.

Nem toda tarefa possui as quatro categorias. Algumas variantes compartilham
uma classe, como threshold/Otsu/adaptativo, ou herdam uma implementação,
como LSTM com fluxo. O guia da tarefa identifica esses casos.

| Nome de arquivo | Papel |
|---|---|
| Arquivo do método dentro de uma família | Implementação concreta do algoritmo |
| `base.py` | Interface e tipos comuns; métodos abstratos são intencionais |
| `registry.py` ou `factory.py` | Associação entre nome do método e classe |
| `pipeline.py` | Integração da execução com configuração, entradas e artefatos |
| `runner.py` | Processamento repetido de frames ou detecções, quando separado |
| `__init__.py` | Identificação do pacote e exportação das classes; pode ser pequeno |

## Infraestrutura compartilhada

| Área | Arquivos para começar | Responsabilidade |
|---|---|---|
| Caminhos e artefatos | [core/paths.py](core/paths.py), [artifacts.py](core/artifacts.py), [relocation.py](core/relocation.py) | Localização, escrita e resolução de caminhos históricos |
| Configuração e protocolo | [experiments/config.py](experiments/config.py), [dataset.py](experiments/dataset.py), [protocol.py](experiments/protocol.py) | YAML, splits e restrições das etapas |
| Execuções experimentais | [experiments/runs.py](experiments/runs.py), [resources.py](experiments/resources.py), [sweep.py](experiments/sweep.py), [sampling.py](experiments/sampling.py) | Proveniência, custo, busca e amostragem |
| Avaliação | [evaluation/detection.py](evaluation/detection.py), [tracking.py](evaluation/tracking.py), [statistics.py](evaluation/statistics.py), [pareto.py](evaluation/pareto.py) | Matching, avaliação MOT, estatística por vídeo e qualidade/custo |
| Catálogo derivado | [db/build_db.py](db/build_db.py), [run_ingest.py](db/run_ingest.py) | Consolidação dos artefatos em SQLite |
| Validação estrutural | [experiments/validate.py](experiments/validate.py) | Conferência de inventários e divisões |

Os [testes automatizados](../tests/README.md) verificam o código. O
[estado científico](../docs/projeto/MATRIZ_EXPERIMENTOS.md) registra quais
experimentos reais foram concluídos. Esses dois estados são diferentes.
