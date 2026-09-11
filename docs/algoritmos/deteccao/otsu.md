# Otsu

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/otsu/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | Caminho local `data/tests/detection/otsu/` · [Guia dos ensaios](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Usa o registro `threshold` com `threshold_value: null`; o identificador científico das saídas é `otsu`. A implementação é compartilhada com os limiares fixo e adaptativo.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Resultado de treino conferido — 11/09/2026

Quatro configurações de abertura/fechamento foram comparadas nos mesmos 576
quadros dos 12 treinos, sob v3. A melhor desta grade, `otsu_v1_004`, usa
uma abertura, dois fechamentos, kernel 3, blur 1, objetos claros e área
3–300. F1 macro a 10 px **0,546675**, precisão 0,488463 e recall 0,699844;
F1 a 15/20 px 0,557180/0,562437. Foram 266 previsões ignoradas a 10 px,
após a proteção de indivíduos. Detecção média em cache: 2,172 ms/quadro.

O F1 varia de 0,062652 no vídeo 23 a 0,933432 no 13; a média menor que
T218 não significa que a referência prevaleça em todo vídeo. Essa variação
descritiva justifica analisar iluminação, densidade e falhas visuais, sem
atribuir uma causa apenas pelos números. Os pilotos anteriores continuam
históricos; os resultados acima pertencem à busca v3 em `2547109`.

Pais para refinamento: `otsu_v1_004` e `otsu_v1_003`. A vizinhança
prospectiva altera abertura ou fechamento em uma unidade por vez; o novo
YAML/executor e a validação completa continuam pendentes. Não há promoção.
[Valores por vídeo e sensibilidades](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).

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
