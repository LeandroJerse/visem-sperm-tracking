# Diário de Progresso — TCC VISEM

Registro simples e cronológico do que foi feito e testado. Entrada mais recente no topo.

## 2026-09-08 — amostra pronta; custo inicial exige otimização

- Plano e executor registrados em `9940337` antes da execução real.
- Cache concluído: 576 quadros (48 por vídeo de treino), com subconjuntos
  aninhados de 144 e 12 quadros, sem lacunas; 532.540.304 bytes, 19,29 s,
  RSS amostrado de 156,473 MiB. Nenhum vídeo de validação/teste foi processado.
- Benchmark completo: 171 candidatos × 12 quadros = 2.052 avaliações;
  laço de 131,7403 s, projeção de 3.167,83 s acima do limite de 1.200 s.
  Não foi produzido ranking nem iniciada a busca grossa.
- A análise dos custos e um perfil sintético localizaram consultas repetidas
  ao Git e ao ambiente como principal custo evitável. Revisão operacional:
  compartilhar a captura de proveniência na bateria e revalidar ao final,
  sem alterar plano, amostra, parâmetros, métricas ou orçamento.
- Artefatos iniciais preservados; novo benchmark dependerá de novo commit.
  Evidências e tempos no [registro da busca](../metodologia/BUSCA_THRESHOLD_V3.md).
- Captura compartilhada implementada, com conferência final de commit,
  Git limpo, código e ambiente antes da classificação. A suíte curta completa
  passou em **442 testes, 102,60 s**. Isso verifica software, não desempenho
  do detector. O benchmark completo será repetido sob o novo commit.

## 2026-09-08 — nível 3: plano prospectivo antes da busca

- Registrado o [plano de threshold v3](../metodologia/BUSCA_THRESHOLD_V3.md):
  171 combinações fixas, mesmos 12 quadros por vídeo de treino, sem abrir
  validação ou teste. Seleção por F1 macro entre vídeos; desempates por recall,
  MAE de contagem e identificador, sem usar tempo ou arredondamento.
- A amostra principal terá 48 quadros anotados por vídeo, com subconjuntos
  aninhados de 12 e um quadro. Cache de pixels decodificados do MP4 canônico,
  sem resize ou nova compressão, GT completo e hashes das entradas.
- Benchmark das 171 configurações em um quadro por vídeo mede custo. A busca
  depende de projeção até 1.200 s e tem teto operacional de 1.800 s. Falhas,
  universos incompletos ou orçamento excedido impedem a classificação.
- Refinamento previsto: cinco candidatos, limiares inteiros ±15, morfologia
  herdada, área fixa, até 155 configurações nos 48 quadros por vídeo. A sua
  execução e nova medição de custo ainda serão implementadas.
- Este registro antecede a preparação real da amostra, o benchmark e a busca.
  Não é resultado experimental nem promoção de configuração.
- A suíte curta completa passou em 423 testes (70,37 s) após a integração
  estável do cache, agregação por vídeo e executor. A revisão incluiu testes
  de integridade, ausência/duplicação de quadros e preservação de exportações
  interrompidas. Depois dos dois casos adicionais de falha/integridade,
  17 testes do executor e o teste de links passaram em 4,16 s. São 425 testes
  distintos verificados, sem contar a rechecagem como testes adicionais.

## 2026-09-07 — nível 2 concluído: métricas reconstruídas com precisão

- Correção de exportação registrada em `6b0a1e9`, após 287 testes aprovados.
  Repetidos os mesmos quadros 0, 1 e 2 dos vídeos de treino 11 e 12, com
  configuração e oito hashes de entrada iguais aos iniciais; nenhuma seleção.
- Duas novas runs completas, ambas com `git_dirty: false`. As duas runs
  iniciais de `42ced6b` e a verificação que revelou o arredondamento continuam
  preservadas. TP/FP/FN, contagens e métricas calculadas no processamento
  permaneceram iguais; o CSV agora permite reconstruir os erros espaciais.
- A conferência SciPy independente aprovou 36 associações e 168 comparações
  de erros espaciais, com tolerância absoluta 1e-9 px. Maior diferença:
  4,44 × 10⁻¹⁶ px. Registro local `verification_20260907_full_precision.json`
  em `data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/`.
