# Blobs — análise do round3

20/09/2026. Análise das saídas salvas, sem executar novamente os detectores.
Batch: `resultados/frame-to-frame/blobs/round3/batch__20260920T225209430564Z`.

**Resultado:** o maior F1 passou de 0,556433 para 0,567571, ganho de
1,11 ponto percentual. SimpleBlob ainda lidera o agregado, mas DoG chegou
a 0,544980 e encontra mais indivíduos. As melhores configurações continuam
fracas na localização de pequenos; a classificação por área também é limitada.

O [plano do round4](plano_round4_blobs.md) traduz esses achados em 18 testes.
Os [dados estatísticos](estatisticas_round3_blobs.json) preservam 24 configurações,
três referências históricas, 56 contrastes, resultados por vídeo, receita,
versões e hashes das oito fontes utilizadas.

## Integridade e controles

- 24 configurações × 178 quadros = **4.272 avaliações concluídas**.
- 30.046 hashes de saídas e 361 origens conferidos, sem divergências.
- Código arquivado íntegro: 23 arquivos, ZIP e quatro planos de origem.
- Resumos completos: 24 linhas por configuração, 288 por vídeo e 4.272 por quadro.
- PDF de quatro páginas, apontador e hashes válidos.

| Controle | Referência do round2 | F1 indivíduos |
|---|---|---:|
| r3c02 | r2c14 | 0,555359 |
| r3c03 | r2c06 | 0,544038 |
| r3c04 | r2c01 | 0,551828 |
| r3c08 | r2c11 | 0,556433 |

Os controles reproduziram 712 avaliações ao desconsiderar IDs e tempos,
17.502 registros de detecção e 3.560 arquivos idênticos byte a byte:
anotações, detecções, pares, pendências e predições YOLO. Entradas, dependências
e código dos detectores são iguais aos do round2. Repetir controles verifica
reprodução computacional; não acrescenta observações biológicas independentes.

## Resultados principais

O suporte é o mesmo para cada configuração: 3.464 anotações normais,
134 pequenas e 109 aglomeradas. São ocorrências em quadros, não indivíduos únicos.

| Configuração | Parâmetros principais | F1 indivíduos | Precisão | Recall | Normais localizados | Pequenos localizados | Aglomerados localizados |
|---|---|---:|---:|---:|---:|---:|---:|
| r3c08 | SBD área48/dist12/margem4; melhor round2 repetido | 0,556433 | 0,528222 | 0,587827 | 2.113 | 2 | 0 |
| r3c05 | SBD área48/dist6/margem3 | 0,564380 | 0,537167 | 0,594497 | 2.137 | 2 | 0 |
| r3c09 | SBD área64/dist6/margem3 | **0,567571** | 0,557162 | 0,578377 | 2.078 | 3 | 0 |
| r3c24 | DoG resposta0,12/margem6 | 0,544980 | 0,460418 | 0,667593 | 2.402 | 0 | 0 |
| r3c18 | LoG resposta0,12/margem6 | 0,428430 | 0,317324 | 0,659255 | 2.367 | 5 | 14 |
| r3c16 | LoG resposta0,08/margem6 | 0,285958 | 0,183094 | 0,652585 | 2.331 | 17 | 25 |

Frente ao melhor round2, r3c09 retirou 235 FP, mas perdeu 34 TP:
TP 2.115→2.081; FP 1.889→1.654. A melhora decorre do equilíbrio entre
precisão e recall, não de um aumento na quantidade de indivíduos encontrados.

DoG localiza 321 indivíduos adicionais frente ao melhor SBD, com 1.161 FP
adicionais. Supera SBD em quatro vídeos, mas perde em oito. Exemplos:
vídeo11, F1 0,62377 contra 0,37017; vídeo30, 0,50167 contra 0,84150.
Não há um vencedor uniforme entre condições de imagem.

## Comparações estatísticas

Mantidos IoU≥0,50, pares exclusivos, indivíduos 0/2 juntos, aglomerados
separados e F1 calculado das contagens somadas. Trocas 0↔2 são erros de
classificação registrados separadamente.

