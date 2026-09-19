# Detecção clássica

## Estado da implementação

| Método | Estado |
|---|---|
| Limiarização manual/Otsu + morfologia + componentes conectados | Código escrito; execução e validação experimental pendentes |
| Blobs | Planejado |
| Watershed | Planejado; representação dos aglomerados a definir |

Esta etapa contém somente os módulos do primeiro método. Não contém scripts
de execução, leitura de datasets, gravação de resultados ou cálculo de métricas.
Todas as execuções dos algoritmos e experimentos serão feitas pelo pesquisador.

## Arquivos

- `comum.py`: classes, caixas, medidas e representação tabular das detecções.
- `classificacao.py`: hipótese inicial de classificação por área segmentada.
- `limiarizacao.py`: detecção de componentes após limiarização e morfologia.
- `requirements.txt`: dependências declaradas; requer Python 3.10 ou posterior.

As faixas de versões das dependências não constituem um ambiente experimental
congelado. As versões efetivamente utilizadas deverão ser registradas nas
execuções. Não houve instalação de dependências nesta etapa.

## Entrada e saída comuns

A função `detectar(imagem, config)` recebe uma imagem em memória e uma
configuração explícita. Aceita imagens `uint8` em cinza (duas dimensões) ou BGR
(três canais, convenção OpenCV). Não recebe nem consulta as anotações.
A imagem de entrada não é modificada.

As classes mantêm os identificadores da base:

| Identificador | Categoria original |
|---|---|
| 0 | normal |
| 1 | cluster / aglomerado |
| 2 | small_or_pinhead / pequeno ou cabeça pequena |

Cada detecção inclui:

- Caixa em pixels: `x`, `y`, `largura`, `altura`; origem no canto superior esquerdo.
- Caixa normalizada: `center_x`, `center_y`, `width`, `height`, calculados a partir
  do retângulo e das dimensões da imagem, como nas anotações originais.
- Centroide dos pixels do componente, separado do centro geométrico da caixa.
- Área do componente em pixels e área do retângulo, que são medidas diferentes.
- Alongamento da caixa (maior lado / menor lado), ocupação (área do componente /
  área da caixa) e intensidade média na imagem cinza anterior à segmentação.

O limite direito/inferior da caixa em pixels é exclusivo. Para uma caixa
`(x, y, largura, altura)`, o centro usado no formato YOLO é
`(x + largura/2, y + altura/2)`.

`ResultadoDeteccao.linhas_yolo()` devolve as linhas
`class_id center_x center_y width height`, sem gravá-las.
`ResultadoDeteccao.registros()` devolve registros para uma futura tabela.
`indice_deteccao` é apenas um índice dentro da imagem, não uma identidade
persistente entre quadros. Não há score de confiança artificial, velocidade
ou trajetória nesta etapa.

Uma imagem sem componentes aceitos devolve uma coleção vazia. Futuramente,
o registro de execução deverá guardar também a lista de todas as imagens
processadas, inclusive aquelas sem detecções.

## Primeiro método

Sequência: imagem cinza → limiar manual ou Otsu → abertura → fechamento →
componentes conectados → filtro de área → classificação por área → caixas.

Todos os parâmetros experimentais devem ser fornecidos. Não há configurações
selecionadas ou valores apresentados como já calibrados.

| Campo | Significado |
|---|---|
| `metodo` | `manual` ou `otsu` |
| `polaridade` | `claro`: pixels acima do limiar; `escuro`: pixels até o limiar |
| `limiar_manual` | Inteiro entre 0 e 255 para manual; `None` para Otsu |
| `abertura`, `fechamento` | Forma, tamanho e número de iterações de cada operação |
| `conectividade` | Vizinhança de 4 ou 8 pixels |
| `area_minima`, `area_maxima` | Filtro inclusivo pela quantidade de pixels após a morfologia; máximo `None` desativa o limite superior |
| `classificacao` | Limites explícitos do classificador por área |

Cada operação morfológica aceita `elipse`, `retangulo` ou `cruz`, com suporte
quadrado de tamanho ímpar. `iteracoes=0` desativa a operação. A âncora fica no
centro; o tratamento de borda segue o padrão morfológico do OpenCV. A ordem
abertura → fechamento é fixa nesta implementação.

O limiar obtido por Otsu é devolvido por imagem. As detecções são ordenadas
pelo topo e pela esquerda das caixas. As medidas usam a máscara após as duas
operações morfológicas; a intensidade é medida nos pixels dessa região, mas
na imagem cinza original, antes das operações.

### Classificação inicial por área

Para uma região que passou pelo filtro do detector:

- Área até `area_maxima_pequeno`, inclusive: classe 2.
- Área a partir de `area_minima_aglomerado`, inclusive: classe 1.
- Área intermediária: classe 0.

Os limites devem deixar uma faixa inteira intermediária para a classe 0.
Essa regra é uma hipótese a testar: uma região grande não comprova a presença
de vários indivíduos, e uma região pequena não comprova a classe 2.
O filtro de área pode rejeitar regiões antes da classificação; seus limites
devem ser avaliados junto com os limites do classificador.

A comparação com uma regra que use área, forma e intensidade está prevista.
Essa segunda regra ainda não está implementada; as medidas já são retornadas
para permitir sua definição e análise posteriores.

## Organização das futuras execuções

Os módulos de detecção não escolhem pastas nem escrevem arquivos. Os futuros
scripts serão responsáveis pela organização abaixo:

