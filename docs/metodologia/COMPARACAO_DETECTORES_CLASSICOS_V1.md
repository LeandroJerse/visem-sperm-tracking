# Comparação de detectores estáticos — protocolo v1

Registrado prospectivamente em 11/09/2026. Esta etapa inicia a comparação
entre famílias antes da escolha do detector da cadeia de rastreamento e
predição. É uma busca no treino, seguida de refinamento e validação sob
contratos próprios. Não declara vencedor final nem abre os quatro testes.

## Pergunta e escopo

Como alternativas clássicas e um híbrido de processamento de imagem se
comparam ao threshold T218 na detecção de indivíduos do VISEM-Tracking?
Otsu, threshold adaptativo, realce local seguido de threshold, Blob e
Watershed são avaliados usando exatamente os mesmos quadros e anotações.
T218/o0/c2 entra como referência fixa de desenvolvimento, já ajustada em
uma busca anterior. Não é um método sem ajuste.

YOLO terá treinamento e seleção próprios antes de uma comparação final
com os clássicos. MOG2 e KNN precisam de processamento temporal contínuo,
reinício por vídeo e aquecimento: não são executados em imagens espaçadas
como se fossem detectores sem estado. Esta bateria não cobre esses métodos
temporais, rastreamento ou predição. A ordem de execução não os exclui do
plano do TCC.

## Dados e integridade

Somente treino: `11,12,13,15,21,22,23,29,30,35,60,82`.
Reutilizar as imagens BGR sem perda já extraídas e auditadas, 48 por vídeo,
640 × 480, total 576. O smoke utiliza o quadro de benchmark de cada vídeo,
12 ao todo. Nenhuma nova amostragem depende dos resultados dos métodos.
Lacunas de anotação do vídeo 23 não entram como quadros negativos.

Cache:
`data/derived/detection/frame_samples/threshold_search_v3_20260908/manifest.json`.

- SHA256 do manifesto: `4f2712a43b1da795aaee2d5d73750fa29d5c47231d34cf72d8f6cb2bc7c01501`.
- Identidade da amostra: `77ad9cbda76c03d61f3b28dd99520d0c1d6e285452929d847742bc6331473478`.
- Hash canônico do plano original: `b787deb8d49c6adf7902c9370bf567631545fac5e749beef943d54083be7d35d`.

O leitor deve autenticar cache, origem e plano antes do processamento.
Preservar `configs/detection/threshold/search_v3.yaml` e as runs anteriores.
Ler hashes de MP4 não equivale a decodificar seus pixels. Não fornecer GT,
classes, IDs ou máscaras ao detector; as anotações entram apenas no avaliador.

## Grade registrada antes dos resultados

| Família | Parâmetros variáveis | Quantidade |
|---|---|---:|
| Threshold fixo | T218/o0/c2, referência sem busca | 1 |
| Otsu | abertura 0/1; fechamento 0/2 | 4 |
| Adaptativo gaussiano | bloco 15/31/61; C −5/0/5; abertura 0/1; fechamento 1 | 18 |
| Híbrido com CLAHE e realce | clip 1/2; kernel de fundo 15/31; abertura 0/1; fechamento 1; Otsu | 8 |
| Blob | claro/escuro; início da varredura 10/100/180; máximo 255; passo 10 | 6 |
| Watershed | blur 1/3; razão de distância 0,2/0,4/0,6 | 6 |
| **Total** | | **43** |

Área 3–300 pixels e kernel morfológico 3 quando aplicáveis. Os detalhes
resolvidos, inclusive padrões fixos de cada implementação, pertencem ao YAML
`configs/detection/comparison/classical_v1.yaml` e ao manifesto da run.
O YAML e código devem estar em commit limpo antes de abrir os pixels.

O mesmo intervalo numérico de área não torna a geometria interna idêntica:
componentes conectados e regiões Watershed contam pixels; SimpleBlobDetector
usa sua medida geométrica de contorno e gera centros/tamanhos de keypoints.
Registrar a versão OpenCV, que também determina padrões internos como a
repetibilidade mínima do Blob. Este protocolo compara as implementações
declaradas, sem presumir caixas e filtros geometricamente equivalentes.

A grade cobre alternativas com regras distintas, mas é limitada e tem
esforço desigual entre famílias. Um ranking nessa grade não demonstra o
máximo possível de cada algoritmo. Novos valores decorrentes dos resultados
serão identificados como refinamento, em contrato novo, antes da execução.

