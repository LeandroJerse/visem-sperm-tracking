# Limiarização: execução e detalhes das saídas

Para escolher o comando, consulte o [guia de scripts](../README.md).
Todos os comandos abaixo são executados na raiz do projeto.

O [protocolo de desenvolvimento por rodadas](../../analise/protocolo_rodadas.md)
registra o fluxo de preparação, execução, avaliação e revisão conjunta.

## Avaliação final em vídeos — concluída

A seleção em vídeos foi concluída e conferida no batch
`batch__20260920T023832151694Z`. Após a revisão dos resultados, foram aprovadas
as mesmas **s068, s067, s090, s099 e s101**, com parâmetros e métricas congelados,
para os vídeos **14, 24, 38 e 82**. O [plano final](videos/plano_final.json)
registra essa decisão, as fontes e a execução de seleção que a antecedeu.

Para repetir, execute na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_videos.py" --etapa final
```

| Vídeo final | Quadros | FPS |
|---|---:|---:|
| 14 | 1470 | 49 |
| 24 | 1470 | 49 |
| 38 | 1470 | 49 |
| 82 | 1500 | 50 |

Todos têm 640 × 480 pixels e 30 segundos; existem imagens e arquivos de
anotação para todos os índices. São **5.910 quadros por configuração**,
**29.550 avaliações** e **20 MP4 comparativos**, além das tabelas e do PDF
de três páginas. O conteúdo visual mantém anotações à esquerda, detecções
à direita, classes, quadro, tempo e contagens de indivíduos.

As saídas usam a mesma estrutura descrita abaixo, na pasta
`resultados/videos/limiarizacao/final/batch__<execucao>/`. As conferências
de fontes, alinhamento e pixels acontecem antes das detecções e a integridade
dos vídeos gerados é verificada após a gravação. Divergências interrompem
a execução, sem substituições ou exclusões automáticas.

**Informe `--etapa final`: sem esse argumento, o padrão continua sendo seleção.**
O executor rejeita misturas entre plano, vídeos e etapa. `--plano` aceita uma
cópia exata do plano correspondente; não serve para editar configurações.
Os relatórios identificam a etapa e seus quatro vídeos. Para gerar somente
outro PDF de uma execução final concluída:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_videos.py" --etapa final --somente-relatorio ".\resultados\videos\limiarizacao\final\batch__<execucao>"
```

Nesta etapa, o ranking descreve o desempenho das cinco escolhas congeladas.
Não cria novas candidatas nem autoriza ajustes pelos resultados finais.
A reserva dos vídeos nesta versão não elimina seu uso histórico anterior.
O batch `batch__20260920T030805588232Z` concluiu as 29.550 avaliações,
20 MP4 e PDF. A conferência verificou cobertura, contagens e hashes, sem
reexecutar detectores ou decodificar novamente os vídeos. A
[conclusão da limiarização](../../analise/conclusao_limiarizacao.md) reúne
os resultados e as limitações. Os testes de código não foram executados
nesta revisão; seus comandos permanecem na seção seguinte.

## Vídeos completos de seleção — concluídos

Foram aprovadas `s068`, `s067`, `s090`, `s099` e `s101`, mantendo exatamente
os parâmetros da seleção em imagens. O [plano](videos/plano_selecao.json)
fixa essas configurações, os vídeos 13, 29, 52 e 54 e todas as anotações.

