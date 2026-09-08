# Referência de trajetórias individuais — protocolo v1

## Estado e objetivo deste marco

Protocolo prospectivo de 08/09/2026, registrado antes da preparação descrita
aqui. Este documento define uma referência derivada do GT e índices de janelas
para desenvolvimento. As regras prospectivas permanecem abaixo, e os
[resultados posteriores](#resultados-da-preparação--08092026) estão ao final.
Esta preparação não demonstra a hipótese sobre a contribuição do fluxo óptico.

O objetivo é preservar as observações individuais válidas dos **12 vídeos de
treino**, identificar seus trechos consecutivos e registrar quais origens
possuem histórico de 20 quadros e futuro completo de 10 quadros. Nenhum
detector, rastreador, estimador de fluxo ou preditor será executado neste marco.
Não serão selecionados hiperparâmetros nem descartadas trajetórias por
geometria, velocidade, aparência ou desempenho.

Os pontos de entrada implementados são:

| Responsabilidade | Caminho |
|---|---|
| Configuração prospectiva | `configs/protocol/individual_trajectories_v1.yaml` |
| Preparação da referência | `src/prediction/ground_truth.py` |
| Executor | `script/prediction/test/prepare_ground_truth.py` |
| Saídas novas e imutáveis | `data/derived/prediction/ground_truth_individuals/` |

A configuração resolvida e os controles pertinentes deverão ser testados e
registrados antes da execução. Este documento complementa a
[revisão geral](../projeto/REVISAO_GERAL_20260908.md), a
[política de classes](CLASSES_E_AGRUPAMENTOS.md) e o
[protocolo experimental](PROTOCOLO.md).

## Universo autorizado e integridade das entradas

Os únicos IDs admitidos são:

`11, 12, 13, 15, 21, 22, 23, 29, 30, 35, 60, 82`.

Antes de abrir anotações, o executor deverá conferir essa lista exata contra
a configuração e o split vigente. Não basta aceitar uma pasta física chamada
`Train`: a divisão científica é determinada pelos IDs do protocolo. Fontes
dos vídeos de validação 14/19/36/52 e de teste 24/38/47/54 não serão lidas
nesta preparação.

As anotações serão alinhadas pelo índice original no nome do arquivo, sem
comprimir a linha do tempo ou renumerar quadros para remover lacunas. O
inventário versionado deverá fornecer o intervalo esperado de cada vídeo;
duração nominal não substitui a contagem de quadros.

Cada arquivo existente deverá ser lido estritamente no formato
`track_id class_id cx cy w h`: seis campos, identidade preservada como texto,
classe 0/1/2, coordenadas normalizadas finitas e válidas e dimensões positivas.
Duplicidade conflitante de identidade no mesmo quadro não será resolvida
silenciosamente. Identidades e índices ambíguos, linhas malformadas ou hashes
incompatíveis impedem uma preparação aceita.

Arquivo de anotação ausente significa estado não anotado; arquivo existente,
validado e vazio significa quadro anotado sem objetos. Ambos devem permanecer
distintos no inventário derivado. As lacunas do vídeo 23 interrompem a
continuidade disponível; não se convertem em negativos ou posições
interpoladas. Fontes permanecerão intactas, e a run registrará hashes e
contagens suficientes para identificar exatamente as entradas utilizadas.

## Observações individuais e identidades

A referência individual reúne as classes **0 e 2**. A classe original continua
registrada, embora a mudança 0↔2 não interrompa por si só um indivíduo que
mantenha o mesmo ID em quadros consecutivos. A classe 1 representa agrupamento
e não fornece uma posição individual para este produto, conforme a
[distinção já documentada](CLASSES_E_AGRUPAMENTOS.md#o-que-se-pretende-medir).

Toda observação individual válida será preservada, mesmo que pertença a um
trecho curto demais para formar uma janela. Serão mantidos vídeo, quadro, ID
original textual, classe, caixa e centro em precisão de ponto flutuante, sem
arredondamento de apresentação. As anotações brutas, inclusive agrupamentos,
continuam preservadas nas fontes; os agrupamentos serão contabilizados e
identificados como informação de interrupção, não convertidos em indivíduos.

Um indivíduo 0/2 explicitamente anotado dentro de uma caixa cluster permanece
válido. Não haverá exclusão por interseção de caixas, centro dentro de região
agrupada, tamanho, posição na imagem, velocidade ou salto espacial. A presença
de um agrupamento em um quadro não interrompe outros indivíduos desse quadro.

O ID original não será renumerado para sugerir uma nova identidade biológica.
Um identificador técnico de segmento poderá acompanhar o ID original, com
mapeamento explícito entre ambos. Esse identificador descreve continuidade de
observações, não uma conclusão sobre nascimento de outra célula ou associação
de membros de um agrupamento.

## Formação dos segmentos

Para cada par `(video_id, original_id)`, ordenar as observações pelos índices
originais dos quadros. Um segmento é uma sequência máxima de observações
individuais 0/2 em quadros consecutivos. O segmento termina quando:

- o mesmo ID possui registro de classe 1, deixando de fornecer referência
  individual naquele quadro;
- o ID individual está ausente de um quadro anotado;
- falta o arquivo de anotação de um quadro;
- termina o intervalo disponível do vídeo.

O reaparecimento posterior do mesmo ID inicia outro segmento técnico, mantendo
o ID original. Não unir segmentos por interpolação, proximidade de centros,
semelhança de caixas ou previsão de movimento. Um intervalo pode conter mais
de uma causa de interrupção; seus estados observados devem ser rastreáveis,
sem inventar uma explicação biológica para a ausência.

Serão preservados **todos os segmentos**, inclusive os de uma única
observação. O índice de segmentos deverá permitir conferir início, fim,
comprimento e correspondência com as observações originais. A soma dos
comprimentos dos segmentos deve igualar a quantidade de observações
individuais preservadas em cada vídeo.

Essa segmentação define o universo de janelas. **Ela não define uma política
de HOTA**, não muda automaticamente os IDs da avaliação MOT e não autoriza
reiniciar rastreadores em função do GT. O tratamento de identidade através de
oclusões e agrupamentos e sua representação no TrackEval exigem um contrato
separado, conforme [métricas de tracking](METRICAS_TRACKING.md). Renumerar
somente o GT e manter IDs previstos contínuos pode introduzir penalizações
artificiais de associação; isso não será resolvido implicitamente aqui.

## Índices de janelas e contagem das exclusões

Cada observação individual é uma origem candidata `t`. A janela aceita terá:

- histórico: **20 posições**, nos quadros `t−19, ..., t`;
- futuro: **10 posições**, nos quadros `t+1, ..., t+10`;
- passo entre origens (`stride`): **1 quadro**;
- um único vídeo, split, ID original e segmento consecutivo.

Portanto, uma janela exige 30 observações consecutivas do mesmo segmento.
Um segmento de comprimento `L` tem as seguintes contagens, definidas antes
dos resultados:

| Quantidade | Fórmula |
|---|---|
| Origens candidatas | `L` |
| Origens sem histórico completo | `min(L, 19)` |
| Origens com histórico completo | `max(L−19, 0)` |
| Janelas aceitas, com histórico e futuro completos | `max(L−29, 0)` |
| Origens com histórico completo excluídas por futuro incompleto | `max(L−19, 0) − max(L−29, 0)` |

As categorias de exclusão são mutuamente exclusivas: primeiro verificar o
histórico; somente entre origens com histórico completo verificar o futuro.
Assim, por segmento e por vídeo:

`origens candidatas = histórico incompleto + futuro incompleto + janelas aceitas`.

Por exemplo, um segmento com 19 observações não tem histórico completo; um
com 20 tem uma origem com histórico, mas sem os dez passos futuros; um com 30
tem uma janela aceita. Esses exemplos são consequências do protocolo, não
resultados dos vídeos.

O índice de janelas deve registrar a origem e os limites de histórico/futuro,
permitindo reconstruir suas posições a partir das observações preservadas.
As contagens de origens excluídas por futuro incompleto serão apresentadas por
vídeo, juntamente com segmentos e observações sem janela. Não serão apagados
os trechos excluídos nem alterado o comprimento mínimo para obter mais casos.

A existência de GT futuro será usada exclusivamente para identificar o alvo
e declarar a elegibilidade retrospectiva da janela. Não poderá ser apresentada
como informação disponível ao preditor no instante `t`. Uma avaliação posterior
nesse universo será condicionada à existência de referência individual pelos
dez passos futuros; a cobertura e as exclusões tornam essa condição explícita.

## O que permanece para a etapa de predição

Os índices preparados serão comuns aos futuros braços da ablação. Esta etapa
não cria atributos de fluxo, não ajusta preditores e não calcula resultados de
ADE/FDE. Também não elimina janelas por erro, dificuldade ou desempenho de um
método futuro.

Na implementação científica seguinte, os horizontes 1/5/10 serão pontos de
apresentação, mas `ADE_H` deverá usar o erro euclidiano de **todos os passos
1..H**, e `FDE_H` somente o passo H. A média dos erros nos três pontos
1/5/10 não será denominada ADE de 1 a 10. Essa integração entre produção de
previsões e avaliação ainda deverá ser materializada e testada.

Quando forem adicionadas características de fluxo, a validade das entradas e
o pareamento entre métodos exigirão seu próprio registro. Imagens, máscaras e
pares de fluxo usados como entrada deverão terminar em instante menor ou
igual a `t`. O índice atual de janelas não certifica por si só esse controle
de causalidade nem a disponibilidade futura de fluxo válido.

A unidade estatística continua sendo o **vídeo**. Observações, origens,
janelas sobrepostas, segmentos, trajetórias e clipes derivados não serão
tratados como novas aquisições independentes. Pesos e agregações da futura
comparação serão registrados antes de observar desempenho, conforme a
[política estatística](ESTATISTICA_E_PARETO.md).

## Evidências e aceitação da preparação

A saída será criada em um diretório exclusivo sob a área de derivados,
contendo observações individuais, índice de segmentos, índice de janelas,
contagens de cobertura/exclusões e manifesto. Nenhuma execução sobrescreverá
outra. O manifesto deverá registrar configuração resolvida, versão do contrato,
commit e estado do Git, hashes das entradas e saídas, ambiente, custo e estado
de conclusão. Falhas e artefatos parciais não equivalem a preparação aceita.

Antes de aceitar a run, conferir:

1. somente os 12 IDs de treino previstos e nenhum acesso às fontes de
   validação/teste;
2. identidade textual, classe e precisão das observações individuais
   preservadas, inclusive as que não originam janela;
3. segmentação exclusivamente temporal e por estado de anotação/classe,
   preservando indivíduos dentro de agrupamentos;
4. ausência de lacunas, mudança de vídeo/split/ID ou classe 1 dentro das
   janelas aceitas;
5. reconciliação das contagens pelas fórmulas acima, por segmento e por vídeo;
6. integridade dos hashes e correspondência entre observações, segmentos,
   janelas, resumos e manifesto.

Uma conferência independente dos artefatos será realizada após a preparação.
Seu alcance deverá distinguir reconstrução dos arquivos derivados de uma
eventual releitura das fontes; não afirmar verificações que não tenham sido
executadas.

O congelamento da baseline T218 é um registro separado. Esta preparação não
abre o teste, não executa folds e não transforma a configuração de detecção
em uma pipeline temporal validada. As guardas dessas etapas permanecem
aplicáveis, e a exposição histórica do teste continua declarada. A hipótese
central do TCC ainda não foi testada por este marco.

## Resultados da preparação — 08/09/2026

Preparação **concluída e conferida**, sem ajuste ou avaliação de modelo. O
protocolo e o código foram registrados em `33d191d` antes do acesso às fontes,
após **1.026 testes em 108,58 s**. A run manteve Git limpo e terminou em
151,929874 s, com pico amostrado de RSS de 226,148 MiB. O orçamento foi cumprido;
146.913.962 bytes foram contabilizados antes da gravação do manifesto final.
RAM foi amostrada em 14 pontos, portanto não é um máximo contínuo garantido.

O universo contém **17.640 quadros**, dos quais **17.466 anotados** e **174 sem
anotação**, exclusivamente nas duas lacunas já registradas do vídeo 23.
Foram preservadas as 368.487 observações brutas: **363.074 individuais**
(347.847 de classe 0 e 15.227 de classe 2) e **5.413 de agrupamentos**.
Os agrupamentos permanecem no CSV bruto e nas contagens; não viram posições
individuais ou máscaras para modelos.

| Vídeo | Observações individuais | Segmentos | Janelas 20+10 | Origens sem futuro completo após histórico válido |
|---|---:|---:|---:|---:|
| 11 | 53.854 | 60 | 52.223 | 546 |
| 12 | 37.887 | 154 | 34.093 | 1.188 |
| 13 | 62.646 | 81 | 60.406 | 760 |
| 15 | 24.437 | 41 | 23.315 | 376 |
| 21 | 32.510 | 80 | 30.574 | 626 |
| 22 | 15.983 | 38 | 14.944 | 350 |
| 23 | 3.227 | 11 | 2.922 | 100 |
| 29 | 4.348 | 10 | 4.058 | 100 |
| 30 | 16.034 | 54 | 14.582 | 470 |
| 35 | 45.752 | 63 | 43.998 | 600 |
| 60 | 20.401 | 57 | 18.802 | 538 |
| 82 | 45.995 | 76 | 43.859 | 730 |
| **Total descritivo** | **363.074** | **725** | **343.776** | **6.384** |

Há 669 pares distintos `(vídeo, ID individual original)` e 725 segmentos
contínuos. Esses números descrevem IDs observados, não demonstram identidade
biológica perfeita. **623 segmentos têm janela; 102 não têm**, e todos foram
guardados. Os 102 sem janela contêm **1.231 observações**: 77 segmentos têm
menos de 20 observações e 25 têm entre 20 e 29. Nenhum foi apagado para melhorar
a cobertura ou o desempenho de um algoritmo.

A contabilidade de origens fecha exatamente:

`363.074 = 12.914 sem histórico + 6.384 sem futuro + 343.776 janelas aceitas`.

Entre as 350.160 origens com histórico completo, 6.384 não têm dez posições
futuras: 2.244 por fim do vídeo, 20 por ausência de anotação e 4.120 por
ausência do ID. Os segmentos terminaram 229 vezes na borda do vídeo, duas em
lacunas de anotação e 494 por ausência do ID. **Não houve fronteira de classe
1 do mesmo ID nesta referência de treino**; esse ramo foi verificado por
testes sintéticos. Isso não demonstra ausência de oclusões ou agrupamentos
e não permite inferir a causa biológica de `id_absent`.

### Conferência e limites

A conferência independente passou **na primeira execução**, verificando
**86 arquivos** (85 artefatos e o manifesto) e **9.407.090 comparações de
campos/valores**, em 26,3672 s. Uma implementação por agrupamento offline de
índices consecutivos de cada ID reconstruiu todos os segmentos e janelas a
partir de `ground_truth_raw.csv` e `frame_status.csv`. Observações, classes,
coordenadas em ponto flutuante, IDs, razões e resumos coincidiram integralmente.

O executor leu anotações, hashes e metadados dos MP4 apenas do treino e
reconferiu fontes, inventários, artefatos e proveniência antes de completar.
Não decodificou pixels, não executou detector/tracker e não abriu as fontes de
validação/teste. A conferência independente leu somente os derivados; não
constitui uma segunda releitura das fontes nem uma certificação de identidade
biológica. Janelas continuam dependentes dentro do vídeo e condicionadas à
disponibilidade de referência individual futura. Nenhum ADE/FDE, HOTA ou ganho
de fluxo foi medido neste marco.

### Onde navegar

- [Manifesto da run](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/manifest.json),
  [resumo completo](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/summary.json) e
  [pastas dos 12 vídeos](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/by_video).
- [Conferência independente](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/verification_20260908.json).
- [Figura PNG](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/trajetorias_individuais_treino.png),
  [SVG](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/trajetorias_individuais_treino.svg) e
  [revisão visual estática](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/visual_review.json).

Cada pasta de vídeo contém exatamente sete arquivos: `ground_truth_raw.csv`,
`observations.csv`, `segments.csv`, `windows.csv`, `frame_status.csv`,
`summary.json` e `input_contract.json`. As fontes permanecem em seu local;
a preparação é derivada e recriável. IDs originais ficam em `track_id` e os
trechos consecutivos em `segment_id`. Os índices atuais ainda precisam ser
integrados aos consumidores de predição, com controle causal e ADE denso.

SHA-256 do manifesto: `88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35`.
SHA-256 da conferência: `f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9`.

### Próximo marco

Implementar o consumo desses índices comuns pelos baselines de persistência
e velocidade constante, separando entradas até `t` de alvos futuros e
calculando ADE em todos os passos `1..H`. Verificar primeiro com casos
analíticos e registrar o plano antes da execução real. O contrato de tracking
com IDs originais e HOTA permanece uma etapa própria; o acoplamento de fluxo
e a comparação com/sem fluxo vêm após os controles de causalidade e pareamento.
Teste e folds continuam bloqueados pelo desenho confirmatório pendente.
