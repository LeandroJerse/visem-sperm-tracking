# Threshold adaptativo gaussiano

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/adaptive_threshold/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

Usa o registro `threshold` com `adaptive: true`; o identificador científico das saídas é `adaptive_threshold`. A implementação é compartilhada com os limiares fixo e Otsu.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

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