Na raiz do projeto, instale as dependências no Python usado para executar:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_videos.py" --etapa selecao
```

O comando processa os quatro MP4 completos para cada configuração e gera
**20 vídeos comparativos**: anotações originais à esquerda, detecções à direita,
com caixas, classes, número do quadro, tempo e TP/FP/FN dos indivíduos.
As cores permanecem amarelo (0), roxo (1) e ciano (2). Cada vídeo tem 30 segundos,
na velocidade original; a comparação lado a lado tem 1280 × 584 pixels.

| Vídeo | Quadros | FPS |
|---|---:|---:|
| 13 | 1470 | 49 |
| 29 | 1470 | 49 |
| 52 | 1440 | 48 |
| 54 | 1470 | 49 |

São **5.850 quadros por configuração**, totalizando 29.250 avaliações.
Antes da detecção, o executor confere os arquivos e o alinhamento temporal
entre cinco JPEGs de referência de cada vídeo e todos os seus quadros MP4.
O quadro esperado precisa ser o único mais semelhante, pelo erro médio
absoluto em cinza; divergências ou ambiguidades interrompem a execução.
Essa conferência usa amostras e não exige igualdade dos pixels JPEG/MP4.
Imagens da conferência ficam disponíveis para inspeção visual.

A primeira leitura também registra o hash dos pixels de todos os quadros.
As cinco configurações precisam receber esses mesmos pixels nas leituras
seguintes. O tempo salvo é `quadro / FPS`, com índice começando em zero,
conforme os metadados de taxa constante dos MP4. Os arquivos originais são
somente lidos. Os vídeos finais 14, 24, 38 e 82 pertencem à etapa posterior.

```text
resultados/videos/limiarizacao/selecao/batch__<execucao>/
├── plano.json, execucao.json, codigo.zip
├── conferencia/                 imagens, alinhamento e hashes dos quadros
├── resumo_configuracoes.csv, resumo_por_video.csv, ranking.csv
├── <id>__<configuracao>__<execucao>/
│   ├── configuracao.json, execucao.json, avaliacao.json
│   ├── deteccoes.csv, anotacoes.csv, por_quadro.csv
│   ├── pares.csv, pendentes.csv, resumo.csv, resumo_por_video.csv
│   └── midia/<id>__cfg-<hash>__video-<numero>.mp4
└── relatorios/<execucao>/relatorio.pdf
```

O nome da pasta resume os parâmetros; o nome curto de cada MP4 identifica a
configuração e o vídeo, evitando caminhos excessivamente longos no Windows.
`configuracao.json` contém todos os valores. As tabelas preservam caixas em
pixels e normalizadas, classes, áreas, centroides, origem e tempo. Índices de
detecção valem dentro do quadro; ainda não representam trajetórias ou indivíduos
únicos ao longo do vídeo.

O F1 mantém a regra aprovada: indivíduos 0/2 juntos, erros de classificação
separados e aglomerados à parte. As contagens são somadas antes do cálculo.
O PDF terá três páginas com F1, cobertura, classificação e variação por vídeo.
O ranking não escolhe uma vencedora automaticamente.

Cada chamada cria uma nova pasta. Se falhar, os arquivos parciais permanecem
com a falha registrada; não há retomada automática. Se apenas o PDF falhar,
as métricas continuam concluídas. Para gerar somente outro relatório:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_videos.py" --somente-relatorio ".\resultados\videos\limiarizacao\selecao\batch__<execucao>"
```

O pesquisador executou a seleção no batch `batch__20260920T023832151694Z`:
as 29.250 avaliações, os 20 MP4 e o PDF foram concluídos. Foram conferidos
os hashes, as contagens, os registros de alinhamento e as três páginas do PDF.
As configurações manuais falharam em localizar indivíduos nos vídeos 29 e 52;
os resultados permanecem preservados. Para executar os testes de código,
incluindo as verificações acrescentadas para a etapa final:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_videos_limiarizacao analise.test_relatorio_videos
```

## Reavaliação de indivíduos — concluída

A seleção de 122 configurações nos 60 quadros foi concluída no batch
`batch__20260920T012713968145Z`. A reavaliação foi concluída em
`reavaliacoes_individuos/20260920T021112218814Z/`. Para repeti-la:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\reavaliar_selecao.py"
```

Ele refaz o pareamento com dois grupos: indivíduos (0 e 2) e aglomerados (1).
Uma troca 0/2 é acerto de detecção com erro de classificação separado.
Indivíduos e aglomerados não formam par entre si. O ranking usa F1 de
indivíduos, sem pesos ou desempate automático por outra métrica.
As regras e suas limitações estão no [guia de avaliação](../../analise/README.md).

O script lê somente tabelas e registros salvos, confere suas origens,
configurações, quadros e caixas antes de avaliar e registra hashes e código.
Não abre vídeos, imagens ou anotações originais nem repete a detecção.
`--batch` permite informar outra execução completa do mesmo plano aprovado;
sem esse argumento, a origem é fixa e não depende da pasta mais recente.

Cada execução cria a seguinte estrutura dentro do batch:

```text
reavaliacoes_individuos/<data-hora-UTC>/
├── execucao.json, codigo.zip
├── resumo_configuracoes.csv, resumo_por_video.csv, ranking.csv
├── s001/ ... s122/
│   ├── avaliacao.json, por_quadro.csv
│   └── pares.csv, pendentes.csv
└── relatorios/<data-hora-UTC>/
    ├── relatorio.pdf
    ├── relatorio.json
    └── execucao_origem.json
```

