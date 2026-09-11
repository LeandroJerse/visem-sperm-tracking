# Refinamento das famílias clássicas — protocolo v1

**Atualização de 11/09/2026:** refinamento concluído e conferido, com 45
configurações e dez finalistas. Resultados e evidências estão ao fim deste
documento. As seções prospectivas abaixo preservam o desenho anterior à
execução; a validação completa das novas finalistas continua pendente.

Registrado em 11/09/2026, antes de executar os novos candidatos. A busca
anterior terminou e foi conferida em `2547109`; seus resultados foram
documentados em `27bec7a`. Este protocolo resolve a vizinhança já proposta
na seção de continuidade de
[Comparação de detectores estáticos v1](COMPARACAO_DETECTORES_CLASSICOS_V1.md).
Não repete a busca encerrada nem altera suas configurações ou runs.

Plano executável:
[`classical_refinement_v1.yaml`](../../configs/detection/comparison/classical_refinement_v1.yaml).

## Pergunta e alcance

O refinamento investiga ajustes locais das duas melhores configurações
de cada família pesquisada: Otsu, adaptativo gaussiano, híbrido CLAHE,
Blob e Watershed. A seleção continua restrita ao treino. O objetivo é
obter duas finalistas por família para uma validação posterior em vídeos
completos, com executor e contrato próprios.

T218/o0/c2 permanece como referência histórica autenticada e **não será
reexecutado ou ajustado** nesta bateria. Seu F1 nos mesmos quadros pode
ser mostrado como referência, com identificação da origem; seu tempo
anterior não é uma nova medição contemporânea de custo.

YOLO, MOG2/KNN, rastreamento e predição permanecem em etapas próprias.
Não há escolha final do detector da cadeia, promoção, teste, folds ou
conclusão sobre a contribuição do fluxo. Um resultado maior no treino
não demonstra superioridade geral, e F1 de detecção não substitui
HOTA, preservação de identidades ou ADE/FDE.

## Dados e parentesco

Os novos candidatos recebem os mesmos 576 quadros do cache já conferido:
48 por vídeo de treino, nos IDs
`11,12,13,15,21,22,23,29,30,35,60,82`. Nenhum quadro novo é escolhido
conforme a qualidade dos métodos. As lacunas do vídeo 23 permanecem
excluídas; ausência de anotação não se torna quadro negativo.

O YAML fixa caminhos e hashes do cache, plano de amostragem, busca
concluída, conferência aprovada e lista de finalistas. Os dez pais vêm
da seleção registrada, sem substituições:

| Família | Pais, na ordem da seleção anterior |
|---|---|
| Otsu | `otsu_v1_004`, `otsu_v1_003` |
| Adaptativo | `adaptive_threshold_v1_002`, `adaptive_threshold_v1_008` |
| Híbrido CLAHE | `hybrid_threshold_v1_002`, `hybrid_threshold_v1_001` |
| Blob | `blob_v1_003`, `blob_v1_002` |
| Watershed | `watershed_v1_005`, `watershed_v1_002` |

Busca SHA256:
`8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0`.
Conferência SHA256:
`c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792`.
Lista de finalistas SHA256:
`1a8bc9ece78fe62d643b974b324d00ff32eccf6628f4ce165e1fede2c4febe74`.

A autenticação liga os pais aos manifestos e artefatos da busca, reconstrói
a ordem de seleção a partir dos resumos já conferidos e verifica a referência
T218. Não é necessário repetir as associações da bateria anterior para
reutilizar um recibo aprovado e todos os seus hashes.

O conjunto de caminhos de código/configuração do commit histórico permite
reconstruir seu hash agregado usando os bytes locais atuais. Esse hash deve
continuar igual ao da execução anterior, enquanto novos arquivos pertencem
à nova versão. Isso impede que uma alteração silenciosa na implementação
dos detectores, no avaliador ou nas configurações históricas seja tratada
como o mesmo experimento. A nova bateria terá seu próprio hash completo.

## Vizinhança fixada e deduplicação

Variar **um parâmetro por vez**, mantendo todos os demais parâmetros do
respectivo pai. Incluir também cada pai, como controle de equivalência.

| Família | Eixos e passos | Limites |
|---|---|---|
| Otsu | Abertura ±1; fechamento ±1 | Abertura 0..2; fechamento 0..3 |
| Adaptativo | Bloco ±8; C ±2; abertura ±1 | Bloco ímpar 3..127; abertura 0..2; C herda o pai e recebe somente ±2 |
| Híbrido | CLAHE ±0,5; fundo ±8; abertura ±1 | CLAHE 0,5..4; fundo ímpar 3..63; abertura 0..2 |
| Blob | Limiar mínimo ±20 | 0..245; limite superior, passo e filtros herdados |
| Watershed | Blur ±2; razão de distância ±0,1 | Blur ímpar 1..7; razão 0,1..0,9 |

