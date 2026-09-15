# AGENTS.md

<!-- refinement-dataset-completion-20260911 -->

Resultados documentados em `4c96da7693096a7d583efefe60acbbb5af5f6a2d`, com Git limpo ao concluir.
Esse commit documental não altera a proveniência das runs em `ca68f16`.
A edição local foi conferida: 19 capítulos, sete figuras e quatro laboratórios,
com QA estático, navegação e revisão visual. Registro da entrega:
`data/derived/project_audits/general_20260911/classical_refinement_edition/completion.json`.

## Continuidade vigente — refinamento e dataset conferidos em 11/09/2026

Refinamento concluído e conferido em `ca68f16`, com Git limpo na execução: **45 configurações × 576 quadros = 25.920 avaliações**, somente nos 12 treinos. A vizinhança previamente definida gerou 54 propostas, 51 válidas e 45 configurações únicas. Os dez pais passaram na paridade de objetos brutos e métricas; T218 permaneceu histórico, sem nova execução. Há dez finalistas, duas por família, sem promoção ou liberação automática da validação.

Bateria: 528,244100 s; RSS amostrado 410,406 MiB; 394.820.008 bytes dos artefatos das candidatas, excluindo o agregador. QA: 1.061 arquivos, 39.670.198 comparações, 26.831.879 numéricas e 155.520 matchings SciPy em 281,243874 s; diferença numérica máxima 0.

[Manifesto do refinamento](data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json) · [Resumo e resultados por vídeo](data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json).

SHA256 do manifesto: `0c686f61f51af3129b89e878ba60ce2067e15c8c3bcceb478eee074f5e407e6b`.
SHA256 do QA: `d82c58bff8d0ba8323ec1d43af23dc18f470c9da8f72c1c86d7aec14769f8118`.
Fontes da execução: `f2ecb55da1bf19ff1fd2247f0e196d30f064fc95fc399c6b465c805c219a8766`.

Dataset YOLO materializado e conferido em `ca68f16`: **23.316 pares JPEG/anotação**, sendo 17.466 de treino e 5.850 de validação; 174 lacunas de anotação excluídas. Preservadas as três classes e as caixas da referência FTID. O conjunto contém 491.729 observações anotadas, não indivíduos únicos. Foram copiados 46.632 arquivos e gerados três descritores.

Preparação: 1.237,798253 s; RSS amostrado 198,160 MiB; dataset com 1.471.015.512 bytes. QA: 116.590 arquivos, 8.724.385 comparações e 23.316 cópias JPEG decodificadas em 195,027052 s. A conferência verificou paridade de 491.729 anotações, com diferença máxima 0.

[Manifesto do dataset](data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json) · [Conferência independente](data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json). O teste ficou fora da preparação. **Não houve treinamento YOLO:** `training_allowed=false` e `consumer_clone_required=true`; o consumidor deve gerar outro clone independente dentro de sua própria run antes de chamar a biblioteca.

A paridade geométrica entre anotações YOLO e FTID não certifica igualdade de pixels entre JPEG e MP4. Os JPEGs servem ao treinamento e à validação nativa do modelo aprendido. Para comparar F1 v3 com os clássicos, YOLO deverá processar os mesmos quadros MP4/cache usados por eles, com pré-processamento explicitamente registrado. Essa distinção delimita o derivado e o futuro contrato de comparação; não representa falha na organização atual do dataset.

SHA256 do manifesto: `e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42`.
SHA256 do QA: `0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be`.

Próximo marco: registrar validação completa das dez finalistas nos quatro vídeos 14/19/36/52, 5.850 quadros por candidata, 40 runs e 58.500 avaliações novas; T218 só entra como referência histórica autenticada. Em paralelo, registrar receita e executor de treinamento YOLO usando clone do dataset selado. MOG2/KNN precisam de protocolo temporal; rastreadores terão comparação com HOTA e a predição exigirá trajetórias estimadas e ablação causal. Os baselines de ADE/FDE com trajetórias GT já estão concluídos e conferidos; isso não avalia a cadeia com trajetórias estimadas nem a contribuição do fluxo. Não há novo HOTA, ADE/FDE com fluxo, teste ou confirmação 5-fold.

