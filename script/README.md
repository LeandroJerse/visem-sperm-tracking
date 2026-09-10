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
- [Retomada: inspeção de anotações em um quadro de treino](#inspecao-de-anotacoes)
- [Retomada: geometria das anotações dos 12 vídeos de treino](#geometria-das-anotacoes)
- [Busca prospectiva de threshold no treino](#busca-threshold-v3)
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

<a id="busca-threshold-v3"></a>

## Busca prospectiva de threshold no treino

O [plano v3](../configs/detection/threshold/search_v3.yaml) e sua
[justificativa científica](../docs/metodologia/BUSCA_THRESHOLD_V3.md) definem
171 candidatos, 12 quadros por vídeo de treino e seleção por F1 com peso igual
entre vídeos. O executor [search.py](detection/test/threshold/search.py) exige
um commit limpo. A bancada interativa e seu lote histórico continuam úteis
para inspeção, mas não executam este protocolo prospectivo.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode prepare --dry-run
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode prepare
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode benchmark
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode coarse --benchmark-manifest CAMINHO_DO_MANIFESTO_BENCHMARK
```

Substitua o último argumento pelo caminho `batch_manifest` impresso pelo
benchmark. A projeção de custo deve caber no orçamento previamente declarado;
falhas interrompem a bateria e impedem a classificação parcial.

A preparação decodifica sequencialmente somente os 12 MP4 de treino e guarda
48 quadros por vídeo em
`data/derived/detection/frame_samples/threshold_search_v3_20260908/`, com
GT integral e hashes. Os subconjuntos de 12 quadros da busca e de um quadro
do benchmark são aninhados nessa amostra, sem lacunas de anotação.

Cada candidato reúne os 12 vídeos em uma run própria sob
`data/tests/detection/threshold/<configuração>/<benchmark|search>/`. O manifesto
da bateria liga o plano, a amostra e todos os candidatos. Somente uma busca
grossa completa produz `ranking.csv` e `shortlist.json`; estes selecionam
candidatos para refinamento no treino, sem promover o detector. O refinamento
está descrito no plano e usa os modos específicos abaixo.

As runs da bateria compartilham uma captura explícita de commit, estado do
Git e ambiente, evitando centenas de consultas idênticas. Cada manifesto
registra a origem e o instante dessa captura; a bateria confere novamente
esses dados antes de aceitar a comparação. Um benchmark anterior a uma
mudança de código não habilita a nova busca: repita-o em outra run, preservando
a execução anterior. O cache pode ser reutilizado quando plano, fontes e
amostra continuam idênticos e passam na validação de hashes.

### Refinamento dos candidatos v3

Os modos abaixo verificam a busca grossa concluída e a lista derivada,
usando a [configuração operacional](../configs/detection/threshold/refinement_v3.yaml).
O YAML-base e o cache de 48 quadros por vídeo permanecem iguais. `--dry-run`
confere os artefatos dos pais e informa o universo; não carrega pixels nem
executa o detector.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode refine --dry-run
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode refinement_benchmark
.\.venv\Scripts\python.exe -m script.detection.test.threshold.search --mode refine --benchmark-manifest CAMINHO_DO_MANIFESTO_REFINEMENT_BENCHMARK
```

Use o manifesto do novo benchmark de refinamento: o benchmark da busca
grossa não serve para essa autorização. `--refinement-config` permite
informar explicitamente o YAML operacional; o padrão é o arquivo ligado acima.
A projeção deve ser até 4.800 s e a execução tem teto operacional de 7.200 s.
Nenhum modo deste executor abre validação ou teste.

O benchmark usa todos os 117 candidatos nos mesmos 12 quadros de custo;
o refinamento, todos os candidatos nos mesmos 576 quadros. As runs ficam
sob `<configuração>/refinement_benchmark/` ou `<configuração>/refinement/`,
com a mesma estrutura de dados da busca grossa. Somente o refinamento completo
produz `ranking.csv` e `finalists.json`, com dois candidatos de treino para a
validação posterior. Não são configurações congeladas.

### Validação completa dos dois finalistas v3

O [plano de validação](../configs/detection/threshold/validation_v3.yaml) fixa
T219/o0/c2 e T218/o0/c2, recuperadas por hashes do refinamento. O
[protocolo](../docs/metodologia/VALIDACAO_THRESHOLD_V3.md) exige quatro vídeos
integrais: 14/19/36 com 1.470 quadros e 52 com 1.440, totalizando 11.700
avaliações em oito runs. Registre código e protocolo em commit antes de executar.

```powershell
.\.venv\Scripts\python.exe -m script.detection.test.threshold.validate --dry-run
.\.venv\Scripts\python.exe -m script.detection.test.threshold.validate
```

`--dry-run` confere somente metadados e hashes dos resultados anteriores.
A execução exige Git limpo, leitura integral, GT estrito, exportação sem
arredondamento e rechecagem de hashes. Não aceita overrides de parâmetros,
vídeos ou quantidade de quadros. `--plan` informa o plano explicitamente;
`--out-dir` muda somente o destino, que não pode ficar em `data/sources/`.
As oito runs e o lote ficam em `data/tests/detection/threshold/`, na etapa
`validation`. Somente o lote completo gera uma seleção válida em
`selection.json`, sem congelar parâmetros, abrir o teste ou executar folds.
Manifesto com `status: failed` invalida qualquer artefato de seleção parcial.

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

<a id="inspecao-de-anotacoes"></a>

## Inspeção de anotações

O nível 1 da retomada confere um quadro de treino com suas caixas manuais,
antes de testar qualquer limiar. O executor
[`inspect_annotations.py`](project/test/inspect_annotations.py) aceita somente
vídeos do treino, não executa detector e recusa sobrescrever saídas existentes.

```powershell
.\.venv\Scripts\python.exe -m script.project.test.inspect_annotations `
  --video-id 11 --frame 0 --audit-id retomada_20260907_nivel1
```

Saída local:
`data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/`.
O primeiro quadro tem índice `0`. As imagens, a tabela de anotações e o
manifesto são explicados no
[guia dos artefatos de inspeção](../data/derived/detection/annotation_audit/README.md).
São derivados para conferir o gabarito; não substituem as runs históricas em
`data/tests/` e `data/results/` nem aprovam uma bateria de detecção.

O exemplo do nível 1 foi compreendido pelo pesquisador. No nível 2, foi
aprovada a prioridade à localização dos centros e o raio principal de 10 px,
com sensibilidade obrigatória a 15/20 px na resolução original de 640 × 480 px,
igual para todos os detectores. A política posterior de classes está abaixo.
Essas decisões não certificam todas as anotações da coleção.

<a id="geometria-das-anotacoes"></a>

## Geometria das anotações dos vídeos de treino

A auditoria descritiva do nível 2 examina as anotações dos 12 vídeos do treino
registrado, para discutir o tamanho das caixas e a proximidade entre centros.
O executor [`analyze_annotation_geometry.py`](project/test/analyze_annotation_geometry.py)
confere o split antes de acessar as fontes. Lê os arquivos de anotações e os
JPEGs para dimensões e hashes, sem decodificar os vídeos, executar detector,
fazer matching ou selecionar parâmetros. Não lê fontes de validação ou teste.

```powershell
.\.venv\Scripts\python.exe -m script.project.test.analyze_annotation_geometry --run
```

Saída local fixa:
`data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/`.
O executor recusa a execução se essa pasta já existir. Para reproduzir esta
auditoria, use uma cópia do repositório com as fontes disponíveis e a saída
ausente; não apague a saída anterior para refazer. Uma nova auditoria exige
um destino distinto, definido em uma etapa própria.

Depois da auditoria, o executor
[`render_annotation_geometry.py`](project/test/render_annotation_geometry.py)
gera uma figura a partir dos CSVs derivados, sem abrir os dados-fonte:

```powershell
.\.venv\Scripts\python.exe -m script.project.test.render_annotation_geometry --run
```

Ele salva `tolerancias_geometria.png` e `figure_manifest.json` na mesma pasta
da auditoria e recusa sobrescrever esses arquivos. O manifesto da figura
registra sua proveniência separadamente do manifesto da auditoria.

As tabelas descrevem anotações por frame, não células únicas: uma identidade
presente em vários frames participa várias vezes. Os grupos `class0`, `class1`
e `class2` são descritos separadamente, além de `cells0_2` (classes 0 e 2) e
`all` (classes 0, 1 e 2). Esses recortes não definem quais classes contar na
avaliação futura. Lacunas de anotação são excluídas, nunca tratadas como
negativos; arquivos anotados vazios têm registro próprio.

Os raios 10, 15 e 20 px descrevem a geometria das anotações, sem medir erros do
detector. A auditoria foi concluída antes da aprovação de 10 px principal;
seus CSVs e manifestos permanecem imutáveis. Os resultados são resumidos
primeiro por vídeo. Consulte o
[guia dos artefatos](../data/derived/detection/annotation_audit/README.md)
para os CSVs, o resumo e o manifesto, e a
[decisão sobre a tolerância espacial](../docs/metodologia/TOLERANCIA_ESPACIAL.md)
para sua interpretação.

<a id="agrupamentos-no-treino"></a>

### Auditoria das regiões de agrupamento

[`audit_cluster_regions.py`](project/test/audit_cluster_regions.py) confere
as anotações dos mesmos 12 vídeos contra os hashes e contagens da auditoria
de geometria. Calcula a área da união das caixas cluster, recortada à imagem,
sem contar sobreposições duas vezes. A figura usa o primeiro quadro com
cluster de cada vídeo pertinente, sem resultados de detector.

```powershell
.\.venv\Scripts\python.exe -m script.project.test.audit_cluster_regions --run
```

Saída nova: `data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/`.
O executor recusa sobrescrever a pasta. As coberturas têm denominadores
explícitos por vídeo e por quadro; a auditoria não mede erros do detector.

### Versão vigente da avaliação

A avaliação usa `center_distance_v3_individuals_ignore_clusters_10px`:
indivíduos GT 0/2 como alvos, regiões cluster para ignorar previsões residuais
sem indivíduo próximo, 10 px principal e sensibilidades obrigatórias 15/20.
As coordenadas são as da imagem original de 640 × 480 px. A regra completa,
incluindo proteção de duplicatas e comparação com todos os objetos, está em
[Classes e agrupamentos](../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md).

`center_distance_v1_15px` é a referência histórica para as métricas antigas
a 15 px. Os YAMLs históricos T200/T190 e as configurações congeladas mantêm
seus valores. A versão intermediária v2 registrou apenas a mudança de raio,
antes da política de classes. Resultados e manifestos anteriores permanecem
imutáveis. O orçamento da busca e o desenho confirmatório ainda precisam
ser registrados prospectivamente.

<a id="smoke-contrato-v3"></a>

### Smoke real do contrato v3

A configuração [protocol_smoke_v3.yaml](../configs/detection/threshold/protocol_smoke_v3.yaml)
fixa T200/o1/c2 e somente os quadros 0, 1 e 2 dos vídeos de treino 11 e 12.
O propósito é conferir processamento, contagens e arquivos; o resultado não
seleciona parâmetros nem promove o detector. Execute após os testes de código
e o commit, para registrar a versão da implementação em cada manifesto:

```powershell
foreach ($trainingVideoId in @(11, 12)) {
  .\.venv\Scripts\python.exe -m src.detection.pipeline `
    --config configs/detection/threshold/protocol_smoke_v3.yaml `
    --video "data/sources/visem_tracking/dataset/Train/$trainingVideoId/$trainingVideoId.mp4" `
    --gt-dir "data/sources/visem_tracking/dataset/Train/$trainingVideoId/labels_ftid"
}
```

Os caminhos devem corresponder à fonte local inventariada. Cada execução cria
uma run distinta sob `data/tests/detection/threshold/`, com dados brutos,
`frame_metrics.csv`, configuração resolvida e manifesto. Nunca reutilize a
pasta de uma execução para salvar outra. Validação, teste e folds não fazem
parte deste smoke.

Execução de 07/09/2026 concluída sob o commit `42ced6b`, com Git limpo:
três quadros por vídeo, dados brutos preservados e nenhuma previsão ignorada
nesse recorte. A configuração registra os oito hashes dos insumos antes da
execução. As duas runs estão sob
`data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/`.
Contagens e limites de interpretação estão na
[verificação do contrato](../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md#verificação-da-implementação--07092026).
Essa primeira execução revelou arredondamento de coordenadas no CSV. A
verificação da precisão de exportação exige novas runs dos mesmos quadros,
preservando as iniciais; contagens consistentes não bastam para declarar
reconstrução exata dos erros de distância.

A correção no commit `6b0a1e9` foi verificada repetindo os mesmos seis quadros
em novas runs, com Git limpo e parâmetros iguais. O registro local
`verification_20260907_full_precision.json`, no mesmo diretório `smoke/`,
confirma 36 associações independentes e 168 comparações de erros espaciais
a 1e-9 px. Os arquivos iniciais e sua verificação continuam preservados.

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

## Smoke causal de Farnebäck — nível 7

O [contrato causal v1](../docs/metodologia/FLUXO_CAUSAL_V1.md) e
[plano fixo](../configs/flow/farneback/causal_smoke_v1.yaml) exigem Git limpo
e testes aprovados antes dos pixels. O comando não aceita overrides:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.flow.test.causal_smoke
```

Decodifica somente os 20 primeiros quadros de cada treino 11/12, produz 19
pares por vídeo e características nos centros históricos. Falha de leitura
não equivale a conclusão. Saída nova em `data/tests/flow/farneback/`, etapa
`smoke/`, com quadros cinza, pares NPZ autenticados, índices, features, cobertura
e diagnósticos. Não usa máscara GT nem fluxo posterior à origem; não prevê
posições ou libera validação/teste. O caminho de fluxo anterior é exploratório.

Conferência independente, somente nos derivados da run concluída:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.flow.test.verify_causal_smoke `
  --run "data/tests/flow/farneback/<config>/smoke/<run>" `
  --output "data/tests/flow/farneback/<config>/smoke/verification_<identificador>.json"
```

O relatório de conferência deve ter nome novo; não sobrescrever tentativas.

## Benchmark compacto de fluxo causal — nível 8a

O [contrato compacto](../docs/metodologia/FLUXO_COMPACTO_V1.md) e o
[plano fixo](../configs/flow/farneback/compact_benchmark_v1.yaml) definem os
primeiros 60 quadros dos 12 treinos. Exige código registrado e Git limpo;
sem overrides, busca ou avaliação de predição. Não repetir runs encerradas.

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.flow.test.compact_benchmark
```

Guarda amostras únicas, ligações por janela, cobertura e quatro vizinhos
por interpolação. Apenas dois sentinelas por vídeo guardam campos densos.
A projeção indica viabilidade provisória; nunca libera extração completa.
A conferência lê somente derivados e deve produzir um arquivo novo:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.flow.test.verify_compact_benchmark `
  --manifest "data/tests/flow/farneback/<config>/benchmark/<run>/manifest.json" `
  --output "data/tests/flow/farneback/<config>/benchmark/verification_<identificador>.json"
```

O `--self-test` do verificador usa apenas casos sintéticos e precede os pixels.
O nível 7 e seus arquivos permanecem preservados.

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

## Referência de trajetórias individuais do treino

Plano: [individual_trajectories_v1.yaml](../configs/protocol/individual_trajectories_v1.yaml).
Contrato: [trajetórias individuais v1](../docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md).
Executar somente com Git limpo, após os testes do código:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.prediction.test.prepare_ground_truth
```

O comando não aceita substituição de split, vídeo ou parâmetros. Prepara os
12 vídeos de treino registrados, preserva GT bruto e observações 0/2, separa
segmentos contínuos e exporta índices de janelas 20+10. Não executa modelo,
fluxo ou métrica de predição. Só consulta metadados e hash do MP4; não certifica
decodificação integral de pixels. A run nova fica sob
`data/derived/prediction/ground_truth_individuals/`, com `manifest.json`,
`summary.json` e sete artefatos em `by_video/<id>/`. Falhas ficam preservadas.

O [T218 congelado para desenvolvimento](../configs/frozen/detection/threshold/t218_o0_c2_v3.yaml)
é a referência de detecção v3. Seu escopo bloqueia teste, folds e aplicação,
mesmo quando uma chamada tenta trocar flags ou o arquivo de splits.

## Baselines causais de predição no treino

Plano: [prediction_baselines_v1.yaml](../configs/protocol/prediction_baselines_v1.yaml).
Método e aceitação: [protocolo de baselines v1](../docs/metodologia/BASELINES_PREDICAO_V1.md).
Executar com Git limpo, após o registro e os testes do código:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.prediction.test.evaluate_baselines
```

O comando não recebe overrides: avalia persistência e velocidade constante com
mediana das últimas cinco diferenças nas mesmas janelas do pai conferido.
Lotes de 512 recebem apenas histórico; alvos ficam separados. Predições e
erros usam float64, futuro denso 1..10 e ADE/FDE nos horizontes 1, 5 e 10.
Não reexecuta a preparação ou lê fontes originais/validação/teste.

A saída nova fica sob `data/tests/prediction/baselines/`. Cada pasta de vídeo e
método contém `predictions.csv` (uma linha por janela e vinte coordenadas),
`window_metrics.csv`, `track_metrics.csv` e `summary.json`. O alvo é localizado
no pai pelo mesmo `window_id`. O manifesto, as médias e as diferenças por vídeo
ficam no topo do lote. O esquema largo é explícito e preserva os dez passos;
não substitui silenciosamente o CSV longo histórico do executor genérico.
