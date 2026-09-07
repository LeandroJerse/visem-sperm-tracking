# Otsu

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/otsu/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/otsu/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Usa o registro `threshold` com `threshold_value: null`; o identificador científico das saídas é `otsu`. A implementação é compartilhada com os limiares fixo e adaptativo.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

O método escolhe em cada frame o limiar global que minimiza a variância dentro
das duas classes do histograma. Depois usa a mesma morfologia e componentes
conexos do threshold fixo.

## Parâmetros a estudar

Polaridade, blur, kernel, abertura/fechamento e área. Não há
`threshold_value`: o valor é recalculado em todo frame.

## Pontos fortes

- elimina a escolha manual de um valor global;
- é determinístico, rápido e não exige treino;
- pode acompanhar mudanças globais moderadas entre vídeos ou frames.

## Pontos fracos

- pressupõe separação útil do histograma em duas populações;
- fundo dominante, baixo contraste e detritos deslocam o limiar;
- no piloto VISEM superdetectou fortemente em vários vídeos;
- continua sem resolver iluminação espacialmente não uniforme.

## Adaptação e validação

Usar a mesma pós-filtragem de área dos demais baselines e reportar o limiar
escolhido por frame para explicar falhas. Ele não deve ser promovido só por alto
recall se precision e count bias indicarem superdetecção.
