# Avaliação de detecções

O fluxo de execução, avaliação e revisão conjunta de cada rodada está no
[protocolo de desenvolvimento por rodadas](protocolo_rodadas.md), com fluxograma.

O avaliador compara caixas detectadas com as anotações já exportadas por uma
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
