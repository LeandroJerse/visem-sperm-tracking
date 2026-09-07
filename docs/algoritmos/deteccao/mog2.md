# Background subtraction MOG2

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [background_subtraction.py](../../../src/detection/classical/background_subtraction.py) — `MOG2Detector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/mog2/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) · [Inspeção temporal por clipes](../../../script/detection/test/background_subtraction/README.md) |
| Ensaios e resultados | Caminho local `data/tests/detection/mog2/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

MOG2 e KNN compartilham `BackgroundSubtractionDetector`, mas usam classes e configurações próprias. O alias genérico `bgsub` não substitui o nome científico do método.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Modela cada pixel por uma mistura adaptativa de Gaussianas. Pixels incompatíveis
com o fundo aprendido viram movimento; a máscara é aberta e seus contornos
geram detecções.

## Parâmetros a estudar

`history`, `var_threshold`, sombra, kernel, área e número de frames de
aquecimento. O estado deve ser reiniciado entre vídeos.

## Pontos fortes

- explora o tempo e pode ignorar detritos realmente estáticos;
- adapta-se gradualmente a variações de fundo;
- é clássico, disponível no OpenCV e relativamente eficiente.

## Pontos fracos

- não faz sentido avaliá-lo em frames independentes;
- durante aquecimento tende a marcar grande parte da imagem;
- células lentas podem ser absorvidas pelo fundo; movimento de câmera gera FPs;
- produz fantasmas e score binário sem confiança calibrada.

## Adaptação e validação

Usar clipes com pelo menos 100 frames de aquecimento, excluir esse transiente das
métricas e nunca carregar estado de um vídeo ao seguinte. Reportar também falhas
por deriva e por células temporariamente imóveis.
