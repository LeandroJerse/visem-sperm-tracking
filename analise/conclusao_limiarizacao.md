# Conclusão dos experimentos de limiarização

## Resultado principal

O ciclo de desenvolvimento e avaliação da limiarização foi concluído. Nas
cinco configurações congeladas, os maiores F1 de indivíduos nos vídeos finais
foram **0,566796**, para `s099` e `s101`, ambas com Otsu e fechamento retangular
5×5. Nos vídeos de seleção, o maior F1 havia sido **0,257230**, para `s068`,
com limiar manual 90. Essa inversão de posições evidencia a dependência do
resultado em relação aos vídeos utilizados.

O desempenho final não permite considerar resolvida a detecção das três
classes: `s099` e `s101` não localizaram nenhuma das 2.936 ocorrências de
pequenos anotadas, e seu F1 de aglomerados foi 0,009006. O resultado serve
como referência experimental para os próximos detectores, com essas
limitações explicitadas.

**O ranking final é descritivo.** Ele não transforma a configuração com
maior F1 final em uma escolha feita antes do teste, não estabelece
superioridade estatística e não fundamenta novos ajustes usando os resultados finais.
O conjunto avaliado permanece o das cinco configurações aprovadas.

## Escopo e fontes

Foram comparadas caixas de detecção com as caixas anotadas na base
VISEM-Tracking. Permanecem os rótulos originais: **0 — normal**,
**1 — aglomerado** e **2 — pequeno (`small_or_pinhead`)**. A análise considera
ocorrências nos quadros; não conta indivíduos únicos ao longo do vídeo nem
avalia rastreamento, velocidade ou comportamento.

As fontes principais desta síntese são:

- [Resumo das cinco rodadas](rodadas/desenvolvimento_resumo.json) e
  [revisão do round5](rodadas/round5_revisao.md).
- [Plano das 122 candidatas](../scripts/limiarizacao/selecao/plano.json).
- [Seleção em imagens, reavaliada por indivíduos — resumo CSV](../resultados/frame-to-frame/limiarizacao/selecao/batch__20260920T012713968145Z/reavaliacoes_individuos/20260920T021112218814Z/resumo_configuracoes.csv).
- [Seleção em vídeos — resumo CSV](../resultados/videos/limiarizacao/selecao/batch__20260920T023832151694Z/resumo_configuracoes.csv).
- [Vídeos finais — resumo CSV](../resultados/videos/limiarizacao/final/batch__20260920T030805588232Z/resumo_configuracoes.csv),
  [resultados por vídeo](../resultados/videos/limiarizacao/final/batch__20260920T030805588232Z/resumo_por_video.csv)
  e [ranking](../resultados/videos/limiarizacao/final/batch__20260920T030805588232Z/ranking.csv).
- [Plano final congelado](../scripts/limiarizacao/videos/plano_final.json),
  [manifesto da execução final](../resultados/videos/limiarizacao/final/batch__20260920T030805588232Z/execucao.json)
  e [PDF final](../resultados/videos/limiarizacao/final/batch__20260920T030805588232Z/relatorios/20260920T032102344806Z/relatorio.pdf).

Os CSVs e manifestos preservam a precisão original; as tabelas deste documento
usam arredondamento somente para apresentação. Os resultados e a base de
dados ficam fora do Git; os links dependem desses arquivos locais. O
[README principal](../README.md) descreve as dependências de reprodução.

## Percurso experimental

### Desenvolvimento em imagens

As cinco rodadas utilizaram os mesmos **178 quadros anotados** dos vídeos
11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47 e 60. Foram previstos os índices
0, 100, ..., 1400; os quadros 900 e 1100 do vídeo 23 foram excluídos por
ausência de anotação. Todas as configurações receberam a mesma composição.

