# Dataset YOLO independente — contrato v1

**Atualização de 11/09/2026:** materialização e conferência concluídas,
com 23.316 pares de treino/validação. Resultados e evidências estão ao fim
deste documento. As seções prospectivas abaixo preservam o desenho anterior
à execução; o treinamento YOLO continua pendente.

Registrado em 11/09/2026 antes da materialização. Esta etapa prepara entradas
reproduzíveis para futuros ensaios YOLO. Não treina, seleciona hiperparâmetros,
executa inferência ou promove um detector. A preparação antiga continua
histórica; o novo contrato não altera `yolo_training.py`.

## Motivação e estado

O [ambiente aprendido](AMBIENTE_APRENDIDO_V1.md) está conferido por exemplos
sintéticos CUDA. A implementação antiga aponta listas de imagens diretamente
para fontes. Ultralytics pode criar caches e reparar JPEGs junto às imagens;
por isso o novo preparo produz cópias independentes, autenticadas por conteúdo.
Hardlinks, symlinks, junctions e outros reparse points são recusados nos
caminhos utilizados. Não apagar ou reparar material antigo.

**Estado no registro prospectivo, antes da execução:** código e testes sintéticos preparados; fontes foram
inspecionadas apenas por nomes, stat e conteúdo de anotações nos 16 vídeos
permitidos. Nenhum JPEG VISEM foi aberto/decodificado ou copiado, e nenhuma
materialização real foi executada nesta preparação de código.

## Entradas e universos fechados

[Plano YAML](../../configs/detection/yolo/dataset_v1.yaml),
[biblioteca](../../src/detection/yolo_dataset.py),
[entrada CLI](../../script/detection/test/yolo/prepare_dataset.py) e
[testes sintéticos](../../tests/detection/test_yolo_dataset.py).

Fonte: `data/sources/visem_tracking/dataset/Train/<id>/`.
Somente estes IDs são enumerados:

- Treino: 11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82.
- Validação: 14, 19, 36, 52.

O descritor produzido tem somente `train` e `val`; não contém entrada `test`.
O código não percorre os diretórios dos quatro vídeos de teste. Ler sua
identificação nos manifestos globais não significa acessar imagens/anotações
do teste. O teste historicamente exposto continua bloqueado; esta preparação
não recupera sua cegueira.

O YAML vincula por SHA256 o split, inventário de vídeos e lacunas oficiais.
Recusa chaves desconhecidas/duplicadas, IDs diferentes, caminhos alternativos
de fonte/manifestos, travessia de diretórios e contagens divergentes.
Os universos dentro de `images/`, `labels/` e `labels_ftid/` devem coincidir
exatamente com os nomes canônicos e números de quadro previstos.
MP4s e outros metadados fora dessas três pastas não são entradas deste preparo.

Há **17.466 pares JPEG/label no treino e 5.850 na validação**, 23.316 ao todo.
Os JPEGs existem também para as **174 lacunas do vídeo 23**: quadros
823–972 e 1084–1107. Esses quadros são inventariados como não anotados e
excluídos da cópia; não se tornam negativos. Nenhum quadro anotado é
subamostrado ou descartado por qualidade. Um label vazio, quando permitido
pelo universo anotado, significa negativo anotado e é preservado.

Os nomes de imagem são `<id>_frame_<n>.jpg`; labels YOLO usam o mesmo stem
com `.txt`; a referência usa `<id>_frame_<n>_with_ftid.txt`. Arquivos extras,
nomes alternativos para o mesmo número, labels nas lacunas e arquivos
ausentes interrompem a preparação.

### Caches legados nas fontes

A inspeção encontrou **23.316 sidecars `.npy`** junto aos JPEGs permitidos.
Eles já existiam antes desta etapa. O plano aceita apenas sidecars cujo stem
corresponda a um JPEG previsto, registra caminho/tamanho/mtime, exclui-os da
cópia e não abre seu conteúdo. Não os trata como imagens originais nem
como fonte autenticada de pixels. Outros arquivos inesperados nas pastas
de entrada são recusados. Os caches legados permanecem preservados.

## Anotações YOLO e vínculo com a avaliação v3

Cada linha de `labels/` deve conter exatamente cinco campos:
`class cx cy width height`. Classes aceitas: 0 `sperm`, 1 `cluster` e
2 `small_or_pinhead`. As quatro coordenadas são normalizadas; devem ser
finitas, largura/altura positivas e caixa contida na imagem. Duplicatas
numéricas completas são recusadas. Não arredondar, recortar, reordenar ou
reescrever os arquivos; a cópia preserva os bytes originais.

