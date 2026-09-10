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
Execução em `16eecbb` concluída e conferida: 40 quadros, 68 janelas e 1.292
amostras históricas válidas. O QA aprovado após a correção de esquema em
`0fccda8` conferiu 190 arquivos, sem repetir o estimador. Consulte resultados,
custos, limites e hashes no contrato. O espaço de busca legado não foi
executado nesta etapa; a hipótese de ganho na predição continua pendente.

O [benchmark compacto do nível 8a](../../metodologia/FLUXO_COMPACTO_V1.md)
foi concluído em `6110c44` e conferido independentemente: 720 quadros dos
12 treinos, 10.848 janelas e 15.762 amostras distintas válidas. Sua projeção
de tempo (134,21 min) ultrapassa o teto de 120 min; a extração completa
permanece bloqueada. O próximo ajuste deve medir as parcelas do laço e
preservar os parâmetros científicos. Isso não avalia o preditor ou a hipótese.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e implementação

Aproxima vizinhanças por polinômios quadráticos e estima como a transformação
desses polinômios explica o deslocamento. Pirâmides tratam escalas diferentes.
`FarnebackFlow` preserva o algoritmo do OpenCV e retorna campo denso; a máscara
apenas define quais vetores podem entrar na análise.

## Espaço legado previsto — ainda não executado

- `levels`: 3, 4 e 5; `pyr_scale`: 0,5;
- `winsize`: 11, 15, 21 e 31;
- `iterations`: 3, 5 e 7;
- `poly_n`: 5 e 7; `poly_sigma`: 1,1, 1,3 e 1,5, em listas independentes;
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
híbrido, mas seu resultado puro será preservado para comparação. O smoke
causal está concluído; busca, ablação e avaliação científica ampliada seguem
**pendentes**, sob plano próprio. Fotometria, consistência e custo são
diagnósticos complementares; não usar um placar subjetivo ou interpretá-los
como prova de ganho em ADE/FDE.
