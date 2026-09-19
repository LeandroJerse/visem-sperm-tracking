# Revisão do round1 e plano do round2

Data: 19/09/2026. Algoritmo: limiarização manual/Otsu.

## Conclusão

O desempenho foi baixo pelos critérios acordados. A maior macro-F1 foi
**0,224303**, na configuração `round1/c10`. Há excesso de detecções sem
correspondência, perdas de localização e dificuldade especialmente grave na
classe 2. Ajustar somente a classificação por área não resolve esses problemas.

A reavaliação de 15 combinações sobre as caixas já salvas elevou a maior
macro-F1 para **0,229123**, um ganho de apenas 0,004820. O round2 concentra
o orçamento em outras combinações de limiarização e morfologia, mantendo
algumas referências e alternativas de classificação. Seus resultados ainda
dependem da execução pelo pesquisador.

## Dados e critérios

- Origem: [batch do round1](../../resultados/frame-to-frame/limiarizacao/round1/batch__20260919T192640642218Z/execucao.json).
- 48 configurações, mesmos 178 quadros de 12 vídeos de desenvolvimento.
- 3.707 caixas anotadas por configuração: 3.464 normais, 109 aglomerados e
  134 pequenos. São observações em quadros, não indivíduos únicos.
- Fontes: `resumo_configuracoes.csv`, `resumo_por_video.csv`, `rodada.json`
  e as tabelas de detecções, anotações, pares e pendências das configurações.
- Mesma classe, IoU >= 0,50 e associação um para um. TP/FP/FN são somados
  antes de calcular os F1; a macro-F1 reúne as três classes com pesos iguais.
  Classe 0 continua prioritária somente no empate exato da macro-F1.
- Nenhum dado dos conjuntos de seleção ou avaliação final orientou o plano.
  O histórico de exposição anterior aos dados permanece registrado no protocolo.

As médias entre configurações não estimam generalização: a amostragem inicial
varia vários fatores simultaneamente e os quadros de um vídeo são relacionados.
A média de macro-F1 das 48 configurações foi 0,037740, a mediana 0,000323 e
18 configurações tiveram macro-F1 igual a zero.

## Melhores resultados observados

| Round1 | Macro-F1 | F1 normal | F1 aglomerado | F1 pequeno | F1 localização |
|---|---:|---:|---:|---:|---:|
| c10 | 0,224303 | 0,445643 | 0,226087 | 0,001179 | 0,320228 |
| c08 | 0,177178 | 0,363157 | 0,168378 | 0,000000 | 0,169536 |
| c03 | 0,175781 | 0,342727 | 0,184615 | 0,000000 | 0,136010 |
| c12 | 0,154564 | 0,316226 | 0,147465 | 0,000000 | 0,230341 |
| c05 | 0,130358 | 0,342825 | 0,046167 | 0,002081 | 0,387238 |

Os números completos estão no [resumo original](../../resultados/frame-to-frame/limiarizacao/round1/batch__20260919T192640642218Z/resumo_configuracoes.csv).
As cinco linhas acima são um resumo descritivo, não a seleção das cinco
finalistas prevista para a etapa posterior.

Todas usam Otsu claro. A melhor manual foi `c27`, com macro-F1 de 0,103603,
limiar 120, abertura 3 e fechamento desligado. Entre as variantes escuras,
a maior macro-F1 foi 0,000512. Por isso o round2 usa a polaridade clara.
Isso é uma decisão para estes dados e este detector, não uma conclusão
universal sobre imagens de espermatozoides.

## O que está falhando

### Localização e classificação são problemas diferentes

`round1/c10` usa Otsu claro, abertura desligada, fechamento elíptico 5 x 5,
área mínima 6, pequeno até 80 e aglomerado a partir de 1.000 pixels segmentados.

