# Configurações experimentais

[Início](../README.md) · [Mapa do código e dos métodos](../src/README.md)
· [Comandos oficiais](../script/README.md)

## Encontre a configuração

| Tarefa | Parâmetros | Código e explicação de cada método |
|---|---|---|
| Detecção | [detection/](detection/) | [Guia da detecção](../src/detection/README.md) |
| Tracking | [tracking/](tracking/) | [Guia do tracking](../src/tracking/README.md) |
| Fluxo | [flow/](flow/) | [Guia do fluxo](../src/flow/README.md) |
| Predição | [prediction/](prediction/) | [Guia da predição](../src/prediction/README.md) |
| Divisões de vídeos | [protocol/splits.yaml](protocol/splits.yaml) | [Protocolo](../docs/metodologia/PROTOCOLO.md) |
| Configurações congeladas | [frozen/README.md](frozen/README.md) | [Matriz experimental](../docs/projeto/MATRIZ_EXPERIMENTOS.md) |

Registros históricos do threshold a 15 px: [T200/o1/c2](detection/threshold/t200_o1_c2.yaml),
[T190/o1/c1](detection/threshold/t190_o1_c1.yaml) e
[T200 congelado](frozen/detection/threshold/t200_o1_c2.yaml).

## Avaliação de detecção aprovada em 07/09/2026

O bloco `evaluation` de [splits.yaml](protocol/splits.yaml) registra
`center_distance_v3_individuals_ignore_clusters_10px`: F1 por centros dos
indivíduos 0/2 a 10 px como critério principal, 15/20 px como sensibilidades
e política `individuals_ignore_clusters`. Os pixels são medidos na resolução original.
Os `search.yaml` da detecção e os padrões dos executores usam essa definição.
As divisões de vídeos, os parâmetros dos detectores e seus espaços de busca
não foram modificados por esta decisão. As regras de agrupamentos e a
avaliação complementar estão em
[Classes e agrupamentos](../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md).
O plano prospectivo [search_v3.yaml](detection/threshold/search_v3.yaml)
registra a amostra, as 171 combinações, o orçamento e os critérios antes da
busca. Leia a [justificativa](../docs/metodologia/BUSCA_THRESHOLD_V3.md).
Esse plano tem executor próprio; o `search.yaml` anterior permanece histórico.
O [refinement_v3.yaml](detection/threshold/refinement_v3.yaml) vincula a
execução do refinamento aos hashes da busca grossa e dos 117 candidatos
derivados. Registra o novo benchmark e orçamento sem reescrever o plano-base
ou invalidar o cache; os dois finalistas continuam candidatos de treino.

O [validation_v3.yaml](detection/threshold/validation_v3.yaml) fixa as duas
finalistas por hash e os quatro vídeos completos, com 5.850 quadros cada
candidato, critérios, ordem e orçamento próprios. Possui executor estrito
separado e não substitui uma configuração congelada. Leia o
[protocolo prospectivo](../docs/metodologia/VALIDACAO_THRESHOLD_V3.md).

O [smoke v3](detection/threshold/protocol_smoke_v3.yaml) fixa T200/o1/c2 em
três quadros dos vídeos de treino 11 e 12 para verificar o contrato. Ele não
seleciona parâmetros, não é configuração congelada e não promove o detector.

Os YAMLs nomeados T190/T200 acima e o arquivo congelado permanecem exatamente
como registrados, com 15 px principal e 10/20 px de sensibilidade. Carregá-los
explicitamente no executor geral reproduz a definição histórica; não os use
como configuração da nova avaliação. Nenhuma configuração de threshold foi
promovida a 10 px. Fundamentação e limites estão na
[decisão sobre tolerância espacial](../docs/metodologia/TOLERANCIA_ESPACIAL.md).

## Como ler os YAMLs

Cada algoritmo possui sua própria pasta. Arquivos `search.yaml` descrevem a
configuração inicial e o espaço de busca; candidatos nomeados ficam na pasta do
algoritmo. Somente arquivos copiados para `frozen/` podem abrir o teste.

```text
configs/
├── protocol/splits.yaml
├── detection/<algoritmo>/*.yaml
├── tracking/<algoritmo>/search.yaml
├── flow/<algoritmo>/search.yaml
├── prediction/<algoritmo>/search.yaml
└── frozen/<domínio>/<algoritmo>/<configuração>.yaml
```

Todo YAML executável declara `configuration_id`. A pasta de uma run combina
esse nome curto com um hash científico calculado sem vídeo, split, seed ou
estágio. Assim, todos os vídeos da mesma configuração ficam juntos, enquanto a
configuração resolvida completa continua registrada no manifesto de cada run.

Configuração congelada histórica, sob avaliação a 15 px:

- `frozen/detection/threshold/t200_o1_c2.yaml` — selecionada na validação dos
  vídeos 14, 19, 36 e 52; a execução confirmatória no teste ainda não ocorreu.

Limitação: o piloto exploratório antigo examinou três frames de cada um dos 20
vídeos, incluindo `24, 38, 47, 54`. Assim, o holdout atual não é totalmente
cego, embora nenhuma bateria confirmatória com a configuração congelada tenha
sido executada. O desenho da nova seleção e avaliação, incluindo folds,
continua pendente. Redistribuir os mesmos vídeos não desfaz a influência
das explorações anteriores na escolha de parâmetros.

## Linha de base v3 e trajetórias individuais

- [T218/o0/c2 v3](frozen/detection/threshold/t218_o0_c2_v3.yaml): parâmetros
  fixos para desenvolvimento; teste/folds não liberados. A seleção original
  e os hashes da conferência permanecem registrados.
- [Referência individual v1](protocol/individual_trajectories_v1.yaml): coorte
  de treino, regras de segmentação, histórico 20, futuro 10 e orçamento,
  registrados antes da preparação. Não é configuração de um preditor.