Não repetir as baterias concluídas, não reescrever pais/runs ou YAMLs históricos e não entregar o dataset selado diretamente à biblioteca de treinamento. O commit do código/run é `ca68f16`; o commit documental final está registrado no início desta seção. HTMLs, guia local, instruções locais e monografia permanecem fora dos commits. Contagens editoriais de figuras/capítulos/laboratórios dependem da revisão própria do relatório e não são atestadas por este registro científico.

[Guia permanente, seção 21](docs/projeto/NAVEGACAO.md). Os registros de continuidade abaixo são históricos e conservam suas datas e proveniência.

Instruções para agentes de código que trabalham neste repositório.

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

## Navegação e retomada

Síntese didática completa atualizada em 11/09/2026 em
[docs/projeto/RELATORIO_COMPLETO_TCC.html](docs/projeto/RELATORIO_COMPLETO_TCC.html),
com atalho na raiz, 19 capítulos, seis figuras, quatro laboratórios e referências locais. Use-a para explicar a
lógica ao pesquisador; confira diário e manifestos para o estado científico.
A atualização do relatório usa derivados já conferidos. O benchmark compacto do
nível 8a foi executado separadamente; sua projeção excedeu o teto de tempo.
O próximo marco é refinar e validar os novos detectores, com preparação do YOLO em paralelo. Atualize o relatório quando esse
marco mudar, preservando sua distinção entre histórico, evidência e proposta.
O relatório, o atlas e os guias locais continuam fora dos commits.
A edição de 10/09 acrescenta roteiros de estudo, funcionamento dos algoritmos,
um exemplo numérico completo e leitura de artefatos reais autenticados.
A edição de 11/09 incorpora a busca comparativa concluída; o fluxo mantém o marco 8a de 09/09.
Consulte a seção 18 do guia para capítulos, componentes e QA desta edição.

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

Run do nível 7: `data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/manifest.json`.
QA: `data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/verification_20260909_retry1.json`.
Manifesto SHA256: `fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98`.
QA SHA256: `b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652`.
O novo consumidor causal e os hashes substituem o caminho legado somente
para esta nova cadeia. `future_flow_mode=observed` continua proibido.
A conferência não decodifica MP4 nem refaz Farnebäck; essa limitação permanece
explícita. Seção 16 do guia e bloco `fluxo-causal-nivel7` do atlas.

