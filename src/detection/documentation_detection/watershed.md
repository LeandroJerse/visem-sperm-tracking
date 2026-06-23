# Watershed

**Arquivo:** `detect_watershed.py` · **classe:** `WatershedDetector` · **`--method watershed`**

## Ideia

Técnica intermediária para **separar objetos grudados** (a classe `cluster`).
Trata a imagem como um relevo e "inunda" a partir de marcadores. Pipeline:

1. máscara de foreground (Otsu invertido) + abertura morfológica;
2. `distanceTransform` → distância ao fundo (picos = centros de células);
3. limiar da distância (`dist_ratio` × máximo) → **sementes** de foreground;
4. banda "desconhecida" = fundo dilatado − sementes;
5. `connectedComponents` rotula as sementes; `cv2.watershed` propaga os rótulos;
6. uma bounding box por região rotulada (filtro por área).

## Parâmetros-chave

| parâmetro | default | efeito |
|---|---|---|
| `min_area`, `max_area` | 3, 600 | faixa de área (px²) por região |
| `blur` | 3 | desfoque antes do limiar (ímpar) |
| `invert` | `True` | objetos escuros sobre fundo claro |
| `dist_ratio` | 0.4 | fração do pico de distância p/ semear foreground |
| `morph_kernel` | 3 | elemento estruturante |

## Pontos fortes / fracos

- **Forte:** divide aglomerados que o threshold simples funde numa caixa só.
- **Fraco:** depende fortemente do `dist_ratio` e da qualidade da máscara
  inicial; se o Otsu satura (foreground quase inteiro), degenera para ~1 região
  por frame (observado nos defaults sobre o VISEM original); custo maior.

## Ajuste no contexto

Pré-condição é uma máscara binária **boa** — herda os ajustes do
[threshold](threshold_contours.md). Variar `dist_ratio` (0.3–0.6): menor separa
mais (risco de fragmentar), maior funde mais. Usar principalmente onde há
clusters; calibrar com `--gt-dir` (classe `cluster`).
