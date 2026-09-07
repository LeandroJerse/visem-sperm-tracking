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

Para retomar o threshold: [T200/o1/c2](detection/threshold/t200_o1_c2.yaml),
[T190/o1/c1](detection/threshold/t190_o1_c1.yaml) e
[T200 congelado](frozen/detection/threshold/t200_o1_c2.yaml).

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

Configuração congelada atual:

- `frozen/detection/threshold/t200_o1_c2.yaml` — selecionada na validação dos
  vídeos 14, 19, 36 e 52; a execução confirmatória no teste ainda não ocorreu.

Limitação: o piloto exploratório antigo examinou três frames de cada um dos 20
vídeos, incluindo `24, 38, 47, 54`. Assim, o holdout atual não é totalmente
cego, embora nenhuma bateria confirmatória com a configuração congelada tenha
sido executada. O legado não participa da seleção atual e a confirmação 5-fold
deve acompanhar obrigatoriamente o resultado isolado.
