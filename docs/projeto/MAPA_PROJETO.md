# Mapa vivo do projeto

Atualizado em 2026-08-31. Este é o ponto de entrada para retomar o TCC depois
de uma pausa. O fluxo científico está em
[`docs/metodologia/PROTOCOLO.md`](../metodologia/PROTOCOLO.md) e a situação de
cada método está na
[`MATRIZ_EXPERIMENTOS.md`](MATRIZ_EXPERIMENTOS.md).

Para localizar uma implementação, abra o
[mapa do código](../../src/README.md). O
[catálogo de algoritmos](../algoritmos/README.md) explica os métodos, e os
[comandos oficiais](../../script/README.md) indicam como iniciar cada etapa.

## 1. Pergunta e pipeline

O trabalho compara qualidade, custo computacional e esforço de implementação
de algoritmos clássicos, aprendidos e híbridos para quatro tarefas:

```text
vídeo → detecção → tracking → trajetória observada → predição
           └──────────── movimento aparente por fluxo ───────┘
```

A hipótese central é verificar se o fluxo óptico melhora tracking e/ou predição
de trajetória. Como não há ground truth físico da corrente, o fluxo estimado é
descrito como **movimento aparente da imagem**.

## 2. Quais dados servem para quê

```text
20 vídeos VISEM-Tracking anotados
  ├─ treino (12): 11 12 13 15 21 22 23 29 30 35 60 82
  ├─ validação (4): 14 19 36 52
  └─ teste bloqueado (4): 24 38 47 54
          ↓ configuração congelada + confirmação 5-fold
65 vídeos VISEM sem tracking manual
          ↓ aplicação; sem alegação de acurácia contra IDs inexistentes
```

Os vídeos anotados são o gabarito quantitativo. Os 502 clipes derivados não são
novas amostras independentes. As 174 lacunas de labels do vídeo 23 ficam fora
de treino e métricas e nunca são tratadas como frames negativos.

O formato e a política de alinhamento estão em
[`docs/dados/FORMATO_VISEM.md`](../dados/FORMATO_VISEM.md).

## 3. Mapa dos diretórios

| Caminho | Responsabilidade | Pode conter resultados científicos? |
|---|---|---:|
| `data/sources/` | Datasets externos originais; somente leitura | não |
| `data/manifests/` | Inventário, hashes, splits, folds, lacunas e migração | metadados |
| `data/datasets/` | Definições derivadas, como listas oficiais do YOLO | não |
| `data/derived/` | Frames convertidos, caches e outros intermediários recriáveis | não |
| `data/tests/` | Smoke, buscas, pilotos e validação por algoritmo/configuração | sim, evidência experimental |
| `data/results/` | Teste de configurações congeladas e aplicação final | sim, resultado promovido |
| `data/models/` | Pesos externos ou modelos exportados; não métricas | não |
| `data/catalog/` | Cópia SQLite derivada de CSVs e manifests | não |
| `data/quarantine/` | Arquivos preservados fora do fluxo ativo para revisão manual | não |
| `src/` | Biblioteca importável; implementação por tarefa e família | não |
| `script/` | Executores e lotes separados em `test/` e `application/` | não |
| `tests/` | Testes automatizados sintéticos e de integração do código | não |
| `configs/` | Parâmetros de busca e cópias congeladas | configuração |
| `docs/` | Metodologia, operação, dados e fichas científicas | documentação |
| `monografia/` | Fonte LaTeX oficial e entregas acadêmicas | texto acadêmico |

As antigas raízes `results/`, `output/`, `tmp/` e `notebooks/` não fazem mais
parte do layout. Resultados experimentais ficam exclusivamente em `data/`;
arquivos temporários descartáveis devem usar o diretório temporário do sistema.

### Organização de código

Cada tarefa em `src/` separa, quando aplicável:

```text
src/<tarefa>/
├── classical/       baseline clássico sem melhorias escondidas
├── modern/          método moderno sem mistura com híbridos (quando aplicável)
├── hybrid/          adaptação clássica/neural explicitamente nomeada
├── learned/         modelos que dependem de treino ou pesos
├── pipeline.py      contrato de aplicação reutilizável
└── README.md        mapa técnico do módulo
```