Marco anterior de 08/09/2026: **nível 6 concluído e conferido**.
Resultados científicos documentados em `b55490f616c926cc937215372c0e2436dcbd437a`,
com Git limpo ao concluir. A fonte LaTeX foi atualizada localmente, fora do Git.
Esse commit documental não muda a proveniência da run, do protocolo ou do código abaixo.
Protocolo e implementação foram registrados em
`5289c93e448c7e571ea92f30de3a7f5cb2c0d611`, após 1.362 testes da suíte
completa selecionada em 144,75 s. A bateria terminou em 54,191753 s, com Git
limpo e reconferido. A conferência independente passou na primeira execução:
187 arquivos, 34.749.527 comparações (18.572.544 numéricas), 180,6702972 s;
maior diferença numérica 1,4210854715202004e-14.
O contrato prospectivo está em `docs/metodologia/BASELINES_PREDICAO_V1.md`
e `configs/protocol/prediction_baselines_v1.yaml`; implementação em
`src/experiments/prediction_baselines.py`, entrada em
`script/prediction/test/evaluate_baselines.py`. O leitor protegido é
`src/prediction/reference.py`; `dense_trajectory_metrics`, em
`src/prediction/metrics.py`, calcula ADE sobre todos os passos 1..H.
Consulte a seção 15 do guia permanente e `predicao-baselines-nivel6` no atlas.
Persistência repete a última posição. `cv_median5` usa seis posições para
as cinco últimas diferenças, com mediana por componente, dentro do histórico
comum de 20 posições. Ambas usaram as mesmas 343.776 janelas GT dos 12 treinos,
com dez alvos futuros separados; métricas ADE/FDE em H=1/5/10, em pixels.
A agregação principal reúne janelas do mesmo ID original, inclusive seus
segmentos, depois dá peso igual aos IDs do vídeo e, por fim, aos 12 vídeos.
Parâmetros fixos, sem busca, seleção de vencedor, promoção, p-valor ou IC.
Este marco isola extrapolação com GT; não avalia a pipeline T218/tracker nem
a hipótese de contribuição do fluxo. A elegibilidade exige futuro completo.
As janelas representam 606 IDs originais com janela entre 669 individuais;
os 63 sem janela não receberam erro zero. Em H=10, ADE/FDE principais são
3,890964/6,619751 px para persistência e 3,137020/5,774373 px para cv_median5.
São resultados descritivos GT no treino: cv_median5 tem ADE10 menor em 9/12
vídeos e FDE10 menor em 7/12; não há superioridade uniforme nem promoção.
RSS amostrado 199,027 MiB (1.376 amostras), 419.207.751 bytes antes do manifesto
e 419.292.960 bytes finais da run.
Run: `data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42/manifest.json`.
SHA256 do manifesto: `fefb77906d3af9629c22a21b4c989f62d9f295f73f65708894c8672975fe2f2d`;
fontes: `f738122f1f98c19202014f584f9e4b3d45e549fe3245cadfd673ac2c94fbb0db`.
Figura e revisão visual aprovada em
`data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/`.
QA: `development/verification_20260908.json`, ao lado da pasta da run;
SHA256 `9bc9cd8beee29636470e747851e735ab481f23afcdd4b41ef36c7acf12550b69`.
A conferência reconstruiu 687.552 linhas por família de saída, 6.875.520
posições futuras, 13.751.040 coordenadas e 4.125.312 métricas de janela.
O próximo passo é preparar contrato e smoke causal de Farnebäck: histórico
de 20 posições permite 19 transições até t; explicitar amostragem na origem,
disponibilidade, hashes e exclusões em coorte comum antes do smoke 11/12.
Este marco não mediu fluxo. Não iniciar o smoke antes de seu protocolo;
não reiniciar a bateria nem repetir a preparação da referência.
Na retomada do fluxo, revisar os contratos legados antes de ler pixels: a
linha t representa t→t+1 e fica fora do histórico disponível até t; o consumidor
antigo exige fluxo além do histórico e não certifica validade/par/hash.
`future_flow_mode=observed` é oráculo e deve ser recusado pelo novo consumidor.
Eliminar ambiguidades de cache sem vídeo, vincular NPZ por hash e impedir que
falha de decodificação conte como execução completa. Fixar vínculo exato com
a referência, par, origem, validade e completude; a máscara atual atua depois
da estimação, e amostrar um anel não mede a velocidade física do fluido.

