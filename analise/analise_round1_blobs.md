# Análise do round1 de blobs

20/09/2026. Análise das saídas existentes; nenhum detector ou nova configuração
foi executado nesta revisão. As propostas abaixo ainda não constituem o plano
congelado do round2.

## Origem e integridade

- Batch: `resultados/frame-to-frame/blobs/round1/batch__20260920T193937586038Z`.
- 48 configurações completas nos mesmos 178 quadros: 8.544 avaliações.
- 60.056 hashes de arquivos de saída conferidos, sem divergências.
- Os resumos têm 48 configurações, 576 linhas por configuração/vídeo e
  8.544 linhas por configuração/quadro. Agregações e suportes conferidos pelo
  leitor do relatório; PDF de oito páginas com hash e origens íntegros.
- Fontes: `plano.json`, `resumo_configuracoes.csv`, `resumo_por_video.csv`,
  `resumo_por_quadro.csv` e registros de anotações, detecções e pares por quadro.
- [PDF da rodada](../resultados/frame-to-frame/blobs/round1/batch__20260920T193937586038Z/relatorios/20260920T200035636661Z/relatorio.pdf).

A tentativa anterior foi interrompida por acesso negado e consta no histórico.
A repetição manteve as configurações e alterou o tratamento técnico de gravação.
A pasta da tentativa anterior não estava presente na auditoria atual;
a auditoria anterior de suas 11 configurações completas permanece registrada
na [síntese de continuidade](estado_pesquisa.md).

## Resultado e limites

Há uma região promissora, mas o desempenho ainda é insuficiente para representar
bem as três classes. O melhor F1 de indivíduos foi 0,551828, na r1c29. Isso
não significa 55% de acurácia nem validação fora do desenvolvimento.

| Configuração | F1 indivíduos | Precisão | Recall | Normais localizados | Pequenos localizados | Aglomerados localizados |
|---|---:|---:|---:|---:|---:|---:|
| r1c29 | 0,551828 | 0,503554 | 0,610339 | 2.194/3.464 | 2/134 | 0/109 |
| r1c23 | 0,373375 | 0,311054 | 0,466926 | 1.677/3.464 | 3/134 | 14/109 |
| r1c19 | 0,357670 | 0,329737 | 0,390773 | 1.404/3.464 | 2/134 | 2/109 |
| r1c26 | 0,343925 | 0,442501 | 0,281267 | 1.011/3.464 | 1/134 | 0/109 |

R1c29 teve 2.196 TP, 2.165 FP e 1.402 FN de indivíduos. Quase metade das
previsões desse grupo não encontrou correspondência válida nas anotações.
Essas contagens descrevem ocorrências nos quadros, não indivíduos únicos.

Foram previstas 4.361 classes 0, 113 classes 1 e nenhuma classe 2. Os dois
pequenos localizados foram rotulados como normais: contam como acertos de
localização e erros de classificação, conforme o protocolo vigente.
A acurácia condicional de 99,91% considera somente os pares encontrados e
não demonstra cobertura das três classes. Pequenos são apenas 3,72% das
anotações de indivíduos; o F1 agregado deve ser acompanhado de sua cobertura.

Parâmetros r1c29: polaridade clara; limiares 80–220 (máximo exclusivo), passo
5; repetibilidade 2; distância mínima 12 px; área interna 32–500 px²
(máximo exclusivo); inércia mínima 0,4; margem de caixa 4 px por lado.
Classificação: área circular estimada até 28,2743 para pequeno e a partir
de 452,3893 para aglomerado. As demais classes ocupam o intervalo intermediário.

## O efeito das caixas foi demonstrado pelos controles

| Caixa | F1 claro | F1 escuro |
|---|---:|---:|
| Original | 0,013645 | 0,000885 |
| Escala 2 | 0,220763 | 0,01136 |
| Escala 3 | 0,243805 | 0,02507 |
| Escala 4 | 0,17211 | 0,03275 |
| Margem 4 | 0,262084 | 0,01807 |
| Margem 8 | 0,331596 | 0,046965 |

