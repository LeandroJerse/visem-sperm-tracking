# Revisão do round3 e plano do round4

Data: 19/09/2026. Algoritmo: limiarização manual/Otsu.

## Conclusão

A execução está completa e consistente. A maior macro-F1 foi **0,235414**,
em `round3/c07`, contra 0,233460 do controle que reproduz a melhor configuração
do round2. O ganho de 0,001954 (0,84% relativo) veio da remoção de falsos positivos; os acertos
da avaliação principal permaneceram iguais. O desempenho continua limitado,
especialmente na localização e classificação dos objetos da classe 2.

`round3/c15`, com fechamento retangular 5 x 5, obteve macro-F1 **0,234380**
e o maior F1 de localização da rodada, **0,417590**. Localizou mais objetos
que `c07` e acertou mais normais e pequenos, mas menos aglomerados. Essa
diferença de resultados justifica manter ambas como referências de análise,
sem declarar superioridade estatística nem escolher as cinco finalistas.

A reavaliação de 23 combinações sobre caixas já salvas favoreceu ajustes
moderados de classificação. O round4 foi preparado com 18 configurações,
sem alterar o detector, as métricas ou o conjunto de quadros. Sua execução
fica com o pesquisador; os resultados exploratórios não substituem esse batch.

## Execução e auditoria

- Origem: [registro do batch](../../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/execucao.json).
- **24 configurações concluídas nos mesmos 178 quadros: 4.272 avaliações**.
- 3.707 caixas anotadas por configuração: 3.464 normais, 109 aglomerados e
  134 pequenos. Essas observações se repetem ao longo dos quadros; não são
  contagens de indivíduos únicos.
- A conferência dos arquivos e hashes não encontrou divergências. Foram
  preservados o plano, os registros de execução, as tabelas e as mídias.
- Os quatro controles reproduziram exatamente os resultados anteriores,
  conforme o mapeamento abaixo. Tempos de execução não entram nessa igualdade.
- O [PDF da rodada](../../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/relatorios/20260919T210030743972Z/relatorio.pdf)
  foi concluído e contém três páginas.

| Controle no round3 | Referência no round2 |
|---|---|
| c01 | c17 |
| c02 | c04 |
| c03 | c24 |
| c04 | c25 |

Fontes principais: [plano executado](../../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/rodada.json),
[resumo das configurações](../../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/resumo_configuracoes.csv)
e [resumo por vídeo](../../resultados/frame-to-frame/limiarizacao/round3/batch__20260919T205704135470Z/resumo_por_video.csv).
Os diagnósticos abaixo também usam `deteccoes.csv`, `anotacoes.csv`, `pares.csv`
e `pendentes.csv` das configurações identificadas no resumo.

Nenhum detector foi novamente executado para esta análise. Os conjuntos
reservados para seleção e avaliação final não orientaram as conclusões.

## Critérios mantidos

O acerto principal exige mesma classe, IoU >= 0,50 e associação um para um.
Somam-se TP, FP e FN dos quadros antes de calcular os F1. A macro-F1 reúne
as três classes com pesos iguais; a classe 0 tem prioridade somente no empate
exato da macro-F1. A análise auxiliar de localização refaz o pareamento
ignorando a classe e não substitui a métrica principal.

Valores sem casos continuam indefinidos, não iguais a zero. Os tempos medidos
permanecem diagnósticos. Não foram criados critérios de desempate ou de parada.

## Resultados principais

| Round3 | Macro-F1 | F1 normal | F1 aglomerado | F1 pequeno | F1 localização |
|---|---:|---:|---:|---:|---:|
| c07 | 0,235414 | 0,453476 | 0,247104 | 0,005660 | 0,413683 |
| c06 | 0,234712 | 0,453476 | 0,247104 | 0,003557 | 0,387227 |
| c15 | 0,234380 | 0,457602 | 0,236735 | 0,008803 | 0,417590 |
| c05 | 0,234161 | 0,453476 | 0,243346 | 0,005660 | 0,413495 |
| c01 | 0,233460 | 0,453476 | 0,243346 | 0,003557 | 0,387063 |
| c10 | 0,230867 | 0,459202 | 0,230088 | 0,003311 | 0,417221 |

Os valores estão arredondados para apresentação. A tabela é descritiva;
essas linhas não constituem a seleção das cinco finalistas.

