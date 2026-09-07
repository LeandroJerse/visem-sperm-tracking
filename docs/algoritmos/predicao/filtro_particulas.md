# Filtro de Partículas

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [particle_filter.py](../../../src/prediction/classical/particle_filter.py) — `ParticleFilterPredictor` |
| Configuração | [YAML de desenvolvimento](../../../configs/prediction/particle_filter/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#4-predição) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/prediction/README.md) · [Área de resultados promovidos](../../../data/results/prediction/README.md) |

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Teoria e versões

Representa a distribuição do estado `[x, y, vx, vy]` por partículas. Cada passo
propaga movimento e ruído, pondera pela observação e faz resampling sistemático
quando o tamanho efetivo cai. A versão `flow_aware` opera em coordenadas sem o
movimento ambiental e o recompõe no futuro. A semente reinicia a cada chamada,
garantindo repetibilidade da mesma trajetória.

## Parâmetros a testar

- partículas: 250, 500, 1000 e 2000;
- ruído de posição: 0,1, 0,35 e 1 px;
- ruído de velocidade: 0,05, 0,15 e 0,5 px/frame;
- ruído de medição calibrado pelo tracker;
- resampling em ESS de 0,3, 0,5 e 0,7 do total.

## Pontos fortes

- Pode representar distribuições não gaussianas e dinâmica não linear futura.
- Produz covariância empírica e aceita extensões de movimento.
- Resampling sistemático tem baixa variância e custo linear.

## Pontos fracos e falhas esperadas

- O modelo implementado ainda usa velocidade aproximadamente constante; o
  ganho sobre Kalman virá da distribuição, não de uma dinâmica mágica.
- Muitas partículas elevam custo; poucas causam empobrecimento.
- Hiperparâmetros e sementes afetam resultados.

## Custo e decisão

CPU proporcional a partículas × frames × trajetórias, sem treino. Registrar as
três sementes e só promover se o ganho justificar o custo. Resultado:
**pendente**.