Foi repetido o bootstrap exploratório pareado por vídeo: 12 blocos com
reposição, 10.000 reamostragens, `numpy.random.default_rng(42)`, mesma matriz
de índices em todas as configurações e percentis 2,5/97,5 com interpolação
linear. Cada bloco reúne os JPEGs anotados daquele vídeo; não são frames
independentes nem os vídeos completos. Empates por vídeo são comparados
como frações exatas, sem arredondamento. Nas interações, somam-se os quatro
termos de F1 em cada reamostragem.

| Comparação | ΔF1 agregado | Vídeos melhora/empate/piora | Intervalo de 95% exploratório |
|---|---:|---|---|
| Melhor round3 − melhor round2 | +0,011139 | 8/0/4 | −0,005867 a +0,029797 |
| SBD área64 − área48, distância6/margem3 | +0,003191 | 8/0/4 | −0,021775 a +0,030160 |
| SBD distância6 − distância12, área64/margem3 | +0,000228 | 5/6/1 | −0,000344 a +0,000597 |
| DoG margem6 − margem4, resposta0,12 | +0,126149 | 12/0/0 | +0,063555 a +0,215789 |
| DoG resposta0,12 − resposta0,08, margem6 | +0,120728 | 12/0/0 | +0,074841 a +0,153877 |
| LoG margem6 − margem4, resposta0,12 | +0,050393 | 9/0/3 | +0,007410 a +0,118061 |
| Melhor DoG − melhor SBD | −0,022591 | 4/0/8 | −0,111685 a +0,073381 |

O pequeno ganho do maior F1 não sustenta uma conclusão de superioridade geral.
Os intervalos são condicionais a somente 12 vídeos já usados na busca,
não corrigem multiplicidade nem escolha adaptativa do melhor resultado e
não demonstram desempenho em dados inéditos. Nenhum conjunto reservado foi usado.
As 10.000 reamostragens dos 56 contrastes tiveram F1 definido.

## Área e margem interagem no SimpleBlob

Com distância6, reduzir a margem de 4 para 3 piora F1 em área32
(−0,008089), mas melhora em área64 (+0,032729). A diferença desses efeitos
é +0,040818, intervalo exploratório +0,023491 a +0,055198: dez vídeos
favorecem essa diferença, dois não. Na estatística salva, o contraste
equivalente usa margem4−3 e, portanto, apresenta o sinal contrário.

Não basta aumentar a área e conservar uma caixa escolhida anteriormente.
Área48/margem3 fica perto da liderança; por isso permanece como referência.
A distância6 fica fixa no round4, permitindo gastar o orçamento na interação
área × caixa. Área80 e margem2 serão hipóteses novas, não valores já validados.

## O que mudou em LoG e DoG

Os candidatos brutos são idênticos nos 178 quadros de todos os 12 pares
que diferem somente na margem. As pontes entre rodadas também foram verificadas:
r2c28→r3c13/r3c14 preserva 26.791 candidatos LoG; r2c32→r3c19/r3c20
preserva 15.189 candidatos DoG. Foram conferidos índices, centro, sigma,
diâmetro, área estimada e classe, com entradas e dependências iguais.

Com resposta0,05, aumentar margem2→6 elevou os TP LoG de 1.278 para 2.404
e DoG de 848 para 2.680. Nesse contraste, o ganho é da representação da caixa,
sem encontrar novos candidatos. A resposta é outro fator:

| Método, margem6 | Resposta0,05: TP/FP | Resposta0,08: TP/FP | Resposta0,12: TP/FP |
|---|---|---|---|
| LoG | 2.404/23.605 | 2.348/10.476 | 2.372/5.103 |
| DoG | 2.680/12.509 | 2.638/6.200 | 2.402/2.815 |

Isso apoia explorar respostas maiores no DoG. Entretanto, os pequenos
localizados caem de 15→2→0; no LoG, de 46→17→5. A resposta não é uma
probabilidade de confiança e aumentá-la não garante preservar objetos reais.

## Diagnóstico dos erros restantes

