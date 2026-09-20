# Revisão do round4 e plano do round5

Data: 19/09/2026. Algoritmo: limiarização manual/Otsu.

## Conclusão

O round4 está completo e consistente. A maior macro-F1 foi **0,237044**,
em `c07`: Otsu claro, sem abertura, fechamento retangular 5 x 5, área mínima
48, máxima 5.000, pequeno até 120 e aglomerado a partir de 900 pixels
segmentados. O ganho sobre o maior valor do round3 foi **0,001630**, ou
**0,69% relativo**.

Em relação à referência retangular já testada (`round3/c15`, repetida em
`round4/c02`), a mudança favorável foi de classificação. Ela mantém as caixas
e melhora o equilíbrio medido pela macro-F1, sem localizar novos objetos.
A dificuldade com a classe 2 e a concentração dos acertos raros em poucos
vídeos permanecem. O melhor manual, `c18`, chegou a macro-F1 **0,198801** e
teve o maior F1 de aglomerado da rodada, mas localizou menos normais que Otsu.

A reavaliação de 25 combinações sobre caixas salvas não superou as duas
referências examinadas. O round5 foi preparado com 14 configurações para
investigar duas vizinhanças Otsu ainda não calculadas e novas segmentações
manuais. A perspectiva é de refinamento limitado, sem garantia de melhoria.
O pesquisador executará o batch.

## Execução e auditoria

- Origem: [registro do batch](../../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/execucao.json).
- **18 configurações concluídas nos mesmos 178 quadros: 3.204 avaliações**.
- 3.707 caixas anotadas por configuração: 3.464 normais, 109 aglomerados e
  134 pequenos. São observações ao longo dos quadros, não indivíduos únicos.
- Conferidos os 12 hashes de código, a integridade das fontes registradas,
  as agregações e os cálculos de F1, incluindo os valores sem casos.
- Presentes 3.204 arquivos de previsões e 3.204 imagens comparativas.
- Os quatro controles reproduziram exatamente os resultados de referência;
  tempos de execução não entram nessa igualdade.
- Os oito casos previstos pela reavaliação do round3 foram confirmados:
  os quatro controles e `c05`, `c07`, `c14` e `c17`.
- Os 1.457 valores indefinidos de macro-F1 por quadro correspondem
  corretamente a classe sem casos; não foram convertidos em zero.
- O [PDF da rodada](../../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/relatorios/20260919T215405414224Z/relatorio.pdf)
  está concluído, com três páginas e fontes conferidas.

| Controle no round4 | Referência no round3 |
|---|---|
| c01 | c07 |
| c02 | c15 |
| c03 | c19 |
| c04 | c22 |

Fontes: [plano executado](../../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/rodada.json),
[resumo das configurações](../../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/resumo_configuracoes.csv),
[resumo por vídeo](../../resultados/frame-to-frame/limiarizacao/round4/batch__20260919T215117276355Z/resumo_por_video.csv)
e as tabelas `deteccoes.csv`, `anotacoes.csv`, `pares.csv` e `pendentes.csv`
das configurações indicadas nesses resumos.

Esta análise utiliza as saídas salvas; não executou novos detectores.
Os dados de seleção e avaliação final não orientaram o refinamento.

## Resultados principais

| Round4 | Macro-F1 | F1 normal | F1 aglomerado | F1 pequeno | F1 localização |
|---|---:|---:|---:|---:|---:|
| c07 | 0,237044 | 0,458260 | 0,244068 | 0,008803 | 0,417590 |
| c08 | 0,236360 | 0,458518 | 0,241758 | 0,008803 | 0,417590 |
| c05 | 0,236113 | 0,453062 | 0,244068 | 0,011211 | 0,417590 |
| c06 | 0,235432 | 0,453326 | 0,241758 | 0,011211 | 0,417590 |
| c01 | 0,235414 | 0,453476 | 0,247104 | 0,005660 | 0,413683 |
| c09 | 0,234988 | 0,460517 | 0,241135 | 0,003311 | 0,417221 |
| c18, melhor manual | 0,198801 | 0,321188 | 0,273504 | 0,001712 | 0,295310 |

O ranking usa os valores completos; a tabela arredonda para apresentação.
Essas linhas não constituem a escolha das cinco finalistas.