## Avaliação e ordem de seleção

Contrato `center_distance_v3_individuals_ignore_clusters_10px`:
matching Húngaro um a um dos centros individuais, classes 0/2, até 10 px.
Avaliar também sensibilidades 15 e 20 px. Previsões residuais próximas a
qualquer indivíduo continuam sendo FP; das demais, ignorar apenas centros
no interior de caixas GT de clusters. Manter indivíduos que estejam dentro
de clusters e exportar todas as previsões e anotações brutas. Aplicar também
a avaliação secundária de todos os objetos. As regras completas estão em
[Classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md).

Somar TP/FP/FN nos quadros de cada vídeo e calcular suas métricas; a medida
principal é a média de F1 entre os 12 vídeos, com peso igual. Não tratar 576
quadros como 576 réplicas independentes. Desempate: recall macro maior,
MAE de contagem menor, identificador de configuração em ordem crescente.
Tempo não desempata qualidade; será relatado separadamente.

A busca guarda **duas finalistas por família**, quando disponíveis, e a
referência T218. Esse resultado é uma shortlist de treino, não congelamento,
seleção final ou autorização para teste. `validation_released=false` nesta
etapa. O refinamento e a validação completa exigem planos subsequentes
registrados; os quatro vídeos de teste permanecem bloqueados.

## Execução, recursos e falhas

1. Testes sintéticos dos novos contratos e integrações, sem dados de avaliação.
2. Smoke: 43 × 12 = **516 avaliações**, sem ranking ou seleção.
3. Conferência da completude, exportação, proveniência e métricas do smoke.
4. Busca: 43 × 576 = **24.768 avaliações**, somente após smoke compatível.
5. Conferência independente dos artefatos, agregações e ranking completos.

Uma avaliação corresponde a uma configuração em um quadro. Configurações
não são réplicas experimentais. Ordem pseudoaleatória fixa com seed 42;
OpenCV usa o número de threads registrado. Medir detecção, avaliação,
exportação, tempo total, pico de RSS amostrado e bytes de saída. O custo de
detecção com cache em RAM não mede a velocidade da pipeline com decodificação.

Sem teto de tempo nesta nova bateria. Limites operacionais prospectivos:
RSS amostrado 2.048 MiB, artefatos 2.048 MiB e 2.000 previsões por quadro.
Exceder limite ou ocorrer falha interrompe a execução, preservando recibo
de falha e artefatos já escritos. Não truncar previsões, eliminar candidatos
problemáticos ou ranquear uma bateria incompleta. A amostragem de RSS não
garante que nenhum pico instantâneo tenha ocorrido entre medições.

Cada run registra configuração resolvida, commit, Git limpo, hashes, versões,
hardware, seed, recursos e arquivos. Saídas exclusivas não sobrescrevem
execuções. Registrar CSVs brutos, métricas por quadro e vídeo, resumos por
configuração e manifesto de bateria. Verificar proveniência novamente antes
de classificar resultados.

## Conferência e interpretação

A conferência deve recomputar associações com SciPy a partir dos centros
exportados, ignorados, contagens, agregações por vídeo e ranking. Comparar
GT com o cache autenticado. Verificar todos os arquivos por hash e os
universos exatos de quadros/configurações. Conferir a referência T218 contra
os resultados anteriores nos mesmos 576 quadros, excluindo tempo e metadados
da nova execução. A conferência de derivados não prova que a imagem original
foi decodificada corretamente nem reexecuta os detectores.

Relatar qualidade por vídeo, sensibilidades, falsos positivos, falsos
negativos, contagens ignoradas e custo. Não declarar significância,
generalização, superioridade universal ou melhoria de tracking a partir
desta busca. O detector escolhido para a cadeia será decidido após a
comparação e validação pertinentes; maior F1 de detecção não assegura maior
HOTA ou menor ADE/FDE. A cadeia final também deve ser avaliada como sistema.

## Continuidade definida antes desta busca

Após conferir esta bateria, registrar YAML/executor próprios de refinamento
local nos mesmos 576 quadros. Aplicar a cada uma das duas finalistas das
cinco famílias pesquisadas a vizinhança abaixo, variando **um parâmetro por
vez**, incluindo o pai e deduplicando configurações. T218 não ganha nova busca.