Marco anterior de 08/09/2026: **nível 5 concluído e conferido**.
Resultados documentados em `6ffe6c5`, com Git limpo ao concluir; código, plano
e run permanecem atribuídos a `33d191d`.
Código e plano foram registrados em `33d191d`, após 1.026 testes em 108,58 s.
A preparação real terminou em `33d191d`, com Git limpo: 17.640 quadros,
17.466 anotados e 174 lacunas; 368.487 observações brutas, 363.074 individuais
e 5.413 clusters. Foram preservados 725 segmentos (623 com janelas e 102 sem),
350.160 origens com histórico completo, 343.776 janelas e 6.384 origens sem
futuro completo; outras 12.914 origens não têm histórico completo.
São contagens do derivado, não células únicas nem desempenho de um preditor.
Tempo 151,929874 s, RSS amostrado 226,148 MiB e 146.913.962 bytes antes do manifesto.
Run: `data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation/20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42/manifest.json`.
O resumo e `by_video/` ficam ao lado. Figura PNG/SVG em
`data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/`.
A conferência independente passou na primeira execução: 86 arquivos (85
artefatos e manifesto), 9.407.090 comparações, 26,3672 s, sem reler fontes.
Relatório: `preparation/verification_20260908.json`, ao lado da pasta da run;
SHA256 `f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9`.
SHA256 do manifesto: `88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35`.
Os 102 segmentos sem janela guardam 1.231 observações (77 segmentos <20
posições e 25 com 20–29). Reconciliação: 363.074 = 12.914 + 6.384 + 343.776.
A preparação leu hashes e labels apenas do treino, sem decodificar pixels;
a conferência verificou derivados. `visual_review.json` da figura foi aprovado.
Ao concluir o nível 5, o próximo marco era consumir os índices nos baselines de
predição; a execução do nível 6 acima terminou e foi conferida independentemente.
O contrato de HOTA permanece próprio
e pendente; nenhum modelo foi executado nesta preparação.
T218/o0/c2 está congelado **para desenvolvimento**, no novo YAML
`configs/frozen/detection/threshold/t218_o0_c2_v3.yaml`. O recibo
`data/derived/project_audits/general_20260908/freeze_t218_development_20260908.json`
registra 46 hashes preservados. Não reescrever YAMLs T200/T190 ou runs anteriores.
A guarda executável em `src/experiments/protocol.py` mantém teste, folds, `all`
e aplicação bloqueados para esse congelamento de escopo `development_only`.
Ele permite apenas `development/train`, `smoke/train` e `validation/val`;
não equivale a confirmação independente nem libera o teste já exposto.

O plano `configs/protocol/individual_trajectories_v1.yaml`, o módulo puro
`src/prediction/ground_truth.py` e a CLI
`script/prediction/test/prepare_ground_truth.py` estão registrados para preparar
somente os 12 treinos. Consulte `docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md`
e `docs/metodologia/CONGELAMENTO_THRESHOLD_V3.md`, além da seção 14 do guia.
Preservar observações individuais 0/2 e IDs originais, todos os segmentos,
ausência de anotação distinta de quadro vazio e janelas de 20 posições de
histórico + 10 futuras, stride 1. Classe 0↔2 mantém continuidade; classe 1,
ausência do ID ou de anotação interrompe o segmento. Um indivíduo dentro da
caixa de outro cluster permanece válido. Não interpolar, filtrar por velocidade
ou geometria, nem usar futuros como pistas do preditor. Este marco não executa
detector, tracker, fluxo ou preditor; não calcular ADE/FDE como resultado dele.
Os 12 vídeos têm contagens registradas: 35 com 1.440 quadros, 82 com 1.500 e
os demais com 1.470; preservar as 174 lacunas registradas do vídeo 23.
Não confundir a preparação conferida com avaliação de preditores. Preservar
fontes e esta run, sem refazer a preparação já concluída. O futuro serve somente
ao alvo e à elegibilidade offline; não constitui informação disponível na origem.

Histórico anterior — conclusão da validação, antes do congelamento acima:

Marco de 08/09/2026 posterior ao refinamento: a revisão geral confirmou
alinhamento com o projeto assinado, conferiu 3.248 arquivos e 17.753 itens,
sem divergências. O commit `7f47afb` registra protocolo e executor estrito
de validação antes dos dados, após 824 testes (110 s). O plano está em
`configs/detection/threshold/validation_v3.yaml`; a CLI oficial é
`script/detection/test/threshold/validate.py`. Duas finalistas T219/o0/c2 e
T218/o0/c2, vídeos 14/19/36 com 1470 quadros e 52 com 1440: 11.700
avaliações em oito runs. Não confundir com execução do teste ou congelamento.
Bateria concluída em `7f47afb`: T218/o0/c2 selecionada (F1 macro
0,658959), sem congelamento, teste ou folds. QA aprovada em
`verification_20260908_retry2.json`: 46 arquivos, 1.772.878 comparações
e 144 matchings. As duas falhas iniciais do verificador estão preservadas.
Consulte a seção 13 do guia e o diário, sem repetir a bateria.
Os resultados foram documentados em `f308d08`, com Git limpo ao encerrar;
as runs e o código mantêm `7f47afb` como proveniência científica.
Os controles da hipótese incluem janelas comuns, informação apenas até t,
GT individual 0/2 e ADE 1..H; não estão resolvidos pela validação de threshold.