| Configuração e avaliação | TP | FP | FN |
|---|---:|---:|---:|
| c07: normal | 1.699 | 2.252 | 1.765 |
| c07: aglomerado | 36 | 150 | 73 |
| c07: pequeno | 5 | 997 | 129 |
| c07: localização | 1.847 | 3.292 | 1.860 |
| c18: normal | 1.071 | 2.134 | 2.393 |
| c18: aglomerado | 48 | 194 | 61 |
| c18: pequeno | 1 | 1.033 | 133 |
| c18: localização | 1.209 | 3.272 | 2.498 |

FP significa previsão sem correspondência válida no protocolo. Não permite,
isoladamente, concluir que a região seja resíduo ou determinar sua natureza
biológica.

### Evolução nos dados de desenvolvimento

| Rodada | Maior macro-F1 observada |
|---|---:|
| round1 | 0,224303 |
| round2 | 0,233460 |
| round3 | 0,235414 |
| round4 | 0,237044 |

São máximos escolhidos após examinar os mesmos dados de desenvolvimento,
com quantidades e combinações de configurações diferentes. A sequência não
é uma comparação independente, uma estimativa de generalização ou evidência
de superioridade estatística.

## Comparações controladas

### Limite de aglomerado no retângulo 5

`c02` e `c07` diferem somente no limite de aglomerado: 1.000 → 900.
O F1 de localização permanece 0,417590 e as caixas são as mesmas.

- Normais: TP 1.708 → 1.699; FP 2.293 → 2.252.
- Aglomerados: TP 29 → 36; FP 107 → 150.
- Pequenos: permanecem cinco TP e 997 FP.
- Macro-F1: 0,234380 → 0,237044.

O limite menor recupera sete classificações de aglomerado, mas aumenta
os FP dessa classe e perde nove classificações normais corretas. A soma
dos TP principais cai de 1.742 para 1.740. A melhoria de macro-F1 é uma
troca entre tipos de erro, não o surgimento de novas localizações.

`c08`, com limite 950, tem macro-F1 0,236360. Acerta seis normais a mais e
três aglomerados a menos que `c07`. O melhor valor global não torna todos
os seus componentes superiores.

### Limite de pequeno na mesma segmentação

`c05` e `c07` mantêm aglomerado desde 900 e diferem somente em pequeno
até 100 ou 120. Ao aumentar o limite:

- TP normais: 1.735 → 1.699; FP normais: 2.460 → 2.252.
- TP pequenos: continuam cinco; FP pequenos: 753 → 997.
- Macro-F1: 0,236113 → 0,237044.

O limite maior reduz previsões da classe normal, elevando seu F1, mas
piora o F1 pequeno sem recuperar pequenos adicionais. Por isso a análise
dos TP, FP e FN acompanha o ranking.

### Transferência entre formas de fechamento

`c09` usa elipse 5 e `c07` usa retângulo 5, mantendo os mesmos filtros
e limites de classificação. O retângulo tem macro-F1 maior, mas F1 normal
ligeiramente menor: 0,458260 contra 0,460517. O F1 normal melhora em três
vídeos, empata em um e piora em oito. Entre os dez vídeos com macro-F1
definida nas duas configurações, melhora em quatro, empata em um e piora
em cinco.

Assim, transferir os mesmos limites entre segmentações não garante ganho
uniforme. Os resultados por vídeo continuam necessários para interpretar
as pequenas diferenças globais.

### Refinamento manual de 110 para 112

`c17` e `c18` mantêm fechamento elíptico 7, mínimo 48, máximo 5.000,
pequeno até 120 e aglomerado desde 1.000. Muda somente o limiar manual:
110 → 112.

| Resultado | Manual 110, c17 | Manual 112, c18 |
|---|---:|---:|
| Macro-F1 | 0,191321 | 0,198801 |
| TP normais | 1.003 | 1.071 |
| FP normais | 2.031 | 2.134 |
| TP aglomerados | 50 | 48 |
| FP aglomerados | 218 | 194 |
| TP pequenos | 0 | 1 |
| FP pequenos | 779 | 1.033 |
| TP localização | 1.130 | 1.209 |
| FP localização | 2.951 | 3.272 |

O F1 normal melhora em quatro vídeos, empata em três e piora em cinco.
O F1 de localização melhora em seis, empata em três e piora em três.
Há melhoria agregada, acompanhada de mais FP e sem uniformidade entre vídeos.

Essa comparação é controlada. Resultados anteriores com limiar 115 e
pequeno até 80 não isolam o efeito do limiar para normais ou pequenos;
não são usados aqui para concluir superioridade de 112 sobre 115.

## Compromissos entre as três classes

