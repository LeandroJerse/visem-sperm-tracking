# Detecção — índice de comparação

[Catálogo](../README.md) · [Código e contratos](../../../src/detection/README.md) · [Parâmetros](../../../configs/detection/) · [Comandos oficiais](../../../script/README.md#1-detecção) · [Ensaios](../../../data/tests/detection/README.md) · [Resultados promovidos](../../../data/results/detection/README.md)

Os três modos de limiarização usam a mesma implementação-base, mas são tratados
como algoritmos experimentais separados porque escolhem o limiar de maneira
diferente. MOG2 e KNN também compartilham uma interface, porém mantêm estado e
hiperparâmetros distintos.

Em 11/09 foi executado e conferido o
[protocolo comparativo estático v1](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md)
com 43 configurações de threshold fixo, Otsu, adaptativo, híbrido,
Blob e Watershed na mesma amostra do treino. Há comparação real entre essas
famílias; a seleção final para a pipeline continua pendente. YOLO e métodos
temporais precisam de seus próprios executores de dados/treinamento.

| Método | Família | Principal vantagem | Principal risco |
|---|---|---|---|
| [Threshold fixo](threshold_fixo.md) | clássico puro | rapidez e interpretação | mudança de iluminação |
| [Otsu](otsu.md) | clássico puro | limiar automático global | superdetecção quando histograma não é bimodal |
| [Threshold adaptativo](threshold_adaptativo.md) | clássico puro | iluminação não uniforme | ruído local e muitos falsos positivos |
| [Threshold híbrido](threshold_hibrido.md) | híbrido clássico | corrige fundo antes de segmentar | mais parâmetros e possível realce de detritos |
| [Blob](blob.md) | clássico puro | filtros geométricos explícitos | sensível a polaridade, escala e sobreposição |
| [MOG2](mog2.md) | clássico temporal | separa movimento de fundo estático | aquecimento, fantasmas e deriva |
| [KNN](knn.md) | clássico temporal | fundo flexível, não paramétrico | custo e forte dependência do histórico |
| [Watershed](watershed.md) | clássico puro | separa regiões encostadas | sementes instáveis e sobre/subsegmentação |
| [YOLO](yolo.md) | aprendido | aparência, classes e confiança | labels/GPU/treino e overfitting |

Nova avaliação: F1 por vídeo, com matching Húngaro de centros a 10 px e
sensibilidades de 15/20 px, conforme a
[decisão sobre tolerância](../../metodologia/TOLERANCIA_ESPACIAL.md).
A versão v3 avalia indivíduos 0/2, ignora previsões residuais em regiões
cluster somente sem indivíduo próximo e mantém avaliação complementar de
todos os objetos. Regra em [Classes e agrupamentos](../../metodologia/CLASSES_E_AGRUPAMENTOS.md).
As métricas já registradas a 15 px permanecem históricas. O custo é medido
junto; nenhuma variante híbrida ganha o nome do baseline que estende.

## Busca comparativa conferida — 11/09/2026

Foram 48 quadros de cada um dos 12 vídeos de treino: **576 imagens físicas**,
43 configurações e **24.768 avaliações configuração–quadro**. O smoke anterior
cobriu 43 × 12 = 516 avaliações e verificou a engenharia, sem selecionar
parâmetros. A busca, em commit `2547109` com Git limpo, foi conferida
independentemente antes da leitura do ranking.

Cada linha abaixo é a melhor configuração **da grade testada** na família.
TP/FP/FN são somados dentro de cada vídeo; F1, precisão e recall são então
agregados com peso igual entre vídeos. O F1 macro não é a média harmônica
da precisão macro com o recall macro, nem a média dos F1 de cada quadro.

| Família | Configurações | Melhor identificador da grade | F1 macro 10 px | Precisão macro | Recall macro | Detecção ms/quadro |
|---|---:|---|---:|---:|---:|---:|
| Blob | 6 | `blob_v1_003` | 0,791005 | 0,760180 | 0,848556 | 1,285 |
| Threshold fixo | 1 referência | `t218_o0_c2_reference_v1` | 0,775634 | 0,728333 | 0,852686 | 1,950 |
| Watershed | 6 | `watershed_v1_005` | 0,609765 | 0,540194 | 0,797990 | 21,674 |
| Otsu | 4 | `otsu_v1_004` | 0,546675 | 0,488463 | 0,699844 | 2,172 |
| Híbrido CLAHE | 8 | `hybrid_threshold_v1_002` | 0,185388 | 0,127623 | 0,450986 | 4,950 |
| Adaptativo | 18 | `adaptive_threshold_v1_002` | 0,148689 | 0,083095 | 0,929020 | 3,512 |

Blob apresenta F1 macro 0,015371 maior que T218, cerca de 1,54 ponto
percentual, mas fica acima dele em apenas 7 dos 12 vídeos. Isso descreve a
amostra usada para escolher configurações; não prova superioridade geral.
Otsu varia de F1 0,062652 no vídeo 23 a 0,933432 no 13. Watershed varia de
0,280374 no 23 a 0,907000 no 13. Essas diferenças reforçam a necessidade
da avaliação por vídeo. O recall alto do adaptativo vem acompanhado de
precisão baixa e não basta para escolher esse detector.

Os parâmetros, sensibilidades de 15/20 px, ignorados e valores por vídeo
estão nas fichas e no
[resumo autenticado](../../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json).
A [figura por família e vídeo](../../../data/derived/detection/comparison_reports/classical_v1_20260911/comparacao_classicos_treino.png)
ajuda a ler a heterogeneidade. Não há p-valor, intervalo de confiança ou
inferência de generalização nesta seleção.

O laço das candidatas durou 749,312176 s; a run registra 752,160737 s após
a autenticação inicial do cache, de 4,833700 s. Pico de RSS amostrado:
823,145 MiB; artefatos das candidatas: 523.379.582 bytes. A coluna de tempo
mede somente o detector sobre imagem em cache, sem decodificação, tracking
ou predição. Não representa FPS da pipeline; o resumo médio também não
substitui mediana/p95 de uma futura medição operacional.

A conferência aprovou 289 arquivos, 30.927.965 comparações, das quais
21.050.826 numéricas, e 148.608 matchings SciPy, em 338,200844 s; diferença
numérica máxima zero. Ela reconstrói as associações e agregações a partir
dos derivados autenticados, sem decodificar fontes ou executar novamente
os detectores. T218 reproduziu o resultado dos mesmos 576 quadros da run
anterior, exceto tempo e identificação. Manifestos e hashes estão no
[registro científico](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).

O primeiro smoke v1 falhou ao exceder 2.000 previsões por quadro. A revisão
operacional v2 preservou dados, grade, avaliação e candidatos e elevou essa
guarda a 307.200, o número de pixels de uma imagem. Não truncou previsões;
RAM e artefatos mantiveram o teto de 2.048 MiB cada. A falha ficou preservada
e a busca acima só começou após novo smoke completo. Esse limite de contagem
é uma guarda de engenharia, não uma hipótese de densidade biológica.

## Próximas etapas

`family_finalists.json` registra dois pais por família pesquisada e T218:
11 configurações, sem promoção. O próximo passo é resolver a vizinhança
prospectiva em YAML/executor de refinamento, incluindo pais e deduplicação;
depois validar as dez finalistas refinadas nos quatro vídeos completos.
A grade é limitada e recebeu esforço desigual entre famílias; T218 já
havia passado por busca extensa e validação própria. Não interpretar a
tabela como o desempenho máximo possível de cada algoritmo.

MOG2/KNN precisam de sequência contínua, reinício e aquecimento. YOLO tem
[ambiente CUDA sinteticamente conferido](../../metodologia/AMBIENTE_APRENDIDO_V1.md),
mas requer dataset derivado autenticado e executor de treinamento estrito
antes dos ensaios no split oficial. O piloto antigo não é promovido.
Depois das comparações pertinentes, o detector alimentará uma comparação
própria de rastreadores: maior F1 não assegura maior HOTA, preservação de
identidade ou menor ADE/FDE. Teste e folds continuam bloqueados nesta etapa.