| Configuração e avaliação | TP | FP | FN |
|---|---:|---:|---:|
| c07: normal | 1.696 | 2.320 | 1.768 |
| c07: aglomerado | 32 | 118 | 77 |
| c07: pequeno | 3 | 923 | 131 |
| c07: localização | 1.820 | 3.272 | 1.887 |
| c15: normal | 1.708 | 2.293 | 1.756 |
| c15: aglomerado | 29 | 107 | 80 |
| c15: pequeno | 5 | 997 | 129 |
| c15: localização | 1.847 | 3.292 | 1.860 |

Uma previsão sem correspondência é um FP neste protocolo. Isso não basta
para determinar sua natureza biológica ou afirmar que seja um resíduo.

## Comparações controladas

### Filtros de área: redução de previsões, sem novos acertos

`c01` e `c07` usam Otsu claro, sem abertura, fechamento elíptico 7 x 7,
pequeno até 120 e aglomerado a partir de 1.000 pixels segmentados. `c07`
aumenta a área mínima de 24 para 48 e acrescenta o máximo de 5.000.
`c05` e `c06` permitem observar cada filtro separadamente.

Os TP principais de `c01` e `c07` são idênticos nas três classes. Os FP
pequenos caem de 1.550 para 923; os FP aglomerados, de 122 para 118.
O F1 normal permanece igual nos 12 vídeos.

Na avaliação auxiliar, cinco normais localizados são descartados pelo
filtro mínimo, mas já estavam classificados incorretamente como pequenos.
Os pares de localização caem de 1.825 para 1.820, enquanto os FP de
localização caem de 3.898 para 3.272. O F1 de localização aumenta nos
12 vídeos. Isso expressa uma troca favorável entre quantidade de FP e TP,
não a localização de novos objetos.

### Forma e tamanho do fechamento

As comparações abaixo mantêm área mínima 48, máxima 5.000, pequeno até 120,
aglomerado a partir de 1.000, Otsu claro e abertura desligada.

| Comparação | Alteração isolada | Efeito observado |
|---|---|---|
| c10 → c15 | Elipse 5 → retângulo 5 | TP normais permanecem 1.708; aglomerados 26 → 29; pequenos 2 → 5; macro-F1 0,230867 → 0,234380 |
| c07 → c14 | Elipse 7 → elipse 9 | TP normais 1.696 → 1.656; aglomerados 32 → 30; pequenos permanecem 3; macro-F1 0,235414 → 0,217048 |
| c07 → c16 | Elipse 7 → retângulo 7 | TP normais 1.696 → 1.663; aglomerados 32 → 31; pequenos permanecem 3; macro-F1 0,235414 → 0,220433 |

O retângulo 5 merece acompanhamento, mas seu ganho não é uniforme: o F1
normal melhora em quatro vídeos e piora em oito frente à elipse 5, embora
o total de TP normais seja igual. Seus pares de localização passam de 1.851
para 1.847; aumentar a macro-F1 não equivale a aumentar todos os acertos.

A elipse 9 piora o F1 normal em 11 dos 12 vídeos frente à elipse 7 e piora
a macro-F1 nos nove vídeos em que ambas a têm definida. O retângulo 7 piora
o F1 normal em dez dos 12 vídeos. Não há apoio nesses resultados para
presumir que elementos morfológicos maiores melhorarão o método.

### Variantes manuais

A maior macro-F1 manual foi **0,188982**, em `c22`: limiar 110, fechamento
elíptico 7, área mínima 48, máxima 5.000, pequeno até 80 e aglomerado desde
1.000. A configuração acertou 50 aglomerados, distribuídos entre os vídeos
11 e 19, mas somente 1.033 normais e nenhum pequeno.

`c19`, com limiar 105 e fechamento elíptico 5, teve o maior F1 pequeno da
rodada, **0,011364**, com quatro TP e 566 FP dessa classe. Os quatro acertos
vieram do vídeo 36. Sua macro-F1 foi 0,160951. Já o controle manual `c04`
acertou oito pequenos, todos no vídeo 21, mas produziu 2.523 FP pequenos.

Esses contrastes ajudam a diagnosticar a sensibilidade ao limiar e à imagem.
Não autorizam escolher uma configuração diferente para cada vídeo nem
selecionar o detector somente pelo resultado de uma classe.

## Áreas e classificação

As áreas abaixo são os pixels da região segmentada após a morfologia.
Não são as áreas das caixas da anotação. A amostra inclui somente previsões
pareadas na avaliação de localização e, portanto, é condicionada ao sucesso
de localização. Há repetição temporal dos mesmos objetos.

