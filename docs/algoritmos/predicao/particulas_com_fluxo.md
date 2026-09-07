# Filtro de Partículas com fluxo

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [particle_filter_with_flow.py](../../../src/prediction/hybrid/particle_filter_with_flow.py) — `FlowAwareParticleFilterPredictor` · [Filtro de partículas reutilizado](../../../src/prediction/classical/particle_filter.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/flow_aware_particle_filter/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

A variante reutiliza o filtro de partículas e adiciona a compensação pelo fluxo; os dois métodos mantêm configurações separadas.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Ideia e hipótese

`FlowAwareParticleFilterPredictor` estima partículas no referencial compensado
pelo fluxo e recompõe o deslocamento ambiental na saída.

## Pontos fortes

- Representa dinâmica residual não linear e distribuições multimodais.
- Pode manter hipóteses alternativas em trajetórias erráticas.
- A seed torna cada repetição auditável.

## Pontos fracos

- Custo cresce com a quantidade de partículas e os horizontes.
- Ruído de fluxo, processo e medição interagem e aumentam a calibração.
- Degeneração/resampling podem dominar qualquer ganho ambiental.

## Parâmetros e decisão

Testar partículas, ruídos e limiar de resampling com seeds 42, 123 e 2026,
sempre pareado ao mesmo filtro sem fluxo. Reportar ADE/FDE, variabilidade,
latência e memória. Resultado: **pendente**.