Propostas fora desses limites são descartadas, sem projetá-las para a
borda. A aritmética dos passos decimais usa `Decimal` antes da conversão
para os valores efetivamente enviados ao detector. O identificador de
deduplicação considera método e parâmetros completos; configuração
repetida é executada uma vez, preservando todas as origens na linhagem.
As implementações mantêm suas definições próprias de área e região;
limites numéricos iguais não tornam essas geometrias equivalentes.

A resolução dos metadados, sem executar os detectores, resultou em:

| Família | Propostas incluindo pais | Válidas após limites | Configurações únicas |
|---|---:|---:|---:|
| Otsu | 10 | 9 | 8 |
| Adaptativo | 14 | 14 | 13 |
| Híbrido CLAHE | 14 | 13 | 11 |
| Blob | 6 | 6 | 6 |
| Watershed | 10 | 9 | 7 |
| Total | 54 | 51 | **45** |

As três exclusões são fechamento −1, abertura −1 e blur −1, produzidos
por pais na borda inferior. Seis propostas válidas coincidem com outra
proposta e são deduplicadas. Os dez pais estão entre as 45 configurações.
T218 está fora dessa contagem e permanece apenas como referência histórica.

Não se exploram todas as interações entre parâmetros. A grade limitada e
o esforço desigual de busca entre famílias devem acompanhar a interpretação
dos resultados. Os pais repetidos são controles, não réplicas independentes.

## Execução, custos e falhas

Um smoke de todas as 45 configurações em um quadro de cada vídeo precede
o refinamento: **540 avaliações**, modo interno `refinement_smoke`.
Ele utiliza os 12 quadros de benchmark já fixados no cache e não seleciona
parâmetros. Sua conferência independente deve passar antes da ampliação.

O refinamento usa **45 × 576 = 25.920 avaliações**, modo `refinement`.
Exige manifesto e recibo de conferência do smoke compatíveis com os mesmos
dados, parâmetros e versão de código. A ordem dos candidatos é embaralhada
com seed 42, após resolução determinística. OpenCV usa uma thread. Não
serão produzidos vídeos; tempo é medido sem corte temporal nesta nova etapa.

Os tetos prospectivos são 2.048 MiB de RSS amostrado, 2.048 MiB de artefatos
do lote e 307.200 previsões por quadro. O último é uma guarda operacional,
não uma estimativa biológica ou um filtro de detecções. Nenhuma previsão
será truncada para cumprir o limite. Falhas preservam os manifestos e saídas
parciais e impedem classificar um subconjunto incompleto.

Custos de autenticação dos pais/cache, laço, exportação e conferência devem
ficar distinguíveis. A medição de detecção sobre imagens em cache não
representa latência de vídeo ou FPS da pipeline. O RSS amostrado não
certifica ausência de picos entre medições. A bateria científica será
executada sem outro treinamento ou bateria de imagens simultânea para
reduzir interferência na medição de custo.

Código, plano e controles devem ser registrados em commit antes das novas
avaliações, com Git limpo. Cada run conserva configuração resolvida, seed,
versões, hardware, hashes e recursos. Pais, cache e proveniência da nova
execução serão reconferidos antes da classificação. Arquivos históricos
e fontes não são sobrescritos.

## Métricas, seleção e conferência

Preservar o contrato
`center_distance_v3_individuals_ignore_clusters_10px`: indivíduos GT 0/2,
matching Húngaro a 10 px, sensibilidades integrais de 15/20 px, proteção
contra duplicatas próximas e ignorados somente nas regiões de cluster
permitidas. Todas as previsões e GT brutos são exportados; máscaras GT
não entram no detector.

Somar TP/FP/FN dentro de cada vídeo, calcular F1 e depois dar peso igual
aos 12 vídeos. A regra de ordenação é F1 macro decrescente, recall macro
decrescente, MAE de contagem crescente e identificador crescente. Tempo
não decide a ordem. Selecionar duas finalistas em cada uma das cinco
famílias, totalizando dez, somente após completude e conferência. Relatar
precisão, recall, ignorados, variação por vídeo, sensibilidades e custo.

A conferência independente autentica os arquivos, reconstrói a vizinhança,
os universos exatos e as associações com SciPy, e recalcula métricas,
agregações, ranking e finalistas. Para cada um dos dez pais, confronta
centros/GT brutos e métricas com sua execução anterior nos mesmos quadros,
exceto tempo e metadados de identificação da nova run. No smoke são 12
quadros por pai; no refinamento, 576.

