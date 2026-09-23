# Análise da seleção de blobs em imagens

## Resultado e proposta para revisão

A seleção foi concluída em
`resultados/frame-to-frame/blobs/selecao/batch__20260921T011058635016Z`.
Foram comparadas **119 configurações distintas nos mesmos 60 JPEGs** dos
vídeos 13, 29, 52 e 54: **7.140 avaliações**, com parâmetros preservados.

Pelo critério acordado de **F1 de indivíduos**, a proposta para revisão
conjunta é **s052, s082, s084, s103 e s051**, nesta ordem. Ainda não há
plano de finalistas aprovado nem executor de vídeos de blobs preparado.
Nenhuma configuração foi alterada ou promovida automaticamente nesta análise.

| Posto | Configuração | Origem | Método | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | s052 | round2 / r2c08 | SimpleBlob | 908 | 544 | 352 | 0,625344 | 0,720635 | **0,669617** |
| 2 | s082 | round3 / r3c10 | SimpleBlob | 840 | 430 | 420 | 0,661417 | 0,666667 | **0,664032** |
| 3 | s084 | round3 / r3c12 | SimpleBlob | 840 | 436 | 420 | 0,658307 | 0,666667 | **0,662461** |
| 4 | s103 | round4 / r4c10 | DoG | 780 | 323 | 480 | 0,707162 | 0,619048 | **0,660178** |
| 5 | s051 | round2 / r2c07 | SimpleBlob | 862 | 590 | 398 | 0,593664 | 0,684127 | **0,635693** |
| 6 | s101 | round4 / r4c08 | DoG | 905 | 692 | 355 | 0,566688 | 0,718254 | 0,633532 |

**Não há empate exato entre a quinta e a sexta colocadas.** A diferença é
0,002162 de F1, ou 0,216 ponto percentual. Essa separação numérica resolve
a ordem pelo protocolo; não demonstra uma diferença estatisticamente estável
fora das imagens observadas. As contagens são somadas antes de calcular F1;
não se usa média dos F1 dos frames ou novo peso de classe.

## O que esse resultado permite afirmar

O melhor resultado de desenvolvimento, r5c06, corresponde a **s113** e ficou
em **11º**, com F1 de **0,611623** (TP 763, FP 472, FN 497). A primeira colocada
da seleção veio do round2. Comparar todas as configurações distintas, em vez
de levar somente as melhores do round5, permitiu observar essa mudança.

O maior F1 do desenvolvimento era 0,568779, em outro conjunto. A diferença
para 0,669617 na seleção não representa uma melhoria adicional do algoritmo:
mudaram os dados avaliados, enquanto os parâmetros permaneceram congelados.

Todas as cinco propostas usam objetos claros e nenhum CLAHE. Quatro usam
SimpleBlob e uma usa DoG. O melhor LoG foi s090, em 30º, com F1 de 0,454982.
O protocolo compara configurações e não reserva uma vaga para cada método.
Além disso, os esforços de busca foram diferentes: 84 SimpleBlob, 22 DoG e
13 LoG distintos; esse resultado não demonstra superioridade universal de
uma família de detectores.

## Limitações de cobertura e classificação

Há **1.200 ocorrências anotadas de normais, 60 de pequenos e 45 de aglomerados**
nos 60 frames. Ocorrências em frames diferentes não representam necessariamente
indivíduos biologicamente distintos, pois ainda não há rastreamento.

| Configuração | Normais localizados | Pequenos localizados | Aglomerados localizados | Erros de classe entre pares 0/2 | Acurácia de classe entre pares |
|---|---:|---:|---:|---:|---:|
| s052 | 901/1.200 | 7/60 | 0/45 | 7/908 | 99,23% |
| s082 | 833/1.200 | 7/60 | 0/45 | 7/840 | 99,17% |
| s084 | 833/1.200 | 7/60 | 0/45 | 7/840 | 99,17% |
| s103 | 778/1.200 | 2/60 | 0/45 | 571/780 | 26,79% |
| s051 | 857/1.200 | 5/60 | 0/45 | 5/862 | 99,42% |

Nas quatro SimpleBlob, os pequenos localizados receberam rótulo normal.
A acurácia condicional próxima de 99% é dominada pelos normais e não significa
boa distinção entre as duas classes. No DoG s103, as 571 trocas são normais
previstos como pequenos. Pela regra acordada, uma troca 0↔2 preserva o acerto
de localização e é registrada separadamente como erro de classificação.

