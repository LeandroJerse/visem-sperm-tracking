# Farneback

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [farneback.py](../../../src/flow/classical/farneback.py) — `FarnebackFlow` |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/farneback/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

O [contrato causal v1](../../metodologia/FLUXO_CAUSAL_V1.md) registra o primeiro
smoke do protocolo atual: uma configuração fixa, treinos 11/12, quadros 0..19.
Sua execução e conferência serão registradas após os testes. O espaço de busca
legado não foi executado nesta etapa.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e implementação

Aproxima vizinhanças por polinômios quadráticos e estima como a transformação
desses polinômios explica o deslocamento. Pirâmides tratam escalas diferentes.
`FarnebackFlow` preserva o algoritmo do OpenCV e retorna campo denso; a máscara
apenas define quais vetores podem entrar na análise.

## Parâmetros a testar

- `levels`: 3, 4 e 5; `pyr_scale`: 0,5;
- `winsize`: 15, 21 e 31;
- `iterations`: 3, 5 e 7;
- `poly_n/poly_sigma`: 5/1,1 e 7/1,5;
- janela gaussiana ligada e desligada.

## Pontos fortes

- Denso, rápido, sem treino e disponível no OpenCV.
- Bom compromisso inicial entre cobertura e custo.
- Fácil de armazenar e amostrar ao longo de trajetórias.

## Pontos fracos e falhas esperadas

- Mistura movimento de câmera, células, detritos e fundo.
- Janelas grandes suavizam fronteiras; pequenas amplificam ruído.
- Violações de constância de brilho e grandes deslocamentos degradam o campo.
- Um campo visualmente suave não garante movimento fisicamente correto.

## Custo e decisão

CPU, memória linear no número de pixels e nenhum treino. É o estimador-base do
híbrido, mas seu resultado puro será preservado para comparação. Promover pela
combinação de erro fotométrico, consistência e latência. Resultado: **pendente**.
