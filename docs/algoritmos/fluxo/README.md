# Mapa dos algoritmos de fluxo óptico

[Catálogo](../README.md) · [Código e contratos](../../../src/flow/README.md) · [Parâmetros](../../../configs/flow/) · [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) · [Ensaios](../../../data/tests/flow/README.md) · [Resultados promovidos](../../../data/results/flow/README.md)

Neste projeto, **fluxo óptico mede movimento aparente entre imagens**. Ele não é
uma medição física direta da velocidade do fluido. O campo segue a convenção
`flow[y, x] = (u, v)`: o ponto `(x, y)` no frame anterior é procurado em
`(x + u, y + v)` no próximo frame.

## Implementação

| Método | Natureza | Documento | Saída |
|---|---|---|---|
| Lucas–Kanade | clássico puro | [lucas_kanade.md](lucas_kanade.md) | esparsa |
| Farneback | clássico puro | [farneback.md](farneback.md) | densa |
| Horn–Schunck | clássico puro | [horn_schunck.md](horn_schunck.md) | densa |
| RAFT | rede pré-treinada | [raft.md](raft.md) | densa |
| Híbrido robusto CPU | clássico + consistência/compensação | [robust_hybrid.md](robust_hybrid.md) | densa/base |
| Híbrido robusto + RAFT | clássico + refinamento neural | [robust_hybrid_raft.md](robust_hybrid_raft.md) | densa |

Todos implementam `FlowEstimator.estimate(previous, next, mask=None)` e retornam
`FlowResult(flow, valid, confidence, metadata)`. A máscara usa `True` para a
região permitida. Para estimar o fundo, células e artefatos devem ser removidos
da máscara. Um vetor inválido jamais deve ser interpretado como movimento zero.

O módulo `cache.py` persiste campos com chave baseada em conteúdo e amostra
`u`, `v`, magnitude e direção nas trajetórias. Quando a célula foi mascarada,
`sample_background_flow` usa a mediana de um anel válido ao redor dela, em vez
de inventar fluxo zero. `metrics.py` implementa erro fotométrico após warp,
consistência forward/backward e EPE.

`synthetic.py` gera translações inteiras ou subpixel e o campo verdadeiro
correspondente para testes controlados, sem confundir esse EPE com dados reais.
`temporal_flow_change` mede mudança/estabilidade entre campos consecutivos; ela
é um descritor de aceleração aparente, não uma medida de acurácia.

## Protocolo

1. Testar pares sintéticos com translação conhecida e reportar EPE.
2. Em vídeos reais, reportar erro fotométrico, consistência temporal,
   consistência forward/backward, fração válida e tempo por frame.
3. Não reportar EPE real, pois o VISEM não fornece ground truth físico de fluxo.
4. Avaliar fluxo bruto e fluxo com máscara de células separadamente.
5. Congelar parâmetros na validação antes do teste isolado.

Na condição mascarada, cada campo `t -> t+1` usa a união das caixas de `t` e
`t+1`, expandida pela margem configurada. Isso evita que uma célula que mudou de
posição contamine apenas um sentido da estimativa. Forward e backward recebem
a mesma região permitida. O CSV, seu SHA-256, a fonte das caixas, o vídeo e a
margem fazem parte da proveniência e da chave de cache.

Resultados ainda não executados devem permanecer como `pendente`; esta pasta
documenta a hipótese e o protocolo, não antecipa conclusões.

`configs/flow/robust_hybrid/search.yaml` é a variante clássica executável em
CPU, sem refinador neural. `configs/flow/robust_hybrid_raft/search.yaml`
habilita RAFT explicitamente e exige
PyTorch/pesos; assim o custo neural nunca é acionado silenciosamente.

## Execução e artefatos

Use os [comandos oficiais de fluxo](../../../script/README.md#3-movimento-aparente-por-fluxo).
O [guia do módulo](../../../src/flow/README.md) detalha máscaras, cache e entradas.

A precedência é: defaults, YAML, flags explícitas e, por último, `--set`.
Chaves simples de `--set`, como `winsize=31`, entram em `params`; chaves
pontuadas, como `evaluation.compute_backward=false`, alteram a seção indicada.
O split de teste exige um YAML promovido em `configs/frozen/`, com a etapa e
o split de teste e `run.frozen: true`. A avaliação congelada processa o vídeo
completo, sem `--max-pairs`; os
[controles do protocolo](../../../script/README.md#0-verificação-antes-de-uma-bateria)
definem essas condições.

Cada execução cria uma pasta nova em
`data/tests/flow/<algoritmo>/<configuração>/<etapa>/<run_id>/`; somente
teste/OOF/aplicação congelados seguem para `data/results/`, contendo:

- `pair_metrics.csv`: tempo, erro fotométrico, cobertura, magnitude,
  consistência forward/backward e mudança temporal por par;
- `summary.json` e `summary.csv`: agregação e uso de RAM/VRAM;
- `metadata.json` e `manifest.json`: hash do vídeo, configuração resolvida,
  ambiente, seed e artefatos;
- `cache_index.csv`, somente quando o cache está ativo.

O cache pode ser controlado com `--cache/--no-cache` e `--cache-dir`. Sua chave
inclui hash do vídeo, frames, parâmetros, hash da implementação e configuração
da máscara. A CLI nunca calcula EPE em vídeo real; `epe_status` registra
explicitamente a ausência de ground truth. `--max-pairs` limita um smoke test
sem mudar a ordem dos pares.

O uso de detecções automáticas para excluir células está descrito no
[guia de máscaras do módulo](../../../src/flow/README.md).

## Ligação cache -> trajetória -> predição

`src.integration.enrich_tracks_with_flow` lê o `cache_index.csv` da run de
fluxo e cria um novo
CSV de tracks com `u`, `v`, magnitude, direção, validade e confiança. A opção
principal para fluxo de fundo é a mediana em anel; a amostragem direta fica como
controle quando o centro da célula permaneceu válido. Os comandos de
[enriquecimento de trajetórias](../../../script/README.md#3-movimento-aparente-por-fluxo)
ficam junto dos comandos de fluxo.

Ausência de cache ou amostra insuficiente produz `flow_valid=0` e campos
vetoriais vazios, nunca zero artificial. O `tracks.csv` original não é
sobrescrito e um `--output` preexistente é recusado.
