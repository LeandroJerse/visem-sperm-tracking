# Fluxo óptico — movimento aparente entre frames

[← Mapa do código](../README.md) · [Comandos de fluxo](../../script/README.md#3-movimento-aparente-por-fluxo) · [Estado dos experimentos](../../docs/projeto/MATRIZ_EXPERIMENTOS.md)

Recebe dois frames consecutivos e estima deslocamentos aparentes em pixels.
A convenção é `flow[y, x] = (u, v)`, do frame anterior para o seguinte.
Isso não mede velocidade física do fluido sem uma referência física correspondente.

## Onde está cada algoritmo

| Método | Implementação Python | Configuração de busca | Ficha científica |
|---|---|---|---|
| Lucas–Kanade piramidal esparso | [classical/lucas_kanade.py](classical/lucas_kanade.py) | [YAML](../../configs/flow/lucas_kanade/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/lucas_kanade.md) |
| Farneback denso | [classical/farneback.py](classical/farneback.py) | [YAML](../../configs/flow/farneback/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/farneback.md) |
| Horn–Schunck em escala única | [classical/horn_schunck.py](classical/horn_schunck.py) | [YAML](../../configs/flow/horn_schunck/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/horn_schunck.md) |
| RAFT pré-treinado | [learned/raft.py](learned/raft.py) | [YAML](../../configs/flow/raft/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/raft.md) |
| Híbrido robusto clássico | [hybrid/robust.py](hybrid/robust.py) | [YAML](../../configs/flow/robust_hybrid/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/robust_hybrid.md) |
| Híbrido robusto com RAFT | [hybrid/robust.py](hybrid/robust.py) + [learned/raft.py](learned/raft.py) | [YAML](../../configs/flow/robust_hybrid_raft/search.yaml) | [Ficha](../../docs/algoritmos/fluxo/robust_hybrid_raft.md) |

Lucas–Kanade e Farneback chamam implementações do OpenCV; Horn–Schunck contém
as atualizações numéricas em NumPy. RAFT é um adaptador de inferência do
torchvision, com normalização e ajuste das dimensões dos frames. A rede e seus
pesos são carregados somente ao executar a estimativa; importar o módulo ou
criar o objeto não testa a rede. Não há rotina própria de treino de RAFT aqui.

As duas configurações híbridas compartilham a mesma implementação. O refinamento
por RAFT é opcional. Quando habilitada, a compensação global remove um campo
afim e devolve movimento residual; essa escolha é registrada nos metadados.

## Arquivos compartilhados

| Arquivo | O que procurar nele |
|---|---|
| [base.py](base.py) | Contrato `estimate`, validação de frames e `FlowResult.valid`. A base abstrata não é um algoritmo pendente. |
| [registry.py](registry.py), [__init__.py](__init__.py) | Registro de nomes e importações públicas. |
| [pipeline.py](pipeline.py) | Leitura do vídeo, pares consecutivos, máscaras, configuração e registro da execução. |
| [metrics.py](metrics.py) | Erro após warp, consistência forward/backward, estabilidade e EPE. |
| [synthetic.py](synthetic.py) | Translações com deslocamento verdadeiro conhecido, apropriadas para EPE. |
| [cache.py](cache.py) | Escrita e leitura do campo `.npz`, índice e amostragem válida. |
| [Integração com trajetórias](../integration/README.md) | Como o cache gera `tracks_with_flow.csv` para a predição. |

## Pares de frames, resultados e verificação

O processamento e as métricas são por **par de frames**, não por imagem isolada.
`FlowResult.valid` identifica onde houve medida válida: zeros fora dessa máscara
não significam ausência de movimento. Máscaras de células podem excluir caixas
dos dois frames para avaliar o fundo; a amostragem em anel está em [cache.py](cache.py).

As execuções de desenvolvimento ficam em [data/tests/flow](../../data/tests/flow/),
por algoritmo, configuração, etapa e execução, com `pair_metrics.csv`, resumos,
metadados e manifesto. O cache opcional fica em
[data/derived/flow/cache](../../data/derived/flow/cache/), acompanhado de índice.
Por padrão, etapas finais de teste, folds e aplicação usam
[data/results](../../data/results/).

Os [testes de fluxo e predição](../../tests/integration/test_flow_prediction.py)
incluem verificações sintéticas e de interfaces. Código presente, teste sintético
e avaliação científica são evidências diferentes; consulte a
[matriz](../../docs/projeto/MATRIZ_EXPERIMENTOS.md) antes de afirmar que um método
está validado. EPE requer deslocamento verdadeiro conhecido.
Os [comandos oficiais](../../script/README.md#3-movimento-aparente-por-fluxo)
ficam em `script/README.md`.
