# Diário de Progresso — TCC VISEM

Registro simples e cronológico do que foi feito e testado. Entrada mais recente no topo.

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