| Família | Vizinhança local proposta para o próximo contrato |
|---|---|
| Otsu | Abertura ±1 em 0..2; fechamento ±1 em 0..3 |
| Adaptativo | Bloco ±8 em 3..127, ímpar; C ±2; abertura ±1 em 0..2 |
| Híbrido | CLAHE ±0,5 em 0,5..4; fundo ±8 em 3..63, ímpar; abertura ±1 em 0..2 |
| Blob | Limiar mínimo ±20 em 0..245; demais parâmetros herdados |
| Watershed | Blur ±2 em 1..7, ímpar; razão de distância ±0,1 em 0,1..0,9 |

São no máximo 54 configurações antes de deduplicar, com parâmetros dos pais
preservados e linhagem explícita. Os controles repetidos não constituem
réplicas independentes. Essa proposta foi fixada antes de observar a busca
atual; o próximo contrato deverá resolver limites e deduplicação, fixar todos
os parâmetros e hashes e manter a interpretação de busca limitada.

Depois, as dez finalistas refinadas podem seguir para os quatro vídeos
completos de validação: 5.850 quadros por candidata, 40 runs e 58.500
avaliações novas. Reutilizar T218 como referência histórica somente após
conferir entradas, implementação, parâmetros, manifestos e QA. Preservar seu
commit/ambiente/tempo originais; não atribuir essas runs à bateria nova nem
usar tempos históricos como medição contemporânea. A nova CLI de busca
não autoriza essa validação por si só.

Esse roteiro não resolve treinamento YOLO ou os detectores temporais; a
escolha do detector da cadeia final permanece posterior às comparações e
validações pertinentes.

## Revisão operacional v2 — após o primeiro smoke

O smoke registrado em `574038b` foi interrompido após 36 candidatas completas.
A candidata 37, `adaptive_threshold_v1_004` (bloco 15, C=0, abertura 1,
fechamento 1), excedeu 2.000 previsões no vídeo 30, quadro 781. Não houve
truncamento, ranking ou descarte de candidatas. O manifesto de falha e os
arquivos parciais permanecem preservados:

`data/tests/detection/classical_comparison/classical_detection_comparison_v1_20260911_batch__cfgcbbae012/smoke/20260911T143918692719Z__574038b__cfgbff0b8bab575__src8b42901b3a__s42/manifest.json`.

SHA256 `a11c69b9c4b8165835f8db3333cd541b9a4a1d660f2b9fa69ef26290394e1711`.
Tempo até a falha: 15,643522 s, sem incluir a autenticação inicial do cache.
O erro original não guardou a contagem exata acima de 2.000; não inferi-la
das saídas parciais, que não incluem a avaliação do quadro interrompido.

Superdetecção é um comportamento a medir, inclusive pelos falsos positivos;
o teto de 2.000 impedia avaliá-lo. A configuração nova
`configs/detection/comparison/classical_v1_operational_v2.yaml` eleva apenas
o limite operacional de previsões a **307.200**, o número de pixels de uma
imagem 640×480. É um limite conservador de engenharia para estes detectores,
não um número biologicamente plausível de células nem um filtro de qualidade.
Os limites de RSS e artefatos permanecem 2.048 MiB; não há corte temporal.

O YAML v1 permanece intacto e é vinculado pelo hash canônico
`6dd487d03f4de19ee27983fc9c4308d7a6c5bfcd0f444bfc8c21290a9f85d43b`.
A revisão deve comprovar igualdade de dados, grade, sementes, ordem,
avaliação e seleção. Alteram-se somente identidade/linhagem operacional e o
teto de contagem. Registrar código e revisão em novo commit limpo e executar
um novo smoke completo antes da busca. O primeiro smoke é falha de engenharia
preservada; não é comparação científica concluída nem seleção de parâmetros.

## Resultados da busca e conferência — 11/09/2026

A revisão operacional v2 concluiu o smoke e a busca com Git limpo em
`2547109`. O smoke cobriu 43 configurações × 12 quadros = 516
avaliações; não selecionou candidatas. A busca cobriu as mesmas 43
configurações × 576 quadros = **24.768 avaliações**, nos 12 vídeos de treino.
Foram mantidos todos os candidatos e todas as previsões, inclusive
superdetecções. A falha operacional v1 permanece preservada acima.

