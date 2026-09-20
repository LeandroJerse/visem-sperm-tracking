# Round5 e encerramento do desenvolvimento da limiarização

Análise dos resultados de desenvolvimento; seleção ainda não executada.

## Conferência da execução

Batch: `resultados/frame-to-frame/limiarizacao/round5/batch__20260920T010415641826Z`.
Execução concluída pelo pesquisador em 19/09/2026, às 22:06:16 de Brasília.

- 14 configurações × 178 quadros = **2.492 avaliações** concluídas.
- Plano executado idêntico ao preparado; hashes do código arquivado,
  configurações, fontes e 358 arquivos originais conferidos.
- Presentes 2.492 previsões, 2.492 imagens comparativas, tabelas e registros.
- Contagens por quadro, por vídeo e totais consistentes com as métricas.
- Os 1.013 macro-F1 indefinidos por quadro seguem a regra de classe sem casos.
- PDF concluído, com três páginas e fontes conferidas.
- Controles reproduzidos exatamente, desconsiderando tempos:
  `c01 = round4/c07`, `c02 = round4/c09`, `c03 = round4/c01` e `c04 = round4/c18`.

Fontes: [resumo das configurações](../../resultados/frame-to-frame/limiarizacao/round5/batch__20260920T010415641826Z/resumo_configuracoes.csv),
[resumo por vídeo](../../resultados/frame-to-frame/limiarizacao/round5/batch__20260920T010415641826Z/resumo_por_video.csv)
e [PDF](../../resultados/frame-to-frame/limiarizacao/round5/batch__20260920T010415641826Z/relatorios/20260920T010616636381Z/relatorio.pdf).
Esta revisão usa resultados salvos, sem executar novamente o detector.

## Resultado e origem do ganho

| Resultado | Melhor round4: c07 | Melhor round5: c06 |
|---|---:|---:|
| Macro-F1 | 0,237044 | **0,238522** |
| F1 normal | 0,458260 | 0,458535 |
| F1 aglomerado | 0,244068 | 0,248227 |
| F1 pequeno | 0,008803 | 0,008803 |
| F1 de localização, ignorando classe | 0,417590 | 0,417590 |

`round5/c06` usa Otsu claro, abertura desligada, fechamento retangular 5×5
com uma iteração, conectividade 8, área entre 48 e 5.000 pixels, pequeno
até 120 pixels e aglomerado a partir de 925 pixels. O limite de aglomerado
era 900 em `round4/c07`; os demais parâmetros são idênticos.

| Classe | TP antes → depois | FP antes → depois | FN antes → depois |
|---|---:|---:|---:|
| Normal | 1.699 → 1.703 | 2.252 → 2.261 | 1.765 → 1.761 |
| Aglomerado | 36 → 35 | 150 → 138 | 73 → 74 |
| Pequeno | 5 → 5 | 997 → 997 | 129 → 129 |

O ganho é **0,001478 de macro-F1**, aproximadamente **0,62% relativo**.
Resulta de uma troca de rótulos nas mesmas caixas: menos falsos positivos
de aglomerado, com perda de um acerto dessa classe e mudanças nos normais.
Não houve melhoria de localização: continuam 1.847 TP, 3.292 FP e 1.860 FN
na avaliação auxiliar.

O ganho não é uniforme. Entre os dez vídeos com macro-F1 definido nas duas
configurações, melhora em dois (19 e 35), piora em três (11, 22 e 36) e
empata em cinco. Nos vídeos 30 e 60 permanece indefinido. O único TP de
aglomerado no vídeo 11 foi perdido; os 35 restantes estão no vídeo 19.
Os cinco TP pequenos permanecem concentrados no vídeo 21.

O limite 875 (`c05`) teve macro-F1 0,234546. As oito novas variações manuais
não superaram o controle manual 112 com fechamento elíptico 7 (`c04`,
macro-F1 0,198801). Ajustar limiar ou forma de fechamento não produziu
uma nova melhoria manual nessa rodada.

## Balanço das cinco rodadas

| Rodada | Configurações executadas | Melhor macro-F1 |
|---|---:|---:|
| round1 | 48 | 0,224303 |
| round2 | 32 | 0,233460 |
| round3 | 24 | 0,235414 |
| round4 | 18 | 0,237044 |
| round5 | 14 | 0,238522 |

Foram 136 execuções de configuração, correspondentes a **122 configurações
distintas** e 24.208 avaliações de imagem. As 14 repetições são controles,
não novas configurações nem observações independentes. A equivalência
ignora apenas forma/tamanho das operações morfológicas desativadas, conforme
a regra já usada pelo executor. As repetições possuem métricas iguais.

O [resumo completo](desenvolvimento_resumo.json) preserva parâmetros, origens,
métricas e hashes das fontes. As primeiras posições no desenvolvimento são:

| Origem | Macro-F1 |
|---|---:|
| round5/c06 | 0,238522 |
| round4/c07, repetida em round5/c01 | 0,237044 |
| round4/c08 | 0,236360 |
| round4/c05 | 0,236113 |
| round4/c06 | 0,235432 |