| Avaliação de c10 | TP | FP | FN | Precisão | Recall |
|---|---:|---:|---:|---:|---:|
| Normal | 1.777 | 2.734 | 1.687 | 39,39% | 51,30% |
| Aglomerado | 26 | 95 | 83 | 21,49% | 23,85% |
| Pequeno | 2 | 3.257 | 132 | 0,06% | 1,49% |
| Localização, ignorando classe | 1.857 | 6.034 | 1.850 | 23,53% | 50,09% |

Mesmo ignorando a classe, aproximadamente metade das anotações não recebeu
uma correspondência válida. Trocar um rótulo não corrige caixas ausentes,
fragmentadas ou grandes demais. Uma previsão sem correspondência conta
como FP neste protocolo; isso não determina, por si só, sua natureza biológica.

### Área mínima: a mudança mais bem sustentada

`c11`, `c10` e `c05` compartilham a mesma segmentação. Seus mínimos 1, 6 e 24
preservaram os mesmos 1.857 pares de localização, com FP respectivamente
11.852, 6.034 e 4.027. As 5.884 caixas de `c05` coincidem com as de `c10`
filtradas por área >= 24, embora usem limites de classificação diferentes.

Portanto, aumentar o mínimo de **6 para 24** elimina **2.007 FP de localização**
sem perder acertos nessa segmentação. A reavaliação exata confirmou o efeito
em todos os 12 vídeos. Mínimo 40 elimina mais 528 detecções, perdendo cinco
pares de localização, mas preservando os TP da avaliação principal.

Mínimo 60 elimina os dois pequenos corretamente classificados na referência.
Seu F1 de localização cresce, mas a macro-F1 cai. Ele não integra o round2.

### Limites entre as classes

Os limites usam **pixels da região segmentada depois da morfologia**.
Não se pode copiar diretamente a área da caixa da anotação para esses limites.

Nos pares de localização de `c10`, as áreas segmentadas têm a seguinte distribuição:

| Classe anotada | Pares | Mínimo | Mediana | Máximo |
|---|---:|---:|---:|---:|
| Normal | 1.795 | 25 | 234 | 1.068 |
| Aglomerado | 53 | 440 | 970 | 3.420 |
| Pequeno | 9 | 56 | 348 | 575 |

Esta é uma amostra condicionada à localização correta, com repetição temporal.
Não representa a distribuição de todos os objetos nem indivíduos independentes.

Limites de aglomerado 150–250 são muito baixos para muitos componentes normais.
Em `c05`, o limite 250 atribui classe aglomerado a 788 normais localizados.
Na reavaliação com mínimo 24, variar somente o limite de aglomerado mostrou:

| Aglomerado a partir de | TP | FP | FN | F1 aglomerado | Origem dos TP |
|---:|---:|---:|---:|---:|---|
| 600 | 44 | 408 | 65 | 0,156863 | Vídeos 11 e 19 |
| 800 | 40 | 219 | 69 | 0,217391 | Vídeos 11 e 19 |
| 1.000 | 26 | 95 | 83 | 0,226087 | Somente vídeo 19 |

Assim, 1.000 é a referência e 800 permanece como alternativa para recuperar
mais aglomerados. Não se afirma que 1.000 seja o limite correto universal.
Há sobreposição de áreas e concentração de acertos em poucos vídeos.

### Classe 2: área não equivale à classe biológica

Somente 9 das 134 caixas pequenas foram localizadas em `c10`. Duas previsões
têm áreas 56 e 58; as outras sete, do vídeo 35, têm áreas 339–575 e se
sobrepõem às áreas dos normais. Além disso, 104 das 134 anotações pequenas
têm melhor IoU inferior a 0,1 com qualquer previsão de `c10`.

Esse diagnóstico usa a maior IoU apenas para entender as perdas; não altera
o limiar oficial de 0,50. Aumentar o limite de pequeno não recupera regiões
que não foram localizadas e pode simplesmente reclassificar normais e FP.