| Configuração | Classe anotada | Pares | Mediana da área | Percentis 10–90 | Máximo |
|---|---|---:|---:|---:|---:|
| c07 | Normal | 1.762 | 252 | 150–472 | 1.087 |
| c07 | Aglomerado | 49 | 1.096 | 517–1.789 | 3.576 |
| c07 | Pequeno | 9 | 375 | 64–456 | 595 |
| c15 | Normal | 1.782 | 245 | 146–464 | 1.073 |
| c15 | Aglomerado | 54 | 1.037 | 506–1.715 | 3.543 |
| c15 | Pequeno | 11 | 357 | 71–423 | 585 |

Percentis calculados por interpolação linear no índice `(n - 1) × p`,
arredondados ao pixel inteiro. As medianas pequenas elevadas refletem a
mistura de poucos componentes pequenos e outros com áreas semelhantes
às dos normais; a área sozinha não separa essas classes de modo confiável.

### Diagnóstico de limites em c15

Esta contagem aplica faixas aos pares já salvos de localização. Não refaz
o pareamento nem calcula o F1 de uma configuração nova.

| Pequeno até | Pequenos localizados na faixa | Normais localizados na faixa | FP de localização na faixa |
|---:|---:|---:|---:|
| 80 | 5 | 10 | 471 |
| 100 | 5 | 36 | 717 |
| 120 | 5 | 72 | 925 |
| 140 | 5 | 156 | 1.127 |

Os cinco pequenos corretamente localizados nessa faixa já cabem no limite
80. Subir esse limite redistribui normais e previsões sem correspondência;
não recupera pequenos localizados adicionais nessa segmentação.

| Aglomerado desde | Aglomerados localizados na faixa | Normais localizados na faixa | FP de localização na faixa |
|---:|---:|---:|---:|
| 900 | 36 | 11 | 139 |
| 1.000 | 29 | 2 | 105 |
| 1.100 | 20 | 0 | 80 |

Reduzir o limite recupera aglomerados, mas também reclassifica normais e
mais FP como aglomerados. A escolha exige reavaliação completa, sem usar
apenas a quantidade de previsões ou uma dessas colunas isoladamente.

### Limites de filtragem

Comparação descritiva com a área mínima atual de 48:

| Configuração | Novo mínimo | FP de localização descartados | Pares de localização descartados |
|---|---:|---:|---|
| c07 | 64 | 221 | 4 normais e 1 pequeno |
| c07 | 80 | 423 | 8 normais e os 3 pequenos |
| c15 | 64 | 238 | 4 normais e 1 pequeno |
| c15 | 80 | 457 | 10 normais e os 5 pequenos |

Nos pares da avaliação principal, as perdas dessas alterações são somente
da classe 2: mínimo 64 elimina um TP pequeno em cada configuração, e mínimo
80 elimina todos os TP pequenos. Aumentar o filtro pode melhorar uma medida
de precisão sem preservar a capacidade de detectar essa classe.

O teto atual de 5.000 já removeu os componentes muito grandes. Em `c07`,
o maior FP de localização restante tem área 2.701, e o maior par correto
de localização tem área 3.576. Em `c15`, os valores são 2.637 e 3.543.
Teto 4.000 produziria o mesmo conjunto salvo; teto 3.000 descartaria quatro
aglomerados localizados e nenhum FP em cada configuração. Não há ganho
observado que justifique ajustar o teto à medida desses poucos exemplos.

## Classes raras, localização e variação entre vídeos

Todos os 32 TP aglomerados de `c07` e os 29 de `c15` vieram do vídeo 19.
Todos os três TP pequenos de `c07` e os cinco de `c15` vieram do vídeo 21.
Em `c15`, são os quadros 900, 1100, 1200, 1300 e 1400, com áreas segmentadas
53, 75, 71, 71 e 74. Esses quadros são correlacionados; não são cinco provas
independentes de generalização. Outros seis pequenos localizados, do vídeo
35, têm áreas 357–585 e são classificados como normais.

Para distinguir falhas de localização das de classificação, também foi
calculada, para cada anotação pequena, a maior IoU com qualquer previsão
do respectivo quadro. Essa medida diagnóstica pode reutilizar uma previsão
entre anotações; não é o pareamento um para um nem modifica o limiar de 0,50.

| Configuração | IoU = 0 | 0 < IoU < 0,25 | 0,25 <= IoU < 0,50 | IoU >= 0,50 |
|---|---:|---:|---:|---:|
| c07 | 101 | 13 | 11 | 9 |
| c15 | 99 | 13 | 11 | 11 |
| c19 | 92 | 16 | 8 | 18 |
| c22 | 98 | 12 | 9 | 15 |

