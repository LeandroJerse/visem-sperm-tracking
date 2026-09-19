# Revisão do round2 e plano do round3

Data: 19/09/2026. Algoritmo: limiarização manual/Otsu.

## Conclusão

O round2 concluiu as 32 configurações nos mesmos 178 quadros, sem
inconsistências na auditoria. A maior macro-F1 passou de **0,224303** no
round1 para **0,233460** no round2: **+0,009157**, ou **4,08% de ganho relativo**.
Houve progresso, mas a classe pequena continua com desempenho muito baixo.

A melhor configuração foi `round2/c17`: Otsu claro, sem abertura,
fechamento elíptico 7 x 7, área mínima 24, pequeno até 120 e aglomerado
a partir de 1.000 pixels segmentados.

O fechamento 7 não melhorou uniformemente a detecção. Em relação ao
fechamento 5 com os mesmos limites de classe, houve menos acertos de normais
e de localização, compensados na macro-F1 por mais acertos das classes raras.
O round3 mantém as duas segmentações para comparação.

## Fontes e conferências

- [Batch do round2](../../resultados/frame-to-frame/limiarizacao/round2/batch__20260919T203029199281Z/execucao.json).
- [Resumo por configuração](../../resultados/frame-to-frame/limiarizacao/round2/batch__20260919T203029199281Z/resumo_configuracoes.csv)
  e [resumo por vídeo](../../resultados/frame-to-frame/limiarizacao/round2/batch__20260919T203029199281Z/resumo_por_video.csv).
- Tabelas de caixas, pares, pendências e métricas das configurações analisadas.
- [Análise anterior](round1_revisao.md), que justificou a preparação do round2.

Foram conferidos o plano salvo, as 32 configurações, 12 hashes de arquivos
do código arquivado, as 5.696 avaliações e suas mídias e previsões. As somas
de TP/FP/FN por quadro, vídeo e total coincidem com os resumos. O PDF consta
concluído, com três páginas e hashes consistentes.

Os controles `round2/c01 = round1/c10` e `round2/c02 = round1/c27`
reproduziram caixas, classes, métricas, pares, pendências e previsões.
Diferenças de tempo não entram nessa comparação. A correspondência exata
dos controles permite comparar os resultados das rodadas operacionalmente.

Cada configuração foi avaliada contra 3.707 caixas anotadas: 3.464 normais,
109 aglomerados e 134 pequenos. São registros em quadros, não indivíduos
independentes. Casos indefinidos continuam registrados como `sem_casos`.
Não foram usados os conjuntos reservados de seleção ou avaliação final.

## Resultados principais

| Referência | Macro-F1 | F1 normal | F1 aglomerado | F1 pequeno | F1 localização |
|---|---:|---:|---:|---:|---:|
| Melhor round1, c10 | 0,224303 | 0,445643 | 0,226087 | 0,001179 | 0,320228 |
| Round2/c17, fechamento7 e pequeno120 | 0,233460 | 0,453476 | 0,243346 | 0,003557 | 0,387063 |
| Round2/c16, fechamento7 e pequeno80 | 0,229542 | 0,440337 | 0,243346 | 0,004942 | 0,387063 |
| Round2/c04, fechamento5 e pequeno120 | 0,229123 | 0,459202 | 0,226087 | 0,002081 | 0,387238 |
| Round2/c05, fechamento5 e mínimo40 | 0,225464 | 0,445643 | 0,226087 | 0,004662 | 0,408695 |
| Round2/c24, manual110 e fechamento5 | 0,168551 | 0,318640 | 0,187013 | 0 | 0,269329 |

Todas as linhas do round2 acima usam polaridade clara, abertura desligada,
aglomerado desde 1.000 e nenhum teto de área. O mínimo é 24, salvo `c05`;
`c05` e `c24` usam pequeno até 80.

O F1 de localização das configurações com maior macro-F1 subiu 20,87% entre
as rodadas, mas grande parte desse ganho decorre do filtro mínimo 6→24 já demonstrado na revisão
anterior. O fechamento 7, isoladamente, praticamente não melhorou essa métrica.

A média de macro-F1 das configurações passou de 0,037740 para 0,175863 e
a mediana, de 0,000323 para 0,207251. Essas distribuições descrevem listas
de testes diferentes: o round2 excluiu regiões ruins do espaço de parâmetros,
como a polaridade escura. Não representam uma comparação pareada nem prova
de ganho dessa magnitude para o detector.

