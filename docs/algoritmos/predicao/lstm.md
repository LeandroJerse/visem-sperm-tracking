# LSTM sem fluxo

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [lstm.py](../../../src/prediction/learned/lstm.py) — `LSTMPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/lstm/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Arquitetura

O modelo recebe a sequência de deslocamentos, não coordenadas absolutas. Isso
reduz dependência da posição no microscópio. A última saída recorrente passa por
uma cabeça que prevê diretamente deslocamentos para todos os passos até o
horizonte máximo. Normalização usa somente estatísticas do treino; Smooth L1,
AdamW, clipping de gradiente e early stopping estabilizam o ajuste.

`LSTMPredictor` recebe dois atributos por passo `(dx, dy)`. PyTorch só é
importado quando treino ou inferência são solicitados. A variante com fluxo tem
ficha própria para não esconder seu custo nem suas entradas adicionais.

## Parâmetros a testar após smoke test

- tamanho oculto: 32, 64 e 128;
- camadas: 1 e 2; dropout 0 e 0,2 quando houver duas camadas;
- learning rate: 3e-4 e 1e-3;
- batch: 64 e 128;
- sementes: 42, 123 e 2026.

## Pontos fortes

- Aprende padrões temporais não lineares e saídas de vários horizontes.
- A representação relativa reduz memorização espacial.
- Serve como baseline aprendido direto para a ablação com fluxo.

## Pontos fracos e falhas esperadas

- Requer volume de trajetórias, GPU para agilidade e controle de overfitting.
- Pode aprender viés de vídeos ou indivíduos se houver vazamento por janelas.
- Previsão direta não se adapta online a uma trajetória nova sem reexecução.

## Custo e decisão

Registrar épocas, tempo, VRAM, tamanho do checkpoint e variabilidade entre
sementes. Promover somente com ganho fora da amostra sobre Kalman e velocidade
constante. Resultado: **pendente**.