Em `c15`, 109 das 134 anotações pequenas têm melhor IoU inferior a 0,1,
incluindo 99 sem nenhuma sobreposição. Alterar o rótulo não recupera essas
regiões. Os resultados manuais mostram outros compromissos: `c22` chega
a 15 pequenos com IoU suficiente, mas nenhum acerto principal dessa classe.

Entre normais de `c15`, 1.169 anotações têm melhor IoU entre 0,25 e 0,50.
Em 471 casos, a caixa prevista tem menos da metade da área anotada; em
350, mais que o dobro. Há simultaneamente caixas insuficientes e excessivas.
Ampliar todas as caixas ou aumentar indiscriminadamente o fechamento não
é uma correção sustentada por esse diagnóstico.

O F1 de localização de `c07` varia de 0,078240 no vídeo 60 a 0,742574 no
vídeo 30; em `c15`, de 0,078240 a 0,746269 nos mesmos vídeos. A macro-F1
de ambas é indefinida nos vídeos 30, 47 e 60 por classe sem casos. Esses
valores não viram zero e não devem ser excluídos do exame dos F1 por classe
e das contagens para favorecer uma configuração.

## Reavaliação exata de 23 combinações

O registro [round3_reavaliacao_areas.json](round3_reavaliacao_areas.json)
contém a grade definida antes de executar as variações, incluindo quatro
referências. A avaliação usou somente caixas e áreas salvas; não processou
imagens nem alterou as detecções originais.

- `c15`: pequeno 80/100/120/140 × aglomerado 900/1.000/1.100,
  mais mínimo 64 com os limites originais: 13 casos.
- `c07`: referência e mínimo 64: dois casos.
- `c19`: pequeno 80/100/120/140, mantendo aglomerado 1.000: quatro casos.
- `c22`: pequeno 80/120/200/250, mantendo aglomerado 1.000: quatro casos.

Todos mantêm máximo 5.000 e mínimo 48, salvo as duas variações de mínimo 64.
As quatro referências reproduziram as métricas por quadro, vídeo e total
antes das variações. Foram conferidos e preservados 39 hashes das fontes.
O avaliador refez os pareamentos para cada combinação e quadro; as contagens
foram somadas antes do cálculo dos F1. Não foi ampliada a grade após os resultados.

| Origem e alteração | Macro-F1 | TP normal | TP aglomerado | TP pequeno |
|---|---:|---:|---:|---:|
| c15 original | 0,234380 | 1.708 | 29 | 5 |
| c15, aglomerado desde 900 | 0,237044 | 1.699 | 36 | 5 |
| c15, pequeno até 100 e aglomerado desde 900 | 0,236113 | 1.735 | 36 | 5 |
| c15, mínimo 64 | 0,234432 | 1.708 | 29 | 4 |
| c07 original | 0,235414 | 1.696 | 32 | 3 |
| c07, mínimo 64 | 0,235125 | 1.696 | 32 | 2 |
| c19 original | 0,160951 | 875 | 50 | 4 |
| c19, pequeno até 120 | 0,163358 | 861 | 50 | 5 |
| c22 original | 0,188982 | 1.033 | 50 | 0 |
| c22, pequeno até 120 | 0,191321 | 1.003 | 50 | 0 |
| c22, pequeno até 250 | 0,170023 | 623 | 50 | 15 |

**Retângulo 5 com pequeno 120 e aglomerado 900 foi o melhor caso dessa grade.**
Contra sua origem `c15`, acrescenta sete TP aglomerados, mas também 43 FP
aglomerados: 36 TP e 150 FP. Dos acertos, 35 vêm do vídeo 19 e um do vídeo 11.
Perde nove TP normais. O F1 de localização permanece 0,417590: há
reclassificação das mesmas caixas, não descoberta de novos objetos.

Essa variação melhora a macro-F1 em seis dos nove vídeos em que a métrica
é definida nas duas versões; piora no vídeo 35 e empata nos vídeos 12 e 23.
No vídeo 47, a macro-F1 passa de indefinida para definida pela introdução
de um falso positivo aglomerado. Essa mudança de situação não é um ganho
comparável de macro-F1; as contagens e os F1 por classe devem ser examinados.