| Rodada | Configurações executadas | Avaliações de imagem | Maior macro-F1 histórico |
|---|---:|---:|---:|
| [round1](../resultados/frame-to-frame/limiarizacao/round1/batch__20260919T192640642218Z/resumo_configuracoes.csv) | 48 | 8.544 | 0,224303 |
| [round2](../resultados/frame-to-frame/limiarizacao/round2/batch__20260919T203029199281Z/resumo_configuracoes.csv) | 32 | 5.696 | 0,233460 |
| [round3](../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/resumo_configuracoes.csv) | 24 | 4.272 | 0,235414 |
| [round4](../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/resumo_configuracoes.csv) | 18 | 3.204 | 0,237044 |
| [round5](../resultados/frame-to-frame/limiarizacao/round5/batch__20260920T010415641826Z/resumo_configuracoes.csv) | 14 | 2.492 | 0,238522 |
| Total | 136 | 24.208 | — |

As 136 execuções correspondem a **122 configurações distintas**; há 14
ocorrências adicionais de configurações equivalentes. A equivalência ignora
forma e tamanho de operações morfológicas desligadas. Repetições não constituem novas configurações nem
amostras independentes.

As rodadas posteriores foram orientadas pelos resultados anteriores,
mantendo seus planos e parâmetros explícitos. O ganho do melhor macro-F1
entre round4 e round5 foi 0,001478 e ocorreu com mudança do limite de
classificação nas mesmas caixas, conforme a revisão do round5. O encerramento
em cinco rodadas não demonstra que o espaço de parâmetros foi esgotado.

### Seleção, mudança de critério e congelamento

As 122 candidatas foram comparadas nos mesmos **60 quadros** dos vídeos
13, 29, 52 e 54, nos índices 0, 100, ..., 1400: 7.320 avaliações.
O critério histórico exigia mesma classe no pareamento, usava macro-F1 das
três classes e F1 normal somente em empate exato.

**Depois de observar essa seleção**, foi aprovada a separação entre
localização de indivíduos e classificação 0/2. As mesmas caixas salvas foram
reavaliadas, preservando os resultados históricos. Não houve nova detecção
nessa reavaliação. A alteração metodológica, portanto, foi posterior à
observação de resultados; não deve ser apresentada como decisão anterior
a todos os experimentos.

O F1 de indivíduos passou a orientar a comparação. Foram aprovadas `s068`,
`s067`, `s090`, `s099` e `s101`, incluindo o empate entre as duas últimas,
que ocupava as posições 4 e 5. Não havia empate atravessando o corte de cinco.

Essas cinco configurações foram executadas nos vídeos completos de seleção
13, 29, 52 e 54: **5.850 quadros por configuração**, totalizando 29.250
avaliações. Após a revisão, as mesmas cinco seguiram, sem alteração de
parâmetros ou critérios, para os vídeos finais 14, 24, 38 e 82:
**5.910 quadros por configuração**, totalizando 29.550 avaliações.

O macro-F1 histórico das rodadas e o F1 de indivíduos usado posteriormente
têm definições diferentes. Seus valores não formam uma única curva de
melhoria e não devem ser comparados como se medissem o mesmo resultado.

## Critério da avaliação em indivíduos

- Indivíduos agrupam as classes 0 e 2; aglomerados, classe 1, são avaliados
  separadamente.
- O pareamento é um para um, dentro do mesmo grupo, com IoU ≥ 0,50.
  Primeiro maximiza o número de pares válidos; depois, a soma das IoUs.
- Trocas 0↔2 contam como acertos de localização, com erro de classificação
  registrado separadamente. Trocas entre indivíduo e aglomerado geram perda
  no grupo anotado e falsa detecção no grupo previsto.
- TP são pares aceitos; FP são previsões sem par; FN são anotações sem par.
  As contagens são somadas antes de calcular precisão, recall e F1.
- `Precisão = TP/(TP+FP)`, `recall = TP/(TP+FN)` e
  `F1 = 2TP/(2TP+FP+FN)`. Não se faz média de F1 por quadro.
- F1 fica sem casos somente quando TP = FP = FN = 0. Se houver FP ou FN
  sem TP, F1 = 0. Outros denominadores nulos também permanecem indefinidos.