`pasta_origem` remete às configurações e imagens comparativas anteriores;
não são geradas novas imagens. As tabelas registram contagens e métricas dos
dois grupos, cobertura de cada classe original, matriz de classificação 0/2
e erros entre os indivíduos pareados. `ranking.csv` mantém postos iguais nos
empates exatos, destaca empate atravessando a quinta posição e não promove
configurações automaticamente.

O PDF reúne F1 de indivíduos, cobertura de normais/pequenos, classificação
condicional e variação por vídeo. Uma falha no PDF preserva as métricas.
Para gerar apenas outro PDF, substitua `<execucao>` pelo nome da reavaliação:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\reavaliar_selecao.py" --somente-relatorio ".\resultados\frame-to-frame\limiarizacao\selecao\batch__20260920T012713968145Z\reavaliacoes_individuos\<execucao>"
```

Dependências: `analise/requirements.txt` e `analise/requirements-relatorio.txt`.
O pesquisador executou a reavaliação e gerou seu PDF; os resultados foram
conferidos. Os testes de código permanecem disponíveis:

```powershell
& "C:\Python313\python.exe" -m unittest analise.test_avaliacao_individuos analise.test_relatorio_individuos scripts.testes.test_reavaliar_selecao
```

## Seleção original — concluída

As cinco rodadas foram concluídas. A [revisão do round5](../../analise/rodadas/round5_revisao.md)
recomenda encerrar o desenvolvimento e registra a seleção aprovada:
122 configurações distintas das cinco rodadas, sem novos ajustes, nos
quadros 0, 100, ..., 1400 dos vídeos 13, 29, 52 e 54.

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_selecao.py"
```

O [plano de seleção](selecao/plano.json) fixa os 60 quadros, seus hashes,
as 122 configurações e todas as suas origens. São 7.320 avaliações.
Os IDs `s001` a `s122` seguem a primeira ocorrência nas rodadas; não são
posições no ranking. Repetições equivalentes foram retiradas apenas da seleção.

Os resultados foram salvos em `resultados/frame-to-frame/limiarizacao/selecao/`,
no mesmo formato das rodadas: uma pasta de batch, uma por configuração,
imagens comparativas, previsões, tabelas e PDF. Com 122 configurações e
quatro vídeos, o PDF terá nove páginas, em três blocos de até 48 configurações.
Repetir o comando cria nova execução, preservando a anterior.
`--plano` permite apontar uma cópia do plano salvo.

O executor confere a composição aprovada e os hashes antes de detectar.
Não aceita vídeos de desenvolvimento ou de avaliação final como substitutos.
Esse executor mantém as regras históricas: macro-F1 das três classes e
F1 normal somente no empate. Seu PDF facilita a revisão, sem escolher cinco.
A reavaliação acima usa o novo critério acordado, em saídas separadas.
As cinco aprovadas seguem para a execução em vídeos descrita no início deste guia.

## Quinta rodada em batch — concluída

O plano [round5.json](rodadas/round5.json) contém **14 configurações** definidas
após a [revisão do round4](../../analise/rodadas/round4_revisao.md). É a última
rodada planejada de desenvolvimento. A
[reavaliação de 25 combinações](../../analise/rodadas/round4_reavaliacao_areas.json)
sobre caixas salvas não superou a melhor macro-F1 do round4 nessa grade.
Os parâmetros abaixo foram testados; seus resultados estão na
[revisão do round5](../../analise/rodadas/round5_revisao.md).

| Grupo | Configurações | Parâmetros comparados |
|---|---:|---|
| Controles | 4 | Repetição de `round4/c07`, `round4/c09`, `round4/c01` e `round4/c18` |
| Otsu com fechamento retangular 5 | 2 | Limite pequeno 120; início de aglomerado 875/925, próximos da referência 900 |
| Manual com fechamento elíptico 7 | 4 | Limiares 111/113/114/115; limite pequeno 120 e aglomerado 1000 |
| Comparação de forma no manual | 4 | Limiares 112/113 × fechamento elíptico/retangular 5; limite pequeno 120 e aglomerado 1000 |

Todas usam área mínima 48, máxima 5000, abertura desligada, polaridade clara
e conectividade 8. As áreas são pixels da região segmentada. Os parâmetros
completos e os objetivos de cada configuração estão no plano.

