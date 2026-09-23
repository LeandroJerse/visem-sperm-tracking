# Análise da seleção de watershed em imagens

## Resultado e proposta para revisão

Execução concluída e conferida em
`resultados/frame-to-frame/watershed/selecao/batch__20260921T203527246803Z`.
São **114 configurações distintas × 60 imagens = 6.840 avaliações**,
nos vídeos 13, 29, 52 e 54, com os parâmetros e critérios congelados.

Pelo **F1 de localização de indivíduos (0 e 2)**, as candidatas propostas
para revisão são **s063, s064, s061, s062 e s098**, nesta ordem. A execução
está íntegra, mas o desempenho é limitado. Após esta análise, o pesquisador
aprovou as cinco para os vídeos completos de seleção. O
[plano da próxima etapa](plano_videos_watershed.md) está preparado para execução.

| Posto | ID | Origem | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | s063 | r2c19 | 398 | 663 | 862 | 0,375118 | 0,315873 | **0,342956** |
| 2 | s064 | r2c20 | 389 | 632 | 871 | 0,380999 | 0,308730 | **0,341078** |
| 3 | s061 | r2c17 | 432 | 1.045 | 828 | 0,292485 | 0,342857 | **0,315674** |
| 4 | s062 | r2c18 | 392 | 944 | 868 | 0,293413 | 0,311111 | **0,302003** |
| 5 | s098 | r4c10 | 321 | 625 | 939 | 0,339323 | 0,254762 | **0,291024** |
| 6 | s097 | r4c09 | 326 | 670 | 934 | 0,327309 | 0,258730 | 0,289007 |

Não há empate exato na quinta vaga. A diferença entre s098 e s097 é
**0,0020173865 de F1**, aproximadamente 0,202 ponto percentual. Isso define
a ordem no conjunto observado; não comprova uma diferença estável fora dele.
Não foram acrescentados pesos, exigências de diversidade ou novos desempates.

## O que mudou em relação ao desenvolvimento

A líder do round5, **r5c10 = s110**, passou de F1 0,482362 no desenvolvimento
para **0,250587 e 22º lugar** na seleção. A líder atual, s063, veio do round2
e tinha F1 0,431870 no desenvolvimento. As quatro primeiras vieram do round2;
a quinta veio do round4. Isso sustenta a decisão de comparar todas as
configurações distintas, inclusive as que não lideraram as rodadas recentes.

Os conjuntos são diferentes. A queda não significa que o código foi alterado
ou que uma rodada foi desfeita: o código arquivado coincide com as fontes
atuais e os parâmetros são os mesmos. Os 178 JPEGs do desenvolvimento e
os 60 da seleção têm **640 × 480 pixels**; não houve mudança de resolução.
Os resultados mostram dependência das condições dos vídeos avaliados.

## Cobertura e classificação

Referência nos 60 quadros: **1.200 normais, 60 pequenos e 45 aglomerados**.
São ocorrências anotadas por quadro, não indivíduos biologicamente distintos.

| ID | Normais localizados | Pequenos localizados | Aglomerados localizados | Trocas 0/2 | Acurácia entre pares 0/2 |
|---|---:|---:|---:|---:|---:|
| s063 | 396/1.200 | 2/60 | 28/45 | 3/398 | 99,25% |
| s064 | 387/1.200 | 2/60 | 28/45 | 3/389 | 99,23% |
| s061 | 423/1.200 | 9/60 | 31/45 | 9/432 | 97,92% |
| s062 | 384/1.200 | 8/60 | 25/45 | 8/392 | 97,96% |
| s098 | 319/1.200 | 2/60 | 29/45 | 4/321 | 98,75% |

Nenhuma das cinco classificou corretamente como 2 um pequeno localizado.
Todos os pequenos pareados receberam classe 0. Nas s063/s064 houve também
um normal previsto como pequeno; na s098, dois. A acurácia condicional alta
é dominada pelos normais e exclui as perdas e falsas detecções.

