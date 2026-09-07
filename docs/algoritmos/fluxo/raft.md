# RAFT

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [raft.py](../../../src/flow/learned/raft.py) — `RAFTFlow` |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/raft/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e implementação

RAFT constrói correlações entre todos os pares de pixels e atualiza o fluxo de
forma recorrente. O wrapper usa `torchvision`, pesos pré-treinados, RGB,
normalização oficial, padding múltiplo de 8 e o último refinamento da rede. O
carregamento é tardio: importar o projeto não exige PyTorch.

## Parâmetros a testar

- variante `small` e, se houver recursos, `large`;
- pesos oficiais fixos;
- precisão mista em GPU ligada/desligada;
- imagem integral versus blocos sobrepostos somente se faltar memória.

Não se deve usar RAFT com pesos aleatórios como resultado científico.

## Pontos fortes

- Representa deslocamentos grandes e padrões complexos.
- Campo denso com boa capacidade de generalização em benchmarks usuais.
- Pode funcionar como refinador independente no híbrido.

## Pontos fracos e falhas esperadas

- Alto uso de VRAM, latência e dependências.
- Possível diferença de domínio entre imagens naturais e microscopia VISEM.
- Pode confundir alterações de iluminação e objetos móveis com fluxo do fundo.
- Pesos externos precisam ser identificados e congelados na proveniência.

## Custo e decisão

Requer PyTorch; GPU é recomendada. Registrar VRAM, tempo, tamanho dos pesos e
eventual download. Promover somente se o ganho pareado superar claramente os
clássicos e justificar o custo. Resultado: **pendente**.