São os mesmos **178 quadros**, ordem, hashes e duas exclusões das rodadas
anteriores: **2.492 avaliações de imagem**, já concluídas. Para repetir:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round5
```

As saídas ficarão em `resultados/frame-to-frame/limiarizacao/round5/`, com
relatório PDF automático ao concluir. A lista é determinística, sem sorteio;
a seed 42 permanece como registro. Para repetir, use o mesmo JSON salvo.
`preparar_rodada.py` não reconstrói essa lista. **Sem argumentos, o executor
continua usando round1**, por isso informe `--rodada round5`.

A revisão encerrou as cinco rodadas e orientou o plano de seleção acima.
Nenhuma finalista foi escolhida com os resultados de desenvolvimento.
Round0 fica fora das cinco rodadas; a avaliação final permanece posterior.

## Quarta rodada em batch — anterior

O plano [round4.json](rodadas/round4.json) contém **18 configurações** definidas
após a [revisão do round3](../../analise/rodadas/round3_revisao.md). Quatro
repetem configurações anteriores; as demais refinam limites de classificação
e limiares manuais nas segmentações comparadas.

| Grupo | Configurações | Parâmetros comparados |
|---|---:|---|
| Controles | 4 | Repetição de `round3/c07`, `round3/c15`, `round3/c19` e `round3/c22` |
| Otsu com fechamento retangular 5 | 4 | Limite pequeno 100/120 × início de aglomerado 900/950 |
| Otsu com fechamento elíptico 5/7 | 4 | Limite pequeno 120 × início de aglomerado 900/950 |
| Limiar manual | 6 | 103/105/107 com fechamento elíptico 5; 108/110/112 com fechamento elíptico 7; limite pequeno 120 e aglomerado 1000 |

Todas usam área mínima 48, máxima 5000, polaridade clara e conectividade 8.
As áreas são medidas em pixels da região segmentada. Os parâmetros completos
e os objetivos de cada configuração estão no plano.

São os mesmos **178 quadros**, ordem, hashes e duas exclusões das rodadas
anteriores: **3.204 avaliações de imagem**. Para repetir a rodada já executada:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round4
```

As saídas ficam em `resultados/frame-to-frame/limiarizacao/round4/`, com
relatório PDF automático ao concluir. A lista é determinística, sem sorteio;
a seed 42 permanece como registro. Para repetir, use o mesmo plano salvo.
`preparar_rodada.py` não reconstrói essa lista. **Sem argumentos, o executor
continua usando round1**, por isso informe `--rodada round4`.

A [revisão dos resultados](../../analise/rodadas/round4_revisao.md) orientou
o plano do round5. O plano e os resultados do round4 permanecem preservados.

## Terceira rodada em batch — anterior

O plano [round3.json](rodadas/round3.json) contém **24 configurações** definidas
após a [revisão do round2](../../analise/rodadas/round2_revisao.md). Compara
referências anteriores e ajustes de filtros, morfologia e limiar manual,
mantendo os limites de classe das respectivas referências. Os parâmetros
completos e os objetivos estão no plano.

Todas usam os mesmos **178 quadros**, ordem, hashes e exclusões das rodadas
anteriores: **4.272 avaliações de imagem**. Para repetir a rodada já executada:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round3
```

As saídas ficam em `resultados/frame-to-frame/limiarizacao/round3/`, com
relatório PDF automático ao concluir. A lista é determinística, sem sorteio;
a seed 42 permanece como registro. Para repetir, use o mesmo plano salvo.
`preparar_rodada.py` não reconstrói essa lista. **Sem argumentos, o executor
continua usando round1**, por isso informe `--rodada round3`.

A [revisão dos resultados](../../analise/rodadas/round3_revisao.md) orientou
o plano do round4. O plano e os resultados do round3 permanecem preservados.

## Segunda rodada em batch — anterior

O plano [round2.json](rodadas/round2.json) contém **32 configurações** definidas
após a [revisão do round1](../../analise/rodadas/round1_revisao.md). Duas repetem
referências do round1; as demais comparam filtros, limites de classificação,
morfologia e limiares manuais. Os parâmetros completos e a finalidade de cada
configuração estão no plano.

São os mesmos **178 quadros**, na mesma ordem e com os mesmos hashes e
exclusões: **5.696 avaliações de imagem**. Para repetir a rodada já executada:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round2
```

As saídas seguem a estrutura descrita abaixo, em
`resultados/frame-to-frame/limiarizacao/round2/`, com PDF ao concluir.
O plano é uma lista determinística, sem sorteio; a seed 42 permanece apenas
como registro. Repita pelo JSON salvo: `preparar_rodada.py` não reconstrói
essa rodada. Seus resultados orientaram o round3.

## Primeira rodada em batch — anterior

