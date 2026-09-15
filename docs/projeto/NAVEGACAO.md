# Guia permanente de navegação e retomada

<!-- refinement-dataset-completion-20260911 -->

Resultados documentados em `4c96da7693096a7d583efefe60acbbb5af5f6a2d`, com Git limpo ao concluir.
Esse commit documental não altera a proveniência das runs em `ca68f16`.
A edição local foi conferida: 19 capítulos, sete figuras e quatro laboratórios,
com QA estático, navegação e revisão visual. Registro da entrega:
`data/derived/project_audits/general_20260911/classical_refinement_edition/completion.json`.

## Continuidade vigente — refinamento e dataset conferidos em 11/09/2026

Refinamento concluído e conferido em `ca68f16`, com Git limpo na execução: **45 configurações × 576 quadros = 25.920 avaliações**, somente nos 12 treinos. A vizinhança previamente definida gerou 54 propostas, 51 válidas e 45 configurações únicas. Os dez pais passaram na paridade de objetos brutos e métricas; T218 permaneceu histórico, sem nova execução. Há dez finalistas, duas por família, sem promoção ou liberação automática da validação.

Bateria: 528,244100 s; RSS amostrado 410,406 MiB; 394.820.008 bytes dos artefatos das candidatas, excluindo o agregador. QA: 1.061 arquivos, 39.670.198 comparações, 26.831.879 numéricas e 155.520 matchings SciPy em 281,243874 s; diferença numérica máxima 0.