O verificador não importa o produtor ou o avaliador científico e não
reexecuta detectores nem decodifica fontes. Pode reutilizar o núcleo de
matemática e leitura do verificador independente anterior. A tolerância
numérica e eventuais limites de empates ótimos devem permanecer explícitos
no recibo; contagens, F1 e distância ótima total não são dispensados.

## Continuidade após esta etapa

Depois de conferir o refinamento, registrar validação estrita das dez
finalistas nos quatro vídeos completos: 5.850 quadros por candidata,
40 runs e 58.500 avaliações. O resultado T218 previamente obtido nesses
vídeos só poderá entrar como referência após autenticação, preservando
seu commit, ambiente e custo históricos.

A validação continua sendo usada para seleção, e não confirmação
independente. A exposição histórica do teste permanece declarada. YOLO e
os métodos temporais ainda precisam de comparações pertinentes antes da
escolha da cadeia. Os rastreadores receberão detecções comuns e terão
métricas próprias; a predição sobre trajetórias estimadas e a ablação
causal com/sem fluxo permanecem necessárias para responder à hipótese.

<!-- refinement-dataset-completion-20260911 -->
## Resultados do refinamento e conferência — 11/09/2026

Refinamento concluído e conferido em `ca68f16`, com Git limpo na execução: **45 configurações × 576 quadros = 25.920 avaliações**, somente nos 12 treinos. A vizinhança previamente definida gerou 54 propostas, 51 válidas e 45 configurações únicas. Os dez pais passaram na paridade de objetos brutos e métricas; T218 permaneceu histórico, sem nova execução. Há dez finalistas, duas por família, sem promoção ou liberação automática da validação.

Bateria: 528,244100 s; RSS amostrado 410,406 MiB; 394.820.008 bytes dos artefatos das candidatas, excluindo o agregador. QA: 1.061 arquivos, 39.670.198 comparações, 26.831.879 numéricas e 155.520 matchings SciPy em 281,243874 s; diferença numérica máxima 0.

[Manifesto do refinamento](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json) · [Resumo e resultados por vídeo](../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

SHA256 do manifesto: `0c686f61f51af3129b89e878ba60ce2067e15c8c3bcceb478eee074f5e407e6b`.
SHA256 do QA: `d82c58bff8d0ba8323ec1d43af23dc18f470c9da8f72c1c86d7aec14769f8118`.
Fontes da execução: `f2ecb55da1bf19ff1fd2247f0e196d30f064fc95fc399c6b465c805c219a8766`.

| Família | Melhor configuração local | F1 macro 10 px | Precisão | Recall | ms/quadro |
|---|---|---:|---:|---:|---:|
| Blob | `blob_refinement_v1_001` | 0,791005 | 0,760180 | 0,848556 | 1,257 |
| Watershed | `watershed_refinement_v1_003` | 0,627005 | 0,567531 | 0,794746 | 21,020 |
| Otsu | `otsu_refinement_v1_003` | 0,626315 | 0,591799 | 0,742933 | 2,208 |
| Adaptativo | `adaptive_threshold_refinement_v1_007` | 0,446885 | 0,338566 | 0,854802 | 3,303 |
| Híbrido CLAHE | `hybrid_threshold_refinement_v1_002` | 0,364491 | 0,273488 | 0,662509 | 4,770 |

Os números apresentados descrevem a melhor configuração da vizinhança por família no treino. Frames e configurações não são réplicas independentes; F1 é calculado dentro de cada vídeo e depois recebe peso igual entre vídeos. Esforço desigual e seleção prévia de T218 impedem interpretar este ranking como superioridade universal ou detector final da pipeline. Tempo com imagem em cache não mede a cadeia completa.

Finalistas para o próximo contrato, preservando todos os parâmetros e a linhagem:

- Otsu: `otsu_refinement_v1_003` e `otsu_refinement_v1_008`.
- Adaptativo: `adaptive_threshold_refinement_v1_007` e `adaptive_threshold_refinement_v1_013`.
- Híbrido CLAHE: `hybrid_threshold_refinement_v1_002` e `hybrid_threshold_refinement_v1_007`.
- Blob: `blob_refinement_v1_001` e `blob_refinement_v1_003`.
- Watershed: `watershed_refinement_v1_003` e `watershed_refinement_v1_005`.

Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold.

O commit documental posterior não altera o commit do código, os hashes ou os recursos das runs. Os registros prospectivos acima permanecem como histórico do plano executado.
