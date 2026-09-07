# Híbrido robusto com refinamento RAFT

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [robust.py](../../../src/flow/hybrid/robust.py) — `RobustHybridFlow` · [Refinador RAFT](../../../src/flow/learned/raft.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/robust_hybrid_raft/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

Usa o registro `robust_hybrid` com `refiner_method: raft`. A variante tem YAML próprio e compartilha a classe de composição com o híbrido CPU.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Composição

Esta variante usa o mesmo pipeline explícito de consistência, máscara e
compensação do híbrido clássico, mas funde Farneback com um campo RAFT
pré-treinado. Ela possui [configuração própria](../../../configs/flow/robust_hybrid_raft/search.yaml) e
nunca é acionada implicitamente pela configuração CPU.

## Pontos fortes

- Combina um baseline auditável com capacidade neural para movimentos maiores.
- Permite variar o peso do refinador e medir onde o RAFT realmente contribui.
- Mantém a saída dos algoritmos puros intacta para ablações pareadas.

## Pontos fracos

- Exige PyTorch, pesos, GPU/memória e pode precisar download inicial.
- A diferença de domínio pode introduzir vetores visualmente plausíveis porém
  inadequados à microscopia.
- Custo de duas estimativas e da fusão pode não justificar ganho pequeno.

## Parâmetros e decisão

Testar pesos de fusão 0,25/0,5/0,75, máscara e compensação ligadas/desligadas,
mantendo o Farneback base congelado. Reportar métricas reais de consistência e
custo, além de EPE apenas no sintético. Resultado: **pendente**.