O plano `scripts/limiarizacao/rodadas/round1.json` contém as 48 configurações
completas da primeira rodada, geradas com seed **42**. São 24 manuais e 24 Otsu,
com 12 configurações por combinação de método e polaridade. A configuração
`c01` repete os parâmetros do teste inicial como referência.

Todas usam os mesmos **178 quadros anotados** dos 12 vídeos de desenvolvimento.
Os quadros 900 e 1100 do vídeo 23 foram explicitamente excluídos por ausência
de anotação, conforme acordado; não são tratados como imagens sem objetos.
As demais imagens seguem os quadros 0, 100, ..., 1400. São 8.544 avaliações de
imagem, com uma comparação PNG por avaliação. Reserve espaço para essas mídias.

Para repetir a rodada já executada, abra o terminal na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round1
```

Um único executor atende às rodadas: `--rodada round1` carrega
`scripts/limiarizacao/rodadas/round1.json`. Sem argumentos, também usa `round1`.
`--rodada round2`, `--rodada round3`, `--rodada round4` e `--rodada round5`
carregam os respectivos planos salvos.
Para usar um plano em outro local, informe `--plano` em vez de `--rodada`.
Caso falte alguma dependência,
instale no mesmo Python e repita o comando:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
```

O PDF utiliza Matplotlib e ReportLab. O executor verifica essas dependências
antes de iniciar as detecções. A instalação e as execuções são realizadas
pelo pesquisador no mesmo ambiente Python.

O executor confere o plano e os hashes das entradas antes de detectar. Durante
o processamento, verifica novamente o conteúdo de cada entrada. Um arquivo
alterado, ausente ou inválido interrompe a execução; não há exclusão automática.
Os vídeos de seleção e avaliação final não são aceitos neste executor.

Cada configuração produz detecções e calcula as métricas já acordadas: IoU
>= 0,50, associação única por classe, precisão, recall, F1, macro-F1 e análise
auxiliar de localização. Os resultados são agregados somando TP/FP/FN antes
de calcular F1. Não se calcula a média dos F1 dos quadros.

```text
resultados/frame-to-frame/limiarizacao/round1/
├── batch__<data-hora-UTC>/
│   ├── rodada.json
│   ├── execucao.json
│   ├── codigo.zip
│   ├── resumo_configuracoes.csv
│   ├── resumo_por_video.csv
│   └── relatorios/<data-hora-UTC>/
│       ├── relatorio.pdf
│       ├── relatorio.json
│       └── execucao_origem.json
└── <configuracao>__<data-hora-UTC>/
    ├── configuracao.json
    ├── execucao.json
    ├── deteccoes.csv
    ├── anotacoes.csv
    ├── por_quadro.csv
    ├── metricas_por_quadro.csv
    ├── metricas_por_video.csv
    ├── metricas.csv
    ├── avaliacao.json
    ├── pares.csv
    ├── pendentes.csv
    ├── predicoes/<video>_frame_<quadro>.txt
    └── midia/<video>_frame_<quadro>__comparacao.png
```

`resumo_configuracoes.csv` reúne os resultados das configurações concluídas,
na ordem do plano. `resumo_por_video.csv` permite verificar a variação entre
vídeos. O script não escolhe automaticamente configurações para a próxima
rodada nem as cinco finalistas. As decisões serão tomadas com o pesquisador.

Para consultar o resultado principal, abra `resumo_configuracoes.csv` e
localize a coluna `macro_f1`. Os F1 por classe estão em `f1_classe_0`,
`f1_classe_1` e `f1_classe_2`. `f1_localizacao` é o diagnóstico que ignora a
classe, não a métrica principal. `configuracao_id` identifica o teste e
`pasta` indica onde estão seus parâmetros, tabelas detalhadas e imagens.

`pares.csv` e `pendentes.csv` distinguem as avaliações principal e auxiliar
pela coluna `avaliacao`. Índices de objetos valem somente para o respectivo
vídeo/quadro. F1 sem casos fica vazio nos CSV, com situação `sem_casos`; no
JSON, fica `null`. As coordenadas e áreas continuam em pixels.

O tempo registrado mede uma chamada ao detector por imagem, sem cache de
detecções; exclui leitura, avaliação e gravação. OpenCV usa uma thread e
OpenCL desativado. Essa medição é diagnóstica, varia entre execuções e não
implementa ainda o desempate por desempenho.

### Relatório PDF automático

Ao concluir o batch, o executor gera o relatório a partir das tabelas salvas.
Para até 48 configurações e 12 vídeos, o PDF apresenta três páginas: macro-F1 de todas as
configurações, F1 das três classes e macro-F1 por vídeo. A ordenação visual
facilita a leitura e não seleciona as cinco finalistas.

