# Tolerância espacial para avaliar a detecção

[Documentação](../README.md) · [Comandos oficiais](../../script/README.md#geometria-das-anotacoes) · [Organização dos artefatos](../../data/derived/detection/annotation_audit/README.md)

Estudo descritivo concluído em 07/09/2026, restrito às anotações de treino.
O pesquisador aprovou priorizar a localização dos centros e, posteriormente,
**aprovou 10 px como raio principal, com 15 e 20 px de sensibilidade obrigatória**.
A decisão vale para todos os detectores na resolução original de 640 × 480 px.
O estudo descritivo não executou detectores; suas fontes e resultados
permanecem preservados durante as etapas posteriores.

## Pergunta e alcance

A tolerância espacial é a distância máxima entre um centro previsto e o centro
de uma caixa de referência para permitir um pareamento. Ela é expressa em
pixels da imagem original, diferente do limiar de intensidade do detector
(por exemplo, T200). O pareamento final deve ser um-para-um.

Examinamos tamanhos das caixas e separação dos centros para interpretar os
raios de 10, 15 e 20 px já presentes na discussão. Nenhum detector foi executado
e nenhum F1 foi usado para escolher a proposta. Geometria não revela, sozinha,
o erro dos anotadores nem determina um raio ótimo.

## Fontes e verificações locais

Foram lidos somente os vídeos de treino registrados em
`configs/protocol/splits.yaml`: **11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60 e 82**.
O executor verifica essa lista e a disjunção dos splits antes de acessar fontes.
Não abre arquivos-fonte de validação ou teste. Lê anotações e cabeçalhos JPEG;
o conteúdo completo dos arquivos usados é lido para calcular SHA-256. Não
decodifica os pixels nem abre os MP4.

| Conferência | Resultado |
|---|---:|
| Quadros indexados | 17.640 |
| Quadros com anotação | 17.466 |
| Quadros sem anotação, excluídos como `unlabeled` | 174, todos no vídeo 23 |
| Arquivos de anotação existentes e vazios | 0 |
| Observações anotadas válidas | 368.487 |
| Linhas inválidas no formato primário | 0 |
| Quadros com divergência de classe/coordenadas entre os formatos | 0 |
| Resolução dos quadros anotados | 640 × 480 px |

Uma observação é uma anotação em um quadro. A mesma identidade reaparece no
tempo: **368.487 observações não são 368.487 células distintas nem amostras
estatísticas independentes**.

O formato primário é `labels_ftid`: seis campos, com ID textual no início.
Foram verificados número de campos, classe, coordenadas finitas e normalizadas,
largura/altura positivas, ID único dentro do quadro e limites da caixa
(tolerância numérica de 10⁻⁹ px). Os arquivos `labels` foram comparados por
classe/coordenadas, sem depender da ordem das linhas, com tolerância absoluta
de 10⁻¹² nos valores normalizados. Não houve correção, recorte ou exclusão de
linhas geométricas nesta execução.

`anomalies.csv` também lista **17.466 arquivos auxiliares `.npy`** como
`unexpected_filename`: o indexador encontrou essa extensão na pasta de imagens
e a ignorou, pois usa JPEG. Seus conteúdos não foram abertos. Essas entradas
não representam coordenadas inválidas, falhas de anotação ou justificativa
para apagar arquivos. As outras 174 entradas registram as lacunas conhecidas.

Esta conferência não mede completude do GT, correção biológica das classes,
consistência temporal dos IDs ou alinhamento JPEG–MP4 de toda a coleção.

## Classes e unidade do resumo

| Grupo | Observações | Vídeos com presença |
|---|---:|---:|
| Classe 0 (`normal`/`sperm`, sem significado de diagnóstico) | 347.847 | 12 |
| Classe 1 (`cluster`, agrupamento) | 5.413 | 4 |
| Classe 2 (`small_or_pinhead`) | 15.227 | 8 |
| Classes 0 e 2 (`cells0_2`) | 363.074 | 12 |
| Todas as classes (`all`) | 368.487 | 12 |

Cada classe foi analisada separadamente. `cells0_2` permite descrever caixas
de células sem confundi-las com caixas de agrupamentos. `all` corresponde ao
agrupamento binário de objetos do protocolo existente. Essa descrição não
decide se os agrupamentos devem participar da nova avaliação; um agrupamento
não equivale a uma cabeça individual.

Dentro de cada vídeo e grupo, calculamos quantis de tamanho e distância ao
vizinho. O resumo de tamanho é a **mediana das medianas dos vídeos**. Para
percentuais, calculamos primeiro a fração por vídeo e depois a média com peso
igual. Vídeos sem aquele grupo ficam fora de seu resumo, sem receber zero.
Não calculamos intervalos de confiança tratando quadros como independentes.

## Tamanhos e proximidade

Nas classes 0 e 2, a mediana das medianas de largura é **21,0 px**; de altura,
**19,5 px**. As duas estatísticas são marginais: não descrevem necessariamente
uma mesma caixa. A mediana das medianas da distância centro–canto é **14,60 px**.
São dimensões das caixas anotadas, não medidas anatômicas ou de incerteza.

| Vídeo | Mediana largura (px) | Mediana altura (px) | Mediana centro–canto (px) | Mediana distância ao vizinho (px) |
|---|---:|---:|---:|---:|
| 11 | 17,00 | 18,00 | 12,38 | 47,31 |
| 12 | 22,86 | 23,00 | 15,91 | 56,49 |
| 13 | 24,00 | 22,00 | 16,26 | 42,55 |
| 15 | 17,00 | 16,00 | 11,72 | 63,20 |
| 21 | 21,00 | 20,00 | 14,60 | 55,30 |
| 22 | 17,33 | 16,00 | 11,72 | 119,69 |
| 23 | 18,00 | 17,00 | 12,38 | 238,76 |
| 29 | 21,00 | 18,35 | 14,60 | 209,40 |
| 30 | 22,00 | 20,00 | 14,99 | 78,50 |
| 35 | 30,00 | 31,00 | 21,22 | 45,21 |
| 60 | 27,00 | 28,00 | 19,14 | 73,36 |
| 82 | 19,00 | 19,00 | 13,27 | 45,94 |

Tabela restrita a `cells0_2`. O vizinho é outra anotação do mesmo grupo no
mesmo quadro, nunca de outro instante. Quadros com um único objeto fornecem
distância infinita: entram no denominador das frações, mas não nos quantis
de distâncias finitas. Os CSVs registram ambos os denominadores.

## O que muda com o raio

Para cada anotação i, sejam dᵢ a distância ao vizinho mais próximo no mesmo
quadro/grupo e hᵢ = √(largura² + altura²)/2 a distância centro–canto.

- **dᵢ ≤ r:** outro centro anotado está dentro ou na borda da região de aceitação.
- **dᵢ < 2r:** duas regiões de aceitação têm sobreposição de área positiva.
  Uma previsão nessa interseção poderia ser elegível para ambas; o pareamento
  um-para-um ainda precisa escolher sua associação. A tangência em 2r não é contada.
- **r > hᵢ:** o raio admite posições mais distantes do centro do que qualquer
  canto da caixa. O caso inverso não garante que todo o círculo caiba na caixa.

**Nenhuma dessas medidas é uma taxa de erro observada de detecção ou tracking.**
Elas também não implicam que todo par geometricamente elegível será escolhido.

Médias com peso igual dos 12 vídeos, incluindo todas as classes (`all`):

| Raio | Outro centro a ≤ r | Regiões sobrepostas, d < 2r | Raio maior que centro–canto |
|---|---:|---:|---:|
| 10 px | 1,85% | 7,38% | 4,63% |
| 15 px | 4,41% | 16,75% | 56,82% |
| 20 px | 7,38% | 26,84% | 87,19% |

Nas classes 0 e 2, sem agrupamentos, a mesma leitura é:

| Raio | Outro centro a ≤ r | Regiões sobrepostas, d < 2r | Raio maior que centro–canto |
|---|---:|---:|---:|
| 10 px | 1,72% | 6,80% | 4,72% |
| 15 px | 3,85% | 14,59% | 58,10% |
| 20 px | 6,80% | 24,77% | 88,92% |

A heterogeneidade entre vídeos permanece relevante. Em `all`, a sobreposição
varia de 0 a 19,07% para 10 px, de 0 a 29,81% para 15 px e de 0,93 a 45,16%
para 20 px. São faixas observadas, não intervalos de confiança. A região circular
de 15 px tem 2,25 vezes a área da de 10 px; a de 20 px tem quatro vezes essa área.

## Confronto com fontes primárias

- **VISEM-Tracking, Thambawita et al. (2023):** Methods e Technical Validation,
  Tabela 4. Descreve caixas verificadas por biólogos e avaliação de detecção com
  mAP0.5/mAP0.5:0.95. Não fornece uma justificativa para adotar 15 px como padrão
  de avaliação por centros. Não encontramos uma distribuição quantitativa de
  divergências entre anotadores que permitisse derivar esse raio.
  [Artigo do dataset](https://www.nature.com/articles/s41597-023-02173-4).
- **Zhang et al. (2024):** Evaluation Metrics, equações 24–27. Avalia detecção
  por precisão, recall e mAP com critérios de IoU. Componentes de distância na
  regressão das caixas não equivalem a um corte de 15 px na avaliação.
  [Sperm YOLOv8E-TrackEVD](https://pmc.ncbi.nlm.nih.gov/articles/PMC11175353/).
- **Hart et al. (2026):** Experiment 3: Bounding Boxes vs. Centroids, Figura 4,
  e Unique considerations for evaluating sperm detection. Discute representação
  pontual e associação com corte de distância. Mostra diferenças entre centros
  de caixas VISEM e centros estimados por Trackpy. Isso apoia tratar o centro
  da caixa como referência operacional, sem identificá-lo com o centro físico
  exato da cabeça. O texto principal não estabelece um raio transferível ao
  nosso estudo; o apêndice e o código não foram verificados nesta consulta.
  Não substituímos o GT por estimativas algorítmicas.
  [A framework for evaluating predicted sperm trajectories in crowded microscopy videos](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013955).

## Decisão aprovada pelo pesquisador — 07/09/2026

**Adotar 10 px como tolerância principal da nova avaliação, com 15 e 20 px
como análises de sensibilidade obrigatórias, iguais para todos os detectores.**

A justificativa é operacional: a prioridade aprovada é localizar centros;
10 px exige localização mais precisa, situa-se aproximadamente na metade
das dimensões marginais típicas das caixas de células e oferece uma região
menor de associação. Os dados descrevem o custo geométrico de relaxar essa
exigência. Eles não provam que 10 px seja ótimo, que 15 px seja incorreto,
ou que o ruído de anotação seja inferior a 10 px. Um raio menor pode penalizar
desvios entre centro visual da cabeça e centro geométrico da caixa.

Escolher sempre o menor raio por produzir menos sobreposição levaria a zero
e não resolveria a avaliação. Por isso a decisão depende da precisão de
localização que queremos exigir e da transparência da análise de sensibilidade,
não de minimizar estes percentuais ou maximizar o F1.

A definição é igual para todos os detectores, em coordenadas da resolução
original de 640 × 480 px, desfazendo redimensionamento e padding antes de
calcular as distâncias. O centro da caixa é uma referência geométrica
operacional, não um ponto anatômico exato da cabeça.
O erro de localização dos pares válidos deverá acompanhar precisão, recall
e F1; sendo condicionado aos pares aceitos, ele não substitui contabilizar FP/FN.
Os três raios serão reportados mesmo se mudarem a ordenação dos métodos.

A decisão sobre o raio recebeu o identificador **`center_distance_v2_10px`**.
A política de agrupamentos, aprovada posteriormente, a sucede com
**`center_distance_v3_individuals_ignore_clusters_10px`**, registrada em
`evaluation.protocol_id` de `configs/protocol/splits.yaml`, sem mudar os raios.
**`center_distance_v1_15px`** identifica, como referência histórica, a avaliação
anterior com raio principal de 15 px. Esse nome retrospectivo não foi inserido
nos manifestos antigos. Resultados de versões diferentes não devem ser
misturados ou apresentados como se usassem o mesmo critério principal.

Os YAMLs históricos de T200/T190 e as configurações congeladas preservam
15 px; as configurações ativas da nova avaliação adotam 10 px. Nenhuma run
foi recalculada ou promovida por essa decisão, e os artefatos desta auditoria
descritiva permanecem imutáveis.

A aprovação do raio, isoladamente, não definiu a política de classes nem
resolveu a influência das antigas explorações sobre o teste. A decisão
posterior sobre indivíduos 0/2 e regiões de agrupamento está registrada em
[Classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md). Seleção, orçamento de busca
e desenho confirmatório ainda precisam de definição prospectiva.

## Reprodução e localização

Executor: [analyze_annotation_geometry.py](../../script/project/test/analyze_annotation_geometry.py).
Figura: [render_annotation_geometry.py](../../script/project/test/render_annotation_geometry.py).
Os comandos existem apenas no [guia oficial](../../script/README.md#geometria-das-anotacoes).

Os artefatos locais ficam em
`data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/`:

- `per_frame_counts.csv`: presença de anotações, contagens, classes e formatos.
- `per_video_geometry.csv`: quantis e denominadores por vídeo, grupo e medida.
- `per_video_gates.csv`: numeradores e frações para cada raio.
- `anomalies.csv`: lacunas e arquivos auxiliares ignorados.
- `summary.json`: totais e agregações com peso igual por vídeo.
- `input_files.csv` e `manifest.json`: 52.400 arquivos usados, hashes,
  parâmetros resolvidos, código, estado do Git, ambiente e recursos.
- `tolerancias_geometria.png` e `figure_manifest.json`: figura derivada dos
  CSVs, com proveniência própria; o manifesto da auditoria permanece intacto.

A execução levou aproximadamente 340 segundos, com pico amostrado de memória
do processo de 141,2 MiB e sem uso de GPU. É determinística, sem seed aleatória.
O código recusa sobrescrever a saída. Nenhuma fonte ou run antiga foi alterada.