Nenhuma configuração é melhor em todos os F1 de classe. Os maiores valores
individuais foram: normal em `c09` (0,460517), aglomerado em `c18` (0,273504)
e pequeno em `c03` (0,011364). O último é o controle manual 105 com pequeno
até 80: quatro TP e 566 FP pequenos, todos os acertos no vídeo 36.

Essas diferenças não alteram o critério acordado: macro-F1 principal, com
prioridade da classe 0 somente no empate exato. Esta análise não seleciona
finalistas nem prova generalização.

## Áreas: limites dependem da segmentação

As áreas usadas na classificação são os pixels do componente após a
morfologia, não a área da caixa anotada. Os números abaixo descrevem
apenas os pares salvos de localização. A amostra é condicionada ao sucesso
de localização e contém repetição temporal.

| Configuração | Classe real | Pares localizados | Mediana da área | Percentis 10–90 |
|---|---|---:|---:|---:|
| c07 | Normal | 1.782 | 245 | 146–464 |
| c07 | Aglomerado | 54 | 1.037 | 506–1.715 |
| c07 | Pequeno | 11 | 357 | 71–423 |
| c18 | Normal | 1.124 | 286,5 | 149–504 |
| c18 | Aglomerado | 68 | 1.058,5 | 542–1.556 |
| c18 | Pequeno | 17 | 179 | 146–202 |

Percentis calculados por interpolação linear no índice `(n - 1) × p`,
arredondados ao pixel inteiro. As medianas preservam os valores calculados.

### Faixas diagnósticas em c07

Aplicar uma faixa aos pares existentes não refaz o pareamento nem calcula
o F1 de uma configuração nova. As tabelas seguintes servem para estabelecer
hipóteses antes de uma reavaliação exata.

| Pequeno até | Pequenos localizados na faixa | Normais localizados na faixa | FP de localização na faixa |
|---:|---:|---:|---:|
| 100 | 5 | 36 | 717 |
| 110 | 5 | 51 | 828 |
| 120 | 5 | 72 | 925 |
| 130 | 5 | 111 | 1.024 |

Nenhum limite dessa faixa recupera um pequeno localizado adicional.
Os cinco casos estão no vídeo 21; os outros seis pequenos localizados,
do vídeo 35, têm áreas 357–585 e se sobrepõem às áreas normais.

| Aglomerado desde | Aglomerados localizados na faixa | Normais localizados na faixa | FP de localização na faixa | Aglomerados por vídeo |
|---:|---:|---:|---:|---|
| 800 | 42 | 19 | 224 | 6 no vídeo 11; 36 no vídeo 19 |
| 850 | 40 | 15 | 175 | 4 no vídeo 11; 36 no vídeo 19 |
| 900 | 36 | 11 | 139 | 1 no vídeo 11; 35 no vídeo 19 |
| 950 | 33 | 5 | 126 | 33 no vídeo 19 |

Baixar 900 para 850 inclui quatro aglomerados localizados adicionais,
mas também quatro normais e mais 36 FP de localização nessa classe.
A recuperação de aglomerados tem um custo que precisa aparecer nos F1
e nas contagens, sem tratar a quantidade detectada como quantidade correta.

### Faixas diagnósticas no manual c18

Os 17 pequenos localizados de `c18` estão no vídeo 21. Suas áreas vão de
114 a 423; apenas um cabe no limite atual 120. Portanto, os limites úteis
para examinar a classificação manual podem diferir dos limites de Otsu.

| Pequeno até | Pequenos localizados na faixa | Normais localizados na faixa | FP de localização na faixa |
|---:|---:|---:|---:|
| 120 | 1 | 47 | 986 |
| 160 | 4 | 133 | 1.268 |
| 200 | 15 | 267 | 1.526 |

Aumentar o limite manual pode recuperar rótulos pequenos que já possuem
caixas localizadas, mas também reclassifica numerosos normais e FP.
Os acertos potenciais permanecem concentrados em um único vídeo, com
quadros relacionados; não são 15 observações independentes.

| Aglomerado desde | Aglomerados localizados na faixa | Normais localizados na faixa | FP de localização na faixa |
|---:|---:|---:|---:|
| 900 | 56 | 12 | 248 |
| 1.000 | 48 | 6 | 188 |
| 1.100 | 19 | 2 | 165 |

Subir de 1.000 para 1.100 retira 29 aglomerados localizados da faixa,
enquanto elimina quatro normais e 23 FP de localização dessa classe.
O custo concentra-se nos dois vídeos com aglomerados acertados:
vídeo 11, de 20 para três; vídeo 19, de 28 para 16.