As estatísticas descritivas mostram média, mediana, desvio padrão amostral,
mínimo, máximo e quantidade de valores definidos entre as configurações.
Não representam intervalo de confiança nem prova de superioridade. Não se
calcula a média dos F1 dos quadros para obter o F1 de uma configuração.
Valores `sem_casos` continuam distintos de zero.

Cada geração cria `relatorios/<data-hora-UTC>/`, sem sobrescrever PDFs
anteriores. `relatorio.json` registra a geração e `execucao_origem.json`
preserva o registro da execução utilizada. O estado do relatório fica
separado do estado da detecção: uma falha no PDF preserva as métricas já
concluídas. É possível gerar o relatório depois, sem repetir o batch.

Para a primeira rodada já executada, instale as dependências do relatório e
gere somente o PDF, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\avaliacao\gerar_relatorio_rodada.py" --batch ".\resultados\frame-to-frame\limiarizacao\round1\batch__20260919T192640642218Z"
```

Para outra execução, substitua o caminho de `--batch` pela pasta que contém
`resumo_configuracoes.csv` e `resumo_por_video.csv` daquela execução. Não
informe a pasta inteira do `round` nem a pasta de uma configuração isolada.
Os PDFs das cinco rodadas foram gerados e conferidos. A adaptação à seleção
foi revisada estaticamente; seu primeiro PDF depende da execução pelo pesquisador.

### Repetição e seed

Para repetir a primeira rodada, execute o mesmo comando. O programa lê as
configurações já salvas; não faz novo sorteio nem preenche parâmetros com base
nos resultados anteriores. A pasta `round1` é preservada e recebe novas
execuções com data/hora distinta. Uma falha preserva os arquivos parciais e
marca a execução como `falhou`; repetir começa uma execução completa, sem
retomar ou misturar dados parciais.

Também é possível repetir a cópia do plano guardada em um batch:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --plano ".\resultados\frame-to-frame\limiarizacao\round1\batch__<data-hora-UTC>\rodada.json"
```

A seed controla a geração das combinações da exploração inicial; manual e Otsu não sorteiam novos
parâmetros durante a detecção. O plano guarda configurações, ordem dos quadros
e hashes de imagens/anotações. A execução guarda versões, hashes do código e
uma cópia dos fontes em `codigo.zip`. Reproduzir resultados requer conservar
as entradas, o código e o ambiente, não apenas a seed; horários e tempos de
processamento naturalmente diferem.

