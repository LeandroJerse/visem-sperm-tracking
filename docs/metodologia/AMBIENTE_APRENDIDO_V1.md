# Ambiente aprendido v1 — CUDA, YOLO, RAFT e LSTM

## Escopo

O ambiente `.venv-ml/` é separado da `.venv/` clássica. A preparação instala
dependências para os modelos aprendidos e verifica sua execução na GPU.
Não utiliza vídeos, labels, splits ou pesos externos; não mede detecção,
rastreamento ou previsão no VISEM. Passar nesta verificação não promove um
algoritmo nem substitui seu protocolo de treinamento e avaliação.

O perfil é Windows x64, Python 3.13 e CUDA 12.8. PyTorch `2.9.1+cu128`
e torchvision `0.24.1+cu128` formam o par publicado na documentação oficial
de [versões do PyTorch](https://pytorch.org/get-started/previous-versions/).
A escolha fixa uma versão estável compatível; não exige a versão mais recente.
O pacote Ultralytics foi fixado em `8.4.147`, obtido do índice oficial PyPI.
A [instalação oficial](https://docs.ultralytics.com/quickstart/) orienta
preparar PyTorch de acordo com sistema e CUDA antes do pacote de detecção.
Fontes consultadas em 11/09/2026.

O arquivo [requirements-ml.lock](../../requirements-ml.lock) registra as
versões diretas e transitivas instaladas, incluindo os sufixos CUDA. Os
relatórios locais de instalação registram URLs e SHA256 das distribuições
baixadas. O lock fixa versões, mas não substitui esses hashes de origem.
O perfil contém somente `opencv-python`: não instalar simultaneamente a
distribuição headless neste mesmo ambiente. A `.venv/` conserva seu próprio
OpenCV e suas versões históricas.

## Verificação sintética

Entrada oficial: `script/project/test/validate_learned_environment.py`;
comandos de criação, instalação e execução em [script/README.md](../../script/README.md).
O executor confere cada versão do lock, executa `pip check` e exige CUDA.
Não aceita fallback CPU como aprovação. Cada recibo recebe um nome próprio
e criação exclusiva: uma tentativa anterior não é sobrescrita.

As conexões de rede são desabilitadas durante importações e verificações;
caches de bibliotecas são direcionados ao ambiente isolado. Os testes usam
seed 42 e executam, nesta ordem:

1. Multiplicação de matrizes CUDA com resultado conhecido.
2. NMS de torchvision em CUDA, com caixas e índices esperados conhecidos.
3. Wrapper RAFT do repositório, variante small com `weights=None`, em um par
   sintético 128×128. Conferem forma, validade e finitude; não calculam EPE.
4. Arquitetura YOLOv8n construída a partir do YAML instalado, três classes e
   pesos aleatórios, com tensor 1×3×128×128. Conferem forma e finitude da
   saída bruta. Isso não valida o wrapper de pesos treinados do repositório,
   o pós-processamento completo ou a qualidade de detecção.
5. Arquitetura LSTM do repositório sem e com fluxo, entrada de 19 transições,
   saída de dez passos, forward e backward finitos. Não há passo do
   otimizador nem treinamento em observações. Os números de parâmetros são
   registrados separadamente: adicionar entradas de fluxo aumenta a
   capacidade, condição a controlar na futura ablação científica.

`weights=None` constrói RAFT sem pesos pré-treinados, opção descrita pela
[API torchvision](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.optical_flow.raft_small.html).
Esses vetores aleatórios não são resultados científicos de fluxo.

## Proveniência e limites

O JSON guarda versões, dispositivo, driver, capacidade CUDA, memória total,
memória alocada e reservada pelo PyTorch, memória do processo, seed, duração,
commit/estado do Git e hashes do lock, verificador e wrappers utilizados.
Não confundir o pico de alocação do PyTorch com toda a VRAM do processo ou
com certificação de um lote de treinamento. O pequeno tensor de smoke não
garante que vídeos completos ou lotes de produção caibam na GPU.

O ambiente habilita o próximo smoke de cada método. Antes de experimentos
reais, registrar arquitetura/pesos e seus hashes, treinamento permitido,
resolução, batch, política de precisão, memória, normalização, seeds e
critérios de validação. RAFT aprendido exige pesos externos documentados;
YOLO precisa de treinamento no protocolo atual; LSTM precisa de controle de
entradas causais e capacidade. Nenhuma dessas etapas é concluída apenas
pela instalação do ambiente.

## Resultado de engenharia — 11/09/2026

### Preparação necessária para o primeiro treinamento YOLO

A revisão do caminho existente encontrou ajustes necessários além do ambiente:

- `src/detection/yolo_training.py::build_dataset` aponta listas para fontes;
  a biblioteca pode escrever `labels.cache`, caches de imagens e reparos de
  JPEG junto a elas. Materializar cópias independentes autenticadas em
  `data/datasets/yolo/`, sem hardlinks, antes do treino. O descritor consumido
  não deve apontar para `data/sources/` nem conter uma entrada de teste.
- Vincular split, imagens e labels aos hashes e universos oficiais. Contagens
  esperadas: 17.466 quadros anotados de treino e 5.850 de validação; as 174
  lacunas do vídeo 23 não são negativos. Os labels YOLO têm cinco campos;
  `labels_ftid`, com identidades, pertence à avaliação de trajetórias.
- `_training_kwargs` não repassa toda opção atualmente aceita pelo resolvedor.
  Registrar uma lista explícita de opções admitidas, rejeitar desconhecidas e
  guardar argumentos efetivamente enviados, incluindo otimizador, precisão,
  augmentations, batch, workers, seed e política de checkpoint.
- Na versão instalada, `best.pt` é escolhido por mAP50–95. Não descrevê-lo
  como melhor F1 de centros. Escolha de época e seleção do detector são
  decisões distintas, a fixar antes de observar desempenho real.
- Para ByteTrack, preservar scores e caixas com piso de confiança compatível
  com o menor `low_threshold` prospectivo. O wrapper conserva scores, mas
  seu corte padrão 0,25 descarta previsões que poderiam servir à recuperação
  de baixa confiança. Fixar também NMS, `max_det` e precisão.

Essas constatações vieram de leitura do código local e da versão instalada;
não foram executados treinamentos ou avaliações de qualidade nessa revisão.
O próximo contrato deverá prever smoke nos treinos 11/12 antes da receita
completa, pesos de origem autenticada e seeds agregadas dentro de cada vídeo.
O uso da validação para escolher checkpoint/configuração deve permanecer
explícito: esse conjunto não fornece uma estimativa independente de desempenho.

### Evidência do ambiente

A primeira validação passou nos seis checks, em **12,0624322 s**, com
55 distribuições fixadas e `pip check` aprovado. Dispositivo: NVIDIA
GeForce RTX 4070 Ti, driver 596.36, compute capability 8.9, 12.282 MiB de
VRAM reportada. CUDA de runtime 12.8 e cuDNN 91002. O pico de alocação
PyTorch foi 25,80078125 MiB, o pico reservado 42 MiB e o pico de working set
do processo no Windows 1.433,8125 MiB; esses valores pertencem apenas ao
smoke pequeno descrito acima.

O LSTM sem fluxo possui 22.868 parâmetros; com fluxo, 23.380. Ambos
produziram saída 2×10×2 e gradientes finitos, com zero passos de otimização.
O YOLOv8n de três classes produziu saída bruta 1×7×336; RAFT small produziu
128×128×2 valores finitos. Não foram calculadas métricas de qualidade.

Recibo local: `data/derived/project_audits/learned_environment/20260911_validation_v1.json`.
SHA256: `29414ce0667c40ccd23e317cc86c07b6ed048e2efa249d968fb60c3fa907312b`.
SHA256 do lock: `ff379dca5a9face930c9e3a1c878f98ad5f01e895b9b2655c164d96714eeafff`.
O recibo de instalação `20260911_installation_provenance.json`, na mesma
pasta, liga os dois relatórios de instalação e seus hashes ao smoke. O
verificador tem SHA256 `546e3c6e0e9c4004820fbb51f14bc3307c788a65424c8382f599921e0bfad7b9`.
Esta conferência de engenharia ocorreu com alterações locais ainda não
commitadas; o recibo preserva esse estado e o HEAD `a924fe5`. O commit
posterior que registra o ambiente não altera retroativamente a proveniência.