A tolerância numérica prospectiva é **1e−9 em coordenadas normalizadas**,
apenas para erro de representação de ponto flutuante. A leitura preliminar
dos 23.316 labels encontrou 125 caixas com excedente estritamente positivo
de borda, máximo **2,220446049250313e−16**, e nenhuma acima de 1e−9.
Não há extrapolação material que exija remediação nesta leitura. Zero
duplicatas, linhas inválidas ou arquivos vazios foram encontrados.

Cada quadro também é comparado à referência `labels_ftid/`, de seis campos:
`track_id class cx cy width height`. IDs originais devem ser distintos no
quadro. Comparam-se os multiconjuntos de classe e quatro coordenadas,
ignorando **somente** o ID e a ordem das linhas, com matching um a um por
classe a 1e−9 normalizado. Isso impede treinar uma versão das caixas e
avaliar outra. Divergência de contagem, classe, geometria ou universo aborta
a run; nenhuma fonte é corrigida automaticamente.

A auditoria preliminar de anotações confirmou **igualdade exata dos
multiconjuntos nos 23.316 quadros**, antes de precisar da tolerância. As
contagens somadas foram 458.327 observações classe 0, 13.026 classe 1 e
20.376 classe 2. São linhas por quadro, não indivíduos biológicos únicos.
Essa leitura preliminar orienta o contrato; a futura run deve repetir e
registrar a conferência e os hashes, sem reaproveitar uma afirmação manual
como certificado de execução.

`labels_ftid` é lido e autenticado, mas **não é copiado para o treinamento**.
O manifesto deriva hashes independentes de JPEG, label YOLO e label FTID por
quadro. Treinar três classes não muda o avaliador principal v3: indivíduos
GT 0/2 e ignorados em clusters após a proteção dos indivíduos. A avaliação
secundária de classes/mAP permanece distinta do F1 de centros.

## Duas fases de execução

1. **Planejamento de metadados:** autenticar os três manifestos, verificar
   universos, nomes, tamanhos e vínculos de caminhos; imprimir contagens,
   exclusões e orçamento. Não abrir JPEGs ou conteúdo de labels/FTID; não
   criar runs ou copiar fontes. Esse modo pode rodar antes do commit.
2. **Materialização:** depois do commit limpo e da autorização de execução,
   capturar `RunSnapshot`, criar `RunContext` exclusivo, refazer o preflight,
   copiar por streaming e validar todas as entradas. Verificar hashes antes
   e depois da cópia e novamente ao final, incluindo referências FTID.
   Conferir universo final, recursos, plano, manifestos e proveniência antes
   de concluir. Esta fase não importa Ultralytics nem executa treinamento.

Comandos, a partir da raiz:

```powershell
.venv\Scripts\python.exe -m script.detection.test.yolo.prepare_dataset --mode plan
.venv\Scripts\python.exe -m script.detection.test.yolo.prepare_dataset --mode materialize
```

O segundo comando deve ser executado somente após o registro prospectivo
do código/plano em Git limpo. A CLI não oferece override de IDs, saída,
limites, split ou critérios de exclusão. Uma mudança de contrato exige novo
YAML/registro; uma falha não autoriza uma alteração silenciosa.

O decoder OpenCV abre **somente a cópia JPEG**, exige marcadores de início/fim,
imagem BGR `uint8` com forma 480×640×3 e recusa decodificação inválida.
Não existe reparo ou descarte de imagens. A cópia é reautenticada depois
dessa validação. Verificar formato/forma não prova a qualidade biológica
das anotações nem a origem externa dos JPEGs; os hashes certificam a fonte
local usada nesta run.

## Recursos prospectivos

A inspeção `stat` dos 16 IDs calculou **1.465.425.356 bytes** de JPEGs e labels
que serão copiados, aproximadamente **1.397,54 MiB**. O maior JPEG tem
101.546 bytes. FTID é autenticado, sem cópia, e caches NPY ficam excluídos.

- Teto de todos os artefatos da run: **2.048 MiB**.
- Reserva adicional de espaço livre: **512 MiB**.
- Envelope prévio para manifestos/metadados: **64 MiB**, incluído na projeção;
  o limite final continua aplicado ao tamanho efetivamente escrito.
- Pico de RSS amostrado: **1.024 MiB**; RSS indisponível reprova o ensaio.
- Cópia em blocos de **1 MiB**, um JPEG decodificado por vez, sem cache global
  de pixels; label/FTID limitados a 1 MiB por arquivo e JPEG a 16 MiB.

