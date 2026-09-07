# Formato dos dados VISEM

Este documento descreve como os datasets são interpretados pelo projeto. Os
arquivos originais ficam sob `data/sources/` e são imutáveis; qualquer
conversão pertence a `data/derived/`.

## VISEM

```text
data/sources/visem/
├── videos/       85 arquivos AVI
├── clinical/     tabelas clínicas CSV
└── metadata/     descrição e catálogo original dos vídeos
```

O ID é o inteiro antes do primeiro sublinhado do nome do vídeo, por exemplo
`14_09.01.27_SSW.avi` corresponde ao vídeo `14`. O nome completo é preservado
no catálogo; código não deve reconstruir caminhos supondo que todos os sufixos
tenham o mesmo formato.

## VISEM-Tracking

```text
data/sources/visem_tracking/
├── dataset/Train/<video_id>/
│   ├── <video_id>.mp4
│   ├── images/<video_id>_frame_<n>.jpg
│   ├── labels/<video_id>_frame_<n>.txt
│   └── labels_ftid/<video_id>_frame_<n>_with_ftid.txt
└── metadata/                    tabelas auxiliares do recorte anotado
```

Há 20 IDs anotados: `11, 12, 13, 14, 15, 19, 21, 22, 23, 24, 29, 30, 35,
36, 38, 47, 52, 54, 60, 82`.

### Labels de detecção

Cada linha de `labels/` segue o formato YOLO normalizado:

```text
class_id center_x center_y width height
```

As coordenadas e dimensões estão normalizadas pelo tamanho do frame.
As classes originais são `0 = normal`, `1 = cluster` e `2 = small_or_pinhead`.
A avaliação principal v3 reúne os indivíduos 0/2 e usa agrupamentos como
regiões ignoradas somente para previsões residuais sem indivíduo próximo.
A avaliação complementar reúne todos os objetos anotados; um cluster é um
objeto agrupamento, não uma célula. As linhas originais permanecem nos dados
e a análise morfológica YOLO preserva as três classes. Regra completa em
[Classes e agrupamentos](../metodologia/CLASSES_E_AGRUPAMENTOS.md).

### Labels com identidade

Cada linha de `labels_ftid/` acrescenta o ID persistente à esquerda:

```text
feature_track_id class_id center_x center_y width height
```

`feature_track_id` é uma string, não um inteiro sequencial. Ele deve ser
preservado literalmente ao construir o ground truth de tracking.

## Alinhamento correto de frames

Arquivos aparecem em ordem lexicográfica no sistema de arquivos — por exemplo,
`frame_10` pode surgir antes de `frame_2`. Portanto, imagem e label são
associados pelo inteiro `<n>` extraído do nome, nunca pela posição em uma lista.

Um arquivo de label existente e vazio representa um frame anotado sem objetos.
Um arquivo ausente representa anotação desconhecida e fica fora de treino e
métricas, salvo indicação explícita contrária no catálogo.

O vídeo 23 possui duas lacunas conhecidas:

| Intervalo inclusivo | Frames | Política |
|---|---:|---|
| 823–972 | 150 | excluir |
| 1084–1107 | 24 | excluir |

A fonte oficial dessas exceções é o catálogo de lacunas em `data/catalog/`.

## Splits e independência

| Papel | Vídeos |
|---|---|
| Treino | 11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82 |
| Validação | 14, 19, 36, 52 |
| Teste bloqueado | 24, 38, 47, 54 |

O split é por vídeo. Frames e clipes do mesmo vídeo nunca podem aparecer em
papéis diferentes. Os 502 clipes extraídos são derivados e não constituem 502
amostras independentes.

O planejamento de cinco folds ainda exige um desenho que separe seleção e
avaliação; aplicar a mesma configuração já escolhida a cinco grupos não
estabelece, por si só, previsões independentes da seleção. O piloto histórico
já expôs os vídeos do teste. Essa limitação permanece documentada no
[protocolo](../metodologia/PROTOCOLO.md). Os 65 vídeos sem tracking ficam
reservados para aplicação posterior ao congelamento, sem acurácia de IDs.

## Catálogo e validação

`data/catalog/` deve registrar, no mínimo, ID, caminho relativo, hash, presença
de tracking, split, fold, quantidade total/anotada de frames e intervalos
excluídos. Caminhos absolutos de uma máquina não pertencem ao catálogo
versionável.
