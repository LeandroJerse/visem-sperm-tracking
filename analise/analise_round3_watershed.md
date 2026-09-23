# Watershed — análise do round3

21/09/2026. Análise dos resultados salvos, sem executar novamente o detector.
Batch: `resultados/frame-to-frame/watershed/round3/batch__20260921T174126692210Z`.
As [estatísticas completas](estatisticas_round3_watershed.json) registram
contagens, parâmetros, contrastes, integridade e diagnóstico das perdas.

**Conclusão:** execução íntegra. O maior F1 de indivíduos subiu de **0,466361
para 0,478007**, com 64 acertos adicionais e 18 falsas detecções adicionais.
As quatro primeiras configurações usam Otsu com deslocamento −5.
A melhora não é uniforme entre vídeos, e a cobertura de pequenos continua
baixa. A rodada sustenta outro refinamento, sem eleger finalistas.

## Conferência

- **24 configurações × 178 quadros = 4.272 avaliações** concluídas.
- **55.596 hashes de saídas e 4.634 de origens** conferidos, sem divergências.
- **1.068 casos de controle**, com 4.272 arquivos de previsões, detecções,
  avaliações e diagnósticos idênticos ao round2.
- 32 fontes no arquivo de código, íntegras e iguais às fontes atuais.
- Tabelas completas: 24 configurações, 288 linhas por vídeo e 4.272 por quadro.
  Contagens, agregações, ranking e metadados de segmentação reconciliados.
- Todas as avaliações JSON e tabelas de pares conferidas; os doze arquivos
  previstos por quadro estão presentes.
- Os pareamentos dos 178 quadros da líder r3c18 foram recalculados das caixas
  salvas e coincidiram integralmente com as avaliações.
- PDF original de cinco páginas, hash e 12.876 fontes conferidos. As cinco
  páginas foram inspecionadas visualmente, assim como as comparações de
  r3c18 em 11/0, 23/0 e 60/0.

A execução registrada durou **19 minutos e 27 segundos**, antes do PDF.
Nenhum resultado original, detector, plano executável ou critério foi alterado.

## Resultado principal

| Medida | Líder round2, repetida em r3c02 | Líder round3, r3c18 |
|---|---:|---:|
| F1 de indivíduos | 0,466361 | **0,478007** |
| Precisão | 0,441520 | 0,448284 |
| Recall | 0,494163 | 0,511951 |
| Acertos — TP | 1.778 | 1.842 |
| Falsas detecções — FP | 2.249 | 2.267 |
| Perdas — FN | 1.820 | 1.756 |
| Normais localizados | 1.771/3.464 | 1.835/3.464 |
| Pequenos localizados | 7/134 | 7/134 |
| Aglomerados localizados | 36/109 | 46/109 |
| F1 de aglomerados | 0,244068 | 0,224939 |

A diferença de F1 é **+0,011646**, ou **+1,16 ponto percentual** na escala
de 0 a 100%. F1 não é porcentagem de objetos localizados: essa medida é o recall.
O ganho de localização veio de normais; não houve aumento líquido de pequenos.
Mais aglomerados foram localizados, mas os FP desse grupo subiram de 150
para 254, reduzindo seu F1. Isso continua explícito no critério separado.

Líder: Otsu −5, polaridade clara, sem abertura, fechamento retangular 5×5,
área mínima 120, semente 0,35 e preservação de aglomerados por área.
Máximo 5.000, pequeno até 120 e aglomerado a partir de 900 permanecem iguais.

| Posição | Configuração | Ajuste Otsu | Semente | Área mínima | Política | F1 indivíduos |
|---:|---|---:|---:|---:|---|---:|
| 1 | r3c18 | −5 | 0,35 | 120 | preservar | 0,478007 |
| 2 | r3c21 | −5 | 0,75 | 120 | separar | 0,473263 |
| 3 | r3c22 | −5 | 0,75 | 120 | preservar | 0,473245 |
| 4 | r3c17 | −5 | 0,35 | 120 | separar | 0,470146 |
| 5 | r3c13 | 0 | 0,75 | 132 | separar | 0,466868 |

Estas são posições de desenvolvimento, não as cinco finalistas do protocolo.
Todas as configurações históricas continuam elegíveis para a seleção posterior.

## O que os contrastes mostram

### Deslocamento de Otsu

O ajuste **−5 melhora as quatro combinações de semente 0,35/0,75 e política**
contra seus controles de ajuste zero. Os ganhos de F1 variam de 0,007744
a 0,011646. Em cada contraste, há melhora em sete vídeos e piora em cinco.

