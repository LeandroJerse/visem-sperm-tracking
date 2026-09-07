# Catálogo de algoritmos

Escolha a tarefa abaixo e abra a ficha do método. No início de cada ficha,
**Onde encontrar** liga diretamente a implementação Python, os parâmetros,
os comandos oficiais e as pastas de ensaios e resultados que já existem.

| Tarefa | Fichas dos métodos | Código | Parâmetros | Comandos |
|---|---|---|---|---|
| Detecção | [Comparar detectores](deteccao/README.md) | [Mapa de `src/detection`](../../src/detection/README.md) | [Configurações de detecção](../../configs/detection/) | [Executar detecção](../../script/README.md#1-detecção) |
| Tracking | [Comparar rastreadores](tracking/README.md) | [Mapa de `src/tracking`](../../src/tracking/README.md) | [Configurações de tracking](../../configs/tracking/) | [Executar tracking](../../script/README.md#2-tracking) |
| Fluxo óptico | [Comparar estimadores](fluxo/README.md) | [Mapa de `src/flow`](../../src/flow/README.md) | [Configurações de fluxo](../../configs/flow/) | [Executar fluxo](../../script/README.md#3-movimento-aparente-por-fluxo) |
| Predição | [Comparar preditores](predicao/README.md) | [Mapa de `src/prediction`](../../src/prediction/README.md) | [Configurações de predição](../../configs/prediction/) | [Executar predição](../../script/README.md#4-predição) |

Para retomar o threshold já usado, abra a [ficha do threshold fixo](deteccao/threshold_fixo.md).
A [bancada frame a frame](../../script/detection/test/threshold/README.md)
explica a inspeção visual de uma imagem. Os
[testes automatizados](../../tests/README.md) verificam o código; os
[ensaios experimentais](../../data/tests/README.md) guardam as saídas das execuções.

Um arquivo curto pode reutilizar uma classe de outro arquivo. As fichas apontam
também para essa implementação compartilhada quando necessário, como na LSTM
com fluxo e no rastreador Húngaro. Otsu e threshold adaptativo usam a mesma
classe do threshold fixo, com configurações e identidades científicas distintas.

As áreas de resultados podem conter somente sua documentação. Uma pasta ou
implementação existente não significa que houve validação experimental.
Consulte a [matriz de experimentos](../projeto/MATRIZ_EXPERIMENTOS.md)
para o estado de cada método. O catálogo não promove resultados.

Cada método e cada variante híbrida têm sua própria ficha. O
[protocolo comum dos preditores com fluxo](predicao/hibridos_com_fluxo.md)
reúne as ablações compartilhadas; não representa outro algoritmo.

## Conteúdo das fichas

Toda ficha deve registrar:

1. ideia e hipótese;
2. entrada e saída;
3. parâmetros e espaço de busca;
4. adaptações específicas ao VISEM;
5. pontos fortes e pontos fracos;
6. falhas visuais típicas;
7. métricas por vídeo e incerteza;
8. mediana/p95 de tempo, RAM/VRAM e custo de treino;
9. esforço de implementação e dependências;
10. configuração congelada, hash e decisão de promoção.

Os READMEs de cada módulo são o índice comparativo; os arquivos individuais são
a evidência usada para escrever os capítulos da monografia.

## Escopo executável desta etapa

| Módulo | Baselines puros | Moderno/opcional | Híbridos explícitos |
|---|---|---|---|
| Detecção | threshold fixo, Otsu, adaptativo, Blob, MOG2, KNN, Watershed | YOLO | CLAHE + correção de fundo + threshold |
| Tracking | centroide guloso, Húngaro, SORT | ByteTrack-style | Adaptive Flow-SORT |
| Fluxo | Lucas–Kanade, Farneback, Horn–Schunck | RAFT | fluxo robusto com consistência, compensação e refino opcional |
| Predição | persistência, velocidade constante, Kalman, partículas | LSTM | versões flow-aware de velocidade, Kalman, partículas e LSTM |

DeepSORT/BoT-SORT, U-Net, PWC-Net/VideoFlow, GRU e Transformer continuam como
backlog opcional. Eles não entram silenciosamente na comparação principal antes
de todos os métodos acima estarem congelados; adicionar largura agora reduziria
a profundidade dos testes por vídeo.
