# Busca prospectiva do threshold fixo — 08/09/2026

[Protocolo](PROTOCOLO.md) · [Classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md)
· [Configuração registrada](../../configs/detection/threshold/search_v3.yaml)
· [Comandos oficiais](../../script/README.md#busca-threshold-v3)

## Pergunta, alcance e limite

Qual configuração de limiar fixo e morfologia apresenta o melhor F1 de
localização individual na amostra de treino definida antes da busca?
O resultado será uma lista de candidatos para refinamento. Não é estimativa
de generalização, promoção de detector ou comparação final do TCC.

Esta busca é hierárquica e limitada por orçamento. Não demonstra ótimo global
do método. O raio de avaliação, a política de agrupamentos e os vídeos não
serão ajustados pelos resultados. O histórico de exploração dos quatro vídeos
reservados ao teste continua registrado; novo planejamento não restaura cegueira.

A otimização de um critério medido em uma amostra finita pode produzir viés
de seleção. Separar seleção e avaliação e relatar todo o procedimento é
necessário para interpretar resultados. [Cawley e Talbot, JMLR, 2010](https://www.jmlr.org/papers/v11/cawley10a.html).

## Amostra compartilhada

Usar exclusivamente os vídeos de treino 11, 12, 13, 15, 21, 22, 23, 29,
30, 35, 60 e 82. Antes de abrir as fontes, conferir essa lista contra o
split vigente e contra a auditoria de geometria anterior.

1. Ordenar os índices dos quadros com arquivo GT existente. Conferir hashes
   e contagens contra a auditoria anterior; nenhuma linha malformada será
   omitida silenciosamente. GT existente e vazio é negativo explícito;
   GT ausente é desconhecido, fora da amostra.
2. Selecionar 48 índices por vídeo sobre essa lista ordenada. Para uma lista
   de tamanho N e k posições, usar `floor(j*(N-1)/(k-1))`, j de 0 a k−1.
   Exigir a quantidade planejada, sem devolver uma amostra menor silenciosamente.
3. Selecionar 12 posições da lista de 48 pela mesma regra para a busca grossa.
4. Para o benchmark, usar a posição `len(coarse)//2` da lista de 12: o elemento
   mediano superior. Os três universos ficam aninhados e seus índices exatos
   são gravados antes de executar qualquer candidato.

Essa distribuição é uniforme na ordem das anotações disponíveis. Com lacunas,
não corresponde a intervalos iguais no relógio. Os quadros do vídeo 23 sem
anotação continuam excluídos. Cada candidato recebe exatamente o mesmo universo.
Quadros adjacentes ou do mesmo vídeo não se tornam réplicas independentes.

Os pixels vêm da decodificação sequencial do MP4 canônico, desde o quadro 0,
sem seek por candidato. Os JPEGs fornecidos não substituem esses pixels,
pois podem conter diferenças de compressão. Guardar os 48 quadros selecionados
em um array BGR `uint8` por vídeo, sem nova compressão com perda, e consumir
o cache em modo somente leitura. “Sem perda” refere-se aos pixels já
decodificados, não ao vídeo microscópico antes de sua compressão original.

O cache registra índices, GT com IDs e precisão integral, hashes dos MP4,
labels e arrays, versão/backend do decodificador, código, ambiente, tempos e
memória. A identidade da amostra é obrigatória em cada execução; o hash dos
parâmetros, isoladamente, não identifica as imagens usadas.

## Espaço de busca grossa

| Parâmetro | Valores |
|---|---|
| Limiar de intensidade | 0, 16, 32, 48, 64, 80, 96, 112, 128, 144, 160, 176, 190, 192, 200, 208, 224, 240, 255 |
| Iterações de abertura | 0, 1, 2 |
| Iterações de fechamento | 0, 1, 2 |
| Kernel morfológico | Elíptico, 3 × 3, fixo |
| Área aceita do componente | 3 a 300 pixels, inclusive, fixa |
| Blur, inversão e adaptativo | Desativados: blur=1, invert=false, adaptive=false |

São **19 × 3 × 3 = 171 configurações**, cada uma em **12 × 12 = 144
quadros**, totalizando **24.624 avaliações configuração–quadro**. O algoritmo
é o threshold fixo existente, sem Otsu misturado à mesma busca.

A grade de intensidade cobre toda a escala de 8 bits em passos grossos,
incluindo extremos; 190 e 200 são âncoras históricas explicitamente registradas.
Elas recebem as mesmas condições de avaliação que os demais valores.
O limiar de intensidade separa pixels; ele é diferente do raio de 10 px que
associa centros na avaliação. No modo binário usado, intensidades maiores
que o limiar tornam-se primeiro plano. [Documentação OpenCV](https://docs.opencv.org/4.13.0/d7/d4d/tutorial_py_thresholding.html).

Os níveis morfológicos representam ausência da operação e uma ou duas iterações.
Kernel, polaridade, blur e faixa de área preservam a definição operacional
do baseline. Não são declarados ótimos. A área de pixels de um componente
segmentado não equivale à área de sua caixa nem à área da caixa manual.
Um estudo posterior desses parâmetros exigirá outra definição prospectiva.

## Custo, ordem e falhas

O benchmark executa todas as 171 configurações em um quadro por vídeo:
**2.052 avaliações**, sem produzir lista de melhores parâmetros. Usa a
mesma detecção, avaliação e exportação pretendidas para a busca grossa.
A preparação do cache é medida separadamente e não é repetida por candidato.

A projeção operacional para a busca grossa é:

`tempo_validacao_cache + 2 × (12/1) × tempo_loop_candidatos_benchmark`.

O laço inclui detecção, matching, exportação, metadados e progresso; o fator 2
é margem operacional, não intervalo de confiança ou garantia de pior caso.
Um quadro por vídeo não cobre a variabilidade temporal do custo. A busca
grossa só inicia se o benchmark terminar completo e a projeção for ≤1.200 s.

Tetos operacionais: benchmark 600 s, busca grossa 1.800 s, RSS amostrado
2.048 MiB, artefatos da bateria 2.048 MiB, cache 1.024 MiB e 2.000 previsões
por quadro. Os limites são verificados entre operações: não são interrupções
rígidas de uma chamada nativa. Exceder um teto interrompe a bateria e preserva
o material parcial; não se truncam detecções para obter métricas favoráveis.
Os tetos de tempo são decisões de orçamento, não tempos previstos de execução.

Usar uma thread OpenCV, execução serial e ordem de candidatos embaralhada
deterministicamente com seed 42. O método é determinístico; repetir seeds não
criaria novos vídeos ou réplicas estatísticas. Tempos são informativos nesta
triagem e não decidem empates. Comparações finais de custo exigem medição própria.

Qualquer erro de leitura, hash, dimensão, GT, detector ou universo invalida a
bateria para seleção. Não continuar omitindo o quadro e comparar denominadores
diferentes. Não produzir ranking de candidatos parcialmente avaliados. Uma
mudança no orçamento ou espaço exige novo registro antes da execução correspondente.

## Agregação e seleção

Para cada candidato, somar TP/FP/FN nos 12 quadros de cada vídeo e calcular o
F1 daquele vídeo. O critério principal é a média dos 12 F1, com pesos iguais.
Não usar F1 dos totais de todos os vídeos ou média de F1 por quadro como substitutos.

Ordenar por F1 macro decrescente; em igualdade, recall macro decrescente,
MAE de contagem avaliada macro crescente e identificador crescente. O último
critério apenas garante ordem determinística, sem interpretação de superioridade.
Usar precisão integral para ordenar, sem arredondamento de apresentação.

Reportar também precisão, erros de centro, contagens brutas/avaliadas/ignoradas,
avaliação secundária de todos os objetos e sensibilidades de 15/20 px. Os
quadros anotados formam o denominador fixo da contagem. Não escolher o raio
que produz a classificação mais favorável e não usar os 12 vídeos como se
as 144 observações fossem 144 amostras independentes.

Somente uma busca grossa completa pode fornecer os cinco candidatos para
refinamento. Preservar a tabela de todos os 171 candidatos e os resultados
por vídeo; não salvar somente os vencedores.

## Refinamento e etapas posteriores

O refinamento previsto percorre todos os inteiros de T−15 até T+15 de cada
um dos cinco pais, limitados a 0–255, mantendo sua morfologia e a área 3–300.
Deduplicar parâmetros idênticos. Limite: 155 candidatos × 576 quadros =
89.280 avaliações, nos mesmos 48 quadros por vídeo já manifestados.

Esse desenho melhora a resolução do limiar em regiões selecionadas pelo
treino; não promete explorar todos os parâmetros conjuntamente. O teto
registrado é 7.200 s, mas a execução exigirá nova projeção de custo. O executor
deste marco oferece somente preparação, benchmark e busca grossa.

Depois de refinamento completo, duas finalistas poderão seguir para os
quatro vídeos completos de validação. Congelamento, avaliação reservada e
folds permanecem etapas posteriores, com a limitação histórica do teste
explicitada. A hipótese sobre fluxo óptico e predição não é testada nesta busca.

## Estado deste registro

Plano e executores em preparação, antes da formação do cache e de qualquer
resultado de benchmark ou busca grossa. Os resultados e commits de execução
serão registrados abaixo após as verificações correspondentes.