Dentro de cada polaridade, esses controles preservam detector e classificação.
Entre r1c01 e r1c06 foram conferidos os mesmos 12.309 candidatos nos 178 quadros,
com índices, centros, diâmetros, áreas estimadas e classes idênticos.
Somente as caixas mudaram. Os TP de indivíduos subiram de 106 para 2.576.

Isso demonstra que a caixa original prejudicava a correspondência. Não demonstra
que ampliar indefinidamente seja adequado: escala 4 já piora o resultado claro
em relação à escala 3. As 11.939 previsões de indivíduos claros e 66.454 escuras
permanecem em cada respectivo controle; ampliar caixas não remove candidatos.

## Diagnóstico geométrico da r1c29

Usaram-se apenas centros, caixas, classes e pares já salvos. Centro dentro de
anotação é uma incidência geométrica, não uma nova definição de acerto. Pode
haver anotações sobrepostas e um centro não comprova identidade biológica.
O matching oficial continua exclusivo, por grupos e com IoU mínimo de 0,50.

| Situação dos FN oficiais | Normal | Pequeno | Total |
|---|---:|---:|---:|
| Nenhum centro dentro da anotação | 477 | 125 | 602 |
| Centro do grupo indivíduos presente, mas nenhuma caixa válida com IoU suficiente | 729 | 7 | 736 |
| Centros presentes somente como aglomerado | 57 | 0 | 57 |
| Candidato com IoU válido, perdido na correspondência exclusiva | 7 | 0 | 7 |
| Total | 1.270 | 132 | 1.402 |

Nos 729 FN normais com centro do grupo correto e IoU insuficiente, 719 têm
exatamente um centro. Desses, 390 apresentam caixa com mais do dobro da área
anotada, 112 com menos da metade e 217 entre esses limites. Portanto, a
correção exige comparar também caixas menores e revisar posição/proporção.

Exemplos em r1c29:

- Vídeo 11, quadro 0, anotação 1 e detecção 24: 17×18 px contra 29×28 px,
  razão de área 2,65 e IoU 0,3768. A caixa já está grande demais.
- Vídeo 12, quadro 100, anotação 13 e detecção 4: 27×25 px contra 18×18 px,
  razão de área 0,48 e IoU 0,48. A caixa ainda é pequena.

Dos 2.165 FP de indivíduos, 1.398 (64,6%) têm centro fora de todas as
anotações. Os outros 767 têm centro dentro de alguma anotação: 683 dentro
de indivíduos e 84 somente dentro de aglomerados. São falsos positivos
perante a referência acordada; não se deve concluir automaticamente que
todo candidato não anotado seja sujeira ou alterar a base após ver previsões.

O problema dos pequenos vem antes da classificação: 125/134 não têm centro
candidato. Mudar apenas o corte entre classes 0 e 2 não recupera essas
ocorrências nem altera o F1 agrupado quando os candidatos/caixas permanecem
iguais. A área mínima do detector e a área estimada usada para classificar
são medidas diferentes; seus valores não demonstram, por si só, uma
impossibilidade matemática de obter classe 2.

Aglomerados também precisam de investigação própria: 33/109 não têm centro,
74 têm apenas centros classificados como indivíduos e dois têm centro do
grupo aglomerados, mas caixa insuficiente. Em 30 há ao menos dois centros;
um conjunto pode ser representado por várias partes, sem uma caixa única.

## Generalidade e hipóteses

R1c29 supera r1c23 nos 12 vídeos, mas varia de F1 0,23853 no vídeo 23 a
0,79564 no 30. Também apresenta F1 0,36137 no 11 e 0,36453 no 19. R1c19
atinge 0,42373 no 23, e r1c26 chega a 0,44797 no 11 e 0,52288 no 15.
Há motivo para conservar alternativas, sem concentrar toda a busca numa
única configuração.