### Filtros mínimo e máximo

O mínimo 48 preserva os cinco TP pequenos atuais de `c07`; mínimo 64
descartaria um deles, e mínimo 80 descartaria todos. O teto de 5.000 já
removeu componentes muito grandes. Em `c07`, reduzi-lo para 4.000 não
mudaria as previsões; 3.000 eliminaria quatro aglomerados localizados e
nenhum FP. Esses custos já foram observados na análise da mesma segmentação
no [round3](round3_revisao.md).

No manual `c18`, teto 4.000 descartaria somente dois FP de localização;
teto 3.000 descartaria seis FP e dois aglomerados localizados. Isso não
sustenta apertar os filtros como solução geral nem ajustar um limite
exatamente à área dos poucos pequenos corretos.

## Localização, classes raras e variação por vídeo

Em `c07`, somente 11 das 134 anotações pequenas são localizadas e cinco
recebem a classe correta. No manual `c18`, 17 são localizadas e apenas uma
recebe a classe correta. Há duas limitações diferentes: regiões que não
recebem uma caixa com IoU suficiente e regiões localizadas com classe errada.
Alterar limites de classificação atua somente sobre a segunda.

Isso não atribui todas as perdas à iluminação: a segmentação, a morfologia,
os filtros e a forma ou dimensão das caixas também podem impedir o pareamento.
Os limites continuam usando IoU >= 0,50; o diagnóstico não relaxa o critério.

O F1 de localização de `c07` vai de 0,078240 no vídeo 60 a 0,746269 no
vídeo 30. Em `c18`, vai de zero no vídeo 30 a 0,624176 no vídeo 22.
O melhor resultado global esconde diferenças importantes entre vídeos.

A macro-F1 de `c07` é indefinida nos vídeos 30 e 60; a de `c18`, nos
vídeos 23, 35 e 47. Valores sem casos não viram zero. Comparações por vídeo
devem examinar suporte, contagens e F1 por classe, sem favorecer uma
configuração por produzir FP que tornem uma macro-F1 antes indefinida
matematicamente definida.

## Reavaliação exata de 25 combinações

O arquivo [round4_reavaliacao_areas.json](round4_reavaliacao_areas.json)
registra a grade definida antes das variações, fontes, versões e resultados
totais e por vídeo. Foram usados somente caixas, classes e áreas salvas;
nenhum detector foi executado nesta reavaliação.

- `c07`, Otsu retângulo 5: pequeno 100/110/120/130 × aglomerado
  800/850/900/950 — 16 combinações, incluindo sua referência.
- `c18`, manual 112 elipse 7: pequeno 120/160/200 × aglomerado
  900/1.000/1.100 — nove combinações, incluindo sua referência.
- Mínimo 48 e máximo 5.000 em todos os casos.

As duas referências reproduziram, cada uma, 712 linhas de métricas por
quadro, 48 por vídeo, quatro totais e os resumos antes das 23 variações.
Os 23 hashes das fontes foram conferidos antes e depois. O avaliador refez
os pareamentos em cada quadro e combinação; as contagens foram agregadas
antes dos F1. A grade não foi ampliada depois dos resultados.

**Nenhuma variação superou sua referência.** As matrizes abaixo apresentam
macro-F1, com arredondamento somente para exibição.

| Otsu: pequeno até | Aglomerado 800 | 850 | 900 | 950 |
|---:|---:|---:|---:|---:|
| 100 | 0,227096 | 0,233943 | 0,236113 | 0,235432 |
| 110 | 0,227869 | 0,234695 | 0,236849 | 0,236166 |
| 120 | 0,228092 | 0,234900 | **0,237044** | 0,236360 |
| 130 | 0,227114 | 0,233913 | 0,236050 | 0,235369 |

| Manual 112: pequeno até | Aglomerado 900 | 1.000 | 1.100 |
|---:|---:|---:|---:|
| 120 | 0,196071 | **0,198801** | 0,150076 |
| 160 | 0,194439 | 0,197167 | 0,148437 |
| 200 | 0,189769 | 0,192557 | 0,143869 |

No Otsu, reduzir aglomerado 900 para 850 eleva TP de 36 para 40 e FP de
150 para 190, piorando a macro-F1 em 0,002143. Três acertos adicionais
vêm do vídeo 11 e um do 19. Reduzir até 800 eleva TP a 42, mas FP a 243.
Aumentar pequeno 120 para 130 perde 39 TP normais sem ganhar TP pequenos.