Comece pelo [guia permanente de navegação](docs/projeto/NAVEGACAO.md).
Ele liga cada tarefa às implementações, configurações, executores, testes e
artefatos, e registra os caminhos antigos que foram reorganizados.
O [README da raiz](README.md) é a entrada rápida para o pesquisador.

Em 07/09/2026, após a discussão de centros, raios e agrupamentos, o pesquisador
autorizou continuidade autônoma: perguntar apenas o necessário, explicar os
avanços, atualizar os HTMLs e registros e fazer commits. Essa autorização
substitui a exigência anterior de aprovação a cada etapa. Avance por etapas
verificáveis, com protocolo registrado antes de buscas, sem apagar fontes,
reescrever runs, simular independência do teste ou publicar resultados sem
evidência. HTMLs, guia local, instruções de agentes e arquivos que exponham
assistência de IA ficam fora dos commits, conforme preferência já registrada.

Histórico concluído em 07/09/2026 (nível 2): contrato de detecção v3 e auditorias
somente no treino. O smoke inicial de `42ced6b` revelou arredondamento de coordenadas;
o commit `6b0a1e9` corrigiu a exportação, passou em 287 testes e repetiu
os mesmos seis quadros (0–2 dos vídeos 11/12), com Git limpo em novas runs.
Conferência independente: 36 associações e 168 comparações espaciais a 1e-9 px
aprovadas. Fontes e runs iniciais preservadas.
Consulte o diário e `docs/metodologia/CLASSES_E_AGRUPAMENTOS.md` para evidências;
o smoke não promove o detector e não substitui avaliação em vídeos completos.

Estado de 08/09/2026: busca grossa v3 concluída e conferida; registro final em `480491c`. Plano em
`9940337` antes dos dados; otimização de proveniência em `3f73a52`, com
442 testes aprovados. Benchmark inicial preservado (projeção 3167,83 s),
segundo benchmark compatível com o mesmo orçamento (986,31 s); CSVs de
detecções/GT idênticos para 171 candidatos. Busca: 171 × 144 = 24.624 avaliações,
291,32 s, Git limpo e proveniência revalidada antes de classificar. Conferência
independente: 1205 arquivos, 1631066 comparações e 72 verificações SciPy.
Top5 no treino: T224/o0/c2, T208/o0/c2, T224/o0/c1, T200/o1/c2, T208/o1/c2;
primeiro F1 macro 0,7753 a 10 px. Nenhum método promovido na v3.