- A cobertura por classe é a fração das anotações da classe que recebeu
  par, mesmo com troca 0↔2. A acurácia condicional mede o rótulo correto
  somente entre os pares encontrados, excluindo FN e FP.

O ranking considera a fração exata do F1. Empates mantêm o mesmo posto;
o ID organiza apenas a apresentação. Não há peso adicional nem desempate
automático por outra métrica no critério atual.

## Parâmetros das cinco configurações

Todas usam polaridade clara, abertura desligada, conectividade 8 e uma
iteração de fechamento. O tamanho 3×3 registrado para a abertura não produz
efeito porque sua quantidade de iterações é zero.

| ID | Limiarização | Fechamento | Área mínima | Área máxima | Pequeno até | Aglomerado a partir de |
|---|---|---|---:|---:|---:|---:|
| s068 | Manual: 90 | Elipse 5×5 | 24 | Sem limite | 80 | 1.000 |
| s067 | Manual: 90 | Elipse 3×3 | 24 | Sem limite | 80 | 1.000 |
| s090 | Otsu | Retângulo 7×7 | 48 | 5.000 | 120 | 1.000 |
| s099 | Otsu | Retângulo 5×5 | 48 | 5.000 | 100 | 900 |
| s101 | Otsu | Retângulo 5×5 | 48 | 5.000 | 120 | 900 |

Os valores de área representam pixels da **região segmentada**, não a área
da caixa delimitadora. Os limites de retenção são inclusivos. Depois do
filtro, área menor ou igual ao limite de pequeno recebe classe 2; área maior
ou igual ao limite de aglomerado recebe classe 1; a faixa intermediária
recebe classe 0. Trata-se de uma hipótese operacional de classificação,
sem equivalência biológica demonstrada.

`s099` e `s101` diferem apenas no limite entre pequeno e normal. Mantêm as
mesmas caixas e o mesmo limite de aglomerado; por isso apresentam exatamente
as mesmas contagens de localização de indivíduos, com diferenças nos rótulos
0/2. Os parâmetros completos estão no plano final citado acima e a regra
está em [classificacao.py](../algoritmos/classicos/classificacao.py).

## Resultados comparados entre etapas

Todos os valores desta tabela são **F1 de indivíduos**, sob o critério atual.
A coluna de imagens corresponde à reavaliação das caixas, não ao macro-F1
da seleção original.

| Configuração | Seleção: 60 imagens | Seleção: vídeos completos | Final: vídeos completos |
|---|---:|---:|---:|
| s068 | 0,273511 | 0,257230 | 0,019524 |
| s067 | 0,257778 | 0,246072 | 0,020649 |
| s090 | 0,173576 | 0,163433 | 0,542395 |
| s099 | 0,172026 | 0,162946 | 0,566796 |
| s101 | 0,172026 | 0,162946 | 0,566796 |

As três colunas provêm dos respectivos resumos CSV listados nas fontes.
São configurações fixas aplicadas a entradas diferentes. A diferença entre
colunas não é ganho causado por treinamento ou novo ajuste. A seleção em
vídeos amplia os quadros dos mesmos quatro vídeos já usados em imagens;
não constitui uma amostra independente da seleção em imagens.

## Detalhamento dos vídeos finais

### Localização de indivíduos e aglomerados

| Configuração | TP indivíduos | FP indivíduos | FN indivíduos | Precisão | Recall | F1 indivíduos | F1 aglomerados |
|---|---:|---:|---:|---:|---:|---:|---:|
| s099 | 89.460 | 66.757 | 69.992 | 0,572665 | 0,561047 | 0,566796 | 0,009006 |
| s101 | 89.460 | 66.757 | 69.992 | 0,572665 | 0,561047 | 0,566796 | 0,009006 |
| s090 | 85.959 | 71.550 | 73.493 | 0,545740 | 0,539090 | 0,542395 | 0,007641 |
| s067 | 4.239 | 246.893 | 155.213 | 0,016880 | 0,026585 | 0,020649 | 0,047595 |
| s068 | 3.360 | 181.380 | 156.092 | 0,018188 | 0,021072 | 0,019524 | 0,022656 |

