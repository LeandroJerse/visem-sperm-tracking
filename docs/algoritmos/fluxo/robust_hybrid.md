# Fluxo híbrido robusto clássico/CPU

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [robust.py](../../../src/flow/hybrid/robust.py) — `RobustHybridFlow` |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/robust_hybrid/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

A classe também atende à variante com RAFT; este YAML usa Farneback e não ativa refinador neural.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Composição

`RobustHybridFlow` mantém cada baseline puro disponível e adiciona, em ordem:

1. estimativa-base, por padrão Farneback;
2. rejeição por consistência forward/backward;
3. nenhum refinador neural na configuração desta ficha;
4. estimação afim global com pontos LK e RANSAC;
5. subtração do movimento global da câmera;
6. máscara para impedir que células e artefatos contaminem a análise do fundo.

Quando a compensação está ligada, a saída é o **movimento residual aparente**.
A matriz afim removida fica nos metadados. O método não preenche regiões sem
evidência e não altera o resultado armazenado dos algoritmos puros.

## Parâmetros a testar

- base Farneback e, como análise adicional, Horn–Schunck;
- `consistency_threshold`: 0,5, 1,0, 1,5 e 2,0 px;
- compensação global ligada/desligada;
- máscara ligada/desligada;
- estimador-base e limiar de consistência;
- limiar RANSAC: 1, 2 e 3 px.

## Pontos fortes

- Separa explicitamente deriva global e movimento residual.
- Rejeita vetores incoerentes sem exigir treino ou GPU.
- Mantém proveniência de cada componente e permite ablações pareadas.

## Pontos fracos e falhas esperadas

- A compensação pode remover movimento real se quase toda a imagem se mover.
- RANSAC falha sem textura ou quando a maioria dos pontos pertence às células.
- A qualidade da máscara passa a ser parte do erro do sistema.

## Custo e decisão

Reportar cada ablação: puro, +consistência, +máscara e +compensação. A variante
com RAFT tem ficha/config própria; este híbrido só será promovido se melhorar
estabilidade ou erro sem custo desproporcional. Resultado: **pendente**.
