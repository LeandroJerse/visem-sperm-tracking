# LSTM com fluxo histórico

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [lstm_with_flow.py](../../../src/prediction/hybrid/lstm_with_flow.py) — `FlowAwareLSTMPredictor` · [Rede e treino compartilhados](../../../src/prediction/learned/lstm.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/flow_aware_lstm/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

O arquivo da variante é curto porque herda a LSTM e ativa `use_flow=True`; a rede, o treino e a inferência estão em `learned/lstm.py`.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia e hipótese

`FlowAwareLSTMPredictor` concatena `(u,v)` histórico aos deslocamentos `(dx,dy)`.
Ele nunca recebe fluxo futuro durante a inferência operacional. Arquitetura,
janelas, otimizador, hiperparâmetros e seeds devem ser idênticos aos da LSTM
sem fluxo; somente as duas features adicionais mudam.

## Pontos fortes

- Aprende quanto usar ou ignorar o fluxo, sem impor soma rígida.
- Modela relações temporais não lineares e múltiplos horizontes.
- É a ablação aprendida diretamente ligada à hipótese principal.

## Pontos fracos

- Pode memorizar ruído e aumentar variância/overfitting.
- Requer geração, armazenamento e alinhamento de fluxo além do treino neural.
- Um ganho aparente desaparece se dados/seeds não forem rigorosamente pareados.

## Parâmetros e decisão

Usar exatamente a grade, early stopping e seeds da LSTM pura. Comparar por
vídeo em trajetórias GT e fim a fim, reportando ADE/FDE, épocas, GPU-horas,
VRAM e checkpoint. Resultado: **pendente**.