Por isso, **s103 permanece na proposta pelo F1 de localização**. Excluí-la
agora somente por sua classificação mudaria a regra de seleção após observar
os resultados. A proposta mantém o critério e documenta o problema. Nenhuma
das cinco pode ser descrita como satisfatória nas três classes: a cobertura
de pequenos foi de 3,33% a 11,67%, e a de aglomerados foi nula.

A faixa DoG testada não alcança o diâmetro necessário para prever classe 1,
uma limitação já registrada no desenvolvimento. Os limites de área das
SimpleBlob também não devem ser confundidos com uma segmentação perfeita
da cabeça; a classificação usa área circular estimada dos candidatos.

## Variação entre vídeos

Cada vídeo contribuiu com 15 frames, mas com quantidades diferentes de objetos.

| Vídeo | Normais | Pequenos | Aglomerados | Total de indivíduos 0/2 |
|---|---:|---:|---:|---:|
| 13 | 625 | 15 | 0 | 640 |
| 29 | 44 | 0 | 5 | 44 |
| 52 | 140 | 35 | 10 | 175 |
| 54 | 391 | 10 | 30 | 401 |

O vídeo 13 contém 50,79% dos indivíduos anotados; os vídeos 13 e 54 juntos,
82,62%. O F1 agregado reflete as contagens de acertos e erros de todos os vídeos,
com maior influência dos casos mais numerosos. O desempenho por vídeo precisa
acompanhar o ranking.

| Configuração | Vídeo 13 | Vídeo 29 | Vídeo 52 | Vídeo 54 |
|---|---:|---:|---:|---:|
| s052 | 0,838127 | 0,230088 | 0,444882 | 0,622426 |
| s082 | 0,779602 | 0,549020 | 0,503226 | 0,605459 |
| s084 | 0,779602 | 0,549020 | 0,496815 | 0,605459 |
| s103 | 0,848282 | 0,031250 | 0,419689 | 0,533333 |
| s051 | 0,803615 | 0,424779 | 0,472441 | 0,524027 |

s052 tem maior F1 agregado, mas s082 e s084 se saem melhor nos vídeos 29 e
52. O DoG s103 vai bem no vídeo 13, mas encontra apenas um dos 44 indivíduos
do vídeo 29. Não há uma vencedora uniforme em todas as condições.
Esses dados sustentam testar as cinco configurações congeladas em todos os
frames, sem afirmar antecipadamente que a primeira colocada será a melhor
nos vídeos completos.

## Parâmetros e inspeção das caixas

| Configuração | Diferenças principais que identificam a configuração |
|---|---|
| s052 | SimpleBlob; área mínima 32; distância mínima 12; margem 6 pixels |
| s082 | SimpleBlob; área mínima 64; distância mínima 6; margem 4 pixels |
| s084 | SimpleBlob; área mínima 64; distância mínima 12; margem 4 pixels |
| s103 | DoG; resposta 0,16; sigma mínimo 2/máximo solicitado 12; razão 1,6; margem 8 pixels |
| s051 | SimpleBlob; área mínima 32; distância mínima 12; margem 5 pixels |

As quatro SimpleBlob compartilham área máxima 500, inércia mínima 0,4,
limiares 80–220, passo 5 e repetibilidade 2; circularidade e convexidade
desativadas. Seus cortes de classe correspondem a diâmetros 6 e 24 pixels.
O DoG usa sobreposição 0,5 e cortes equivalentes a diâmetros 8 e 24 pixels.
Os parâmetros completos e suas identidades estão preservados no
[plano de seleção](../scripts/blobs/selecao/plano.json).

s051 e s052 diferem somente na margem. Os 1.471 candidatos brutos e suas
classes são iguais nos 60 frames. A margem de 6 recupera 87 anotações
adicionais (85 normais e dois pequenos), mas perde 41 normais: saldo de
46 TP no agregado, com piora nos vídeos 29 e 52.
s082 e s084 diferem na distância mínima. Seus 840 pares acertados são os
mesmos, inclusive as caixas e as IoUs; em 46/60 frames, todas as detecções
são idênticas. s084 acrescenta seis FP individuais no vídeo 52.
São configurações distintas, quase redundantes nestas imagens, e serão
mantidas na proposta conforme a ordenação acordada, sem nova regra de
diversidade ou exclusão por semelhança.

