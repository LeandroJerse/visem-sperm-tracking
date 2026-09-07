# SORT

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [sort.py](../../../src/tracking/classical/sort.py) — `SortTracker` · [Filtro de Kalman](../../../src/tracking/kalman.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/tracking/sort/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#2-tracking) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/tracking/README.md) · [Área de resultados promovidos](../../../data/results/tracking/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Definição

Implementação clássica e transparente do princípio SORT:

1. cada track prevê a próxima caixa com um filtro de Kalman de velocidade
   constante;
2. calcula-se IoU entre caixas previstas e detecções;
3. o algoritmo Húngaro minimiza `1 - IoU`;
4. pares abaixo de `iou_threshold` são rejeitados;
5. tracks ausentes sobrevivem por até `max_age` e novas detecções criam IDs.

O estado é `(cx, cy, w, h, vx, vy, vw, vh)`. A forma direta preserva
estabilidade numérica em caixas pequenas melhor que parametrizar área e razão de
aspecto. O filtro usa a atualização de covariância na forma de Joseph.

## Parâmetros

| Parâmetro | Função |
|---|---|
| `iou_threshold` | sobreposição mínima da associação |
| `max_age` | tolerância a detecções ausentes |
| `min_hits` | observações para confirmação |
| `process_noise` | liberdade do modelo de movimento |
| `measurement_noise` | confiança relativa nas caixas do detector |
| `emit_predictions` | inclui caixas não observadas na saída |

Para caixas pequenas, iniciar `iou_threshold` em 0,01, 0,05, 0,10, 0,20 e 0,30.
O valor não deve ser copiado de benchmarks de pedestres sem validação.

## Pontos fortes

- baixo custo e execução online;
- previsão reduz dependência da posição no frame anterior;
- tolera desaparecimentos curtos;
- baseline clássico amplamente compreendido.

## Pontos fracos

- velocidade constante é uma aproximação limitada para motilidade errática;
- IoU pode zerar rapidamente para caixas pequenas;
- sem aparência, cruzamentos ainda causam troca de ID;
- previsões durante falhas podem virar falsos positivos se avaliadas sem cuidado.

## Decisões experimentais

- O baseline ignora qualquer `flow` recebido pela API.
- A saída padrão não emite caixas preditas durante falhas.
- Avaliar primeiro com boxes GT para medir o tracker sem ruído de detecção.
- Registrar separadamente resultados observados e resultados com
  `emit_predictions=True`.

Status: implementação NumPy e cruzamento sintético concluídos; avaliação VISEM
pendente.
