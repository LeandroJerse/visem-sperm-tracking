# Avaliação de detecções

O fluxo de execução, avaliação e revisão conjunta de cada rodada está no
[protocolo de desenvolvimento por rodadas](protocolo_rodadas.md), com fluxograma.

## Critério atual: localizar indivíduos e registrar a classificação

A seleção original de 122 configurações nos 60 quadros dos vídeos 13, 29, 52
e 54 foi concluída. Após a revisão dos resultados, foi aprovada uma nova
avaliação das **mesmas caixas salvas**, mantendo os resultados anteriores:

- **Indivíduos (0 e 2):** uma correspondência com IoU ≥ 0,50 conta como acerto
  de detecção, mesmo com troca entre normal e pequeno. Essa troca é registrada
  como erro de classificação.
- **Aglomerados (1):** avaliados separadamente. Uma troca entre indivíduo e
  aglomerado continua sendo erro de detecção nos respectivos grupos.
- O pareamento é um para um, maximiza a quantidade de pares e depois a soma
  das IoUs. As correspondências são recalculadas, preservando os rótulos originais.

`avaliacao_individuos.py` implementa as novas regras e a agregação das contagens.
O pesquisador executou `scripts/limiarizacao/reavaliar_selecao.py`.
Para repetir essa reavaliação:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\reavaliar_selecao.py"
```

O batch de origem padrão é `batch__20260920T012713968145Z`, na seleção.
Dentro dele, cada execução cria `reavaliacoes_individuos/<execucao>/`:

| Campo ou arquivo | Como interpretar |
|---|---|
| `ranking.csv`: `f1_individuos` | Métrica principal, usando TP/FP/FN somados dos indivíduos |
| `recall_classe_0`, `recall_classe_2` | Fração dos normais/pequenos anotados que recebeu par, mesmo com troca 0/2 |
| `f1_aglomerados` | F1 separado da classe 1 |
| `pares_corretos`, `pares_incorretos` | Rótulos iguais ou trocados entre indivíduos pareados |
| `matriz_0_0`, `matriz_0_2`, `matriz_2_0`, `matriz_2_2` | Primeiro índice: anotação; segundo: previsão, somente indivíduos pareados |
| `acuracia_condicional` | Pares com rótulo correto / pares de indivíduos; exclui perdas e falsas detecções |
| `resumo_por_video.csv` | Mesmos diagnósticos por vídeo |
| `sXXX/pares.csv`, `sXXX/pendentes.csv` | Correspondências e objetos sem par, rastreáveis até suas caixas salvas |

O F1 de indivíduos não é a média dos F1 de normal e pequeno. Somar as
contagens dá mais influência às classes e vídeos com mais casos; cobertura
por classe e resultados por vídeo complementam a revisão. Acurácia condicional
alta, sozinha, não significa que o detector encontrou muitos objetos.
Denominadores nulos permanecem indefinidos. Se houver apenas FP ou FN, F1=0.

O ranking usa a fração exata do F1: empates mantêm o mesmo posto, sem pesos
ou desempate automático por outra métrica. IDs apenas estabilizam a ordem
visual. Após a revisão, foram aprovadas `s068`, `s067`, `s090`, `s099` e `s101`
para os vídeos completos de seleção. O empate entre as duas últimas ocupa
as posições 4 e 5; não atravessa o limite das cinco vagas.

`relatorio_individuos.py` gera um novo PDF com F1 de indivíduos, cobertura,
classificação condicional e comparação entre vídeos. As estatísticas são
descritivas entre configurações, sem teste de significância. Para as 122
candidatas, são nove páginas. Os comandos de repetição do relatório, dependências
e testes estão no [guia de limiarização](../scripts/limiarizacao/README.md).
A reavaliação `20260920T021112218814Z` e seu PDF foram executados pelo
pesquisador e conferidos: 122 configurações × 60 quadros, preservando as caixas.

A mudança do critério foi decidida após observar a primeira seleção.
Esse histórico está registrado na versão 2 do protocolo; a mudança não deve
ser apresentada como uma regra anterior aos resultados. As métricas de três
classes, o macro-F1 e os PDFs históricos descritos a seguir permanecem intactos.

## Avaliação dos vídeos completos de seleção — concluída

`scripts/limiarizacao/executar_videos.py` aplica as cinco configurações aprovadas
aos MP4 completos 13, 29, 52 e 54, sem mudar parâmetros ou critérios.
São 5.850 quadros por configuração, todos com arquivo de anotação previsto.
O executor verifica fontes e alinhamento antes de detectar; interrupções não
são transformadas em quadros sem objetos. Os detalhes e comandos estão no
[guia de limiarização](../scripts/limiarizacao/README.md).

As contagens de indivíduos e aglomerados são somadas antes de recalcular F1,
tanto por vídeo como por configuração. As tabelas distinguem cobertura de
normais/pequenos e erros de classificação entre os pares 0/2. As contagens
representam ocorrências nos quadros, sem deduplicação temporal ou rastreamento.

`relatorio_videos.py` gera três páginas com F1 de indivíduos, cobertura,
classificação condicional e resultados por vídeo. Confere os hashes dos
resumos, a cobertura esperada e a coerência entre totais e subtotais antes
de montar o PDF. As estatísticas descrevem as cinco configurações, sem teste
de significância ou escolha automática da vencedora. O relatório usa os
resumos; a conferência dos MP4 gerados cabe ao executor.

O pesquisador concluiu o batch `batch__20260920T023832151694Z`: 29.250
avaliações, 20 MP4 e PDF de três páginas. Hashes, contagens e correspondências
salvas foram conferidos, assim como o alinhamento registrado e a apresentação
do PDF. O maior F1 de indivíduos foi 0,257230 (`s068`), com falhas importantes:
as duas manuais tiveram F1 zero nos vídeos 29 e 52; a cobertura de pequenos
ficou abaixo de 5% nas cinco configurações. Os pequenos localizados foram
rotulados como normais nos pares aceitos.
Os vídeos de seleção já foram usados em imagens. Diferenças de compressão
JPEG/MP4 e a ampliação para todos os quadros devem ser consideradas na análise;
essa etapa não constitui uma nova amostra independente.

## Avaliação final — concluída

Após revisar a seleção em vídeos, foram aprovadas as mesmas cinco configurações
para os MP4 completos **14, 24, 38 e 82**. Parâmetros, IoU, grupos, agregação
e regras de classificação permaneceram iguais. Foram avaliados **5.910 quadros
por configuração**, com arquivos de anotação para todos os índices, totalizando
29.550 avaliações. Arquivos ausentes ou divergentes interrompem a execução.

O comando é `scripts/limiarizacao/executar_videos.py --etapa final`; as saídas
ficam em `resultados/videos/limiarizacao/final/`. O mesmo módulo de relatório
distingue seleção e final pelo manifesto, pelo plano e pela pasta de origem.
Os gráficos finais descrevem as cinco escolhas já congeladas; o ranking não
serve para iniciar novos ajustes ou apresentar a melhor escolha posterior
como se tivesse sido fixada antes de observar os resultados finais.

A reserva dos dados nesta versão não elimina seu histórico de uso anterior.
O batch `batch__20260920T030805588232Z` concluiu as 29.550 avaliações,
20 vídeos e PDF. Contagens, cobertura e hashes foram conferidos. `s099` e
`s101` empataram com F1 de indivíduos de 0,566796, mas nenhuma localizou
as 2.936 ocorrências anotadas de pequenos. O ranking final é descritivo.
Resultados, parâmetros e limitações estão na
[conclusão da limiarização](conclusao_limiarizacao.md).
O [plano de blobs](plano_blobs.md) mantém o ciclo com adaptações nas medidas.
Seu detector e o executor de `round0` estão preparados, com avaliação pelo
critério atual de indivíduos e classificação separada. O relatório inicial
(`relatorio_inspecao_blobs.py`) mostra métricas e resultados por quadro, sem
ranking; sua geração depende da execução pelo pesquisador. Consulte o
[guia de blobs](../scripts/blobs/README.md). Os testes preparados para essa
implementação ainda não foram executados.
Comandos, dependências e saídas estão no
[guia de limiarização](../scripts/limiarizacao/README.md).

## Avaliadores históricos: três classes e localização auxiliar

O avaliador original compara caixas detectadas com as anotações já exportadas por uma
execução individual. Ele não executa novamente o detector, não abre os arquivos
originais da base e não gera novas imagens. As três classes permanecem:
0 — normal, 1 — aglomerado e 2 — pequeno (`small_or_pinhead`).

`avaliacao_deteccao.py` contém a representação `Objeto` e a função
`avaliar(anotacoes, deteccoes)`. O comando de entrada está em
`scripts/avaliacao/avaliar_imagem.py`, que avalia somente uma imagem.
`agregacao_deteccao.py` reúne as contagens de vários quadros antes de recalcular
as métricas. O executor `scripts/limiarizacao/executar_rodada.py` usa essas duas
funções na rodada de desenvolvimento descrita em [`scripts/README.md`](../scripts/README.md).
A seleção das melhores configurações permanece uma decisão conjunta.

As cinco rodadas de desenvolvimento estão concluídas. A
[revisão do round5](rodadas/round5_revisao.md) apresenta o balanço geral, e
[desenvolvimento_resumo.json](rodadas/desenvolvimento_resumo.json) reúne
as 122 configurações distintas, métricas e origens. Essa ordenação não
substitui a seleção nos dados reservados.

`scripts/limiarizacao/executar_selecao.py` realizou a comparação
das mesmas candidatas nos 60 quadros aprovados dos vídeos 13, 29, 52 e 54.
As saídas usam a pasta `selecao` no lugar de `round<N>`, com os mesmos
resumos e regras. O PDF identifica essa partição como Seleção.

## Onde consultar o F1 de uma rodada

Dentro de `resultados/frame-to-frame/limiarizacao/round<N>/batch__<execucao>/`,
abra `resumo_configuracoes.csv`. Cada linha representa uma configuração:

| Coluna | Significado |
|---|---|
| `configuracao_id` | Identificador da configuração no plano |
| `macro_f1` | Métrica principal histórica: média dos três F1 de classe, após agregar as contagens |
| `f1_classe_0`, `f1_classe_1`, `f1_classe_2` | F1 de normal, aglomerado e pequeno, respectivamente |
| `f1_localizacao` | Diagnóstico auxiliar, ignorando a classe |
| `pasta` | Local das imagens, parâmetros e tabelas detalhadas dessa configuração |

`resumo_por_video.csv` apresenta essas métricas para cada vídeo separadamente.
Um campo de F1 vazio, acompanhado de `sem_casos`, não equivale a zero.

## Relatório da rodada

O batch gera automaticamente um PDF ao concluir. Também é possível criá-lo
a partir de um batch já concluído, usando
[`gerar_relatorio_rodada.py`](../scripts/avaliacao/gerar_relatorio_rodada.py),
sem executar novamente a detecção ou alterar as métricas salvas. O módulo
`relatorio_rodada.py` lê os resultados e usa Matplotlib e ReportLab; as
dependências estão em `requirements-relatorio.txt`.

Para gerar o PDF da primeira rodada já executada, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\avaliacao\gerar_relatorio_rodada.py" --batch ".\resultados\frame-to-frame\limiarizacao\round1\batch__20260919T192640642218Z"
```

