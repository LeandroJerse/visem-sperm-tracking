# Threshold fixo + morfologia

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [Busca v3](../../../configs/detection/threshold/search_v3.yaml) · [Refinamento v3](../../../configs/detection/threshold/refinement_v3.yaml) · [Smoke de engenharia](../../../configs/detection/threshold/protocol_smoke_v3.yaml) · [T200 histórica](../../../configs/detection/threshold/t200_o1_c2.yaml) · [T190 histórica](../../../configs/detection/threshold/t190_o1_c1.yaml) · [T200 congelada histórica](../../../configs/frozen/detection/threshold/t200_o1_c2.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#threshold-etapa-atual) · [Inspeção de um frame](../../../script/detection/test/threshold/README.md) |
| Ensaios e resultados | [Ensaios do método](../../../data/tests/detection/threshold) · [Seleção congelada](../../../data/results/detection/threshold/t200_o1_c2__cfg3276cf65/README.md) |

A classe é compartilhada com os outros modos de threshold; o YAML e o identificador científico mantêm os experimentos separados.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia

Um limiar global definido antes da execução separa primeiro plano e fundo. Uma
abertura remove componentes pequenos, um fechamento reconecta fragmentos e
componentes conexos produzem uma box e um centro por região.

## Parâmetros a estudar

`threshold_value`, polaridade, blur, kernel, iterações de abertura/fechamento
e limites de área. O planejamento anterior usou a faixa 190–205 e preservou
os pilotos `T200/o1/c2` e `T190/o1/c1`. Essas configurações históricas não são
finalistas ou vencedoras automáticas do contrato v3. A busca prospectiva de
08/09 reavaliou esses parâmetros sob a nova regra, como descrito abaixo.

## Pontos fortes

- custo muito baixo, comportamento determinístico e fácil de explicar;
- não requer treino, labels de classe, GPU nem sequência temporal;
- bom baseline para quantificar quanto cada etapa mais complexa realmente ganha.

## Pontos fracos

- um único limiar não acompanha mudanças de contraste ou iluminação;
- morfologia pode unir células próximas ou apagar cabeças pequenas;
- detritos com intensidade e área semelhantes viram falsos positivos;
- cada componente recebe score 1, limitando trackers baseados em confiança.

## Adaptação e validação

Filtragem por área e kernel elíptico são adequações ao tamanho/formato das
cabeças. Validar separadamente por vídeo e inspecionar densidade, detritos e
clusters. O baseline deve continuar puro; CLAHE/top-hat pertencem ao híbrido.

## Decisão atual

A validação completa das duas finalistas terminou em `7f47afb`, após 824
testes: oito runs, 11.700 avaliações, Git limpo, conferência independente
aprovada (46 arquivos, 1.772.878 comparações e 144 matchings).

| Configuração | F1 macro 10 px | Precisão macro | Revocação macro | MAE de contagem macro |
|---|---:|---:|---:|---:|
| t218_o0_c2 | 0,658959 | 0,590922 | 0,794711 | 4,408433 |
| t219_o0_c2 | 0,657819 | 0,591304 | 0,791474 | 4,435930 |

**T218/o0/c2 foi selecionada na validação**, sem congelamento ou teste.
Cada candidata vence em dois vídeos; a diferença macro é 0,11403 ponto
percentual, sem inferência de significância. Tempo total 166,657535 s e
RSS amostrado 236,594 MiB. Os detalhes e limites estão no
[relatório de validação](../../metodologia/VALIDACAO_THRESHOLD_V3.md#resultados-da-validação--08092026).

## Histórico do refinamento no treino

O refinamento registrado da seleção de treino foi **concluído em 08/09/2026**:
117 configurações nos mesmos 48 quadros de cada um dos 12 vídeos de treino,
totalizando 576 quadros por configuração e **67.392 avaliações**. A bateria
usou o commit `da057ef`, com Git limpo, e terminou em 454,647241 s, com pico
amostrado de RSS de 140,77 MiB. Os **502 testes** da suíte passaram antes da
execução. A conferência independente dos resultados foi **aprovada na
primeira execução**: 2.451 arquivos, 4.029.280 comparações de campos/valores,
ranking completo das 117 configurações e os dois finalistas reconstruídos.
Foram conferidos 162 matchings com SciPy em 27 combinações predeterminadas
de configuração/quadro, nos três raios e nas duas políticas. Nos cinco pais,
720 pares configuração/quadro coincidiram com a busca grossa nos mesmos
144 quadros físicos, exceto pelo tempo `detection_ms`.

| Ordem no refinamento | Finalista de treino | F1 macro de treino a 10 px |
|---|---|---:|
| 1 | T219/o0/c2 | 0,775790026345069 |
| 2 | T218/o0/c2 | 0,7756341553985521 |

O F1 é calculado após somar TP/FP/FN dentro dos 48 quadros de cada vídeo,
seguido de média com peso igual entre os 12 vídeos. Os valores selecionam
**dois finalistas de treino**, sem demonstrar superioridade fora dessa amostra.
A diferença de aproximadamente 0,000156 de F1 macro é pequena e descritiva;
não demonstra generalização ou superioridade estatística.
Não houve validação completa, teste ou promoção no contrato v3. A morfologia
foi herdada e a área permaneceu fixa em 3–300 pixels; o refinamento não alterou
o raio principal de 10 px ou as sensibilidades de 15/20 px.

Manifesto e `finalists.json` permanecem em
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/`.

O relatório independente está em
`data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json`.
A figura de seleção no treino está em
`data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.png`,
com versão vetorial `refinamento_threshold_treino.svg` na mesma pasta.
A conferência reconstruiu a aritmética de todos os quadros e as médias por
vídeo; o matching independente foi amostral e usou somente CSVs das runs,
sem reabrir fontes de vídeo, anotações originais ou pixels do cache.

A etapa seguinte foi a **validação registrada das duas finalistas**, concluída acima.
O [protocolo prospectivo](../../metodologia/VALIDACAO_THRESHOLD_V3.md) e o
executor estrito fixam 11.700 avaliações em oito runs completas, critérios
de seleção, orçamento e hashes. O vídeo 52 possui 1.440 quadros; os outros
três, 1.470. As fontes foram abertas somente após registrar plano e executor em `7f47afb`.
Referência: [protocolo mestre](../../metodologia/PROTOCOLO.md).

### Busca grossa preservada — primeira seleção de treino

O [plano prospectivo v3](../../metodologia/BUSCA_THRESHOLD_V3.md) registra
171 combinações para os mesmos 12 quadros de cada vídeo de treino, com
orçamento prévio, benchmark obrigatório e refinamento desenhado. A busca
grossa terminou todas as 24.624 avaliações: T224/o0/c2 liderou a amostra de
treino com F1 macro de 0,7753; T208/o0/c2, T224/o0/c1, T200/o1/c2 e T208/o1/c2
completaram os cinco candidatos para o refinamento posterior. Naquele marco,
os 442 testes de código e a conferência independente da busca grossa passaram.
Essa seleção não promoveu o detector nem alterou os resultados históricos.

### Histórico do contrato e do smoke de engenharia

O avaliador **`center_distance_v3_individuals_ignore_clusters_10px`** está
implementado; a suíte curta passou com 287 testes após a correção da precisão
de exportação e seis regressões adicionais. A repetição dos mesmos seis
quadros em `6b0a1e9`, com Git limpo, confirmou a reconstrução dos CSVs:
36 associações independentes e 168 comparações espaciais a 1e-9 px.
O contrato usa indivíduos das
classes 0/2 como alvos, raio principal 10 px e sensibilidades obrigatórias
15/20 px na resolução original de 640 × 480. A secundária
`binary_all_objects` compara todos os objetos, incluindo agrupamentos.

O matching dos indivíduos tem prioridade. Predições restantes dentro de
caixas de agrupamento só podem ser ignoradas quando estão fora dos discos
de proteção de todos os indivíduos. Duplicatas próximas continuam FP,
inclusive se receberem classe de agrupamento; a classe prevista não filtra
candidatos. A auditoria de treino encontrou 4.250 centros individuais dentro
de regiões de agrupamento, portanto o GT individual nessas regiões permanece.

O **smoke inicial de engenharia está concluído**: frames 0, 1 e 2 de cada vídeo
de treino 11/12, seis frames ao todo. As duas runs usam o commit `42ced6b`,
com `git_dirty: false` e `status: complete`. A 10 px, o vídeo 11 somou
106 TP/29 FP/23 FN e o vídeo 12, 73 TP/9 FP/10 FN. Não houve predições
ignoradas, inclusive nos frames com agrupamento do vídeo 12. Os testes
sintéticos cobrem ignorados, duplicatas protegidas e ramos de quadros vazios.

Saídas locais:
`data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/`.
Os seis frames verificam a execução do contrato; seu F1 não estima a qualidade
geral do threshold e não orienta seleção de parâmetros. Naquele marco ainda
não havia busca na v3. A busca de treino posterior está registrada acima;
a validação e a promoção do método na v3 continuam pendentes. O raio é uma convenção
operacional, não uma estimativa de ótimo ou referência anatômica exata.

A verificação independente confirmou TP/FP/FN nos seis frames, mas encontrou
centros arredondados a duas casas em `detections.csv`, enquanto as métricas
usavam os valores originais. A exportação foi corrigida; as runs iniciais
permanecem imutáveis. O nível 2 foi concluído após repetir os mesmos seis
quadros em duas novas runs de `6b0a1e9`, sem alterar parâmetros ou contagens.
O registro local `verification_20260907_full_precision.json`, no diretório
`smoke/`, contém a conferência independente dos erros espaciais exportados.
Após esse marco, o plano prospectivo foi registrado e a busca grossa foi
executada, seguida pelo refinamento descrito na decisão atual. Raio e política
de classes permaneceram iguais. A preparação da validação completa é o
próximo marco, sem reaproveitar como finalistas os YAMLs históricos a 15 px.

## Decisão histórica preservada — avaliação de 15 px

Nos vídeos completos de validação `14, 19, 36, 52`, T200/o1/c2 obteve o melhor
F1 macro por vídeo (`0,6863`) e menor erro de contagem; T190/o1/c1 preservou
recall maior. A configuração T200 está congelada em
`configs/frozen/detection/threshold/t200_o1_c2.yaml` e sua seleção auditável em
`data/results/detection/threshold/t200_o1_c2__cfg3276cf65/selection/`.

O teste isolado `24, 38, 47, 54` ainda não foi executado. Logo, este resultado
é uma decisão de validação, não a estimativa final fora da amostra.

Essas métricas pertencem à referência `center_distance_v1_15px`. A versão
intermediária `center_distance_v2_10px` também é histórica após a introdução
da política de agrupamentos. Nenhuma dessas evidências promove T200 na v3;
YAMLs congelados, fontes e artefatos anteriores permanecem imutáveis.