Há uma restrição explícita nos parâmetros das cinco: **área mínima aceita
120 pixels e classe 2 até 120 pixels, inclusive**. Assim, apenas uma região
com exatamente 120 pixels pode receber classe 2; regiões menores são
descartadas. Essa regra ajuda a explicar a classificação, mas não explica
sozinha todas as perdas de localização. Não foi modificada nesta análise.

A maior cobertura de pequenos em todo o catálogo foi 14/60 na s031, porém
com F1 global 0,008172 e 103º lugar. As s037/s038 classificaram corretamente
quatro pequenos, mas tiveram F1 0,019656. Portanto, não há evidência de uma
configuração do catálogo que resolva simultaneamente as limitações observadas.

## Variação entre vídeos

Cada vídeo tem quinze quadros. O vídeo 13 contém 640/1.260 indivíduos anotados
(50,79%); 13 e 54 juntos têm 82,62%. O F1 agregado soma contagens e, portanto,
recebe maior influência dos casos mais numerosos.

| ID | Vídeo 13 | Vídeo 29 | Vídeo 52 | Vídeo 54 |
|---|---:|---:|---:|---:|
| s063 | 0,218527 | 0,240000 | 0,542986 | 0,375000 |
| s064 | 0,218527 | 0,275229 | 0,542986 | 0,364865 |
| s061 | 0,369819 | 0,000000 | 0,379110 | 0,292237 |
| s062 | 0,369819 | 0,000000 | 0,382294 | 0,247485 |
| s098 | 0,156716 | 0,392523 | 0,554779 | 0,272517 |

As s061/s062 encontram mais indivíduos no vídeo 13, mas nenhum dos 44
indivíduos anotados no vídeo 29. A s098 é superior às outras quatro no
vídeo 52. Nenhuma é a melhor em todos os vídeos.

Como análise de sensibilidade, recalculou-se a ordem das 114 configurações
retirando um vídeo por vez, sem executar detecção ou ajustar parâmetros:

| Vídeo retirado | Primeira colocada | Cinco primeiras no subconjunto |
|---|---|---|
| 13 | s063 | s063, s064, s098, s097, s113 |
| 29 | s063 | s063, s064, s061, s062, s098 |
| 52 | s061 | s061, s063, s064, s062, s097 |
| 54 | s062 | s062, s061, s064, s063, s088 |

O grupo das cinco muda em três das quatro retiradas. É uma verificação
descritiva de sensibilidade, não validação cruzada ou teste de significância.
O ranking acordado continua sendo o dos 60 quadros completos.

## Diagnóstico das perdas da líder

Foram examinadas as caixas emitidas e todas as regiões candidatas já salvas
da s063, incluindo as rejeitadas pelo filtro de área. Para cada indivíduo
perdido, aplicou-se a sequência abaixo, sem modificar seu pareamento oficial:

| Diagnóstico | FN |
|---|---:|
| Caixa individual com IoU suficiente, mas indisponível no pareamento exclusivo | 5 |
| Sem o caso anterior; caixa emitida como aglomerado com IoU suficiente | 2 |
| Sem os casos anteriores; candidato rejeitado por área mínima com IoU suficiente | 6 |
| Sem os casos anteriores; algum candidato sobreposto, todos com IoU abaixo de 0,50 | **827** |
| Nenhum candidato sobreposto | 22 |
| Total | **862** |

Nos 827 casos de sobreposição insuficiente, a caixa do candidato com maior
IoU era menor que a anotada em 687 casos. A razão mediana entre suas áreas
foi **0,2940**. Isso é área de caixa, não área segmentada. No vídeo 13,
a mediana foi 0,2143 em 518 perdas; no vídeo 29, foi 2,9412 em 29 perdas.
Há tanto caixas pequenas demais quanto regiões maiores que a referência.

Dos melhores candidatos nesses 827 casos, 430 foram rejeitados por área
mínima e 397 foram aceitos. Mesmo removendo esse filtro, suas caixas salvas
continuariam sem atingir IoU 0,50. Os seis casos com candidato rejeitado e
IoU suficiente são indícios para diagnóstico, não uma estimativa de ganho
ao reduzir o mínimo: novos falsos positivos e disputas de pareamento também
teriam de ser avaliados em outro experimento.

