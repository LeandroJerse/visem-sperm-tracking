# Lucas–Kanade piramidal

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [lucas_kanade.py](../../../src/flow/classical/lucas_kanade.py) — `LucasKanadeFlow` |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/lucas_kanade/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

O registro aceita `lucas_kanade` e o alias `lk`; a configuração usa o nome completo.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e implementação

Estima um deslocamento local que minimiza o erro de brilho em uma janela,
assumindo movimento aproximadamente constante nela. A pirâmide permite tratar
deslocamentos maiores. A implementação detecta cantos, rastreia nos dois
sentidos e rejeita pontos cujo erro forward/backward excede o limite. A saída é
deliberadamente esparsa; pixels sem ponto rastreado ficam inválidos.

## Parâmetros a testar

- `max_corners`: 500, 1200 e 2500;
- `quality_level`: 0,001, 0,005 e 0,01;
- `min_distance`: 3, 5 e 7 px;
- `win_size`: 15, 21 e 31 px;
- `max_level`: 2, 3 e 4;
- `forward_backward_threshold`: 0,5, 1,0 e 1,5 px.

## Pontos fortes

- Muito rápido quando poucos pontos representam a cena.
- A máscara de validade torna explícito onde existe medição.
- O teste bidirecional elimina muitos rastreamentos incorretos.

## Pontos fracos e falhas esperadas

- Não produz diretamente um campo denso.
- Regiões uniformes não oferecem pontos rastreáveis.
- Oclusões, desfoque, baixa textura e deslocamento além da pirâmide causam perda.
- Pontos em células medem a célula, não o fundo; por isso a máscara é essencial.

## Custo e decisão

Não exige treino e usa somente CPU/OpenCV. Promover se mantiver cobertura útil,
boa consistência bidirecional e latência inferior aos métodos densos. Resultado:
**pendente**.