Refinamento concluído e conferido, sem promoção. Os resultados foram registrados
no commit `bd2d216`; código, protocolo e runs mantêm o commit `da057ef`. O executor
e a configuração operacional foram registrados em `da057ef` antes do novo
benchmark; 502 testes da suíte curta passaram em 95,97 s. O benchmark terminou
117/117 candidatos, 1.404 avaliações, laço de 16,9821 s. Conferência do cache:
6,1535 s; dos pais: 3,2060 s. Projeção de 1.639,6385 s abaixo do limite de
4.800 s, com Git limpo e proveniência final conferida. Esse custo liberou a
bateria completa, sem selecionar candidatos. A CLI
`script/detection/test/threshold/search.py` implementa `refinement_benchmark`
e `refine`, reutilizando a avaliação existente. Os pais e seus artefatos são
conferidos em `src/experiments/detection_refinement.py`. A configuração
operacional `configs/detection/threshold/refinement_v3.yaml` é separada do
plano-base imutável `search_v3.yaml`, cujo hash identifica o cache existente.
Benchmark prospectivo: 117 candidatos × 12 quadros = 1.404 avaliações, teto
600 s, sem seleção. Só liberar o refinamento se a projeção for ≤4800 s;
refinamento: 117 × 576 = 67.392 avaliações, 48 quadros por vídeo e teto 7200 s.
Área, kernel, polaridade e métrica foram preservados. A bateria completa
terminou 117/117 candidatos × 576 quadros = 67.392 avaliações, em 454,647241 s,
com pico amostrado de RAM de 140,77 MiB e 338.594.816 bytes de artefatos dos
candidatos. Commit de execução `da057ef`, Git limpo e proveniência revalidada.
Finalistas pela ordem registrada: T219/o0/c2, F1 macro 0,775790026345069, e
T218/o0/c2, 0,7756341553985521. Ambas sem abertura e com dois fechamentos.
Diferença de 0,000155871, cerca de 0,0156 ponto percentual: não declarar
superioridade geral ou significância a partir da seleção no treino.
Conferência independente aprovada na primeira execução: 2.451 arquivos,
4.029.280 comparações de campos/valores e 162 associações SciPy. A paridade
dos cinco pais cobriu 720 pares configuração–quadro, correspondentes aos
mesmos 144 quadros físicos, com igualdade exceto tempo. Não são 720 réplicas.
Não repetir o refinamento encerrado nem usar o batch_frames.py histórico.
Guia seção 12 e atlas bloco
`busca-threshold-v3` ligam planos, cache, runs, conferência e figuras. Não
repetir busca grossa já encerrada nem confundir a shortlist com congelamento.
Na conclusão do refinamento, o próximo marco era preparar protocolo e executor
robusto para as duas finalistas nos quatro vídeos completos de validação.
Essas pendências foram resolvidas no nível 4, registrado acima e na seção 13
do guia. A afirmação de que validação e teste não haviam sido reabertos se
refere àquela etapa de treino. Não repetir as baterias concluídas; o marco
atual é o marco 8a descrito no início. Fontes e todas as runs preservadas.

## Objetivo

Este TCC da UFU compara algoritmos clássicos, aprendidos e híbridos para:

1. detectar espermatozoides em vídeos microscópicos;
2. manter IDs ao longo dos frames;
3. estimar movimento aparente por fluxo óptico;
4. prever trajetórias futuras a partir de posição, histórico e fluxo.

O fluxo óptico não deve ser descrito como velocidade física do fluido sem um
ground truth físico correspondente.

## Arquitetura do repositório

```text
data/
  sources/       fontes externas imutáveis
  manifests/     inventário, hashes, splits, folds e lacunas
  datasets/      definições derivadas de datasets
  derived/       intermediários recriáveis
  tests/         execuções experimentais por tarefa/algoritmo/configuração
  results/       configurações promovidas, teste final e aplicação
  models/        pesos externos ou exportados
  catalog/       banco SQLite analítico derivado
  quarantine/    material fora do fluxo ativo, pendente de revisão manual
src/             biblioteca importável
script/          CLIs e lotes, por tarefa e por test/application
tests/           testes automatizados do código
configs/         espaços de busca e configurações congeladas
docs/            documentação científica e operacional
monografia/      LaTeX oficial e entregas acadêmicas
```

Dentro de `src/<tarefa>/`, preserve a distinção entre `classical/`, `modern/`,
`hybrid/` e `learned/` quando ela existir. Código reutilizável pertence a `src/`; seleção
de parâmetros e orquestração pertencem a `script/`; asserts automatizados
pertencem a `tests/`; CSVs, vídeos e métricas pertencem a `data/`.

