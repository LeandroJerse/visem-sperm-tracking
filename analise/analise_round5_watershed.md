# Watershed — análise do round5 e encerramento do desenvolvimento

21/09/2026. Conferência dos resultados salvos, sem nova execução do detector.
Batch: `resultados/frame-to-frame/watershed/round5/batch__20260921T193215730860Z`.
As [estatísticas completas](estatisticas_round5_watershed.json) preservam
contagens, referências, contrastes, sensibilidade e diagnóstico das perdas.
O [plano aprovado](plano_round5_watershed.md) registra as hipóteses anteriores à execução.

**Conclusão:** round5 íntegro, com ganho pequeno de F1 e resultados diferentes
conforme o vídeo. A líder passou de **0,481308 para 0,482362**, encontrando
33 indivíduos adicionais e gerando 87 falsas detecções adicionais.
A localização de pequenos caiu de 10/134 para 6/134. Recomenda-se encerrar
as cinco rodadas e avançar à seleção em outras imagens, preservando todas
as 114 configurações distintas. Ainda não há cinco finalistas escolhidas.

## Conferência da execução

- **14 configurações × 178 quadros = 2.492 avaliações** completas.
- **34.218 hashes de saídas e 4.636 de origens**, sem divergências.
- **1.068 controles e 4.272 arquivos** idênticos às referências do round4.
- 38 fontes arquivadas, íntegras e iguais às fontes atuais.
- Tabelas com 14 configurações, 168 linhas por vídeo e 2.492 por quadro:
  parâmetros, contagens, agregações, ranking e metadados reconciliados.
- Todas as avaliações JSON, tabelas de pares e listas de pendentes conferidas.
  Cada caso possui os doze arquivos previstos.
- Pareamentos dos **178 quadros da líder r5c10** recalculados das caixas
  salvas, coincidentes integralmente com as avaliações.
- PDF original de cinco páginas, hash e 11.078 fontes conferidos.
  Todas as páginas foram inspecionadas visualmente.
- Nos cinco rounds, os planos usam os mesmos quadros e exclusões.
  Os hashes das tabelas históricas consultadas foram conferidos; as métricas
  das configurações repetidas coincidem. São 136 entradas e **114 distintas**.
  A auditoria integral das mídias históricas permanece nos relatórios anteriores.

Duração registrada: **12 minutos e 31 segundos**, antes da geração do PDF.
Imagens, anotações, código experimental, planos executados e resultados
originais foram preservados.

## Resultado principal

| Medida | Líder round4, repetida em r5c02 | Líder round5, r5c10 |
|---|---:|---:|
| F1 de indivíduos | 0,481308 | **0,482362** |
| Precisão | 0,451534 | 0,446522 |
| Recall | 0,515286 | 0,524458 |
| Acertos — TP | 1.854 | 1.887 |
| Falsas detecções — FP | 2.252 | 2.339 |
| Perdas — FN | 1.744 | 1.711 |
| Normais localizados | 1.844/3.464 | 1.881/3.464 |
| Pequenos localizados | 10/134 | 6/134 |
| Aglomerados localizados | 46/109 | 43/109 |
| F1 de aglomerados | 0,224939 | 0,270440 |

O ganho de F1 é **+0,001054**, aproximadamente **0,11 ponto percentual**
na escala de 0 a 100%. F1 não é a porcentagem de objetos encontrados;
o recall de indivíduos é 52,45%. A precisão caiu, pois as falsas detecções
cresceram proporcionalmente mais que os acertos.

r5c10 usa Otsu −5, semente 0,50, mínimo 120, fechamento retangular **3×3**
e preservação de aglomerados por área. Frente a r5c02, muda somente o
fechamento de 5×5 para 3×3. O ganho líquido de 33 indivíduos resulta de
37 normais adicionais e quatro pequenos a menos.

O F1 de aglomerados cresce apesar de três perdas adicionais, porque seus
FP diminuem de 254 para 166. Esse resultado continua separado do ranking
principal de localização de indivíduos.

### Primeiras posições do round5

| ID | Otsu | Semente | Área mínima | Fechamento | Política | F1 | TP | FP | Pequenos |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| r5c10 | −5 | 0,50 | 120 | 3 | preservar | 0,482362 | 1.887 | 2.339 | 6/134 |
| r5c14 | −5 | 0,50 | 144 | 5 | preservar | 0,481586 | 1.798 | 2.071 | 9/134 |
| r5c13 | −5 | 0,50 | 144 | 5 | separar | 0,481385 | 1.849 | 2.235 | 9/134 |
| r5c02 | −5 | 0,50 | 120 | 5 | preservar | 0,481308 | 1.854 | 2.252 | 10/134 |
| r5c12 | −3 | 0,50 | 120 | 3 | preservar | 0,480672 | 1.859 | 2.278 | 7/134 |