A saída fica em `batch__<execucao>/relatorios/<data-hora-UTC>/`: `relatorio.pdf`,
`relatorio.json` e `execucao_origem.json`. Cada geração é preservada. Uma falha
na geração do PDF não desfaz as detecções e métricas já concluídas.

Para até 48 configurações e 12 vídeos, o relatório contém três páginas: gráfico do
macro-F1 de todas as configurações, mapa dos F1 por classe e mapa do macro-F1
por vídeo. A ordenação dos gráficos é descritiva e não seleciona finalistas.
Os estados sem casos são mantidos, inclusive quando uma classe está ausente
em determinado vídeo e torna seu macro-F1 indefinido.

Média, mediana, desvio padrão amostral, mínimo, máximo e quantidade de valores
definidos descrevem a distribuição das métricas **entre configurações**.
Somente valores definidos participam dessas estatísticas, com quantidade
informada; isso não muda a regra do macro-F1 de cada configuração. Desvio
padrão amostral exige pelo menos dois valores. Essas estatísticas não são
intervalos de confiança ou testes de significância. O tempo permanece
diagnóstico. O relatório não cria novas regras de seleção ou agregação.

Os PDFs das cinco rodadas e da seleção original foram produzidos e conferidos.
Para 122 configurações e quatro
vídeos, a paginação divide os gráficos em três blocos, totalizando nove páginas.

