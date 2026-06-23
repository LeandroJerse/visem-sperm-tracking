# Background Subtraction (movimento)

**Arquivo:** `detect_bgsub.py` · **classe:** `BackgroundSubtractionDetector` · **`--method bgsub`**

## Ideia

Espermatozoides **se movem**; o fundo é quase estático. Um modelo de fundo
adaptativo (MOG2 ou KNN) separa o primeiro plano em movimento. Pipeline:

1. `subtractor.apply(frame)` → máscara de primeiro plano;
2. limiar para manter só foreground duro (descarta sombras);
3. abertura morfológica;
4. `findContours` → caixas, filtradas por área.

É **stateful**: o modelo de fundo aprende ao longo do vídeo. `reset()` recria o
subtrator entre vídeos (o `runner` chama automaticamente).

## Parâmetros-chave

| parâmetro | default | efeito |
|---|---|---|
| `method` | `"MOG2"` | `MOG2` ou `KNN` |
| `min_area`, `max_area` | 3, 400 | faixa de área (px²) |
| `history` | 200 | nº de frames na memória do modelo |
| `var_threshold` | 16 | sensibilidade (MOG2) |
| `dist2_threshold` | 400 | sensibilidade (KNN) |
| `detect_shadows` | `False` | detectar sombras (descartadas no limiar) |

## Pontos fortes / fracos

- **Forte:** ignora detritos **estáticos** (vantagem real neste dataset, que tem
  muito debris parado); complementar aos métodos por aparência.
- **Fraco:** perde células **paradas/lentas**; sensível a *drift* da câmera
  (vários vídeos do VISEM têm "drift"/"minor drift" no nome → fundo inteiro vira
  movimento); precisa de alguns frames para estabilizar o modelo.

## Ajuste no contexto

Em vídeos com drift, aumentar `var_threshold`/`history` ou pré-estabilizar.
Combinar com threshold/blob (movimento ∩ aparência) reduz falsos positivos.
Calibrar com `--gt-dir`.
