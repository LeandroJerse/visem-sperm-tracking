# Blob Detection

**Arquivo:** `detect_blob.py` · **classe:** `BlobDetector` · **`--method blob`**

## Ideia

Usa `cv2.SimpleBlobDetector`, projetado para objetos pequenos e aproximadamente
circulares — adequado a cabeças de espermatozoides. Internamente limiariza a
imagem em vários níveis e agrupa regiões estáveis, filtrando por cor, área e
(opcionalmente) circularidade/convexidade. Retorna **centroide + diâmetro**, que
mapeamos para uma caixa quadrada.

## Parâmetros-chave

| parâmetro | default | efeito |
|---|---|---|
| `min_area`, `max_area` | 2, 200 | faixa de área (px²) |
| `min_threshold`, `max_threshold` | 10, 200 | faixa de limiares varridos |
| `threshold_step` | 10 | passo entre limiares |
| `dark` | `True` | detecta blobs escuros (`blobColor=0`) |
| `min_circularity` | `None` | se definido, exige circularidade mínima |
| `min_convexity` | `None` | se definido, exige convexidade mínima |

## Pontos fortes / fracos

- **Forte:** robusto para objetos pontuais; a varredura multi-limiar tolera
  variação de contraste melhor que um único Otsu.
- **Fraco:** com defaults frouxos **super-detecta** (cada textura/ruído vira
  blob — observado: milhares por frame no VISEM original); precisa apertar área e
  ativar filtros de forma; assume formato circular (ruim para caudas/clusters).

## Ajuste no contexto

Apertar `min_area`/`max_area` à cabeça real e ligar `min_circularity` (~0.6) e
`min_convexity` (~0.8) para cortar ruído. Calibrar com `--gt-dir` do
VISEM-Tracking.