`preparar_rodada.py` permite reconstruir o sorteio inicial sem executar
detectores, mas **não é necessário para executar planos já preparados** e
**não reconstrói round2, round3, round4 ou round5**, definidos a partir das análises:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\preparar_rodada.py" --seed 42 --rodada round1 --saida "scripts/limiarizacao/rodadas/round1_reproduzida.json"
```

O plano da primeira rodada foi apenas movido para `rodadas/round1.json`,
sem alterar seu conteúdo. O caminho e o hash do gerador permanecem como
registro histórico da preparação original. O gerador atual está em
`preparar_rodada.py`; novos planos registram a versão atual. Para repetir a
rodada existente, use `executar_rodada.py` com o plano salvo.

O gerador exige um arquivo novo, não sobrescreve planos e registra sua versão
e a versão do Python. Seu espaço é o da exploração inicial. Round2, round3,
round4 e round5 usam listas determinísticas já salvas e executadas.
Seus resultados foram revisados antes de preparar a seleção.

| Parâmetro explorado | Valores da primeira rodada |
|---|---|
| Limiar manual | 60, 90, 120, 150, 180, 210; cada um duas vezes por polaridade |
| Polaridade | Claro e escuro |
| Abertura e fechamento | Desativados, elipse 3 × 3 ou 5 × 5 com uma iteração |
| Área mínima | 1, 3, 6, 12, 24 pixels |
| Máximo da classe pequena | 20, 40, 80, 120 pixels |
| Mínimo da classe aglomerado | 150, 250, 400, 600, 1000 pixels |
| Fixos | Conectividade 8; sem área máxima |

Os valores são hipóteses exploratórias. Não foram escolhidos por desempenho.
A amostragem é sem configurações duplicadas e preserva uma faixa possível
para a classe pequena (`area_minima <= area_maxima_pequeno`).

### Testes do código

O código foi conferido estaticamente. A execução do batch e dos testes cabe
ao pesquisador. Testes sintéticos de agregação e integridade do plano:

```powershell
& "C:\Python313\python.exe" -m unittest analise.test_avaliacao_deteccao analise.test_agregacao_deteccao scripts.testes.test_plano_limiarizacao scripts.testes.test_selecao_limiarizacao
```

## Execução individual em imagem

`inspecionar_imagem.py` recebe uma imagem, sua anotação e uma configuração.
Executa a variante manual ou Otsu e grava uma comparação visual e tabelas.
As execuções serão feitas pelo pesquisador. O script foi revisado estaticamente
e o pesquisador realizou uma primeira inspeção individual do quadro 0 do vídeo 11.
O resultado dessa inspeção não valida o detector experimentalmente.

As primeiras inspeções devem usar imagens do conjunto de desenvolvimento.
O script registra `inspecao_individual`, não atribui automaticamente a entrada
a um conjunto do protocolo e não bloqueia arquivos de outros conjuntos.

Não calcula IoU, precisão, recall ou F1, não escolhe parâmetros e não executa
lotes, vídeos ou seleção das melhores configurações. As contagens exportadas
descrevem as saídas; não representam acertos.

Para calcular as métricas de uma execução já salva, use o script separado
[`avaliacao/avaliar_imagem.py`](../avaliacao/avaliar_imagem.py), descrito em
[`analise/README.md`](../../analise/README.md).
Não é necessário repetir a detecção. O avaliador foi escrito e revisado
estaticamente; sua execução e a dos testes sintéticos cabem ao pesquisador.

## Preparação

Abra o terminal na raiz do projeto. É necessário Python 3.10 ou posterior.
Use o mesmo ambiente Python na instalação e na execução:

```powershell
python -m pip install -r algoritmos/classicos/requirements.txt
```

Copie `scripts/configuracoes/limiarizacao.modelo.json` para
`scripts/configuracoes/minha_configuracao.json` e preencha os campos. O modelo
foi originalmente entregue incompleto e pode ter sido preenchido localmente
para a primeira inspeção. Os valores usados nessa inspeção são provisórios.
O script informa campos obrigatórios ainda nulos e interrompe a execução.
JSON não aceita comentários; textos precisam de aspas duplas.

| Campo | Preenchimento |
|---|---|
| `metodo` | `"manual"` ou `"otsu"` |
| `polaridade` | `"claro"` seleciona pixels acima do limiar; `"escuro"`, até o limiar |
| `limiar_manual` | Inteiro de 0 a 255 para manual; `null` para Otsu |
| `abertura.forma`, `fechamento.forma` | `"elipse"`, `"retangulo"` ou `"cruz"` |
| `abertura.tamanho`, `fechamento.tamanho` | Inteiro positivo ímpar; largura e altura do elemento em pixels |
| `abertura.iteracoes`, `fechamento.iteracoes` | Inteiro não negativo; zero desativa a respectiva operação |
| `conectividade` | 4 ou 8 |
| `area_minima` | Inteiro positivo; regiões menores são descartadas |
| `area_maxima` | Inteiro maior ou igual à área mínima; `null` desativa o limite superior |
| `classificacao.area_maxima_pequeno` | Inteiro positivo; até esse valor, inclusive, classe 2 |
| `classificacao.area_minima_aglomerado` | Inteiro pelo menos duas unidades acima do limite pequeno; a partir dele, classe 1 |

Os campos de forma e tamanho precisam ser preenchidos mesmo quando a operação
está desativada. Somente `limiar_manual` em Otsu e `area_maxima` sem limite
superior podem permanecer `null`. A faixa intermediária da classificação é a
classe 0. As áreas se referem aos pixels da região após a morfologia.

Os valores serão discutidos e avaliados no conjunto de desenvolvimento.
Preencher uma configuração não significa que ela está calibrada ou validada.

## Comando

Após preencher a configuração, este comando utiliza o quadro 0 do vídeo 11,
pertencente ao conjunto de desenvolvimento:

```powershell
python scripts/limiarizacao/inspecionar_imagem.py --imagem "bases_de_dados/visem_tracking/dataset/Train/11/images/11_frame_0.jpg" --anotacao "bases_de_dados/visem_tracking/dataset/Train/11/labels/11_frame_0.txt" --config "scripts/configuracoes/minha_configuracao.json"
```

Para consultar os argumentos sem executar o detector:

```powershell
python scripts/limiarizacao/inspecionar_imagem.py --help
```

Os caminhos de entrada relativos são interpretados a partir da pasta atual
do terminal. Caminhos com espaços devem ficar entre aspas. A saída sempre
fica na pasta `resultados/` deste projeto, independentemente da pasta do terminal.

A imagem deve ser uint8 em cinza ou BGR com três canais. A leitura preserva a
orientação armazenada dos pixels, sem aplicar rotação automática por EXIF.
Imagens com transparência ou profundidade diferente de 8 bits são rejeitadas.

A anotação deve vir de `labels/`, com cinco campos por linha:

```text
class_id center_x center_y width height
```

Imagem e anotação devem ter o mesmo nome-base, como `11_frame_0`. Essa conferência
evita trocas de nomes, mas não verifica visualmente se os arquivos correspondem.
As classes aceitas são 0, 1 e 2. As coordenadas precisam ser finitas e normalizadas,
com caixas de tamanho positivo dentro da imagem. Há tolerância de `1e-8` apenas
para arredondamento decimal nas bordas. As coordenadas originais são preservadas
na tabela; a conversão para pixels inteiros ocorre somente no desenho.

Arquivo de anotação existente e vazio é aceito como zero anotações. Arquivo
ausente interrompe a execução; nunca é convertido implicitamente em vazio.
Arquivos de `labels_ftid/`, com seis campos, são rejeitados neste script.

## Resultados

```text
resultados/frame-to-frame/limiarizacao/
└── round0/<resumo>__cfg-<hash>__<data-hora-UTC>/
    ├── configuracao.json
    ├── execucao.json
    ├── deteccoes.csv
    ├── anotacoes.csv
    ├── predicoes.txt
    ├── por_quadro.csv
    └── midia/
        └── <imagem>__comparacao.png