## Mudanças que puderam ser isoladas

### Fechamento 5 contra 7

`c04` e `c17` diferem somente no tamanho do fechamento. Os limites de classe
e o filtro mínimo permanecem iguais.

| Contagem | Fechamento5, c04 | Fechamento7, c17 |
|---|---:|---:|
| TP normal | 1.708 | 1.696 |
| TP aglomerado | 26 | 32 |
| TP pequeno | 2 | 3 |
| TP localização | 1.857 | 1.825 |
| FP localização | 4.027 | 3.898 |

A macro-F1 aumenta 0,004336, enquanto o F1 normal cai 0,005726 e piora
em oito dos 12 vídeos. Os 32 acertos de aglomerado de `c17` vêm somente do
vídeo 19. Seus três acertos pequenos vêm do vídeo 21, quadros 1100, 1200
e 1400, que são temporalmente relacionados.

Portanto, fechamento 5 permanece uma referência útil. Fechamento 9 pode
ser investigado em poucos ensaios, sem pressupor que aumentar o elemento
morfológico continue trazendo benefício. Ele também pode unir objetos.

### Limite de pequeno 80 contra 120

`c16` e `c17` têm as mesmas caixas. Aumentar o limite de pequeno para 120
mantém três TP pequenos, mas aumenta seus FP de 1.077 para 1.550. Os TP
normais caem de 1.751 para 1.696 e seus FP, de 2.738 para 2.320.

A maior macro-F1 não significa que apareceram novos objetos localizados:
há uma troca entre precisão e recuperação e uma redistribuição de erros.
Nos pares atuais de `c17`, aumentar ainda mais o limite para 160 ou 200
não recuperaria pequenos adicionais, mas passaria mais 170 e
414 normais localizados para a faixa pequena, além dos 68 já nessa faixa
com limite 120. Isso desaconselha aumentar
indiscriminadamente esse limite.

### Abertura

Adicionar abertura 3 antes do fechamento 5 (`c03`→`c19`) reduz a macro-F1
de 0,224872 para 0,214613 e os pares de localização de 1.857 para 1.704.
Os dois pequenos corretamente classificados deixam de ser recuperados.
Essa combinação não será o centro do refinamento seguinte.

### Filtros de área

Os diagnósticos abaixo contam o que seria removido das previsões e pares
atuais de `c17`. Sozinhos, não substituem o novo pareamento para calcular F1.

| Filtro | FP de localização descartados | Pares atuais descartados |
|---|---:|---|
| Mínimo32 | 258 | Dois normais |
| Mínimo40 | 457 | Cinco normais |
| Mínimo48 | 622 | Cinco normais |
| Máximo2000 | 18 | Quatro aglomerados |
| Máximo3000 | 4 | Quatro aglomerados |
| Máximo5000 | 4 | Nenhum |

Os mínimos 32/40/48 preservam os três pequenos atuais, cujas áreas são
56, 66 e 67. Isso sustenta sua reavaliação, sem escolher um limite exatamente
ajustado à menor dessas três observações. O teto 5.000 segue secundário:
os quatro FP removidos são componentes muito grandes do vídeo 23.

### Limite de aglomerado

Com fechamento 7, baixar o limite de 1.000 para 800 (`c16`→`c18`)
eleva TP aglomerados de 32 para 38, mas também FP de 122 para 278.
A macro-F1 cai de 0,229542 para 0,209803.

No diagnóstico de áreas dos pares de `c17`, limites 900, 1.000 e 1.100
preservam respectivamente 34, 32 e 23 aglomerados localizados. Assim,
a vizinhança de 1.000 merece refinamento moderado. Aumentos muito maiores
tendem a perder aglomerados sem resolver a localização dos objetos ausentes.

## Limitações que permanecem

A classe pequena continua quase sem recuperação. `c17` localiza nove
anotações dessa classe: três viram pequenos, e seis do vídeo 35, com áreas
371–595, viram normais. Área segmentada não é uma definição biológica de classe.

Algumas configurações manuais recuperam casos diferentes: `c25`, manual120
e fechamento3, acerta oito pequenos, todos no vídeo 21, com 2.523 FP dessa
classe. `c21`, manual90 e fechamento3, acerta três pequenos nos vídeos 12
e 15, mas tem 2.897 FP pequenos. São pistas sobre contraste e segmentação,
não uma justificativa para escolher parâmetros por vídeo ou misturar saídas
automaticamente.