A inspeção de **s052, vídeo 52, frame 300**, confirma que uma caixa próxima
da cabeça nem sempre atinge IoU ≥ 0,50. Nesse caso houve 1 TP, 22 FP e 6 FN.
Quatro normais perdidos tinham caixas previstas sobrepostas, com IoU máximo
de 0,3903; 0,4750; 0,4444; e 0,4958. Os dois pequenos anotados não tinham
previsão sobreposta. Esse diagnóstico usa exclusivamente as caixas já salvas,
sem novo pareamento de avaliação nem ajuste de limiares.

Foram também inspecionadas as comparações de s103 no vídeo 13/frame 0,
onde várias cabeças anotadas como normais aparecem localizadas com rótulo
pequeno. A inspeção ilustra a separação entre localização e classificação;
não altera as anotações ou o resultado registrado.

## Integridade e fontes

A auditoria conferiu:

- **51.158 hashes de saídas** e **134 hashes de entradas/origens**, sem
  ausências ou divergências; 5.622.534.120 bytes de saídas verificados.
- 119 pastas concluídas, cada uma com 60 frames; 119 agregados de configuração,
  476 agregados por vídeo e 7.140 linhas por quadro, com contagens coerentes.
- Plano idêntico ao congelado; 13 cópias de origens e 136 ocorrências de
  configurações no desenvolvimento preservadas; ZIP com 28 fontes íntegro.
- Mesmas dependências e implementações de detecção/avaliação usadas no
  desenvolvimento, conforme disponibilidade de cada variante em cada rodada.
- PDF de sete páginas, todas renderizadas e revisadas; 19 fontes do relatório,
  metadados, cópias de plano/manifesto e seis hashes do código conferidos.

Python 3.13.3, NumPy 2.3.3, OpenCV 4.13.0, SciPy 1.16.2,
scikit-image 0.26.0 e ReportLab 4.5.1 constam na execução.

| Fonte | SHA-256 |
|---|---|
| `execucao.json` | `f6a6a46301f8dd646306ea4ff2ed575d6319ae93f1a7f830e00fae5107a7d9e1` |
| `plano.json` | `b33cdd0b1bb16386230bdf4f55a11bf94b57436ceeabe4c163f4aece885636a4` |
| `ranking.csv` | `7b94caabc4a886245d73c5fecdc19270e614d1268de81a256808507310ef8507` |
| `codigo.zip` | `06d9d37da532a1a7cb6a92fbf44dbb2ea094a8ad5cce7d942f17b3d25552b1b0` |
| `relatorio.pdf` | `93837b6ff4eac4d51ad4d0ac7aa2e4c2ec4a3779693b8064216a05d51a368995` |

O [PDF da seleção](../resultados/frame-to-frame/blobs/selecao/batch__20260921T011058635016Z/relatorios/20260921T013159493770Z/relatorio.pdf)
e os três resumos CSV do batch contêm os resultados das 119 configurações.
Esta análise não executou detectores, não refez o experimento e não modificou
resultados, parâmetros ou imagens originais.

## Próxima decisão do protocolo

Recomenda-se aprovar **s052, s082, s084, s103 e s051** para preparar os
vídeos completos **13, 29, 52 e 54**, mantendo suas configurações e as métricas.
Serão 5.850 frames por configuração, ou 29.250 avaliações, com 20 vídeos
comparativos, tabelas e PDF. A execução continuará a cargo do pesquisador.

Essa etapa amplia a cobertura temporal dos mesmos vídeos usados na seleção
em imagens; não é uma avaliação independente. Após sua análise, o protocolo
prevê congelar as mesmas cinco para os vídeos finais **14, 24, 38 e 82**.
O histórico de uso dos dados permanece registrado. Alterar critérios ou
parâmetros agora exigiria uma decisão metodológica explícita; não ocorreu
nesta análise.

O registro desta etapa acrescenta este documento e atualiza o
[estado da pesquisa](estado_pesquisa.md), o [README principal](../README.md),
o [guia dos scripts](../scripts/README.md), o [guia de blobs](../scripts/blobs/README.md)
e o [guia de análise](README.md). Nenhum código de detecção ou configuração
experimental foi modificado.

## Decisão posterior: preparação dos vídeos aprovada

O pesquisador aprovou prosseguir com **s052, s082, s084, s103 e s051** nos
vídeos completos **13, 29, 52 e 54**, mantendo parâmetros e métricas. O
[plano de vídeos](plano_videos_blobs.md) documenta a preparação do executor,
comparações visuais, tabelas e PDF. A execução continua a cargo do pesquisador;
esta decisão não representa resultados de vídeo nem autorização para alterar
as configurações ou executar a avaliação final automaticamente.