Exemplos visuais salvos: [vídeo 21, quadro 1100](../../resultados/frame-to-frame/limiarizacao/round1/otsu-claro-abe3x0-fee5x1-area__cfg-81b71e8083ac__20260919T192640642218Z/midia/21_frame_1100__comparacao.png)
e [vídeo 35, quadro 0](../../resultados/frame-to-frame/limiarizacao/round1/otsu-claro-abe3x0-fee5x1-area__cfg-81b71e8083ac__20260919T192640642218Z/midia/35_frame_0__comparacao.png).

### Área máxima e morfologia

Teto 5.000 remove somente quatro FP de localização em `c10`, sem perder pares.
Teto 2.000 removeria 12 FP, mas também três aglomerados localizados. Apenas
o teto 5.000 entra como ensaio secundário; os demais casos permanecem sem teto.

Entre normais não pareados, há caixas previstas menores e maiores que as
anotadas. Um fechamento maior pode unir fragmentos, mas também juntar objetos.
O round2 compara fechamento desligado, 3, 5 e 7, além de algumas aberturas,
em vez de assumir que aumentar a morfologia sempre melhora o resultado.

### Variação entre vídeos

Todos os 26 TP de aglomerado de `c10` vieram do vídeo 19. Seu F1 de localização
varia de 0,0400 no vídeo 23 a 0,6696 no vídeo 30. Uma média global esconde
diferenças relevantes.

As variantes manuais continuam úteis à exploração: `c25`, limiar 90, obteve
maior F1 de localização nos vídeos 12 e 23; `c30`, limiar 120, no vídeo 60.
O round2 mantém 90 e refina a vizinhança de 120 com 110 e 130. Uma mesma
configuração será aplicada aos 178 quadros, sem escolher parâmetros por vídeo.

Os macro-F1 de `c10` nos vídeos 30, 47 e 60 são indefinidos por classe sem
casos. Eles não viram zero. Comparações por vídeo consideram os F1 por classe,
suporte e localização; não favorecem uma configuração só porque FP fizeram
seu macro-F1 passar de indefinido para definido.

## Reavaliação exploratória das áreas

Registro completo: [round1_reavaliacao_areas.json](round1_reavaliacao_areas.json).

Foram preservadas as caixas de `c10` e reatribuídas classes/filtros em 15
combinações. Para cada uma, o avaliador refez os pareamentos por quadro,
incluindo o diagnóstico de localização; não reutilizou os pares antigos.
Depois somou TP/FP/FN antes dos F1. A referência original foi reproduzida
antes das variações, com conferência de 712 linhas por quadro, 48 por vídeo,
quatro totais e os resumos. O registro inclui parâmetros, versões e hashes.

| Caso | Mínimo | Pequeno até | Aglomerado desde | Teto | Macro-F1 | F1 localização |
|---|---:|---:|---:|---:|---:|---:|
| c10 original | 6 | 80 | 1.000 | Sem | 0,224303 | 0,320228 |
| e09, referência refinada | 24 | 80 | 1.000 | Sem | 0,224872 | 0,387238 |
| e12, maior macro da grade | 24 | 120 | 1.000 | Sem | 0,229123 | 0,387238 |
| e13, filtro maior | 40 | 80 | 1.000 | Sem | 0,225464 | 0,408695 |
| e14, filtro excessivo | 60 | 80 | 1.000 | Sem | 0,223910 | 0,427200 |
| e15, teto de área | 24 | 80 | 1.000 | 5.000 | 0,226206 | 0,387400 |

O ganho de `e12` exige cuidado: pequeno 80→120 aumenta o F1 normal, mas
reduz seus TP de 1.777 para 1.708 e seus FP de 2.734 para 2.267. Os FP de
pequeno crescem de 1.250 para 1.786, sem recuperar pequenos adicionais.
Parte da melhoria é uma troca entre tipos de erro, não detecção de novos objetos.