Código reutilizável não deve ficar em scripts de lote. Um híbrido nunca
substitui silenciosamente o clássico: ambos preservam nomes, configurações,
fichas e resultados próprios.

### Organização dos testes experimentais

```text
data/tests/<tarefa>/<algoritmo>/<configuração>/<etapa>/<run_id>/
```

Exemplos de `<etapa>`: `smoke`, `search`, `refinement`, `validation` e `pilot`.
Uma pasta de configuração usa um nome legível e um hash, evitando a ambiguidade
de diretórios como `teste_final_2`. Cada run guarda config resolvida, seed,
commit, ambiente, hardware, status, métricas e artefatos sem sobrescrever outra.

### Organização dos resultados promovidos

```text
data/results/<tarefa>/<algoritmo>/<configuração>/<teste-ou-aplicação>/<run_id>/
```

Somente configurações congeladas entram aqui. Buscas e validações permanecem em
`data/tests/`, mesmo quando obtêm um número alto. Os 65 vídeos sem anotação são
marcados como `application`, nunca como `test`.

`selection/` é um registro de promoção sem execução e, por isso, não possui
`run_id`; ele apenas referencia as runs de validação e o YAML congelado.

### Organização dos scripts

```text
script/<tarefa>/
├── test/             smoke, busca, refinamento, validação e avaliação
└── application/      execução de configuração já congelada
```

Os comandos e entradas oficiais ficam em
[`script/README.md`](../../script/README.md).

## 4. Estado científico recuperado

- O threshold piloto selecionou `T=200, abertura=1, fechamento=2`; a alternativa
  `T=190, abertura=1, fechamento=1` prioriza recall.
- A exploração histórica anterior usou frames dos 20 vídeos, inclusive os
  quatro hoje reservados ao teste. Portanto, o holdout não é completamente
  cego; essas 120 observações estão rotuladas como legado e não são usadas na
  seleção atual. O que permanece pendente é a execução **confirmatória** da
  configuração congelada, reforçada depois pela confirmação 5-fold.
- As duas configurações já foram executadas integralmente nos vídeos de
  validação `14, 19, 36, 52`. Pela média macro por vídeo, T200 apresentou
  melhor F1 e menor erro de contagem; T190 manteve recall maior. T200 está
  formalmente congelado; o teste confirmatório ainda não foi executado.
- O YOLO de 100 épocas é piloto: o melhor desempenho ocorreu cedo e o restante
  do treino mostrou overfitting. Ele será refeito no split oficial, com early
  stopping e três seeds.
- Detectores, trackers, estimadores de fluxo e preditores já têm esqueletos e
  testes sintéticos, mas isso não os torna vencedores no VISEM.

O histórico detalhado de execuções e decisões está no
[`DIARIO.md`](DIARIO.md).

## 5. Handoffs entre módulos

```text
run de detecção
  detections.csv + frame_metrics.csv
        ↓
run de tracking
  tracks.csv + tracks_mot.txt
        ↙                         ↘
cache de fluxo (.npz)       avaliação MOT oficial
        ↓
tracks enriquecidas com flow_u/flow_v
        ↓
run de predição
  predictions.csv + window_metrics.csv
        ↓
agregação por vídeo + estatística pareada + Pareto
```

Um vetor de fluxo ausente permanece inválido, não zero. Tracking usa o universo
de frames anotados para distinguir um frame vazio de uma lacuna. Janelas de
predição não atravessam vídeo, ID, split nem interrupção da trajetória.

## 6. Como retomar sem se perder

1. Verifique a próxima célula pendente na matriz.
2. Leia a ficha do algoritmo em `docs/algoritmos/`.
3. Trabalhe somente no split permitido pela etapa.
4. Execute smoke, busca e refinamento sem promover saídas manualmente.
5. Compare duas finalistas em validação completa por vídeo.
6. Registre a decisão e congele a configuração.
7. Abra o teste uma única vez; depois produza a confirmação 5-fold.
8. Só então execute a aplicação nos 65 vídeos sem tracking.

Documentos particulares eventualmente isolados em `data/quarantine/` não são
parte do TCC nem instrução vigente. A fonte acadêmica válida é sempre
`monografia/`.