| Família | Configuração da grade | F1 macro a 10 px | Precisão macro | Recall macro | ms/quadro |
|---|---|---:|---:|---:|---:|
| Blob | `blob_v1_003` | 0,791005 | 0,760180 | 0,848556 | 1,285 |
| Threshold T218 | `t218_o0_c2_reference_v1` | 0,775634 | 0,728333 | 0,852686 | 1,950 |
| Watershed | `watershed_v1_005` | 0,609765 | 0,540194 | 0,797990 | 21,674 |
| Otsu | `otsu_v1_004` | 0,546675 | 0,488463 | 0,699844 | 2,172 |
| Híbrido CLAHE | `hybrid_threshold_v1_002` | 0,185388 | 0,127623 | 0,450986 | 4,950 |
| Adaptativo | `adaptive_threshold_v1_002` | 0,148689 | 0,083095 | 0,929020 | 3,512 |

Cada linha mostra a melhor configuração **desta grade** dentro da família.
A métrica agrega TP/FP/FN dentro do vídeo e depois dá peso igual aos 12
vídeos. Não é uma média de F1 por quadro. A grade tem esforço desigual entre
famílias e T218 foi ajustado anteriormente; não descreve os máximos possíveis
de cada algoritmo. Precisão e recall também são médias por vídeo: seu F1
harmônico não precisa coincidir com o F1 macro da tabela.

As 11 candidatas registradas em `family_finalists.json` são as duas primeiras
de cada uma das cinco famílias pesquisadas e a referência T218. São pais
para a próxima etapa, não configurações promovidas. Ainda não houve
refinamento dessas novas famílias, validação comparativa completa, teste,
confirmação por folds ou escolha da pipeline. MOG2/KNN e YOLO não participaram
desta bateria; necessitam protocolo temporal e treinamento próprios.

A busca durou 752,160737 s após a autenticação inicial do
cache (4,833700 s). O laço de
candidatas durou 749,312176 s. RSS máximo
amostrado 823,145 MiB, em
24.857 medições;
523.379.582 bytes de artefatos das
candidatas. Esse número não inclui os arquivos do agregador. Os limites de
2.048 MiB de RSS e artefatos foram respeitados. O custo por quadro da tabela
mede o detector sobre imagem em cache; não é FPS da pipeline completa.

A conferência independente da busca passou na primeira tentativa:
289 arquivos, 30.927.965 comparações,
21.050.826 numéricas e
148.608 matchings SciPy, em 338,200844 s.
Maior diferença numérica: 0.0.
T218 reproduziu os centros/GT e métricas dos mesmos 576 quadros da run de
refinamento anterior, exceto tempo e identificação da nova execução.
O QA não refaz inferência ou decodificação; verifica os derivados autenticados
e reconstrói as associações, agregações, ranking e candidatas seguintes.
As limitações e eventuais empates ótimos estão descritos no recibo completo.

O QA do smoke também passou: 286 arquivos,
838.040 comparações,
3.096 matchings, paridade T218 nos 12 quadros.
O smoke e a busca são execuções diferentes e conservam seus próprios recibos.

Busca: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/20260911T144742812472Z__2547109__cfgbecfe1d189e7__srcf14ede5a12__s42/manifest.json`.
SHA256 do manifesto: `8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0`.
QA: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/verification_20260911.json`.
SHA256 do QA: `c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792`.
Fontes da execução: `f14ede5a1240d6e6588f5859a02e408ec99601aa019513af7a6f4478ac86d64c`.

Smoke v2: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgd3cb65ba/smoke/20260911T144621160257Z__2547109__cfg69087a632a64__srcf14ede5a12__s42/manifest.json`.
Manifesto SHA256 `2cad2719b618e14fe07a3f45bba658499fa557c798d0fc59f60610b3b1406b54`.
QA: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgd3cb65ba/smoke/verification_20260911.json`.
QA SHA256 `05095ce3c4659b29935df343f1d2b990a4a7f5b38bbc406e232e76e7adb9a1d8`.

A tabela e a figura descritiva derivada estão em
`data/derived/detection/comparison_reports/classical_v1_20260911/`, com
manifesto de origem, QA e hashes em `summary.json`. Os CSVs completos e as
sensibilidades de 15/20 px permanecem nas runs.

Próximo marco: resolver as vizinhanças prospectivas desta seção anterior em
novo YAML e executor de refinamento, incluindo pais/deduplicação, e conferir
os resultados. Depois, validar as finalistas nos quatro vídeos completos.
YOLO deve completar a comparação antes da escolha do detector da cadeia.
Tracking terá comparação própria: F1 de detecção não substitui HOTA,
identidade ou cobertura; predição deve medir ADE/FDE sobre trajetórias
estimadas, além dos controles GT já existentes.
