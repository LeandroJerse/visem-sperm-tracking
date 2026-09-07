# Threshold fixo + morfologia

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [threshold.py](../../../src/detection/classical/threshold.py) — `ThresholdContourDetector` |
| Configuração | [Smoke de engenharia v3, sem busca](../../../configs/detection/threshold/protocol_smoke_v3.yaml) · [T200 histórica](../../../configs/detection/threshold/t200_o1_c2.yaml) · [T190 histórica](../../../configs/detection/threshold/t190_o1_c1.yaml) · [T200 congelada histórica](../../../configs/frozen/detection/threshold/t200_o1_c2.yaml) |
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
finalistas ou vencedoras do contrato v3; a nova busca ainda não foi executada.

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

O avaliador **`center_distance_v3_individuals_ignore_clusters_10px`** está
implementado, com testes finais em curso. O contrato usa indivíduos das
classes 0/2 como alvos, raio principal 10 px e sensibilidades obrigatórias
15/20 px na resolução original de 640 × 480. A secundária
`binary_all_objects` compara todos os objetos, incluindo agrupamentos.

O matching dos indivíduos tem prioridade. Predições restantes dentro de
caixas de agrupamento só podem ser ignoradas quando estão fora dos discos
de proteção de todos os indivíduos. Duplicatas próximas continuam FP,
inclusive se receberem classe de agrupamento; a classe prevista não filtra
candidatos. A auditoria de treino encontrou 4.250 centros individuais dentro
de regiões de agrupamento, portanto o GT individual nessas regiões permanece.

O pesquisador autorizou continuidade autônoma. O próximo marco é um **smoke
de engenharia em três quadros dos vídeos de treino 11/12, ainda não executado**.
Ele verificará o contrato, sem selecionar um limiar. Não há resultado de
desempenho, busca, validação ou promoção de threshold no protocolo v3.
O raio é uma convenção operacional, não uma estimativa de ótimo ou uma
referência anatômica exata.

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