Tempo é medido, sem corte temporal. A run registra os recursos amostrados;
isso não garante ausência de pico instantâneo entre medições. Não há
certificação de memória para treino CUDA, batches ou workers nesta etapa.
Se o orçamento falhar, preservar a tentativa e registrar revisão operacional
antes de executar novamente, sem apagar saídas ou reduzir a coorte.

## Saídas e consumo futuro

A interface `RunContext` cria:

```text
data/datasets/yolo/materialized/<config>/preparation/<run>/
  manifest.json
  source_metadata.json
  dataset_manifest.json
  dataset/
    visem.yaml
    train.txt
    val.txt
    images/<train|val>/<video_id>/<id>_frame_<n>.jpg
    labels/<train|val>/<video_id>/<id>_frame_<n>.txt
```

`source_metadata.json` registra o universo e a exclusão dos caches.
`dataset_manifest.json` registra hashes fonte/cópia/referência, paridade das
caixas, classes, contagens, descritores e recursos. `manifest.json` liga tudo
a commit, Git, código-fonte, configuração, ambiente e seed. A preparação
não contém pesos ou resultados de qualidade do detector.

O dataset materializado é **selado e imutável**. O descritor aponta para
essas cópias para inspeção e autenticação; não é liberação para chamar a
biblioteca diretamente nessa pasta. O futuro executor deve criar outro
clone independente dentro da run consumidora, reautenticá-lo e gerar ali
seu próprio descritor. Caches `labels.cache` e caches de imagem pertencem
à run consumidora. Mesmo com `cache=False`, a biblioteca pode escrever
cache de labels; essa opção sozinha não protege o derivado selado.
Mudanças nos bytes JPEG/labels durante o consumo devem ser detectadas e
tratadas como mudança de entrada, nunca incorporadas silenciosamente.

Falhas deixam manifesto `failed` e todos os parciais. O recibo
`source_authentication_failure.json` reautentica as fontes já abertas e
registra qualquer mudança ou erro de leitura; esse escopo parcial não
certifica fontes ainda não processadas. Não há overwrite, retomada in-place,
reparo de fonte ou exclusão automática. Reexecutar significa criar outra run.

Depois da materialização, uma conferência independente deve autenticar os
artefatos antes do smoke de treinamento YOLO. Arquitetura/pesos, receita,
augmentations, seeds, checkpoint e preservação de scores para ByteTrack
pertencem a um contrato posterior. Preparar o dataset não resolve essas
decisões nem promove os pilotos históricos.

<!-- refinement-dataset-completion-20260911 -->
## Materialização e conferência concluídas — 11/09/2026

Dataset YOLO materializado e conferido em `ca68f16`: **23.316 pares JPEG/anotação**, sendo 17.466 de treino e 5.850 de validação; 174 lacunas de anotação excluídas. Preservadas as três classes e as caixas da referência FTID. O conjunto contém 491.729 observações anotadas, não indivíduos únicos. Foram copiados 46.632 arquivos e gerados três descritores.

Preparação: 1.237,798253 s; RSS amostrado 198,160 MiB; dataset com 1.471.015.512 bytes. QA: 116.590 arquivos, 8.724.385 comparações e 23.316 cópias JPEG decodificadas em 195,027052 s. A conferência verificou paridade de 491.729 anotações, com diferença máxima 0.

[Manifesto do dataset](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json). O teste ficou fora da preparação. **Não houve treinamento YOLO:** `training_allowed=false` e `consumer_clone_required=true`; o consumidor deve gerar outro clone independente dentro de sua própria run antes de chamar a biblioteca.

A paridade geométrica entre anotações YOLO e FTID não certifica igualdade de pixels entre JPEG e MP4. Os JPEGs servem ao treinamento e à validação nativa do modelo aprendido. Para comparar F1 v3 com os clássicos, YOLO deverá processar os mesmos quadros MP4/cache usados por eles, com pré-processamento explicitamente registrado. Essa distinção delimita o derivado e o futuro contrato de comparação; não representa falha na organização atual do dataset.

SHA256 do manifesto: `e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42`.
SHA256 do QA: `0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be`.

Contagens de observações por classe: classe 0: 458.327; classe 1: 13.026; classe 2: 20.376.

O dataset selado não contém pesos nem qualidade de um detector aprendido. O próximo contrato deve fixar arquitetura/pesos, augmentations, seeds, checkpoint, seleção e preservação de scores. Não repetir a materialização concluída nem modificar suas fontes/cópias; caches pertencem apenas ao clone consumidor.