F1 = 0,566796 não significa que 56,68% dos objetos foram encontrados. Para
`s099`/`s101`, a fração dos indivíduos anotados que recebeu par é o recall,
0,561047; a fração de previsões de indivíduos com par é a precisão, 0,572665.
Mesmo as maiores pontuações mantêm quantidades expressivas de FP e FN.

### Variação por vídeo

| Vídeo | Quadros | Anotações normal / aglomerado / pequeno | F1 s099 e s101 | F1 s090 | F1 s067 | F1 s068 |
|---|---:|---|---:|---:|---:|---:|
| 14 | 1.470 | 5.029 / 721 / 0 | 0,372133 | 0,323680 | 0,000000 | 0,000000 |
| 24 | 1.470 | 91.596 / 5.880 / 0 | 0,536123 | 0,512030 | 0,044101 | 0,040427 |
| 38 | 1.470 | 16.832 / 0 / 0 | 0,894497 | 0,866137 | 0,000000 | 0,000000 |
| 82 | 1.500 | 43.059 / 0 / 2.936 | 0,553413 | 0,542487 | 0,002442 | 0,002307 |

Os F1 são de indivíduos. As duas configurações manuais não produziram
nenhum par de indivíduo nos vídeos 14 e 38. `s099`/`s101` variam de 0,372133
a 0,894497 entre os vídeos, embora seus parâmetros permaneçam iguais.
Essa observação não isola uma causa específica: iluminação, contraste,
conteúdo, segmentação e classificação exigiriam diagnósticos próprios para
atribuir responsabilidades. Não se conclui causalidade a partir do ranking.

### Cobertura das classes e classificação condicional

Cada configuração foi comparada com **156.516 ocorrências normais,
6.601 aglomerados e 2.936 pequenos**. As ocorrências de pequenos estão
concentradas no vídeo 82; os aglomerados, nos vídeos 14 e 24.

| Configuração | Normais localizados | Recall normal | Pequenos localizados | Recall pequeno | Aglomerados localizados | Recall aglomerado |
|---|---:|---:|---:|---:|---:|---:|
| s099 | 89.460 | 0,571571 | 0 | 0,000000 | 47 | 0,007120 |
| s101 | 89.460 | 0,571571 | 0 | 0,000000 | 47 | 0,007120 |
| s090 | 85.952 | 0,549158 | 7 | 0,002384 | 39 | 0,005908 |
| s067 | 4.239 | 0,027083 | 0 | 0,000000 | 1.158 | 0,175428 |
| s068 | 3.360 | 0,021467 | 0 | 0,000000 | 519 | 0,078624 |

| Configuração | Normal → normal | Normal → pequeno | Pequeno → normal | Pequeno → pequeno | Acurácia condicional |
|---|---:|---:|---:|---:|---:|
| s099 | 88.544 | 916 | 0 | 0 | 0,989761 |
| s101 | 86.602 | 2.858 | 0 | 0 | 0,968053 |
| s090 | 83.514 | 2.438 | 1 | 6 | 0,971626 |
| s067 | 4.239 | 0 | 0 | 0 | 1,000000 |
| s068 | 3.360 | 0 | 0 | 0 | 1,000000 |

Na matriz, a origem da seta é a anotação e o destino é a previsão, somente
entre indivíduos pareados. As duas manuais alcançam acurácia condicional
1,000000 porque classificam corretamente seus poucos pares; isso não
compensa a baixa localização nem as falsas detecções.

Entre as configurações empatadas em localização, `s099` tem 916 trocas 0/2,
contra 2.858 de `s101`. Essa diferença é um diagnóstico descritivo e não um
novo desempate introduzido após o teste. Nenhuma delas localizou pequenos.
`s090` localizou sete ocorrências pequenas, das quais seis receberam classe 2.
A quantidade é insuficiente para caracterizar a detecção de pequenos como
resolvida.

## Integridade e alcance da conferência