O ajuste **+5 piora as quatro combinações**, com perda de 226 a 250 TP
e queda de F1 de 0,036744 a 0,039746. Eliminar FP não compensou essas perdas.
Os quatro testes com −5 ocupam as primeiras posições da rodada.

A fração média da máscara muda de 3,95% dos pixels com ajuste zero para
5,73% com −5 e 2,53% com +5. A redução moderada do limiar recuperou regiões
úteis, mas também ampliou regiões inadequadas. Não se deve extrapolar que
limiares cada vez menores sejam melhores: −10 e −20 perderam no round2.

### Área mínima

Reduzir **120 para 108** piora as quatro combinações de semente/política:
ganha 24 TP, mas acrescenta entre 142 e 198 FP. Não recupera pequenos
adicionais em nenhum desses contrastes.

Aumentar **120 para 132** depende da semente. Com 0,35, perde no agregado
nas duas políticas. Com 0,75, ganha aproximadamente 0,0013 em F1, eliminando
176–177 FP e perdendo 47 TP; melhora em oito vídeos e piora em quatro.
Esses testes usaram ajuste zero. O efeito conjunto com −5 ainda não foi
medido por uma nova execução.

### Sementes e preservação

Semente **0,60 perde para 0,50** nas duas políticas, com ajuste zero.
Acrescenta 58–60 FP e apenas 3–10 TP, além de perder dois pequenos localizados.
Não há evidência para continuar aumentando essa fração como regra geral.

Com ajuste −5 e semente 0,35, preservar em vez de separar remove 246 FP,
perde 36 TP individuais e aumenta F1 em 0,007861. Com semente 0,75, os dois
F1 ficam próximos: 0,473263 e 0,473245. A vantagem da política depende dos
demais parâmetros, justificando manter comparações aos pares.

## Variação por vídeo e estabilidade

Comparando r3c18 com a referência r3c02, que reproduz a líder do round2:

| Vídeo | F1 anterior | F1 novo | Diferença |
|---|---:|---:|---:|
| 11 | 0,473643 | 0,354890 | −0,118753 |
| 12 | 0,387500 | 0,494012 | +0,106512 |
| 15 | 0,409836 | 0,506770 | +0,096934 |
| 19 | 0,196721 | 0,235145 | +0,038424 |
| 21 | 0,634823 | 0,624813 | −0,010010 |
| 22 | 0,684597 | 0,582339 | −0,102258 |
| 23 | 0,180905 | 0,324786 | +0,143882 |
| 30 | 0,796834 | 0,785340 | −0,011493 |
| 35 | 0,545813 | 0,526621 | −0,019191 |
| 36 | 0,573150 | 0,633446 | +0,060296 |
| 47 | 0,284483 | 0,311787 | +0,027304 |
| 60 | 0,087629 | 0,202020 | +0,114391 |

O vídeo 11 perde 76 TP e acrescenta 73 FP. No vídeo 23, o ganho de F1 vem
principalmente da redução de 83 FP, com apenas um TP adicional. Portanto,
o mesmo ajuste pode melhorar por mecanismos distintos em cada vídeo.

Retirando um vídeo de cada vez e recalculando os F1, **r3c18 permanece
primeira nas doze retiradas, entre as 24 configurações do round3**.
A margem pode ficar pequena: sem o vídeo 19, a diferença para r3c21 é
aproximadamente 0,000243. Isso mostra estabilidade local da posição,
mas não comprova significância nem desempenho em dados reservados.
Não é validação cruzada; os quadros de um mesmo vídeo são correlacionados.

## Limitações: geometria, falsos positivos e pequenos

Entre os **1.756 indivíduos perdidos** pela líder:

| Diagnóstico dos candidatos salvos | Quantidade |
|---|---:|
| Sobreposição, mas nenhum candidato alcança IoU 0,50 | 1.633 |
| Nenhum candidato sobreposto | 54 |
| Candidato com IoU suficiente rejeitado por área | 48 |
| Candidato aceito no grupo de aglomerados | 12 |
| Candidato individual válido sem par exclusivo disponível | 9 |

As categorias são exclusivas; a prioridade está no JSON das estatísticas.
São **1.116 FN com melhor IoU entre 0,25 e 0,50**. Entre os candidatos de
maior IoU dos FN com sobreposição, 824 caixas têm pelo menos o dobro da área
anotada, enquanto 449 têm menos da metade. Uma expansão uniforme das caixas
continua sem sustentação: há caixas grandes e pequenas demais.