A tabela decompõe os FN oficiais em categorias mutuamente exclusivas.
Primeiro procura-se candidato do grupo correto com IoU válido; caso exista
mas não tenha par, registra-se competição. Depois verificam-se centros do
grupo dentro da anotação, centros somente do outro grupo e ausência de centro.
Centro dentro da caixa é diagnóstico geométrico, não um novo TP nem identidade
biológica: pode ser ruído, brilho ou fragmento.

| Diagnóstico de FN | SBD r3c09 | LoG r3c18 | DoG r3c24 |
|---|---:|---:|---:|
| Sem centro dentro da anotação nem candidato válido do grupo | 728 | 255 | 615 |
| Centro de indivíduo, caixa sem IoU suficiente | 723 | 671 | 572 |
| Centros somente classificados como aglomerado | 59 | 298 | 0 |
| Competição na correspondência exclusiva | 7 | 2 | 9 |
| **Total FN indivíduos** | **1.517** | **1.226** | **1.196** |

Para cada FN com centro do grupo correto, foi examinada a caixa de maior IoU
entre esses centros. A razão é área da caixa detectada / área da anotação:

- **SBD:** entre 721 normais nessa condição, 372 caixas excedem duas vezes
  a área anotada e 116 ficam abaixo da metade; mediana 2,025. Margem2/3
  testa uma redução moderada.
- **DoG:** 318 dos 562 normais usam sigma2, com razão mediana 0,492 e
  anotação mediana 25×25; 162 ficam abaixo da metade. Margem6/8 explora
  expansão. Nos outros 244 casos, a mediana já é 2,081: expansão não ajuda todos.
- **LoG:** 422 dos 644 normais usam sigma maior que2, mediana 2,161;
  279 excedem o dobro. Os outros 222 têm mediana 0,489. Margem5/6 testa
  redução leve, mantendo a referência, em vez de expandir todas as caixas.

Entre FP, centros fora de qualquer anotação são 923/1.654 no SBD,
3.537/5.103 no LoG e 1.901/2.815 no DoG. Apenas ajustar margens não elimina
todos os candidatos espúrios.

No melhor SBD, 129 dos 134 pequenos não possuem centro candidato. No melhor
DoG são 124; os dez restantes falham geometricamente. LoG tem cinco pequenos
localizados, 102 sem centro e 27 com caixa insuficiente. Aumentar a margem
não recupera candidatos ausentes. O round4 mantém LoG com resposta0,08
para investigar essa perda de sensibilidade, embora seu F1 global seja inferior.

## Localização e classificação são resultados diferentes

| Método | Pares classificados incorretamente | Acurácia somente nos pares |
|---|---:|---:|
| SBD r3c09 | 3/2.081 | 0,998558 |
| LoG r3c18 | 793/2.372 | 0,665683 |
| DoG r3c24 | 1.275/2.402 | 0,469192 |

No DoG, todos os 2.402 TP são anotações normais: 1.127 saem como normal e
1.275 como pequeno. Isso não significa recuperar a classe2. No LoG, os 793
erros também são normais rotulados como pequenos; seus cinco pequenos foram
localizados com classe correta. No SBD, os três pequenos saem como normal.

Alterar somente o corte entre 0 e2 não melhora F1 de indivíduos, pois eles
já são pareados juntos. Classificação continuará registrada; os limites
permanecem fixos nesta rodada para isolar detecção e caixa. A acurácia alta
do SBD também não compensa seus objetos perdidos. k-NN permanece na etapa híbrida.

Aglomerados: 0/109 no SBD, 14/109 no LoG e 0/109 no DoG. A grade DoG
termina em sigma8,192 e não alcança o diâmetro24 necessário para classe1
pela regra atual. Nenhuma margem resolve esse limite de escala/classificação.

## Continuidade

Preparar 18 configurações, com cinco repetições e 13 novas: seis SBD,
oito DoG e quatro LoG. O [plano do round4](plano_round4_blobs.md) registra
os valores e o motivo de cada faixa. A escolha dá mais exploração ao DoG,
mantendo referências SBD e LoG e a cobertura por classe visível.

Após a execução, conferir integridade, controles e candidatos nos pares
de caixa; analisar os contrastes antes de definir o round5. Não escolher
finalistas agora. O documento explicativo completo de blobs continua previsto
após o round5, antes da seleção em outras imagens e dos vídeos.