```

- **Comparação:** anotações à esquerda e detecções à direita, sem redimensionar
  a imagem. As mesmas cores e números identificam as classes nos dois painéis.
  A legenda e as contagens aparecem acima das imagens. Caixas sobrepostas
  permanecem presentes; não há remoção de duplicidades da anotação.
- **`configuracao.json`:** configuração completa efetivamente entregue ao detector,
  no mesmo formato aceito em `--config`; pode ser reutilizada.
- **`execucao.json`:** situação, horários UTC, origem, hashes dos arquivos de
  entrada, configuração, código, commit quando disponível, versões e unidades.
  Os hashes dos arquivos Python identificam também alterações ainda não commitadas.
- **`deteccoes.csv`:** uma linha por detecção, com classe, caixa em pixels e
  normalizada, centroide, áreas, alongamento da caixa, ocupação e intensidade.
- **`anotacoes.csv`:** uma linha por anotação, incluindo a linha de origem e
  as coordenadas normalizadas originais e convertidas para pixels.
- **`predicoes.txt`:** previsões no formato de cinco campos usado em `labels/`.
- **`por_quadro.csv`:** resumo da imagem, contagens totais e por classe e limiar usado.

As tabelas têm cabeçalho mesmo quando não há objetos. O resumo mantém uma linha
para a imagem, inclusive com zero detecções. Os CSV usam vírgula como separador,
ponto decimal e UTF-8 com BOM. No Excel, se necessário, use a importação
**Dados → De Texto/CSV** e selecione vírgula como delimitador.

O script individual usa `round0` por padrão. Para atribuir a inspeção a outra
rodada, informe `--rodada round1`, por exemplo. Ele não move resultados antigos.

O padrão `<video>_frame_<quadro>` do nome da imagem permite registrar a origem
do quadro. Para outros nomes, vídeo e quadro ficam vazios. Tempo em segundos
permanece vazio: este script não conhece a taxa de quadros. O índice da detecção
vale apenas dentro da imagem e não representa identidade entre quadros.

O resumo do nome inclui variante, polaridade e morfologia. `ab` significa
abertura; `fe`, fechamento; `e`, elipse; `r`, retângulo; `c`, cruz. Após a forma,
aparecem tamanho e iterações, separados por `x`. O hash usa todos os parâmetros,
inclusive os limites de área, evitando depender de nomes excessivamente longos.
São usados 12 caracteres do hash no nome e o SHA-256 completo nos metadados.
A data UTC inclui microssegundos. Uma colisão interrompe a execução sem sobrescrever.

Uma pasta só está completa quando `execucao.json` indica `"situacao": "concluida"`.
Falhas tratadas ficam registradas como `"falhou"`; encerramento abrupto pode
deixar `"em_andamento"`. Arquivos parciais são preservados para diagnóstico.
Os horários registrados não constituem uma medição de desempenho do detector.

Os arquivos originais são somente lidos. As anotações não são passadas ao
detector; servem à comparação visual e à exportação da referência.