- Esses seis quadros verificam implementação e reprodutibilidade. Não há
  promoção científica, estimativa da qualidade geral ou escolha de limiar.
  Zero previsões foram ignoradas nesse recorte; os casos ignorados e de
  fronteira permanecem cobertos pelos testes sintéticos.
- Próximo marco: nível 3, registrar amostragem, espaço de busca, orçamento e
  critérios de seleção antes da busca em treino. Validação, teste e folds
  não foram processados nesta etapa; a exposição histórica continua registrada.
- Mapa didático, guia de navegação, matriz, ficha e método LaTeX atualizados.
  A fonte acadêmica ainda aguarda compilação; os PDFs anteriores permanecem
  históricos. HTMLs e guias locais continuam fora dos commits.

> As entradas seguintes preservam a descoberta e a resolução do problema.

## 2026-09-07 — precisão dos CSVs: fechamento do nível 2 pendente

- A verificação independente confirmou as contagens TP/FP/FN dos seis
  frames do smoke inicial, mas identificou uma limitação de exportação:
  `detections.csv` arredondava os centros a duas casas decimais, enquanto
  `frame_metrics.csv` usava os valores originais. No frame 1 do vídeo 11,
  a reconstrução da soma das distâncias divergiu aproximadamente 0,0278 px.
- A exportação foi corrigida e recebeu seis testes de regressão adicionais.
  A suíte curta completa passou: **287 testes em 22,37 s**. A repetição dos
  mesmos frames 0–2 dos vídeos de treino 11/12 em novas runs ainda está
  pendente, assim como a conferência das métricas reconstruídas dos CSVs.
- O smoke inicial permanece concluído e seus artefatos são preservados.
  O nível 2 permanece aberto até essa conferência; não há busca, seleção
  ou promoção de algoritmo. O planejamento prospectivo de threshold virá
  depois, mantendo o raio e a política de classes já definidos.

> A entrada abaixo registra o estado anterior à conferência independente;
> a declaração de fechamento foi superada pela limitação de exportação.

## 2026-09-07 — smoke inicial: contrato v3 e execução real

- Contrato `center_distance_v3_individuals_ignore_clusters_10px` verificado
  estruturalmente e em smoke real. Na suíte curta, 280 testes de código
  passaram; a única falha de link foi corrigida. A rechecagem de 31 testes
  de configuração/documentação passou, completando a verificação dos 281
  testes da suíte, sem contar a rechecagem como testes adicionais.
- Executadas duas runs de engenharia com `protocol_smoke_v3.yaml`, usando
  somente os frames 0, 1 e 2 de cada vídeo de treino 11/12: **seis frames**.
  Ambos os manifestos registram `status: complete`, commit `42ced6b` e
  `git_dirty: false`. Não foram abertas fontes de validação ou teste.

| Vídeo | Predições | GT individual | GT agrupamentos | TP | FP | FN | Ignoradas |
|---|---:|---:|---:|---:|---:|---:|---:|
| 11 | 135 | 129 | 0 | 106 | 29 | 23 | 0 |
| 12 | 82 | 83 | 3 | 73 | 9 | 10 | 0 |

Contagens somadas nos três frames de cada vídeo, com raio principal de 10 px;
não representam células únicas. Métricas principais/secundárias e os três
raios foram exportados. O F1 desses seis frames é diagnóstico de engenharia,
não estimativa da qualidade geral ou comparação para escolher limiares.

- Nenhuma predição foi ignorada no smoke, inclusive no vídeo 12, que contém
  agrupamentos. Os casos com ignorados, duplicatas protegidas e quadros
  vazios/exclusivamente de agrupamentos estão cobertos pelos testes sintéticos;
  o smoke real não exercitou todos esses ramos.
- As duas runs ficam sob
  `data/tests/detection/threshold/protocol_smoke_t200_o1_c2_v3__cfg2aefee95/smoke/`:
  `20260907T230907692812Z__42ced6b__cfg6d44ac336151__src38fc0c5da3__s42` (11) e
  `20260907T230908566607Z__42ced6b__cfgff74f997d29b__src38fc0c5da3__s42` (12).
  Cada uma preserva manifestos, detecções, métricas por frame e resumo.