São resultados exploratórios nos mesmos dados de desenvolvimento, condicionados
à segmentação original. Não são uma execução do round2 nem evidência independente
de generalização. Por isso não há promessa de melhoria nas novas segmentações.

## Plano preparado para o round2

[round2.json](../../scripts/limiarizacao/rodadas/round2.json) contém **32 configurações**,
com os mesmos 178 quadros, ordem, hashes e duas exclusões. São **5.696 avaliações**.
Não houve nova execução de detector nesta análise.

| IDs do round2 | Quantidade | Objetivo |
|---|---:|---|
| c01–c02 | 2 | Repetir round1/c10 e round1/c27 como controles |
| c03–c06 | 4 | Referência mínimo24; pequeno120; mínimo40; teto5000 |
| c07–c18 | 12 | Otsu com fechamento 0/3/7, pequeno40/80/120 e alternativa aglomerado800 |
| c19–c20 | 2 | Otsu com abertura3, fechamento5 e pequeno80/120 |
| c21–c28 | 8 | Manual90/110/120/130, cada um com fechamento3 e5 |
| c29–c30 | 2 | Manual90 com abertura5, fechamento5 e pequeno80/120 |
| c31–c32 | 2 | Manual120 com abertura3, sem fechamento e pequeno80/120 |

A referência `round2/c03` altera somente o mínimo 6→24 de `round1/c10`.
Os controles conservam todos os parâmetros originais. Os casos novos usam
polaridade clara, conectividade 8, área mínima 24 salvo o ensaio 40, e nenhum
teto salvo o ensaio 5.000. Elementos morfológicos são elípticos, com uma
iteração quando ativados.

Na referência `round2/c03`, a regra fica explícita:

| Área segmentada | Tratamento |
|---|---|
| Menor que 24 | Descartar pelo filtro de tamanho |
| 24 a 80 | Classe 2, pequeno |
| 81 a 999 | Classe 0, normal |
| 1.000 ou mais | Classe 1, aglomerado |

Esses intervalos são parâmetros a avaliar, não definições biológicas das classes.

No grupo c07–c18, cada fechamento recebe os pares de classificação
`(pequeno, aglomerado) = (40,1000), (80,1000), (120,1000), (80,800)`.
Isso permite comparar limites dentro da mesma segmentação e fechamentos
com os mesmos limites. Não se supõe que áreas calibradas com fechamento5
sejam automaticamente adequadas quando a segmentação muda.

A grade de 15 reavaliações já respondeu às primeiras perguntas de área
com fechamento5. O novo batch evita repetir toda essa grade e prioriza
combinações ainda não avaliadas. As poucas repetições completas produzem
controles e mídias verificáveis pelo pesquisador.

A lista é determinística: seed 42 fica como registro de continuidade, sem
novo sorteio. A reprodução usa o JSON salvo; `preparar_rodada.py` continua
sendo o sorteador da exploração inicial e não reconstrói este plano.
Os JSON de planos e registros de análise usam finais de linha LF no Git,
evitando mudanças de hash causadas somente por conversão de linhas no Windows.
Os IDs são locais à rodada: `round1/c10` e `round2/c10` são configurações diferentes.

Para executar na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round2
```

O executor mantém as saídas usuais e gera o PDF no batch do round2.

## O que decidir depois da execução

Comparar a macro-F1 e os F1 por classe com os controles, observando TP, FP e FN.
Verificar se a melhoria aparece em vários vídeos ou fica concentrada em um só.
Inspecionar as caixas das classes raras e as fusões causadas pela morfologia.

Se a classe 2 permanecer quase sem localização, novas mudanças apenas nos
limites de classe terão alcance restrito. Isso será uma limitação observada
desta família clássica e orientará a comparação posterior com blobs,
watershed e o híbrido com kNN já previsto. Não serão removidas classes nem
alterados os critérios para melhorar artificialmente a métrica.

O round3 e as cinco finalistas continuam dependentes da revisão conjunta.
