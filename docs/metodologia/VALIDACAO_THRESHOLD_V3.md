# Validação completa das finalistas do threshold v3

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