- **Nível 2 concluído como contrato e verificação de engenharia.** Não houve
  busca, seleção ou promoção de threshold na v3. T200 a 15 px e v2 continuam
  históricos. A próxima etapa é planejar a busca prospectiva de threshold,
  com raio e política de classes já definidos.

Configuração: [smoke de engenharia v3](../../configs/detection/threshold/protocol_smoke_v3.yaml).
Comandos: [guia oficial](../../script/README.md#threshold-etapa-atual).

> As entradas seguintes preservam o estado anterior à execução: o smoke
> então planejado e os testes ainda em curso não são pendências atuais.

## 2026-09-07 — nível 2: contrato v3 e auditoria dos agrupamentos

- O pesquisador autorizou a continuidade autônoma do desenvolvimento, com
  explicação das decisões e preservação da rastreabilidade. Os pedidos de
  autorização por etapa registrados anteriormente pertencem ao histórico.
- Auditoria de agrupamentos concluída somente no treino: 5.413 anotações
  de classe 1 em 4.056 quadros dos vídeos 11, 12, 15 e 29. Zero quadros
  contêm exclusivamente agrupamentos. Foram examinados os 17.466 quadros
  anotados, mantendo excluídas as 174 lacunas já registradas.
- Há 4.250 observações individuais com centro dentro de caixas de agrupamento
  e 6.277 caixas individuais com interseção de área positiva. São observações
  por quadro, não células únicas; a classe 0 responde pelos 4.250 centros.
- A cobertura foi calculada pela união geométrica exata dos retângulos,
  limitada à imagem. Média com peso igual dos 12 vídeos sobre todos os
  quadros anotados: 0,2869%. Média condicionada a quadros com agrupamentos,
  com peso igual entre os quatro vídeos pertinentes: 1,1233%. Não são
  segmentações nem estimativas da quantidade de células em agrupamentos.
- Artefatos separados em
  `data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_agrupamentos/`:
  CSVs por vídeo/quadro, exemplos determinísticos, inventário com hashes,
  resumo, manifesto e `agrupamentos_primeiros_quadros.png`. A figura mostra
  quatro JPEGs de treino com o GT manual. Os testes sintéticos da união e
  as conferências de hashes/contagens passaram; nenhum detector foi executado
  nesta auditoria, nem foram abertas fontes de validação ou teste.
- Contrato ativo: **`center_distance_v3_individuals_ignore_clusters_10px`**,
  política **`individuals_ignore_clusters`**, raio principal de 10 px e
  sensibilidades obrigatórias de 15/20 px na resolução original 640 × 480.
  Classes 0/2 são alvos individuais; agrupamentos delimitam regiões de
  ignorados. Primeiro ocorre o matching de todos os candidatos com os
  indivíduos. Uma predição restante só pode ser ignorada se estiver dentro
  de uma caixa de agrupamento e fora dos discos de proteção de todos os
  indivíduos, inclusive dos já pareados. Duplicatas próximas continuam FP.
- A classe prevista não filtra candidatos. A análise secundária
  `binary_all_objects` avalia todas as classes como objetos, sem ignorar
  agrupamentos. Contagens brutas, pontuadas e ignoradas ficam separadas.
- O avaliador v3 está implementado; os testes finais estão em curso.
  **Smoke real de engenharia planejado em três quadros dos vídeos 11/12,
  ainda não executado.** Não há promoção de threshold ou resultado novo
  de desempenho no protocolo v3. A versão v2 e T200 sob a avaliação antiga
  de 15 px permanecem históricos, sem recálculo ou sobrescrita.

Próximo marco: concluir os testes finais do contrato de avaliação e executar
o smoke de engenharia. Busca de limiares e avaliação científica dependem de
um desenho explícito; a exposição histórica do teste continua documentada.
Estado do código: [avaliador de detecção](../../src/evaluation/detection.py).

> As entradas abaixo preservam etapas anteriores: a aprovação do raio na v2,
> a proposta então pendente e os limites de autonomia vigentes em cada momento.

## 2026-09-07 — nível 2: aprovado raio principal de 10 px

- O pesquisador aprovou **10 px como raio principal**, com **15 e 20 px de
  sensibilidade obrigatória**, iguais para todos os detectores. A avaliação
  usa centros na resolução original de 640 × 480 px, desfazendo eventuais
  redimensionamento e padding antes de calcular distâncias.
- Registrada a versão **`center_distance_v2_10px`** para a nova avaliação,
  em `evaluation.protocol_id` de `configs/protocol/splits.yaml`, sem mudar
  os splits. **`center_distance_v1_15px`** é a referência histórica dos
  resultados anteriores a 15 px; o nome não foi inserido em manifestos antigos.
- O raio é uma convenção operacional de precisão de localização. Não foi
  demonstrado como ótimo, não estima o ruído dos anotadores e não transforma
  centros de caixas em ground truth anatômico exato.
- A documentação passa a distinguir a avaliação ativa dos YAMLs históricos
  T200/T190 e configurações congeladas, que preservam 15 px. Os resultados
  das duas versões não devem ser misturados como se usassem a mesma métrica.
- Os artefatos da auditoria, as fontes e as runs anteriores permanecem
  imutáveis. Esta decisão não executou detectores em vídeos reais, criou novos resultados científicos ou
  promoveu algoritmos; as entradas anteriores preservam o estado da discussão
  antes da aprovação.
- Alinhados os padrões do avaliador, runner, pipeline e bancadas de threshold
  e MOG2/KNN. Os oito `search.yaml` de detecção adotam a nova avaliação;
  parâmetros dos algoritmos e espaços de busca permanecem como estavam.
  Os novos comparativos de threshold usam a subpasta
  `frame_screening/center_distance_v2_10px/`, com raio, versão e sensibilidades
  registrados. A agregação por vídeo preserva os resultados dos três raios.
- Validação: **165 testes passaram** nos módulos de detecção, configuração,
  documentação e infraestrutura experimental. Foram usados casos sintéticos,
  incluindo distância de 12 px, fronteira inclusiva de 10 px, sensibilidades,
  agregação por vídeo e reprodução explícita da configuração histórica.
- Conferidos hashes de 19 arquivos preservados: YAMLs T190/T200 e congelados,
  artefatos locais e executores da auditoria. Divisões, folds e seeds mantidos.
  Atualizado o texto-fonte do método; o PDF acadêmico ainda requer compilação.

Decisão e justificativa: [Tolerância espacial](../metodologia/TOLERANCIA_ESPACIAL.md).
Próxima discussão: **política de classes e agrupamentos**, antes de debater
busca de limiares. Seleção e desenho da avaliação, inclusive folds, continuam
pendentes e não autorizam uma próxima execução automática.

> As entradas seguintes são históricas. Menções a raio ainda pendente ou
> configurações ativas em 15 px descrevem o momento anterior à aprovação acima.

## 2026-09-07 — nível 2: auditoria de geometria concluída, raio pendente

- Concluída a auditoria descritiva das anotações dos 12 vídeos de treino:
  17.466 quadros anotados e 368.487 observações válidas. São anotações por
  quadro, não células únicas ou amostras independentes.
- Excluídas 174 lacunas do vídeo 23 como `unlabeled`. Zero linhas inválidas
  no formato primário e zero divergências de classe/coordenadas entre os
  formatos comparados. Os 17.466 `.npy` enumerados como nomes inesperados
  foram ignorados; não são erros de anotação e seus conteúdos não foram lidos.
- Descritos tamanhos das caixas e proximidade entre centros por classe, nas
  classes 0/2 e em todas as classes. O resumo foi agregado primeiro por vídeo.
  A política de classes da nova avaliação continua em discussão.
- Em `all`, a média com peso igual por vídeo da fração com regiões de
  tolerância sobrepostas foi 7,38% a 10 px, 16,75% a 15 px e 26,84% a 20 px.
  A condição é distância entre centros menor que dois raios; essas frações
  descrevem geometria, não erros medidos de detecção ou tracking.
- Artefatos separados em
  `data/derived/detection/annotation_audit/retomada_20260907_nivel2/treino_geometria/`:
  CSVs, resumo, inventário com hashes e manifesto. A figura
  `tolerancias_geometria.png` deriva dos CSVs e tem `figure_manifest.json`
  próprio; o manifesto original da auditoria foi preservado.
- Não foram executados detectores nem abertas fontes de validação/teste.
  A leitura usou anotações e JPEGs para dimensões e hashes, sem decodificar
  pixels ou abrir MP4s. As fontes e runs anteriores foram preservadas.
- **Proposta pendente: 10 px principal e 15/20 px de sensibilidade. Ainda
  não aprovada.** É uma convenção operacional de precisão da localização,
  não um raio ótimo estimado, uma medida de incerteza dos anotadores ou uma
  escolha baseada em F1. As configurações continuam com 15 px principal;
  os resultados anteriores não foram recalculados ou promovidos.

Fundamentação, limites e fontes: [Tolerância espacial](../metodologia/TOLERANCIA_ESPACIAL.md).
Os comandos ficam exclusivamente no [guia oficial](../../script/README.md#geometria-das-anotacoes).
Próximo passo: discutir a proposta com o pesquisador antes de alterar a
avaliação. Busca de limiares, novo protocolo e desenho de folds continuam
pendentes; esta auditoria não restaura o desconhecimento histórico do teste.

## 2026-09-07 — retomada, nível 2: prioridade aos centros

- O pesquisador confirmou a compreensão da caixa anotada e de seu centro no
  exemplo do nível 1. A conferência continua limitada ao quadro 0 do vídeo 11;
  não certifica toda a coleção.
- Aprovada a localização dos centros como critério principal da avaliação da
  detecção. Tamanho e formato das caixas ficam como aspectos complementares.
- A tolerância espacial ainda não foi aprovada nesta retomada. Os valores
  existentes em `configs/protocol/splits.yaml` — 15 px como gate principal e
  10/20 px para sensibilidade — permanecem em discussão no nível 2.
- O novo protocolo de seleção/avaliação e a execução de limiares ainda não
  foram autorizados. Esta entrada registra uma decisão conceitual, sem
  alterar configurações, código, dados ou resultados.

Próximo passo: explicar o significado da tolerância espacial e revisar os
valores existentes com o pesquisador antes de decidir como aplicá-los.

## 2026-09-07 — retomada, nível 1: conferir o gabarito

- Autorizada a inspeção de um único quadro do vídeo de treino 11, antes de
  testar limiares. A etapa é entender imagem, caixas, centros, classes e IDs;
  o nível 1 permanece em revisão com o pesquisador.
- Preservados os vídeos, as anotações originais, as configurações e todos os
  resultados históricos. Não foram apagadas ou sobrescritas runs. Reiniciar
  o desenvolvimento não apaga a influência de observações anteriores sobre
  vídeos de teste, e não foi aprovado um novo protocolo de avaliação.
- Criada uma área própria de derivados:
  `data/derived/detection/annotation_audit/retomada_20260907_nivel1/video_11/frame_000000/`.
  Ela reúne quadro original decodificado, sobreposição de anotações, exemplo
  ampliado, tabela e manifesto, sem executar detector ou calcular seu
  desempenho. O comando fica no [guia oficial](../../script/README.md#inspecao-de-anotacoes).
- Conferidos somente `11_frame_0.txt` e `11_frame_0_with_ftid.txt`: 43 linhas
  em cada formato, todas da classe 0, com classes e coordenadas exatamente
  iguais na mesma ordem; o formato FTID contém 43 IDs únicos. O leitor
  existente retorna as mesmas caixas e preserva os IDs textuais.
- Na referência de imagem 640 × 480 px, nenhuma caixa ultrapassa os limites
  (tolerância de 10⁻⁹ px); uma caixa toca a borda direita. Classe 0 é um
  rótulo do dataset, não um diagnóstico clínico. Não há `cluster` ou
  `pinhead` anotados nesse quadro.
- A igualdade dos formatos não certifica completude do gabarito nem
  continuidade das identidades. Não foram inspecionados outros vídeos para
  esta conferência, promovidos algoritmos ou alterados métricas e splits.

Próximo passo: discutir a imagem e o significado de uma anotação com o
pesquisador. A definição da avaliação e da busca de parâmetros é uma etapa
posterior, que exige nova autorização.

## 2026-09-07 — correção da origem dos dados e do escopo

- Confirmado com o pesquisador o uso exclusivo dos vídeos VISEM e das
  anotações VISEM-Tracking, provenientes da mesma coleção: 20 vídeos com
  trechos anotados para desenvolvimento/avaliação e outros 65 sem tracking
  manual para aplicação posterior.
- Retirada do escopo a segunda coleção descrita como vídeos com
  contracorrente gerada por tubo. Os artigos de aquisição não documentam
  essa condição experimental. A deriva mencionada no VISEM original não
  demonstra sua causa nem implica contracorrente controlada.
- Mantida a hipótese principal de redução de ADE/FDE com características
  locais de fluxo e histórico de posições, comparadas a preditores
  equivalentes sem fluxo. Movimento aparente da imagem não equivale a
  velocidade física do fluido sem ground truth correspondente.
- Alinhados o protocolo, os documentos de navegação e o texto acadêmico local
  (resumo, abstract, introdução, fundamentação e método). A fonte LaTeX foi
  verificada estaticamente, mas ainda não recompilada por indisponibilidade de
  compilador neste ambiente. O PDF assinado e as entregas foram preservados.
- Esta revisão não executou experimentos, promoveu algoritmos nem alterou
  splits ou resultados.

Fontes primárias: [VISEM, 2019](https://doi.org/10.1145/3304109.3325814) e
[VISEM-Tracking, 2023](https://www.nature.com/articles/s41597-023-02173-4).
Descrição vigente: [escopo no protocolo](../metodologia/PROTOCOLO.md#escopo-dos-dados-e-interpretação-do-movimento).

## 2026-09-07 — navegação do projeto e auditoria de arquivos

- A entrada do projeto passou a priorizar o algoritmo threshold, a bancada
  frame a frame e os mapas das quatro tarefas.
- Documentados caminhos históricos e localização dos módulos nos guias
  técnicos para facilitar a retomada do desenvolvimento.
- Guias dos módulos e fichas científicas agora ligam implementação, YAML,
  comandos e resultados existentes. Exemplos duplicados/inconsistentes foram
  substituídos por links ao guia oficial `script/README.md`.
- Cabeçalhos de pacotes e executores curtos explicam a função de `__init__.py`
  e indicam a implementação chamada. Nenhuma mudança de código executável foi
  detectada na comparação sintática dos 163 Python antes/depois da organização.
- Centralizada a documentação de execução para evitar instruções duplicadas.
- A auditoria não justificou excluir arquivos-fonte ou configurações. Arquivos
  pequenos de pacote, interfaces e variantes compartilhadas têm uso real.
- Verificação focada: 19 testes de links e contratos dos executores aprovados.
  Nenhuma bateria científica foi executada nem etapa promovida.
Pendências de protocolo e a revisão do bloqueio de `--video` na bancada devem
ser discutidas antes de novas execuções.

> Entradas anteriores à reorganização de 2026-08-29 preservam nomes de caminhos
> históricos como evidência. Eles não são comandos vigentes. O mapa
> `data/manifests/layout_20260829.csv` traduz origem para destino; a estrutura
> atual está em `docs/projeto/MAPA_PROJETO.md` e `script/README.md`.

---

## 2026-08-29 — reorganização científica do repositório

**Arquitetura documental e acadêmica**

- Documentação separada em `docs/projeto/`, `docs/metodologia/`, `docs/dados/`,
  `docs/operacao/`, `docs/algoritmos/` e `docs/referencias/`.
- Criado um índice único em `docs/README.md` e um contrato explícito para
  `data/sources`, `manifests`, `datasets`, `derived`, `tests`, `results`,
  `models`, `catalog` e `quarantine`.
- PDFs de referência do VISEM foram centralizados em
  `docs/referencias/datasets/`, com links oficiais documentados.
- Entregas E2–E5 e o pacote-fonte da E2 foram preservados em
  `monografia/entregas/`; `monografia/` permanece a única fonte acadêmica.
- Após inventário e conferência das fontes canônicas, 149 documentos
  substituídos, renders, builds e duplicatas (30.199.294 bytes) foram removidos
  definitivamente. Dois PDFs potencialmente particulares permanecem isolados
  em `data/quarantine/unrelated_private_documents/` para revisão do
  proprietário; não foram abertos nem incorporados ao TCC.

**Threshold em validação completa**

- `T200/o1/c2` e `T190/o1/c1` foram executados nos vídeos `14, 19, 36, 52`.
- T200 obteve melhor F1 macro por vídeo e menor MAE de contagem; T190 obteve
  recall maior. T200 foi registrado e congelado, mas o teste bloqueado ainda
  não foi executado.

**Validação da reorganização**

- A migração registrou 2.623 operações verificadas; 544 entradas PNG idênticas
  foram deduplicadas em 60 imagens comuns, sem perder os 604 summaries de
  triagem frame a frame.
- Os `manifest.json`, `metadata.json` e demais JSONs históricos não foram
  reescritos: referências aos caminhos antigos continuam como evidência. A
  leitura canônica é resolvida por `src/core/relocation.py` a partir de
  `data/manifests/layout_20260829.csv`.
- O inventário final confirmou 85 vídeos VISEM, 20 anotados, 11 runs imutáveis
  existentes e ausência das raízes legadas `results/`, `output/`, `tmp/`,
  `data/raw/`, `data/tracked/`, `data/processed/` e `data/yolo/`.
- Preditores clássicos, aprendido e híbridos foram separados em nove módulos
  individuais, preservando a API pública e o registro de algoritmos.
- Tracking, fluxo, integração e predição passaram a exigir YAML promovido para
  runs congeladas, bloquear overrides científicos/amostrais e confrontar o
  `video_id` real dos artefatos com o split declarado. `application` também é
  um par exato entre stage e split.
- A triagem temporal de MOG2/KNN ganhou executor próprio: clipes distribuídos,
  reset por clipe, aquecimento mínimo de 100 frames totalmente excluído das
  métricas e F1 Húngaro binário a 15 px agregado primeiro por vídeo.
- A suíte completa terminou com **223 testes aprovados em 12,84 s**; 21 CLIs
  responderam `--help` e os validadores confirmaram splits disjuntos, cinco
  folds, lacunas, 85 vídeos, 20 conjuntos anotados, 11 runs e 2.623 movimentos
  de migração auditáveis. Nenhuma bateria longa nem vídeo do holdout foi aberto
  nessa validação estrutural.
- O SQLite canônico foi reconstruído com as mesmas 372.142 detecções, 7
  resumos, 85 linhas clínicas e 29.196 contagens GT do banco legado, além das
  tabelas de runs, métricas e custos. As 11/11 runs possuem ID e hash de
  configuração, e a auditoria encontrou 0 referências de artefato quebradas.
- O antigo tuning frame a frame expôs historicamente frames dos quatro vídeos
  hoje reservados ao holdout. Essa limitação permanece declarada; ela não é
  apagada pela reorganização nem autoriza reutilizar o holdout para selecionar
  parâmetros. O teste confirmatório da configuração congelada **não foi
  executado**.

---

## 2026-08-29 — retomada, organização e esqueleto experimental

**Dados e protocolo**

- Confirmados 85 vídeos VISEM: 20 com tracking manual para desenvolvimento e
  validação quantitativa; 65 sem tracking para aplicação posterior.
- Registrados split fixo 12/4/4, cinco folds OOF e seeds 42/123/2026.
- Inventariados 29.196 frames anotados e 502 clipes derivados; estes clipes não
  contam como amostras independentes.
- As 174 lacunas de labels do vídeo 23 são `unlabeled` e ficam fora de treino e
  métricas; não viram frames negativos.

**Organização e rastreabilidade**

- Fonte LaTeX mais nova copiada de `tmp/` para `monografia/` com hashes iguais.
- Criados mapa vivo, relatório por algoritmo, matriz de testes, protocolo,
  ambiente, comandos oficiais e fichas individuais em `docs/algoritmos/`.
- Criados manifestos de dados, YAMLs por método, esqueletos de
  `data/processed/` e `configs/frozen/` e runs que nunca sobrescrevem outra.
- Run registra config resolvida, seed, código/commit, ambiente, tempo, RAM/VRAM,
  hashes e artefatos; o SQLite consolida frame, par de frames, janela, vídeo e
  custos.

**Algoritmos implementados**

- Detecção: threshold fixo, Otsu, adaptativo, Blob, MOG2, KNN, Watershed, YOLO
  e híbrido CLAHE/correção de fundo/threshold.
- Tracking: centroide, Húngaro, SORT, ByteTrack-style e Adaptive Flow-SORT.
- Fluxo: Lucas–Kanade, Farneback, Horn–Schunck, RAFT lazy, híbrido robusto CPU
  e variante com refinamento RAFT.
- Predição: persistência, velocidade constante, Kalman, partículas, LSTM e
  variantes separadas com fluxo.
- Fechados os handoffs: detecção → tracking; cache mascarado de fluxo → tracking
  híbrido; cache → `tracks_with_flow.csv` → predição.
- Treino e avaliação YOLO agora usam runs imutáveis; `--resume` in-place foi
  bloqueado para preservar os pilotos.

**Validação curta concluída**

- `150 passed in 8.65s` na suíte sintética/estrutural.
- `compileall` aprovado para `src/` e `tests/`.
- `pip check`: nenhuma dependência quebrada no ambiente clássico/CPU.
- Validador: 20 vídeos, splits disjuntos, cinco folds, inventário 85 e lacunas
  consistentes.

**Pendente antes de resultados científicos**

- Fazer commit da infraestrutura e das configurações antes das runs finais.
- Executar as baterias longas VISEM na máquina do pesquisador, começando pelas
  duas finalistas de threshold nos vídeos 14, 19, 36 e 52.
- Validar o ambiente CUDA para YOLO/RAFT/LSTM e executar TrackEval para
  HOTA/IDF1/MOTA; nenhum wrapper estrutural substitui essas execuções reais.

---

## 2026-06-23

> **Entrada histórica.** O split 16/4, as métricas e os comandos abaixo
> pertencem ao piloto anterior ao protocolo 12/4/4. Não os use para a
> confirmação científica atual.

**Detecção — módulo completo**
- Baselines clássicos prontos: `threshold`, `blob`, `bgsub`, `watershed`.
- CLI `run_detection` e modo interativo (`interactive`) funcionando.
- Convenção do vídeo: verde = detecção do algoritmo · vermelho = ground truth.

**YOLO — detector moderno**
- `detect_yolo.py`: wrapper do Ultralytics; exige `--weights`.
- Corrigido o erro "YoloDetector requer --weights" no modo interativo: agora
  o menu detecta pesos de treinos anteriores, deixa informar o caminho, ou treinar na hora.

**Treino do YOLO (`train_yolo.py`)** — criado e testado:
- Split **por vídeo** (16 treino / 4 val) para não vazar frames quase-iguais.
- Gera `data/yolo/{train,val}.txt` + `visem.yaml`. 3 classes (sperm/cluster/small_or_pinhead).
- Flags: `--batch -1` (auto), `--cache disk`, `--max-frames-per-video`, `--resume`.
- ✅ Testado `--prepare-only` (29.196 frames) e smoke test de 1 época na GPU.

**GPU / CUDA** — habilitado:
- torch era CPU-only → reinstalado com CUDA (`cu128`).
- ✅ `torch.cuda.is_available() == True` — RTX 4070 Ti (12 GB) reconhecida.
- Treino completo (`--epochs 100 --batch -1 --cache disk --name visem_full`) iniciado;
  auto-batch escolheu 22, AMP ligado. Saída: `results/yolo/visem_full/weights/best.pt`.

**Infra**
- README, `requirements.txt` (+ultralytics), `.gitignore` (PDFs, `runs/`, `data/yolo/`).
- Testes de I/O de detecção (`tests/`).

---

## Como retomar aquele treino interrompido

O `--resume` in-place foi desativado na infraestrutura atual porque o
Ultralytics pode reabrir e alterar a pasta histórica. Se um `last.pt` ainda for
útil, passe-o como `--model` em uma **nova** run imutável; o piloto original
permanece preservado em
`data/tests/detection/yolo/pilot_100_epochs__cfglegacy/`.

## Próximos passos
- [ ] Concluir o treino completo do YOLO e avaliar (mAP50 / mAP50-95).
- [ ] Rodar detecção YOLO com o `best.pt` e comparar com os baselines clássicos.
- [ ] Módulo de fluxo óptico (`src/flow`): Farneback → RAFT.
- [ ] Rastreamento (`src/tracking`): SORT → ByteTrack.
- [ ] Predição (`src/prediction`): Kalman → LSTM.