Exemplos visuais conferidos: s063, quadros 0 dos vídeos 13, 52 e 54.
No vídeo 13/quadro 0, das 46 regiões, 44 ficaram abaixo do mínimo; sobraram
duas detecções e nenhuma atingiu um par válido, com 44 FN. No vídeo 52/quadro
0 aparecem 19 detecções para oito anotações, ilustrando também candidatos
excedentes. A correspondência continua usando as mesmas caixas e a mesma IoU.

O problema observado envolve segmentação, extensão das regiões e filtros.
Mudar somente o rótulo das detecções não recupera as cabeças não localizadas.
Não se recomenda ajustar caixas, limiares ou limites de área com base nestas
imagens e apresentar isso como continuidade da mesma seleção congelada.
Uma investigação posterior exigiria uma nova versão e o registro dessa
exposição aos dados.

## Configurações propostas e continuidade

Todas usam Otsu para objetos claros, abertura desligada, fechamento retangular
5×5 uma vez, conectividade 8, área aceita 120–5.000 pixels, corte de pequeno
120 e início de aglomerado 900. As diferenças são:

| ID | Deslocamento de Otsu | Fração da semente | Política de aglomerados |
|---|---:|---:|---|
| s063 | −10 | 0,75 | Separar |
| s064 | −10 | 0,75 | Preservar por área |
| s061 | −20 | 0,75 | Separar |
| s062 | −20 | 0,75 | Preservar por área |
| s098 | −7 | 0,35 | Preservar por área |

Mantém-se a proposta dessas cinco pelo critério acordado, com as limitações
explícitas. As políticas em pares são configurações distintas; não há regra
nova para excluir configurações semelhantes.

Após a aprovação conjunta, foram preparados os testes dessas cinco nos vídeos
completos **13, 29, 52 e 54**, produzindo vídeos anotados e métricas, sem
mudar parâmetros. Depois da revisão dessa etapa, congelar as escolhas para
os vídeos finais **14, 24, 38 e 82**. A execução dos novos experimentos
continua com o pesquisador. Nesta análise não foram executados detectores
na base. O JSON de estatísticas preserva a situação anterior à aprovação;
o novo plano registra a decisão posterior sem alterar aquela evidência.

## Integridade e arquivos

- 6.840 avaliações, 114 configurações e 456 linhas por configuração/vídeo.
- **82.468 hashes de saídas**, cobrindo 7.285.764.581 bytes, e **274 hashes
  de entradas/origens** conferidos sem ausência ou divergência.
- 42 fontes em `codigo.zip`, também idênticas às fontes atuais. Planos,
  origens históricas, configurações e metadados de segmentação conferidos.
- Doze arquivos em cada pasta de quadro; avaliações, pares, pendentes,
  candidatos e agregações reconciliados em todos os 6.840 casos.
- **360 avaliações recalculadas das caixas salvas**: todas as sessenta
  imagens das seis primeiras configurações, sem divergências. Não houve
  nova segmentação ou detecção.
- PDF original com **oito páginas**, **7.228 fontes** conferidas e todos
  os 114 IDs presentes. As oito páginas foram revisadas visualmente.
- Duração registrada até concluir as métricas: **1.866,351683 segundos**,
  aproximadamente 31min06s, excluindo a geração posterior do PDF.

Fontes: [estatísticas e diagnóstico](estatisticas_selecao_watershed.json),
[plano congelado](../scripts/watershed/selecao/plano.json) e
[PDF original](../resultados/frame-to-frame/watershed/selecao/batch__20260921T203527246803Z/relatorios/20260921T210644997021Z/relatorio.pdf).
O manifesto da execução tem seu hash registrado nas estatísticas.
Os resultados originais foram preservados. A seleção já utilizou imagens
vistas em outros detectores; não é avaliação final inédita.
