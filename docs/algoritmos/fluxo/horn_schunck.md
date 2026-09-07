# Horn–Schunck

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [horn_schunck.py](../../../src/flow/classical/horn_schunck.py) — `HornSchunckFlow` |
| Configuração | [YAML de desenvolvimento](../../../configs/flow/horn_schunck/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#3-movimento-aparente-por-fluxo) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/flow/README.md) · [Área de resultados promovidos](../../../data/results/flow/README.md) |

O registro aceita `horn_schunck` e o alias `hs`; a configuração usa o nome completo.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e implementação

Minimiza globalmente a soma entre erro de constância de brilho e suavidade do
campo. `alpha` controla esse compromisso. A implementação NumPy usa derivadas
simétricas, média ponderada dos oito vizinhos e a atualização iterativa clássica.
Uma tolerância opcional encerra convergência cedo sem mudar a função objetivo.

## Parâmetros a testar

- `alpha`: 0,02, 0,05, 0,08, 0,15 e 0,30 em imagens normalizadas;
- `iterations`: 50, 100, 150 e 300;
- `tolerance`: 0, 1e-5, 1e-4 e 1e-3.

## Pontos fortes

- Formulação matemática simples, global e interpretável.
- Campo denso mesmo em regiões com pouca textura.
- Baseline independente de OpenCV e de treinamento.

## Pontos fracos e falhas esperadas

- A versão clássica é single-scale e pressupõe deslocamentos pequenos.
- A regularização pode espalhar movimento das células pelo fundo.
- Muitas iterações elevam custo; `alpha` alto suaviza movimento real.
- Fronteiras de movimento e oclusões violam a suavidade global.

## Custo e decisão

CPU, nenhum treino, custo proporcional a pixels × iterações. Deve permanecer
como baseline clássico mesmo se não entrar na fronteira de Pareto. Resultado:
**pendente**.