O batch final `batch__20260920T030805588232Z` registra conclusão das cinco
configurações. Foram conferidos, por leitura dos arquivos existentes:

- 5.910 índices únicos por configuração, sem lacunas: 1.470 para cada um
  dos vídeos 14, 24 e 38; 1.500 para o vídeo 82.
- 22 contagens por quadro, agregadas por vídeo e por configuração,
  compatíveis com os resumos; F1 consistente com TP, FP e FN.
- 5.944 hashes de arquivos de origem e 98 hashes de saídas, sem divergências.
- Arquivo de código com 15 entradas, hashes e integridade ZIP compatíveis
  com o manifesto.
- 20 MP4 presentes, totalizando 441.901.353 bytes. Os manifestos registram
  a conferência de decodificação realizada pelo executor durante a execução.
- Registro de alinhamento com 20 referências, cinco por vídeo: o índice
  previsto foi o mínimo único de erro registrado em todas elas. Isso é uma
  verificação técnica de alinhamento, não uma avaliação de detecção.
- PDF final existente e registrado como concluído, com três páginas no
  manifesto do relatório; suas quatro fontes e seu hash correspondem aos
  arquivos atuais.

Esta conferência não executou novamente o detector nem refez os pareamentos.
Também não decodificou novamente os MP4, não conferiu visualmente todos os
quadros e não renderizou o PDF final. A consistência e os hashes atestam o
registro da execução, sem equivaler a uma validação independente da
correção das anotações ou de todas as decisões do avaliador.

## Limitações metodológicas e uso como referência

1. **Dependência do vídeo.** A inversão entre manual e Otsu e a variação
   dentro da partição final impedem resumir o comportamento apenas pelo F1
   agregado. Não foi identificado um mecanismo causal único para as falhas.
2. **Poucas unidades de aquisição.** A avaliação final tem quatro vídeos.
   Milhares de quadros do mesmo vídeo são correlacionados e podem conter os
   mesmos indivíduos. As contagens não representam milhares de amostras
   independentes; não foram feitos testes de significância ou intervalos
   de confiança que sustentem superioridade estatística.
3. **Distribuição desigual.** Somar TP/FP/FN dá maior influência a vídeos e
   classes com mais ocorrências. O vídeo 24 concentra 91.596 das 156.516
   ocorrências normais. O desempenho agregado é dominado por normais, e não
   demonstra sucesso em pequenos ou aglomerados.
4. **Classe e localização continuam interagindo.** A tolerância à troca
   0/2 separa parte do problema, mas trocas entre indivíduo e aglomerado
   continuam impedindo o pareamento. O F1 atual não ignora toda classificação.
5. **Mudança de critério após observação.** A otimização das cinco rodadas
   usou o macro-F1 histórico; o critério de indivíduos foi adotado após a
   seleção original. O percurso é adaptativo e deve ser relatado como tal.
6. **Exposição histórica.** Os dados finais já tiveram uso na versão
   anterior do projeto, conforme o plano final. Reservá-los nesta versão
   não os torna historicamente inéditos. Agora seus resultados também são
   conhecidos; usá-los para orientar o próximo algoritmo limita qualquer
   futura alegação de teste intocado.
7. **Imagens e vídeo não são entradas idênticas.** Além da quantidade de
   quadros, mudam os arquivos JPEG e os quadros decodificados do MP4.
   O alinhamento verificado não implica igualdade dos pixels nem permite
   atribuir as diferenças de desempenho somente à compressão.
8. **Reprodução depende dos registros.** Seed, parâmetros explícitos,
   código arquivado e hashes auxiliam a reprodução, mas não substituem
   os dados e os manifestos históricos exigidos pelos planos congelados.

A limiarização permanece uma referência com ganhos locais e falhas
documentadas. O próximo detector pode ser comparado sob as mesmas
definições de saída e avaliação, com seu protocolo previamente definido.
Reutilizar os mesmos vídeos permite comparação pareada entre métodos, mas
deve preservar o histórico de exposição e não converter estes resultados
em um novo conjunto de teste supostamente inédito.
