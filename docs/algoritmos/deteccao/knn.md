# Background subtraction KNN

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [background_subtraction.py](../../../src/detection/classical/background_subtraction.py) — `KNNDetector` |
| Configuração | [YAML de desenvolvimento](../../../configs/detection/knn/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#outros-detectores) · [Inspeção temporal por clipes](../../../script/detection/test/background_subtraction/README.md) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/detection/README.md) · [Área de resultados promovidos](../../../data/results/detection/README.md) |

KNN e MOG2 compartilham `BackgroundSubtractionDetector`, mas usam classes e configurações próprias. O alias genérico `bgsub` não substitui o nome científico do método.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Classifica o pixel comparando sua observação recente a amostras do histórico,
sem assumir uma mistura paramétrica fixa. A máscara temporal recebe a mesma
pós-filtragem do MOG2.

## Parâmetros a estudar

`history`, `dist2_threshold`, sombra, kernel, área e aquecimento. Reinicialização
por vídeo é obrigatória.

## Pontos fortes

- fundo não paramétrico e flexível para distribuições complexas;
- pode lidar melhor que MOG2 com alguns fundos multimodais;
- não exige labels nem treinamento offline.

## Pontos fracos

- custo e memória maiores que um threshold simples;
- forte dependência do histórico e do limiar de distância;
- sofre com câmera/fundo em movimento, células imóveis e fantasmas;
- também não fornece scores úteis para ByteTrack.

## Adaptação e validação

Aplicar exatamente o mesmo protocolo temporal do MOG2, incluindo 100 frames de
aquecimento e reset. Comparações em frame único são inválidas e devem ser
recusadas pelo executor ou marcadas como smoke visual, nunca como métrica final.
