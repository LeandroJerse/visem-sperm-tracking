# Validação completa das finalistas do threshold v3

Resultado posterior: [validação concluída e conferida](#resultados-da-validação--08092026),
com T218/o0/c2 selecionada. Depois, foi registrado seu
[congelamento para desenvolvimento](CONGELAMENTO_THRESHOLD_V3.md), sem liberar
teste ou folds. O protocolo prospectivo
abaixo permanece preservado.

## Estado e finalidade

Protocolo prospectivo registrado em 08/09/2026, antes de abrir os vídeos e
anotações de validação para esta bateria. O
[plano executável](../../configs/detection/threshold/validation_v3.yaml)
é a referência dos valores resolvidos. O executor e seus controles estão
implementados, incluindo revisão cruzada e testes sintéticos de entradas,
completude, métricas e adulteração de artefatos. O código, o plano e os testes
pertinentes devem ser registrados em commit antes da execução. Este registro
prospectivo não afirma que a bateria científica já foi executada.

A finalidade é escolher entre **T219/o0/c2 e T218/o0/c2**, as duas finalistas do
refinamento de treino, nos quatro vídeos completos de validação. A conclusão
será uma **seleção na validação**, destinada a uma futura decisão de
congelamento. A bateria não congela automaticamente uma configuração, não
executa o teste e não verifica a hipótese central sobre fluxo óptico.

## Origem imutável e identidade dos candidatos

O plano identifica a
[run de refinamento](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/manifest.json),
seu arquivo de finalistas e a
[conferência independente](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json)
por caminho e SHA-256. Parâmetros devem ser recuperados das finalistas
verificadas, não reconstruídos somente a partir do nome abreviado.

| Configuração | SHA-256 dos parâmetros |
|---|---|
| `t219_o0_c2` | `2bee065ae23c3a63f2f03888d933fed7e2d2b0c67ffd6d05e243195efc9b78a9` |
| `t218_o0_c2` | `5b9dacca7e53b226fe90c42f1cb98d673193f0b43d0af8e2952677bc733acfa3` |

Os hashes completos do manifesto de origem, finalistas, conferência,
[split](../../configs/protocol/splits.yaml) e
[inventário versionado](../../data/manifests/visem_tracking.csv) constam no YAML.
Qualquer divergência deve impedir a seleção. Não serão ajustados limiar,
morfologia, filtro de área, métrica ou regra de desempate depois de observar a
validação. Alterar o plano exige uma nova versão e a declaração da exposição
já ocorrida, preservando as evidências anteriores.

## Universo e acesso às entradas

| Vídeo de validação | Quadros esperados por candidato |
|---|---:|
| 14 | 1.470 |
| 19 | 1.470 |
| 36 | 1.470 |
| 52 | 1.440 |
| **Total por candidato** | **5.850** |
| **Total dos dois candidatos** | **11.700** |

Essas contagens vêm do inventário existente; não foram inferidas de uma duração
nominal. São oito pares configuração–vídeo, avaliados sobre os mesmos 5.850
quadros físicos. A pasta física `dataset/Train` não define o split do estudo:
os únicos IDs autorizados nesta etapa são 14, 19, 36 e 52. Os vídeos 24, 38, 47
e 54 permanecem bloqueados para esta seleção.

A leitura deve ser sequencial, em resolução original 640 × 480, sem
redimensionamento. Deve exigir exatamente a quantidade prevista de quadros
por vídeo e fazer uma tentativa adicional de leitura para detectar quadros
extras. Falha de decodificação antes da contagem esperada, dimensões ou tipo
de imagem incompatíveis e quadro extra impedem a conclusão da bateria. Uma
interrupção antecipada não pode ser rotulada como vídeo completo.

Os arquivos `tracked_yolo` devem ser lidos estritamente: seis campos
`track_id class_id cx cy w h`, ID preservado como texto, classe 0/1/2,
coordenadas normalizadas finitas e válidas e dimensões positivas. A cobertura
completa indicada pelo inventário deve ser conferida pelo índice original do
quadro. Arquivo ausente ou linha malformada causa falha; não equivale a GT
vazio. Arquivo existente, validado e sem objetos tem significado distinto.
Entradas e anotações devem ter hashes e contagens registrados, suficientes
para verificar que os dois candidatos usaram o mesmo universo.

O detector recebe somente a imagem e seus parâmetros. O GT é usado para
avaliação, nunca para mascarar regiões, reduzir previsões ou ajustar o
processamento. Fontes e resultados anteriores são imutáveis; as novas saídas
devem usar diretórios exclusivos.

## Métricas e seleção previamente fixadas

O contrato é `center_distance_v3_individuals_ignore_clusters_10px`, com
`class_policy: individuals_ignore_clusters`. O matching principal considera
indivíduos das classes 0/2 a 10 px, com associação um-para-um. Após a associação,
previsões residuais a até esse raio de qualquer indivíduo permanecem FP;
somente as demais podem ser ignoradas por terem centro em uma caixa de
agrupamento da classe 1. Isso preserva os indivíduos anotados dentro de
agrupamentos e a penalização de duplicatas. A
[regra completa de classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md) permanece
inalterada.

Em cada vídeo, somam-se TP, FP e FN de todos os quadros anotados antes de
calcular F1 e revocação. O critério principal é a média aritmética dos quatro
F1 por vídeo, `macro_video_f1_individuals_center_10px`; cada vídeo tem o mesmo
peso. A MAE de contagem usa, em todos os quadros anotados, a diferença entre
previsões avaliadas e GT individual avaliado. Ela não estima o total biológico
de células encobertas pelos agrupamentos.

A ordenação dos dois candidatos segue, nessa ordem:

1. maior F1 macro por vídeo a 10 px;
2. maior revocação macro por vídeo;
3. menor MAE de contagem macro por vídeo;
4. identificador de configuração em ordem crescente.

Os resultados a 15/20 px, recalculados com suas próprias associações e regras
de ignorados, e `secondary_all_objects_*` são descritivos. Não participam da
ordenação. Também não participam tempo, RAM, quantidade de artefatos ou uma
preferência por morfologia. Serão preservadas contagens brutas, avaliadas,
ignoradas e de GT individual/agrupado, para tornar a interpretação auditável.

Não haverá teste de hipótese ou intervalo de confiança nesta etapa, pois os
mesmos quatro vídeos servem à seleção. A regra operacional de ordenação não
equivale a evidência de significância. O
[protocolo estatístico](ESTATISTICA_E_PARETO.md) trata separadamente a análise
final e suas limitações amostrais.

## Ordem, orçamento e falhas

A ordem dos oito pares será embaralhada deterministicamente com seed 42 e
registrada. O OpenCV usará uma thread, e o detector será reiniciado para cada
vídeo. A seed determina a ordem operacional; não cria réplicas independentes.
Não serão gerados MP4 de saída nesta bateria.

| Limite prospectivo | Valor |
|---|---:|
| Tempo de parede da bateria, teto operacional suave | 1.800 s |
| RSS | 2.048 MiB (2 GiB) |
| Artefatos da bateria | 2.048 MiB (2 GiB) |
| Previsões por quadro | 2.000 |

Não é necessário um novo benchmark do detector para esta bateria, menor que
o refinamento já executado. Essa decisão operacional não garante o tempo de
conclusão de vídeos completos; os limites acima continuam aplicáveis e
prospectivos. O teto suave será verificado nos pontos de controle do executor,
sem alegação de interrupção instantânea durante uma chamada em andamento.

Ultrapassar um limite ou falhar em integridade, leitura, contagem, avaliação ou
escrita deve preservar a evidência parcial e impedir a seleção. Não truncar
previsões para caber no limite, não omitir pares que falharam e não ranquear
somente os que terminaram. Uma repetição deve receber outra run, mantendo
registro da falha e da eventual correção ou mudança operacional.

## Evidências exigidas para aceitar a bateria

- Manifesto da bateria e das oito runs, com estado de conclusão, plano e
  configuração resolvidos, hashes das entradas/saídas, referência ao
  refinamento, commit e estado do Git, ambiente, ordem e custo medido.
- Todas as detecções e GT originais por quadro em CSV, preservando IDs,
  classes, multiplicidade e precisão dos valores de ponto flutuante. Nenhum
  arredondamento de apresentação pode alterar uma associação na reanálise.
- Métricas por quadro e resumo por vídeo/candidato, incluindo métricas
  principais, sensibilidades, avaliação secundária, contagens e cobertura.
- Confirmação das 11.700 avaliações esperadas, igualdade do universo entre os
  candidatos, integridade dos hashes e reconciliação dos resumos com os CSVs.
- Resultado de seleção somente após as oito runs completas e verificadas,
  identificado como seleção de validação, sem promoção automática ao teste.

## Conferência independente planejada

Após a conclusão, uma conferência independente usará somente os CSVs e demais
artefatos exportados. Não voltará a abrir pixels ou anotações nas fontes. Ela
reconstruirá contagens e agregações dos **11.700 registros de quadro**, a
ordenação das duas finalistas e a integridade dos hashes das oito runs.

Além da conferência integral dos registros, o matching será refeito com SciPy
em uma amostra fixada antes dos resultados: índices `0`, `floor((N-1)/2)` e
`N-1` de cada vídeo, para os dois candidatos, nos três raios e nas duas
políticas. Isso corresponde a **144 verificações de matching**
(`4 vídeos × 3 quadros × 2 candidatos × 3 raios × 2 políticas`), sobre 12
quadros físicos. Para os vídeos com 1.470 quadros, os índices são 0/734/1469;
para o vídeo com 1.440, são 0/719/1439. A comparação preservará a multiplicidade
das detecções, os IDs/classes e a precisão exportada, incluindo a proteção de
duplicatas e as contagens ignoradas. Essa amostra de matching complementa a
reconstrução integral das agregações; não será descrita como reavaliação de
todas as associações espaciais da bateria.

Depois da conferência, o resultado será registrado na matriz, diário e ficha
do algoritmo. O congelamento e qualquer avaliação posterior exigem seus
próprios critérios e registros. A exposição histórica dos quatro vídeos de
teste continua sendo uma limitação; preservá-los bloqueados agora não a apaga.


## Resultados da validação — 08/09/2026

Protocolo e executor registrados em **`7f47afb`**, antes da abertura das
fontes desta bateria, após **824 testes em 110,00 s**. A run concluiu os
oito pares previstos, com Git limpo e rechecagem de fontes, pais, saídas,
código e ambiente. Foram **11.700 avaliações em 5.850 quadros físicos**,
166,657535 s totais e pico amostrado de RSS de 236,594 MiB. Os artefatos
somavam 63.093.945 bytes antes da escrita do manifesto final, dentro do
orçamento. Tempo e memória não participaram da seleção.

**T218/o0/c2 foi selecionada na validação**, com abertura zero e dois
fechamentos. Os demais parâmetros permaneceram idênticos aos do treino.

| Configuração | F1 macro 10 px | Precisão macro | Revocação macro | MAE de contagem macro |
|---|---:|---:|---:|---:|
| t218_o0_c2 | 0,658959 | 0,590922 | 0,794711 | 4,408433 |
| t219_o0_c2 | 0,657819 | 0,591304 | 0,791474 | 4,435930 |

| Vídeo | Quadros | F1 T218 | F1 T219 |
|---|---:|---:|---:|
| 14 | 1470 | 0,628657 | 0,630831 |
| 19 | 1470 | 0,559725 | 0,557932 |
| 36 | 1470 | 0,794239 | 0,789071 |
| 52 | 1440 | 0,653215 | 0,653441 |

A diferença de F1 macro é **0,0011402996734879**, ou **0,11403 ponto
percentual**, a favor de T218. T218 vence nos vídeos 19/36; T219, em 14/52.
A escolha segue a regra previamente fixada, sem evidência de superioridade
geral ou significância estatística. Os valores da amostra de treino e dos
vídeos completos de validação pertencem a universos distintos; sua diferença
não mede isoladamente melhora ou piora do algoritmo.

As sensibilidades preservaram a mesma ordem: T218 teve F1 macro
0,663448/0,664873 a 15/20 px; T219, 0,662237/0,663842. Cada configuração
usou o mesmo GT exportado: 123.242 objetos, sendo 115.629 indivíduos e
7.613 anotações de agrupamento. São ocorrências ao longo dos quadros, não
células únicas. Foram ignoradas 16.147 previsões de T218 e 15.792 de T219
a 10 px, mantendo todas as previsões e anotações brutas nos CSVs. A métrica
secundária conta cada agrupamento como um objeto, sem inferir quantas células
ele contém. A grande variação entre vídeos merece análise futura, sem
atribuir uma causa visual que esta bateria quantitativa não verificou.

### Conferência e limitações

A conferência independente aprovou **46 arquivos**, **1.772.878 comparações
de campos/valores**, todos os registros e agregados e **144 verificações
SciPy** nos casos previamente definidos. O ranking foi reconstruído e o GT
exportado coincidiu entre candidatos. Essa conferência não reabriu fontes:
hashes dos MP4/anotações e EOF são evidência registrada pelo executor;
o matching independente foi amostral, não integral.

Duas tentativas iniciais do verificador falharam por suposições de formato:
tamanho opcional nas referências e igualdade literal entre inteiros e
decimais das sensibilidades. Corrigiu-se somente o verificador local; as
falhas foram preservadas e a terceira tentativa foi aprovada. Nenhuma run
científica, configuração ou fonte foi alterada ou reexecutada para isso.

Ao concluir a bateria, o resultado era uma **seleção de validação ainda não
congelada**. Posteriormente, o [congelamento para desenvolvimento](CONGELAMENTO_THRESHOLD_V3.md)
fixou T218 sem teste, folds ou nova busca. A [referência individual do treino](TRAJETORIAS_INDIVIDUAIS_V1.md)
foi preparada para as janelas comuns da futura ablação. A hipótese de
predição com fluxo continua pendente.

### Artefatos locais preservados

- [Manifesto da bateria](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/manifest.json),
  [seleção](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/selection.json),
  [ranking](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/ranking.csv) e
  [oito resumos por vídeo](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/video_metrics.csv).
- [Conferência aprovada](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/verification_20260908_retry2.json) e
  [histórico das três tentativas](../../data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/verification_attempts_20260908.json).
- [Figura PNG](../../data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/validacao_threshold_completa.png), [SVG](../../data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/validacao_threshold_completa.svg)
  e [revisão visual](../../data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/visual_review.json).

SHA-256 do manifesto: `ce0a391b792b8a8081f1ea41aaa7678fcae4973c48cc6a5ce159a27147b3cd55`.
SHA-256 da conferência: `9f6b79f5d68b5db59cda035d93036752801b77568d2a24fff8c265865037ffd7`.
