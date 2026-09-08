# TCC — análise de trajetórias no VISEM

O projeto compara métodos de detecção, rastreamento, fluxo óptico e predição
de trajetórias de espermatozoides. O fluxo óptico representa **movimento
aparente da imagem**; não há medição física do fluido que permita tratá-lo
como velocidade real da corrente.

O escopo usa exclusivamente vídeos do **VISEM** e as anotações do
**VISEM-Tracking**, uma extensão da mesma coleção. São 20 vídeos com trechos
anotados para avaliação quantitativa e outros 65 para aplicação posterior.
A aquisição descrita nos artigos não documenta contracorrente imposta por tubo
ou bomba. A origem dos dados e os limites dessa interpretação estão no
[protocolo experimental](docs/metodologia/PROTOCOLO.md#escopo-dos-dados-e-interpretação-do-movimento).

## Comece por aqui

| Quero… | Abra |
|---|---|
| Encontrar o threshold que já usamos | [Algoritmo threshold.py](src/detection/classical/threshold.py) |
| Inspecionar um frame e as etapas da detecção | [Threshold frame a frame: comandos e menu](script/README.md#threshold-frame-a-frame) |
| Acompanhar a busca atual de threshold no treino | [Plano prospectivo v3](docs/metodologia/BUSCA_THRESHOLD_V3.md) · [Executor e comandos](script/README.md#busca-threshold-v3) |
| Conferir alinhamento e próxima avaliação | [Revisão geral](docs/projeto/REVISAO_GERAL_20260908.md) · [Validação de duas finalistas](docs/metodologia/VALIDACAO_THRESHOLD_V3.md) |
| Encontrar todos os outros algoritmos | [Mapa do código](src/README.md) |
| Entender um método e seus parâmetros | [Catálogo de algoritmos](docs/algoritmos/README.md) |
| Saber o que realmente foi avaliado | [Matriz de experimentos](docs/projeto/MATRIZ_EXPERIMENTOS.md) |
| Entender a estrutura e retomar o trabalho | [Mapa do projeto](docs/projeto/MAPA_PROJETO.md) |
| Trabalhar no texto acadêmico | Guia local em `monografia/README.md` |

## O caminho do threshold

1. **Algoritmo:** [src/detection/classical/threshold.py](src/detection/classical/threshold.py).
   A classe `ThresholdContourDetector` contém segmentação, morfologia,
   componentes conexos e filtragem por área. Otsu e adaptativo usam variantes
   dessa mesma implementação.
2. **Referência histórica a 15 px:** [T200, abertura 1, fechamento 2](configs/detection/threshold/t200_o1_c2.yaml).
   A [cópia congelada](configs/frozen/detection/threshold/t200_o1_c2.yaml)
   registra a seleção após validação no protocolo antigo. O
   [smoke v3](configs/detection/threshold/protocol_smoke_v3.yaml) verifica a
   nova avaliação de indivíduos e agrupamentos; ainda não promove o threshold.
   A [busca e o refinamento v3](docs/metodologia/BUSCA_THRESHOLD_V3.md#refinamento-v3)
   selecionaram **T219/o0/c2 e T218/o0/c2 no treino**. A [validação completa](docs/metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026)
   selecionou **T218/o0/c2**, com F1 macro de 0,658959; nenhuma configuração
   foi liberada para confirmação. A [T218 v3 congelada para desenvolvimento](configs/frozen/detection/threshold/t218_o0_c2_v3.yaml)
   fixa os parâmetros e mantém teste/folds bloqueados. O próximo marco prepara
   [trajetórias individuais de referência](docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md) no treino.
3. **Bancada visual:** [menu](script/detection/test/threshold/interactive.py),
   [frame único](script/detection/test/threshold/single_frame.py) e
   [lote de frames](script/detection/test/threshold/batch_frames.py).
   Os [comandos oficiais](script/README.md#threshold-frame-a-frame) explicam
   como executar cada modo.
4. **Saídas locais:** `data/tests/detection/threshold/` e
   `data/tests/detection/otsu/`. O
   [guia dos artefatos de detecção](data/tests/detection/README.md) explica
   a organização dessas pastas; as runs não acompanham o código versionado.

O arquivo antigo `src/detection/detect_threshold_contours.py` foi reorganizado
em `src/detection/classical/threshold.py`. A antiga bancada `tests/sandbox/`
fica agora em `script/detection/test/threshold/`.

## Onde fica cada parte

| Pasta | O que você encontra | Guia |
|---|---|---|
| `src/` | Implementações dos algoritmos e funções reutilizáveis | [Código por tarefa](src/README.md) |
| `configs/` | Parâmetros de cada algoritmo, splits e configurações congeladas | [Configurações](configs/README.md) |
| `script/` | Arquivos que iniciam execuções, menus e lotes | [Comandos oficiais](script/README.md) |
| `tests/` | Testes automatizados que verificam o código | [Testes do software](tests/README.md) |
| `data/` | Vídeos, anotações, saídas experimentais, modelos e resultados | [Dados e resultados](data/README.md) |
| `docs/` | Metodologia, explicações dos métodos e progresso científico | [Documentação](docs/README.md) |
| `monografia/` | Fonte LaTeX oficial e entregas acadêmicas locais | `monografia/README.md` |

As pastas dos algoritmos **já existem**:
[detecção](src/detection/README.md), [tracking](src/tracking/README.md),
[fluxo](src/flow/README.md) e [predição](src/prediction/README.md).
Cada guia liga diretamente o método ao Python, ao YAML e à sua ficha.

## Por que alguns arquivos parecem vazios?

- **`__init__.py`:** identifica e, em alguns casos, organiza as importações
  de um pacote Python. Pode estar vazio ou conter apenas uma descrição.
- **Arquivo de execução curto em `script/`:** encaminha a chamada para a
  implementação em `src/`. O cabeçalho indica qual arquivo abrir.
- **`base.py`:** define a interface comum. Os algoritmos concretos ficam nas
  famílias `classical/`, `modern/`, `hybrid/` e `learned/`, quando aplicáveis.

Exemplo da integração: [arquivo de execução](script/integration/application/enrich_tracks_with_flow.py)
→ [implementação](src/integration/enrich_tracks_with_flow.py).
O `__init__.py` dessa pasta não precisa conter o algoritmo.

## Três usos diferentes de “teste”

| Caminho | Função |
|---|---|
| [tests/](tests/README.md) | Verificar o software com testes automatizados |
| [script/detection/test/threshold/](script/detection/test/threshold/README.md) | Executar a inspeção experimental frame a frame |
| [data/tests/](data/tests/README.md) | Guardar saídas de desenvolvimento, busca e validação |

O **conjunto de teste científico** é uma divisão dos vídeos, registrada em
[splits.yaml](configs/protocol/splits.yaml). Não é nenhuma dessas pastas de código.
As avaliações confirmatórias ficam em [data/results/](data/results/README.md).

## Regras para interpretar os resultados

Os 20 vídeos anotados são separados por vídeo em treino, validação e teste.
Os outros 65 servem para aplicação sem acurácia contra tracking manual.
Clipes não são amostras independentes e lacunas de anotação não são negativos.
A unidade estatística é o vídeo.

A presença de Python e YAML significa que há implementação, não que o método
tenha sido validado experimentalmente. Consulte a
[matriz](docs/projeto/MATRIZ_EXPERIMENTOS.md), o
[protocolo](docs/metodologia/PROTOCOLO.md) e o
[diário](docs/projeto/DIARIO.md) antes de avançar. A exposição de frames do
teste no piloto antigo permanece uma limitação declarada.