[Manifesto do refinamento](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json) · [Resumo e resultados por vídeo](../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

SHA256 do manifesto: `0c686f61f51af3129b89e878ba60ce2067e15c8c3bcceb478eee074f5e407e6b`.
SHA256 do QA: `d82c58bff8d0ba8323ec1d43af23dc18f470c9da8f72c1c86d7aec14769f8118`.
Fontes da execução: `f2ecb55da1bf19ff1fd2247f0e196d30f064fc95fc399c6b465c805c219a8766`.

Dataset YOLO materializado e conferido em `ca68f16`: **23.316 pares JPEG/anotação**, sendo 17.466 de treino e 5.850 de validação; 174 lacunas de anotação excluídas. Preservadas as três classes e as caixas da referência FTID. O conjunto contém 491.729 observações anotadas, não indivíduos únicos. Foram copiados 46.632 arquivos e gerados três descritores.

Preparação: 1.237,798253 s; RSS amostrado 198,160 MiB; dataset com 1.471.015.512 bytes. QA: 116.590 arquivos, 8.724.385 comparações e 23.316 cópias JPEG decodificadas em 195,027052 s. A conferência verificou paridade de 491.729 anotações, com diferença máxima 0.

[Manifesto do dataset](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json). O teste ficou fora da preparação. **Não houve treinamento YOLO:** `training_allowed=false` e `consumer_clone_required=true`; o consumidor deve gerar outro clone independente dentro de sua própria run antes de chamar a biblioteca.

A paridade geométrica entre anotações YOLO e FTID não certifica igualdade de pixels entre JPEG e MP4. Os JPEGs servem ao treinamento e à validação nativa do modelo aprendido. Para comparar F1 v3 com os clássicos, YOLO deverá processar os mesmos quadros MP4/cache usados por eles, com pré-processamento explicitamente registrado. Essa distinção delimita o derivado e o futuro contrato de comparação; não representa falha na organização atual do dataset.

SHA256 do manifesto: `e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42`.
SHA256 do QA: `0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be`.

Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold.

Não repetir as baterias concluídas, não reescrever pais/runs ou YAMLs históricos e não entregar o dataset selado diretamente à biblioteca de treinamento. O commit do código/run é `ca68f16`; o commit documental final está registrado no início desta seção. HTMLs, guia local, instruções locais e monografia permanecem fora dos commits. Contagens editoriais de figuras/capítulos/laboratórios dependem da revisão própria do relatório e não são atestadas por este registro científico.

[Guia permanente, seção 21](NAVEGACAO.md). Os registros de continuidade abaixo são históricos e conservam suas datas e proveniência.

## Histórico — comparação clássica conferida em 11/09/2026

Resultados científicos documentados em `27bec7a`, com Git limpo ao concluir.
Esse commit documental não muda a proveniência da busca/smoke em `2547109`.
Registro local desta entrega em
`data/derived/project_audits/general_20260911/classical_comparison_edition/completion.json`.

A orientação atual é testar e validar os demais algoritmos antes de escolher
a cadeia de tracking/predição. **Smoke e busca clássica concluídos e
conferidos** em `2547109`, Git limpo: 43 configurações de seis famílias,
576 quadros dos 12 treinos, 24.768 avaliações. Não repetir essas baterias.
Conferência: 289 arquivos,
30.927.965 comparações, 148.608 matchings
SciPy, paridade T218 nos 576 quadros. Busca 752,160737 s,
RSS amostrado 823,145 MiB.

Busca: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/20260911T144742812472Z__2547109__cfgbecfe1d189e7__srcf14ede5a12__s42/manifest.json`.
SHA256 do manifesto: `8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0`.
QA: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/verification_20260911.json`.
SHA256 do QA: `c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792`.
Fontes da execução: `f14ede5a1240d6e6588f5859a02e408ec99601aa019513af7a6f4478ac86d64c`.

Smoke v2: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgd3cb65ba/smoke/20260911T144621160257Z__2547109__cfg69087a632a64__srcf14ede5a12__s42/manifest.json`.
Manifesto SHA256 `2cad2719b618e14fe07a3f45bba658499fa557c798d0fc59f60610b3b1406b54`.
QA: `data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgd3cb65ba/smoke/verification_20260911.json`.
QA SHA256 `05095ce3c4659b29935df343f1d2b990a4a7f5b38bbc406e232e76e7adb9a1d8`.

Plano executado: `configs/detection/comparison/classical_v1_operational_v2.yaml`.
O v1 e sua falha por limite de 2.000 previsões permanecem preservados; v2
mudou somente identidade/linhagem e teto operacional para 307.200. Não truncar
previsões nem reinterpretar a falha como comparação concluída. Protocolo e
resultados em `docs/metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md`.

Próximo marco: novo YAML/executor de **refinamento** sobre as 11 candidatas
em `family_finalists.json` (T218 fixa; dois pais por família pesquisada).
Resolver a vizinhança um eixo por vez, previamente definida no protocolo,
incluindo pais e deduplicação, até 54 configurações antes de deduplicar.
Depois, nova validação das dez finalistas em quatro vídeos completos;
T218 histórica só entra após autenticação, preservando custo/commit próprios.
Não relaxar a CLI histórica `threshold/validate.py`: criar consumidor novo.
A CLI `compare_classical.py` atual aceita apenas smoke/search; não libera
refinamento, validação, teste ou promoção. A nova QA deverá manter paridade.

Ambiente `.venv-ml` validado sinteticamente na RTX 4070 Ti: torch 2.9.1+cu128,
torchvision 0.24.1+cu128, ultralytics 8.4.147. Recibo
`data/derived/project_audits/learned_environment/20260911_validation_v1.json`;
hash `29414ce0667c40ccd23e317cc86c07b6ed048e2efa249d968fb60c3fa907312b`.
Foi executado em a924fe5 com Git sujo declarado; não reatribuir o código.
YOLO precisa de cópias derivadas autenticadas: a biblioteca escreve caches
mesmo com cache=False e pode reparar JPEG; não apontar às fontes nem usar
hardlinks. Fixar receita/checkpoints por protocolo próprio, pesos/hashes,
treino nas três classes e avaliação de indivíduos 0/2 com a regra de clusters v3. O smoke não treinou YOLO/RAFT/LSTM.

Contrato de rastreamento em `docs/metodologia/RASTREAMENTO_COMPARACAO_V1.md`
e `configs/tracking/comparison_v1.yaml`: rascunho não executável, com cinco
métodos. HOTA oficial, política de clusters/lacunas, adaptador sem IDs GT e
cache de detecções comum ainda devem ser implementados/conferidos.
MOG2/KNN precisam de clipes cronológicos e aquecimento; não usar os quadros
espaçados desta busca como se fossem sequências consecutivas.

A primeira ablação causal nas 10.848 janelas disponíveis continua prevista.
O histórico do 8a abaixo continua válido para fluxo: não existe ADE/FDE real
com fluxo, HOTA real atual ou teste da hipótese. O teto histórico de 120 min
não limita novos planos, conforme autorização de 11/09; preservar YAML/run
anteriores, recursos, causalidade, exclusões e completude. Teste/folds
continuam bloqueados e sua exposição histórica declarada.

O relatório e atlas locais incorporam os resultados de 11/09: 19 capítulos,
seis figuras e quatro laboratórios. Componentes e QA em `tmp/tcc_report/`;
figura/resumo autenticado em
`data/derived/detection/comparison_reports/classical_v1_20260911/`.
Snapshot e registro da edição:
`data/derived/project_audits/general_20260911/classical_comparison_edition/`.
Os HTMLs, este guia, instruções locais e monografia permanecem fora dos commits.

Atualizado em 2026-09-11. Este é o ponto de partida operacional para o
pesquisador e para agentes que retomarem o repositório. O estado científico
continua na matriz e no diário; este arquivo explica onde encontrá-lo.

Para compreender o projeto do início ao fim, leia o
[relatório completo do TCC](RELATORIO_COMPLETO_TCC.html), atualizado em 11/09/2026.
São 19 capítulos sobre objetivo, dados, pipeline, decisões, resultados,
métricas, pastas, alinhamento acadêmico e próximos passos. Os capítulos novos
explicam como estudar o projeto, a lógica dos algoritmos, um exemplo completo
e a leitura de arquivos reais. Há busca, seis figuras científicas e quatro
laboratórios: F1, ADE/FDE, causalidade e interpolação bilinear. O atalho da raiz é
[RELATORIO_COMPLETO_TCC.html](../../RELATORIO_COMPLETO_TCC.html).
O gerador documental não executa modelos. Esta edição incorpora a busca
comparativa real de 11/09, executada e conferida separadamente. O nível 8a
permanece o último resultado de fluxo; sua projeção excedeu o limite histórico.
Refinamento/validação dos detectores e YOLO são as próximas etapas; ablação
e extração ampliada continuam previstas sob contratos próprios. HTMLs e este guia permanecem fora dos commits.
Os componentes da edição ficam em `tmp/tcc_report/`; o HTML canônico contém
figuras, estilos e exemplos incorporados e pode ser preservado sozinho.
Se os componentes temporários não estiverem disponíveis em uma retomada,
atualize o HTML canônico e mantenha o atalho, o atlas e este guia coerentes.
O registro da edição histórica de 08/09 e suas evidências visuais ficam em
[relatorio_completo_tcc_20260908/completion.json](../../data/derived/project_audits/general_20260908/relatorio_completo_tcc_20260908/completion.json).
Na edição de 08/09 foram conferidos 854 links locais do relatório, interações no navegador,
leitura em computador/celular e apresentação da impressão, sem gerar PDF.
Esclarecimentos públicos de documentação foram registrados em `7896e3e`;
esse commit não altera o código científico nem a proveniência das runs.

A atualização histórica do nível 7, em 09/09, tem quatro figuras incorporadas, 883 links locais no
relatório canônico conferidos, leitura desktop/celular e interações aprovadas.
O atlas também foi conferido nos dois tamanhos; caminhos longos agora quebram
linha sem alargar a página. Evidências e registro desta conclusão:
[nível 7 — conclusão local](../../data/derived/project_audits/general_20260909/causal_flow_level7_completion_20260909/completion.json).

Registro anterior da frente de fluxo: **nível 8a concluído e conferido — 09/09/2026**.
Resultados documentados em `400cc2d0ed042a27ae88e8c4a81d2d9ae2da7981`, com Git limpo ao concluir.
Esse commit documental não altera a proveniência da run/código em `6110c44`.

O benchmark compacto de engenharia terminou em `6110c44526c30f8f8f7a2fdeb276f7169d2fcd88`,
com Git limpo, após 1.728 testes em 181,93 s. Foram 720 quadros nos 12 treinos,
708 campos forward, 24 backward, 10.848 janelas, 15.762 amostras distintas
válidas e 206.112 usos. Todas as janelas têm as cinco amostras finais válidas.
Tempo 199,583442 s, RSS amostrado 375,145 MiB, 154.023.508 bytes finais.
QA aprovado na primeira tentativa: 288 arquivos, 934.668 comparações,
127.506 numéricas, 94.572 coordenadas, 23,4658582 s; diferença máxima
3,552713678800501e-15. O QA usa os testemunhos de todas as amostras e os
campos densos sentinelas, sem decodificar fontes ou refazer Farnebäck.

**A projeção de tempo NÃO passou:** 8.052,675671 s (134,21 min) > 7.200 s
(120 min). Os 1.768,62 MiB projetados cabem nos 4.096 MiB; RAM completa
continua não certificada. Não elevar o teto retroativamente, remover o fator 2
ou executar a extração completa com esta CLI. O laço responde por 93,34% do
tempo projetado, mas reúne decodificação/estimação/amostragem/testemunhos.
Próximo marco: registrar instrumentação dessas parcelas e ajuste operacional
verificável, com equivalência numérica e recursos, antes de novo ensaio.
Depois, plano completo de extração, memória/índices e ablação pareada.
Não repetir as baterias encerradas. Não há ADE/FDE com fluxo, seleção,
promoção ou teste da hipótese. O preditor causal existe e só foi testado
sinteticamente. `future_flow_mode=observed` segue proibido.

Run: `data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/manifest.json`.
QA: `data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/verification_20260909.json`.
Manifesto SHA256: `72c7df2d895d1fa02014dfa1100a1a7defc8351ea19d86392ad09e5473fcd278`.
QA SHA256: `20af88c5930434685a86330d98692f99d9a429f0e0e61723ae41138e1af1435c`.
Código-fonte SHA256: `a19f8367f992f31710d50dc6e17bec33cdbce4905eae3a8eb9bc6bb477e0c81d`.
Plano e contrato: `configs/flow/farneback/compact_benchmark_v1.yaml` e
`docs/metodologia/FLUXO_COMPACTO_V1.md`. Entradas e arquivos na seção 17 do
guia; bloco `fluxo-compacto-nivel8a` no atlas. O identificador da run é UTC
de 10/09; a data local da execução é 09/09 em São Paulo. HTMLs, guias e
monografia permanecem fora dos commits. Preservar fontes e runs anteriores.

Marco anterior: **nível 7 concluído e conferido — 09/09/2026**.
Resultados documentados em `581f15c62b6f345b0a5e5b72bc89c1c337eeb319`,
com Git limpo ao concluir. Esse commit documental não altera a proveniência
da run em `16eecbb` nem a correção do verificador em `0fccda8`.
Protocolo/código/run em `16eecbb32b3edb4b4908ced344367670132a4cc1`, com Git
limpo. Suíte selecionada: 1.495 testes em 160,71 s antes dos pixels. Smoke 11/12,
quadros 0..19: 40 quadros, 38 pares, 76 campos, 68 janelas, 1.292 amostras válidas,
zero inválidas; 56,923953 s, 289,598 MiB RSS amostrado, 193.999.043 bytes finais.
Conferência: 190 arquivos, 37.406 comparações (8.378 numéricas), 21,051553 s;
máxima diferença 8,881784197001252e-16. A primeira falha de esquema do
verificador foi preservada; correção em `0fccda8`, com nove testes sintéticos,
sem alterar ou repetir a run. Consulte a seção 16 para todas as entradas.
Não há teste da hipótese ou promoção. O próximo marco é registrar protocolo
da extração causal ampliada e ablação equivalente com/sem fluxo no treino.
Preservar referência, baselines e smoke; não repetir baterias encerradas.

Marco anterior: **nível 6 concluído e conferido**.
Resultados científicos documentados em `b55490f616c926cc937215372c0e2436dcbd437a`,
com Git limpo ao concluir. A fonte LaTeX foi atualizada localmente, fora do Git.
Esse commit documental não altera a proveniência do protocolo, código e run em `5289c93`.
Protocolo e implementação em `5289c93e448c7e571ea92f30de3a7f5cb2c0d611`;
1.362 testes da suíte completa selecionada passaram em 144,75 s. A bateria
terminou em 54,191753 s, com Git limpo e reconferido.
Protocolo, plano e executor dos dois baselines fixos estão na seção 15.
Persistência e `cv_median5` usaram as mesmas 343.776 janelas GT, com ADE denso
em H=1/5/10 e peso igual por ID original dentro do vídeo, depois por vídeo.
Os resultados descritivos e artefatos estão na seção 15; a revisão visual e
o QA independente passaram. A primeira conferência verificou 187 arquivos e
34.749.527 comparações. O próximo marco será preparar
contrato e smoke causal de Farnebäck; esta bateria não mediu fluxo.

Marco anterior: **nível 5 concluído e conferido**.
Resultados registrados em `6ffe6c5`; Git limpo ao concluir. Esse commit
documental não muda a proveniência da preparação.
Código, plano e run em `33d191d`, após 1.026 testes em 108,58 s, com Git limpo.
A referência contém 363.074 observações individuais, 725 segmentos e 343.776
janelas. A primeira conferência independente passou: 86 arquivos e 9.407.090
comparações. São contagens da preparação, sem desempenho de predição.
T218/o0/c2 está congelado para desenvolvimento; teste e folds permanecem
bloqueados. Plano, módulo e CLI de trajetórias individuais v1 estão registrados.
Consulte a seção 14. O histórico da validação continua em `f308d08`, com
protocolo, código e runs em `7f47afb`; a seção 13 preserva essa proveniência.

[Início](../../README.md) · [Atlas visual](mapa-tcc-didatico.html)
· [Regras do repositório](../../AGENTS.md)

## 1. Ordem de leitura ao retomar

A auditoria de geometria de 07/09 foi concluída antes da aprovação do raio.
Seu manifesto conserva o hash de `configs/protocol/splits.yaml` daquele
momento. As atualizações posteriores do bloco de avaliação para as versões
2 e 3 mudam esse hash, sem mudar os IDs de treino ou reescrever os artefatos da
auditoria. Os manifestos descrevem o estado da respectiva execução.

1. Leia o pedido atual do usuário e [AGENTS.md](../../AGENTS.md).
2. Use este guia e o [mapa do código](../../src/README.md) para localizar a tarefa.
3. Confira a [matriz de experimentos](MATRIZ_EXPERIMENTOS.md) e as entradas
   recentes do [diário](DIARIO.md). Distinga implementação, teste automatizado,
   piloto, validação e confirmação científica.
4. Leia a [ficha do algoritmo](../algoritmos/README.md), sua implementação e
   o YAML específico. Consulte o [protocolo](../metodologia/PROTOCOLO.md).
5. O pesquisador autorizou a continuidade autônoma. Explique finalidade e
   decisões, registre os limites de cada evidência e avance nas etapas
   necessárias, sem repetir pedidos de autorização já concedida. O marco
   atual é o marco 8a, benchmark compacto concluído e conferido,
   conforme a seção 17. A continuidade vigente consta no início deste guia. Os baselines do nível 6 permanecem na seção 15. A referência individual do nível 5 já está concluída
   e conferida; preservar seus índices e hashes sem repetir a preparação.
   O nível 4 concluiu a validação; o nível 3 teve plano registrado,
   cache concluído e benchmark inicial
   acima do orçamento, seguido de otimização e repetição bem-sucedidas. A busca
   grossa já foi concluída e conferida. O refinamento registrado está
   concluído e conferido, com 117 candidatos. T219/o0/c2 e T218/o0/c2 são
   finalistas de treino, sem promoção. A revisão geral confirmou o alinhamento
   e levou ao executor estrito e à validação completa das duas finalistas.
   T218/o0/c2 foi selecionada, F1 macro 0,658959; naquele encerramento ainda
   não havia congelamento. Agora está fixada para desenvolvimento, com teste
   e folds bloqueados, conforme a seção 14.
   Runs de `7f47afb`, 824 testes e conferência independente aprovada.
   Consulte a seção 13 para esta etapa; a seção 12 preserva o refinamento
   registrado em `bd2d216`, com execução em `da057ef`. Não confunda custo de execução com seleção científica.
6. Verifique as mudanças locais antes de editar. Preserve trabalho existente,
   dados originais e runs. Os [comandos oficiais](../../script/README.md)
   são a única referência de execução.

## 2. Responsabilidade de cada área

| Procura | Local e entrada |
|---|---|
| Algoritmos | [src/README.md](../../src/README.md) e guias por tarefa |
| Parâmetros, espaços de busca e splits | [configs/README.md](../../configs/README.md) |
| Menus, executores e lotes | [script/README.md](../../script/README.md) |
| Testes automatizados | [tests/README.md](../../tests/README.md) |
| Saídas de desenvolvimento | [data/tests/README.md](../../data/tests/README.md) |
| Seleções congeladas, confirmação e aplicação | [data/results/README.md](../../data/results/README.md) |
| Fontes e derivados | [data/README.md](../../data/README.md) |
| Fundamentação e decisões metodológicas | [docs/README.md](../README.md) |
| Texto acadêmico oficial | [monografia/README.md](../../monografia/README.md) |

`tests/`, `script/<tarefa>/test/` e `data/tests/` têm funções distintas:
verificar código, iniciar experimentos e guardar seus resultados, respectivamente.
O conjunto de teste científico é uma divisão em
[splits.yaml](../../configs/protocol/splits.yaml), não uma pasta de código.

## 3. Caminho completo do threshold e do frame a frame

| Parte | Abra |
|---|---|
| Implementação fixa, Otsu e adaptativa | [ThresholdContourDetector](../../src/detection/classical/threshold.py) |
| Baseline v3 atual, congelada para desenvolvimento | [T218/o0/c2 v3](../../configs/frozen/detection/threshold/t218_o0_c2_v3.yaml) e [escopo do congelamento](../metodologia/CONGELAMENTO_THRESHOLD_V3.md) |
| Configuração usada | [T200/o1/c2 de desenvolvimento](../../configs/detection/threshold/t200_o1_c2.yaml) |
| Registro de parâmetros congelados | [T200/o1/c2 congelado](../../configs/frozen/detection/threshold/t200_o1_c2.yaml) |
| Teoria e estado do método | [Ficha do threshold fixo](../algoritmos/deteccao/threshold_fixo.md) |
| Menu da bancada | [interactive.py](../../script/detection/test/threshold/interactive.py) |
| Execução de um frame | [single_frame.py](../../script/detection/test/threshold/single_frame.py) |
| Bateria de frames | [batch_frames.py](../../script/detection/test/threshold/batch_frames.py) |
| Busca prospectiva v3 | [search.py](../../script/detection/test/threshold/search.py) → [detection_search.py](../../src/experiments/detection_search.py) |
| Plano registrado da busca | [search_v3.yaml](../../configs/detection/threshold/search_v3.yaml) |
| Configuração operacional do refinamento | [refinement_v3.yaml](../../configs/detection/threshold/refinement_v3.yaml), separada do plano-base imutável |
| Conferência dos pais e expansão do refinamento | [detection_refinement.py](../../src/experiments/detection_refinement.py) |
| Cache canônico compartilhado | [detection_sample.py](../../src/experiments/detection_sample.py) |
| Leitura de frame e anotação | [frames.py](../../script/detection/test/threshold/frames.py) |
| Como executar | [Comandos oficiais do frame a frame](../../script/README.md#threshold-frame-a-frame) |
| Significado das imagens e tabelas | [Guia da bancada](../../script/detection/test/threshold/README.md) |
| Resultados existentes | [threshold](../../data/tests/detection/threshold/), [otsu](../../data/tests/detection/otsu/) |
| Leitura das pastas de saída | [Artefatos de detecção](../../data/tests/detection/README.md) |

O mesmo algoritmo gera as detecções e as imagens intermediárias. Não existe
uma segunda implementação de threshold escondida na bancada.

Otsu compartilha a classe: `threshold_value: null` e `adaptive: false`.
O limiar fixo T200 exige `threshold_value: 200`. MOG2/KNN dependem de histórico
e têm [bancada temporal própria](../../script/detection/test/background_subtraction/README.md).

Novas runs frame a frame seguem
`data/tests/detection/<algoritmo>/<configuração>/frame_screening/<run_id>/`.
Vídeo e frame ficam no manifesto. O legado pode conservar níveis adicionais
`video_<id>/frame_<n>/`; não mova runs antigas para imitar a estrutura nova.

## 4. Demais algoritmos e dependências

| Tarefa | Mapa dos arquivos | Entrada → saída |
|---|---|---|
| Detecção | [Guia](../../src/detection/README.md) | Vídeo → detecções e métricas por frame |
| Tracking | [Guia](../../src/tracking/README.md) | Detecções → trajetórias com identidades e formato MOT |
| Fluxo | [Guia](../../src/flow/README.md) | Par de frames → campo aparente, validade e índice de cache |
| Integração | [Guia](../../src/integration/README.md) | Trajetórias + cache → trajetórias enriquecidas com fluxo |
| Predição | [Guia](../../src/prediction/README.md) | Histórico → previsões e métricas por janela |

Os guias por tarefa são os índices completos de Python, YAML e ficha.
Algumas classes compartilham bases ou usam bibliotecas externas: arquivo curto
não significa algoritmo ausente. `__init__.py` identifica o pacote e pode
conter só uma descrição. Executores curtos de `script/` indicam no cabeçalho
qual implementação de `src/` chamar.

Infraestrutura transversal: [caminhos](../../src/core/paths.py),
[runs/proveniência](../../src/experiments/runs.py),
[regras executáveis](../../src/experiments/protocol.py),
[matching de detecção](../../src/evaluation/detection.py),
[TrackEval](../../src/evaluation/tracking.py),
[estatística](../../src/evaluation/statistics.py) e
[catálogo SQLite](../../src/db/build_db.py).

## 5. Endereços históricos que causam confusão

| Caminho antigo | Local atual |
|---|---|
| `src/detection/detect_threshold_contours.py` | [src/detection/classical/threshold.py](../../src/detection/classical/threshold.py) |
| `src/detection/base_detector.py` | [src/detection/base.py](../../src/detection/base.py) |
| `src/detection/run_detection.py` | [Executor](../../script/detection/test/run_detection.py) → [pipeline](../../src/detection/pipeline.py) |
| `src/detection/interactive.py` | [script/detection/test/interactive.py](../../script/detection/test/interactive.py) |
| `tests/sandbox/single_frame.py` | [script/detection/test/threshold/single_frame.py](../../script/detection/test/threshold/single_frame.py) |
| `tests/sandbox/batch.py` | [script/detection/test/threshold/batch_frames.py](../../script/detection/test/threshold/batch_frames.py) |
| `tests/sandbox/interactive.py` | [script/detection/test/threshold/interactive.py](../../script/detection/test/threshold/interactive.py) |
| `tests/sandbox/stages.py` | [diagnostic_stages no próprio detector](../../src/detection/classical/threshold.py) |

O [manifesto de migração dos artefatos](../../data/manifests/layout_20260829.csv)
registra os destinos dos dados migrados. Ele não é um inventário completo de
renomeações de código. Referências internas de runs antigas podem ser resolvidas
por [core/relocation.py](../../src/core/relocation.py).

## 6. Como manter a navegação

- Quando mudar o caminho de um algoritmo, atualize seu guia em `src/`, a ficha
  em `docs/algoritmos/` e os links deste arquivo que apontem diretamente a ele.
- Mantenha comandos oficiais em `script/README.md`; outros documentos devem
  apontar para suas seções, sem manter comandos concorrentes.
- O atlas visual editável fica em
  [docs/projeto/mapa-tcc-didatico.html](mapa-tcc-didatico.html).
  O [MAPA_TCC_DIDATICO.html](../../MAPA_TCC_DIDATICO.html) da raiz é um atalho
  que abre esse atlas, preservando a âncora da URL. Não mantenha uma segunda
  cópia integral do conteúdo na raiz.
- Atualizações de navegação não promovem um método na matriz científica.
  Datas de revisão documental e de resultados experimentais devem permanecer
  distintas.
- Use a [verificação existente de links](../../tests/config/test_documentation_links.py)
  e confira também âncoras e links do HTML quando alterar mapas.

## 7. Pendências metodológicas e sequência de execução

Na retomada de setembro de 2026, o pesquisador pediu confirmar primeiro o
objetivo e avançar lentamente, com explicação e autorização por etapa.
Posteriormente autorizou continuidade autônoma; esse limite de autorização
foi substituído, mantendo explicação, rastreabilidade e separação científica.
O escopo foi confirmado em 07/09/2026: usar exclusivamente vídeos VISEM e
anotações VISEM-Tracking, uma extensão da mesma coleção. Há 20 vídeos com
trechos anotados para avaliação quantitativa e outros 65 sem tracking manual
para aplicação posterior. A condição de contracorrente gerada por tubo
citada anteriormente na monografia não está documentada nos artigos de
aquisição; foi retirada do escopo. Isso não prova ausência de deriva.
Consulte a decisão e as fontes no
[protocolo](../metodologia/PROTOCOLO.md#escopo-dos-dados-e-interpretação-do-movimento).

A hipótese principal permanece a redução de ADE/FDE por características
locais de fluxo óptico combinadas ao histórico de posições, comparadas a
preditores equivalentes sem fluxo. O planejamento ainda precisa detalhar
os critérios das comparações e o desenho da confirmação em folds diante da
exposição histórica do teste. Essas pendências não foram resolvidas pela
correção do escopo. O contrato v3, o smoke e a precisão dos CSVs foram
verificados, como descrito na seção 11.

A auditoria de navegação encontrou implementações concretas de threshold,
tracking, fluxo e predição, inclusive LSTM e o adaptador RAFT. Ela não
equivale a executar os modelos nem a comprovar seu desempenho no VISEM.
Consulte a matriz e as runs antes de declarar qualquer etapa concluída.

Na revisão inicial, a bancada permitia contornar a recusa por `--id` usando
um caminho em `--video`. O problema foi corrigido no nível 2:
[single_frame.py](../../script/detection/test/threshold/single_frame.py) recusa
também os caminhos conhecidos do teste antes da decodificação. A regressão é
sintética; não foi necessário abrir esses vídeos para verificar o bloqueio.

## 8. Revisão de organização e limpeza — 07/09/2026

- Verificados 163 arquivos Python em `src/`, `script/` e `tests/`: sintaxe
  válida. Os dois arquivos com zero bytes são marcadores `__init__.py` válidos.
- Os cabeçalhos de 22 pacotes e 16 executores curtos de `script/` passaram a
  explicar sua função e indicar onde encontrar a implementação.
- A comparação das árvores sintáticas antes/depois, desconsiderando
  docstrings, confirmou nenhuma mudança de código executável nesta organização.
- Os 19 testes existentes selecionados de links e contratos dos executores
  passaram. Isso verifica navegação/estrutura, não desempenho científico.
- A busca nas áreas ativas não encontrou código ou documentação comprovadamente
  inútil, nem diretórios de cache Python/pytest para excluir. Não foram removidos
  algoritmos, configurações, fontes, entregas nem artefatos experimentais.
- A cópia integral do atlas na raiz (133.557 bytes) foi substituída por uma
  entrada de redirecionamento (969 bytes): 132.588 bytes de conteúdo duplicado
  eliminados, mantendo o nome de acesso pedido pelo pesquisador.
- Comandos repetidos foram substituídos por links à referência oficial.
  Conteúdo histórico e navegação atual do frame a frame estão separados no atlas.

A prévia do HTML no navegador integrado foi bloqueada pela política de URLs
locais. A conferência desta revisão é estática; a aparência renderizada ainda
deve ser conferida ao abrir o atlas no navegador local do pesquisador.

## 9. Arquivos locais e commit — 07/09/2026

O pesquisador solicitou que o commit contenha código, configurações e
documentação técnica, excluindo HTMLs e registros de assistência por IA.
O commit local `c86d60f` registra a reorganização; 223 testes passaram.

- `AGENTS.md`, este guia, a pasta `monografia/` e os inventários JSON
  históricos estão excluídos localmente por `.git/info/exclude`.
- HTML, PDF, DOCX e ZIP estão ignorados no `.gitignore`.
- Esses arquivos continuam no computador. A monografia e sua declaração de
  assistência foram preservadas integralmente, fora desse commit.
- Os README versionados navegam pelos mapas técnicos; os links para documentos
  locais excluídos foram retirados para não quebrar em outra cópia do repositório.
- `AGENTS.md` foi retirado somente do índice. Versões anteriores permanecem
  no histórico; não foi solicitado nem realizado reescrever commits antigos.
- Antes de outro commit, revisar os arquivos efetivamente selecionados e
  respeitar essa separação. Não incluir arquivos locais com `git add -f`.

## 10. Correção do escopo e próxima conversa — 07/09/2026

Após consulta aos artigos originais e ao PDF assinado enviado pelo pesquisador,
foi autorizada e aplicada a correção do texto-fonte em `monografia/`:

- `template_tcc_bsi.tex`: resumo e abstract descrevem exclusivamente vídeos
  VISEM, com anotações VISEM-Tracking em trechos de 20 vídeos.
- `cap_introducao/introducao.tex`: retirada a segunda coleção do cenário-alvo.
- `cap_fundamentacao/fundamentacao.tex`: explicados aquisição, deriva e ausência
  de documentação de contracorrente imposta; mantidas as fontes originais.
- `cap_metodo/metodo.tex`: explicitados trechos anotados, origem comum dos
  vídeos e limites da conversão de movimento aparente para unidades físicas.

O método local já continha atualizações posteriores ao PDF assinado; elas
foram preservadas. A hipótese principal, os splits, as configurações e as runs
não foram alterados. Também foram alinhados protocolo, diário, README e atlas.

As verificações estáticas dos sete arquivos LaTeX e de suas 18 chaves de
citação passaram. Não foi encontrado compilador LaTeX disponível; ainda é
necessário compilar a fonte e conferir o PDF visualmente. O PDF assinado e as
entregas anteriores foram preservados. Esta revisão não criou um novo commit.

Na conversa seguinte, foram explicados treino, validação e teste. O pesquisador
relatou que comparava diversos limiares com as anotações de referência para
escolher o melhor e aceitou considerar um reinício organizado se necessário.
Isso caracteriza seleção de parâmetros; não implica erro no formato dos dados.
O histórico registra exploração nos 20 vídeos, inclusive nos quatro reservados
ao teste. Reexecutar ou redistribuir esses vídeos não restaura seu desconhecimento
durante o desenvolvimento. Aplicar um threshold fixo já selecionado a cinco
grupos também não torna as métricas uma avaliação independente da seleção.

Verificação limitada do leitor: 11 testes sintéticos existentes de
`tests/detection/test_io.py` passaram (17 não selecionados). Foram cobertos
coordenadas YOLO, IDs textuais, alinhamento por número do frame e distinção
entre anotação ausente e arquivo vazio. Não foram lidos vídeos nem anotações
reais do teste nessa verificação. Isso não certifica toda a coleção.

Pendências de auditoria em `src/detection/io.py`: o cabeçalho descreve ID opcional
no fim, enquanto o parser usa ID textual no início; faltam verificações
explícitas de finitude, intervalo normalizado, classes e número de campos.
IDs numéricos podem ser ambíguos na heurística. A distinção ausência/vazio
depende de `load_gt_for_frame`; `load_gt_frame` isolado retorna lista vazia
para arquivo ausente. Nenhuma dessas observações, sozinha, demonstra erro nas
anotações reais. Revisar também a proteção de caminhos da bancada descrita
na seção 7 antes de novas baterias.

Naquele momento, o próximo passo autorizado era conferir um quadro do vídeo
11, pertencente ao treino, com as anotações sobrepostas, antes de variar limiares.
Depois, definir busca reproduzível e seleção separada da avaliação por vídeo.
O código, as configurações congeladas e os resultados históricos permanecem
preservados; naquele momento ainda não havia aprovação de um novo protocolo.
A autorização posterior aparece na seção 11; o estado vigente está na seção 12.

## 11. Histórico da retomada: níveis 1 e 2 concluídos — 07/09/2026

O pesquisador autorizou começar pela conferência de um quadro do vídeo 11.
Ele também pediu clareza na organização dos novos dados e perguntou sobre
apagar o histórico. A retomada preserva todas as fontes, configurações e runs
anteriores; não é necessário apagar resultados para começar uma inspeção nova.

| Procura | Local |
|---|---|
| Executor sem detector, restrito ao treino | [inspect_annotations.py](../../script/project/test/inspect_annotations.py) |
| Única referência do comando | [Inspeção de anotações](../../script/README.md#inspecao-de-anotacoes) |
| Organização e significado das saídas | [Guia dos derivados de inspeção](../../data/derived/detection/annotation_audit/README.md) |
| Quadro original decodificado do MP4 | [00_quadro_original.png](../../data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/00_quadro_original.png) |
| Quadro com caixas e centros manuais | [01_quadro_anotado.png](../../data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/01_quadro_anotado.png) |
| Exemplo ampliado de uma anotação | [02_exemplo_anotacao.png](../../data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/02_exemplo_anotacao.png) |
| Coordenadas, classes e IDs | [annotations.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/annotations.csv) |
| Proveniência da inspeção | [manifest.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/manifest.json) |

Nos dois arquivos de anotações do frame 0 há 43 caixas da classe 0, iguais
linha a linha, com 43 IDs textuais únicos no formato FTID. Na imagem de
referência 640 × 480 px, todas as caixas respeitam os limites; a linha 36 toca
x = 640. A primeira anotação tem centro (176,5; 198) px, largura 17 px e
altura 18 px. O leitor existente interpreta ambos os formatos de maneira
equivalente; o formato sem IDs usa −1 como ausência de identidade.

Esses fatos conferem a consistência de um quadro, não a completude de todo o
dataset, o tracking temporal ou o desempenho do threshold. Classe `normal`
é um rótulo de anotação, não diagnóstico. `cluster` representa agrupamento;
não deve ser contado automaticamente como uma célula individual. Não há
anotações dessa classe no quadro inspecionado.

O pesquisador confirmou que compreendeu a diferença entre a caixa anotada e
seu centro no exemplo do nível 1. Essa compreensão não certifica toda a coleção.
No nível 2, aprovou priorizar a localização dos centros na avaliação da
detecção; tamanho e formato das caixas ficam como aspectos complementares.

### Auditoria descritiva do treino concluída

Foram examinadas as anotações dos 12 vídeos de treino: 17.466 quadros anotados
e 368.487 observações válidas. Uma observação é uma anotação em um quadro;
identidades repetidas no tempo não representam células novas. As 174 lacunas
do vídeo 23 foram excluídas como `unlabeled`. Não houve linhas inválidas no
formato primário nem divergências de classe/coordenadas entre os formatos.
Os 17.466 arquivos auxiliares `.npy` registrados como `unexpected_filename`
foram apenas enumerados e ignorados, sem ler seus conteúdos.

A auditoria leu anotações e JPEGs para dimensões e hashes, sem decodificar os
pixels ou abrir MP4s. Não executou detector nem abriu fontes de validação ou
teste. A figura foi gerada somente dos CSVs derivados. Isso não verifica
completude do GT, correção biológica das classes, continuidade dos IDs ou
alinhamento JPEG–MP4 de toda a coleção.

| Procura no nível 2 | Local |
|---|---|
| Fundamentação, achados e decisão aprovada | [Tolerância espacial](../metodologia/TOLERANCIA_ESPACIAL.md) |
| Executor da auditoria | [analyze_annotation_geometry.py](../../script/project/test/analyze_annotation_geometry.py) |
| Executor da figura | [render_annotation_geometry.py](../../script/project/test/render_annotation_geometry.py) |
| Única referência dos comandos | [Geometria das anotações](../../script/README.md#geometria-das-anotacoes) |
| Contagens e estados por quadro | [per_frame_counts.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/per_frame_counts.csv) |
| Tamanhos e distâncias por vídeo/grupo | [per_video_geometry.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/per_video_geometry.csv) |
| Frações para 10, 15 e 20 px | [per_video_gates.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/per_video_gates.csv) |
| Lacunas e nomes auxiliares ignorados | [anomalies.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/anomalies.csv) |
| Resumo com agregação por vídeo | [summary.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/summary.json) |
| Inventário e hashes das entradas | [input_files.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/input_files.csv) |
| Proveniência da auditoria | [manifest.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/manifest.json) |
| Figura comparativa dos raios | [tolerancias_geometria.png](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/tolerancias_geometria.png) |
| Proveniência da figura | [figure_manifest.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/figure_manifest.json) |

Estado: **10 px como raio principal e 15/20 px como análises de sensibilidade
obrigatórias foram aprovados**, iguais para todos os detectores, na resolução
original de 640 × 480 px após desfazer redimensionamento e padding. É uma
convenção operacional para exigir localização mais precisa, não um raio ótimo
determinado pela geometria ou um padrão universal da literatura. A auditoria
não mediu incerteza dos anotadores nem usou F1 para selecionar esse raio. O
centro geométrico da caixa é referência operacional, não ponto anatômico exato.

A avaliação ativa se chama
**`center_distance_v3_individuals_ignore_clusters_10px`**, registrada em
`evaluation.protocol_id` de `configs/protocol/splits.yaml`. O contrato
`individuals_ignore_clusters` usa classes 0/2 como alvos e caixas de classe 1
como regiões potenciais de ignorados. O matching dos indivíduos vem primeiro;
predições restantes só podem ser ignoradas dentro dessas caixas e fora dos
discos de proteção dos indivíduos, inclusive dos já pareados. Duplicatas
próximas continuam FP. Todas as predições são candidatas, sem filtro por classe
prevista. A secundária `binary_all_objects` compara todos os objetos.

Os splits foram preservados. **`center_distance_v2_10px`** registra a etapa
anterior à política de agrupamentos; **`center_distance_v1_15px`** é a
referência histórica da avaliação a 15 px. Os YAMLs históricos T200/T190 e as
configurações congeladas mantêm seus valores. Não misturar métricas das
versões nem promover T200 no contrato novo a partir de resultados antigos.

### Auditoria dos agrupamentos e smoke inicial de engenharia concluídos

Nos 12 vídeos de treino há 5.413 anotações de agrupamento em 4.056 quadros,
distribuídas pelos vídeos 11, 12, 15 e 29. Há 4.250 centros individuais dentro
dessas regiões e 6.277 caixas individuais com interseção positiva; não remover
GT individual por estar dentro de um agrupamento. Zero quadros contêm somente
agrupamentos. Esses valores contam observações por quadro, não células únicas.

A união exata das caixas cobre em média 0,2869% da imagem, agregando todos
os quadros anotados e depois atribuindo peso igual aos 12 vídeos. Condicionada
a quadros com agrupamento, a média entre os quatro vídeos pertinentes é
1,1233%. A auditoria conferiu contagens e hashes anteriores, manteve as lacunas
excluídas e não executou detector. A figura usa somente os quatro primeiros
quadros com agrupamentos, selecionados deterministicamente no treino.

| Procura | Local |
|---|---|
| Avaliador v3 | [detection.py](../../src/evaluation/detection.py) |
| Configuração do contrato ativo | [splits.yaml](../../configs/protocol/splits.yaml) |
| Auditoria das regiões de agrupamento | [audit_cluster_regions.py](../../script/project/test/audit_cluster_regions.py) |
| Contagens e cobertura por vídeo | [per_video_clusters.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/per_video_clusters.csv) |
| Quadros com agrupamentos | [frames_with_clusters.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/frames_with_clusters.csv) |
| Exemplos selecionados e suas anotações | [selected_examples.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/selected_examples.csv) · [example_annotations.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/example_annotations.csv) |
| Resumo da auditoria | [summary.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/summary.json) |
| Entradas e proveniência | [input_files.csv](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/input_files.csv) · [manifest.json](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/manifest.json) |
| Figura com GT manual | [agrupamentos_primeiros_quadros.png](../../data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/agrupamentos_primeiros_quadros.png) |

**Estado:** nível 2 concluído. O smoke inicial de `42ced6b` revelou
arredondamento das coordenadas exportadas. O commit `6b0a1e9` corrigiu a
exportação e passou em 287 testes; os mesmos seis quadros foram repetidos
em novas runs, preservando as anteriores. A conferência independente aprovou
36 associações e 168 comparações espaciais a 1e-9 px, com diferença máxima
4,44 × 10⁻¹⁶ px. Configuração, contagens e oito hashes de entrada iguais.

Registro local: [verificação de precisão](../../data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/verification_20260907_full_precision.json).
O arquivo `verification_20260907.json` registra a descoberta inicial;
ambas as verificações e as quatro runs permanecem preservadas.

O smoke real executou os frames 0, 1 e 2 dos vídeos de treino 11 e 12, seis
frames ao todo. Ambos os manifestos estão completos e registram commit
`6b0a1e9`, `git_dirty: false` e avaliação v3. A 10 px, o vídeo 11 somou
106 TP/29 FP/23 FN; o vídeo 12 somou 73 TP/9 FP/10 FN. Foram zero predições
ignoradas, mesmo nos três frames com agrupamento do vídeo 12. Os casos
ignorados e ramos de quadros vazios são cobertos sinteticamente; não atribuir
essa cobertura ao smoke real.

| Smoke com precisão corrigida | Local |
|---|---|
| Configuração de engenharia, sem busca | [protocol_smoke_v3.yaml](../../configs/detection/threshold/protocol_smoke_v3.yaml) |
| Vídeo 11: manifesto e métricas por frame | [manifest.json](../../data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/20260907T232142422929Z__6b0a1e9__cfg6d44ac336151__srca58a6221de__s42/manifest.json) · [frame_metrics.csv](../../data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/20260907T232142422929Z__6b0a1e9__cfg6d44ac336151__srca58a6221de__s42/frame_metrics.csv) |
| Vídeo 12: manifesto e métricas por frame | [manifest.json](../../data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/20260907T232143290517Z__6b0a1e9__cfgff74f997d29b__srca58a6221de__s42/manifest.json) · [frame_metrics.csv](../../data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/20260907T232143290517Z__6b0a1e9__cfgff74f997d29b__srca58a6221de__s42/frame_metrics.csv) |

Não usar o F1 desses seis frames para estimar qualidade geral, criar ranking
ou escolher parâmetros. A etapa seguinte registrou o plano e iniciou as
verificações de custo, como descrito abaixo. Ainda não há promoção na v3.
Fontes e artefatos anteriores permanecem imutáveis; redistribuir vídeos em
folds não desfaz a exposição histórica do teste.

## 12. Estado atual: refinamento concluído e conferido — 08/09/2026

Registro do fechamento da busca grossa: `480491c`. Plano prospectivo em `9940337`, antes dos dados. A otimização de proveniência
em `3f73a52` passou em 442 testes da suíte curta. Benchmark inicial preservado:
131,7403 s, projeção 3.167,83 s acima do limite. Novo benchmark: 40,8452 s,
projeção 986,31 s dentro do mesmo limite. CSVs de detecções/GT idênticos nos
171 candidatos e métricas por quadro iguais exceto tempo. Não repetir a busca
por desconhecer esse histórico: ela foi concluída e conferida.

Busca grossa: **171 × 144 = 24.624 avaliações**, 291,32 s totais, Git limpo,
commit `3f73a52` e checagem final de código/ambiente aprovada. Top5 para
refinamento: T224/o0/c2 (F1 0,7753), T208/o0/c2, T224/o0/c1, T200/o1/c2,
T208/o1/c2. A avaliação é a v3 dos indivíduos a 10 px, com sensibilidades
15/20 px. É seleção no treino, sem promoção; não confundir com T200 histórica
congelada a 15 px. Validação, teste e folds não foram abertos nesta etapa.

A conferência independente aprovou 1.205 arquivos, 1.631.066 comparações
numéricas e 72 verificações SciPy em 12 casos predeterminados. Ela reconstrói
rankings e agregações; não certifica GT completo nem generalização.

| Para retomar | Abra |
|---|---|
| Plano prospectivo | [search_v3.yaml](../../configs/detection/threshold/search_v3.yaml) |
| Configuração operacional do refinamento concluído | [refinement_v3.yaml](../../configs/detection/threshold/refinement_v3.yaml) |
| Método e resultados detalhados | [BUSCA_THRESHOLD_V3.md](../metodologia/BUSCA_THRESHOLD_V3.md) |
| Comandos oficiais | [Busca v3](../../script/README.md#busca-threshold-v3) |
| Executor, amostra e classificação | [search.py](../../script/detection/test/threshold/search.py) · [detection_sample.py](../../src/experiments/detection_sample.py) · [detection_search.py](../../src/experiments/detection_search.py) |
| Integridade dos pais e candidatos herdados | [detection_refinement.py](../../src/experiments/detection_refinement.py) |
| Regressões do refinamento | [test_detection_refinement.py](../../tests/experiments/test_detection_refinement.py) · [test_threshold_refinement_cli.py](../../tests/detection/test_threshold_refinement_cli.py) |
| Proveniência compartilhada | [runs.py](../../src/experiments/runs.py) — RunSnapshot opt-in; demais runs mantêm comportamento anterior |
| Cache completo | [manifest.json](../../data/derived/detection/frame_samples/threshold_search_v3_20260908/manifest.json) |
| Novo benchmark | [manifest.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark/20260908T141314464252Z__3f73a52__cfgcbefe6ab9f8a__srceae1c32fd9__s42/manifest.json) |
| Busca completa | [manifest.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/manifest.json) · [ranking.csv](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/ranking.csv) · [shortlist.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42/shortlist.json) |
| Conferência independente | [verification_20260908.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/verification_20260908.json) |
| Comparação dos benchmarks | [benchmark_parity_20260908.json](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark/benchmark_parity_20260908.json) |
| Figura científica | [PNG](../../data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.png) · [SVG](../../data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.svg) |
| Plano herdado do refinamento | [117 candidatos](../../data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search/refinement_plan_20260908.json) |
| Benchmark específico do refinamento concluído | [manifest.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg10615a87/refinement_benchmark/20260908T145306368969Z__da057ef__cfg6ed5cd6a66dd__src3847d91dfb__s42/manifest.json) |
| Refinamento completo e duas finalistas | [manifest.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/manifest.json) · [ranking.csv](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/ranking.csv) · [finalists.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/20260908T145354693902Z__da057ef__cfge5e4d7fa737b__src3847d91dfb__s42/finalists.json) |
| Conferência independente do refinamento | [verification_20260908.json](../../data/tests/detection/threshold/threshold_refinement_v3_20260908_batch__cfg2ebedc67/refinement/verification_20260908.json) |
| Figura do refinamento | [PNG](../../data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.png) · [SVG](../../data/derived/detection/search_reports/threshold_refinement_v3_20260908/refinamento_threshold_treino.svg) |

O cache conserva 576 quadros (48 por vídeo de treino), com subconjuntos
aninhados de 144/12, 532.540.304 bytes, preparo em 19,285 s. Identidade:
`77ad9cbda76c03d61f3b28dd99520d0c1d6e285452929d847742bc6331473478`.
Não recriar a amostra para escolher outro conjunto de quadros. A seleção é
uniforme na lista de índices anotados, não no tempo onde há lacunas.

**Estado do refinamento: concluído e conferido, sem promoção.**
O executor e a configuração operacional foram
registrados em `da057ef` antes do benchmark novo. A suíte curta passou em
502 testes, em 95,97 s. O benchmark terminou os 117 candidatos e suas 1.404
avaliações, sem seleção, com Git limpo e proveniência conferida ao final.
Laço: 16,9821 s; cache: 6,1535 s; pais: 3,2060 s. A projeção de **1.639,6385 s**
ficou abaixo dos 4.800 s registrados e liberou a bateria completa. Os tempos
mostrados estão arredondados; o manifesto guarda a precisão original.
O executor já implementa os modos `refinement_benchmark` e `refine`,
reutilizando o detector, a avaliação e os formatos de saída existentes.
O primeiro modo usa os 12 quadros de benchmark do cache; o segundo usa
todos os 576 quadros do subconjunto `master`, sem somar métricas antigas.

Deduplicação dos cinco pais: 117 configurações × 576 quadros = 67.392
avaliações. T193–239/o0/c2, T209–239/o0/c1, T185–223/o1/c2; área 3–300,
kernel 3, polaridade e métrica inalteradas. A configuração operacional é
separada do plano-base: não modificar `search_v3.yaml` nem recriar o cache.

O benchmark prospectivo contém todos os 117 candidatos nos mesmos 12 quadros:
**1.404 avaliações**, sem classificação para seleção e com teto de 600 s.
A projeção soma os tempos de conferência do cache e dos pais a
`2 × 48 × tempo do laço do benchmark`. Só liberar o refinamento com projeção
**≤4.800 s**, mantendo o teto de **7.200 s**. Falha ou orçamento excedido
preserva a execução parcial e impede seleção. O benchmark da busca grossa
não autoriza esta etapa.

A bateria terminou as **67.392 avaliações**, sob o commit `da057ef`, em
**454,647241 s**, com pico amostrado de RAM de **140,77 MiB**. Os artefatos
dos candidatos somam **338.594.816 bytes**. Git limpo e código/ambiente
conferidos ao final; todas as 117 configurações entraram na classificação.

| Ordem no treino | Configuração | F1 macro a 10 px | Recall macro | MAE da contagem avaliada |
|---|---|---|---|---|
| 1 | T219/o0/c2 | 0,775790026345069 | 0,8520497783439963 | 4,255208333333333 |
| 2 | T218/o0/c2 | 0,7756341553985521 | 0,8526857946223801 | 4,237847222222222 |

Ambas usam abertura zero e dois fechamentos. A diferença de F1 é
**0,000155871**, cerca de **0,0156 ponto percentual**. É uma ordenação
descritiva na amostra usada para selecionar, com peso igual por vídeo;
não demonstra superioridade geral ou significância estatística.

A conferência independente da primeira execução aprovou **2.451 arquivos**,
**4.029.280 comparações de campos/valores** e **162 associações SciPy** em
casos predeterminados. A paridade dos cinco pais com a busca grossa cobriu
**720 pares configuração–quadro**, correspondentes aos mesmos **144 quadros
físicos**, com igualdade exceto tempo. Não são réplicas independentes.

O registro final dos resultados está no commit **`bd2d216`**. O executor,
o protocolo e as runs conservam o commit **`da057ef`**.

**Planejamento histórico ao concluir o refinamento:** o próximo marco era
preparar protocolo e executor robusto para validar as duas
finalistas nos quatro vídeos completos de validação. Não iniciar validação
ou teste sem a preparação e o protocolo correspondentes. Não repetir a
busca ou o refinamento encerrados. A regra usada na seleção do treino foi
F1 macro, recall, MAE de contagem e ID; registrar a regra de seleção e desempate
da validação antes de acessar seus dados. Não usar o antigo `batch_frames.py`
para executar esse plano. Validação e teste continuam sem nova execução;
folds não desfazem a exposição histórica do teste.

Pendências históricas de preparação, registradas antes da certificação do
executor de validação completa (resolvidas na seção 13):

| Ponto de entrada ou implementação | O que conferir antes dos dados de validação |
|---|---|
| [CLI por split](../../script/detection/test/run_split.py) → [orquestração por split](../../src/detection/split_runner.py) | Usar apenas as duas finalistas e os quatro vídeos completos de validação, preservando a separação do teste. |
| [Leitor de vídeo](../../src/detection/runner.py) | Distinguir fim esperado do vídeo de falha de leitura; impedir que uma interrupção seja registrada como avaliação integral. |
| [Leitor de GT](../../src/detection/io.py) | Rejeitar linhas malformadas com erro identificável, sem omissão silenciosa; manter ausência de anotação distinta de quadro anotado vazio. |
| [Pipeline de detecção](../../src/detection/pipeline.py) | Conferir completude das saídas e registrar seus hashes na proveniência final. |
| [Agregação e seleção da busca](../../src/experiments/detection_search.py) | Os utilitários exigem 12 vídeos e não atendem diretamente à validação com quatro; preparar agregação com peso igual por vídeo e regra prospectiva de desempate. |

Naquele momento, esses pontos eram pendências de revisão e implementação;
seu desfecho está na seção 13. A continuidade autônoma permanece válida após essas
garantias; não há nova exigência de confirmação a cada etapa.

O atlas e este guia são locais. Código/plano e registro de resultados recebem
commits; HTMLs, instruções de agentes e a monografia permanecem excluídos,
conforme preferência registrada. O método LaTeX recebeu o desenho da busca e
a ressalva correta sobre folds; o PDF ainda não foi recompilado.


## 13. Revisão geral e validação das duas finalistas — 08/09/2026

[Parecer de alinhamento](REVISAO_GERAL_20260908.md) e
[plano científico](../metodologia/VALIDACAO_THRESHOLD_V3.md).
A revisão basal conferiu 3.248 arquivos e 17.753 itens sem divergências;
502 testes passaram antes das novas implementações. Não exige reinício.

| Parte | Local |
|---|---|
| Plano imutável antes dos dados | [validation_v3.yaml](../../configs/detection/threshold/validation_v3.yaml) |
| Execução das oito runs | [validate.py](../../script/detection/test/threshold/validate.py) |
| GT explícito, inventário, hashes e identidade do vídeo | [strict_inputs.py](../../src/detection/strict_inputs.py) e [io.py](../../src/detection/io.py) |
| Decodificação integral e EOF adicional | [runner.py](../../src/detection/runner.py) com FullVideoInput obrigatório nesta bateria |
| Conferência por quadro dos CSVs | [validation_frame_checks.py](../../src/experiments/validation_frame_checks.py) |
| Pais, finalistas, agregação e seleção | [detection_validation.py](../../src/experiments/detection_validation.py) |
| Comandos oficiais | [script/README.md](../../script/README.md#validação-completa-dos-dois-finalistas-v3) |

Plano: T219/o0/c2 e T218/o0/c2; 14/19/36 com 1.470 quadros, 52 com
1.440. São 5.850 quadros por configuração e 11.700 avaliações. O dry-run
lê só metadados. A execução exige Git limpo e orçamento de 1.800 s, 2 GiB
de RSS/artefatos e 2.000 previsões por quadro, sem truncamento. Qualquer
falha invalida a seleção; preservar runs incompletas. Não usar a CLI de
split legada como atalho e não congelar automaticamente o resultado.

Os controles futuros da hipótese são janelas comuns, somente informação
até t, elegibilidade individual 0/2 e ADE de todos os passos 1..H. O teste
histórico já foi exposto; quatro vídeos limitam inferência. Folds exigem
seleção dentro dos treinos externos, sem alegar restauração de cegueira.


### Desfecho posterior à preparação

Run completa em `7f47afb`, Git limpo, após 824 testes. T218/o0/c2 foi
selecionada com F1 macro 0,658959; T219/o0/c2 teve 0,657819. Todas as
11.700 avaliações passaram na conferência independente: 46 arquivos,
1.772.878 comparações e 144 matchings. Bateria 166,657535 s/RSS 236,594 MiB.
Os dois erros iniciais do verificador estão preservados; as runs não mudaram.
Na conclusão daquela bateria não havia congelamento, teste ou fold. O
congelamento posterior, apenas para desenvolvimento, está na seção 14;
os resultados e hashes das runs de validação permanecem intactos.

Manifesto: `data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/manifest.json`.

Conferência aprovada: `data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/verification_20260908_retry2.json`.

Figura final: `data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/validacao_threshold_completa.png`.

O marco seguinte, agora registrado na seção 14, fixou o congelamento para
desenvolvimento e o contrato de trajetórias individuais. Não repetir a
validação, escolher novos limiares usando esses resultados ou abrir teste
e OOF sem desenho próprio. Código/custos continuam em `7f47afb`.


## 14. Nível 5 — congelamento para desenvolvimento e referência individual v1

**Estado: preparação concluída e conferida.** Código,
plano e run em `33d191d`, após 1.026 testes em 108,58 s; execução com Git
limpo. Esses testes verificam a implementação; as contagens abaixo descrevem
o derivado real, sem avaliação de modelos. T218/o0/c2
está fixada como linha de base de desenvolvimento sob a avaliação v3, a 10 px
com sensibilidades de 15/20 px. Esse escopo não demonstra a hipótese temporal
e não autoriza teste, folds ou aplicação. Um
[recibo com 46 hashes preservados](../../data/derived/project_audits/general_20260908/freeze_t218_development_20260908.json)
vincula o congelamento aos artefatos existentes, sem reescrever as runs.

| Responsabilidade | Caminho para retomar |
|---|---|
| Escopo e limites da baseline | [CONGELAMENTO_THRESHOLD_V3.md](../metodologia/CONGELAMENTO_THRESHOLD_V3.md) |
| Parâmetros fixados para desenvolvimento | [t218_o0_c2_v3.yaml](../../configs/frozen/detection/threshold/t218_o0_c2_v3.yaml) |
| Guarda executável de teste/folds e escopo | [protocol.py](../../src/experiments/protocol.py) |
| Contrato científico da referência individual | [TRAJETORIAS_INDIVIDUAIS_V1.md](../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md) |
| Plano prospectivo, treino e universo esperado | [individual_trajectories_v1.yaml](../../configs/protocol/individual_trajectories_v1.yaml) |
| Segmentação pura, sem I/O ou modelo | [ground_truth.py](../../src/prediction/ground_truth.py) |
| Preparação com proveniência e orçamento | [prepare_ground_truth.py](../../script/prediction/test/prepare_ground_truth.py) |
| Casos sintéticos de elegibilidade e causalidade do prefixo | [test_individual_ground_truth.py](../../tests/integration/test_individual_ground_truth.py) |
| Ponto único de comandos oficiais | [script/README.md](../../script/README.md#referência-de-trajetórias-individuais-do-treino) |

O YAML congelado permite `development/train`, `smoke/train` e `validation/val`.
A guarda recusa teste, folds, `all` e aplicação, inclusive tentativas de remover
o congelamento por override. Os YAMLs históricos T190/T200 mantêm seu contrato
original; não tratá-los como avaliação v3 ou atalho para confirmar T218.

A preparação abrange somente os 12 treinos: `11,12,13,15,21,22,23,29,30,35,60,82`.
O plano fixa 1.440 quadros para 35, 1.500 para 82 e 1.470 para os demais;
as 174 lacunas conhecidas do vídeo 23 foram preservadas como não anotadas.
Essas expectativas foram registradas antes da preparação.

Foram mantidas todas as observações 0/2, caixas, centros e IDs originais,
inclusive trechos curtos. Classe 0↔2 mantém continuidade; classe 1, ausência
do ID ou falta de anotação interrompe o segmento. `segment_id` descreve um
trecho contínuo sem renumerar a identidade biológica. Indivíduos explicitamente
anotados dentro de outro cluster continuam válidos; as classes 1 ficam fora
das observações individuais e continuam contabilizadas e preservadas no GT bruto.

Cada janela exige **20 posições de histórico + 10 futuras**, com **stride 1**.
A saída contém apenas índices e relata origens excluídas por futuro incompleto.
Não há interpolação, filtro por tamanho/velocidade, modelo ou uso de informação
futura como entrada. Essa referência não define automaticamente a política de
HOTA nem certifica causalidade de características de fluxo futuras.

Os derivados foram criados em run nova sem sobrescrita. A conferência
independente aprovou integridade, cobertura e reconciliação das contagens na
primeira execução. Nenhum detector, tracker, fluxo ou preditor foi executado;
a preparação leu hashes e labels somente do treino, sem decodificar pixels.
A conferência reconstruiu derivados sem reler fontes.

| Contagem da preparação | Total |
|---|---:|
| Quadros do universo / anotados / lacunas | 17.640 / 17.466 / 174 |
| Observações brutas / individuais / clusters | 368.487 / 363.074 / 5.413 |
| Segmentos / com janelas / sem janelas | 725 / 623 / 102 |
| Origens com histórico completo | 350.160 |
| Janelas com histórico e futuro completos | 343.776 |
| Origens excluídas por futuro incompleto | 6.384 |
| Origens sem histórico completo | 12.914 |

Reconciliação: `363.074 = 12.914 + 6.384 + 343.776`. Janelas sobrepostas,
segmentos e observações não são aquisições independentes; a unidade estatística
permanece o vídeo. Custo: **151,929874 s**, RSS amostrado **226,148 MiB** e
**146.913.962 bytes** de artefatos antes do manifesto.
Os 102 segmentos sem janelas preservam **1.231 observações**: 77 segmentos
contêm menos de 20 posições e 25 contêm entre 20 e 29.

| Artefato produzido | Caminho local |
|---|---|
| Manifesto da preparação | [manifest.json](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/manifest.json) |
| Resumo por vídeo e totais | [summary.json](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/summary.json) |
| Observações, GT bruto, segmentos, janelas e estado por quadro | [by_video/](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/by_video/) |
| Figura da cobertura e das exclusões | [PNG](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/trajetorias_individuais_treino.png) e [SVG](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/trajetorias_individuais_treino.svg) |
| Proveniência da figura | [manifest.json](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/manifest.json) |
| Conferência independente aprovada | [verification_20260908.json](../../data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/verification_20260908.json) |
| Revisão visual aprovada | [visual_review.json](../../data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/visual_review.json) |

A primeira conferência aprovou **86 arquivos (85 artefatos e manifesto)** e
**9.407.090 comparações**, em **26,3672 s**. SHA256 do relatório:
`f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9`;
do manifesto: `88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35`.
Consulte os [resultados científicos da preparação](../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md#resultados-da-preparação--08092026).

O passo posterior foi executado no nível 6, detalhado abaixo: consumir
esses índices comuns nos baselines, com entradas apenas até a origem e
`ADE_H` sobre **todos os passos 1..H**, mais `FDE_H` no passo H.
Esta preparação não gerou ADE/FDE; os resultados dos baselines e seu estado
de conferência estão no nível 6. A hipótese com fluxo ainda não foi avaliada.
O tratamento de identidade para HOTA precisa de contrato
próprio; a segmentação desta referência não o resolve automaticamente.

## 15. Nível 6 — baselines fixos concluídos e conferidos

**Estado: execução completa; conferência independente aprovada na primeira execução.**
Código e protocolo foram registrados em
`5289c93e448c7e571ea92f30de3a7f5cb2c0d611`, após 1.362 testes da suíte
completa selecionada em 144,75 s. A execução terminou com Git limpo e
reconferido, em **54,191753 s**. Os resultados abaixo são descritivos GT no treino.
A conferência independente e a revisão visual da figura passaram, com registros
separados. Não reiniciar a run ou reescrever seus artefatos.

| Responsabilidade | Caminho confirmado |
|---|---|
| Contrato científico prospectivo | [BASELINES_PREDICAO_V1.md](../metodologia/BASELINES_PREDICAO_V1.md) |
| Plano, métodos, pais fixados por hash e orçamento | [prediction_baselines_v1.yaml](../../configs/protocol/prediction_baselines_v1.yaml) |
| Entrada oficial sem overrides científicos | [evaluate_baselines.py](../../script/prediction/test/evaluate_baselines.py) |
| Coordenação, cobertura, agregação e proveniência | [prediction_baselines.py](../../src/experiments/prediction_baselines.py) |
| Consumo protegido das quatro tabelas, históricos e alvos separados | [reference.py](../../src/prediction/reference.py) |
| ADE/FDE densos em todos os passos | [dense_trajectory_metrics](../../src/prediction/metrics.py) |
| Testes do leitor, lote/métrica e executor | [test_prediction_reference.py](../../tests/experiments/test_prediction_reference.py), [test_dense_prediction_baselines.py](../../tests/integration/test_dense_prediction_baselines.py), [test_prediction_baselines.py](../../tests/experiments/test_prediction_baselines.py) |
| Ponto único de comandos oficiais | [script/README.md](../../script/README.md) |

Persistência repete `p(t)` em todos os dez passos. `cv_median5` utiliza
`p(t−5)..p(t)`: **seis posições e cinco diferenças**, com mediana separada de
dx/dy; extrapola `p(t)+h*v`. As outras 14 posições do histórico comum não entram
nessa estimativa. Esses parâmetros foram fixados antes dos resultados; não
buscar janela, estimador ou melhor configuração nesta bateria.

Ambas usaram **343.776 janelas dos 12 vídeos de treino**, sem novo filtro de
elegibilidade. Históricos float64 de forma `[N,20,2]` e alvos `[N,10,2]` ficam
separados; o preditor recebe somente históricos. O leitor confere hashes,
classes 0/2, IDs, lacunas, continuidade, índices e a ordem exata das janelas.
`window_keys_sha256` permite conferir o consumo completo, além de contagens e
unicidade. As causas `class_1` versus `id_absent` permanecem herdadas da
referência previamente auditada. Não reabrir fontes originais nem executar
detector, rastreador ou fluxo neste marco.

ADE_H é a média dos erros euclidianos de **todos os passos 1..H**; FDE_H usa
o passo H, para H=1/5/10. Relatar pixels e duração nominal H/FPS de cada vídeo;
as 20 posições históricas abrangem 19 intervalos. O FPS vem do contrato
exportado; não assumir 30 ou 50 FPS para todos os vídeos.

A agregação principal reúne todas as janelas de cada `(vídeo, ID original)`,
inclusive de vários segmentos; depois calcula média com peso igual entre
os IDs com janela do vídeo e entre os 12 vídeos. A média por janela dentro
do vídeo, seguida da média igual entre vídeos, é secundária. Fragmentação
não deve dar peso extra ao ID. Os dois métodos devem consumir exatamente as
mesmas janelas; falha não autoriza excluir registros difíceis.

A comparação é descritiva no treino, condicionada a futuro GT completo.
Não mede o desempenho da pipeline com T218/tracking, não testa a contribuição
do fluxo e não promove um método. Não haverá busca, ranking, p-valor ou IC.
Teste, folds e HOTA continuam exigindo contratos próprios.

### Resultados descritivos da execução — conferência independente aprovada

Há **606 IDs originais com janela entre 669 individuais**; os **63 sem janela**
permanecem contabilizados e não recebem erro zero. Cada método cobriu 343.776
janelas; as duas famílias de saídas somam 687.552 pares método/janela cada.

| Método | ADE/FDE H=1 (px) | ADE H=5 (px) | FDE H=5 (px) | ADE H=10 (px) | FDE H=10 (px) |
|---|---:|---:|---:|---:|---:|
| Persistência | 0,851447 | 2,308355 | 3,677067 | 3,890964 | 6,619751 |
| cv_median5 | 0,505077 | 1,670137 | 2,845992 | 3,137020 | 5,774373 |

A tabela usa a agregação principal: janelas → ID original → vídeo → média
igual entre 12 vídeos. Na agregação secundária por janela e vídeo, ADE/FDE
H=10 são 2,149073/3,667572 px para persistência e 1,685941/3,163498 px para
cv_median5. Os pesos diferentes respondem a perguntas diferentes. A melhora
macro não é uniforme por vídeo: cv_median5 tem ADE10 menor em **9/12** e FDE10
menor em **7/12**. Isso não constitui seleção de vencedor ou teste de hipótese.

Custo observado: **54,191753 s**, RSS amostrado **199,027 MiB** em **1.376
amostras**, **419.207.751 bytes** antes do manifesto e **419.292.960 bytes**
finais da run. Lotes de 512; os limites
prospectivos de 1.200 s, 2.048 MiB RSS e 3.072 MiB de artefatos continuam fixos.

| Evidência da execução | Caminho local |
|---|---|
| Manifesto, configuração resolvida e proveniência | [manifest.json](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/manifest.json) |
| Resumo completo e limites de interpretação | [summary.json](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/summary.json) |
| Métricas por vídeo / diferenças pareadas descritivas | [video_metrics.csv](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/video_metrics.csv) e [paired_video_metrics.csv](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/paired_video_metrics.csv) |
| Previsões e erros por janela, métricas por ID | [by_video/](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/by_video/) |
| Conferência independente aprovada na primeira execução | [verification_20260908.json](../../data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/verification_20260908.json) |
| Figura com pesos por ID e vídeo | [PNG](../../data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/baselines_predicao_treino.png) e [SVG](../../data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/baselines_predicao_treino.svg) |
| Dados, proveniência e revisão visual da figura | [figure_data.json](../../data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/figure_data.json), [manifest.json](../../data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/manifest.json) e [visual_review.json](../../data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/visual_review.json) |

SHA256 do manifesto: `fefb77906d3af9629c22a21b4c989f62d9f295f73f65708894c8672975fe2f2d`.
Hash das fontes: `f738122f1f98c19202014f584f9e4b3d45e549fe3245cadfd673ac2c94fbb0db`.

QA: **187 arquivos**, **34.749.527 comparações**, incluindo **18.572.544
numéricas**, em **180,6702972 s**. Maior diferença numérica:
`1,4210854715202004e-14`. Foram conferidas **687.552 linhas por família de
saída**, **6.875.520 posições futuras**, **13.751.040 coordenadas** e
**4.125.312 métricas de janela**. SHA256 do relatório:
`9bc9cd8beee29636470e747851e735ab481f23afcdd4b41ef36c7acf12550b69`.

**Sequência para retomar:** preservar runs e referência conferidas e preparar
contrato e smoke causal de Farnebäck. O histórico de 20 posições oferece
19 transições até t; fixar amostragem na origem, disponibilidade temporal,
hashes e exclusões em coorte comum antes de executar o smoke nos vídeos 11/12.
Nenhum fluxo foi medido nesta bateria. Teste, folds e avaliação com detecções/rastreamento
continuam exigindo os protocolos correspondentes; não extrapolar estes números
de históricos GT para a pipeline completa.

**Pontos concretos a fechar no próximo protocolo:** no legado, a linha t do
fluxo corresponde a t→t+1 e fica fora do histórico até t. O consumidor antigo
exige fluxo além do histórico e não certifica `flow_valid`, par ou hash.
O modo `future_flow_mode=observed` é oráculo e deve ser recusado pelo novo
consumidor. O cache permite fallback sem vídeo e NPZ sem hash fixado; a pipeline
pode interpretar falha de decodificação como conclusão. Fixar vínculo exato
da referência, vídeo/par, origem, validade e cobertura antes de abrir pixels.
A máscara atual é aplicada após a estimação; um anel espacial não representa
velocidade física do fluido. São lacunas de contrato para a próxima etapa,
não alterações já implementadas ou resultados de fluxo.

## 16. Fluxo causal — nível 7 concluído e conferido

Leia primeiro o [contrato e resultados](../metodologia/FLUXO_CAUSAL_V1.md).
O [plano fixo](../../configs/flow/farneback/causal_smoke_v1.yaml) foi registrado
antes dos pixels. Em t=19 só existem os pares 0→1..18→19. Cada vetor é amostrado
em p_s, com interpolação estrita em float64, não em p_(s+1). Ausência não é
zero; validade numérica não é acurácia. Os campos são movimento aparente.

| Tarefa | Caminho |
|---|---|
| Consumidor causal, índices, NPZ, validade, interpolação e diagnósticos | [src/flow/causal.py](../../src/flow/causal.py) |
| Históricos sem coordenadas futuras | [src/prediction/reference.py](../../src/prediction/reference.py), `history_batch_at_origin` |
| Orquestração estrita e recursos | [src/experiments/causal_flow_smoke.py](../../src/experiments/causal_flow_smoke.py) |
| CLI oficial e conferência independente | [causal_smoke.py](../../script/flow/test/causal_smoke.py) e [verify_causal_smoke.py](../../script/flow/test/verify_causal_smoke.py); comandos em [script/README.md](../../script/README.md) |
| Testes sintéticos | [núcleo](../../tests/integration/test_causal_flow.py), [executor](../../tests/experiments/test_causal_flow_smoke.py), [verificador](../../tests/experiments/test_causal_flow_verification.py) |
| Run completa e resumo | [manifest.json](../../data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/manifest.json), [summary.json](../../data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/summary.json), [by_video](../../data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/by_video) |
| Tentativa falha preservada / conferência aprovada | [primeira](../../data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/verification_20260909.json) / [segunda](../../data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/verification_20260909_retry1.json) |
| Figura e proveniência | [PNG](../../data/derived/flow/reports/farneback_causal_smoke_v1_20260909/smoke_fluxo_causal.png), [SVG](../../data/derived/flow/reports/farneback_causal_smoke_v1_20260909/smoke_fluxo_causal.svg), [provenance.json](../../data/derived/flow/reports/farneback_causal_smoke_v1_20260909/provenance.json) |

Manifesto SHA256: `fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98`.
QA SHA256: `b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652`.
Fontes do código da run:`3f9307153a3c7c661ba59b007e8d003b5cecdc6b93bec18f5cb32d12c243879b`.
Plano canônico:`f7e0afa345b3774127bb622a03ab21d1100dd9655dbd7bb0c6c3eaaa4f13708f`.

`frames/*.npy` guarda os cinzas observados; `pairs/*.npz` os dois sentidos e
validade; índices ligam conteúdo, vídeo, par e configuração por hash.
`selected_windows.csv` e `histories.csv` preservam a referência histórica;
`features.csv` traz 19 vetores por janela; `window_coverage.csv` guarda
ausências; `pair_metrics.csv` e `temporal_metrics.csv` guardam denominadores e
diagnósticos. Não confundir 68 janelas com68 réplicas independentes: são 2 vídeos.
O QA reconstrói a matemática dos derivados; não refaz decodificação/estimação.

O próximo contrato deverá fixar amostra e orçamento ampliados, política para
ausências e coorte comum, preditores equivalentes, ajuste/normalização no treino
correspondente, horizontes e agregação por ID/vídeo. Não selecionar amostras por
erro futuro. Registrar os critérios antes de novas extrações. Máscaras/anéis,
tracking/HOTA, RAFT e ablação aprendida continuam exigindo desenho próprio.


## 17. Fluxo compacto — nível 8a conferido, custo ampliado bloqueado

Comece pelo [contrato e resultado](../metodologia/FLUXO_COMPACTO_V1.md).
Este marco é benchmark de engenharia; não é a ablação do nível 8 inteiro.
O limite prospectivo de tempo ampliado foi excedido e permanece preservado.

| Procurar | Arquivo |
|---|---|
| Plano imutável: 12 treinos, prefixos 0..59, limites, coorte e projeção | [compact_benchmark_v1.yaml](../../configs/flow/farneback/compact_benchmark_v1.yaml) |
| Construção histórica sem retorno dos alvos | [reference.py](../../src/prediction/reference.py), `VideoReference.iter_history_batches` |
| Deduplicação, ligações, validade, cobertura e quatro vizinhos | [compact.py](../../src/flow/compact.py) |
| Produtor sequencial, retenção sentinela, recursos e projeção | [compact_flow_benchmark.py](../../src/experiments/compact_flow_benchmark.py) |
| Preditor causal float64 com cinco fluxos finais | [causal_constant_velocity.py](../../src/prediction/hybrid/causal_constant_velocity.py); somente testes sintéticos até aqui |
| CLI e conferência independente | [compact_benchmark.py](../../script/flow/test/compact_benchmark.py), [verify_compact_benchmark.py](../../script/flow/test/verify_compact_benchmark.py); comandos em [script/README.md](../../script/README.md) |
| Testes | [compactação](../../tests/integration/test_compact_flow.py), [preditor](../../tests/integration/test_causal_flow_prediction.py), [executor](../../tests/experiments/test_compact_flow_benchmark.py), [conferência](../../tests/experiments/test_compact_flow_verification.py) |
| Run e saídas | [manifesto](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/manifest.json), [summary](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/summary.json), [by_video](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/by_video) |
| QA aprovado na primeira tentativa | [verification_20260909.json](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/verification_20260909.json) |
| Figura | [PNG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.png), [SVG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.svg), [proveniência](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/provenance.json) |

`selected_windows.csv` guarda as janelas e chaves originais; `requests.csv`
as amostras distintas; `links.csv` liga cada janela a seus 19 identificadores.
`features.csv` guarda u/v, validade e motivo; `window_coverage.csv` guarda
contagens das 19 transições e das cinco usadas pelo preditor. `witnesses.npz`
preserva os quatro vizinhos de cada interpolação. `frame_index.json` e
`pair_index.json` ligam hashes e fontes; `frames/` e `checkpoints/` retêm
somente os sentinelas 0→1 e 58→59. `checkpoint_metrics.csv` descreve apenas
esses pares; não representa todos os 59 pares de cada prefixo.

Fora dos sentinelas, o hash não recompõe o campo descartado: o QA confere a
interpolação dos testemunhos e a procedência registrada, sem repetir o
estimador. Vetor numericamente válido não significa movimento verdadeiro.
O benchmark respeitou seus próprios tetos, mas a projeção ficou em 134,21 min
contra 120 min; não está liberada a extração completa. Próximo trabalho:
instrumentar o laço dominante, registrar ajuste e equivalência antes de novo
ensaio; depois registrar extração e ablação completas. Não mudar parâmetros
para melhorar o erro, não elevar orçamento retroativamente e não repetir
referência, baselines, smoke ou esta run encerrada.

A edição histórica de 09/09, ao concluir o nível 8a, tinha 15 capítulos, cinco figuras incorporadas e
915 links locais do relatório canônico conferidos. As interações passaram
em computador/celular; o atlas tem 245 links conferidos e não alarga a página
nessas telas. Alterações finais de contagem de arquivos e separador decimal
receberam conferência estática e visual direcionada; os controles interativos
permaneceram iguais. O LaTeX foi atualizado localmente, sem compilar PDF.
Evidências visuais: `tmp/tcc_report/qa_20260909_nivel8a/`.
Registro completo: [completion.json](../../data/derived/project_audits/general_20260909/compact_flow_level8a_completion_20260909/completion.json).
O HTML do nível 7 foi preservado byte a byte em
[snapshot anterior](../../data/derived/project_audits/general_20260909/compact_flow_level8a_report_20260909/level7_before_compact_5629f67773ad15e0.html).

## 18. Relatório ampliado — edição documental de 10/09/2026

O [relatório canônico](RELATORIO_COMPLETO_TCC.html) passou de 15 para 19
capítulos. O objetivo desta edição é permitir ao pesquisador acompanhar a
lógica e conferir suas fontes. O marco científico permanece o 8a de 09/09:
nenhuma nova execução de detector, tracker, fluxo ou preditor foi realizada
para compor o relatório. Os resultados de código/run continuam em `6110c44`,
documentados em `400cc2d`; essa edição não muda sua proveniência.

| Necessidade de leitura | Entrada |
|---|---|
| Escolher uma sequência de estudo e preparar explicações para a defesa | [Capítulo 2: roteiros e perguntas](RELATORIO_COMPLETO_TCC.html#guia-leitura) |
| Explicar entrada, mecanismo, saída e limite dos métodos implementados | [Capítulo 10: algoritmos](RELATORIO_COMPLETO_TCC.html#algoritmos-detalhados) |
| Acompanhar coordenadas, matching, segmentos, janelas, fluxo e erro | [Capítulo 11: exemplo numérico completo](RELATORIO_COMPLETO_TCC.html#exemplo-completo) |
| Entender F1, HOTA, IDF1, MOTA, ADE/FDE, fluxo, custo e inferência | [Capítulo 12: métricas](RELATORIO_COMPLETO_TCC.html#metricas-guia) |
| Experimentar F1, ADE/FDE, informação disponível e interpolação | [Capítulo 13: quatro laboratórios](RELATORIO_COMPLETO_TCC.html#laboratorio) |
| Encontrar implementações, executores, configurações e testes | [Capítulo 14: pastas](RELATORIO_COMPLETO_TCC.html#pastas) |
| Ler manifesto, janela, amostra e cobertura reais | [Capítulo 15: artefatos](RELATORIO_COMPLETO_TCC.html#ler-artefatos) |
| Entender o impedimento de custo e a sequência científica | [Capítulo 17: próximos passos](RELATORIO_COMPLETO_TCC.html#proximos) |

O exemplo completo e os quatro laboratórios são fictícios e identificados.
O capítulo 15 incorpora a primeira janela e a primeira amostra do treino 11
do benchmark concluído, com bytes e hashes autenticados; não são casos
selecionados por desempenho. A restrição causal é por janela: o produtor
processou 0..59 para várias origens, mas a janela em 19 usa somente pares que
terminam até 19. A revisão corrigiu também uma pendência histórica do nível 6
que ainda aparecia como próxima etapa na explicação das pastas.

Conferência final: 1.017 links locais e 79 destinos internos HTML no relatório;
248 links locais e 55 destinos internos no atlas, além dos atalhos da raiz.
São contagens de ocorrências, não arquivos únicos. Estrutura, identificadores
e funcionamento sem dependências remotas passaram. Referências externas são
links de leitura; sua disponibilidade HTTP não foi retestada nesta conferência.
As cinco figuras científicas permanecem incorporadas. Os 19 capítulos também
podem ser lidos sem JavaScript, com exemplos numéricos alternativos.

O navegador verificou os quatro laboratórios, busca, índice, detalhes,
aumento de texto, menu móvel, impressão e atalhos com âncora. A leitura em
1440 e 390 px não alargou o documento. Um corte detectado nas legendas do
novo diagrama móvel foi corrigido, com conferência direcionada posterior;
isso foi ajuste visual documental, sem alteração da matemática científica.
Não foi gerado PDF nem repetida a suíte experimental de 1.728 testes.

Componentes novos em `tmp/tcc_report/`: `reading_guide.html`,
`algorithms_deep.html`, `walkthrough.html`, `artifacts_guide.html`,
`lab_extensions.html`, `lab_extensions.js` e `report_extensions.py`.
O gerador é `build_report.py`; a autenticação dos recortes reais ocorre antes
de sua incorporação. HTML, CSS, JavaScript, figuras e metadados finais estão
no arquivo canônico, que continua utilizável sem esses componentes de edição.

QA: `tmp/tcc_report/qa_20260910_ampliado/`, com `static_checks.json`,
`browser_checks.json`, `final_targeted_checks.json` e `visual_review.json`.
O script `check_report_ampliado.py` confere HTML/links e os scripts
`qa_report_ampliado.cjs` / `qa_final_ampliado.cjs` verificam a apresentação.
A edição anterior e seus componentes foram preservados no
[inventário anterior](../../data/derived/project_audits/general_20260910/relatorio_ampliado_20260910/before_manifest.json).
O [recibo da edição](../../data/derived/project_audits/general_20260910/relatorio_ampliado_20260910/completion.json)
registra hashes finais, revisões e o estado documental do Git. HTMLs, guia,
instruções locais e evidências de apresentação continuam fora dos commits.

## 19. Comparação clássica e edição do relatório — 11/09/2026

A busca real acrescentou 43 configurações × 576 quadros ao estado científico.
Ela foi executada em `2547109` e conferida independentemente antes da leitura
do ranking. O relatório é uma síntese desses derivados; seu gerador não roda
novamente os detectores. As evidências científicas e próximos passos estão
na abertura deste guia e no
[protocolo comparativo](../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md).

| Para retomar | Arquivo |
|---|---|
| Conferir a grade executada | [YAML operacional v2](../../configs/detection/comparison/classical_v1_operational_v2.yaml) |
| Entender produtor e orçamento | [Biblioteca comparativa](../../src/experiments/classical_detection_comparison.py) |
| Executar ou conferir uma nova bateria compatível | [Comandos oficiais](../../script/README.md#comparacao-classicos-v1) |
| Conferir as associações exportadas | [QA independente SciPy](../../script/detection/test/verify_classical_comparison.py) |
| Ler resultados por família e vídeo | [Resumo autenticado](../../data/derived/detection/comparison_reports/classical_v1_20260911/summary.json) |
| Abrir a edição atual | [Resultados no relatório](RELATORIO_COMPLETO_TCC.html#comparacao-classicos-20260911) · [Resumo no atlas](mapa-tcc-didatico.html#comparacao-classicos-atual) |
| Conferir estrutura e links HTML | [QA estático](../../tmp/tcc_report/qa_20260911_classical_final_retry1/static_checks.json) |
| Conferir navegador e aparência | [QA navegador](../../tmp/tcc_report/qa_20260911_classical_final_retry1/browser_checks.json) · [Revisão visual](../../tmp/tcc_report/qa_20260911_classical_final_retry1/visual_review.json) |

Esta edição tem 19 capítulos, seis figuras e quatro laboratórios; cerca de
41 mil palavras. Foram conferidos 1.035 links locais no relatório e 263 no
atlas, além dos atalhos. A revisão cobriu computador/celular, tabelas com
rolagem horizontal, valores por vídeo, figura e próximos passos. O JavaScript
interativo permaneceu idêntico à edição anterior; suas baterias encerradas
não foram repetidas. Nenhum PDF foi gerado.

Os componentes da nova seção estão em
`tmp/tcc_report/classical_comparison_template.html` e `core.html`; a figura
é incorporada por `build_report.py`, com hashes de manifesto, QA, resumo e
figuras. `publish_classical_edition.py` e `classical_status_corrections.py`
foram ferramentas de edição usadas uma vez; **não são comandos de retomada
idempotentes**. Leia o HTML atual antes de editar e preserve o histórico.
`classical_results_artifacts.py` cria uma pasta nova e não deve ser executado
de novo sobre a saída existente. Os snapshots anteriores e as tentativas
de QA visual foram preservados. O primeiro erro de teste de rolagem foi uma
suposição sobre o elemento HTML do verificador, corrigida sem mudar a página.

## 21. Refinamento clássico e dataset YOLO — entradas e retomada

| Procurar | Abrir |
|---|---|
| Plano do refinamento | [Plano do refinamento](../../configs/detection/comparison/classical_refinement_v1.yaml) |
| Executor do refinamento | [Executor do refinamento](../../src/experiments/classical_detection_refinement.py) |
| CLI do refinamento | [CLI do refinamento](../../script/detection/test/refine_classical.py) |
| QA independente do refinamento | [QA independente do refinamento](../../script/detection/test/verify_classical_refinement.py) |
| Resultados e lógica do refinamento | [Resultados e lógica do refinamento](../metodologia/REFINAMENTO_CLASSICOS_V1.md) |
| Manifesto do refinamento | [Manifesto do refinamento](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json) |
| QA do refinamento | [QA do refinamento](../../data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json) |
| Figura e resumo autenticados | [Figura e resumo autenticados](../../data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json) |
| Plano do dataset YOLO | [Plano do dataset YOLO](../../configs/detection/yolo/dataset_v1.yaml) |
| Produtor do dataset | [Produtor do dataset](../../src/detection/yolo_dataset.py) |
| CLI de materialização | [CLI de materialização](../../script/detection/test/yolo/prepare_dataset.py) |
| Manifesto do dataset | [Manifesto do dataset](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json) |
| QA independente do dataset | [QA independente do dataset](../../data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json) |
| Contrato do dataset e clones consumidores | [Contrato do dataset e clones consumidores](../metodologia/DATASET_YOLO_V1.md) |
| Comandos oficiais | [Comandos oficiais](../../script/README.md) |

Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold.

O descriptor e os arquivos selados são somente referência autenticada para criar o clone consumidor. Este marco não treinou YOLO, não executou a validação completa dos novos detectores e não avaliou a hipótese de contribuição do fluxo. A seção 19 conserva a busca anterior; esta seção registra sua continuidade.


Notas preparatórias locais para o próximo marco: [classical_full_validation_design_v1.md](../../tmp/tcc_report/classical_full_validation_design_v1.md) · [yolo_training_design_v1.md](../../tmp/tcc_report/yolo_training_design_v1.md). São propostas de implementação, sem autorização executável por si mesmas; a nota clássica antecede a conclusão da run acima. O próximo contrato deve vincular as dez finalistas e os hashes agora conferidos.
