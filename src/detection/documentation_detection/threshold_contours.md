# Threshold + Contours

**Arquivo:** `detect_threshold_contours.py` · **classe:** `ThresholdContourDetector` · **`--method threshold`**

## Ideia

Baseline mais simples. Cabeças de espermatozoides aparecem como pequenos blobs
**escuros** sobre fundo claro (microscopia de contraste de fase). Pipeline:

1. converter para tons de cinza;
2. desfoque gaussiano (reduz ruído);
3. limiarização **invertida** (objetos escuros → branco): Otsu (global) ou
   adaptativa;
4. abertura morfológica (remove ruído pontual);
5. `findContours` (externos) → uma bounding box por contorno;
6. filtro por área (`min_area`, `max_area`) para descartar ruído e detritos grandes.

## Parâmetros-chave

| parâmetro | default | efeito |
|---|---|---|
| `min_area`, `max_area` | 3, 300 | faixa de área (px²) aceita por objeto |
| `blur` | 3 | tamanho do kernel gaussiano (ímpar) |
| `invert` | `True` | objetos escuros sobre fundo claro |
| `adaptive` | `False` | usa limiar adaptativo em vez de Otsu |
| `adaptive_block`, `adaptive_c` | 21, 5 | parâmetros do limiar adaptativo |
| `morph_kernel` | 3 | tamanho do elemento estruturante |

## Pontos fortes / fracos

- **Forte:** rápido, sem treino, ótimo ponto de partida e referência.
- **Fraco:** sensível a iluminação não uniforme (Otsu global falha em gradientes
  → usar `adaptive=True`); funde células grudadas em uma só caixa (ver
  [watershed](watershed.md)); não distingue classes.

## Ajuste no contexto

Nos vídeos do VISEM original os defaults sub-detectam (iluminação/contraste
diferentes do alvo). Ajustar `min_area`/`max_area` ao tamanho real das cabeças e
testar `adaptive=True`. Calibrar contra o ground truth do VISEM-Tracking
(`--gt-dir`) comparando precision/recall por área.