O limite pequeno 100 com aglomerado 900 ficou próximo, com mais TP normais
e macro-F1 inferior. Ele será preservado em uma comparação controlada com
120. Isso não muda o ranking principal nem cria peso extra para normais.
O limite de aglomerado 950 testa o intervalo entre 900 e a referência 1.000.

Mínimo 64 perde um pequeno em ambas as segmentações. O ganho de macro-F1
em `c15` é de apenas 0,000052, enquanto em `c07` há perda. A proposta mantém
48 como referência conservadora; não declara 64 universalmente inferior.

No manual 105, pequeno 120 recupera um quinto pequeno do vídeo 36, mas
os FP pequenos aumentam de 566 para 912. No manual 110, pequeno 120 melhora
a macro-F1 pela redistribuição dos erros, sem recuperar pequenos. Aumentar
até 250 recupera 15 pequenos do vídeo 21, mas perde 410 TP normais e aumenta
os FP pequenos de 429 para 1.838. Esse caso ilustra a sobreposição de áreas
entre classes e não será levado ao próximo plano.

Todas essas estimativas reutilizam os dados de desenvolvimento. São
condicionadas às quatro segmentações salvas, não constituem validação
independente nem resultados de uma execução do round4.

## Configurações preparadas para o round4

O [round4.json](../../scripts/limiarizacao/rodadas/round4.json) contém
**18 configurações × 178 quadros = 3.204 avaliações**, com a mesma ordem,
hashes e duas exclusões aprovadas. Os IDs abaixo pertencem ao round4.

| IDs | Quantidade | Comparação |
|---|---:|---|
| c01–c04 | 4 | Controles de round3/c07, c15, c19 e c22 |
| c05–c08 | 4 | Otsu retângulo 5: pequeno 100/120 × aglomerado 900/950 |
| c09–c12 | 4 | Otsu elipse 5/7 × aglomerado 900/950, pequeno 120 |
| c13–c15 | 3 | Manual 103/105/107 com elipse 5, pequeno 120 e aglomerado 1.000 |
| c16–c18 | 3 | Manual 108/110/112 com elipse 7, pequeno 120 e aglomerado 1.000 |

Todas usam área mínima 48, máxima 5.000, polaridade clara, conectividade 8,
abertura desligada e uma iteração de fechamento. Os controles manuais
preservam pequeno 80; os seis novos casos manuais usam pequeno 120.

As razões do plano são:

1. **Repetir quatro referências.** Conservam a melhor configuração global,
   a alternativa retangular e duas variantes manuais com resultados distintos.
2. **Refinar a classificação no retângulo 5.** A grade exata favoreceu
   aglomerado 900; 950 testa a vizinhança. Pequeno 100/120 permite comparar
   a troca entre acertos normais e falsos positivos com segmentação fixa.
3. **Testar a transferência para as elipses.** Os limites 900/950 são
   cruzados com elipse 5/7, mantendo pequeno 120. Não se presume que o
   melhor limite do retângulo seja o melhor em outra segmentação.
4. **Explorar as duas vizinhanças manuais.** 103/107 cercam o limiar 105,
   que recuperou pequenos no vídeo 36; 108/112 cercam 110, a melhor manual
   global. As âncoras 105/110 com pequeno 120 isolam a alteração de classe
   quando comparadas aos respectivos controles com pequeno 80.
5. **Concentrar o orçamento.** Não acrescentar novas dimensões nem insistir
   em elipse 9, retângulo 7, mínimos maiores ou limites pequenos 200/250,
   cujas perdas já foram examinadas. O detector não recebeu filtros novos.

A lista é determinística; a seed 42 é mantida como registro. Para repetir
esta rodada, use o JSON salvo. `preparar_rodada.py` não reconstrói essa lista.
Os planos e resultados anteriores permanecem intactos.

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round4
```

As saídas ficam em `resultados/frame-to-frame/limiarizacao/round4/`, com
PDF ao concluir. O round4 não foi executado na preparação deste plano.

## Continuidade do desenvolvimento

O planejamento continua sendo de cinco rodadas de desenvolvimento, round1
a round5, com round0 reservado à inspeção inicial. O round3 está concluído
e o round4 preparado. O plano do round5 depende dos resultados do round4.

O round5 encerra a revisão nos dados de desenvolvimento e o congelamento
das candidatas; não é a avaliação final. A seleção e a avaliação posterior
continuam seguindo o [protocolo](../protocolo_rodadas.md), com os conjuntos
reservados preservados. Nenhuma rodada garante melhoria ou comprova
generalização a novos vídeos.
