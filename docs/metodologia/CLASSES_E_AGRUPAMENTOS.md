# Células individuais e agrupamentos na avaliação

[Documentação](../README.md) · [Protocolo](PROTOCOLO.md) · [Tolerância espacial](TOLERANCIA_ESPACIAL.md)

Decisão de 07/09/2026: a avaliação principal mede localização de células
individualmente anotadas (classes 0 e 2). A classe 1 delimita agrupamentos com
referência individual insuficiente. A avaliação complementar mantém todos os
objetos anotados, incluindo cada agrupamento como um objeto. Os três raios
de 10, 15 e 20 px continuam obrigatórios; 10 px é o principal.

## O que se pretende medir

O TCC investiga trajetórias individuais. A posição de uma caixa de agrupamento
não pode ser interpretada automaticamente como posição de uma única célula.
O artigo VISEM-Tracking define clusters como várias células agrupadas que
dificultam a anotação separada; distingue também células individuais e
small/pinhead. [Descrição original, Methods e Data Records](https://www.nature.com/articles/s41597-023-02173-4).

| Classe do gabarito | Papel principal | Papel complementar |
|---|---|---|
| 0 — normal/sperm | Alvo individual | Objeto e classe original |
| 2 — small/pinhead | Alvo individual, reunido à classe 0 | Objeto e classe original |
| 1 — cluster | Região aproximada sem referência individual suficiente | Um objeto agrupamento, não uma célula |

Essa política avalia localização, não a classificação morfológica ou a precisão
do tamanho da caixa. As classes previstas não decidem se uma previsão é
ignorada: todas participam do matching principal. Um detector não pode evitar
um falso positivo apenas atribuindo à sua previsão a classe cluster.

## Regra operacional por quadro e por raio

1. Usar as coordenadas originais da imagem e as anotações alinhadas pelo
   número do quadro. Anotação ausente continua `unlabeled`, fora das métricas.
2. Fazer matching Húngaro um-para-um entre todas as previsões e os alvos GT
   das classes 0 e 2. Maximizar o número de pares com distância ≤ raio e,
   entre soluções de mesma cardinalidade, minimizar a distância total.
3. Cada alvo individual sem par é FN; cada par válido é TP, mesmo quando o
   alvo está dentro de uma caixa de agrupamento.
4. Entre previsões sem par, manter como FP aquelas que estão a distância
   ≤ raio de qualquer centro GT individual. Essa proteção é geométrica e
   não depende da ordem das previsões ou de o alvo já estar pareado.
5. Das restantes, ignorar somente as cujo centro está dentro de uma caixa GT
   de classe 1. Os limites do retângulo são inclusivos, sem margem extra.
   As outras previsões são FP. Sobrepor várias caixas não ignora uma
   mesma previsão mais de uma vez.

A regra é recalculada integralmente para cada raio. Não se reutilizam os
pares ou a lista de previsões ignoradas da avaliação a 10 px para obter os
resultados a 15/20 px.

O [avaliador oficial COCO](https://github.com/cocodataset/cocoapi/blob/master/PythonAPI/pycocotools/cocoeval.py)
oferece precedente de referências ignoradas e preferência por alvos válidos.
O COCO usa sobreposição e associação por confiança. O teste de centro dentro
do retângulo e a proteção por distância aqui definidos são adaptações próprias,
não uma reprodução do protocolo COCO ou uma regra oficial VISEM.

## Limites e casos de fronteira

Com um alvo individual em (20, 20) e duas previsões em (20, 20) e (28, 20),
ambas dentro de um cluster, a primeira pode ser TP e a segunda permanece FP
a 10 px. Já uma previsão extra em (32, 20) poderá ser ignorada se não houver
outro alvo próximo. A geometria não distingue perfeitamente duplicação mal
localizada de uma célula do grupo que não foi anotada individualmente.

Consequentemente, aumentar o raio pode fazer uma previsão antes ignorada
passar a FP pela proteção dos alvos individuais. O F1 das sensibilidades
não tem garantia geral de crescimento monotônico nesta política.

Caixas de cluster podem incluir fundo e células anotadas separadamente.
A prioridade aos alvos individuais preserva sua avaliação, mas algumas
previsões incorretas sobre o fundo dentro da região poderão ser ignoradas.
Por isso reportamos quantidade de previsões ignoradas, quadros afetados e
cobertura espacial das regiões por vídeo. Resultados favoráveis da métrica
principal não demonstram separação das células dentro de agrupamentos.

## Quadros vazios, sem referência e contagem

- Arquivo GT ausente: não avaliável, nunca negativo.
- GT existente e vazio: negativo anotado; previsões são FP.
- Quadro com apenas clusters: previsões fora das regiões ignoradas continuam
  contribuindo como FP. Sem alvos individuais e sem previsões avaliáveis,
  não se atribui um acerto perfeito na métrica principal.
- TP/FP/FN são agregados dentro de cada vídeo antes de calcular F1. Um vídeo
  inteiramente sem evidência individual, composto apenas por clusters sem
  FP, não recebe F1=1.

A contagem principal compara previsões avaliadas (TP + FP) com alvos
individuais (TP + FN). Sua MAE/bias usa o universo fixo de quadros anotados,
inclusive zeros; não se muda o denominador conforme o detector ignore mais
ou menos previsões. Essa é contagem do universo avaliado, não o total
biológico de células presentes na imagem. Quantidades brutas e contagem de
todos os objetos anotados ficam identificadas separadamente.

Médias de F1 por quadro são apenas diagnósticas, com denominador informado.
A comparação científica usa agregação por vídeo e não transforma quadros,
trajetórias ou seeds do mesmo vídeo em amostras independentes.

## Auditoria descritiva do treino

A auditoria dos 17.466 quadros anotados dos 12 vídeos de treino encontrou
5.413 observações de agrupamento, em 4.056 quadros dos vídeos 11, 12, 15 e 29.
São observações repetidas ao longo do tempo, não células distintas. Há 4.250
centros individuais dentro dessas regiões e 6.277 caixas individuais com
interseção de área positiva. Nenhum quadro anotado contém somente clusters.
Isso justifica operacionalmente preservar os indivíduos explicitamente
anotados dentro de agrupamentos; não prova completude das anotações.

A área da união das caixas cluster foi recortada à imagem, sem somar duas
vezes áreas sobrepostas. A cobertura média foi 0,2869% ao resumir todos os
quadros anotados dentro de cada vídeo e dar peso igual aos 12 vídeos. Ao usar
somente quadros com cluster em cada um dos quatro vídeos pertinentes e dar
peso igual a esses quatro vídeos, a média foi 1,1233%. O segundo denominador
é distinto do primeiro. Caixas pequenas ainda podem conter várias células
ou fundo; cobertura de imagem não determina proporção de erros ignorados.

Os artefatos locais estão em
`data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/`.
O [comando oficial](../../script/README.md#agrupamentos-no-treino) verifica os
hashes e as contagens da auditoria anterior e preserva fontes e derivados.
Sua figura mostra os primeiros quadros com cluster dos quatro vídeos,
escolhidos sem executar detector.

## Coerência entre etapas

As caixas ignoradas são informação manual exclusiva do avaliador. O detector
recebe a imagem inteira, e todas as suas saídas e todos os GT originais
permanecem nos artefatos. Nenhum resultado pode ser apresentado como aplicação
autônoma se precisou das caixas GT para remover previsões ou alimentar tracking.

O treinamento YOLO mantém inicialmente as três classes originais. Simplesmente
apagar labels de cluster não implementa uma região ignorada na função de perda
e pode ensinar aquela região como fundo. Qualquer mudança dessa supervisão
exigirá definição e verificação próprias. A análise principal reunirá as
previsões por localização, igual aos demais detectores; a classificação
morfológica será complementar.

Esta regra não redefine HOTA, as identidades temporais ou as janelas de
predição. IDs de agrupamento não serão tratados como IDs individuais. A
transição indivíduo–agrupamento será auditada antes de definir sua avaliação
temporal; o rastreador não recebe a máscara manual como entrada.

## Versões e sequência de validação

- `center_distance_v1_15px`: referência retrospectiva dos resultados históricos
  com todas as classes, raio 15 e sensibilidades 10/20.
- `center_distance_v2_10px`: decisão anterior de raio 10, ainda com todas as
  classes; a auditoria de geometria não executou detectores nessa versão.
- `center_distance_v3_individuals_ignore_clusters_10px`: nova política,
  `class_policy: individuals_ignore_clusters`, principal 10 e sensibilidades
  15/20, com resultado complementar `secondary_all_objects_*`.

Não reescrever runs ou YAMLs congelados anteriores. Nenhuma seleção histórica
de T200 é promovida para v3 apenas pela mudança de métrica.

A sequência desta etapa é: auditoria de regiões no treino; casos sintéticos
do avaliador e da integração; commit da implementação; smoke real curto com
parâmetros fixos históricos, sem seleção; registro dos resultados. Só depois
se prepara a busca reproduzível, com orçamento e critério registrados antes
de observar seus resultados. O histórico de exposição dos vídeos de teste
continua uma limitação da avaliação interna; esta etapa não restaura cegueira.