Dos **2.267 FP individuais**, 1.355 não sobrepõem nenhum indivíduo anotado,
899 têm sobreposição insuficiente e 13 correspondem geometricamente a
aglomerados. O diagnóstico não permite afirmar que toda previsão sem par
seja sujeira: o rótulo FP é relativo às anotações disponíveis.

A líder localiza **7/134 pequenos (5,22%)**, todos classificados como normal.
A matriz dos pares individuais é `[[1834, 1], [7, 0]]`, com linhas e colunas
na ordem normal/pequeno. A acurácia condicional de 99,57% é dominada por
normais e exclui perdas e falsas detecções. Nenhuma das 24 configurações
classificou corretamente como pequeno um pequeno localizado; a maior cobertura
foi 10/134, nas configurações de controle r3c03/r3c04.

Dos 127 pequenos perdidos pela líder, 72 têm IoU insuficiente, 48 não têm
candidato sobreposto, seis foram rejeitados por área e um sofre competição
de pareamento. Mudar apenas o limite entre classes 0 e 2 não resolveria
essas perdas de localização. Em 60/0, as comparações mostram objetos anotados
como pequenos sem caixa detectada e várias caixas menores que as anotações.

## Recomendação para a próxima rodada

Vale realizar um **round4 concentrado**, mantendo os 178 quadros, critérios,
caixas atuais, controles e relatório. A proposta para discussão tem
**18 configurações: seis controles e 12 novas**, organizadas em nove pares
separar/preservar. Não há plano executável do round4 preparado nesta análise.

| Papel | Ajuste Otsu | Semente | Área mínima | Fechamento | Configurações |
|---|---:|---:|---:|---:|---:|
| Controle r3c01/r3c02 | 0 | 0,35 | 120 | 5×5 | 2 |
| Controle r3c17/r3c18 | −5 | 0,35 | 120 | 5×5 | 2 |
| Controle r3c21/r3c22 | −5 | 0,75 | 120 | 5×5 | 2 |
| Refinar limiar | −3 | 0,35 | 120 | 5×5 | 2 |
| Refinar limiar | −7 | 0,35 | 120 | 5×5 | 2 |
| Combinar área com −5 | −5 | 0,35 | 132 | 5×5 | 2 |
| Combinar área com −5 | −5 | 0,35 | 144 | 5×5 | 2 |
| Semente intermediária | −5 | 0,50 | 120 | 5×5 | 2 |
| Fechamento menor com −5 | −5 | 0,35 | 120 | 3×3 | 2 |

Motivos:

1. **−3 e −7** delimitam a vizinhança de −5, entre os resultados de zero
   e −10. Permitem procurar equilíbrio sem repetir deslocamentos extremos.
2. **132 e 144 com −5** testam se um filtro um pouco maior reduz os FP
   gerados pela nova máscara. O ganho ou perda não pode ser inferido dos
   testes de área feitos com ajuste zero; candidatos e pareamentos mudam.
3. **Semente 0,50 com −5** preenche uma combinação ainda não testada,
   usando a fração que teve a maior cobertura de pequenos com ajuste zero.
4. **Fechamento 3×3 com −5** testa uma interação específica: se a máscara
   ampliada precisa de menos união morfológica. O fechamento menor perdeu
   com ajuste zero no round2; essa hipótese merece apenas um par controlado,
   sem presumir que reduza as caixas ou melhore a localização.
5. **Seis controles** preservam a referência anterior, a líder atual e o
   par competitivo com semente 0,75. Todos os testes novos têm comparação
   que altera um único parâmetro em relação ao par r3c17/r3c18.

Os limites de classificação permanecem fixos nesta proposta. A cobertura
fraca de pequenos e a variação entre vídeos devem acompanhar a decisão,
sem alterar retrospectivamente a métrica. Após aprovação, preparar o plano
congelado e os testes para execução pelo pesquisador. O round5 dependerá
dos resultados seguintes; a seleção em outras imagens permanece posterior.

## Arquivos desta análise

- Criados: `analise/analise_round3_watershed.md` e
  `analise/estatisticas_round3_watershed.json`.
- Atualizados para indicar a etapa concluída: `analise/estado_pesquisa.md`,
  `analise/README.md`, `analise/plano_watershed.md`, `README.md`,
  `scripts/README.md`, `scripts/watershed/README.md` e
  `algoritmos/classicos/README.md`.
- Código, configurações, arquivos originais e resultados da execução preservados.