```text
resultados/
├── frame-to-frame/
│   └── <algoritmo>/
│       └── <configuracao>__<execucao>/
└── videos/
    └── <algoritmo>/
        ├── selecao/
        │   └── <configuracao>__<execucao>/
        └── final/
            └── <configuracao>__<execucao>/
```

Os nomes de algoritmo serão `limiarizacao`, `blobs` e `watershed`.
As variantes manual e Otsu pertencem à família `limiarizacao`.

O nome de configuração terá um resumo legível e um identificador derivado de
todos os parâmetros; o identificador da execução incluirá data e hora UTC.
O resumo não substitui o arquivo de configuração. Colisões de nomes deverão
ser detectadas sem sobrescrever resultados. Exemplo apenas de nomenclatura,
sem representar uma configuração escolhida:

```text
otsu-ab3-fe5-area__cfg-a1b2c3d4e5f6__20260919T180000Z
```

Cada pasta de execução reunirá:

- `configuracao.json`: todos os parâmetros fornecidos, com suas unidades.
- `execucao.json`: etapa, algoritmo, configuração, versão do código, versões
  das dependências, dados utilizados, horários e situação da execução.
- `deteccoes.csv`: caixas, classes e medidas, com identificação da imagem,
  vídeo e número original do quadro quando aplicável.
- `avaliacao.json`: contagens e métricas, globais e por classe, após implementação
  do avaliador; o tempo de processamento será registrado separadamente.
- `por_quadro.csv`: resumo de cada quadro processado, inclusive sem detecções.
- `midia/`: imagens ou vídeos com caixas e classes, conservando a identificação
  do vídeo/quadro de origem no nome do arquivo.

Arquivos de mídia poderão combinar origem e nome da configuração/execução,
respeitando o limite de caminho do ambiente. Quando uma execução abranger
vários vídeos, cada um terá sua mídia própria; vídeos distintos não serão
concatenados. Imagens e vídeos originais serão lidos sem alterações.

O número original do quadro e o tempo correspondente, quando conhecido,
deverão acompanhar os resultados de vídeos. Ausência de tempo ou calibração
espacial não será substituída por valores presumidos. As medidas espaciais
disponíveis aqui estão em pixels, não em micrômetros.

A etapa de desenvolvimento ou seleção das execuções em imagens ficará no
registro de execução. Para vídeos, a pasta `selecao/` distinguirá o trabalho
com as cinco configurações da avaliação final, após o congelamento das escolhas.

## Protocolo acordado

| Uso | Vídeos |
|---|---|
| Desenvolvimento | 11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47, 60 |
| Seleção | 13, 29, 52, 54 |
| Avaliação final | 14, 24, 38, 82 |

Para a fase em imagens: 15 quadros por vídeo, numerados 0, 100, 200, …, 1400.
A lista definitiva do vídeo 23 depende da conferência descrita adiante.
As mesmas imagens e anotações serão utilizadas para todas as configurações.

As cinco configurações escolhidas nas imagens de seleção serão avaliadas nos
quatro vídeos completos de seleção. Depois do congelamento das escolhas, a
avaliação final usará os quatro vídeos completos reservados e as anotações
disponíveis, sem limitação a 15 imagens por vídeo.

Acerto: correspondência única entre previsão e anotação, mesma classe e
IoU maior ou igual a 0,50. Previsões sem correspondência contam como falsos
positivos; anotações sem correspondência contam como falsos negativos.
Uma previsão da classe errada não é acerto de classificação: contribui como
falso positivo na classe prevista e falso negativo na classe real.

A seleção utilizará a média dos F1 das três classes (macro-F1), calculando
primeiro as contagens de cada classe no conjunto de seleção. Acompanharemos
também precisão, recall e resultados separados por vídeo. Os vídeos podem
contribuir com quantidades diferentes de objetos dentro de cada classe.

Critérios em ordem:

1. Maior macro-F1.
2. Apenas em empate, maior F1 da classe 0.
3. Persistindo o empate, menor tempo de processamento.

Os empates serão avaliados antes do arredondamento. Diferenças próximas não
equivalem a empate ou a superioridade estatística demonstrada. A medição do
tempo e o tratamento de classes ausentes deverão ser especificados antes da
implementação do avaliador. A classificação por área não implica que as três
classes estarão presentes nas previsões de uma imagem.

## Pendências e limites

- As 174 lacunas do vídeo 23 constam dos registros locais como arquivos de
  anotação ausentes. O artigo da base descreve 174 quadros sem espermatozoides.
  É necessário esclarecer essa diferença antes de substituir quadros. As
  substituições propostas de 900 por 973 e de 1100 por 1108 não foram aplicadas.
  Arquivo ausente não será automaticamente interpretado como anotação vazia.
- Antes do Watershed, definir como representar caixas de aglomerados e de
  indivíduos quando houver sobreposição nas anotações.
- Antes de blobs, definir a extração das regiões e das caixas, mantendo
  explícita a diferença entre área segmentada e área estimada.
- Rastreamento, SORT, Lucas–Kanade, Horn–Schunck e predição estão fora desta etapa.
- A reserva de vídeos vale para esta organização experimental. O uso dos dados
  na versão anterior permanece parte do histórico e não torna esses dados inéditos.
- Até esta entrega, a conferência do código foi estática. Não houve execução
  de detectores, medição de desempenho ou validação das hipóteses nos dados.

## Referências

- [VISEM-Tracking: artigo da base](https://www.nature.com/articles/s41597-023-02173-4).
- [OpenCV: limiarização](https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html).
- [OpenCV: morfologia](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html).
- [OpenCV: componentes conectados](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html).
- [Definição de F1 e suas agregações](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html).