A distância entre primeiro e segundo é apenas **0,000776**. r5c14 reduz
268 FP em relação à líder, mas perde 89 TP. Essas posições descrevem os
quadros de desenvolvimento; não substituem a seleção nas outras imagens.
No histórico sem repetições, r5c02 aparece como sua origem r4c16.

## O que as combinações mostraram

### Fechamento menor depende da política

Com Otsu −5 e semente 0,50, reduzir fechamento de 5 para 3:

- **Preservar:** +33 TP, +87 FP, F1 **+0,001054**; produz a líder.
- **Separar:** +14 TP, +176 FP, F1 **−0,007796**.

Com Otsu −3, a direção se repete: fechamento menor melhora F1 em 0,000505
na preservação e piora em 0,006997 na separação. Portanto, não há evidência
de que “fechamento 3 é melhor” independentemente das demais escolhas.

Na configuração da líder, preservar frente a separar remove 263 FP, perde
32 TP e melhora F1 em 0,009644. Preservar vence no F1 agregado dos sete pares
do round5, mas essa evidência de desenvolvimento não autoriza excluir as
variantes de separação antes da seleção.

### Otsu −3 não soma automaticamente o ganho da semente 0,50

Com fechamento 5 e semente 0,50, mudar −5 para −3 piora o F1 nas duas
políticas: −0,000504 ao separar e −0,001141 ao preservar. Recupera um
pequeno, mas perde 20 e 14 indivíduos, respectivamente.

A combinação dos três ajustes, r5c12, perde para r5c10: −28 TP, −61 FP
e F1 −0,001690. Ela melhora sete vídeos e piora cinco contra r5c10,
embora perca no agregado. Contar vídeos vencidos não é o critério do ranking;
o F1 principal resulta das contagens somadas.

### Área mínima maior: alternativa com menos falsas detecções

Mínimo 144, com Otsu −5, semente 0,50 e fechamento 5, remove 56 TP:

- **Separar:** remove 191 FP, F1 +0,000870.
- **Preservar:** remove 181 FP, F1 +0,000277.

Ambas melhoram oito vídeos e pioram quatro contra seus controles, perdendo
um pequeno localizado. O ganho de F1 continua pequeno e tem custo de cobertura.
Com mínimo 144, nenhuma região pode ser classificada como pequeno, pois
o limite dessa classe continua em 120 pixels.

Os 14 contrastes e as sete comparações entre políticas estão nas estatísticas
e nas páginas finais do PDF, sem mudança de métricas ou ponderações.

## Variação entre vídeos e sensibilidade

A nova líder melhora **sete vídeos e piora cinco** frente à líder do round4.
A mediana das diferenças por vídeo é +0,002067, apenas um resumo descritivo.

| Vídeo | F1 r5c02 | F1 r5c10 | Diferença |
|---|---:|---:|---:|
| 11 | 0,361484 | 0,383854 | +0,022370 |
| 12 | 0,497765 | 0,480243 | −0,017521 |
| 15 | 0,508604 | 0,477273 | −0,031331 |
| 19 | 0,228070 | 0,230216 | +0,002146 |
| 21 | 0,642314 | 0,664671 | +0,022357 |
| 22 | 0,579572 | 0,581560 | +0,001988 |
| 23 | 0,324786 | 0,300000 | −0,024786 |
| 30 | 0,793734 | 0,816754 | +0,023020 |
| 35 | 0,522749 | 0,579048 | +0,056298 |
| 36 | 0,646362 | 0,582923 | −0,063439 |
| 47 | 0,307087 | 0,354978 | +0,047892 |
| 60 | 0,195980 | 0,180451 | −0,015529 |

Retirando um vídeo inteiro por vez e recalculando o F1 das configurações,
sem alterar seus parâmetros, a liderança entre as **114 configurações distintas**
fica com r5c10 em quatro retiradas, r5c12 em quatro, r4c16 em três e r5c13
em uma. Entre as 14 do round5, r4c16 corresponde a r5c02 e o resultado é igual.

Isso mostra sensibilidade à composição dos vídeos. Não é validação cruzada,
pois não há novo ajuste em cada divisão, nem teste de significância.
As configurações já foram ajustadas usando esses dados; quadros de um
mesmo vídeo são correlacionados.

### Inspeção visual dirigida

Foram comparadas r5c02 e r5c10 em dois quadros escolhidos após consultar
as diferenças, sem tratá-los como amostra aleatória:

- **35/400:** maior ganho de TP, +6 TP e −2 FP. O fechamento menor permite
  caixas separadas em locais antes unidos, inclusive no grupo superior.
- **12/800:** maior perda de TP, −4 TP e +3 FP. Alterações no tamanho e na
  união das regiões também podem piorar a correspondência com as caixas anotadas.

Os quatro caminhos estão em `exemplos_para_inspecao` nas estatísticas.
O aspecto visual complementa as contagens; não substitui o pareamento por IoU.

## Limitações que permanecem

Dos **1.711 indivíduos perdidos** pela líder:

| Diagnóstico exclusivo, usando candidatos salvos | Quantidade |
|---|---:|
| Sobreposição, mas nenhum candidato alcança IoU 0,50 | 1.591 |
| Candidato suficiente rejeitado pelo filtro de área | 58 |
| Nenhum candidato sobreposto | 54 |
| Candidato individual válido sem par exclusivo disponível | 5 |
| Candidato aceito como aglomerado | 3 |

São 1.143 perdas com melhor IoU entre 0,25 e 0,50. Entre os melhores
candidatos com sobreposição, 648 caixas têm pelo menos o dobro da área
anotada e 551 têm menos da metade. A geometria das regiões continua sendo
um problema central; expandir todas as caixas não resolveria ambos os casos.

Dos 2.339 FP individuais, 1.304 não sobrepõem indivíduos anotados, 1.023
têm IoU insuficiente e 12 correspondem geometricamente a aglomerados.
FP é definido frente às anotações disponíveis; não é uma classificação
biológica independente de cada estrutura vista.

**Pequenos: 6/134 localizados (4,48%), todos previstos como normal.**
A matriz dos pares individuais da líder é `[[1878, 3], [6, 0]]`,
na ordem normal/pequeno. A acurácia condicional de 99,52% exclui objetos
perdidos e falsas detecções; não demonstra boa classificação dos pequenos.
Nenhuma das 14 configurações classificou corretamente como pequeno um
pequeno pareado. A maior cobertura da rodada foi 11/134, em r5c07/r5c08.

Dos 128 pequenos perdidos pela líder, 76 têm IoU insuficiente, 48 não têm
candidato sobreposto e quatro foram rejeitados por área. Alterar apenas
o limite de classe 0/2 não recuperaria a maioria dessas perdas.

## Encerrar os rounds e avançar

| Rodada | Configurações, incluindo controles | Maior F1 | Ganho frente à anterior |
|---|---:|---:|---:|
| round1 | 48 | 0,429887 | — |
| round2 | 32 | 0,466361 | +0,036473 |
| round3 | 24 | 0,478007 | +0,011646 |
| round4 | 18 | 0,481308 | +0,003301 |
| round5 | 14 | 0,482362 | +0,001054 |

Os ganhos diminuíram; a liderança é sensível aos vídeos e as principais
limitações persistem. O orçamento de cinco rodadas foi cumprido.
**Não se recomenda um round6 neste ciclo.** Encerrar a busca não significa
declarar o método suficientemente preciso ou a líder definitivamente superior.

A próxima etapa proposta mantém o protocolo já utilizado nos outros detectores:

1. Comparar **todas as 114 configurações distintas** nos mesmos **60 quadros
   dos vídeos 13, 29, 52 e 54**, de 0 a 1400 com passo 100: **6.840 avaliações**.
2. Preservar parâmetros, caixas, classes, IoU e F1 de indivíduos; apresentar
   cobertura por classe, erros de classificação, aglomerados e variação por vídeo.
   Repetições entre rounds contam como uma configuração, com todas as origens registradas.
3. Revisar as cinco melhores nessa partição antes dos vídeos completos.
   Empates exatos permanecem explícitos para revisão conjunta.
4. Após essa revisão, preparar vídeos completos de seleção e, depois de
   conferir e congelar as escolhas, os vídeos finais 14, 24, 38 e 82.

Os 60 quadros não participaram do ajuste de watershed. Eles já foram usados
com outros detectores, e o histórico de exposição aos dados permanece relevante.
Não são apresentados como dados inéditos para o estudo.
Nenhuma imagem reservada foi usada nesta análise. O executor de seleção
de watershed ainda não foi preparado; a composição concreta acima aguarda
a autorização da próxima etapa.

## Arquivos desta análise

- Criados: este documento e `estatisticas_round5_watershed.json`.
- Atualizados: `analise/estado_pesquisa.md`, `analise/plano_watershed.md`,
  `analise/README.md`, `README.md`, `scripts/README.md`,
  `scripts/watershed/README.md` e `algoritmos/classicos/README.md`.
- Detector, métricas, scripts experimentais e resultados anteriores preservados.
