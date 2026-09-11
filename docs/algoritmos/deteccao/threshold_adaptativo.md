# Threshold adaptativo gaussiano

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [Grade comparativa executada](../../../configs/detection/comparison/classical_v1_operational_v2.yaml) · [YAML geral de desenvolvimento](../../../configs/detection/adaptive_threshold/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | [Runs do método](../../../data/tests/detection/adaptive_threshold/) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Usa o registro `threshold` com `adaptive: true`; o identificador científico das saídas é `adaptive_threshold`. A implementação é compartilhada com os limiares fixo e Otsu.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Resultado de treino conferido — 11/09/2026

Foram 18 configurações nos mesmos 576 quadros dos 12 treinos, sob v3.
`adaptive_threshold_v1_002` foi a melhor desta grade: bloco 15, C=−5,
uma abertura e um fechamento, kernel 3, blur 1, objetos claros, área 3–300.
F1 macro a 10 px **0,148689**, precisão 0,083095, recall 0,929020;
F1 a 15/20 px 0,152374/0,154454. Foram 1.267 previsões ignoradas a 10 px,
após a proteção dos indivíduos. Detecção média em cache: 3,512 ms/quadro.

O recall alto vem com precisão muito baixa: localizar muitos indivíduos
acompanhados de muitos falsos positivos não produz bom F1. O F1 por vídeo
varia de 0,036974 no 23 a 0,355305 no 13. Não concluir que nenhuma
configuração adaptativa funcionaria: a conclusão cobre a grade registrada.

Uma configuração diferente, `adaptive_threshold_v1_004`, excedeu a guarda
de 2.000 previsões no smoke v1 e interrompeu o lote. A revisão v2 mudou
somente a guarda operacional e sua linhagem para permitir medir a
superdetecção; a run completa conservou candidatos e previsões. A falha
original permanece preservada, sem contagem exata acima de 2.000 registrada.

Pais para refinamento: `adaptive_threshold_v1_002` e
`adaptive_threshold_v1_008`. A vizinhança prospectiva varia bloco ±8,
C ±2 ou abertura ±1, um parâmetro por vez; novo YAML/executor e validação
completa são próximos passos, sem promoção agora.
[Resumo por vídeo](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json)
e [protocolo, falha preservada, manifesto e QA](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md).

## Ideia

Cada pixel recebe um limiar calculado de sua vizinhança ponderada, menos uma
constante `C`. A máscara passa por morfologia e componentes conexos.

## Parâmetros a estudar

`adaptive_block` ímpar, `adaptive_c`, polaridade, blur, kernel,
abertura/fechamento e filtros de área.

## Pontos fortes

- acomoda gradientes de iluminação e regiões com fundo diferente;
- continua sem treino e com baixo custo;
- explicita o compromisso entre escala local (`block`) e sensibilidade (`C`).

## Pontos fracos

- amplifica textura e ruído local, criando muitos componentes;
- janela pequena fragmenta objetos; janela grande se aproxima do caso global;
- é sensível à resolução e exige calibração de `block`/`C`;
- pode marcar halos e bordas do microscópio como células.

## Adaptação e validação

O tamanho do bloco deve ser maior que uma cabeça típica e menor que a escala do
gradiente de fundo. Avaliar count bias e precision junto ao F1; não usar apenas
um frame central quando a iluminação muda ao longo do vídeo.