Comandos oficiais e pontos de entrada devem ser documentados em
[`script/README.md`](script/README.md), não duplicados aqui.

## Dados e protocolo

- Existem 20 vídeos anotados para desenvolvimento e avaliação quantitativa e
  65 vídeos sem tracking manual para aplicação posterior.
- Split fixo: treino `11,12,13,15,21,22,23,29,30,35,60,82`; validação
  `14,19,36,52`; teste bloqueado `24,38,47,54`.
- O vídeo 23 possui lacunas de anotação. Alinhe GT pelo número do frame no nome
  do arquivo e exclua `unlabeled`; não converta ausência de arquivo em negativo.
- Clipes derivados não são amostras independentes.
- A unidade estatística é o vídeo. Agregue frames/trajetórias e seeds dentro do
  vídeo antes dos testes pareados.
- Cada algoritmo passa por smoke, busca em treino, refinamento, validação
  completa, congelamento, teste isolado e confirmação 5-fold.
- Nunca leia o teste para escolher hiperparâmetros.
- O piloto histórico já expôs os quatro vídeos do teste. Preservar seu bloqueio
  agora não restaura cegueira. Cinco folds exigem desenho de seleção e avaliação;
  repetir uma configuração já escolhida em cinco grupos não corrige exposição.

## Contratos dos módulos

```text
detecção → detections.csv/frame_metrics.csv
tracking → tracks.csv/tracks_mot.txt
fluxo    → cache por par de frames + índice
predição → predictions.csv/window_metrics.csv
```

Tracking deve receber chamadas inclusive em frames anotados vazios. MOG2/KNN
devem reiniciar por vídeo e excluir aquecimento. Ausência de fluxo é inválida,
não vetor zero. Janelas de predição não podem cruzar vídeo, ID, split ou lacuna.

## Métricas principais

- Detecção: avaliação `center_distance_v3_individuals_ignore_clusters_10px`,
  F1 dos indivíduos 0/2 por matching Húngaro a 10 px, sensibilidades 15/20.
  Previsões residuais a até um raio de qualquer indivíduo são FP; das demais,
  ignorar somente centros dentro de GT cluster. Preservar indivíduos no cluster,
  todas as previsões e GT brutos; nunca fornecer máscara GT ao detector/tracker.
  Relatar contagens ignoradas e `secondary_all_objects_*`; regra completa em
  `docs/metodologia/CLASSES_E_AGRUPAMENTOS.md`.
  YAMLs nomeados T190/T200 e congelados a 15 px permanecem históricos e não
  devem ser reescritos para simular avaliação pela nova regra.
- Tracking: HOTA oficial; IDF1, MOTA, trocas de ID e fragmentações complementam.
- Fluxo real: fotometria pós-warp, consistência forward/backward, estabilidade e
  custo; EPE apenas onde o deslocamento verdadeiro é conhecido.
- Predição: ADE e FDE nos horizontes definidos.

Comparações finais usam testes pareados por vídeo e fronteira de Pareto, sem
placar ponderado subjetivo.

## Regras de manutenção

- Não altere arquivos de `data/sources/`; derivados devem ser recriáveis.
- Preserve mudanças do usuário e não sobrescreva runs.
- Não coloque o único exemplar de código em notebook.
- Toda run científica registra configuração resolvida, seed, commit, estado do
  Git, versões, hardware, tempo, RAM/VRAM e caminhos dos artefatos.
- Atualize a ficha em `docs/algoritmos/`, a matriz e o diário quando uma etapa
  for promovida.
- Fonte acadêmica oficial fica em `monografia/`, nunca em `tmp/`.

## Tecnologia

Python 3.11–3.13, OpenCV, NumPy/SciPy, scikit-image, PyTorch/torchvision,
Ultralytics e ferramentas de avaliação MOT. O perfil clássico pode usar
OpenCV headless; YOLO, RAFT e LSTM exigem um ambiente PyTorch/CUDA validado
para as baterias práticas.