Descritores já salvos também foram inspecionados. Em `c17`, alongamento
maior que 3 aparece em 68 FP e nenhum par atual. Intensidade abaixo de 100
aparece em 341 FP e nenhum par, mas 326 deles são do vídeo 23, mostrando
forte dependência da iluminação. Remover objetos na borda excluiria 611 FP,
mas também 141 normais e 23 aglomerados localizados. Não foram adicionados
filtros de forma, intensidade ou borda ao detector nesta etapa.

Os resultados por vídeo continuam essenciais: a macro-F1 global não demonstra
robustez entre vídeos. Não foram criados novos pesos, novos limiares de IoU
ou um novo critério de seleção. A prioridade da classe 0 permanece somente
para empate exato da macro-F1.

## Reavaliação exata de 20 combinações

O registro [round2_reavaliacao_areas.json](round2_reavaliacao_areas.json)
contém 20 combinações únicas, incluindo a referência original. A grade foi
definida antes das variações: pequeno 80/100/120/140 e aglomerado
900/950/1000/1050, com mínimo24; mais os mínimos32/40/48 e o teto5000,
isoladamente, mantendo pequeno120 e aglomerado1000.

O avaliador refez os pareamentos usando as caixas salvas de `c17`, sem
executar o detector. A referência reproduziu 712 linhas de métricas por
quadro, 48 por vídeo, quatro totais e os resumos antes das 19 variações.
As contagens foram agregadas antes dos F1; os 15 hashes das fontes
permaneceram iguais. Parâmetros, versões, contagens e métricas por vídeo
estão registrados no JSON.

| Variação sobre c17 | Macro-F1 | F1 localização | Resultado |
|---|---:|---:|---|
| Original: mínimo24, pequeno120, aglomerado1000 | 0,233460 | 0,387063 | Referência |
| Mínimo32 | 0,233676 | 0,397601 | Menos 260 FP pequenos |
| Mínimo40 | 0,233907 | 0,405888 | Menos 462 FP pequenos |
| Mínimo48 | 0,234161 | 0,413495 | Menos 627 FP pequenos |
| Máximo5000 | 0,234712 | 0,387227 | Menos quatro FP aglomerados |

**Nenhuma das regras vizinhas de classificação superou pequeno120 e
aglomerado1000.** Assim, o round3 não repete uma grade ampla desses limites.
Pequeno140 perde 76 TP normais sem ganhar TP pequenos; pequeno100 recupera
34 TP normais, mas acrescenta 189 FP normais e também reduz a macro-F1.

Mínimo48 preserva os TP da avaliação principal (1.696 normais, 32 aglomerados
e três pequenos). Perde cinco pares do diagnóstico de localização: um no
vídeo 11 e quatro no 15. Mínimo40 perde os mesmos cinco pares e remove menos
FP, justificando priorizar 48 para testar nas próximas combinações.

O teto5000 remove quatro FP do vídeo 23 e traz um ganho absoluto de apenas
0,001253 na macro-F1. Não recupera objetos. Os acertos de aglomerados e
pequenos continuam concentrados, respectivamente, nos vídeos 19 e 21.

Esses resultados são exploração dos mesmos dados de desenvolvimento,
condicionada à segmentação `c17`. Não constituem execução do round3 nem
validação independente. A combinação simultânea de mínimo48 e máximo5000
e sua transferência para outras segmentações ficam para o novo batch.

## Configurações preparadas para o round3

[round3.json](../../scripts/limiarizacao/rodadas/round3.json) contém
**24 configurações**, nos mesmos **178 quadros**, totalizando **4.272 avaliações**.
Nenhum detector foi executado para preparar esta rodada.

| IDs round3 | Quantidade | Comparação |
|---|---:|---|
| c01–c04 | 4 | Controles: round2/c17, c04, c24 e c25 |
| c05–c10 | 6 | Otsu fechamento7/5 com mínimo48, teto5000 e ambos juntos |
| c11–c14 | 4 | Otsu fechamento9, mínimos24/48 e teto desativado/5000 |
| c15–c16 | 2 | Fechamento retangular5/7 contra a elipse do mesmo tamanho |
| c17–c24 | 8 | Manual100/105/110/115, cada um com fechamento5 e7 |

