# Bases preservadas

As duas bases foram movidas de `data/sources/` para esta pasta. A árvore
interna e os arquivos existentes foram preservados.

| Local | Conteúdo |
|---|---|
| `visem/videos/` | 85 vídeos AVI originais |
| `visem/clinical/` | Tabelas clínicas originais |
| `visem/metadata/` | Descrição e catálogo dos vídeos |
| `visem_tracking/dataset/Train/<video_id>/` | 20 vídeos MP4 e seus arquivos associados |
| `visem_tracking/dataset/Train/<video_id>/images/` | Imagens JPEG e caches NPY existentes |
| `visem_tracking/dataset/Train/<video_id>/labels/` | Anotações de detecção |
| `visem_tracking/dataset/Train/<video_id>/labels_ftid/` | Anotações com identidade persistente |
| `visem_tracking/metadata/` | Tabelas auxiliares do conjunto anotado |
| `manifestos_historicos/` | Cópia dos inventários, divisão anterior de vídeos e lacunas |

## Formato das anotações

Em `labels/`, cada linha tem:

```text
class_id center_x center_y width height
```

Em `labels_ftid/`, cada linha tem:

```text
feature_track_id class_id center_x center_y width height
```

As posições e dimensões são normalizadas pelo tamanho da imagem. As classes
originais são `0 = normal`, `1 = cluster` e `2 = small_or_pinhead`.
O identificador persistente deve ser preservado como texto.

Imagem e anotação se relacionam pelo número do quadro no nome do arquivo.
Anotação ausente é diferente de arquivo de anotação existente e vazio.
Há 174 lacunas conhecidas no vídeo 23: quadros 823–972 e 1084–1107,
com extremos incluídos. O registro está em
`manifestos_historicos/annotation_gaps.csv`.

## Limites deste reinício

Os manifestos e o `README.md` original foram preservados como registros da
organização anterior. Alguns caminhos e políticas neles descritos são
históricos. A nova metodologia de comparação ainda será definida com o
pesquisador; este reinício não executa nem escolhe métodos.

Os 29.196 caches NPY existentes nas fontes também foram preservados. Nenhuma
limpeza ou nova preparação de dados foi realizada.

O YOLO treinado no piloto anterior está preservado com sua run em
`../../my_tcc_historico_20260914/data/tests/detection/yolo/pilot_100_epochs__cfglegacy/training/visem_full/`.