**Essas cinco posições ainda não são as finalistas.** São variações muito
próximas de Otsu com fechamento retangular 5. Escolhê-las diretamente aqui
usaria os mesmos dados que orientaram seus ajustes. O melhor manual das
cinco rodadas continua sendo `round4/c18`, repetido em `round5/c04`.

## Por que encerrar agora

Recomenda-se encerrar as cinco rodadas previstas, sem round6. Os refinamentos
recentes produziram ganhos pequenos, principalmente na classificação das
mesmas caixas. A localização e a classe pequeno continuam limitantes.
Refinar ainda mais os limites nos mesmos quadros pode ajustar detalhes
específicos dessas amostras sem benefício em outros vídeos.

Essa decisão respeita o orçamento planejado e o padrão observado; não é um
teste estatístico de convergência nem prova de que nenhum parâmetro melhor
exista. Os máximos foram encontrados após examinar os mesmos dados, com
quantidades diferentes de configurações. Não estimam generalização.
**Há evidência suficiente para avançar na comparação, mas o desempenho
atual não permite considerar a limiarização um detector validado.**

## Seleção aprovada

Após a revisão, o pesquisador aprovou preparar a comparação das **122
configurações distintas**, sem novo ajuste, nos **60 quadros** dos vídeos
13, 29, 52 e 54: 0, 100, ..., 1400 de cada vídeo. Todos os pares de imagem
e anotação estão presentes; não há exclusões nessa seleção.

Após fixar as candidatas, a conferência das anotações dos 60 quadros
identificou 1.305 caixas: 1.200 normais, 45 aglomerados e 60 pequenos.
As três classes possuem suporte no conjunto completo. Essas contagens
não foram usadas para alterar parâmetros ou retirar candidatas.

O [plano de seleção](../../scripts/limiarizacao/selecao/plano.json) fixa
parâmetros, origem nas rodadas anteriores, IDs `s001` a `s122`, ordem dos
quadros e hashes. Os IDs seguem a primeira ocorrência nas rodadas, sem
usar o desempenho para ordenar a execução. São **7.320 avaliações**.
As reavaliações exploratórias de caixas, registradas separadamente, não
acrescentam configurações ao conjunto aprovado das cinco rodadas.

Permanece o macro-F1 calculado após somar TP, FP e FN dos 60 quadros por
classe, com mesma classe, IoU ≥ 0,50 e correspondência um para um.
O F1 normal desempata somente macro-F1 exatamente igual, antes do
arredondamento. Não se adicionam pesos, média dos F1 por vídeo ou tempo
como critério. Empates remanescentes e métricas indefinidas são apresentados
para revisão conjunta; o script não decide esses casos silenciosamente.

O pesquisador executará:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_selecao.py"
```

As saídas ficam em `resultados/frame-to-frame/limiarizacao/selecao/`, com
tabelas, imagens e PDF. Depois de examinar esses resultados, serão escolhidas
as cinco configurações para os vídeos completos do conjunto de seleção.
Não serão usados os resultados da seleção para criar novos parâmetros.

O processamento em vídeo ainda será preparado após essa escolha. Avaliará
detecções quadro a quadro, sem rastreamento nem inferência de velocidade.
Antes da comparação com anotações, será necessário conferir correspondência
entre quadros do MP4, imagens e rótulos. A avaliação final nos vídeos
14, 24, 38 e 82 permanece posterior ao congelamento das escolhas. A reserva
atual dos conjuntos não apaga sua exposição histórica em versões anteriores.

## Arquivos preparados e conferências

Novos arquivos:

- `scripts/limiarizacao/executar_selecao.py`: entrada específica da seleção.
- `scripts/limiarizacao/selecao/plano.json`: candidatas e entradas fixadas.
- `scripts/testes/test_selecao_limiarizacao.py`: verificações da composição,
  origem das configurações e recusa de alterações no protocolo.
- `analise/rodadas/desenvolvimento_resumo.json`: consolidação das cinco rodadas.
- `analise/rodadas/round5_revisao.md`: esta análise.

Arquivos adaptados:

- `scripts/limiarizacao/executar_rodada.py`: compartilha o processamento,
  mantendo seu validador de desenvolvimento e seus comandos anteriores.
- `analise/relatorio_rodada.py`: aceita e identifica relatórios da seleção.
- `.gitattributes`: preserva os bytes dos novos planos JSON no Git.
- Guias atualizados: `README.md`, `algoritmos/classicos/README.md`,
  `analise/README.md`, `analise/protocolo_rodadas.md`, `scripts/README.md`
  e `scripts/limiarizacao/README.md`.

A preparação confere hashes, composição, parâmetros e origens, além de
revisão estática do código. O executor de desenvolvimento continua restrito
aos quadros originais; o de seleção exige os 60 quadros e as 122 candidatas
acordadas. Os testes novos foram escritos, mas sua execução, a seleção e
a conferência do primeiro PDF dessa etapa ficam com o pesquisador.
Os comandos dos testes estão no guia de limiarização. Os arquivos originais
da base e os resultados anteriores foram preservados.