No manual, aumentar pequeno 120 para 160 recupera três pequenos, mas perde
86 TP normais; FP pequenos passam de 1.033 para 1.401. Com limite 200,
TP pequenos passam de um para 15, todos no vídeo 21, ao custo de 220 TP
normais e 1.793 FP pequenos. A macro-F1 cai para 0,192557. Subir aglomerado
1.000 para 1.100 perde 29 TP aglomerados e reduz somente 27 FP dessa classe;
a macro-F1 cai para 0,150076, mantendo pequeno 120.

As contagens e métricas de localização permanecem idênticas em cada origem:
foram alterados somente rótulos, não caixas ou filtros. Essa exploração
usa os mesmos dados de desenvolvimento e não demonstra generalização.
Os valores 875/925 do próximo plano ainda não foram reavaliados.

## Configurações preparadas para o round5

O [round5.json](../../scripts/limiarizacao/rodadas/round5.json) contém
**14 configurações × 178 quadros = 2.492 avaliações**. Preserva exatamente
a ordem, os hashes e as duas exclusões aprovadas. Os IDs abaixo são do round5.

| IDs | Quantidade | Finalidade |
|---|---:|---|
| c01–c04 | 4 | Controles de round4/c07, c09, c01 e c18 |
| c05–c06 | 2 | Otsu retângulo 5, pequeno 120 e aglomerado 875/925 |
| c07–c10 | 4 | Manual 111/113/114/115 com elipse 7 |
| c11–c14 | 4 | Manual 112/113, cada um com elipse 5 e retângulo 5 |

Todas mantêm polaridade clara, abertura desligada, uma iteração de
fechamento, conectividade 8, área mínima 48, máxima 5.000 e pequeno até 120.
Os manuais usam aglomerado desde 1.000. Os controles Otsu preservam seus
limites anteriores: 900 nas configurações de fechamento 5 e 1.000 na elipse 7.

### Motivos das escolhas

1. **Quatro controles.** Preservam o maior macro-F1, a elipse 5 para
   comparação de forma, a elipse 7 de rodadas anteriores e o melhor manual.
   São referências experimentais; não são a seleção das finalistas.
2. **Somente dois refinamentos Otsu.** A grade com passo 50 favoreceu 900;
   875/925 investigam os intervalos adjacentes com passo 25. São hipóteses
   prospectivas, sem ganho já demonstrado. Não serão escolhidos limiares
   específicos por vídeo ou exatamente ajustados à área de algum objeto.
3. **Manual 111/113/114/115, com âncora 112.** O ganho controlado de 110
   para 112 justifica examinar essa vizinhança. Incluir 115 com pequeno 120
   permite comparação sem a diferença de classificação do teste histórico,
   que usava pequeno 80. A grade cobre o intervalo 111–115 contando o controle.
4. **Separar tamanho e forma do fechamento manual.** Nos limiares 112 e
   113, as configurações com elipse 7 já têm contrapartes com elipse 5;
   estas recebem contrapartes retangulares 5. Assim, a comparação de forma
   mantém o tamanho, e a comparação de tamanho mantém a forma. O benefício
   observado do retângulo 5 em Otsu não é presumido no manual.
5. **Limitar o orçamento.** A reavaliação já descartou várias mudanças de
   classe. Não há motivo para repeti-las no batch apenas para aumentar sua
   quantidade. Não foram acrescentados filtros, pré-processamentos ou
   famílias de algoritmos ao detector.

O plano completo é determinístico; a seed 42 é preservada no histórico.
Para repetir, use este JSON salvo. `preparar_rodada.py` não reconstrói sua
lista. Os planos e resultados anteriores permanecem intactos.

Na raiz do projeto, o pesquisador executa:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round5
```

As saídas serão gravadas em `resultados/frame-to-frame/limiarizacao/round5/`,
com PDF automático ao concluir. **O round5 foi somente preparado; não foi
executado nesta etapa.**

## Continuidade e última rodada de desenvolvimento

O planejamento permanece de cinco rodadas de desenvolvimento, round1 a
round5, com round0 reservado à inspeção inicial. O round4 está concluído
e o round5 está preparado. Sua execução e revisão conjunta ainda são
necessárias antes de encerrar o desenvolvimento e congelar candidatas.

Após a última rodada e sua revisão conjunta, serão congeladas as candidatas
para a seleção posterior. O round5 não é a avaliação final. Permanecem as
etapas, conjuntos reservados e regras do [protocolo](../protocolo_rodadas.md),
incluindo a mesma métrica principal e o mesmo desempate.