Os controles têm finalidades diferentes: `c01` conserva a maior macro-F1,
`c02` a alternativa Otsu com mais acertos normais, `c03` a melhor manual
global e `c04` a manual que acertou oito pequenos. Preservar esta última
ajuda a observar perdas da classe rara; não cria um novo critério de seleção.

### Motivo de cada mudança

1. **Filtros mínimo e máximo separados e combinados.** Os ensaios isolados
   permitem atribuir o efeito a cada filtro. O mínimo48 foi escolhido pela
   remoção de FP preservando os TP principais na referência, não por uma
   garantia de que preserve todos os objetos de outras segmentações.
2. **Fechamentos5 e7 preservados.** O maior macro-F1 de7 não justifica
   descartar5, que preservou mais normais e teve desempenho superior em
   vários vídeos. Os dois recebem os mesmos ensaios de filtro.
3. **Fechamento9 em quatro casos.** É uma exploração limitada da vizinhança
   de7. Cada caso tem uma contraparte com fechamento7 e os mesmos filtros,
   permitindo identificar recuperação de fragmentos ou fusões prejudiciais.
4. **Dois fechamentos retangulares.** Mudam somente a forma do elemento,
   comparados à elipse de igual tamanho com os mesmos filtros e classes.
   Como a morfologia alterou o equilíbrio entre classes, investigar a forma
   é uma hipótese adicional limitada. Não há melhoria demonstrada ainda.
5. **Manual próximo de110.** O limiar110 apresentou a melhor macro-F1 manual
   do round2. Os valores100/105/110/115 refinam essa região, com fechamentos5/7
   e filtros iguais. As novas combinações não recebem parâmetros por vídeo.
6. **Classificação mantida.** Os novos casos Otsu usam pequeno120 e
   aglomerado1000; os manuais usam pequeno80 e aglomerado1000, como sua
   referência anterior. A grade exata sobre Otsu7 não sustentou limites
   vizinhos melhores. Esses valores continuam sendo hipóteses quando a
   segmentação muda.

Todas as novas configurações têm abertura desligada, polaridade clara,
conectividade8 e uma iteração de fechamento. As manuais usam mínimo48 e
teto5000. Os controles preservam os parâmetros originais. As formas e os
tamanhos já eram parâmetros disponíveis; não foi alterado o código do detector.

O orçamento caiu de 32 para 24 configurações porque a reavaliação das caixas
já respondeu às dúvidas iniciais de classificação. Não é necessário repetir
integralmente essa grade para gerar novas imagens. As repetições escolhidas
funcionam como controles e conferência completa pelo pesquisador.

A lista é determinística, sem novo sorteio. A seed42 registra continuidade;
a reprodução usa este JSON, com a ordem e os hashes das entradas preservados.
Os IDs valem dentro de cada rodada. Os planos anteriores permanecem intactos.

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round3
```

O executor grava em `resultados/frame-to-frame/limiarizacao/round3/` e gera
o PDF do batch. A análise seguinte comparará macro-F1, TP/FP/FN por classe,
localização e distribuição dos erros entre vídeos, mantendo os critérios
acordados. Não serão escolhidas automaticamente as cinco finalistas.

## Cinco rodadas de desenvolvimento

A solicitação atual estabelece cinco rodadas para esta família de limiarização:

| Rodada | Papel |
|---|---|
| Round0 | Inspeção inicial, fora da contagem das cinco rodadas |
| Round1 | Exploração ampla: 48 configurações, já executadas |
| Round2 | Refinamento dirigido: 32 configurações, já executadas |
| Round3 | 24 configurações preparadas para refinar vizinhanças e interações |
| Round4 | Refinar e confirmar hipóteses apoiadas pelo round3 |
| Round5 | Última comparação de desenvolvimento e congelamento das candidatas |

Os planos do round4 e do round5 serão definidos somente após os resultados
anteriores. Não se trata de fabricar melhorias em todas as rodadas: perdas,
estagnação e limites do método também serão documentados.

Round5 não é avaliação final. Depois do desenvolvimento permanecem as etapas
já acordadas nos dados reservados: seleção das cinco finalistas, avaliação
em vídeos e avaliação final após congelar as escolhas. O orçamento de cinco
rodadas não altera o histórico de exposição aos dados nem torna inéditas
as imagens de desenvolvimento.