## Preparação e execução

Abra o terminal na raiz do projeto. Instale as dependências no mesmo Python que
será usado para avaliar. São necessários NumPy e SciPy; o avaliador não depende
do OpenCV nem do scikit-learn.

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\analise\requirements.txt"
```

Para avaliar a execução já existente do quadro 0 do vídeo 11:

```powershell
& "C:\Python313\python.exe" ".\scripts\avaliacao\avaliar_imagem.py" --execucao ".\resultados\frame-to-frame\limiarizacao\round0\otsu-claro-abe3x0-fee3x0-area__cfg-c6339379e654__20260919T182437178768Z"
```

`--execucao` recebe a pasta completa de uma execução de detecção concluída.
Caminhos relativos são interpretados a partir da pasta atual do terminal.
O comando aceita somente execuções dentro de `resultados/frame-to-frame/`
deste projeto.

## Entradas e conferências

O comando lê três arquivos dessa pasta:

- `execucao.json`: situação, origem da imagem, dimensões e quantidades esperadas.
- `deteccoes.csv`: caixas, classes e índices das detecções salvas.
- `anotacoes.csv`: caixas, classes e índices das anotações salvas.

Antes de calcular as métricas, confere a conclusão da execução, a coerência da
origem entre os arquivos, as quantidades declaradas, as classes aceitas, os
índices e as caixas. Coordenadas precisam ser finitas, com dimensões positivas
e compatíveis com a imagem. Uma inconsistência interrompe a avaliação em vez
de ser convertida silenciosamente em ausência de objetos.

As tabelas representam a referência e as previsões daquela execução. Essas
conferências não substituem a inspeção da qualidade das anotações. Os arquivos
de entrada e as mídias existentes são preservados.

## Correspondência das caixas

Para duas caixas, a interseção sobre união é:

```text
IoU = área da interseção / área da união
área da união = área da caixa A + área da caixa B - área da interseção
```

As áreas são geométricas, calculadas a partir das caixas, sem arredondar suas
coordenadas para pixels inteiros. O limiar é fixo: `IoU >= 0,50`.

A avaliação principal admite um par somente quando as classes são iguais e o
limiar de IoU é atendido. Cada anotação e cada detecção participam de no máximo
um par. A associação busca, nesta ordem:

1. O maior número possível de pares válidos.
2. Entre associações com esse número de pares, a maior soma dos valores de IoU.

Essa atribuição global usa `scipy.optimize.linear_sum_assignment`. A prioridade
pela quantidade de pares é incorporada aos pesos; maximizar apenas a soma de
IoU poderia favorecer menos pares. Não se escolhe cada par isoladamente, pois
uma escolha local pode impedir outra associação válida.

As caixas originais de aglomerados e indivíduos podem se sobrepor. O avaliador
preserva todas as anotações: uma detecção não pode acertar simultaneamente a
caixa do conjunto e a de um indivíduo. Esse limite faz parte da correspondência
um a um e não cria nem remove classes.

## Métricas principais

Para cada classe:

- **TP:** quantidade de pares válidos encontrados.
- **FP:** detecções dessa classe que ficaram sem par.
- **FN:** anotações dessa classe que ficaram sem par.

```text
precisão = TP / (TP + FP)
recall = TP / (TP + FN)
F1 = 2 × TP / (2 × TP + FP + FN)
macro-F1 = (F1 da classe 0 + F1 da classe 1 + F1 da classe 2) / 3
```

Precisão mede a proporção de previsões aceitas como acerto; recall mede a
proporção de anotações encontradas. O F1 combina os dois aspectos. Localizar
uma caixa com classe incorreta não produz TP no critério principal: a previsão
e a referência precisam de pares válidos em suas respectivas classes.

Casos sem denominador seguem a convenção acordada:

| Situação | Resultado |
|---|---|
| Nenhuma previsão da classe (`TP + FP = 0`) | Precisão `null` |
| Nenhuma anotação da classe (`TP + FN = 0`) | Recall `null` |
| Nenhuma anotação nem previsão da classe | F1 `null` |
| Nenhum TP, mas existe FP ou FN | F1 igual a zero |
| Qualquer uma das três classes tem F1 `null` | Macro-F1 `null` |

`null` significa que a métrica não pôde ser calculada naquele caso. Nunca se
substitui o macro-F1 das três classes pela média das duas restantes. No CSV,
métricas indefinidas ficam vazias; no resumo, sua ausência fica explícita.

Na avaliação de várias imagens pelo batch, somam-se TP, FP e FN de cada classe
antes de recalcular as métricas. Não se calcula a média dos F1 de cada quadro.
Esta avaliação individual não estabelece uma classificação das configurações.

## Análise auxiliar de localização

Uma segunda associação ignora a classe, mantendo `IoU >= 0,50`, correspondência
um a um e as mesmas prioridades de quantidade de pares e soma de IoU. Ela é
calculada novamente, de forma independente da avaliação principal.

Essa análise mostra quais caixas podem ser associadas espacialmente. A matriz
3 × 3 conta as classes anotadas e previstas somente desses pares: linhas são
as classes da referência; colunas, as classes previstas. Valores fora da
diagonal indicam classes diferentes nos pares dessa análise.

Detecções e anotações sem par ficam nas tabelas de pendências, fora da matriz.
As classes continuam sendo 0, 1 e 2; não há classe adicional para pendências.
Como os pares podem mudar entre as duas associações, a diferença entre seus
totais de TP não equivale necessariamente à quantidade de erros de classe.
As contagens auxiliares não são misturadas com as métricas principais.

## Arquivos gerados

Cada chamada cria uma nova pasta, sem sobrescrever avaliações anteriores:

```text
<execucao>/avaliacoes/<data-hora-UTC>/
├── avaliacao.json
├── metricas.csv
├── pares_classe.csv
├── pares_localizacao.csv
├── pendentes_classe.csv
├── pendentes_localizacao.csv
└── resumo.txt
```

- `avaliacao.json`: estado da avaliação, metadados e resultados estruturados.
- `metricas.csv`: contagens e métricas, separando avaliação principal e auxiliar.
- `pares_classe.csv`: correspondências aceitas no critério principal e seus IoU.
- `pares_localizacao.csv`: correspondências auxiliares, com ambas as classes.
- `pendentes_classe.csv`: detecções e anotações sem par no critério principal.
- `pendentes_localizacao.csv`: pendências da associação que ignora a classe.
- `resumo.txt`: leitura resumida das métricas e dos limites de interpretação.

Os índices permitem rastrear cada objeto até a tabela de entrada. Eles não
representam identidade entre quadros. Não são produzidos valores de confiança,
AP ou mAP: as saídas atuais não possuem pontuações de confiança por detecção.

## Verificação

O batch produz suas próprias tabelas por quadro, vídeo e configuração. Não
use o avaliador individual sobre uma pasta agregada de batch: ele espera
uma única imagem. O macro-F1 do batch é calculado a partir das contagens
totais por classe, nunca pela média dos macro-F1 de imagens ou vídeos.

`test_agregacao_deteccao.py` verifica essa agregação, classes sem casos e a
independência do diagnóstico de localização. Os novos testes foram apenas
conferidos estaticamente. Para executá-los junto com os testes do avaliador:

```powershell
& "C:\Python313\python.exe" -m unittest analise.test_avaliacao_deteccao analise.test_agregacao_deteccao
```

`test_avaliacao_deteccao.py` reúne testes sintéticos, sem usar imagens da base.
Eles foram escritos para conferir as regras de associação e métricas, mas não
foram executados nesta implementação. Para executá-los na raiz do projeto:

```powershell
& "C:\Python313\python.exe" -m unittest analise.test_avaliacao_deteccao
```

A execução sobre os resultados reais também cabe ao pesquisador. A existência
do código e dos testes não constitui validação experimental do detector.

## Referências

- [SciPy: atribuição linear e correspondência de peso máximo](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html).
- [Scikit-learn: definição de F1 e médias por classe](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html).

A política de valores indefinidos e a associação por IoU são decisões deste
protocolo; não se presume que os padrões das bibliotecas sejam idênticos.