Nas 18 exploratórias claras, F1 mediano 0,19004 e máximo 0,55183; nas 18
escuras, mediana 0,01609 e máximo 0,08375 (r1c43). Alguns controles escuros
localizam 81–83 dos 134 pequenos, com excesso de FP; r1c43 localiza 28.
Isso justifica uma investigação limitada dessa polaridade, não uma fusão
automática dos dois resultados.

Vários parâmetros mudaram simultaneamente nas exploratórias. Não atribuir
o ganho isoladamente à inércia, distância, limiar ou área mínima, nem tratar
os 178 quadros do mesmo conjunto como 178 amostras independentes. Não houve
teste de significância ou comparação com conjuntos diferentes da limiarização.

## Proposta inicial para o round2 e decisão posterior

A proposta abaixo registra a análise antes da decisão. Posteriormente foram
aprovados CLAHE e LoG/DoG. O [plano definitivo do round2](plano_round2_blobs.md)
redistribui as 32 tentativas em 4 repetições, 12 refinamentos, 8 CLAHE e 8
LoG/DoG. Os testes dirigidos a pequenos foram incorporados aos refinamentos
e à referência escura. O texto seguinte não é o plano executável vigente.

Manter 32 configurações completas e os mesmos 178 quadros, sem alterar o
avaliador ou promover finalistas. Uma divisão possível é:

| Frente | Configurações | Pergunta |
|---|---:|---|
| Controles repetidos | 4 | O comportamento das referências permanece reproduzível? |
| Refinamento de caixas e filtros | 12 | Quais ajustes em torno das linhas promissoras reduzem caixas inadequadas e FP? |
| Recuperação de pequenos | 8 | Área mínima, forma, distância e polaridade estão eliminando candidatos úteis? |
| Contraste antes do detector | 8 | Uma melhoria controlada do contraste ajuda nas condições em que faltam candidatos? |

Nos refinamentos, comparar margens menores, a margem atual e alternativas
de escala mantendo os demais parâmetros fixos em blocos; variar poucos
fatores por comparação. Nos pequenos, testar filtros menos restritivos e
uma frente escura limitada, medindo também o custo em FP e cobertura normal.
Não declarar que área mínima 32 ou distância 12 sejam as causas isoladas.

Para contraste, a primeira extensão proposta é CLAHE, com controle sem
pré-processamento. Ela melhora contraste local, mas pode realçar ruído;
o efeito sobre F1 precisa ser medido. Incluir essa frente exige implementar
e registrar o pré-processamento como parte da configuração. Não foi
implementada, testada ou incluída em um plano executável nesta análise.

Alternativas posteriores: correção de fundo com top-hat e detecção de blobs
em múltiplas escalas por LoG/DoG. LoG/DoG são outros detectores de blobs,
não ajustes equivalentes do SimpleBlobDetector atual: exigiriam variante
identificada, referências próprias e decisão explícita sobre orçamento.
O k-NN permanece na abordagem híbrida prevista; um classificador posterior
não cria candidatos ausentes. Não ampliar simultaneamente todas essas frentes.

Fontes técnicas consultadas:

- [OpenCV: SimpleBlobDetector](https://docs.opencv.org/4.13.0/d0/d7a/classcv_1_1SimpleBlobDetector.html),
  para limiares, agrupamento, filtros e medidas estimadas.
- [OpenCV: CLAHE](https://docs.opencv.org/4.13.0/d5/daf/tutorial_py_histogram_equalization.html),
  para contraste local e limitação da amplificação de ruído.
- [OpenCV: top-hat e demais operações morfológicas](https://docs.opencv.org/4.13.0/d9/d61/tutorial_py_morphological_ops.html).
- [scikit-image: LoG, DoG e DoH](https://scikit-image.org/docs/stable/auto_examples/features_detection/plot_blob.html),
  para famílias alternativas de detectores. A documentação não demonstra
  superioridade desses métodos nos dados deste projeto.

O orçamento global continua 48/32/24/18/14, com até 122 configurações
distintas. A proposta de quatro repetições no round2 deixa 28 combinações
novas. As faixas e combinações exatas ainda devem ser preparadas e
congeladas antes da próxima execução, que permanece a cargo do pesquisador.
